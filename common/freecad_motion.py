"""Drive an existing slider with FreeCAD's native kinematic solver."""
from common.freecad_geometry import final_roots
from common.freecad_joints import measure_joint_references
from common.motion_evidence import summarize_frames


def _simulation(doc, joint, start, speed):
    # Native solver reads these properties; the GUI view providers are not
    # required. No authored constraints are deleted or replaced.
    simulation = doc.addObject("App::DocumentObjectGroup", "ProbeSimulation")
    for prop, value in (("aTimeStart", 0.), ("bTimeEnd", 1.), ("cTimeStepOutput", .25),
                        ("fGlobalErrorTolerance", 1e-6)):
        kind = "App::PropertyFloat" if prop.startswith("f") else "App::PropertyTime"
        simulation.addProperty(kind, prop)
        setattr(simulation, prop, value)
    motion = doc.addObject("App::FeaturePython", "ProbeMotion")
    motion.addProperty("App::PropertyXLinkSubHidden", "Joint")
    motion.Joint = (joint, [""])
    motion.addProperty("App::PropertyEnumeration", "MotionType")
    motion.MotionType = ["Angular", "Linear"]
    motion.MotionType = "Linear"
    motion.addProperty("App::PropertyString", "Formula")
    motion.Formula = f"({start:.12g})+({speed:.12g})*time"
    simulation.Group = [motion]
    return simulation


def measure_motion(doc):
    saved = measure_joint_references(doc)["joints"]
    sliders = [j for j in saved if j["type"] == "Slider"
               and j["connector_geometry"]["status"] == "measured"]
    roots, _ = final_roots(doc)
    assemblies = [r for r in roots if r.TypeId == "Assembly::AssemblyObject"]
    if len(assemblies) != 1 or len(sliders) != 1:
        return {"status": "unsupported", "reason": "expected one active assembly and one resolved slider"}
    root, driver = assemblies[0], sliders[0]
    start = driver["connector_geometry"]["axial_position_mm"]
    limits = driver["enabled_limits"]
    violation = driver["limits_at_saved_pose"].get("Length", {})
    if violation.get("status") == "inverted_bounds" or violation.get("outside_by", 0) > .01:
        return {"status": "saved_pose_outside_limits", "driver": driver["joint"],
                "saved_axial_mm": start, "limits": limits, "violation": violation}
    positive = limits.get("LengthMax", float("inf")) - start
    negative = start - limits.get("LengthMin", -float("inf"))
    delta = min(5., positive) if positive >= negative else -min(5., negative)
    if abs(delta) < .1:
        return {"status": "insufficient_travel", "saved_axial_mm": start, "limits": limits}
    simulation = _simulation(doc, doc.getObject(driver["joint"]), start, delta)
    code = root.generateSimulation(simulation)
    result = {"status": "solver_failed" if code != 0 else "sampled", "solver_code": code,
              "driver": driver["joint"], "saved_axial_mm": start, "requested_travel_mm": delta,
              "limits": limits, "frames": []}
    if code != 0:
        return result
    n = root.numberOfFrames()
    result["solver_frame_count"] = n
    indices = sorted({round(i * (n - 1) / 19) for i in range(20)}) if n else []
    for index in indices:
        if root.updateForFrame(index) not in (0, None):
            return {**result, "status": "frame_update_failed", "failed_frame": index}
        readings = measure_joint_references(doc)["joints"]
        result["frames"].append({"index": index, "joints": readings})
    result.update(summarize_frames(result["frames"], driver, delta))
    result["status"] = "sampled" if result["travel_verified"] else "travel_unverified"
    return result

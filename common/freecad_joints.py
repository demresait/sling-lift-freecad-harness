"""Measure saved FreeCAD joint connector frames without running the solver."""
from collections import Counter
import math
import re

from common.freecad_geometry import final_roots


def connector_residuals(first, second):
    """Relative connector coordinates; z is the FreeCAD joint axis."""
    import FreeCAD as App

    relative = first.inverse() * second
    p = relative.Base
    x = relative.Rotation.multVec(App.Vector(1, 0, 0))
    z = relative.Rotation.multVec(App.Vector(0, 0, 1))
    return {"origin_gap_mm": p.Length, "radial_gap_mm": math.hypot(p.x, p.y),
            "axial_position_mm": p.z,
            "axis_angle_deg": math.degrees(math.atan2(math.hypot(z.x, z.y), abs(z.z))),
            "axes_same_direction": z.z >= 0,
            "twist_deg": math.degrees(math.atan2(x.y, x.x)),
            "frame_angle_deg": math.degrees(relative.Rotation.Angle)}


def connector_geometry(obj, refs):
    # Use the same endpoint object resolution as the installed Assembly
    # workbench; a Body's feature/datum can be the connector coordinate frame.
    import UtilsAssembly

    placements = []
    for i, ref in enumerate(refs, 1):
        local = getattr(obj, f"Placement{i}", None)
        if local is None or not ref or not ref[0] or not ref[1] or "?" in ref[1][0]:
            return {"status": "unresolved", "reason": f"incomplete endpoint {i}"}
        target = UtilsAssembly.getObject(ref)
        subname = ref[1][0]
        # Datum paths end in a dot and may have no Part subshape. Validate
        # those through Assembly's object resolver, not a B-rep selection.
        topology = re.fullmatch(r"(?:Face|Edge|Vertex)\d+", subname.rsplit(".", 1)[-1])
        if target is None or (topology and ref[0].getSubObject(subname) is None):
            return {"status": "unresolved", "reason": f"endpoint {i} selection not found"}
        placements.append(UtilsAssembly.getGlobalPlacement(ref, target) * local)
    return {"status": "measured", "origins_mm": [list(p.Base) for p in placements],
            **connector_residuals(*placements)}


def limit_violations(limits, residuals):
    """Compare enabled limits with signed position in the first connector frame."""
    result = {}
    for kind, field in (("Length", "axial_position_mm"), ("Angle", "twist_deg")):
        if not any(kind + end in limits for end in ("Min", "Max")):
            continue
        lower = limits.get(kind + "Min", -math.inf)
        upper = limits.get(kind + "Max", math.inf)
        if lower > upper:
            result[kind] = {"status": "inverted_bounds"}
            continue
        value = residuals[field]
        # atan2 yields a principal angle; 360-degree equivalents may lie inside
        # the configured interval. This does not test which branch is reachable.
        values = (value - 360, value, value + 360) if kind == "Angle" else (value,)
        outside = min(max(lower - x, x - upper, 0.) for x in values)
        result[kind] = {"status": "measured", "position": value,
                        "outside_by": outside if outside > 1e-9 else 0.}
    return result


def measure_joint_references(doc):
    roots, _ = final_roots(doc)
    rows = []

    def visit(assembly, path, ancestors):
        if assembly.Name in ancestors:
            return
        members = {obj.Name: obj for obj in assembly.Group}
        joints = dict(members)
        for obj in members.values():
            if obj.TypeId == "Assembly::JointGroup":
                joints.update((joint.Name, joint) for joint in obj.Group)

        for obj in joints.values():
            if "JointType" not in obj.PropertiesList:
                continue
            refs = (getattr(obj, "Reference1", None), getattr(obj, "Reference2", None))
            endpoints = []
            for ref in refs:
                part = ref[0] if ref else None
                if part is None:
                    endpoints.append(None)
                else:
                    endpoints.append({"object": part.Name, "label": part.Label,
                                      "in_assembly": part.Name in members,
                                      "subelements": list(dict.fromkeys(ref[1]))})
            if getattr(obj, "Suppressed", False):
                status = "suppressed"
            elif not all(endpoints):
                status = "missing_endpoint"
            elif not all(e["in_assembly"] for e in endpoints):
                status = "endpoint_outside_assembly"
            elif endpoints[0]["object"] == endpoints[1]["object"]:
                status = "same_object"
            else:
                status = "distinct_member_references"
            limits = {}
            for prop in ("AngleMin", "AngleMax", "LengthMin", "LengthMax"):
                if getattr(obj, "Enable" + prop, False):
                    limits[prop] = float(getattr(obj, prop).Value)
            if status in ("suppressed", "same_object", "missing_endpoint"):
                frames = {"status": "not_measured", "reason": status}
            else:
                try:
                    frames = connector_geometry(obj, refs)
                except (AttributeError, IndexError, ImportError, RuntimeError, TypeError, ValueError) as exc:
                    frames = {"status": "unresolved", "reason": str(exc)}
            limits_at_pose = limit_violations(limits, frames) if frames["status"] == "measured" else {}
            rows.append({"assembly_path": path, "joint": obj.Name, "type": str(obj.JointType),
                         "endpoints": endpoints, "status": status, "enabled_limits": limits,
                         "connector_geometry": frames, "limits_at_saved_pose": limits_at_pose})

        for obj in members.values():
            if not getattr(obj, "Visibility", True):
                continue
            # Native AssemblyLink has its own copied components and joints.
            # Its LinkedObject is the prototype, not the solved occurrence.
            if obj.TypeId in ("Assembly::AssemblyObject", "Assembly::AssemblyLink"):
                visit(obj, path + "/" + obj.Name, ancestors | {assembly.Name})

    for root in roots:
        if root.TypeId == "Assembly::AssemblyObject":
            visit(root, root.Name, set())
    return {"counts": dict(Counter(row["status"] for row in rows)),
            "connector_counts": dict(Counter(row["connector_geometry"]["status"] for row in rows)),
            "joints": rows, "scope": "Saved connector residuals within a common placement frame; "
            "not a solver, contact, or motion verdict."}

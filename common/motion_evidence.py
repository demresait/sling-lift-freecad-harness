"""Summarize measured motion frames without interpreting a solver return as motion."""
from common.sling_joint_score import connection_key


def _key(joint):
    return joint["assembly_path"], joint["joint"]


def _difference_degrees(a, b):
    return abs((a - b + 180) % 360 - 180)


def summarize_frames(frames, driver, requested):
    readings = [{_key(j): j for j in frame["joints"]
                 if j["connector_geometry"]["status"] == "measured"} for frame in frames]
    driver_key = _key(driver)
    positions = [rows[driver_key]["connector_geometry"]["axial_position_mm"]
                 for rows in readings if driver_key in rows]
    travel = positions[-1] - positions[0] if len(positions) >= 2 else None
    start = driver["connector_geometry"]["axial_position_mm"]
    # Require both the recorded pose and the commanded end-to-end displacement.
    travel_verified = (travel is not None and len(positions) == len(frames)
                       and abs(positions[0] - start) <= .05
                       and abs(travel - requested) <= .05)
    maxima, axis_maxima, rotations, limit_violations = {}, {}, {}, []
    for frame, rows in zip(frames, readings):
        for key, joint in rows.items():
            g = joint["connector_geometry"]
            kind = joint["type"]
            if kind in ("Revolute", "Slider", "Cylindrical"):
                angle = g["axis_angle_deg"]
                if kind not in axis_maxima or angle > axis_maxima[kind]["angle_deg"]:
                    axis_maxima[kind] = {"angle_deg": angle, "joint": key[1],
                                         "assembly_path": key[0], "frame": frame["index"]}
            if kind in ("Fixed", "Revolute", "Ball", "Slider", "Cylindrical"):
                field = "radial_gap_mm" if kind in ("Slider", "Cylindrical") else "origin_gap_mm"
                gap = g[field]
                if kind not in maxima or gap > maxima[kind]["gap_mm"]:
                    maxima[kind] = {"gap_mm": gap, "field": field, "joint": key[1],
                                    "assembly_path": key[0], "frame": frame["index"]}
            if kind == "Revolute" and key in readings[0]:
                base = readings[0][key]["connector_geometry"]["twist_deg"]
                connection = connection_key(joint)
                rotations[connection] = max(rotations.get(connection, 0.), _difference_degrees(g["twist_deg"], base))
            for limit, value in joint.get("limits_at_saved_pose", {}).items():
                if value["status"] != "measured" or value["outside_by"] > .01:
                    limit_violations.append({"joint": key[1], "assembly_path": key[0],
                                             "frame": frame["index"], "limit": limit, **value})
    return {"measured_travel_mm": travel, "travel_verified": travel_verified,
            "driver_positions_mm": positions, "moving_revolute_count": sum(a > .1 for a in rotations.values()),
            "max_revolute_rotation_deg": max(rotations.values(), default=0.),
            "max_gap_by_joint_type": maxima, "max_axis_angle_by_joint_type": axis_maxima,
            "sampled_limit_violations": limit_violations,
            "unmeasured_joint_frames": sum(len(f["joints"]) - len(r) for f, r in zip(frames, readings))}

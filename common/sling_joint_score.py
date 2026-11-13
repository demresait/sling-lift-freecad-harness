"""Separate scores for sampled connector alignment and observed articulation."""


def _ramp(error, full, zero):
    return min(1., max(0., (zero - abs(error)) / (zero - full)))


def connection_key(row):
    ends = [e["object"] for e in row["endpoints"] if e]
    if len(ends) == 2 and ends[0] != ends[1]:
        # Object IDs identify repeated connections within one candidate only.
        return row["type"], *sorted(ends)
    return row["type"], row["assembly_path"], row["joint"]


def score_mating(saved, motion):
    """Check movable joints in the saved pose and every measured solver frame."""
    connections = {}
    poses = [saved, *(f["joints"] for f in motion.get("frames", []))]
    for index, rows in enumerate(poses):
        for row in rows:
            kind = row["type"]
            if kind not in {"Revolute", "Slider", "Cylindrical"} or row["status"] == "suppressed":
                continue
            g = row["connector_geometry"]
            if g["status"] != "measured":
                gap, angle, quality = None, None, 0.
            else:
                field = "origin_gap_mm" if kind == "Revolute" else "radial_gap_mm"
                gap, angle = g[field], g["axis_angle_deg"]
                quality = min(_ramp(gap, .1, 2.), _ramp(angle, 1., 10.))
            key = connection_key(row)
            if key not in connections or quality < connections[key]["quality"]:
                connections[key] = {"joint": row["joint"], "type": kind, "quality": quality,
                                    "gap_mm": gap, "axis_angle_deg": angle,
                                    "pose": "saved" if index == 0 else motion["frames"][index - 1]["index"]}
    details = list(connections.values())
    # A single aligned hinge is not sufficient evidence for a pantograph.
    # Four pivot connections permit implementations that combine two coaxial
    # reference joints into one. No reward for declaring extra duplicates.
    pivots = [c for c in details if c["type"] == "Revolute"]
    coverage = min(1., sum(p["gap_mm"] is not None for p in pivots) / 4.)
    score = coverage * sum(c["quality"] for c in details) / len(details) if details else 0.
    return {"score": score, "pivot_coverage": coverage, "connections": details}


def score_articulation(motion):
    """Credit verified travel and coupled rotation; alignment is scored separately."""
    verified = motion.get("status") == "sampled" and motion.get("travel_verified", False)
    travel = min(1., abs(motion["measured_travel_mm"]) / 5.) if verified else 0.
    # Allow tiny numerical roundoff in the solver's end positions.
    if travel >= .99:
        travel = 1.
    rotation = min(1., motion.get("moving_revolute_count", 0) / 2.)
    limits_ok = not motion.get("sampled_limit_violations", [])
    return {"score": travel * rotation if limits_ok else 0.,
            "status": motion.get("status", "not_run"), "verified_travel_credit": travel,
            "coupled_rotation_credit": rotation, "sampled_limits_ok": bool(verified and limits_ok)}

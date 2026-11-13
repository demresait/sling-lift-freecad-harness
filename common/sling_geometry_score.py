"""Sling-lift geometry rubric. Pure Python policy over measured solids."""
from common.geometry_compare import compare_geometry

FULL_ERROR = 0.01
ZERO_ERROR = 0.20
MAX_DRAWING_PINS = 2


def is_optional_pin(solid):
    """Recognize the supplied 6 x 16 spring-pin family by geometry.

    The measured outside diameter of the supplied model is 6.7 mm. The
    allowed envelope includes nominal 6 mm and hollow/slotted variants.
    This is a limited compatibility allowance, not an ISO compliance test.
    """
    radii = solid.get("cylinder_radii_mm", [])
    span = solid.get("pin_axis_vertex_span_mm")
    return (span is not None and 15.5 <= span <= 16.5 and bool(radii)
            and 2.9 <= max(radii) <= 3.45
            and any(1.8 <= r <= 2.6 for r in radii)
            and 120 <= solid["volume_mm3"] <= 400)


def geometry_score(reference, candidate):
    comparison = compare_geometry(reference, candidate)
    ref = {s["id"]: s for s in reference["solids"]}
    cand = {s["id"]: s for s in candidate["solids"]}
    volume = sum(s["volume_mm3"] for s in ref.values())
    count = len(ref)

    def weight(solid):
        # Share credit between part coverage and the amount of material.
        return 0.5 / count + 0.5 * solid["volume_mm3"] / volume

    details = []
    for match in comparison["matches"]:
        error = max(match["max_relative_size_error"], match["shape_descriptor_error"])
        quality = max(0., min(1., (ZERO_ERROR - error) / (ZERO_ERROR - FULL_ERROR)))
        details.append({**match, "error": error, "quality": quality,
                        "reference_weight": weight(ref[match["reference_id"]])})
    optional, extras = [], []
    for ident in comparison["unmatched_candidate"]:
        if len(optional) < MAX_DRAWING_PINS and is_optional_pin(cand[ident]):
            optional.append(ident)
        else:
            extras.append(ident)
    matched_loss = sum(p["reference_weight"] * (1 - p["quality"]) for p in details)
    missing_loss = sum(weight(ref[i]) for i in comparison["unmatched_reference"])
    extra_weight = sum(weight(cand[i]) for i in extras)
    score = max(0., min(1., (1 - matched_loss - missing_loss) / (1 + extra_weight)))
    return {"score": score, "matched_shape_size_loss": matched_loss,
            "missing_reference_loss": missing_loss, "unexpected_geometry_weight": extra_weight,
            "missing_reference": comparison["unmatched_reference"],
            "allowed_drawing_pins": optional, "unexpected_solids": extras,
            "estimated_linear_scale": comparison["estimated_linear_scale"], "matches": details}

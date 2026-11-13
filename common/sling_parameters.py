"""Parametric rubric over evidence from active final-solid dependencies."""

# Nominal drawing dimensions, in millimeters. A sketch radius is converted
# to diameter before comparison. These are identification bands, not GD&T.
SIGNATURES = {
    "pivot spacing": ({"linear"}, 120., .5),
    "small pivot bore": ({"diameter"}, 12.2, .15),
    "large pivot bore": ({"diameter"}, 16.2, .15),
    "sleeve outside diameter": ({"diameter"}, 33.7, .25),
    "sleeve bore": ({"diameter"}, 20.2, .15),
    "plate thickness": ({"extrusion"}, 10., .25),
}


def signature_keys(control):
    return [key for key, (kinds, nominal, tolerance) in SIGNATURES.items()
            if control["kind"] in kinds and abs(abs(control["value"]) - nominal) <= tolerance
            and (key != "pivot spacing" or control.get("pivot_centers_confirmed"))]


def score_parameters(evidence):
    controls = evidence.get("controls", [])
    signatures = evidence.get("signature_matches", {})
    probes = evidence.get("probes", [])
    outputs = {target for c in controls for target in c["outputs"]}
    changed = {target for p in probes if p["status"] == "changed" for target in p["changed_outputs"]}
    return {
        "carries dimensional constraints": min(1., len(controls) / 6, len(outputs) / 3),
        "dimensions drive the geometry": min(1., len(changed) / 3),
        "signature dimensions present": sum(bool(signatures.get(k)) for k in SIGNATURES) / len(SIGNATURES),
    }

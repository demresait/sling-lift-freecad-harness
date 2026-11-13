"""Name-independent solid size diagnostics. No grading policy lives here.

Inertia lengths are equivalent-ellipsoid semiaxes, not literal part lengths.
They are invariant to rigid placement and reflection, and scale linearly.
Matching is one-to-one with explicit unmatched slots. Splitting/fusing solids
can change correspondence; detailed topology and pose checks remain separate.
"""
import math
import statistics

import numpy as np


def describe(solid):
    volume = float(solid["volume_mm3"])
    area = float(solid["area_mm2"])
    if volume <= 0 or area <= 0 or not math.isfinite(volume + area):
        raise ValueError("Solid must have finite positive volume and area")
    matrix = np.array(solid["inertia_mm5"], dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Invalid inertia matrix")
    moments = np.linalg.eigvalsh((matrix + matrix.T) / 2)
    squared = 5 * (moments.sum() / 2 - moments) / volume
    if np.min(squared) < -1e-8 * max(float(np.max(abs(squared))), 1):
        raise ValueError("Non-physical inertia matrix")
    lengths = sorted(math.sqrt(max(float(x), 1e-20)) for x in squared)
    size = volume ** (1 / 3)
    return {"size_mm": size, "inertia_lengths_mm": lengths,
            "normalized_lengths": [x / size for x in lengths],
            "compactness": area / size ** 2,
            "normalized_radii": sorted(r / size for r in solid.get("cylinder_radii_mm", []))}


def shape_cost(a, b):
    """Scale-free descriptor distance; not a proof of equal B-rep geometry."""
    costs = [abs(math.log(x / y)) for x, y in zip(a["normalized_lengths"], b["normalized_lengths"])]
    costs.append(abs(math.log(a["compactness"] / b["compactness"])))
    ra, rb = a["normalized_radii"], b["normalized_radii"]
    if ra and rb:
        costs.append((sum(min(abs(math.log(x / y)) for y in rb) for x in ra) / len(ra)
                      + sum(min(abs(math.log(y / x)) for x in ra) for y in rb) / len(rb)) / 2)
    elif bool(ra) != bool(rb):
        costs.append(1.0)
    return sum(costs) / len(costs)


def assignment(cost):
    """Hungarian minimum assignment for a square cost matrix, O(n^3)."""
    n = len(cost)
    u, v, p, way = [0.] * (n + 1), [0.] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        mins, used = [float("inf")] * (n + 1), [False] * (n + 1)
        while True:
            used[j0], i0, delta, j1 = True, p[j0], float("inf"), 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < mins[j]:
                        mins[j], way[j] = cur, j0
                    if mins[j] < delta:
                        delta, j1 = mins[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    mins[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0], j0 = p[j1], j1
    result = [None] * n
    for j in range(1, n + 1):
        result[p[j] - 1] = j - 1
    return result


def compare_geometry(reference, candidate):
    ref, cand = reference["solids"], candidate["solids"]
    if not ref or not cand:
        raise ValueError("Both measurements must contain solids")
    rd, cd = [describe(s) for s in ref], [describe(s) for s in cand]
    nr, nc = len(ref), len(cand)
    shape = [[shape_cost(a, b) for b in cd] for a in rd]
    # Estimate scale using plausible normalized-shape matches. Repeated parts
    # can be ambiguous; retain the sample spread instead of claiming certainty.
    estimates = []
    for i, row in enumerate(shape):
        j = min(range(nc), key=lambda j: row[j])
        if row[j] <= 0.05:
            estimates.append(cd[j]["size_mm"] / rd[i]["size_mm"])
    scale = statistics.median(estimates) if estimates else None
    align_scale = scale if scale is not None else 1.0
    unmatched_cost = 0.35
    costs = [[0.] * (nr + nc) for _ in range(nr + nc)]
    for i in range(nr):
        for j in range(nc):
            size_cost = abs(math.log(cd[j]["size_mm"] / rd[i]["size_mm"] / align_scale))
            costs[i][j] = shape[i][j] + 0.25 * size_cost
        for j in range(nc, nr + nc):
            costs[i][j] = unmatched_cost
    for i in range(nr, nr + nc):
        for j in range(nc):
            costs[i][j] = unmatched_cost
    selected = assignment(costs)
    matches, missing, matched_candidates = [], [], set()
    for i in range(nr):
        j = selected[i]
        if j >= nc:
            missing.append(ref[i]["id"])
            continue
        matched_candidates.add(j)
        ratios = [b / a for a, b in zip(rd[i]["inertia_lengths_mm"], cd[j]["inertia_lengths_mm"])]
        matches.append({"reference_id": ref[i]["id"], "candidate_id": cand[j]["id"],
                        "shape_descriptor_error": shape[i][j],
                        "linear_scale_ratio": cd[j]["size_mm"] / rd[i]["size_mm"],
                        "inertia_length_ratios": ratios,
                        "max_relative_size_error": max(abs(r - 1) for r in ratios),
                        "volume_ratio": cand[j]["volume_mm3"] / ref[i]["volume_mm3"],
                        "area_ratio": cand[j]["area_mm2"] / ref[i]["area_mm2"]})
    return {"reference_solids": nr, "candidate_solids": nc, "matched_solids": len(matches),
            "unmatched_reference": missing,
            "unmatched_candidate": [s["id"] for j, s in enumerate(cand) if j not in matched_candidates],
            "estimated_linear_scale": scale, "scale_estimate_samples": len(estimates),
            "scale_ratio_range": [min(estimates), max(estimates)] if estimates else None,
            "matches": matches,
            "limitations": ["Solid segmentation affects matching; unmatched does not establish a missing BOM part.",
                             "Descriptors are approximate shape evidence, not a full shape comparison.",
                             "No pose, joint, motion, or parameter influence verdict is produced.",
                             "Scale estimation can be ambiguous for similar shapes in different sizes."]}

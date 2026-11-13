"""Behavior checks for placement invariance, scaling, and missing solids."""
import itertools
import math
import unittest

import numpy as np

from common.geometry_compare import assignment, compare_geometry, describe


def box(ident, sides, rotation=None):
    a, b, c = sides
    volume = a * b * c
    inertia = np.diag([volume * (b*b + c*c) / 12,
                       volume * (a*a + c*c) / 12,
                       volume * (a*a + b*b) / 12])
    if rotation is not None:
        inertia = rotation @ inertia @ rotation.T
    return {"id": ident, "volume_mm3": volume, "area_mm2": 2*(a*b + a*c + b*c),
            "inertia_mm5": inertia.tolist(), "cylinder_radii_mm": []}


class GeometryComparisonTests(unittest.TestCase):
    def test_rigid_rotation_reflection_and_names_do_not_change_size(self):
        theta = 0.73
        rot = np.array([[math.cos(theta), -math.sin(theta), 0],
                        [math.sin(theta), math.cos(theta), 0], [0, 0, -1]])
        a = box("old-name", (10, 30, 120))
        b = box("renamed", (10, 30, 120), rot)
        result = compare_geometry({"solids": [a]}, {"solids": [b]})
        self.assertEqual(result["matched_solids"], 1)
        self.assertLess(result["matches"][0]["max_relative_size_error"], 1e-12)

    def test_uniform_double_scale_is_reported_without_normalizing_it_away(self):
        a, b = box("a", (10, 30, 120)), box("b", (20, 60, 240))
        result = compare_geometry({"solids": [a]}, {"solids": [b]})
        self.assertAlmostEqual(result["estimated_linear_scale"], 2)
        self.assertAlmostEqual(result["matches"][0]["volume_ratio"], 8)
        self.assertAlmostEqual(result["matches"][0]["max_relative_size_error"], 1)

    def test_missing_solid_and_reordering(self):
        a, b = box("a", (10, 30, 120)), box("b", (20, 20, 20))
        result = compare_geometry({"solids": [a, b]}, {"solids": [box("new", (20, 20, 20))]})
        self.assertEqual(result["unmatched_reference"], ["a"])
        self.assertEqual(result["matches"][0]["reference_id"], "b")

    def test_equal_volume_does_not_imply_equal_size(self):
        a, b = box("a", (10, 30, 120)), box("b", (20, 30, 60))
        self.assertNotEqual(describe(a)["inertia_lengths_mm"], describe(b)["inertia_lengths_mm"])

    def test_assignment_agrees_with_brute_force(self):
        cost = [[0.8, 0.2, 0.6], [0.1, 0.9, 0.4], [0.3, 0.5, 0.7]]
        selected = assignment(cost)
        self.assertAlmostEqual(sum(cost[i][j] for i, j in enumerate(selected)),
                               min(sum(cost[i][j] for i, j in enumerate(p))
                                   for p in itertools.permutations(range(3))))


if __name__ == "__main__":
    unittest.main()

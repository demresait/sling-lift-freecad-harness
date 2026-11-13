"""Geometry rubric behavior with controlled measurements."""
import unittest

from common.sling_geometry_score import geometry_score
from test_geometry_compare import box


class GeometryRubricTests(unittest.TestCase):
    def setUp(self):
        self.base = box("sleeve-like", (20, 30, 50))
        self.washer = box("small solid", (2, 5, 7))
        self.reference = {"solids": [self.base, self.washer]}

    def test_identical_geometry_and_scale_error(self):
        self.assertAlmostEqual(geometry_score(self.reference, self.reference)["score"], 1)
        doubled = {"solids": [box("x", (40, 60, 100)), box("y", (4, 10, 14))]}
        self.assertAlmostEqual(geometry_score(self.reference, doubled)["score"], 0)

    def test_local_change_and_missing_solid_have_separate_evidence(self):
        candidate = {"solids": [box("different name", (20, 30, 55))]}
        result = geometry_score(self.reference, candidate)
        self.assertEqual(result["missing_reference"], [self.washer["id"]])
        self.assertGreater(result["matched_shape_size_loss"], 0)
        self.assertGreater(result["missing_reference_loss"], 0)
        self.assertGreater(result["score"], 0)
        self.assertLess(result["score"], 1)

    def test_at_most_two_geometric_pins_without_name_exemption(self):
        def pin(ident, span=16):
            return {**box(ident, (4, 4, 16)), "cylinder_radii_mm": [2.15, 3.35],
                    "pin_axis_vertex_span_mm": span}

        two = {"solids": self.reference["solids"] + [pin("abc"), pin("xyz")]}
        result = geometry_score(self.reference, two)
        self.assertAlmostEqual(result["score"], 1)
        self.assertEqual(result["allowed_drawing_pins"], ["abc", "xyz"])
        many = {"solids": two["solids"] + [pin("third"), pin("spring pin", span=22)]}
        result = geometry_score(self.reference, many)
        self.assertCountEqual(result["unexpected_solids"], ["third", "spring pin"])
        self.assertLess(result["score"], 1)

"""Saved-pose limit evidence does not treat opposite signs as equivalent."""
import unittest

from common.freecad_joints import limit_violations


class SavedJointLimitTests(unittest.TestCase):
    def test_positive_slider_position_is_outside_negative_limits(self):
        reading = limit_violations({"LengthMin": -180, "LengthMax": -130},
                                   {"axial_position_mm": 180})
        self.assertEqual(reading["Length"]["outside_by"], 310)

    def test_valid_position_after_consistent_coordinate_reversal(self):
        forward = limit_violations({"LengthMin": 130, "LengthMax": 180},
                                   {"axial_position_mm": 180.00000000000003})
        reverse = limit_violations({"LengthMin": -180, "LengthMax": -130},
                                   {"axial_position_mm": -180})
        self.assertEqual(forward["Length"]["outside_by"], 0)
        self.assertEqual(reverse["Length"]["outside_by"], 0)

    def test_inverted_limits_and_angle_wrapping(self):
        reading = limit_violations({"LengthMin": 10, "LengthMax": 5,
                                   "AngleMin": 170, "AngleMax": 200}, {"twist_deg": -175})
        self.assertEqual(reading["Length"]["status"], "inverted_bounds")
        self.assertEqual(reading["Angle"]["outside_by"], 0)

"""Check evidence that separates solver frames from actual articulated motion."""
import unittest

from common.motion_evidence import summarize_frames


def joint(name, kind, position=0, gap=0, twist=0, axis=0, outside=0):
    return {"joint": name, "assembly_path": "Assembly", "type": kind,
            "endpoints": [{"object": "root"}, {"object": name}],
            "connector_geometry": {"status": "measured", "axial_position_mm": position,
                                   "radial_gap_mm": 0., "origin_gap_mm": gap,
                                   "axis_angle_deg": axis, "twist_deg": twist},
            "limits_at_saved_pose": {"Length": {"status": "measured", "outside_by": outside}}
            if kind == "Slider" else {}}


class MotionEvidenceTests(unittest.TestCase):
    def test_repeated_pose_does_not_verify_travel(self):
        driver = joint("input", "Slider", -150)
        result = summarize_frames([{"index": i, "joints": [driver]} for i in range(6)], driver, 5)
        self.assertFalse(result["travel_verified"])
        self.assertEqual(result["measured_travel_mm"], 0)

    def test_travel_and_mating_are_independent(self):
        driver = joint("input", "Slider", -150)
        first = {"index": 0, "joints": [driver, joint("pivot", "Revolute", twist=179)]}
        last = {"index": 5, "joints": [joint("input", "Slider", -145, gap=145, outside=2),
                                      joint("pivot", "Revolute", gap=6, twist=-179, axis=40)]}
        result = summarize_frames([first, last], driver, 5)
        self.assertTrue(result["travel_verified"])
        self.assertEqual(result["max_revolute_rotation_deg"], 2)
        self.assertEqual(result["max_gap_by_joint_type"]["Revolute"]["gap_mm"], 6)
        self.assertEqual(result["max_gap_by_joint_type"]["Slider"]["gap_mm"], 0)
        self.assertEqual(result["max_axis_angle_by_joint_type"]["Revolute"]["angle_deg"], 40)
        self.assertEqual(result["sampled_limit_violations"][0]["frame"], 5)

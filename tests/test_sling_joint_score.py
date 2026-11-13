"""Behavior checks for separate mating and articulation credit."""
import unittest

from common.sling_joint_score import score_articulation, score_mating


def pivot(index, gap=0.):
    return {"joint": f"pivot{index}", "assembly_path": "Assembly", "type": "Revolute",
            "status": "distinct_member_references", "endpoints": [
                {"object": f"part{index}"}, {"object": f"part{index+1}"}],
            "connector_geometry": {"status": "measured", "origin_gap_mm": gap,
                                   "axis_angle_deg": 0.}}


class JointRubricTests(unittest.TestCase):
    def test_later_gap_costs_mating_but_not_verified_articulation(self):
        saved = [pivot(i) for i in range(4)]
        motion = {"status": "sampled", "travel_verified": True, "measured_travel_mm": 5.,
                  "moving_revolute_count": 4, "frames": [
                      {"index": 5, "joints": [pivot(i, 6. if i == 1 else 0.) for i in range(4)]}]}
        self.assertEqual(score_mating(saved, motion)["score"], .75)
        self.assertEqual(score_articulation(motion)["score"], 1.)

    def test_duplicate_connections_do_not_increase_coverage(self):
        saved = [{**pivot(0), "joint": f"copy{i}"} for i in range(5)]
        result = score_mating(saved, {})
        self.assertEqual(len(result["connections"]), 1)
        self.assertEqual(result["score"], .25)

    def test_unverified_or_out_of_bounds_motion_gets_no_credit(self):
        motion = {"status": "sampled", "travel_verified": True, "measured_travel_mm": 5.,
                  "moving_revolute_count": 3}
        self.assertEqual(score_articulation({**motion, "travel_verified": False})["score"], 0.)
        self.assertEqual(score_articulation({**motion, "sampled_limit_violations": [1]})["score"], 0.)

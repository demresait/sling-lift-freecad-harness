import unittest

from common.sling_parameters import score_parameters, signature_keys


class ParameterRubricTests(unittest.TestCase):
    def test_linear_value_alone_does_not_identify_pivot_spacing(self):
        control = {"kind": "linear", "value": 120.}
        self.assertEqual(signature_keys(control), [])
        self.assertEqual(signature_keys({**control, "pivot_centers_confirmed": True}), ["pivot spacing"])
        self.assertEqual(signature_keys({"kind": "diameter", "value": 12.2}), ["small pivot bore"])
        self.assertEqual(signature_keys({"kind": "linear", "value": 12.2}), [])

    def test_inventory_and_actual_response_are_independent(self):
        controls = [{"outputs": [f"body{i % 3}"]} for i in range(6)]
        evidence = {"controls": controls, "signature_matches": {"sleeve bore": ["control"]},
                    "probes": [{"status": "unchanged", "changed_outputs": []}]}
        result = score_parameters(evidence)
        self.assertEqual(result["carries dimensional constraints"], 1.)
        self.assertEqual(result["dimensions drive the geometry"], 0.)
        self.assertAlmostEqual(result["signature dimensions present"], 1 / 6)

    def test_many_successes_on_one_output_do_not_prove_coverage(self):
        evidence = {"probes": [{"status": "changed", "changed_outputs": ["one body"]}] * 10}
        self.assertAlmostEqual(score_parameters(evidence)["dimensions drive the geometry"], 1 / 3)

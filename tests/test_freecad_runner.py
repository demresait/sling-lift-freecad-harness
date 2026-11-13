"""Prevent a failed stage from reusing an earlier successful measurement."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from common.harness_base import run_freecad_stage


class FreeCADRunnerTests(unittest.TestCase):
    def test_previous_success_is_not_reused_when_no_output_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "measure.json"
            output.write_text('{"ok": true, "old": true}')
            with patch("common.harness_base.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                measurement, error = run_freecad_stage("stage.py", "candidate.FCStd", out_dir=folder, freecadcmd="fake")
            self.assertIsNone(measurement)
            self.assertIsNotNone(error)
            self.assertFalse(output.exists())

    def test_nonzero_exit_rejects_even_written_success(self):
        with tempfile.TemporaryDirectory() as folder:
            def execute(*args, **kwargs):
                (Path(folder) / "measure.json").write_text('{"ok": true}')
                return subprocess.CompletedProcess([], 2, "", "crash")
            with patch("common.harness_base.subprocess.run", side_effect=execute):
                measurement, error = run_freecad_stage("stage.py", "candidate.FCStd", out_dir=folder, freecadcmd="fake")
            self.assertIsNone(measurement)
            self.assertIn("code 2", error)

    def test_fresh_success_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            def execute(*args, **kwargs):
                (Path(folder) / "measure.json").write_text(json.dumps({"ok": True, "fresh": True}))
                return subprocess.CompletedProcess([], 0, "", "")
            with patch("common.harness_base.subprocess.run", side_effect=execute):
                measurement, error = run_freecad_stage("stage.py", "candidate.FCStd", out_dir=folder, freecadcmd="fake")
            self.assertIsNone(error)
            self.assertTrue(measurement["fresh"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Grading harness for 4_sling_lift: geometry, mechanism, and parameters.

    python3 tests/task/harness/harness.py solution/solution.FCStd

Detailed evidence is available in the corpus report.

WHAT IT HAS TO DO

    the reference   solution/solution.FCStd must score 6 of 6.
    the adversarials  every folder under examples/ must lose the
                      component(s) it actually breaks, and only those.

Grade the geometry and the parametric structure the instruction asks for.
Do not grade object names, document-tree shape, or anything that is true
of the reference by coincidence: a candidate who models the lift a
different way and gets it right must still score 6 of 6. That is the
whole difficulty of the task, and the corpus is built to catch a harness
that takes the easy route.

THE SPLIT, WHICH IS WORTH KEEPING

This file does not import FreeCAD. It runs `measure_stage.py` under
`freecadcmd` through `common.harness_base.run_freecad_stage`, and scores
the JSON that comes back. Two reasons, both practical: the scoring half
stays testable on a machine with no FreeCAD, and a candidate's document
never gets to run its own macros inside the grader's interpreter.

Motion and dimension perturbation run in separate bounded processes so
their temporary changes cannot affect saved geometry evidence.

THE CONTRACT

`Harness` (common/harness_base.py) wants two methods:

    build_state(candidate_path) -> dict
        Expensive shared setup, run once. Whatever the checks read.

    checks(state) -> {name: (name, score, description)}
        `score` is a float in [0, 1]. `description` is the sentence a
        human reads next to the number; make it say what was measured,
        not just pass or fail.

SCORE CONTINUOUSLY. A bool is accepted and is almost always the wrong
answer. Most of these components are questions of degree, and collapsing
them to pass/fail throws away the information that makes a grader useful:

    five joints wanted, three mated                 -> 0.6, not 0
    a link 4% short of the drawing                  -> 0.9, not 0
    two of four signature dimensions present        -> 0.5, not 0

A candidate who gets most of it right should score most of the marks, and
two candidates who are wrong by different amounts should not land on the
same number. Reserve a hard 0 or 1 for components that genuinely have no
middle -- "does it rebuild without errors" is one, and it is the gate.

`common/harness_base.py` has helpers for the usual shapes: `clamp01`,
`score_error(value, perfect, zero)` for a reading that degrades with
distance from a target, `score_ratio` for "how many of these are right",
and `score_band` for a value that has to sit inside a range.

`MUST_PASS` names components that zero the whole score when they fail.
`WEIGHTS` prices them; `max_score` in task.toml must equal the sum.

The seven below are the components the task shipped with. They are a
suggestion, not a requirement: split, merge, reweight, rename or replace
them as your reading of instruction.md warrants, and say why in your
notes. Keep task.toml's max_score in step.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root(start):
    d = start
    for _ in range(8):
        if (d / "common" / "__init__.py").is_file():
            return d
        if d.parent == d:
            break
        d = d.parent
    return start


REPO = _repo_root(HERE)
sys.path[:0] = [str(REPO), "/opt"]

from common.harness_base import Harness, run_freecad_stage  # noqa: E402
from common.sling_geometry_score import geometry_score     # noqa: E402
from common.sling_joint_score import score_articulation, score_mating  # noqa: E402
from common.sling_parameters import score_parameters  # noqa: E402

#: Weight per component; 0 makes it a gate when it is also in MUST_PASS.
#: The sum must equal task.toml's max_score (6 today).
ALL_CRITERIA = {
    "executes and builds geometry": 0,
    "geometry matches ground truth": 1,
    "pantograph joints mated": 1,
    "mechanism articulates": 1,
    "carries dimensional constraints": 1,
    "dimensions drive the geometry": 1,
    "signature dimensions present": 1,
}

REFERENCE = HERE.parent / "reference" / "solution.FCStd"


class SlingLiftHarness(Harness):
    MUST_PASS = ("executes and builds geometry",)
    WEIGHTS = ALL_CRITERIA
    BUILD_TIMEOUT_S = 600

    def build_state(self, candidate_path):
        """Measure the candidate and compare with the pinned reference asset."""
        # Preserve a diagnostic if FreeCAD is not configured or fails to run.
        reference_error, geometry, motion, parameters = None, None, {}, {}
        try:
            measurement, error = self.run_freecad_stage(candidate_path)
        except SystemExit as exc:
            measurement, error = None, str(exc)
        except Exception as exc:                            # noqa: BLE001
            measurement, error = None, f"{type(exc).__name__}: {exc}"
        if error is None:
            try:
                if not hasattr(self, "_reference_geometry"):
                    reference, failure = self.run_freecad_stage(REFERENCE)
                    if failure:
                        raise RuntimeError(failure)
                    self._reference_geometry = reference["geometry"]
                geometry = geometry_score(self._reference_geometry, measurement["geometry"])
            except (Exception, SystemExit) as exc:
                reference_error = f"Geometry comparison unavailable: {exc}"
            try:
                motion, failure = run_freecad_stage(HERE / "motion_stage.py", candidate_path, timeout=45)
                if failure:
                    motion = {"status": "stage_error", "reason": failure}
            except (Exception, SystemExit) as exc:
                motion = {"status": "stage_error", "reason": str(exc)}
            try:
                parameters, failure = run_freecad_stage(HERE / "parameter_stage.py", candidate_path, timeout=75)
                if failure:
                    parameters = {"status": "stage_error", "reason": failure}
            except (Exception, SystemExit) as exc:
                parameters = {"status": "stage_error", "reason": str(exc)}
        saved = (measurement or {}).get("joint_references", {}).get("joints", [])
        return {
            "candidate": candidate_path,
            "measurement": measurement or {},
            "error": error,
            "geometry": geometry,
            "geometry_error": reference_error,
            "motion": motion,
            "mating": score_mating(saved, motion),
            "articulation": score_articulation(motion),
            "parameters": parameters,
            "parameter_scores": score_parameters(parameters),
        }

    def checks(self, state):
        """Score all six criteria independently from their own evidence."""
        err = state["error"]
        out = {}

        # The gate requires saved solid geometry to be measured successfully.
        name = "executes and builds geometry"
        out[name] = (name, err is None,
                     "the measurement stage ran" if err is None
                     else f"the measurement stage failed: {err}")

        name = "geometry matches ground truth"
        geometry = state["geometry"]
        out[name] = (name, geometry["score"] if geometry else 0.,
                     (f"{len(geometry['matches'])} matched solids, "
                      f"{len(geometry['missing_reference'])} missing, "
                      f"{len(geometry['allowed_drawing_pins'])} allowed drawing pins")
                     if geometry else state["geometry_error"] or "candidate measurement unavailable")

        name = "pantograph joints mated"
        mating = state["mating"]
        out[name] = (name, mating["score"], f"{len(mating['connections'])} movable connections measured or checked")
        name = "mechanism articulates"
        out[name] = (name, state["articulation"]["score"], state["articulation"]["status"])

        for name, score in state["parameter_scores"].items():
            out[name] = (name, score, state["parameters"].get("reason", "active final-solid parameter evidence"))
        return out


main = SlingLiftHarness.as_main()

if __name__ == "__main__":
    SlingLiftHarness.cli()

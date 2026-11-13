"""Run the current harness on the supplied corpus and retain its evidence."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "FreeCAD/4_sling_lift"
sys.path.insert(0, str(TASK / "tests/task/harness"))
from harness import SlingLiftHarness
from common.harness_base import finalize


def main():
    paths = [TASK / "solution/solution.FCStd", *sorted((TASK / "examples").glob("*/*.FCStd"))]
    if len(paths) != 6:
        raise RuntimeError("Download all five example FCStd files before evaluating the corpus")
    output = TASK / "results/harness"
    output.mkdir(parents=True, exist_ok=True)
    harness = SlingLiftHarness()
    rows = []
    for path in paths:
        state = harness.build_state(path)
        if state["error"] or state["geometry_error"]:
            raise RuntimeError(f"{path.name}: {state['error'] or state['geometry_error']}")
        report = finalize(TASK, harness.checks(state), must_pass=harness.MUST_PASS,
                          weights=harness.WEIGHTS)
        joints = state["measurement"]["joint_references"]
        evidence = {"result": report, "geometry": state["geometry"], "joint_references": joints,
                    "mating": state["mating"], "articulation": state["articulation"], "motion": state["motion"],
                    "parameters": state["parameters"]}
        (output / f"{path.stem}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        geometry = state["geometry"]
        row = {"model": path.stem, "geometry_score": report["subscores"]["geometry matches ground truth"],
               "mating_score": report["subscores"]["pantograph joints mated"],
               "articulation_score": report["subscores"]["mechanism articulates"],
               "dimensional_constraints_score": report["subscores"]["carries dimensional constraints"],
               "dimensions_drive_score": report["subscores"]["dimensions drive the geometry"],
               "signature_dimensions_score": report["subscores"]["signature dimensions present"],
               "score": report["score"], "max_score": report["max_score"],
               "parameter_status": state["parameters"].get("status", "measured"),
               "motion_status": state["articulation"]["status"],
               "missing_solids": len(geometry["missing_reference"]),
               "allowed_pins": len(geometry["allowed_drawing_pins"]),
               "unexpected_solids": len(geometry["unexpected_solids"]),
               "joint_reference_counts": joints["counts"],
               "joint_connector_counts": joints["connector_counts"]}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

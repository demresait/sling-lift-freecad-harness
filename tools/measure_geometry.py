"""Measure and compare all six models. Run from any working directory.

FREECAD_CMD must be set (or configured in .env with python-dotenv installed).
Requires numpy in this Python interpreter; the FreeCAD stage uses no pip packages.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.geometry_compare import compare_geometry
from common.harness_base import run_freecad_stage


def main():
    task = ROOT / "FreeCAD/4_sling_lift"
    output = task / "results/geometry"
    paths = [task / "solution/solution.FCStd", *sorted((task / "examples").glob("*/*.FCStd"))]
    reference = None
    rows = []
    for path in paths:
        measurement, error = run_freecad_stage(Path(__file__).with_name("geometry_stage.py"),
                                              path, out_dir=output / path.stem)
        if error:
            raise RuntimeError(f"{path.name}: {error}")
        if reference is None:
            reference = measurement
        comparison = compare_geometry(reference, measurement)
        (output / path.stem / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        row = {"model": path.stem, **{k: comparison[k] for k in (
            "reference_solids", "candidate_solids", "matched_solids", "estimated_linear_scale")},
            "unmatched_reference": len(comparison["unmatched_reference"]),
            "unmatched_candidate": len(comparison["unmatched_candidate"])}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    keys = list(rows[0])
    lines = ["# Geometry diagnostics", "", "These are solid counts, not BOM part counts. No scores are assigned.", "",
             "| " + " | ".join(keys) + " |", "| " + " | ".join(["---"] * len(keys)) + " |"]
    lines.extend("| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows)
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

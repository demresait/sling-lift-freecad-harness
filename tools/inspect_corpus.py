"""Inspect the reference and five examples without modifying their documents.

Set FREECAD_CMD, then run: python tools/inspect_corpus.py
Outputs diagnostic JSON and a summary table under results/inventory/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.harness_base import run_freecad_stage


def main():
    task = ROOT / "FreeCAD" / "4_sling_lift"
    out = task / "results" / "inventory"
    paths = [task / "solution" / "solution.FCStd", *sorted((task / "examples").glob("*/*.FCStd"))]
    rows = []
    for path in paths:
        measurement, error = run_freecad_stage(Path(__file__).with_name("inspect_stage.py"),
                                              path, out_dir=out / path.stem)
        if error:
            raise RuntimeError(f"{path.name}: {error}")
        row = {"model": path.stem, **measurement["summary"]}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (out / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    columns = ["model", "sketches", "constraints", "dimensional_constraints",
               "driving_dimensional_constraints", "joints", "inspection_errors"]
    lines = ["# Saved-document inventory", "",
             "Diagnostic counts only. They do not prove geometry, mating, motion, or parameter influence.", "",
             "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    lines.extend("| " + " | ".join(str(r[c]) for c in columns) + " |" for r in rows)
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

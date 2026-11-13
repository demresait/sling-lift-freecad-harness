"""Run each native motion probe in its own FreeCAD process."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "FreeCAD/4_sling_lift"
sys.path.insert(0, str(ROOT))
from common.harness_base import run_freecad_stage


def main():
    paths = [TASK / "solution/solution.FCStd", *sorted((TASK / "examples").glob("*/*.FCStd"))]
    if len(paths) != 6 or not all(p.is_file() for p in paths):
        raise RuntimeError("Download the reference and all five example files first")
    output = TASK / "results/motion"
    rows = []
    for path in paths:
        result, error = run_freecad_stage(TASK / "tests/task/harness/motion_stage.py", path,
                                          out_dir=output / path.stem, timeout=45)
        row = {"model": path.stem, **({"status": "stage_error", "reason": error} if error else
               {k: v for k, v in result.items() if k not in ("input", "ok", "frames")})}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Measure saved geometry and joint references for 4_sling_lift.

Runs inside `freecadcmd`, not in the harness's interpreter. It is
launched by `Harness.run_freecad_stage` with three environment variables
already set:

    FC_STAGE_INPUT    the document to measure
    FC_STAGE_OUT      a directory to write measure.json into
    FC_STAGE_COMMON   the directory holding common/, so this can import
                      the Stage base

Subclass `Stage`, implement `measure(doc) -> dict`, and the base writes
`measure.json` for you, catching and recording any exception as
`{"ok": false, "error": ...}` rather than letting it escape. Your harness
reads that dict back.

**Stdlib and FreeCAD only.** This runs in freecadcmd's own Python, which
is not the interpreter your harness runs in and does not have your pip
packages. Anything from numpy up belongs on the scoring side.

WHAT TO MEASURE IS THE DESIGN QUESTION

The current stage reads final solids, joint reference membership, and saved
connector residuals. It does not yet solve motion or test parameters.
instruction.md asks for a lift that is driven by key
dimensions rather than dead geometry, with its pantograph joints mated so
it articulates. Some things that might be worth getting out of the
document -- none of them prescribed:

  * the solids, and something comparable about their shape and size that
    survives a candidate modelling the lift in a different order, or
    mirrored;
  * the joints: what kind, what they connect, whether they actually
    constrain anything, and their limits;
  * whether the mechanism moves -- and a way to tell "moves" from
    "flies apart";
  * where the dimensions live: sketch constraints, spreadsheet cells,
    expressions, named parameters. And, separately, whether changing one
    changes the geometry, which is a different question from whether it
    exists.

The last of those is worth dwelling on. A document can carry a tidy set
of named constraints that drive nothing at all, and the corpus contains
models built to look right in exactly that way.
"""
import os
import sys

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])

from common.freecad_geometry import GeometryStage          # noqa: E402
from common.freecad_joints import measure_joint_references  # noqa: E402


class SlingLiftStage(GeometryStage):
    def measure(self, doc):
        """Return the JSON-serialisable measurement the harness scores.

        `doc` is the opened FreeCAD document. Everything returned has to
        survive `json.dumps` -- FreeCAD vectors, placements and objects do
        not, so convert them to lists and plain values here.
        """
        geometry = super().measure(doc)
        return {"geometry": geometry, "joint_references": measure_joint_references(doc)}


SlingLiftStage.run()

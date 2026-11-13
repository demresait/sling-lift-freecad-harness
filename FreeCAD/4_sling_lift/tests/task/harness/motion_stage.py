"""FreeCADCmd entrypoint for the isolated, in-memory motion probe."""
import os
import sys

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])
from common.freecad_stage import Stage
from common.freecad_motion import measure_motion


class MotionStage(Stage):
    def measure(self, doc):
        return measure_motion(doc)


MotionStage.run()

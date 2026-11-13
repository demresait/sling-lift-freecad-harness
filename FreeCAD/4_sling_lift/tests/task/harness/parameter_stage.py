"""Isolated FreeCAD process for dimension perturbation."""
import os
import sys

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])
from common.freecad_parameters import measure_parameters
from common.freecad_stage import Stage


class ParameterStage(Stage):
    def measure(self, doc):
        return measure_parameters(doc)


ParameterStage.run()

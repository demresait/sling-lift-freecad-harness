"""FreeCAD stage entrypoint; FreeCAD does not guarantee a __main__ namespace."""
import os
import sys

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])
from common.freecad_geometry import GeometryStage

GeometryStage.run()

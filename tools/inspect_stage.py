"""Read-only corpus inventory, executed by FreeCADCmd through Stage.

This is a diagnostic, not a grader. Object names identify evidence only;
counts include feature history and must not be treated as physical parts.
No document is recomputed, changed, or saved.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])
from common.freecad_stage import Stage

DIMENSIONAL = {"Distance", "DistanceX", "DistanceY", "DistanceZ", "Radius",
               "Diameter", "Angle", "SnellsLaw", "Weight"}


def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "Name"):
        return {"object": value.Name, "type": value.TypeId}
    if hasattr(value, "Value"):
        return float(value.Value)
    return str(value)


class InventoryStage(Stage):
    def measure(self, doc):
        sketches, joints, shapes, expressions, states, errors = [], [], [], [], [], []
        for obj in doc.Objects:
            ident = {"name": obj.Name, "type": obj.TypeId}
            if obj.State:
                states.append(dict(ident, state=list(obj.State)))
            if "ExpressionEngine" in obj.PropertiesList and obj.ExpressionEngine:
                expressions.append(dict(ident, expressions=plain(obj.ExpressionEngine)))
            if obj.TypeId == "Sketcher::SketchObject":
                constraints = []
                for i, constraint in enumerate(obj.Constraints):
                    try:
                        driving = obj.getDriving(i) if constraint.Type in DIMENSIONAL else None
                    except Exception as exc:
                        driving = None
                        errors.append({"object": obj.Name, "constraint": i, "error": str(exc)})
                    constraints.append({"index": i, "type": constraint.Type,
                                        "value": float(constraint.Value),
                                        "name": constraint.Name, "driving": driving})
                sketches.append(dict(ident, constraints=constraints))
            if "JointType" in obj.PropertiesList:
                fields = ("JointType", "Reference1", "Reference2", "Suppressed",
                          "AngleMin", "AngleMax", "LengthMin", "LengthMax",
                          "EnableAngleMin", "EnableAngleMax", "EnableLengthMin",
                          "EnableLengthMax", "Detach1", "Detach2", "Placement1",
                          "Placement2", "Offset1", "Offset2")
                joints.append(dict(ident, properties={
                    k: plain(getattr(obj, k)) for k in fields if k in obj.PropertiesList}))
            try:
                if hasattr(obj, "Shape") and not obj.Shape.isNull():
                    shape = obj.Shape
                    box = shape.BoundBox
                    shapes.append(dict(ident, solid_count=len(shape.Solids),
                                       bbox_mm=[box.XMin, box.YMin, box.ZMin,
                                                box.XMax, box.YMax, box.ZMax]))
            except Exception as exc:
                errors.append({"object": obj.Name, "error": str(exc)})
        dims = [c for s in sketches for c in s["constraints"] if c["type"] in DIMENSIONAL]
        return {
            "schema": "sling-lift-inventory-v1", "freecad_version": list(__import__("FreeCAD").Version()),
            "scope": "Saved document only; no recompute, motion, or parameter perturbation.",
            "summary": {"objects": len(doc.Objects), "sketches": len(sketches),
                        "constraints": sum(len(s["constraints"]) for s in sketches),
                        "dimensional_constraints": len(dims),
                        "driving_dimensional_constraints": sum(c["driving"] is True for c in dims),
                        "joints": len(joints),
                        "joint_types": dict(Counter(j["properties"]["JointType"] for j in joints)),
                        "objects_with_shapes_including_history": len(shapes),
                        "objects_with_expressions": len(expressions), "inspection_errors": len(errors)},
            "object_types": dict(Counter(o.TypeId for o in doc.Objects)),
            "sketches": sketches, "joints": joints, "shapes_including_history": shapes,
            "expressions": expressions, "object_states": states, "inspection_errors": errors,
        }


InventoryStage.run()

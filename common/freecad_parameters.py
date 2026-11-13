"""Inspect and perturb controls upstream of active final solids. Never save."""
import math

from common.freecad_geometry import final_roots
from common.sling_parameters import SIGNATURES, signature_keys

SKETCH_KINDS = {"Distance": "linear", "DistanceX": "linear", "DistanceY": "linear",
                "DistanceZ": "linear", "Radius": "diameter", "Diameter": "diameter",
                "Angle": "angle", "AngleViaPoint": "angle"}
FEATURE_FIELDS = {
    "PartDesign::Pad": {"Length": "extrusion", "Length2": "extrusion"},
    "PartDesign::Pocket": {"Length": "linear", "Length2": "linear"},
    "PartDesign::Hole": {"Diameter": "diameter", "Depth": "linear"},
    "PartDesign::Revolution": {"Angle": "angle"},
    "PartDesign::Groove": {"Angle": "angle"},
    "PartDesign::Fillet": {"Radius": "linear"},
    "Part::Box": {"Length": "extrusion", "Width": "extrusion", "Height": "extrusion"},
    "Part::Cylinder": {"Radius": "diameter", "Height": "extrusion"},
    "Part::Extrusion": {"LengthFwd": "extrusion", "LengthRev": "extrusion"},
}


def final_definitions(doc):
    """Resolve active occurrences to unique, editable final shape definitions."""
    seen, result = set(), {}

    def visit(obj, *, linked=False):
        if not linked and not getattr(obj, "Visibility", True):
            return
        if obj.Name in seen:
            return
        seen.add(obj.Name)
        if obj.TypeId in ("Assembly::JointGroup", "App::Origin") or "JointType" in obj.PropertiesList:
            return
        if obj.TypeId != "Assembly::AssemblyLink" and "LinkedObject" in obj.PropertiesList:
            target = obj.LinkedObject
            if target is not None and getattr(target, "Document", None) == doc:
                visit(target, linked=True)
            return
        if obj.TypeId != "PartDesign::Body" and hasattr(obj, "Group"):
            for child in obj.Group:
                visit(child)
            return
        shape = getattr(obj, "Shape", None)
        if shape is not None and not shape.isNull() and shape.Solids:
            result[obj.Name] = obj

    for root in final_roots(doc)[0]:
        visit(root)
    return result


def dependencies(output):
    """Use the Body Tip rather than every historical feature in the Body."""
    seen = set()
    start = output.Tip if output.TypeId == "PartDesign::Body" else output
    todo = [start] if start else []
    while todo:
        obj = todo.pop()
        if obj.Name in seen or obj.Document != output.Document:
            continue
        seen.add(obj.Name)
        yield obj
        # Support references may point back to the containing Body. Do not
        # follow it to unrelated features or datum objects.
        todo.extend(x for x in obj.OutList if x.TypeId not in ("PartDesign::Body", "App::Part"))


def _pivot_centers(obj, constraint, distance):
    import Part
    indices = (constraint.First, constraint.Second)
    if (indices[0] == indices[1] or min(indices) < 0 or max(indices) >= obj.GeometryCount
            or constraint.FirstPos != 3 or constraint.SecondPos != 3):
        return False
    a, b = (obj.Geometry[i] for i in indices)
    return (all(isinstance(g, Part.Circle) and not obj.getConstruction(i)
                and any(abs(g.Radius - r) <= .1 for r in (6.1, 8.1))
                for i, g in zip(indices, (a, b)))
            and abs((a.Center - b.Center).Length - distance) <= .5)


def _controls(obj):
    expressions = {path for path, _ in getattr(obj, "ExpressionEngine", [])}
    if obj.TypeId == "Sketcher::SketchObject":
        for index, constraint in enumerate(obj.Constraints):
            kind = SKETCH_KINDS.get(constraint.Type)
            if kind is None or not obj.getDriving(index) or not obj.getActive(index):
                continue
            path = f"Constraints[{index}]"
            alias = "Constraints." + constraint.Name if constraint.Name else None
            factor = 2 if constraint.Type == "Radius" else 1
            value = float(constraint.Value) * factor
            control = {"object": obj.Name, "field": path, "index": index, "kind": kind,
                       "value": value, "factor": factor,
                       "expression_bound": path in expressions or alias in expressions}
            if kind == "linear" and abs(abs(value) - 120.) <= .5:
                control["pivot_centers_confirmed"] = _pivot_centers(obj, constraint, abs(value))
            yield control
    for field, kind in FEATURE_FIELDS.get(obj.TypeId, {}).items():
        quantity = getattr(obj, field, None)
        if quantity is None:
            continue
        mode = obj.getEditorMode(field)
        if (mode & 1 if isinstance(mode, int) else "ReadOnly" in mode):
            continue
        factor = 2 if field == "Radius" and kind == "diameter" else 1
        yield {"object": obj.Name, "field": field, "kind": kind, "factor": factor,
               "value": float(quantity.Value if hasattr(quantity, "Value") else quantity) * factor,
               "expression_bound": field in expressions}


def inventory(doc):
    outputs = final_definitions(doc)
    controls, cache = {}, {}
    for name, output in outputs.items():
        for obj in dependencies(output):
            if obj.Name not in cache:
                cache[obj.Name] = [c for c in _controls(obj) if math.isfinite(c["value"]) and abs(c["value"]) > 1e-8]
            for control in cache[obj.Name]:
                key = control["object"], control["field"]
                controls.setdefault(key, {**control, "outputs": []})["outputs"].append(name)
    return outputs, list(controls.values())


def _fingerprint(output):
    shape = output.Shape
    if shape.isNull() or not shape.Solids or "Invalid" in output.State:
        raise ValueError(f"Invalid final shape: {output.Name}")
    return sorted((abs(s.Volume), s.Area, s.MatrixOfInertia.A11 + s.MatrixOfInertia.A22
                   + s.MatrixOfInertia.A33) for s in shape.Solids)


def _different(before, after):
    return len(before) != len(after) or any(
        abs(a - b) > max(abs(a), abs(b), 1.) * 1e-7
        for old, new in zip(before, after) for a, b in zip(old, new))


def _set_value(obj, control, value):
    if "index" not in control:
        setattr(obj, control["field"], value)
        return
    import FreeCAD as App
    index = control["index"]
    original = obj.getDatum(index)
    # Sketch angle constraint.Value is in radians; getDatum carries units.
    quantity = App.Units.Quantity(value, original.Unit) if control["kind"] != "angle" else (
        App.Units.Quantity(math.degrees(value), App.Units.Angle))
    result = obj.setDatum(index, quantity)
    if result not in (0, None) or not math.isclose(obj.Constraints[index].Value, value, abs_tol=1e-8):
        raise ValueError("Sketch rejected the new dimension")


def _probe(doc, outputs, control):
    obj = doc.getObject(control["object"])
    targets = [outputs[name] for name in control["outputs"]]
    baseline = {o.Name: _fingerprint(o) for o in targets}
    value = control["value"] / control["factor"]
    row = {"object": obj.Name, "field": control["field"], "value": value,
           "trial_value": value * 1.01, "changed_outputs": []}
    try:
        _set_value(obj, control, row["trial_value"])
        doc.recompute(targets)
        for output in targets:
            if _different(baseline[output.Name], _fingerprint(output)):
                row["changed_outputs"].append(output.Name)
        row["status"] = "changed" if row["changed_outputs"] else "unchanged"
    except (ValueError, RuntimeError, TypeError) as exc:
        row.update(status="rejected", reason=str(exc), changed_outputs=[])
    finally:
        if "index" not in control or not math.isclose(obj.Constraints[control["index"]].Value, value, abs_tol=1e-8):
            _set_value(obj, control, value)
        doc.recompute(targets)
        if any(_different(baseline[o.Name], _fingerprint(o)) for o in targets):
            raise RuntimeError("Recompute did not restore the original output")
    return row


def measure_parameters(doc):
    outputs, controls = inventory(doc)
    signatures = {key: [] for key in SIGNATURES}
    for control in controls:
        for key in signature_keys(control):
            signatures[key].append(f"{control['object']}.{control['field']}")
    probes, changed = [], set()
    # Prefer drawing-related controls. Stop after three independent final
    # definitions respond, or after the bounded attempt budget is exhausted.
    def priority(control):
        keys = signature_keys(control)
        return (not bool(keys), "pivot spacing" not in keys, "index" not in control)

    ordered = sorted(controls, key=priority)
    for control in ordered:
        if len(probes) >= 12 or len(changed) >= 3:
            break
        if (control["expression_bound"] or control["kind"] == "angle"
                or not set(control["outputs"]) - changed):
            continue
        trial = _probe(doc, outputs, control)
        probes.append(trial)
        changed.update(trial["changed_outputs"])
    return {"controls": controls, "signature_matches": signatures, "probes": probes,
            "active_output_count": len(outputs)}

"""Integration check using temporary in-memory FreeCAD geometry, never saved."""
import json
import os
import sys

sys.path.insert(0, os.environ["FC_STAGE_COMMON"])
sys.path.insert(0, os.path.dirname(__file__))
import FreeCAD as App
import Part
from common.freecad_geometry import GeometryStage
from common.freecad_joints import connector_residuals
from common.freecad_parameters import measure_parameters


doc = App.newDocument("GeometryIntegrationCheck")
try:
    body = doc.addObject("PartDesign::Body", "SourceBody")
    old = body.newObject("PartDesign::Feature", "OldHistory")
    old.Shape = Part.makeBox(10, 30, 130)
    final = body.newObject("PartDesign::Feature", "FinalTip")
    final.Shape = Part.makeBox(10, 30, 120)
    body.Tip = final
    old.Visibility = False
    assembly = doc.addObject("App::Part", "Output")
    first = assembly.newObject("App::Link", "FirstOccurrence")
    first.setLink(body)
    second = assembly.newObject("App::Link", "RotatedOccurrence")
    second.setLink(body)
    second.Placement = App.Placement(App.Vector(1000, -300, 200), App.Rotation(App.Vector(1, 2, 3), 37))
    body.Visibility = False
    doc.recompute()
    measured = GeometryStage().measure(doc)
    assert measured["solid_count"] == 2, measured["solid_count"]
    assert all(s["source_candidates"] for s in measured["solids"])
    assert all(abs(s["volume_mm3"] - 36000) < 1e-6 for s in measured["solids"])
    baseline = measured
    second.Scale = 2
    doc.recompute()
    scaled = GeometryStage().measure(doc)
    assert sorted(round(s["volume_mm3"]) for s in scaled["solids"]) == [36000, 288000]
    first_frame = App.Placement(App.Vector(5, 7, 10), App.Rotation(App.Vector(1, 0, 0), 90))
    shift = App.Placement(App.Vector(3, 4, -12), App.Rotation(App.Vector(0, 0, 1), 30))
    reading = connector_residuals(first_frame, first_frame * shift)
    for key, expected in {"origin_gap_mm": 13, "radial_gap_mm": 5, "axial_position_mm": -12,
                          "axis_angle_deg": 0, "twist_deg": 30}.items():
        assert abs(reading[key] - expected) < 1e-8, (key, reading)
    box = doc.addObject("Part::Box", "ParametricBox")
    box.Length = 10.
    decoy = doc.addObject("Part::Box", "HiddenBox")
    decoy.Visibility = False
    doc.recompute()
    parameters = measure_parameters(doc)
    assert {c["object"] for c in parameters["controls"]} == {box.Name}
    assert any(p["status"] == "changed" and p["changed_outputs"] == [box.Name] for p in parameters["probes"])
    assert abs(box.Length.Value - 10.) < 1e-9
    assert abs(box.Shape.Volume - 1000.) < 1e-8
    output = {"ok": True, "checks": ["feature history excluded", "two linked occurrences preserved",
                                     "rigid placement preserves volume", "link scale preserves cubic volume law",
                                     "connector residuals use the rotated first frame",
                                     "active box responds to perturbation and restores; hidden decoy excluded"],
              "baseline": baseline, "scaled": scaled}
    os.makedirs(os.environ["FC_STAGE_OUT"], exist_ok=True)
    with open(os.path.join(os.environ["FC_STAGE_OUT"], "measure.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("Geometry integration checks passed")
finally:
    App.closeDocument(doc.Name)

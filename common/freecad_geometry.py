"""Measure final assembly solids, not sketch/feature history. FreeCAD only."""
import math
from common.freecad_stage import Stage


def occurrences(root):
    """Walk assembly membership for evidence labels; never feature history.

    Resolve linked subassemblies but retain the link occurrence's path. A part
    container/body is atomic here, even when it contains several solids.
    """
    def walk(container, prefix, ancestors):
        if container.Name in ancestors:
            raise ValueError("Cyclic assembly membership")
        for child in container.Group:
            if "JointType" in child.PropertiesList or child.TypeId == "Assembly::JointGroup":
                continue
            if not getattr(child, "Visibility", True):
                continue
            path = prefix + child.Name + "."
            target = child.getLinkedObject(True) if hasattr(child, "getLinkedObject") else child
            if target.TypeId == "Assembly::AssemblyObject":
                yield from walk(target, path, ancestors | {container.Name})
            else:
                yield {"path": path, "name": child.Name, "label": child.Label,
                       "source_name": target.Name, "source_label": target.Label,
                       "type": child.TypeId}
    if root.TypeId == "Assembly::AssemblyObject":
        yield from walk(root, "", set())
    else:
        yield {"path": "", "name": root.Name, "label": root.Label,
               "source_name": root.Name, "source_label": root.Label, "type": root.TypeId}


def source_candidates(solid, evidence):
    """Attribute geometry by volume and COM, keeping all ambiguous matches."""
    volume = abs(float(solid.Volume))
    center = solid.CenterOfMass
    return [source for other_volume, other_center, source in evidence
            if abs(other_volume - volume) <= 1e-6 * max(volume, 1)
            and (other_center - center).Length <= 1e-5]


def final_roots(doc):
    """Prefer top-level assembly outputs; ignore linked source definitions."""
    assemblies = [o for o in doc.RootObjects if o.TypeId == "Assembly::AssemblyObject"
                  and getattr(o, "Visibility", True)]
    if assemblies:
        return assemblies, "visible top-level assemblies"
    roots = [o for o in doc.RootObjects
             if getattr(o, "Visibility", True)
             and o.TypeId not in ("Sketcher::SketchObject", "App::Origin")
             and not any("LinkedObject" in p.PropertiesList and p.LinkedObject == o
                         for p in doc.Objects)]
    return roots, "visible root shapes (fallback; verify assembly scope)"


class GeometryStage(Stage):
    def measure(self, doc):
        import Part
        roots, strategy = final_roots(doc)
        solids, skipped = [], []
        for root in roots:
            shape = Part.getShape(root)
            if shape.isNull():
                skipped.append(root.Name)
                continue
            evidence = []
            for source in occurrences(root):
                source_shape = Part.getShape(root, source["path"])
                for index, item in enumerate(source_shape.Solids):
                    evidence.append((abs(float(item.Volume)), item.CenterOfMass,
                                     dict(source, occurrence_solid_index=index)))
            for index, solid in enumerate(shape.Solids):
                volume = abs(float(solid.Volume))
                if not math.isfinite(volume) or volume <= 1e-9:
                    raise ValueError("Non-positive or non-finite solid volume")
                inertia = solid.MatrixOfInertia
                cylinders = [f.Surface for f in solid.Faces if isinstance(f.Surface, Part.Cylinder)]
                radii = sorted({round(float(c.Radius), 6) for c in cylinders})
                # A pin's ends have boundary vertices. This vertex span is
                # evidence for that family, not a general oriented bounding box.
                axial_span = None
                if cylinders and 2.9 <= max(radii) <= 3.45:
                    axis = max(cylinders, key=lambda c: c.Radius).Axis
                    projections = [v.Point.dot(axis) for v in solid.Vertexes]
                    if projections:
                        axial_span = max(projections) - min(projections)
                box = solid.BoundBox
                solids.append({
                    "id": f"{root.Name}/solid-{index}",
                    "source_candidates": source_candidates(solid, evidence),
                    "volume_mm3": volume, "area_mm2": float(solid.Area),
                    "center_mm": list(solid.CenterOfMass),
                    "inertia_mm5": [[getattr(inertia, f"A{i}{j}") for j in range(1, 4)]
                                    for i in range(1, 4)],
                    "cylinder_radii_mm": radii,
                    "pin_axis_vertex_span_mm": axial_span,
                    "bbox_world_mm": [box.XMin, box.YMin, box.ZMin,
                                      box.XMax, box.YMax, box.ZMax],
                })
        if not solids:
            raise ValueError("No final assembly solids found")
        return {"schema": "sling-lift-geometry-v1", "units": "mm",
                "selection": strategy, "roots": [o.Name for o in roots],
                "skipped_non_solid_roots": skipped, "solids": solids,
                "solid_count": len(solids),
                "total_volume_mm3": sum(s["volume_mm3"] for s in solids),
                "limitations": ["Solids are geometric units, not necessarily BOM parts.",
                                 "Saved shapes only; no rebuild or mechanism motion test.",
                                 "World bounding boxes are diagnostic only, not size comparisons."]}

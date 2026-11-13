# Geometry measurement: first implementation

`geometry_stage.py` runs inside FreeCAD and delegates to
`common/freecad_geometry.py`, which reads final assembly solids.
It prefers visible top-level assemblies, resolving their final shapes through
`Part.getShape`. For documents without an Assembly object, it falls back to
visible root shapes and excludes linked source definitions. The selected roots
and fallback strategy are recorded for review. No candidate is saved or recomputed.
Each solid also records possible source occurrences, attributed using volume
and world center of mass. Names and labels explain evidence only; the matcher
does not use them. Ambiguous attributions remain a list rather than a forced
identity.

`common/geometry_compare.py` runs in normal Python with NumPy. It compares
volume, area, and principal inertia lengths, with cylinder radii as additional
shape evidence. Principal inertia lengths are equivalent-ellipsoid semiaxes,
not literal widths, thicknesses, or hole-center distances. They are unchanged
by rigid rotation, translation, and reflection, and scale linearly.

Shape descriptors normalized by volume support name-independent one-to-one
matching. Absolute sizes are retained, so normalization does not erase a global
scale error. An estimated scale and its sample range are reported; similar
shapes at different sizes can make that estimate ambiguous. Unmatched entries
are explicit. Matching tolerances are exploratory diagnostics, not grading rules.

Run from the repository root with Python containing NumPy:

```powershell
$env:FREECAD_CMD = 'C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe'
python tools/measure_geometry.py
python -m unittest discover -s tests -p 'test_geometry_compare.py' -v
```

The runner writes measurements, pair comparisons, and a summary under
`FreeCAD/4_sling_lift/results/geometry/`. Source names appear only as evidence
identifiers; no filename or object label contributes to matching.

## Limits and next work

- Solid count is not a bill-of-materials part count. One component may contain
  several solids, and fusing or splitting valid geometry changes correspondence.
- Volume, area, inertia, and cylinder radii cannot prove exact shape equality.
  Detailed hole detection, hole-center distances, and surface comparison remain.
- World bounding boxes and centers are recorded for inspection. They are not
  used to judge dimensions or assembly pose.
- Hidden output selection and unusual document organizations need further
  coverage. Multiple visible assemblies are retained and reported explicitly.
- No joint, articulation, or parameter perturbation checks are implemented here.
- The grading harness is unchanged; no reward or 6-point score is assigned yet.

# Sling lift grading notes

The harness grades six criteria, each worth one point, plus an unweighted
gate requiring readable final solid geometry. It uses the supplied CAD assets
unchanged, as confirmed by the task author. The gate checks the saved solids;
it does not claim that every feature survives a forced full rebuild.

## Measurement and scoring

`measure_stage.py` opens the saved model in FreeCAD and extracts its final
assembly solids. `common/geometry_compare.py` pairs solids one to one using
volume, surface area, principal inertia lengths, and cylinder radii. It
matches without relying on object labels, file names, or a particular
document tree. Size and shape descriptors are invariant to rigid movement
and reflection. Absolute size errors are retained after matching.

Each reference solid contributes half of its share of the solid count and
half of its share of reference volume. This gives small components some
credit without giving a washer and a major structural part equal weight.
Unmatched reference solids lose their full weight. For a matched solid, the
larger of the relative inertia-size error and normalized shape descriptor
error sets quality: full at or below 0.01, linear down to zero at 0.20. These
are rubric thresholds for approximate descriptors, not manufacturing
tolerances. Unexpected candidate solids reduce credit by increasing the
denominator. A solid split/fusion or an assembly with unusual organization
can still affect correspondence; matching is not proof of exact B-rep or
assembly pose equality.

The two 55 mm sleeves lose local geometry credit against the 50 mm reference.
No separate deduction is applied for mirroring: its dimensions can still
be correct. The missing Washer_A loses geometry credit; joint credit must be
based on separate evidence. Up to two unmatched spring-pin-shaped solids
are permitted because the drawing includes them and the supplied reference
omits them. The allowance checks axial vertex span, cylindrical radii, and
volume; it is not an ISO certification or verification of pin placement.
Pins are optional so the supplied reference can receive full geometry credit.

## Observed scores

| Model | Geometry | Mating | Articulation | Constraints | Drive geometry | Signature | Total / 6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 6.0000 |
| Mirrored | 0.9827 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5.9827 |
| Dummy joints | 0.9827 | 0.6609 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5.6436 |
| Half finished | 0.9005 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5.9005 |
| Swapped limits | 0.9827 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5.9827 |
| Missing Washer_A | 0.9910 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5.9910 |

All four models containing two unmatched drawing pins had those pins
accepted. The detailed evidence includes individual solid matches and the
separate sources of score loss.

## Joint evidence and remaining work

`common/freecad_joints.py` follows the active assembly and its linked
subassemblies. It records the two references for each joint, their direct
assembly membership, suppression, and enabled limits. Direct membership is
an investigative signal: a reference outside it may still be legitimate
through a nested assembly path.

The stage now resolves saved connector frames with the installed Assembly
workbench's placement helper. It measures origin separation, lateral offset
from the first connector axis, signed axial position, and angular differences.
The saved pose is compared with enabled limits. For example, the reference
slider has near-zero lateral offset and about 158.73 mm axial separation;
axial separation is allowed for a slider. An `AssemblyLink` has its own
component and joint copies. Inspecting its `LinkedObject` instead observes
the prototype, which is not the assembly being solved. This explains the
previously reported +180 mm reading outside [-180, -130] mm: it was on the
swapped-limits model's prototype. Its active slider instead starts at
-130 mm and stays within the interval during the sampled stroke. There is
no demonstrated active limit violation in that test. The missing-washer
model references the D-ring shackle and also stays within its limits.

## Native motion probe

Run `python tools/evaluate_motion.py` with `FREECAD_CMD` configured. The
probe opens each file in a separate FreeCAD process with a 45-second timeout.
It adds an in-memory driver to an existing slider, commands a 5 mm stroke
from its saved position toward available travel, and uses the native
kinematic solver. No authored joint is replaced or disabled. It verifies
the observed displacement (within 0.05 mm) and reports measured joint
rotation, connector gaps, axis deviation, and enabled-limit violations at
sampled positions. It does not save the document.

All six supplied models completed the short stroke. In the reference,
eight revolute joints rotated, by up to about 1.57 degrees, with practically
zero revolute-origin gap. The mirrored, half-finished, swapped-limits and
missing-washer models also kept the measured revolute origins aligned. The
dummy-joint model moved but had a 6 mm revolute-origin gap and a maximum
revolute axis deviation of about 62.58 degrees. Those maxima can occur at
different joints or frames. The reference also had up to 0.531 mm origin
separation on a fixed joint, which is reported rather than treated as a
revolute fault. See `results/motion/summary.json` and the per-model reports.

The probe currently requires one active assembly and one resolved slider.
A short sampled stroke is not evidence of full range, collision clearance,
or correct constraints on every part. A connector can be aligned yet
connect the wrong components or be redundant.

## Mechanism scoring

Mating uses movable joints (revolute, slider and cylindrical) in the saved
pose and sampled solver frames. Revolute origins should coincide; slider
and cylindrical connectors may separate along their axis. For the relevant
gap, full credit is awarded through 0.1 mm and falls to zero at 2 mm. Axis
alignment similarly falls from full through 1 degree to zero at 10 degrees.
These are diagnostic thresholds, not manufacturing tolerances. The lower
of the gap and angle credits is retained. Each distinct joint type and
endpoint pair contributes its worst observed reading, so repeated copies
of the same connection cannot earn extra credit. An unresolved connector
gets no credit. The mean connection credit is multiplied by coverage of
four measured pivot pairs, a provisional minimum for pantograph evidence.
This leaves room for alternatives that represent coaxial joints with fewer
connections than the reference. The check does not establish complete
pantograph topology or physical contact. Fixed hardware joints and distance
constraints are reported separately and do not enter this alignment score.

Articulation is measured independently: travel credit is proportional to
verified displacement out of 5 mm (full within 0.05 mm), multiplied by
rotation coverage up to two distinct revolute connections changing by
more than 0.1 degree. Unverified travel or an enabled-limit violation gets
no articulation credit. In particular, a model can move and still lose
mating credit. FreeCAD motion runs in a separate, bounded process so a
motion failure does not discard already measured geometry. The short
stroke does not grade the entire permitted travel interval.

## Parametric scoring

The parameter stage resolves visible assembly occurrences to their final
solid definitions and follows dependencies upstream from each Body Tip or
standalone solid. Names are used to identify objects inside a document and
to explain the evidence, not to recognize a candidate's parts by label.
Unrelated hidden solids and unused feature history do not earn credit.

- **Carries dimensional constraints.** Count active driving sketch dimensions
  and editable dimension properties on supported solid-building features.
  Coverage scales to full at six controls spanning at least three distinct
  final definitions. This is a minimum demonstration of distributed controls,
  not an incentive to match the reference's feature count.
- **Signature dimensions present.** Six equally weighted dimension families
  are checked: 120 mm pivot-center spacing, 12.2 and 16.2 mm pivot bores,
  33.7 mm sleeve outside diameter, 20.2 mm sleeve bore, and 10 mm plate
  thickness. For spacing, the constraint must connect centers of two pivot
  circles and their geometry must confirm the separation. Radius controls
  are converted to diameters. The other five are typed dimensional evidence
  within the active dependency graph, not proof that every occurrence of a
  corresponding part has the dimension. The bands in `sling_parameters.py`
  identify nominal dimensions; they are not manufacturing tolerances.
- **Dimensions drive the geometry.** Try at most 12 selected, directly
  editable length controls in a separate FreeCAD process. Increase one by
  1%, recompute its dependent final definitions, and compare per-solid volume,
  area and inertia trace. Revert the value and check that the geometry returns
  to baseline before trying another. Full credit requires three distinct
  final definitions to respond. In the reference, the tested 120 mm spacing,
  12.2 mm diameter and 20.2 mm diameter each changed a different final solid.

All six supplied models retain the measured parametric behavior; the
half-finished example still has the six signature dimension families and
three responsive final definitions. Its missing geometry is penalized
under geometry only. A successful perturbation is evidence for the tested
control, not a full rebuild or proof that all dimensions are editable.
Expression-bound dimensions are inventoried where recognized, but their
upstream spreadsheet or expression drivers are not perturbed. Unlisted
feature types and alternative encodings of signature dimensions can be
undercredited. The finite probe budget can miss valid controls.

Run `python tools/evaluate_sling_lift.py` from the repository root with
`FREECAD_CMD` configured and NumPy installed. The batch report is written to
`FreeCAD/4_sling_lift/results/harness/`. Each model's JSON has the geometry
score breakdown and the joint, motion, and parameter evidence.

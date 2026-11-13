"""Explain geometric mismatches using source labels, without grading by names."""
import json
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "FreeCAD/4_sling_lift"
OUTPUT = TASK / "results/geometry"


def feature_lengths(path):
    """Forensic saved-parameter evidence only; never used for scoring/matching."""
    with zipfile.ZipFile(path) as archive:
        tree = ET.fromstring(archive.read("Document.xml"))
    types = {obj.get("name"): obj.get("type") for obj in tree.findall("./Objects/Object")}
    result = {}
    for obj in tree.findall("./ObjectData/Object"):
        name = obj.get("name")
        if not types[name].startswith("PartDesign::"):
            continue
        for prop in obj.findall("./Properties/Property"):
            value = prop.find("Float")
            if prop.get("name") in ("Length", "Length2") and value is not None:
                result[(name, prop.get("name"))] = float(value.get("value"))
    return result


def sources(solid):
    return solid.get("source_candidates", [])


def main():
    reference = json.loads((OUTPUT / "solution/measure.json").read_text(encoding="utf-8"))
    ref = {s["id"]: s for s in reference["solids"]}
    lengths = feature_lengths(TASK / "solution/solution.FCStd")
    rows = []
    for path in sorted((TASK / "examples").glob("*/*.FCStd")):
        measurement = json.loads((OUTPUT / path.stem / "measure.json").read_text(encoding="utf-8"))
        comparison = json.loads((OUTPUT / path.stem / "comparison.json").read_text(encoding="utf-8"))
        candidate = {s["id"]: s for s in measurement["solids"]}
        changed = []
        for pair in comparison["matches"]:
            if pair["max_relative_size_error"] > 0.001 or pair["shape_descriptor_error"] > 0.001:
                changed.append({**pair, "reference_sources": sources(ref[pair["reference_id"]]),
                                "candidate_sources": sources(candidate[pair["candidate_id"]])})
        candidate_lengths = feature_lengths(path)
        parameter_diffs = [{"object": obj, "property": prop, "reference": value,
                            "candidate": candidate_lengths[(obj, prop)]}
                           for (obj, prop), value in lengths.items()
                           if (obj, prop) in candidate_lengths and abs(candidate_lengths[(obj, prop)] - value) > 1e-9]
        row = {"model": path.stem,
               "attributed_solids": sum(bool(sources(s)) for s in measurement["solids"]),
               "total_solids": len(candidate),
               "unmatched_reference": [ref[i] for i in comparison["unmatched_reference"]],
               "unmatched_candidate": [candidate[i] for i in comparison["unmatched_candidate"]],
               "changed_matches": changed, "saved_parameter_differences": parameter_diffs}
        rows.append(row)
    (OUTPUT / "audit.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = ["# Geometry mismatch audit", "",
             "Source labels and saved parameter names are forensic evidence only; they do not drive matching or grading.",
             "An unmatched solid is not automatically a modeling error. Compare the technical drawing.", ""]
    for row in rows:
        lines += ["## " + row["model"], "", f"Attributed solids: {row['attributed_solids']}/{row['total_solids']}.", ""]
        for category in ("unmatched_reference", "unmatched_candidate"):
            lines += [category + ":", ""]
            for solid in row[category]:
                labels = "; ".join(s["source_label"] for s in sources(solid)) or "unattributed"
                lines.append(f"- {solid['id']}: {labels}; volume {solid['volume_mm3']:.6f} mm^3.")
            if not row[category]:
                lines.append("- None.")
            lines.append("")
        lines += ["Changed matched solids (diagnostic threshold 0.1%, not grading tolerance):", ""]
        for pair in row["changed_matches"]:
            labels = "; ".join(s["source_label"] for s in pair["reference_sources"])
            lines.append(f"- {labels}: inertia-size difference {pair['max_relative_size_error']:.4%}; volume ratio {pair['volume_ratio']:.6f}.")
        if not row["changed_matches"]:
            lines.append("- None.")
        lines += ["", "Saved PartDesign length changes (same internal IDs, forensic only):", ""]
        for diff in row["saved_parameter_differences"]:
            lines.append(f"- {diff['object']}.{diff['property']}: {diff['reference']} -> {diff['candidate']} mm.")
        if not row["saved_parameter_differences"]:
            lines.append("- None.")
        lines.append("")
    (OUTPUT / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUTPUT / "audit.md")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Coverage / confidence report for a parsed PMS (honest extraction metrics)."""
from __future__ import annotations
from typing import Any, Dict


def coverage_report(data: Dict[str, Any]) -> Dict[str, Any]:
    classes = data["classes"]
    n = len(classes)
    comps = sum(c.get("component_count", 0) for c in classes)
    full_hdr = sum(1 for c in classes if c.get("service") and c.get("main_material")
                   and c.get("flange_rating_face"))
    with_pt = sum(1 for c in classes if c.get("temp_C") and c.get("press_barg"))
    zero = [c["class"] for c in classes if not c.get("component_count")]
    no_part = sum(1 for c in classes for x in c.get("components", []) if not x.get("part"))
    return {
        "class_count": n,
        "component_rows": comps,
        "classes_full_header": full_hdr,
        "classes_full_header_pct": round(100 * full_hdr / n, 1) if n else 0,
        "classes_with_pt_table": with_pt,
        "classes_zero_components": zero,
        "rows_without_part_label": no_part,
    }


def format_report(rep: Dict[str, Any]) -> str:
    lines = [
        f"Classes parsed            : {rep['class_count']}",
        f"Component rows            : {rep['component_rows']}",
        f"Classes with full header  : {rep['classes_full_header']} ({rep['classes_full_header_pct']}%)",
        f"Classes with P-T table    : {rep['classes_with_pt_table']}",
        f"Rows without part label   : {rep['rows_without_part_label']}",
    ]
    if rep["classes_zero_components"]:
        lines.append(f"Classes w/ 0 components   : {', '.join(rep['classes_zero_components'])}")
    return "\n".join(lines)

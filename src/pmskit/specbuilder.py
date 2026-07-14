# -*- coding: utf-8 -*-
"""Spec Builder: propose a pipe class from design conditions.

Given a material, flange rating, service and size range plus the class
pressure-temperature points, pick — for each size — the *minimum* standard pipe
schedule whose wall (after mill under-tolerance) satisfies the ASME B31.3
pressure-design thickness, then assemble a class in the canonical PMS schema.

Needs a material datapack for allowable stress (see pmskit.database); without it,
sizes are returned as 'no-stress-data' and no schedule is proposed (never a guess).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from .database import (load_schedules, load_materials, pipe_dims, outer_diameter,
                       find_material, allowable_stress)
from .thickness import governing_case
from .compliance import _NPS_ORDER, _sizes_in_range, _mm

# Human-friendly schedule label preference when several keys map to the same wall.
_LABEL_PREF = ["10", "20", "30", "STD", "40", "60", "XS", "80", "100", "120", "140", "160", "XXS"]


def _ordered_schedules(pipe_entry) -> List[tuple]:
    """Return [(label, wall_mm)] sorted by wall thickness ascending, de-duplicated."""
    walls = pipe_entry.get("wall", {})
    by_wall: Dict[float, str] = {}
    for label, w in walls.items():
        # prefer a nicer label for equal walls
        if w not in by_wall or _LABEL_PREF.index(label) < _LABEL_PREF.index(by_wall[w]) \
                if (label in _LABEL_PREF and by_wall.get(w) in _LABEL_PREF) else w not in by_wall:
            by_wall[w] = label
    return sorted(((lbl, w) for w, lbl in by_wall.items()), key=lambda t: t[1])


def suggest_schedule(nps: str, pts, material, *, ca=0.0, E=1.0, W=1.0, mill_tol=0.125,
                     schedules=None):
    schedules = schedules or load_schedules()
    p = pipe_dims(schedules, nps)
    if not p:
        return {"nps": nps, "status": "no-dimension", "schedule": None}
    D = p["od"]
    if material is None:
        return {"nps": nps, "status": "no-stress-data", "schedule": None, "OD_mm": D}
    g = governing_case(pts, D, lambda T: allowable_stress(material, T),
                       E=E, W=W, family=material.get("family", "ferritic"),
                       c_mm=ca, mill_tol=mill_tol)
    if g is None:
        return {"nps": nps, "status": "no-stress-data", "schedule": None, "OD_mm": D}
    req = g["t_min_with_allowances_mm"]
    for label, wall in _ordered_schedules(p):
        if wall * (1 - mill_tol) >= req:
            return {"nps": nps, "status": "OK", "schedule": label, "wall_mm": wall,
                    "required_mm": req, "OD_mm": D, "governing": g}
    return {"nps": nps, "status": "no-adequate-schedule", "schedule": None,
            "required_mm": req, "OD_mm": D, "governing": g}


def build_spec(*, class_name: str, material_spec: str, grade: Optional[str],
               service: str, flange_rating_face: str, corrosion_allowance: str,
               temp_C: List[str], press_barg: List[str], size_from: str, size_to: str,
               end: str = "BE", pipe_standard: str = "ASME B36.10M",
               datapack: Optional[str] = None, E=1.0, W=1.0, mill_tol=0.125,
               company: str = "SPEC-BUILDER") -> Dict[str, Any]:
    schedules = load_schedules()
    materials = load_materials(datapack)
    material = find_material(materials, material_spec, grade)
    ca = _mm(corrosion_allowance)
    pts = [(float(t), float(p)) for t, p in zip(temp_C, press_barg)
           if _is_num(t) and _is_num(p)]

    per_size = [suggest_schedule(nps, pts, material, ca=ca, E=E, W=W,
                                 mill_tol=mill_tol, schedules=schedules)
                for nps in _sizes_in_range(size_from, size_to)
                if pipe_dims(schedules, nps)]

    # group consecutive sizes sharing the same proposed schedule into PIPE rows
    comps: List[dict] = []
    grade_txt = f" GR.{grade}" if grade else ""
    run = []
    def flush_run():
        if not run:
            return
        sched = run[0]["schedule"]
        sched_txt = sched if sched in ("STD", "XS", "XXS") else (f"SCH{sched}" if sched else None)
        comps.append({
            "part": "PIPE", "symbol": "(P)",
            "size_from": run[0]["nps"], "size_to": run[-1]["nps"],
            "size_raw": [run[0]["nps"], run[-1]["nps"]],
            "description": (f"{material_spec}{grade_txt}, SMLS, {end}, {pipe_standard} [{sched_txt}]"
                           if sched else f"{material_spec}{grade_txt} — NO ADEQUATE SCHEDULE (review)"),
            "notes": [],
            "_suggested_schedule": sched,
            "_required_mm": run[0].get("required_mm"),
        })
    for s in per_size:
        if run and s.get("schedule") == run[-1].get("schedule"):
            run.append(s)
        else:
            flush_run(); run = [s]
    flush_run()

    cls = {
        "class": class_name, "service": service,
        "main_material": material_spec + grade_txt,
        "corrosion_allowance": corrosion_allowance,
        "flange_rating_face": flange_rating_face,
        "temp_C": list(temp_C), "press_barg": list(press_barg),
        "particular_notes": "Auto-generated by pms-toolkit Spec Builder (ASME B31.3). "
                            + ("Allowable stresses are SYNTHETIC demo values — replace with a real datapack."
                               if materials.get("meta", {}).get("SYNTHETIC") else ""),
        "components": comps, "component_count": len(comps),
    }
    return {
        "meta": {"company": company, "generator": "pms-toolkit spec-builder",
                 "code": "ASME B31.3", "class_count": 1,
                 "materials_source": materials.get("meta", {}).get("_source"),
                 "synthetic_stress": bool(materials.get("meta", {}).get("SYNTHETIC"))},
        "classes": [cls],
        "sizing_detail": per_size,
    }


def _is_num(v):
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False

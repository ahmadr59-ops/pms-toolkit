# -*- coding: utf-8 -*-
"""Flange/valve pressure-temperature rating engine (ASME B16.5 / B16.34 semantics).

Implements only the *method*: linear interpolation of a rating curve, class
selection, and per-class adequacy checks against the PMS design points. It
contains NO copyrighted rating tables — values load from a private, git-ignored
datapack (see docs/datapacks.md):

    datapacks/flanges.json                     (your licensed data; preferred)
    examples/flanges.datapack.sample.json      (SYNTHETIC demo fallback)

Rating semantics (per B16.5 para. 2 / B16.34):
  * curve = ascending list of [temp_C, max_working_pressure] points
  * between listed temperatures -> linear interpolation
  * below the first listed temperature -> rating is constant (first value)
  * above the last listed temperature -> not rated (None)

Valves: ASME B16.34 standard-class ratings use the same material groups, so the
same engine serves flanged valves; special-class curves can be added to the
datapack as extra classes if ever needed.
"""
from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .database import _load_json  # same JSON loader, keep one code path

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Standard flange class series (public fact, ASME B16.5).
STANDARD_CLASSES = [150, 300, 400, 600, 900, 1500, 2500]

_COMPONENT_PACKS = ("flanges", "fittings", "valves", "gaskets", "bolting")


def load_component_pack(name: str, datapack: Optional[str] = None) -> Dict[str, Any]:
    """Load a component datapack. Preference: explicit path -> private
    datapacks/<name>.json -> synthetic sample -> empty skeleton."""
    if name not in _COMPONENT_PACKS:
        raise ValueError(f"unknown component pack '{name}' (expected one of {_COMPONENT_PACKS})")
    candidates = [datapack] if datapack else []
    candidates += [
        os.path.join(_ROOT, "datapacks", f"{name}.json"),
        os.path.join(_ROOT, "examples", f"{name}.datapack.sample.json"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            data = _load_json(c)
            data.setdefault("meta", {})["_source"] = os.path.relpath(c, _ROOT)
            return data
    return {"meta": {}}


def load_flanges(datapack: Optional[str] = None) -> Dict[str, Any]:
    return load_component_pack("flanges", datapack)


# ---- material-group resolution ------------------------------------------
def _norm(s: str) -> str:
    """Normalize material text for spec matching. Unifies grade/class markers
    so 'A350 Gr. LF2' matches 'A350 LF2', and 'Cl. 1' / 'Class 1' / the common
    'CI. 1' transcription typo all become 'CL1'. No other rewriting."""
    s = (s or "").upper()
    s = re.sub(r"\b(GRADE|GR)\b\.?", " ", s)
    s = re.sub(r"\b(CLASS|CL|CI)\b\.?\s*(?=\d)", "CL", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def find_group(pack: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
    """Resolve a material group from a group code ('1.1') or a material text
    ('ASTM A105', 'A216-WCB', 'CS A106 Gr.B'). Longest spec match wins so that
    e.g. 'A182 F316L' does not stop at a hypothetical 'A182 F3'."""
    if not text:
        return None
    groups = pack.get("material_groups") or []
    t = (text or "").strip()
    for g in groups:  # exact group code first
        if g.get("group") == t:
            return g
    tn = _norm(t)
    best, best_len = None, 0
    for g in groups:
        for spec in g.get("specs") or []:
            sn = _norm(spec)
            if sn and sn in tn and len(sn) > best_len:
                best, best_len = g, len(sn)
    return best


# ---- rating curve ---------------------------------------------------------
def rated_pressure(group: Dict[str, Any], cls, temp_c: float) -> Optional[float]:
    """Max working pressure of `cls` at `temp_c` for a material group, or None
    if the class/temperature is not rated."""
    curve = (group.get("ratings") or {}).get(str(cls))
    if not curve:
        return None
    pts: List[Tuple[float, float]] = sorted((float(a), float(b)) for a, b in curve)
    if temp_c <= pts[0][0]:
        return pts[0][1]
    if temp_c > pts[-1][0]:
        return None
    for (t1, p1), (t2, p2) in zip(pts, pts[1:]):
        if t1 <= temp_c <= t2:
            if t2 == t1:
                return min(p1, p2)
            return p1 + (p2 - p1) * (temp_c - t1) / (t2 - t1)
    return None


def select_class(group: Dict[str, Any], points: List[Tuple[float, float]],
                 classes: Optional[List[int]] = None) -> Optional[int]:
    """Smallest standard class whose rated pressure covers every
    (temp_C, press_barg) design point. None if no listed class suffices."""
    if not points:
        return None
    for cls in sorted(classes or STANDARD_CLASSES):
        ok = True
        for t, p in points:
            r = rated_pressure(group, cls, t)
            if r is None or r < p:
                ok = False
                break
        if ok:
            return cls
    return None


# ---- PMS adequacy check ---------------------------------------------------
_CLASS_RE = re.compile(r"\bCL\.?\s*(\d{2,4})\b", re.I)


def _is_num(x) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def _pt_points(c: Dict[str, Any]) -> List[Tuple[float, float]]:
    temps, press = c.get("temp_C") or [], c.get("press_barg") or []
    return [(float(t), float(p)) for t, p in zip(temps, press)
            if _is_num(t) and _is_num(p)]


def flange_adequacy(data: Dict[str, Any], datapack: Optional[str] = None) -> List[dict]:
    """For every pipe class, check the specified flange class against the
    class's own P-T design points. Never a false pass: anything unresolvable is
    reported 'not-evaluated'. Returns one row per pipe class."""
    pack = load_flanges(datapack)
    synthetic = bool((pack.get("meta") or {}).get("SYNTHETIC"))
    rows: List[dict] = []
    for c in data.get("classes", []):
        flange_txt = c.get("flange_rating_face") or ""
        m = _CLASS_RE.search(flange_txt)
        cls_num = int(m.group(1)) if m else None
        group = find_group(pack, c.get("main_material") or "")
        pts = _pt_points(c)
        base = {"class": c.get("class"), "flange": flange_txt, "class_number": cls_num,
                "material_group": group.get("group") if group else None,
                "synthetic_data": synthetic}
        if cls_num is None or group is None or not pts:
            why = ("no CL.### in flange text" if cls_num is None else
                   "material group not resolved from main_material" if group is None else
                   "no numeric P-T design points")
            rows.append({**base, "status": "not-evaluated", "worst": None,
                         "margin_pct": None, "suggested_class": None, "remark": why})
            continue
        worst, worst_margin = None, None
        evaluated = True
        for t, p in pts:
            r = rated_pressure(group, cls_num, t)
            if r is None:
                evaluated = False
                worst = {"temp_C": t, "press_barg": p, "rated_barg": None}
                break
            margin = (r - p) / p * 100.0 if p > 0 else float("inf")
            if worst_margin is None or margin < worst_margin:
                worst_margin = margin
                worst = {"temp_C": t, "press_barg": p, "rated_barg": round(r, 2)}
        if not evaluated:
            rows.append({**base, "status": "not-evaluated", "worst": worst,
                         "margin_pct": None, "suggested_class": None,
                         "remark": f"class {cls_num} not rated at {worst['temp_C']}C "
                                   f"for group {group.get('group')}"})
            continue
        status = "adequate" if worst_margin >= 0 else "inadequate"
        suggested = select_class(group, pts) if status == "inadequate" else None
        rows.append({**base, "status": status, "worst": worst,
                     "margin_pct": round(worst_margin, 1), "suggested_class": suggested,
                     "remark": ("OK" if status == "adequate" else
                                f"rated below design at {worst['temp_C']}C; "
                                f"smallest adequate class: {suggested or 'none listed'}")})
    return rows

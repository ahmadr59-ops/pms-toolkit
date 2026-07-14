# -*- coding: utf-8 -*-
"""Shared engineering database: pipe schedule dimensions + material master.

Schedule dimensions (data/schedules.json) are factual pipe geometry and ship
with the repo. Allowable-stress values are copyrighted ASME data and are NOT in
the public repo — they are loaded from a private, git-ignored datapack:

    datapacks/materials.json     (your licensed data; preferred)
    examples/materials.datapack.sample.json   (SYNTHETIC demo fallback)

so thickness/compliance features work locally without publishing copyrighted tables.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schedules(path: Optional[str] = None) -> Dict[str, Any]:
    path = path or os.path.join(_ROOT, "data", "schedules.json")
    return _load_json(path)


def load_materials(datapack: Optional[str] = None) -> Dict[str, Any]:
    """Load the material master. Preference: explicit datapack -> private
    datapacks/materials.json -> synthetic sample -> empty public skeleton."""
    candidates = [datapack] if datapack else []
    candidates += [
        os.path.join(_ROOT, "datapacks", "materials.json"),
        os.path.join(_ROOT, "examples", "materials.datapack.sample.json"),
        os.path.join(_ROOT, "data", "materials.json"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            data = _load_json(c)
            data.setdefault("meta", {})["_source"] = os.path.relpath(c, _ROOT)
            return data
    return {"meta": {}, "materials": []}


# ---- schedule helpers --------------------------------------------------
def _canon_sched(tok: str, aliases: Dict[str, str]) -> Optional[str]:
    if not tok:
        return None
    t = tok.upper().replace(" ", "").replace("SCH.", "SCH")
    if t in aliases:
        return aliases[t]
    t2 = t.replace("SCH", "")
    return t2 or t


def pipe_dims(schedules: Dict[str, Any], nps: str):
    return schedules.get("pipe", {}).get(str(nps))


def wall_thickness(schedules: Dict[str, Any], nps: str, schedule_token: str) -> Optional[float]:
    p = pipe_dims(schedules, nps)
    if not p:
        return None
    key = _canon_sched(schedule_token, schedules.get("aliases", {}))
    walls = p.get("wall", {})
    if key in walls:
        return walls[key]
    # token might already be STD/XS/XXS
    up = (schedule_token or "").upper().strip()
    return walls.get(up)


def outer_diameter(schedules: Dict[str, Any], nps: str) -> Optional[float]:
    p = pipe_dims(schedules, nps)
    return p.get("od") if p else None


# ---- material helpers --------------------------------------------------
def find_material(materials: Dict[str, Any], spec: Optional[str], grade: Optional[str] = None):
    if not spec:
        return None
    def norm(s):
        return re.sub(r"[\s.]+", "", (s or "").upper())
    ns = norm(spec)
    best = None
    for m in materials.get("materials", []):
        if norm(m.get("spec")) == ns:
            if grade and norm(m.get("grade")) == norm(grade):
                return m
            best = best or m
    return best


def allowable_stress(material: Dict[str, Any], temp_c: float) -> Optional[float]:
    """Linear-interpolate S (MPa) at temp_c from the material's [temp, S] points."""
    pts = material.get("s") if material else None
    if not pts:
        return None
    pts = sorted((float(t), float(s)) for t, s in pts)
    if temp_c <= pts[0][0]:
        return pts[0][1]
    if temp_c >= pts[-1][0]:
        return pts[-1][1]
    for (t0, s0), (t1, s1) in zip(pts, pts[1:]):
        if t0 <= temp_c <= t1:
            return s0 + (s1 - s0) * (temp_c - t0) / (t1 - t0)
    return pts[-1][1]

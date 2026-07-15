# -*- coding: utf-8 -*-
"""Convert a local B31.3 wall-thickness calculator's material table into a
pms-toolkit material datapack (materials.json).

The calculator embeds an array ``DEFAULT_MATERIALS = [ {spec, desc, form,
minTemp, maxTemp, s, ref}, ... ]`` where ``s`` is a "temp:stress,..." string.
This reader extracts it and maps to the datapack schema. Run it locally on your
own file — the allowable-stress values are yours and stay local.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List

_ARR = re.compile(r"DEFAULT_MATERIALS\s*=\s*\[(.*?)\]\s*;", re.S)
_OBJ = re.compile(r"\{(.*?)\}", re.S)
_AUSTENITIC = re.compile(r"austenit|stainless|18Cr|Cr-\d*Ni|TP3\d\d|CF8|A312|A358|A403|A182 F3", re.I)


def _field(block: str, name: str):
    m = re.search(rf'{name}\s*:\s*"([^"]*)"', block)
    if m:
        return m.group(1)
    m = re.search(rf"{name}\s*:\s*(-?\d+(?:\.\d+)?)", block)
    return m.group(1) if m else None


def _split_spec_grade(spec: str):
    """'ASTM A106 Gr. B' -> ('ASTM A106','B'); 'ASTM A312 TP304' -> ('ASTM A312','TP304')."""
    if not spec:
        return spec, None
    m = re.search(r"\bGr\.?\s*([A-Za-z0-9]+)", spec, re.I)
    if m:
        base = spec[:m.start()].strip()
        return base, m.group(1)
    m = re.search(r"\b(TP\d+[A-Za-z]*|X\d+|P\d+|F\d+|WPB|WCB)\b", spec, re.I)
    if m:
        base = (spec[:m.start()] + spec[m.end():]).strip().rstrip(",")
        return re.sub(r"\s+", " ", base), m.group(1)
    return spec, None


def _parse_s(s: str) -> List[list]:
    out = []
    for pair in (s or "").split(","):
        pair = pair.strip()
        if ":" in pair:
            t, val = pair.split(":", 1)
            try:
                out.append([float(t), float(val)])
            except ValueError:
                continue
    return out


def parse_calculator_materials(html_text: str) -> List[Dict[str, Any]]:
    m = _ARR.search(html_text)
    if not m:
        raise ValueError("DEFAULT_MATERIALS array not found in the file")
    body = m.group(1)
    materials = []
    for om in _OBJ.finditer(body):
        block = om.group(1)
        spec_full = _field(block, "spec")
        if not spec_full:
            continue
        spec, grade = _split_spec_grade(spec_full)
        desc = _field(block, "desc") or ""
        family = "austenitic" if _AUSTENITIC.search(spec_full + " " + desc) else "ferritic"
        entry = {"spec": spec, "grade": grade, "family": family,
                 "min_temp": _num(_field(block, "minTemp")),
                 "max_temp": _num(_field(block, "maxTemp")),
                 "s": _parse_s(_field(block, "s") or "")}
        if entry["s"]:
            materials.append(entry)
    return materials


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def convert(html_path: str) -> Dict[str, Any]:
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        mats = parse_calculator_materials(f.read())
    return {"meta": {"schema": "material-master v1", "stress_units": "MPa",
                     "temp_units": "C", "source": "converted from local B31.3 calculator"},
            "materials": mats}

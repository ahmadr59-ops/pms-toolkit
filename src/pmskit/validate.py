# -*- coding: utf-8 -*-
"""Rule-based consistency checks for a parsed PMS.

IMPORTANT — scope and IP: these checks use only publicly-established engineering
*conventions* (the set of standard ASME B16.5 flange classes, standard facings,
standard pipe schedules, and physical monotonicity of pressure–temperature
ratings). They deliberately do NOT reproduce any copyrighted allowable-pressure
tables from ASME/API. Full numeric P–T validation requires the purchased
standard and must stay a local, user-supplied plug-in — never bundled here.

Findings have severity: 'error' (almost certainly wrong), 'warning' (unusual,
review), 'info' (note).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

# Public facts, not copyrighted tables:
ASME_B16_5_CLASSES = {150, 300, 400, 600, 900, 1500, 2500}
CAST_IRON_CLASSES = {125, 250}          # ASME B16.1
KNOWN_FACINGS = {"RF", "FF", "RTJ", "FFS", "RJ", "MFF", "LMF", "SMF"}
KNOWN_SCHEDULES = {"5", "10", "20", "30", "40", "60", "80", "100", "120", "140",
                   "160", "STD", "XS", "XXS", "5S", "10S", "40S", "80S", "STD.", "XS.", "XXS."}


def _finding(cls, severity, code, message, context=None):
    return {"class": cls, "severity": severity, "code": code,
            "message": message, "context": context}


def _class_number(flange_text):
    if not flange_text:
        return None
    m = re.search(r"\bCL\.?\s*(\d{2,4})\b", flange_text, re.I)
    return int(m.group(1)) if m else None


def _facing(flange_text):
    if not flange_text:
        return None
    m = re.search(r"\b(RTJ|FFS|RJ|RF|FF|MFF|LMF|SMF)\b", flange_text, re.I)
    return m.group(1).upper() if m else None


def validate(data: Dict[str, Any]) -> List[dict]:
    findings: List[dict] = []
    for c in data.get("classes", []):
        cls = c.get("class")
        flange = c.get("flange_rating_face")
        num = _class_number(flange)
        face = _facing(flange)

        # 1) flange class is a recognised pressure class
        if flange and num is not None and num not in ASME_B16_5_CLASSES | CAST_IRON_CLASSES:
            findings.append(_finding(cls, "warning", "FLANGE_CLASS_UNKNOWN",
                                     f"Flange class CL{num} is not a standard ASME B16.5/B16.1 class",
                                     flange))
        # 2) facing recognised
        if flange and face is None and re.search(r"CL", flange, re.I):
            findings.append(_finding(cls, "info", "FACING_MISSING",
                                     "No standard facing (RF/FF/RTJ...) found in flange rating", flange))
        elif face and face not in KNOWN_FACINGS:
            findings.append(_finding(cls, "warning", "FACING_UNKNOWN",
                                     f"Unrecognised facing '{face}'", flange))
        # 3) facing vs class convention (guidance, not a hard rule)
        if num and face == "RTJ" and num < 600:
            findings.append(_finding(cls, "warning", "RTJ_LOW_CLASS",
                                     f"RTJ facing is unusual below Class 600 (here CL{num})", flange))
        if num and face == "FF" and num >= 300:
            findings.append(_finding(cls, "warning", "FF_HIGH_CLASS",
                                     f"Flat-face (FF) is unusual at Class {num} and above", flange))

        # 4) corrosion allowance present/parsable
        if not c.get("corrosion_allowance"):
            findings.append(_finding(cls, "info", "CA_MISSING",
                                     "Corrosion allowance not captured for this class"))

        # 5) P-T array sanity (length + physical monotonicity)
        t, p = c.get("temp_C"), c.get("press_barg")
        if t and p:
            if len(t) != len(p):
                findings.append(_finding(cls, "error", "PT_LENGTH_MISMATCH",
                                         f"Temp points ({len(t)}) != pressure points ({len(p)})"))
            else:
                pv = _to_floats(p)
                if pv and any(b - a > 1e-9 for a, b in zip(pv, pv[1:])):
                    findings.append(_finding(cls, "warning", "PT_NOT_MONOTONIC",
                                             "Allowable pressure increases with temperature (check parse/data)",
                                             {"press_barg": p}))
        # 6) component-level flange class vs class rating
        if num:
            for x in c.get("components", []):
                if re.search(r"FLANGE|VALVE", (x.get("part") or ""), re.I):
                    cm = re.search(r"\bCL\.?\s*(\d{2,4})\b", x.get("description") or "", re.I)
                    if cm and int(cm.group(1)) not in {num} | {150, 300, 600, 800, 900, 1500, 2500}:
                        # allow common SW valve ratings (800) which differ from flange class
                        findings.append(_finding(cls, "info", "COMPONENT_CLASS_NOTE",
                                                 f"{x.get('part')} references CL{cm.group(1)} "
                                                 f"vs class flange CL{num}", x.get("description")))
        # 7) empty class
        if not c.get("component_count"):
            findings.append(_finding(cls, "warning", "NO_COMPONENTS",
                                     "Class has no parsed component rows"))
    return findings


def _to_floats(arr):
    out = []
    for v in arr:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return []
    return out


def summarize(findings: List[dict]) -> Dict[str, int]:
    s = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        s[f["severity"]] = s.get(f["severity"], 0) + 1
    return s

# -*- coding: utf-8 -*-
"""Normalize a verbatim component description into comparable fields.

PMS descriptions from different issuers describe the *same* item with different
wording, e.g.:
  NIOEC : "ASTM A234 GR.WPB SMLS LONG RADIUS BW AS PER ASME B16.9 SCH40"
  BORC  : "ASTM A234 WPB, BW, SMLS, LR, ASME B16.9 [AS PIPE]"
Comparing raw text would flag everything as different. This module extracts a
small set of engineering fields so comparison happens on meaning, not spelling:

  material   e.g. "ASTM A234"      (spec designation)
  grade      e.g. "WPB"            (grade / type)
  end        e.g. "BW"             (end connection: BW/SW/NPT/PE/BE/FLGD/RF/RTJ)
  radius     e.g. "LR"             (LR/SR for elbows)
  manuf      e.g. "SMLS"           (SMLS/WELDED/DSAW/ERW/FORGED/CAST)
  standards  e.g. ["ASME B16.9"]   (all referenced dimensional/mfg standards)
  rating_sch e.g. "SCH40"          (schedule or pressure class or wall)

Nothing is invented; unmatched tokens are dropped from the normalized form but
the original text is always preserved by the caller.
"""
from __future__ import annotations
import re
from typing import Dict, Any

_SPEC = re.compile(r"\b(?:ASTM|ASME|API|MSS|BS|EN|DIN)\s*[A-Z]?\d[\w.\-]*", re.I)
_MATERIAL = re.compile(r"\b(?:ASTM\s*A?\d{2,4}[A-Z]?|API\s*5[A-Z]{1,3}\d*|API\s*\d{3})\b", re.I)
_GRADE = re.compile(r"\b(?:GR\.?\s*)?(WPB(?:-W)?|WPL6|WP\d+|TP\d+[LH]?N?|GR\.?\s*B|B7|2H|F\d+|"
                    r"CF8M|CF8|WCB|WCC|LCB|LCC|CL\d+CR[\w.\-]*)\b", re.I)
_END = re.compile(r"\b(BW|SW|NPT|MNPT|FNPT|PE|BE|PBE|PLE|TSE|BLE|PSE|FLG(?:D)?|FLANGED|RTJ|RF|FF|THRD|SCRD)\b", re.I)
_RADIUS = re.compile(r"\b(LR|SR|LONG RADIUS|SHORT RADIUS)\b", re.I)
_MANUF = re.compile(r"\b(SMLS|SEAMLESS|WELDED|DSAW|SAW|ERW|EFW|FORGED|FORGING|CAST(?:ING)?)\b", re.I)
_STD = re.compile(r"\b(?:ASME|API|MSS(?:\s*SP)?|BS|EN|DIN)\s*[A-Z]*\s*[-\s]?\s*\d[\w.\-]*", re.I)
_SCH = re.compile(r"\bSCH\.?\s*[0-9]{1,3}[SS]?\b|\b(?:STD|XXS|XS)\b|\bCL\.?\s*\d{2,4}\b|\bCL\d+\b|"
                  r"\b\d+(?:\.\d+)?\s*MM(?:-?T)?\b|\bAS\s*PIPE\b", re.I)


def _first(rx, text, group=0):
    m = rx.search(text)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(group)).strip().upper()


def _canon_grade(g):
    if not g:
        return None
    g = re.sub(r"^GR\.?\s*", "", g).strip().upper()
    return g


def normalize(description: str) -> Dict[str, Any]:
    """Return normalized fields for a component description (best-effort)."""
    t = " " + (description or "") + " "
    material = _first(_MATERIAL, t)
    grade = _canon_grade(_first(_GRADE, t, 1))
    end = _first(_END, t, 1)
    radius = _first(_RADIUS, t, 1)
    radius = {"LONG RADIUS": "LR", "SHORT RADIUS": "SR"}.get(radius, radius)
    manuf = _first(_MANUF, t, 1)
    manuf = {"SEAMLESS": "SMLS", "FORGING": "FORGED", "CASTING": "CAST"}.get(manuf, manuf)
    rating = _first(_SCH, t)
    if rating:
        rating = rating.replace(" ", "").replace("SCH.", "SCH")
    stds = sorted({re.sub(r"\s+", " ", m.group(0)).upper().replace("  ", " ").strip()
                   for m in _STD.finditer(t)
                   if not re.match(r"^(?:ASTM|API)\s*A?\d", m.group(0), re.I)})
    # keep only true dimensional/mfg standards (ASME B##, API 6##, MSS SP-##, BS ####)
    stds = [s for s in stds if re.search(r"B\d|SP|API\s*6|BS\s*\d|EN\s*\d|DIN", s)]
    return {
        "material": material,
        "grade": grade,
        "end": end,
        "radius": radius,
        "manuf": manuf,
        "rating_sch": rating,
        "standards": stds,
    }


# Fields that count as an engineering change when they differ (ordered by importance).
COMPARE_FIELDS = ["material", "grade", "rating_sch", "manuf", "end", "radius", "standards"]

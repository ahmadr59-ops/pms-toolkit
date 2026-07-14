# -*- coding: utf-8 -*-
"""BORC (Bandar Abbas Refinery) PMS adapter.

The BORC PMS is a structured Excel workbook (.xls), one sheet per material
group. Each pipe class is a fixed-column block:
  LINE CLASS (col 16), SERVICE (col 6), MAIN MATERIAL (col 6),
  CORROSION ALLOWANCE (col 19), FLANGE RATING & FACE (col 29),
  TEMP/PRESS rows (cols 5,7,9,...), then component rows with
  NOTE (col 0), symbol/part (col 2), SIZE FROM (col 5), SIZE TO (col 7),
  DESCRIPTION (col 9), RATING/SCH (col 27/28/29).

Descriptions are preserved verbatim; the RATING/SCH column is appended to the
description in square brackets so it stays searchable and visible.
"""
from __future__ import annotations
import os
import re
from .base import PMSAdapter

# Column indices (0-based) in the BORC layout:
C_NOTE, C_PART, C_FROM, C_TO, C_DESC = 0, 2, 5, 7, 9
C_RATING = (27, 28, 29)
C_LINECLASS_VAL = 16
FLANGE_SUBTYPES = {"SW", "WN", "LJ", "SO", "BL", "LR", "SR", "RF", "FF"}


def _fmt(v):
    """Format an xls cell value to a clean string ('' if empty)."""
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


class BORCAdapter(PMSAdapter):
    name = "borc"
    label = "BORC (Bandar Abbas Oil Refinery)"

    def parse(self, path: str, company: str | None = None):
        try:
            import xlrd
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("xlrd is required to read .xls files: pip install xlrd") from e
        wb = xlrd.open_workbook(path)
        classes: dict[str, dict] = {}
        order: list[str] = []
        for sheet in wb.sheets():
            self._parse_sheet(sheet, classes, order)
        out = [classes[k] for k in order]
        for c in out:
            c.pop("_part", None)
            c["component_count"] = len(c["components"])
        return self.envelope(out, company or "BORC", os.path.basename(path))

    def _parse_sheet(self, s, classes, order):
        def cell(r, c):
            try:
                return _fmt(s.cell_value(r, c))
            except IndexError:
                return ""

        cur = None            # current class dict
        last_group = None     # last multi-word part header (for FLANGE subtypes)
        for r in range(s.nrows):
            row = [cell(r, c) for c in range(s.ncols)]
            # -- new class page? --
            if _label(row, 15, "LINE CLASS"):
                code = row[C_LINECLASS_VAL] or _first_after(row, 15)
                if code and code not in classes:
                    classes[code] = _blank_class(code)
                    order.append(code)
                if code:
                    cur = classes[code]
                    last_group = None
                continue
            if cur is None:
                continue
            # -- header fields --
            if _label(row, 1, "SERVICE") and not _label(row, 1, "SERVICE LIMIT"):
                cur["service"] = cur["service"] or _between(row, 2, 14)
                continue
            if _label(row, 1, "MAIN MATERIAL"):
                cur["main_material"] = cur["main_material"] or _between(row, 2, 13)
                if _label(row, 13, "CORROSION"):
                    cur["corrosion_allowance"] = cur["corrosion_allowance"] or _between(row, 14, 23)
                if _label(row, 23, "FLANGE RATING"):
                    cur["flange_rating_face"] = cur["flange_rating_face"] or _between(row, 24, 31)
                continue
            if _label(row, 1, "TEMP"):
                cur["temp_C"] = cur["temp_C"] or _series(row)
                continue
            if _label(row, 1, "PRESS"):
                cur["press_barg"] = cur["press_barg"] or _series(row)
                continue
            if _label(row, 0, "PART NAME") or _label(row, 0, "NOTE") or row[C_PART].upper() == "(MTO)":
                continue
            # -- component / part-header rows --
            part_txt = row[C_PART]
            size_from, size_to, desc = row[C_FROM], row[C_TO], row[C_DESC]
            rating = next((row[c] for c in C_RATING if c < len(row) and row[c]), "")
            has_data = bool(size_from or size_to or desc)
            if not has_data:
                if part_txt:                        # part / group header row
                    if (len(part_txt) <= 3 or part_txt.upper() in FLANGE_SUBTYPES) and last_group:
                        cur["_part"] = f"{last_group} {part_txt}"
                    else:
                        cur["_part"] = part_txt
                        if len(part_txt) > 4 or " " in part_txt:
                            last_group = part_txt
                continue
            # data row
            symbol = part_txt if part_txt.startswith("(") else (part_txt if part_txt and not desc else "")
            symbol = part_txt if part_txt else None
            full_desc = desc
            if rating:
                full_desc = f"{desc} [{rating}]".strip()
            note = row[C_NOTE] if row[C_NOTE].startswith("(") else ""
            cur["components"].append({
                "part": cur.get("_part"),
                "symbol": symbol,
                "size_from": size_from or None,
                "size_to": size_to or None,
                "size_raw": [x for x in [size_from, size_to] if x],
                "description": full_desc,
                "notes": [note] if note else [],
            })


def _blank_class(code):
    return {"class": code, "service": None, "main_material": None,
            "corrosion_allowance": None, "flange_rating_face": None,
            "temp_C": None, "press_barg": None, "particular_notes": None,
            "components": [], "_part": None}


def _label(row, col, text):
    return col < len(row) and row[col].upper().replace(" ", "").startswith(text.upper().replace(" ", ""))


def _first_after(row, col):
    for c in range(col + 1, len(row)):
        if row[c]:
            return row[c]
    return ""


def _between(row, start, end):
    """First non-empty cell value in [start, end) (handles merged-cell drift)."""
    for c in range(start, min(end, len(row))):
        if row[c]:
            return row[c]
    return ""


def _series(row):
    """Collect the numeric TEMP/PRESS series from the value columns."""
    vals = [row[c] for c in range(5, len(row)) if row[c]]
    return vals or None

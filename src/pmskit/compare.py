# -*- coding: utf-8 -*-
"""Compare two PMSs and produce a standard deviation list.

Baseline model: the REFERENCE PMS (basic design) is the baseline; the CONTRACTOR
PMS (detail design) is evaluated against it. Anything in the contractor that
differs from, adds to, or drops from the reference is a deviation.

Pairing:
  * classes are paired by class code (contractor reproduces the same project classes)
  * within a class, component rows are paired by part + overlapping NPS size range
  * comparison is done on NORMALIZED fields (see pmskit.normalize), not raw text,
    so wording differences do not create false deviations.

Severity (conservative, engineering-driven):
  * MAJOR : material/grade/manufacturing changed, schedule/rating REDUCED,
            component removed, class header material/rating/corrosion/P-T changed
  * MINOR : end connection, standards, added component, schedule/rating INCREASED
  * INFO  : cosmetic / equal-after-normalization
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from .normalize import normalize, COMPARE_FIELDS

# ---- NPS size handling -------------------------------------------------
_FRAC = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅛": 0.125}


def nps(size: Optional[str]) -> Optional[float]:
    """Parse an NPS token ('1/2', '1 ½', '1-1/2', '2', '24') to a float."""
    if size is None:
        return None
    s = str(size).strip()
    if not s:
        return None
    for k, v in _FRAC.items():
        s = s.replace(k, " " + str(v))
    s = s.replace("-", " ")
    total = 0.0
    for tok in s.split():
        if "/" in tok:
            try:
                a, b = tok.split("/")
                total += float(a) / float(b)
            except (ValueError, ZeroDivisionError):
                return None
        else:
            try:
                total += float(tok)
            except ValueError:
                return None
    return total or None


def _overlap(a_lo, a_hi, b_lo, b_hi):
    if None in (a_lo, b_lo):
        return False
    a_hi = a_hi if a_hi is not None else a_lo
    b_hi = b_hi if b_hi is not None else b_lo
    return max(a_lo, b_lo) <= min(a_hi, b_hi)


# ---- schedule / rating magnitude --------------------------------------
_SCH_RANK = {"5": 5, "5S": 5, "10": 10, "10S": 10, "20": 20, "30": 30, "STD": 40,
             "40": 40, "40S": 40, "60": 60, "80": 80, "80S": 80, "XS": 80,
             "100": 100, "120": 120, "140": 140, "160": 160, "XXS": 200}


def _sch_rank(v: Optional[str]) -> Optional[float]:
    if not v:
        return None
    v = v.upper().replace("SCH", "").replace(".", "").strip()
    if v in _SCH_RANK:
        return _SCH_RANK[v]
    m = re.match(r"CL\s*(\d+)", v)
    if m:
        return float(m.group(1))
    m = re.match(r"(\d+(?:\.\d+)?)\s*MM", v)
    if m:
        return float(m.group(1)) * 1000  # wall thickness in mm -> large scale
    return None


def _rating_direction(ref: Optional[str], con: Optional[str]) -> Optional[int]:
    """+1 if contractor >= reference (thicker/higher), -1 if reduced, 0 equal, None if not comparable."""
    r, c = _sch_rank(ref), _sch_rank(con)
    if r is None or c is None:
        return None
    return (c > r) - (c < r)


# ---- component pairing within a class ---------------------------------
def _pair_components(ref_comps, con_comps):
    """Yield (ref_row|None, con_row|None) pairs matched by part + size overlap."""
    used_con = set()
    for rc in ref_comps:
        rp = (rc.get("part") or "").upper()
        r_lo, r_hi = nps(rc.get("size_from")), nps(rc.get("size_to"))
        best = None
        for i, cc in enumerate(con_comps):
            if i in used_con:
                continue
            if (cc.get("part") or "").upper() != rp:
                continue
            c_lo, c_hi = nps(cc.get("size_from")), nps(cc.get("size_to"))
            if _overlap(r_lo, r_hi, c_lo, c_hi) or (r_lo is None and c_lo is None):
                best = i
                break
        if best is not None:
            used_con.add(best)
            yield rc, con_comps[best]
        else:
            yield rc, None
    for i, cc in enumerate(con_comps):
        if i not in used_con:
            yield None, cc


def _size_label(row):
    if not row:
        return ""
    a, b = row.get("size_from"), row.get("size_to")
    return f"{a}–{b}" if b and b != a else (a or "")


# ---- deviation classification -----------------------------------------
def _canon_token(t):
    """Canonicalize a spec/standard token for comparison (ignore spacing, dots,
    and the trailing metric 'M' on ASME dimensional standards)."""
    if t is None:
        return None
    t = re.sub(r"[\s.]+", "", str(t).upper())
    t = re.sub(r"(B\d{2}\.?\d+)M$", r"\1", t)   # ASME B36.10M -> B36.10
    t = re.sub(r"(B\d+)M\b", r"\1", t)
    return t


def _cmp_val(v):
    if isinstance(v, list):
        return tuple(sorted(_canon_token(x) for x in v))
    return _canon_token(v)


def _compare_row(ref, con):
    """Return (deviation_type, severity, changed_fields, remark) for a matched/unmatched pair."""
    if ref and not con:
        return "Removed", "major", [], "Item present in reference, missing in contractor"
    if con and not ref:
        return "Added", "minor", [], "Item added by contractor (not in reference)"
    nr, nc = normalize(ref["description"]), normalize(con["description"])
    changed = []
    for f in COMPARE_FIELDS:
        if _cmp_val(nr.get(f)) != _cmp_val(nc.get(f)):
            changed.append(f)
    if not changed:
        return "Equal", "info", [], "Equivalent after normalization"
    severity = "minor"
    remarks = []
    if any(f in changed for f in ("material", "grade", "manuf")):
        severity = "major"
    for f in changed:
        a, b = nr.get(f), nc.get(f)
        if f == "rating_sch":
            d = _rating_direction(a, b)
            if d is not None and d < 0:
                severity = "major"
                remarks.append(f"Schedule/rating REDUCED {a}→{b}")
            elif d is not None and d > 0:
                remarks.append(f"Schedule/rating increased {a}→{b}")
            else:
                remarks.append(f"Schedule/rating changed {a}→{b} (review)")
        elif f == "standards":
            remarks.append(f"Standard {a}→{b}")
        else:
            remarks.append(f"{f} {a}→{b}")
    return "Changed", severity, changed, "; ".join(remarks)


def _std_ref(ref, con):
    src = ref or con
    n = normalize(src["description"]) if src else {}
    return ", ".join(n.get("standards") or [])


# ---- header (class-level) comparison ----------------------------------
_HEADER_FIELDS = [("main_material", "Main material", "major"),
                  ("flange_rating_face", "Flange rating & face", "major"),
                  ("corrosion_allowance", "Corrosion allowance", "major")]


def _header_deviations(cls, ref, con, seq):
    out = []
    for key, label, sev in _HEADER_FIELDS:
        a, b = (ref.get(key) or "").strip(), (con.get(key) or "").strip()
        if _canon(a) != _canon(b):
            seq[0] += 1
            out.append(_row(seq[0], cls, f"CLASS HEADER — {label}", "", a, b,
                            "Changed", sev, "", f"{label} changed"))
    # P-T table
    if (ref.get("temp_C"), ref.get("press_barg")) != (con.get("temp_C"), con.get("press_barg")):
        seq[0] += 1
        out.append(_row(seq[0], cls, "CLASS HEADER — P-T rating", "",
                        _pt(ref), _pt(con), "Changed", "major", "", "Pressure-temperature rating differs"))
    return out


def _canon(s):
    return re.sub(r"[\s.]+", "", (s or "").upper())


def _pt(c):
    t, p = c.get("temp_C") or [], c.get("press_barg") or []
    return "; ".join(f"{a}C:{b}" for a, b in zip(t, p))


def _row(item, cls, comp, size, ref_v, con_v, dev, sev, stdref, remark):
    return {"item": item, "class": cls, "component": comp, "size": size,
            "reference": ref_v, "contractor": con_v, "deviation": dev,
            "severity": sev, "std_ref": stdref, "remark": remark}


# ---- public API --------------------------------------------------------
def compare(reference: Dict[str, Any], contractor: Dict[str, Any],
            include_equal: bool = False) -> Dict[str, Any]:
    ref_by = {(_canon(c["class"])): c for c in reference.get("classes", [])}
    con_by = {(_canon(c["class"])): c for c in contractor.get("classes", [])}
    all_codes = list(dict.fromkeys(list(ref_by) + list(con_by)))
    rows: List[dict] = []
    seq = [0]
    unmatched_classes = []
    for code in all_codes:
        rc, cc = ref_by.get(code), con_by.get(code)
        cls_name = (rc or cc)["class"]
        if rc and not cc:
            unmatched_classes.append((cls_name, "missing in contractor"))
            seq[0] += 1
            rows.append(_row(seq[0], cls_name, "WHOLE CLASS", "", "present", "—",
                             "Removed", "major", "", "Entire class missing in contractor"))
            continue
        if cc and not rc:
            unmatched_classes.append((cls_name, "not in reference"))
            seq[0] += 1
            rows.append(_row(seq[0], cls_name, "WHOLE CLASS", "", "—", "present",
                             "Added", "minor", "", "Class added by contractor (not in reference)"))
            continue
        rows.extend(_header_deviations(cls_name, rc, cc, seq))
        for r, c in _pair_components(rc.get("components", []), cc.get("components", [])):
            dev, sev, changed, remark = _compare_row(r, c)
            if dev == "Equal" and not include_equal:
                continue
            seq[0] += 1
            rows.append(_row(seq[0], cls_name,
                             (r or c).get("part") or "",
                             _size_label(r) or _size_label(c),
                             (r or {}).get("description", "—") if r else "—",
                             (c or {}).get("description", "—") if c else "—",
                             dev, sev, _std_ref(r, c), remark))
    summary = {"total": len(rows),
               "major": sum(1 for x in rows if x["severity"] == "major"),
               "minor": sum(1 for x in rows if x["severity"] == "minor"),
               "info": sum(1 for x in rows if x["severity"] == "info"),
               "added": sum(1 for x in rows if x["deviation"] == "Added"),
               "removed": sum(1 for x in rows if x["deviation"] == "Removed"),
               "changed": sum(1 for x in rows if x["deviation"] == "Changed")}
    return {
        "meta": {
            "reference": reference.get("meta", {}).get("company", "Reference"),
            "contractor": contractor.get("meta", {}).get("company", "Contractor"),
            "baseline": "reference",
        },
        "summary": summary,
        "rows": rows,
    }

# -*- coding: utf-8 -*-
"""Schedule-adequacy compliance check for a parsed PMS (ASME B31.3).

For every PIPE row in each class, at the class's governing pressure-temperature
design point, compute the B31.3 required wall thickness and compare it to the
actual wall of the selected schedule. Flags rows where the selected schedule is
thinner than required.

Requires a material datapack (allowable-stress values) — see pmskit.database.
Without it, rows are reported as 'not evaluated' (never a false pass).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from .database import (load_schedules, load_materials, wall_thickness, outer_diameter,
                       find_material, allowable_stress)
from .normalize import normalize
from .thickness import governing_case

_NPS_ORDER = ["1/2", "3/4", "1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "4", "5", "6", "8",
              "10", "12", "14", "16", "18", "20", "24", "26", "30", "36", "42", "48"]


def _nps_val(s):
    from .compare import nps
    return nps(s)


def _sizes_in_range(size_from, size_to):
    a, b = _nps_val(size_from), _nps_val(size_to)
    if a is None:
        return []
    if b is None:
        b = a
    out = []
    for tok in _NPS_ORDER:
        v = _nps_val(tok)
        if v is not None and a - 1e-9 <= v <= b + 1e-9:
            out.append(tok)
    return out


def _schedule_of(row):
    m = re.search(r"SCH\.?\s*\d+S?|\bXXS\b|\bXS\b|\bSTD\b", (row.get("description") or "").upper())
    return m.group(0) if m else None


def check_pms(data: Dict[str, Any], *, datapack: Optional[str] = None,
              E: float = 1.0, W: float = 1.0, mill_tol: float = 0.125) -> Dict[str, Any]:
    schedules = load_schedules()
    materials = load_materials(datapack)
    rows: List[dict] = []
    seq = 0
    for c in data.get("classes", []):
        temps, press = c.get("temp_C") or [], c.get("press_barg") or []
        pts = [(float(t), float(p)) for t, p in zip(temps, press)
               if _is_num(t) and _is_num(p)]
        ca = _mm(c.get("corrosion_allowance"))
        for x in c.get("components", []):
            if (x.get("part") or "").upper() != "PIPE":
                continue
            n = normalize(x.get("description"))
            mat = find_material(materials, n.get("material"), n.get("grade"))
            sched = _schedule_of(x)
            for nps_tok in _sizes_in_range(x.get("size_from"), x.get("size_to")):
                seq += 1
                D = outer_diameter(schedules, nps_tok)
                actual = wall_thickness(schedules, nps_tok, sched) if sched else None
                base = {"item": seq, "class": c["class"], "size": nps_tok,
                        "schedule": sched, "material": n.get("material"),
                        "grade": n.get("grade"), "OD_mm": D, "actual_wall_mm": actual}
                if not pts or mat is None or D is None:
                    base.update({"status": "not-evaluated", "required_mm": None,
                                 "margin_mm": None, "governing": None,
                                 "remark": _why(pts, mat, D, actual)})
                    rows.append(base)
                    continue
                g = governing_case(pts, D, lambda T: allowable_stress(mat, T),
                                   E=E, W=W, family=mat.get("family", "ferritic"),
                                   c_mm=ca, mill_tol=mill_tol)
                if g is None:
                    base.update({"status": "not-evaluated", "required_mm": None,
                                 "margin_mm": None, "governing": None,
                                 "remark": "No usable allowable stress at design temperatures"})
                    rows.append(base)
                    continue
                req = g["t_min_with_allowances_mm"]
                if actual is None:
                    base.update({"status": "no-schedule", "required_mm": req,
                                 "margin_mm": None, "governing": g,
                                 "remark": "Schedule not recognised in dimension table"})
                else:
                    eff = actual * (1 - mill_tol)   # account for mill under-tolerance on the nominal wall
                    margin = round(eff - req, 3)
                    ok = margin >= 0
                    base.update({"status": "OK" if ok else "UNDER-THICKNESS",
                                 "required_mm": req, "margin_mm": margin, "governing": g,
                                 "remark": (f"Governing {g['temp_C']}C/{g['press_barg']}barg, "
                                            f"S={g['S_MPa']}MPa; req {req}mm vs eff {round(eff,3)}mm")})
                rows.append(base)
    summ = {
        "total": len(rows),
        "under": sum(1 for r in rows if r["status"] == "UNDER-THICKNESS"),
        "ok": sum(1 for r in rows if r["status"] == "OK"),
        "not_evaluated": sum(1 for r in rows if r["status"] in ("not-evaluated", "no-schedule")),
        "materials_source": materials.get("meta", {}).get("_source"),
        "synthetic_stress": bool(materials.get("meta", {}).get("SYNTHETIC")),
    }
    return {"meta": {"company": data.get("meta", {}).get("company"), "code": "ASME B31.3",
                     "E": E, "W": W, "mill_tol": mill_tol}, "summary": summ, "rows": rows}


def _is_num(v):
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def _mm(s):
    m = re.search(r"([0-9.]+)", s or "")
    return float(m.group(1)) if m else 0.0


def _why(pts, mat, D, actual):
    miss = []
    if not pts:
        miss.append("no P-T points")
    if mat is None:
        miss.append("material not in datapack")
    if D is None:
        miss.append("size not in dimension table")
    return "Not evaluated: " + ", ".join(miss) if miss else "Not evaluated"

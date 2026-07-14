# -*- coding: utf-8 -*-
"""ASME B31.3 straight-pipe pressure-design wall thickness (para. 304.1.2).

Implements the code *method* (equation and Y coefficient). It contains NO
copyrighted allowable-stress tables — the allowable stress S is supplied by the
caller (from a material datapack; see pmskit.database).

Pressure design thickness:
    t  = P*D / (2*(S*E*W + P*Y))
    t_m = t + c                      (c = sum of mechanical allowances, mm)
    T_order = t_m / (1 - mill_tol)   (nominal wall to order, incl. mill under-tolerance)

Units: P [MPa], D [mm], S [MPa] -> t [mm].  (1 bar = 0.1 MPa)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


def bar_to_mpa(bar: float) -> float:
    return bar * 0.1


# Y coefficient, ASME B31.3 Table 304.1.1 (ductile metals). Small step table.
def y_coefficient(family: str, temp_c: float) -> float:
    fam = (family or "ferritic").lower()
    if "austen" in fam or "stainless" in fam or fam in ("ss", "cr-ni"):
        if temp_c <= 566:
            return 0.4
        if temp_c <= 593:
            return 0.5
        return 0.7
    # ferritic / carbon / low-alloy (default)
    if temp_c <= 482:
        return 0.4
    if temp_c <= 510:
        return 0.5
    return 0.7


def required_thickness(P_bar: float, D_mm: float, S_MPa: float, *,
                       E: float = 1.0, W: float = 1.0, Y: float = 0.4,
                       c_mm: float = 0.0, mill_tol: float = 0.125) -> Dict[str, float]:
    """Return B31.3 pressure-design thickness results (mm)."""
    P = bar_to_mpa(P_bar)
    denom = 2.0 * (S_MPa * E * W + P * Y)
    t = P * D_mm / denom if denom > 0 else float("inf")
    t_m = t + c_mm
    T_order = t_m / (1.0 - mill_tol) if mill_tol < 1 else float("inf")
    return {
        "pressure_MPa": round(P, 4),
        "t_pressure_design_mm": round(t, 3),
        "t_min_with_allowances_mm": round(t_m, 3),
        "T_nominal_to_order_mm": round(T_order, 3),
    }


def governing_case(pt_points: List[tuple], D_mm: float, s_at_temp, *,
                   E: float = 1.0, W: float = 1.0, family: str = "ferritic",
                   c_mm: float = 0.0, mill_tol: float = 0.125) -> Optional[Dict[str, Any]]:
    """Across all (temp_C, press_bar) design points, return the case that needs
    the greatest thickness. ``s_at_temp(T)`` returns allowable stress (MPa) or None.
    """
    worst = None
    for temp_c, press_bar in pt_points:
        S = s_at_temp(temp_c)
        if S is None or S <= 0:
            continue
        Y = y_coefficient(family, temp_c)
        r = required_thickness(press_bar, D_mm, S, E=E, W=W, Y=Y, c_mm=c_mm, mill_tol=mill_tol)
        r.update({"temp_C": temp_c, "press_barg": press_bar, "S_MPa": round(S, 2), "Y": Y})
        if worst is None or r["t_min_with_allowances_mm"] > worst["t_min_with_allowances_mm"]:
            worst = r
    return worst

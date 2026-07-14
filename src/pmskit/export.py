# -*- coding: utf-8 -*-
"""Export a canonical PMS dict to JSON / CSV / XLSX (flat component rows)."""
from __future__ import annotations
import csv
import json
import re

_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(v):
    return _ILLEGAL.sub(" ", v) if isinstance(v, str) else v
from typing import Any, Dict, List

_FLAT_HEADER = ["class", "service", "main_material", "corrosion_allowance",
                "flange_rating_face", "part", "symbol", "size_from", "size_to",
                "description", "notes"]


def flat_rows(data: Dict[str, Any]) -> List[list]:
    rows = []
    for c in data["classes"]:
        for x in c.get("components", []):
            rows.append([c.get("class"), _clean(c.get("service")), _clean(c.get("main_material")),
                         c.get("corrosion_allowance"), c.get("flange_rating_face"),
                         x.get("part"), x.get("symbol"), x.get("size_from"),
                         x.get("size_to"), x.get("description"),
                         " ".join(x.get("notes") or [])])
    return rows


def to_json(data: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def to_csv(data: Dict[str, Any], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(_FLAT_HEADER)
        w.writerows(flat_rows(data))


def to_xlsx(data: Dict[str, Any], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("openpyxl required for xlsx export: pip install openpyxl") from e
    wb = Workbook()
    ws = wb.active
    ws.title = "Components"
    ws.append(_FLAT_HEADER)
    for r in flat_rows(data):
        ws.append([_clean(v) for v in r])
    ws2 = wb.create_sheet("Classes")
    ws2.append(["class", "service", "main_material", "corrosion_allowance",
                "flange_rating_face", "component_count"])
    for c in data["classes"]:
        ws2.append([_clean(c.get("class")), c.get("service"), c.get("main_material"),
                    c.get("corrosion_allowance"), c.get("flange_rating_face"),
                    c.get("component_count")])
    wb.save(path)

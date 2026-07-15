#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.5 pressure-temperature rating tables (user-supplied Excel
exports of the licensed standard) into a flange-master v1 datapack.

Input directory must contain:
  Table 1.1-1*.xlsx   (List of Material Specifications -> groups, designations, specs)
  Table 2-<g>.xlsx    (P-T ratings per material group, SI units)

Output goes to the git-ignored datapacks/ directory. The output contains
copyrighted ASME values - NEVER commit or publish it.

Extraction rules (no engineering assumptions added):
  * 'Min. to 38 [Note ...]' row -> temperature point 38 C, label kept verbatim.
    (The rating engine holds the rating constant below the first temperature,
    which is exactly the meaning of the 'Min. to 38' row.)
  * Values are copied as-is; nothing is interpolated, rounded or inferred.
  * All table NOTES are preserved verbatim per group.
  * Every group listed in Table 1.1-1 must yield a rating table, else the run fails.

Usage:
  python tools/b16_5_extract.py "path/to/ASME B16.5" -o datapacks/flanges.json
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
import openpyxl  # noqa: E402

GROUP_RE = re.compile(r"^[123]\.\d{1,2}$")
SPEC_START = re.compile(r"(?=\b[AB]\s?\d{2,4}\b)")
NOTE_REF = re.compile(r"\(\d+\)|\[Note[^\]]*\]", re.I)


def _rows(path):
    ws = openpyxl.load_workbook(path, data_only=True).active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _s(v):
    return "" if v is None else str(v).strip()


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ---- Table 1.1-1: groups, designations, applicable specs -------------------
def parse_material_list(paths):
    groups = {}
    for path in sorted(paths):
        for row in _rows(path):
            g = _s(row[0])
            if not GROUP_RE.fullmatch(g):
                continue
            desig = _s(row[1] if len(row) > 1 else "")
            specs_txt = " ".join(_s(c) for c in row[3:6])
            toks = []
            for t in SPEC_START.split(specs_txt):
                t = NOTE_REF.sub("", t).strip(" ,;")
                t = re.sub(r"\s+", " ", t)
                if re.match(r"^[AB]\s?\d{2,4}\b", t):
                    toks.append(t.replace("A ", "A").replace("B ", "B", 1)
                                if re.match(r"^[AB]\s\d", t) else t)
            entry = groups.setdefault(g, {"designation": desig, "specs": []})
            for t in toks:
                if t not in entry["specs"]:
                    entry["specs"].append(t)
    return groups


# ---- Table 2-<g>: rating curves --------------------------------------------
def parse_rating_table(path):
    rows = _rows(path)
    hdr_i = next(i for i, r in enumerate(rows)
                 if any(_s(c).startswith("Temp") for c in r))

    # locate the class-number row: on the Temp row or up to 3 rows below.
    # (the B16.5 class series is a public fact)
    KNOWN = {"150", "300", "400", "600", "900", "1500", "2500"}
    cls_row_i, collapsed = None, False
    for k in range(hdr_i, min(hdr_i + 4, len(rows))):
        found = 0
        for c in rows[k]:
            toks = [t for t in _s(c).split() if t in KNOWN]
            found += len(toks)
            if len(toks) >= 2:
                collapsed = True
        if found >= 2:
            cls_row_i = k
            break
    if cls_row_i is None:
        raise ValueError(f"{path}: no class columns found in header")

    title = next((_s(c) for r in rows[:hdr_i + 1] for c in r
                  if "Table 2-" in _s(c)), "")
    m = re.search(r"Table 2-([123]\.\d{1,2})", title + " " + os.path.basename(path))
    group = m.group(1)

    NOT_RATED = {"\u2026", "...", "-", "\u2014"}

    if collapsed:
        classes = [int(t) for c in rows[cls_row_i] for t in _s(c).split() if t in KNOWN]
    else:
        class_cols = {j: int(_s(c)) for j, c in enumerate(rows[cls_row_i])
                      if _s(c) in KNOWN}
        classes = list(class_cols.values())

    curves = {cls: [] for cls in classes}
    first_label = None
    i = cls_row_i + 1
    while i < len(rows):
        row = rows[i]
        lead_j, lead = next(((j, _s(c)) for j, c in enumerate(row) if _s(c)), (None, ""))
        # a physical row may pack several temperature rows (merged cells):
        temps = []
        mmin = re.match(r"^Min[^\]]*\]?", lead)
        rest = lead
        if mmin:
            temps.append(38.0)
            first_label = mmin.group(0)
            rest = lead[mmin.end():]
        rest_toks = rest.split()
        if any(_num(t) is None for t in rest_toks):
            if not mmin:
                break  # end of data block (e.g. NOTES)
            raise ValueError(f"{path}: unexpected text after Min row: '{rest}'")
        temps.extend(_num(t) for t in rest_toks)
        if not temps:
            break
        temp = temps[0]
        if collapsed:
            toks = [t for j, c in enumerate(row) if j != lead_j for t in _s(c).split()]
            if len(toks) != len(temps) * len(classes):
                raise ValueError(f"{path}: row '{lead}' has {len(toks)} values "
                                 f"for {len(temps)}x{len(classes)}: {toks}")
            pairs = [(cls, tok, temps[k]) for k in range(len(temps))
                     for cls, tok in zip(classes, toks[k*len(classes):(k+1)*len(classes)])]
            pairs = [(c, t) for c, t, tm in pairs] if False else pairs
        else:
            pairs = ((cls, _s(row[j]) if j < len(row) else "")
                     for j, cls in class_cols.items())
        got = 0
        for item in pairs:
            cls, t = item[0], item[1]
            tm = item[2] if len(item) > 2 else temp
            if t == "" or t in NOT_RATED:
                continue  # not rated at this temperature
            p = _num(t)
            if p is None:
                raise ValueError(f"{path}: row '{lead}': bad value '{t}'")
            curves[cls].append([tm, p])
            got += 1
        if got == 0:
            raise ValueError(f"{path}: row '{lead}': no pressures parsed")
        i += 1

    notes = []
    for row in rows[i:]:
        for c in row:
            t = _s(c)
            if t and not t.isdigit():
                notes.append(t)
    return group, curves, notes, first_label


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", help="directory with the B16.5 Excel tables")
    ap.add_argument("-o", "--out", default=os.path.join("datapacks", "flanges.json"))
    ap.add_argument("--edition", default="2025")
    args = ap.parse_args()

    mat_files = glob.glob(os.path.join(args.src, "Table 1.1-1*.xlsx"))
    rating_files = glob.glob(os.path.join(args.src, "Table 2-*.xlsx"))
    if not mat_files or not rating_files:
        sys.exit("missing Table 1.1-1*.xlsx or Table 2-*.xlsx in source directory")

    listed = parse_material_list(mat_files)
    packs = {}
    for f in sorted(rating_files):
        group, curves, notes, first_label = parse_rating_table(f)
        info = listed.get(group, {})
        ratings = {str(c): pts for c, pts in sorted(curves.items()) if pts}
        packs[group] = {
            "group": group,
            "description": info.get("designation", ""),
            "specs": info.get("specs", []),
            "max_temp_C": max(p[0] for pts in ratings.values() for p in pts),
            "rating_table": f"2-{group}",
            "first_row_label": first_label,
            "ratings": ratings,
            "notes": " | ".join(notes),
        }

    missing = sorted(set(listed) - set(packs))
    extra = sorted(set(packs) - set(listed))
    if missing:
        sys.exit(f"FATAL: groups listed in Table 1.1-1 without rating table: {missing}")
    if extra:
        sys.exit(f"FATAL: rating tables not listed in Table 1.1-1: {extra}")

    def gkey(g):
        a, b = g.split(".")
        return (int(a), int(b))

    out = {
        "meta": {
            "schema": "flange-master v1",
            "standard": "ASME B16.5",
            "edition": args.edition,
            "SYNTHETIC": False,
            "note": ("Extracted from the user's licensed ASME B16.5-"
                     f"{args.edition} tables. Copyrighted data - private use "
                     "only, never commit or publish."),
            "pressure_units": "bar",
            "temp_units": "C",
            "dim_units": "mm",
            "source_files": sorted(os.path.basename(f) for f in rating_files + mat_files),
        },
        "material_groups": [packs[g] for g in sorted(packs, key=gkey)],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n_pts = sum(len(p) for g in out["material_groups"] for p in g["ratings"].values())
    print(f"wrote {args.out}: {len(out['material_groups'])} groups, "
          f"{n_pts} rating points, edition {args.edition}")


if __name__ == "__main__":
    main()

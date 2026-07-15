#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.47 tables (user-supplied Excel exports of the licensed
standard) into datapacks/flanges_b16_47.json.

Reuses the verified B16.5 parsing cores (tools/b16_5_extract.py grid/collapsed
rating parser; tools/b16_5_dims_extract.py verbatim-label conventions), with
B16.47 specifics:
  * classes 75/150/300/400/600/900; blank rating cell = not rated
  * NPS ladder 26..60 (large-diameter flanges)
  * dimension tables have no numbered column row and merge drilling + RTJ
    columns into the flange-dimension table (per class per Series A/B)
  * '1 060' style thousands separators (space) in dimension values

Same rules as before: verbatim column labels and notes, character-level
cleanup only, loud failure on structural surprises. Output is copyrighted -
git-ignored, never publish.

Usage:
  python tools/b16_47_extract.py standards-staging/b16_47 [-o datapacks/flanges_b16_47.json]
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b16_5_extract as R          # rating-table core (grid/collapsed)  # noqa: E402
import b16_5_dims_extract as D     # verbatim helpers                    # noqa: E402

CLASSES_47 = ["75", "150", "300", "400", "600", "900"]
LADDER_47 = [str(n) for n in range(26, 62, 2)]  # 26..60
SERIES_TABLES = {32: ("A", 150), 33: ("A", 300), 34: ("A", 400), 35: ("A", 600),
                 36: ("A", 900), 37: ("B", 75), 38: ("B", 150), 39: ("B", 300),
                 40: ("B", 400), 41: ("B", 600), 42: ("B", 900)}


def _s(v):
    return D._s(v)


def _num47(v):
    """Numeric parse tolerating '1 060' thousands spacing."""
    n = D._num(v)
    if n is not None:
        return n
    return D._num(str(v).replace(" ", ""))


def _rows(path):
    return D._rows(path)


def files_for(src, n):
    fs = [f for f in glob.glob(os.path.join(src, f"Table {n}*.xlsx"))
          if re.fullmatch(rf"Table {n}(-[0-9a-f]+)?( \(Cont.d\)[ -]?\d?)?\.xlsx",
                          os.path.basename(f))]
    return sorted(fs, key=lambda f: D._page_key(f))


# ---- ratings (Tables 3..29) -------------------------------------------------
def parse_rating(path):
    """B16.47 rating tables: grid ('Temperature | 75 150 ...' one class per
    cell) or collapsed (classes packed per cell, '\u2026' = not rated).
    'min. to 38' row = point at 38 C."""
    rows = _rows(path)
    txt = " ".join(c for r in rows[:12] for c in r if c)
    m = re.search(r"Ratings for Group ([\d.]+?)\.?(?:\s|Materials|$)", txt)
    group = m.group(1).rstrip(".")
    hdr_i = next(i for i, r in enumerate(rows)
                 if any(_s(c).lower().startswith("temp") for c in r))
    # header: map each physical cell -> the classes it carries (1..n per cell)
    cell_classes, classes = {}, []
    for k in range(hdr_i, min(hdr_i + 3, len(rows))):
        cc = {}
        for j, c in enumerate(rows[k]):
            toks = [int(t) for t in _s(c).split() if t in CLASSES_47]
            if toks:
                cc[j] = toks
        flat = [x for t in cc.values() for x in t]
        if len(flat) >= 2:
            cell_classes, classes, hdr_i = cc, flat, k
            break
    if not classes:
        raise ValueError(f"{path}: no class columns")
    NOT_RATED = {"\u2026", "...", "-", "\u2014"}

    def expand(c):
        out = []
        for t in _s(c).split():
            if set(t) == {"\u2026"}:
                out.extend(["\u2026"] * len(t))
            else:
                out.append(t)
        return out

    curves = {cls: [] for cls in classes}
    first_label, notes, i = None, [], hdr_i + 1
    while i < len(rows):
        r = rows[i]
        lead_j, lead = next(((j, c) for j, c in enumerate(r) if c), (None, ""))
        temps = []
        mmin = re.match(r"^[Mm]in[^\]]*\]?", lead)
        rest = lead[mmin.end():] if mmin else lead
        if mmin:
            temps.append(38.0)
            first_label = mmin.group(0)
        rest_toks = rest.split()
        if any(D._num(t) is None for t in rest_toks):
            if not mmin:
                break  # end of data (NOTES etc.)
            raise ValueError(f"{path}: unexpected text after Min row: '{rest}'")
        temps.extend(D._num(t) for t in rest_toks)
        if not temps:
            break
        toks_by_cell = {j: expand(c) for j, c in enumerate(r)
                        if j != lead_j and _s(c)}
        flat = [t for j in sorted(toks_by_cell) for t in toks_by_cell[j]]
        pairs = []
        if len(flat) == len(temps) * len(classes):
            for k in range(len(temps)):
                pairs += [(cls, tok, temps[k]) for cls, tok in
                          zip(classes, flat[k*len(classes):(k+1)*len(classes)])]
        elif len(temps) == 1:
            # per-cell model: an entirely empty cell = its classes not rated
            stray = set(toks_by_cell) - set(cell_classes)
            if stray:
                raise ValueError(f"{path}: row '{lead}': values in unheadered "
                                 f"columns {sorted(stray)}")
            for j, cs in cell_classes.items():
                toks = toks_by_cell.get(j, [])
                if not toks:
                    continue
                if len(toks) != len(cs):
                    raise ValueError(f"{path}: row '{lead}': cell has {len(toks)} "
                                     f"values for classes {cs}: {toks}")
                pairs += [(cls, tok, temps[0]) for cls, tok in zip(cs, toks)]
        else:
            raise ValueError(f"{path}: row '{lead}': {len(flat)} values for "
                             f"{len(temps)}x{len(classes)} classes")
        got = 0
        for cls, v, tm in pairs:
            if v == "" or v in NOT_RATED:
                continue
            p = D._num(v)
            if p is None:
                raise ValueError(f"{path}: bad rating value '{v}' at {lead}")
            curves[cls].append([tm, p])
            got += 1
        if not got:
            raise ValueError(f"{path}: no pressures in row '{lead}'")
        i += 1
    for r in rows[i:]:
        notes.extend(c for c in r if c and not c.isdigit())
    return group, curves, " | ".join(notes), first_label


# ---- dimension tables (32..42): headers without a numbered column row ------
def parse_dims47(path):
    rows = _rows(path)
    ladder = set(LADDER_47)
    d_start = next((i for i, r in enumerate(rows)
                    if _s(next((c for c in r if c), "")) in ladder
                    and sum(1 for c in r if c) >= 4), None)
    if d_start is None:
        # maybe the page is entirely multi-size packed (damaged) or notes-only
        dmg = []
        for r in rows:
            lead = next((c for c in r if c), "")
            toks = lead.split()
            if toks and all(t in ladder for t in toks):
                vals = [c for j, c in enumerate(r) if c][1:]
                if len(toks) >= 2 or not vals:
                    dmg.append(lead)
        return None, [], _notes_text(rows), dmg
    # header block: contiguous rows above data with >= 2 non-empty cells
    h_start = d_start
    while h_start - 1 >= 0 and sum(1 for c in rows[h_start - 1] if c) >= 2:
        h_start -= 1
    ncols = [j for j, c in enumerate(rows[d_start]) if c]
    labels = []
    for j in ncols:
        parts = [rows[k][j] for k in range(h_start, d_start)
                 if j < len(rows[k]) and rows[k][j]]
        labels.append(" ".join(parts).strip())
    bolt_cols = {j for j, lab in zip(ncols, labels)
                 if "Bolt" in lab and "Circle" not in lab and "No." not in lab
                 and "Length" not in lab}
    data, notes, damaged, in_notes = [], [], [], False
    for r in rows[d_start:]:
        lead = next((c for c in r if c), "")
        if not lead:
            continue
        if in_notes or lead.startswith(("NOTES", "GENERAL NOTE")):
            in_notes = True
            notes.extend(c for c in r if c and not c.isdigit())
            continue
        if lead not in ladder:
            toks = lead.split()
            if len(toks) >= 2 and all(t in ladder for t in toks):
                # multi-size packed row: values are untokenizable in this export
                # (spaced thousands collide with packing) -> record as damaged
                damaged.append(lead)
                continue
            if re.fullmatch(r"\d{1,3}", lead) or lead.startswith("ASME"):
                continue
            break
        obj = {"nps": lead, "values": {}}
        for j, lab in zip(ncols, labels):
            if j == ncols[0]:
                continue
            v = r[j] if j < len(r) else ""
            if v == "":
                continue
            if re.fullmatch(r"\(\d+\)", v):
                obj["values"][lab] = v
            elif j in bolt_cols and _num47(v) is None:
                obj["values"][lab] = D.canon_bolt(v, os.path.basename(path))
            else:
                n = _num47(v)
                obj["values"][lab] = n if n is not None else v
        if obj["values"]:
            data.append(obj)
        else:
            damaged.append(lead)   # size row present but all values missing
    return labels, data, " | ".join(notes), damaged


def _notes_text(rows):
    return " | ".join(c for r in rows for c in r
                      if c and not c.isdigit()
                      and not c.startswith(("Table", "ASME", "Dimensions")))


def verbatim_section(paths, title):
    lines = []
    for p in paths:
        for r in _rows(p):
            cells = [c for c in r if c]
            if cells:
                lines.append("  ".join(cells))
    return {"title": title, "lines": lines}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default=os.path.join("datapacks", "flanges_b16_47.json"))
    ap.add_argument("--edition", default="2025")
    args = ap.parse_args()

    # material list (Table 1): specs live in columns 2..4 (Forgings/Castings/
    # Plates) — one column left of the B16.5 layout (no rating-table column).
    listed = {}
    for path in files_for(args.src, 1):
        for row in _rows(path):
            g = _s(row[0])
            if not re.fullmatch(r"[123]\.\d{1,2}", g):
                continue
            desig = _s(row[1] if len(row) > 1 else "")
            specs_txt = " ".join(_s(c) for c in row[2:5])
            toks = []
            for t in R.SPEC_START.split(specs_txt):
                t = R.NOTE_REF.sub("", t).strip(" ,;")
                t = re.sub(r"\s+", " ", t)
                if re.match(r"^[AB]\s?\d{2,4}\b", t):
                    toks.append(t)
            entry = listed.setdefault(g, {"designation": desig, "specs": []})
            for t in toks:
                if t not in entry["specs"]:
                    entry["specs"].append(t)

    groups = {}
    for n in range(3, 30):
        for f in files_for(args.src, n):
            group, curves, notes, first_label = parse_rating(f)
            info = listed.get(group, {})
            ratings = {str(c): pts for c, pts in sorted(curves.items()) if pts}
            groups[group] = {"group": group, "description": info.get("designation", ""),
                             "specs": info.get("specs", []),
                             "max_temp_C": max(p[0] for pts in ratings.values() for p in pts),
                             "rating_table": f"Table {n}", "first_row_label": first_label,
                             "ratings": ratings, "notes": notes}
    missing = sorted(set(listed) - set(groups))
    extra = sorted(set(groups) - set(listed))
    if missing or extra:
        sys.exit(f"FATAL: rating/material-list mismatch missing={missing} extra={extra}")

    dims, problems = {}, []
    for n, (series, cls) in SERIES_TABLES.items():
        rows_all, labels_ref, notes_all = [], None, []
        damaged_all = []
        for f in files_for(args.src, n):
            labels, data, notes, damaged = parse_dims47(f)
            if data:
                labels_ref = labels_ref or labels
                rows_all += data
            if notes:
                notes_all.append(notes)
            damaged_all += damaged
        if damaged_all:
            problems.append((f"{series}:{cls}", f"Table {n}", damaged_all,
                             len(rows_all)))
        if not rows_all and not damaged_all:
            sys.exit(f"FATAL: dims {series}:{cls}: no rows")
        nps = [r["nps"] for r in rows_all]
        if len(nps) != len(set(nps)):
            sys.exit(f"FATAL: dims {series}:{cls}: duplicate sizes {nps}")
        entry = {"source_table": f"Table {n}", "series": series,
                 "class": cls, "columns": (labels_ref or [""])[1:],
                 "rows": rows_all,
                 "notes": " | ".join(x for x in notes_all if x)}
        if damaged_all:
            entry["DAMAGED_SOURCE"] = ("Source export is corrupt for these packed "
                                       "size rows (values missing/untokenizable); "
                                       "re-export required: " + "; ".join(damaged_all))
        dims[f"{series}:{cls}"] = entry

    # RTJ facing dims (Table 30): two class blocks; key rows by groove number
    rtj_labels, rtj_rows, rtj_notes = None, [], []
    for f in files_for(args.src, 30):
        rows = _rows(f)
        hdr_i = next(i for i, r in enumerate(rows)
                     if any("Groove Number" in _s(c) for c in r))
        # class labels row is directly below the header banner
        cls_row = rows[hdr_i + 1]
        gcol = next(j for j, c in enumerate(rows[hdr_i]) if "Groove Number" in _s(c))
        labels = []
        for j in range(max(len(rows[hdr_i]), len(cls_row))):
            parts = [rows[k][j] for k in (hdr_i, hdr_i + 1)
                     if j < len(rows[k]) and rows[k][j]]
            labels.append(" ".join(parts).strip())
        rtj_labels = rtj_labels or labels
        for r in rows[hdr_i + 2:]:
            g = _s(r[gcol]) if gcol < len(r) else ""
            if not re.fullmatch(r"R\d+", g):
                continue
            obj = {"groove_no": g, "values": {}}
            for j, lab in enumerate(labels):
                if j == gcol or not lab:
                    continue
                v = r[j] if j < len(r) else ""
                if v == "":
                    continue
                n = _num47(v)
                key = lab if j >= gcol else f"NPS for Class {lab}"
                obj["values"][key] = n if n is not None else v
            rtj_rows.append(obj)
        rtj_notes.append(_notes_text(rows[hdr_i:]) if False else "")

    def gkey(g):
        a, b = g.split(".")
        return (int(a), int(b))

    mono = []
    for g in sorted(groups.values(), key=lambda x: gkey(x["group"])):
        for cls, cur in g["ratings"].items():
            ps = [p for _, p in cur]
            for a, b, (t2, _) in zip(ps, ps[1:], cur[1:]):
                if b > a:
                    mono.append({"group": g["group"], "class": cls, "at_temp_C": t2,
                                 "note": "rated pressure increases with temperature "
                                         "in the source export - verify against the "
                                         "printed standard"})
    out = {
        "meta": {"schema": "flange-master v1", "standard": "ASME B16.47",
                 "edition": args.edition, "SYNTHETIC": False,
                 "note": (f"Extracted from the user's licensed ASME B16.47-{args.edition} "
                          "tables. Copyrighted data - private use only, never commit or "
                          "publish. Ratings apply to both Series; dimensions are keyed "
                          "'<series>:<class>'. Class 75 exists in Series B only."),
                 "pressure_units": "bar", "temp_units": "C", "dim_units": "mm",
                 "classes": [int(c) for c in CLASSES_47],
                 "nps_range": [26, 60],
                 "verify_flags": mono},
        "material_groups": [groups[g] for g in sorted(groups, key=gkey)],
        "dims": dims,
        "ring_joints": {"source_table": "Table 30", "columns": (rtj_labels or [""])[1:],
                        "rows": rtj_rows, "keyed_by": "groove_no",
                        "notes": " | ".join(x for x in rtj_notes if x)},
        "facing_imperfections": verbatim_section(files_for(args.src, 31),
                                                 "Table 31 - Permissible Imperfections (verbatim)"),
        "bolting_specs": verbatim_section(files_for(args.src, 2),
                                          "Table 2 - Bolting Specifications (verbatim)"),
        "bolting_recommendations": verbatim_section(files_for(args.src, 43),
                                                    "Table 43 - Flange Bolting Dimensional Recommendations (verbatim)"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if problems:
        print("\n!!! DAMAGED SOURCE TABLES (re-export needed):", file=sys.stderr)
        for key, tno, dmg, ok_rows in problems:
            print(f"  {key} ({tno}): {ok_rows} clean rows; damaged packed rows: "
                  f"{dmg}", file=sys.stderr)
    npts = sum(len(p) for g in out["material_groups"] for p in g["ratings"].values())
    ndim = sum(len(v["rows"]) for v in dims.values())
    print(f"wrote {args.out}: {len(groups)} groups/{npts} rating points, "
          f"{len(dims)} series-class dim tables/{ndim} rows, "
          f"ring_joints {len(rtj_rows)} rows")


if __name__ == "__main__":
    main()

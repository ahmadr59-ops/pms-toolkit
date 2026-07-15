#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.5 dimension tables (user-supplied Excel exports of the
licensed standard) and merge them into the existing flanges datapack.

Handles (2025 edition numbering):
  Table 4            -> facings          (facing dimensions, all classes)
  Table 5            -> ring_joints      (RTJ groove dimensions, all classes)
  Tables 7,10,13,15,17,19,21 -> drilling (bolt circle/holes/count/size, bolt lengths)
  Tables 8,11,14,16,18,20,22 -> dims     (flange dimensions per class)

Extraction rules (no engineering assumptions):
  * Column labels are taken VERBATIM from the table headers (rows between the
    numbered column row and the first data row, concatenated top-down).
  * Values are copied as-is; fraction slash U+2215 is normalized to '/'
    (character-level only, no numeric conversion of fractions).
  * Every NOTES / GENERAL NOTES block is preserved verbatim per section.
  * A run fails loudly on structural surprises rather than guessing.

Output: sections are merged into datapacks/flanges.json (git-ignored;
copyrighted content - never commit or publish).

Usage:
  python tools/b16_5_dims_extract.py "<dir with Table N.xlsx>" [-p datapacks/flanges.json]
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

DRILLING = {7: 150, 10: 300, 13: 400, 15: 600, 17: 900, 19: 1500, 21: 2500}
DIMS = {8: 150, 11: 300, 14: 400, 16: 600, 18: 900, 20: 1500, 22: 2500}
NPS_RE = re.compile(r"^\d{1,2}(/\d{1,2})?$|^\d{1,2}\s?\d/\d$")  # 1/2, 3/4, 1, 11/4(=1 1/4), 24


def _s(v):
    if v is None:
        return ""
    return str(v).replace("∕", "/").replace("⁄", "/").strip()


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _rows(path):
    ws = openpyxl.load_workbook(path, data_only=True).active
    return [[_s(c) for c in r] for r in ws.iter_rows(values_only=True)]


def _canon_nps(tok):
    """Character-level cleanup of an NPS token (e.g. '11/4' printed for 1-1/4).
    The Excel exports collapse '1 1/4' to '11/4'; B16.5 sizes are a closed,
    public list, so the mapping below is lossless."""
    t = tok.replace(" ", "")
    known = {"11/4": "1-1/4", "11/2": "1-1/2", "21/2": "2-1/2", "31/2": "3-1/2"}
    return known.get(t, t)


def _is_nps(tok):
    t = tok.replace(" ", "")
    return bool(re.fullmatch(r"\d{1,2}/\d{1,2}|\d{1,2}|\d\d/\d", t)) and t not in ("0",)


NPS_LADDER = ["1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4","5",
              "6","8","10","12","14","16","18","20","22","24"]
BOLT_LADDER = ["1/2","5/8","3/4","7/8","1","1-1/8","1-1/4","1-3/8","1-1/2",
               "1-5/8","1-3/4","1-7/8","2","2-1/8","2-1/4","2-3/8","2-1/2",
               "2-5/8","2-3/4","2-7/8","3","3-1/8","3-1/4","3-3/8","3-1/2",
               "3-5/8","3-3/4","3-7/8","4","4-1/8"]


def _digits(s):
    return re.sub(r"[^0-9]", "", s)


def align_sizes(tokens, path_label):
    """Map raw size tokens (possibly with lost fraction slashes) onto a strictly
    ascending subsequence of the closed B16.5 NPS ladder. Digit-preserving
    matches cost 0; a repair (token unexplainable by its own digits) costs 1 and
    is accepted only when the minimal-cost assignment is unique. Fails loudly
    otherwise — no silent guessing."""
    n, L = len(tokens), len(NPS_LADDER)
    dig = [_digits(t) for t in tokens]
    ldig = [_digits(v) for v in NPS_LADDER]
    INF = 10**9
    # dp[i][j] = (cost, count_of_min_paths) matching tokens[i:] with ladder index >= j
    dp = [[(INF, 0)] * (L + 1) for _ in range(n + 1)]
    for j in range(L + 1):
        dp[n][j] = (0, 1)
    for i in range(n - 1, -1, -1):
        for j in range(L - 1, -1, -1):
            best, cnt = dp[i][j + 1]           # skip ladder j
            c = 0 if dig[i] == ldig[j] else 1  # use ladder j for token i
            sub, subcnt = dp[i + 1][j + 1]
            if sub < INF:
                cand = c + sub
                if cand < best:
                    best, cnt = cand, subcnt
                elif cand == best:
                    cnt += subcnt
            dp[i][j] = (best, cnt)
    cost, cnt = dp[0][0]
    if cost >= INF:
        raise ValueError(f"{path_label}: size tokens {tokens} cannot align to NPS ladder")
    if cnt != 1:
        raise ValueError(f"{path_label}: ambiguous size alignment for {tokens}")
    # reconstruct
    out, i, j = [], 0, 0
    while i < n:
        c = 0 if dig[i] == ldig[j] else 1
        sub = dp[i + 1][j + 1][0]
        if sub < INF and c + sub == dp[i][j][0] and dp[i + 1][j + 1][1] == dp[i][j][1]:
            out.append((tokens[i], NPS_LADDER[j], c == 1))
            i += 1
            j += 1
        else:
            j += 1
    return out


def canon_bolt(tok, path_label):
    t = tok.replace(" ", "")
    d = _digits(t)
    cands = [v for v in BOLT_LADDER if _digits(v) == d]
    if len(cands) != 1:
        raise ValueError(f"{path_label}: bolt size token '{tok}' not resolvable")
    return cands[0]


def _find_numbers_row(rows):
    for i, r in enumerate(rows):
        cells = [c for c in r if c]
        if len(cells) >= 4 and all(re.fullmatch(r"\d{1,2}", c) for c in cells) \
           and cells[:2] == ["1", "2"]:
            return i
    raise ValueError("no numbered column-header row found")


_LADDER_DIGITS = None
def _looks_size(tok):
    """Size-like iff its digits-only form matches a ladder entry's digits.
    Excludes page numbers like '198' while accepting collapsed '114' (1-1/4)."""
    global _LADDER_DIGITS
    if _LADDER_DIGITS is None:
        _LADDER_DIGITS = {re.sub(r"[^0-9]", "", v) for v in NPS_LADDER}
    d = re.sub(r"[^0-9]", "", tok)
    return d in _LADDER_DIGITS


def parse_table(path):
    """-> (labels, raw_rows, notes). raw_rows = list of (lead_tokens, cells)
    where cells are the physical value columns (verbatim strings)."""
    rows = _rows(path)
    n_i = _find_numbers_row(rows)
    ncols = [j for j, c in enumerate(rows[n_i]) if c]
    h_end = n_i + 1
    while h_end < len(rows):
        lead = next((c for c in rows[h_end] if c), "")
        toks = lead.split()
        if toks and all(_looks_size(t) for t in toks):
            break
        h_end += 1
    labels = []
    for j in ncols:
        parts = [rows[k][j] for k in range(n_i + 1, h_end) if j < len(rows[k]) and rows[k][j]]
        labels.append(" ".join(parts).strip())
    data, notes, in_notes = [], [], False
    for r in rows[h_end:]:
        lead = next((c for c in r if c), "")
        if not lead:
            continue
        if in_notes or lead.startswith(("NOTES", "GENERAL NOTE")):
            in_notes = True
            notes.extend(c for c in r if c and not c.isdigit())
            continue
        toks = lead.split()
        if not toks or not all(_looks_size(t) for t in toks):
            # footer artifacts like 'ASME B16.5-2025' / page numbers end the data block
            if re.fullmatch(r"\d{2,3}", lead) or lead.startswith("ASME"):
                continue
            break
        cells = [r[j] if j < len(r) else "" for j in ncols[1:]]
        data.append((toks, cells))
    return labels, data, " | ".join(notes)


def rows_to_objects(labels, data, path_label, bolt_cols=()):
    """Expand (possibly row-packed) data into one object per size, verbatim
    values; numeric where parseable. Strict token-count checks."""
    flat_tokens = [t for toks, _ in data for t in toks]
    aligned = align_sizes(flat_tokens, path_label)
    repairs = [{"raw": a, "as": b} for a, b, rep in aligned if rep]
    it = iter(aligned)
    out = []
    for toks, cells in data:
        sizes = [next(it)[1] for _ in toks]
        split_cells = []
        for c in cells:
            parts = c.split() if c else []
            if len(toks) == 1:
                split_cells.append([c] if c else [""])
            else:
                if parts and len(parts) != len(toks):
                    raise ValueError(f"{path_label}: cell '{c}' has {len(parts)} values "
                                     f"for sizes {sizes}")
                split_cells.append(parts if parts else [""] * len(toks))
        for k, size in enumerate(sizes):
            obj = {"nps": size, "values": {}}
            for lab, parts in zip(labels[1:], split_cells):
                v = parts[k] if k < len(parts) else ""
                if v == "":
                    continue
                if re.fullmatch(r"\(\d+\)", v):
                    obj["values"][lab] = v          # note reference, verbatim
                elif lab in bolt_cols:
                    obj["values"][lab] = canon_bolt(v, path_label)
                else:
                    n = _num(v)
                    obj["values"][lab] = n if n is not None else v
            out.append(obj)
    return out, repairs


def _bolt_cols(labels):
    return tuple(l for l in labels
                 if "Diameter of Bolt" in l and "Length" not in l and "Circle" not in l)


def _page_key(fname):
    b = os.path.basename(fname)
    m = re.search(r"Cont.d\)(?:[ -]?(\d))?", b)
    return 0 if not m else int(m.group(1) or 1)


def files_for(src, n):
    fs = [f for f in glob.glob(os.path.join(src, f"Table {n}*.xlsx"))
          if re.fullmatch(rf"Table {n}( \(Cont.d\)[ -]?\d?)?\.xlsx", os.path.basename(f))]
    return sorted(fs, key=_page_key)


def _notes_only(path):
    out = []
    for r in _rows(path):
        for c in r:
            if c and not c.isdigit() and not c.startswith(("Table", "ASME", "Dimensions")):
                out.append(c)
    return " | ".join(out)


def build_section(src, table_map, kind):
    section, all_repairs = {}, {}
    for table_no, cls in table_map.items():
        rows_all, labels_ref, notes_all, repairs = [], None, [], []
        for f in files_for(src, table_no):
            try:
                labels, data, notes = parse_table(f)
            except ValueError as e:
                if "no numbered" in str(e):
                    notes_all.append(_notes_only(f))
                    continue
                raise
            if data:
                if labels_ref is None:
                    labels_ref = labels
                objs, reps = rows_to_objects(labels, data, os.path.basename(f),
                                             bolt_cols=_bolt_cols(labels))
                rows_all += objs
                repairs += reps
            if notes:
                notes_all.append(notes)
        if not rows_all:
            sys.exit(f"FATAL: {kind} CL{cls}: no rows extracted")
        nps = [r["nps"] for r in rows_all]
        if len(nps) != len(set(nps)):
            sys.exit(f"FATAL: {kind} CL{cls}: duplicate sizes {nps}")
        section[str(cls)] = {"source_table": f"Table {table_no}",
                             "columns": labels_ref[1:], "rows": rows_all,
                             "notes": " | ".join(n for n in notes_all if n)}
        if repairs:
            section[str(cls)]["token_repairs"] = repairs
    return section


def parse_rtj(paths):
    rows_all, labels_ref, notes_all = [], None, []
    for path in paths:
        rows = _rows(path)
        try:
            n_i = _find_numbers_row(rows)
        except ValueError:
            notes_all.append(_notes_only(path))
            continue
        ncols = [j for j, c in enumerate(rows[n_i]) if c]
        # locate groove-number column via header text in the next few rows
        gcol = None
        for k in range(n_i + 1, min(n_i + 5, len(rows))):
            for j in ncols:
                if j < len(rows[k]) and "Number" in rows[k][j]:
                    gcol = j
        if gcol is None:
            sys.exit(f"FATAL: {os.path.basename(path)}: groove-number column not found")
        # header rows end at first row with numeric groove value
        h_end = n_i + 1
        while h_end < len(rows):
            v = rows[h_end][gcol] if gcol < len(rows[h_end]) else ""
            if _num(v) is not None:
                break
            h_end += 1
        labels = []
        for j in ncols:
            parts = [rows[k][j] for k in range(n_i + 1, h_end) if j < len(rows[k]) and rows[k][j]]
            labels.append(" ".join(parts).strip())
        if labels_ref is None:
            labels_ref = labels
        in_notes = False
        for r in rows[h_end:]:
            lead = next((c for c in r if c), "")
            if in_notes or lead.startswith(("NOTES", "GENERAL NOTE")):
                in_notes = True
                notes_all.append(" ".join(c for c in r if c and not c.isdigit()))
                continue
            g = r[gcol] if gcol < len(r) else ""
            if _num(g) is None:
                continue
            obj = {"groove_no": g, "values": {}}
            for lab, j in zip(labels, ncols):
                if j == gcol:
                    continue
                v = r[j] if j < len(r) else ""
                if v == "":
                    continue
                n = _num(v)
                obj["values"][lab or f"col{j+1}"] = n if n is not None else v
            rows_all.append(obj)
    return {"source_table": "Table 5", "columns": labels_ref, "rows": rows_all,
            "notes": " | ".join(n for n in notes_all if n),
            "data_quality": ("Class/NPS applicability columns contain mangled "
                             "fraction glyphs from the source export (e.g. '%'/'V2'); "
                             "kept verbatim — verify against the printed standard "
                             "before relying on them.")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("-p", "--pack", default=os.path.join("datapacks", "flanges.json"))
    args = ap.parse_args()

    drilling = build_section(args.src, DRILLING, "drilling")
    dims = build_section(args.src, DIMS, "dims")

    # facings (Table 4)
    fac_rows, fac_labels, fac_notes = [], None, []
    for f in files_for(args.src, 4):
        try:
            labels, data, notes = parse_table(f)
        except ValueError as e:
            if "no numbered" in str(e):
                fac_notes.append(_notes_only(f))
                continue
            raise
        if data:
            fac_labels = fac_labels or labels
            objs, _ = rows_to_objects(labels, data, os.path.basename(f))
            fac_rows += objs
        if notes:
            fac_notes.append(notes)

    rtj = parse_rtj(files_for(args.src, 5))

    # cross-check: same size set in drilling vs dims per class
    for cls in drilling:
        a = {r["nps"] for r in drilling[cls]["rows"]}
        b = {r["nps"] for r in dims[cls]["rows"]}
        if a != b:
            print(f"NOTE: CL{cls} size sets differ drilling-only={sorted(a-b)} "
                  f"dims-only={sorted(b-a)}", file=sys.stderr)

    pack = json.load(open(args.pack, encoding="utf-8"))
    pack["drilling"] = drilling
    pack["dims"] = dims
    pack["facings"] = {"source_table": "Table 4", "columns": (fac_labels or [""])[1:],
                       "rows": fac_rows, "notes": " | ".join(n for n in fac_notes if n)}
    pack["ring_joints"] = rtj
    pack["meta"]["dims_note"] = ("Dimension sections extracted verbatim from ASME "
                                 "B16.5-2025 Tables 4,5,7-22 (SI). Column labels are the "
                                 "standard's own header texts; token_repairs lists every "
                                 "size token reconstructed via the closed NPS ladder.")
    json.dump(pack, open(args.pack, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dr = sum(len(v["rows"]) for v in drilling.values())
    dm = sum(len(v["rows"]) for v in dims.values())
    reps = sum(len(v.get("token_repairs", [])) for v in list(drilling.values()) + list(dims.values()))
    print(f"merged into {args.pack}: drilling {len(drilling)}cls/{dr} rows, "
          f"dims {len(dims)}cls/{dm} rows, facings {len(fac_rows)} rows, "
          f"ring_joints {len(rtj['rows'])} rows, token repairs {reps}")


if __name__ == "__main__":
    main()

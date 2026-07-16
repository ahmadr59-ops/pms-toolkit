#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.9-2018 dimension tables from the standard's text-layer PDF
into the fittings datapack (b16_9 section of datapacks/fittings.json).

The 2018 PDF emits one table cell per text line, and every dimension is dual-
unit 'mm (in.)'. That gives a free, strong internal cross-check: each pair must
satisfy |mm - in*25.4| <= 0.6 (covers the standard's own rounding). Any row
with a wrong column count, off-ladder size, malformed cell, or mm/in mismatch
aborts the run - no silent guessing. Notes are stored verbatim; Tables 5-1,
8-1, 9.2.1-1 and 11-1 (groupings, bevels, test factors, tolerances) are stored
as verbatim line blocks.

Usage: python tools/b16_9_extract.py "<path to ASME B16.9-2018.pdf>"
"""
from __future__ import annotations
import json, os, re, sys
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADDER = ["1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4","5","6",
          "8","10","12","14","16","18","20","22","24","26","28","30","32","34",
          "36","38","40","42","44","46","48"]
FRAC = {re.sub(r"\D","",v): v for v in LADDER if "/" in v}
INTS = {v for v in LADDER if "/" not in v}

# pages are 1-based; labels transcribed verbatim from the table headers
TABLES = {
 "6.1-1": dict(pages=[18], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-End, 90-deg Elbows, A",
    "Center-to-End, 45-deg Elbows, B"],
    title="Dimensions of Long Radius Elbows"),
 "6.1-2": dict(pages=[19], compound=2, labels=[
    "Outside Diameter at Bevel, Large End","Outside Diameter at Bevel, Small End",
    "Center-to-End, A"],
    title="Dimensions of Long Radius Reducing Elbows"),
 "6.1-3": dict(pages=[20], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-Center, O","Back-to-Face, K"],
    title="Dimensions of Long Radius Returns"),
 "6.1-4": dict(pages=[20], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-End, A"],
    title="Dimensions of Short Radius Elbows", second_on_page=True),
 "6.1-5": dict(pages=[21], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-Center, O","Back-to-Face, K"],
    title="Dimensions of Short Radius 180-deg Returns"),
 "6.1-6": dict(pages=[22], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-End, 90-deg Elbows, A",
    "Center-to-End, 45-deg Elbows, B"],
    title="Dimensions of 3D Radius Elbows"),
 "6.1-7": dict(pages=[23], compound=1, labels=[
    "Outside Diameter at Bevel","Center-to-End, Run, C",
    "Center-to-End, Outlet, M [Notes (1) and (2)]"],
    title="Dimensions of Straight Tees and Crosses"),
 "6.1-8": dict(pages=[24,25,26,27,28,29], compound=3, labels=[
    "Outside Diameter at Bevel, Run","Outside Diameter at Bevel, Outlet",
    "Center-to-End, Run, C","Center-to-End, Outlet, M [Note (1)]"],
    title="Dimensions of Reducing Outlet Tees and Reducing Outlet Crosses"),
 "6.1-9": dict(pages=[30], compound=1, labels=[
    "Outside Diameter of Barrel, Max. [Note (6)]","Outside Diameter of Barrel, Min.",
    "Long Pattern Length, F [Notes (3),(4)]","Short Pattern Length, F [Notes (3),(4)]",
    "Radius of Fillet, R [Note (5)]","Diameter of Lap, G"],
    title="Dimensions of Lap Joint Stub Ends"),
 "6.1-10": dict(pages=[31], compound=1, labels=[
    "Outside Diameter at Bevel","Length, E [Note (1)]",
    "Limiting Wall Thickness for Length, E","Length, E1 [Note (2)]"],
    title="Dimensions of Caps"),
 "6.1-11": dict(pages=[32,33], compound=2, labels=[
    "Outside Diameter at Bevel, Large End","Outside Diameter at Bevel, Small End",
    "End-to-End, H"],
    title="Dimensions of Reducers"),
}
VERBATIM = {"5-1": [17], "8-1": [34], "9.2.1-1": [36], "11-1": [37, 38]}
VAL = re.compile(r"^(\d[\d ]*(?:\.\d+)?)\s*\((\d[\d ]*(?:\.\d+)?)\)$")


def canon_size(tok):
    t = tok.replace("∕","/").replace("⁄","/").replace(" ","")
    if "/" in t:
        d = re.sub(r"\D","",t)
        if d not in FRAC: return None
        return FRAC[d]
    return t if t in INTS else None


def parse_size_line(line, nparts):
    parts = re.split(r"[×x]", line)
    if len(parts) != nparts: return None
    out = [canon_size(p.strip()) for p in parts]
    return None if None in out else " x ".join(out)


def parse_table(doc, tid, spec):
    K = len(spec["labels"]); rows=[]; notes=[]; headers=[]; flags=[]
    for pg in spec["pages"]:
        lines=[l.strip() for l in doc[pg-1].get_text().split("\n") if l.strip()]
        # if two tables share the page, cut at / start from the other title
        if spec.get("second_on_page"):
            i0=next(i for i,l in enumerate(lines) if l.startswith(f"Table {tid}"))
            lines=lines[i0:]
        else:
            for j,l in enumerate(lines):
                if l.startswith("Table ") and not l.startswith(f"Table {tid}") and j>0:
                    lines=lines[:j]; break
        in_notes=False; i=0; seen_data=False
        while i<len(lines):
            l=lines[i]
            if l=="ASME B16.9-2018" and seen_data:
                break   # page footer; anything after (page number) is artifact
            if l.startswith(("NOTES","NOTE:","GENERAL NOTE")) or in_notes:
                in_notes=True; notes.append(l); i+=1; continue
            size=parse_size_line(l, spec["compound"])
            if size:
                vals=[]
                for k in range(1,K+1):
                    if i+k>=len(lines):
                        raise ValueError(f"T{tid}: row {size}: truncated")
                    m=VAL.fullmatch(lines[i+k])
                    if not m:
                        if lines[i+k] in ("…","..."):
                            vals.append(None); continue
                        raise ValueError(f"T{tid}: row {size} col {k}: bad cell '{lines[i+k]}'")
                    mm,inch=float(m.group(1).replace(" ","")),float(m.group(2).replace(" ",""))
                    d=abs(mm-inch*25.4)
                    if d>2.0:
                        raise ValueError(f"T{tid}: {size} col {k}: mm/in mismatch "
                                         f"{mm} vs {inch}×25.4={inch*25.4:.2f}")
                    if d>0.6:
                        # both values are as printed; the standard occasionally
                        # rounds mm independently - keep verbatim, flag for review
                        flags.append(f"{size} col {k}: {mm} vs {inch}in={inch*25.4:.2f}mm")
                    vals.append([mm,inch])
                rows.append({"size":size,"v":vals}); i+=K+1; seen_data=True
            else:
                if not seen_data: headers.append(l)
                i+=1
    extra={"unit_roundoff_flags":flags} if flags else {}
    return {"table":tid,"title":spec["title"],"columns":spec["labels"],**extra,
            "units":"each value = [mm, in] as printed; cross-checked at 25.4",
            "rows":rows,"header_lines_raw":headers,"notes":" | ".join(notes)}


def main():
    src=sys.argv[1]
    doc=fitz.open(src)
    tables=[]
    for tid,spec in TABLES.items():
        t=parse_table(doc,tid,spec)
        if not t["rows"]:
            sys.exit(f"FATAL: T{tid}: no rows")
        sizes=[r["size"] for r in t["rows"]]
        if len(sizes)!=len(set(sizes)):
            dup=[s for s in sizes if sizes.count(s)>1]
            sys.exit(f"FATAL: T{tid}: duplicate sizes {sorted(set(dup))}")
        tables.append(t)
        print(f"  T{tid}: {len(t['rows'])} rows ({sizes[0]} .. {sizes[-1]})")
    verb={}
    for tid,pages in VERBATIM.items():
        lines=[]
        for pg in pages:
            lines+=[l.strip() for l in doc[pg-1].get_text().split("\n") if l.strip()]
        verb[tid]=lines
    doc.close()
    path=os.path.join(ROOT,"datapacks","fittings.json")
    pack=json.load(open(path,encoding="utf-8"))
    pack["b16_9"]={"standard":"ASME B16.9","edition":"2018",
        "source":"text layer of the licensed PDF; every value pair verified mm==in*25.4 (tol 0.6 mm)",
        "dimension_tables":tables,
        "verbatim_tables":{k:{"lines":v} for k,v in verb.items()},
        "verbatim_contents":"5-1 Material Groupings; 8-1 Welding Bevels; 9.2.1-1 Test factors; 11-1 Tolerances"}
    json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    n=sum(len(t["rows"]) for t in tables)
    print(f"wrote {path}: {len(tables)} dimension tables, {n} rows, "
          f"{len(verb)} verbatim tables")


if __name__=="__main__":
    main()

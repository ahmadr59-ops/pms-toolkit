#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.20-2023 and B16.21-2021 gasket tables from their text-layer
PDFs into datapacks/gaskets.json.

Structured parsing (line-stream: one cell per line) with strict checks:
  * keys: NPS (closed ladder 1/4..60) or ring numbers R-/RX-/BX-###
  * cells: 'mm (in.)' dual (cross-checked at 25.4, tol 0.6) or plain numbers
  * constant column count per table; '...' kept as printed
Any table that violates structure is stored VERBATIM with a parse_note instead
of aborting the whole run - lossless, never silent. Spanned-layout tables
(e.g. SW-2.5-x minimum pipe wall) are verbatim by design.

Usage: python tools/b16_20_21_extract.py "<B16.20 pdf>" "<B16.21 pdf>"
"""
from __future__ import annotations
import json, os, re, sys
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPS = ["1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4",
       "5","6","8","10","12","14","16","18","20","22","24"]+[str(n) for n in range(26,62,2)]
FRAC={re.sub(r"\D","",v):v for v in NPS if "/" in v}
INTS={v for v in NPS if "/" not in v}
RING=re.compile(r"^(R|RX|BX)-?\d+$")
DUAL=re.compile(r"^(\d[\d ]*(?:\.\d+)?)\s*\((\d[\d ]*(?:\.\d+)?)\)$")
PLAIN=re.compile(r"^\d[\d ]*(?:\.\d+)?$")

B20={"RJ-5-1":[16,17,18],"RJ-5-2":[19,20,21],"RJ-5-3":[22,23],"RJ-5-4":[24],
     "RJ-5-5":[25,26],"RJ-5-6":[26],
     "SW-2.1-1":[30,31,32],"SW-2.1-2":[33,34],"SW-2.1-3":[35,36],
     "SW-2.1-4":[37],"SW-2.1-5":[38],"SW-2.1-6":[39],
     "GM-2.1-1":[50],"GM-2.1-2":[51,52],"GM-2.1-3":[53,54]}
B20_VERB={"RJ-3.2-1":[15],"SW-2.5-1":[40],"SW-2.5-2":[41],"SW-2.5-3":[42],
          "SW-2.5-4":[43],"SW-3-1":[44,45],"SW-4.1-1":[45,46],
          "GM-3.1-1":[55],"GM-4.1-1":[56]}
B21={"4.1-1":[14],"4.1-2":[15],"4.1-3":[16],"4.1-4":[17],"4.1-5":[18],
     "4.1-6":[18,19],"4.1-7":[19],"4.1-8":[19,20],"4.1-9":[20]}


def canon_nps(tok):
    t=tok.replace("∕","/").replace("⁄","/").replace(" ","")
    if "/" in t:
        return FRAC.get(re.sub(r"\D","",t))
    return t if t in INTS else None


def key_of(line):
    t=line.strip()
    if RING.fullmatch(t): return ("ring", t)
    n=canon_nps(t)
    return ("nps", n) if n else None


def table_lines(doc, tid, pages):
    out=[]
    for pg in pages:
        lines=[l.strip() for l in doc[pg-1].get_text().split("\n") if l.strip()]
        # slice: from own title (if present) to the next different table title
        start=0
        for i,l in enumerate(lines):
            if l.startswith(f"Table {tid}"): start=i; break
        seg=[]
        for l in lines[start:]:
            if l.startswith("Table ") and not l.startswith(f"Table {tid}") and seg:
                break
            if "U.S. Customary" in l:
                seg.append("__US_UNITS_CUT__"); break
            seg.append(l)
        out+=seg
    return out


def parse_structured(lines, tid):
    rows=[]; headers=[]; notes=[]; in_notes=False; K=None; i=0; seen=False
    flags=[]
    while i<len(lines):
        l=lines[i]
        if l=="__US_UNITS_CUT__": break
        if in_notes or l.startswith(("NOTES","NOTE:","GENERAL NOTE")):
            in_notes=True; notes.append(l); i+=1; continue
        if re.fullmatch(r"ASME B16\.2[01].*",l) and seen:
            i+=1; continue
        k=key_of(l)
        # avoid class-number headers being taken as NPS keys: a key line must be
        # followed by a value-looking line
        if k and i+1<len(lines) and (DUAL.fullmatch(lines[i+1]) or PLAIN.fullmatch(lines[i+1])
                                     or lines[i+1] in ("…","...")):
            vals=[]; j=i+1
            while j<len(lines) and (DUAL.fullmatch(lines[j]) or PLAIN.fullmatch(lines[j])
                                    or lines[j] in ("…","...")):
                m=DUAL.fullmatch(lines[j])
                if m:
                    mm=float(m.group(1).replace(" ","")); inch=float(m.group(2).replace(" ",""))
                    d=abs(mm-inch*25.4)
                    if d>2.0: raise ValueError(f"{tid}: {k[1]}: mm/in mismatch {mm}/{inch}")
                    if d>0.6: flags.append(f"{k[1]}: {mm} vs {inch}in")
                    vals.append([mm,inch])
                elif lines[j] in ("…","..."):
                    vals.append("…")
                else:
                    vals.append(float(lines[j].replace(" ","")))
                j+=1
            if K is None: K=len(vals)
            if len(vals)!=K:
                raise ValueError(f"{tid}: row {k[1]} has {len(vals)} values, expected {K}")
            rows.append({"key":k[1],"kind":k[0],"v":vals}); seen=True; i=j
        else:
            if not seen: headers.append(l)
            i+=1
    if not rows: raise ValueError(f"{tid}: no rows")
    keys=[r["key"] for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError(f"{tid}: duplicate keys")
    out={"table":tid,"n_columns":K,"rows":rows,
         "header_lines_raw":headers,"notes":" | ".join(notes)}
    if flags: out["unit_roundoff_flags"]=flags
    return out


def build(doc, structured, verbatim, std, edition):
    tables=[]; verb={}
    for tid,pages in structured.items():
        lines=table_lines(doc,tid,pages)
        try:
            tables.append(parse_structured(lines,tid))
            r=tables[-1]
            print(f"  {std} {tid}: {len(r['rows'])} rows x {r['n_columns']} cols "
                  f"({r['rows'][0]['key']}..{r['rows'][-1]['key']})")
        except ValueError as e:
            verb[tid]={"lines":lines,"parse_note":str(e)}
            print(f"  {std} {tid}: VERBATIM fallback ({e})")
    for tid,pages in verbatim.items():
        verb[tid]={"lines":table_lines(doc,tid,pages)}
    return {"standard":std,"edition":edition,
            "source":"text layer of the licensed PDF; dual-unit cells verified at 25.4 (tol 0.6 mm)",
            "dimension_tables":tables,
            "verbatim_tables":verb}


def main():
    p20,p21=sys.argv[1],sys.argv[2]
    d20=fitz.open(p20); d21=fitz.open(p21)
    sec20=build(d20,B20,B20_VERB,"ASME B16.20","2023")
    sec21=build(d21,B21,{}, "ASME B16.21","2021")
    d20.close(); d21.close()
    path=os.path.join(ROOT,"datapacks","gaskets.json")
    pack=json.load(open(path,encoding="utf-8")) if os.path.exists(path) else {
        "meta":{"schema":"gasket-master v1"}}
    pack["meta"].update({"SYNTHETIC":False,
        "note":"Extracted from the user's licensed standards. Copyrighted data - private use only."})
    pack["b16_20"]=sec20; pack["b16_21"]=sec21
    json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    n=sum(len(t["rows"]) for s in (sec20,sec21) for t in s["dimension_tables"])
    print(f"wrote {path}: {n} structured rows")


if __name__=="__main__":
    main()

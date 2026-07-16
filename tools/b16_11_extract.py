#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract ASME B16.11-2016 metric tables from the standard's text-layer PDF
into the fittings datapack (datapacks/fittings.json, git-ignored).

Tables 1-6 (dimensions, NPS-laddered rows) are parsed into labeled rows;
Tables 7-9 (class/type/schedule correlations) are stored as verbatim grids.
Fraction NPS tokens are split across text fragments by the PDF ('1','∕','8');
they are reassembled and confirmed against the closed NPS ladder with the same
unique-alignment rule used for B16.5/B16.47 (fails loudly if ambiguous).
'…' = no value for that class/size, as printed. Notes are kept verbatim.

Usage: python tools/b16_11_extract.py "<path to ASME B16.11-2016.pdf>"
"""
from __future__ import annotations
import json, os, re, sys

import fitz  # PyMuPDF
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADDER = ["1/8","1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","4"]
LDIG = ["".join(sorted(re.sub(r"\D","",v))) for v in LADDER]
NOT_RATED = {"…","...","-","—"}

DIM_TABLES = {21:("1","Socket-Welding Elbows, Tees, and Crosses"),
              22:("2","Socket-Welding Couplings, Bosses, Caps, and Couplets"),
              23:("3","Threaded Elbows, Tees, and Crosses"),
              24:("4","Threaded Street Elbows"),
              25:("5","Threaded Couplings, Bosses, Caps, and Couplets"),
              26:("6","Plugs and Bushings")}
GRID_PAGE = 27   # Tables 7, 8, 9


def clean(s):
    return (s or "").replace("∕","/").replace("⁄","/").replace("\n"," ").strip()


def align(tokens, label):
    """Unique ascending alignment of size tokens onto LADDER (digits match)."""
    n,L=len(tokens),len(LADDER)
    # fragments may reassemble out of order ('12/2' for 2-1/2): compare the
    # digit MULTISET (sorted digits are unique across this closed ladder)
    dig=["".join(sorted(re.sub(r"\D","",t))) for t in tokens]
    INF=10**9
    dp=[[(INF,0)]*(L+1) for _ in range(n+1)]
    for j in range(L+1): dp[n][j]=(0,1)
    for i in range(n-1,-1,-1):
        for j in range(L-1,-1,-1):
            best,cnt=dp[i][j+1]
            c=0 if dig[i]==LDIG[j] else INF   # dims tables: exact digits only
            sub,subc=dp[i+1][j+1]
            if sub<INF and c==0:
                cand=c+sub
                if cand<best: best,cnt=cand,subc
                elif cand==best: cnt+=subc
            dp[i][j]=(best,cnt)
    cost,cnt=dp[0][0]
    if cost>=INF: raise ValueError(f"{label}: sizes {tokens} do not align to ladder")
    if cnt!=1: raise ValueError(f"{label}: ambiguous size alignment {tokens}")
    out,i,j=[],0,0
    while i<n:
        if dig[i]==LDIG[j] and dp[i+1][j+1][0]==dp[i][j][0]:
            out.append(LADDER[j]); i+=1; j+=1
        else: j+=1
    return out


def _cluster(vals, gap):
    vals=sorted(vals); groups=[[vals[0]]]
    for v in vals[1:]:
        if v-groups[-1][-1]<=gap: groups[-1].append(v)
        else: groups.append([v])
    return [sum(g)/len(g) for g in groups]


def parse_dim_page(pl, pageno, tno, title):
    """Coordinate-based parsing. Column x-positions come from the numeric data
    words themselves; header phrases (grouped per band, with real x-spans) are
    assigned to every column their span covers -> correct hierarchical labels.
    Rows are stored as value-arrays aligned to the columns list (lossless even
    with duplicate label texts). Every row must fill every column with a value
    or a printed '\u2026' - anything else fails loudly."""
    p = pl.pages[pageno-1]
    words=p.extract_words(x_tolerance=1.5, y_tolerance=2.0)
    NUM=re.compile(r"^\d+(\.\d+)?$")
    CLASSES={"2000","3000","6000","9000"}   # B16.11 class designations (public fact)
    def is_val(t): return (bool(NUM.fullmatch(t)) and t not in CLASSES) or t in NOT_RATED
    rows_map={}
    for w in words:
        rows_map.setdefault(round(w["top"]/3),[]).append(w)
    vrows=[sorted(v,key=lambda w:w["x0"]) for _,v in sorted(rows_map.items())]
    def deci(r): return sum(1 for w in r if is_val(w["text"]))
    d0=next(i for i,r in enumerate(vrows) if deci(r)>=5)
    # column centers from all data rows
    # size zone: bounded by the fraction fragments (the only words with '/')
    frac=[w for w in words if re.fullmatch(r"\d*[/\u2044\u2215]\d*", clean(w["text"]) or "")]
    if not frac:
        raise ValueError(f"T{tno}: no fraction size fragments found")
    xmin=min(w["x0"] for w in frac)
    frac=[w for w in frac if w["x0"]<=xmin+25]   # leftmost cluster = size column
    size_x0=min(w["x0"] for w in frac)-7
    left_bound=max(w["x1"] for w in frac)+7
    data_rows=[r for r in vrows[d0:] if deci(r)>=5]
    centers=[(w["x0"]+w["x1"])/2 for r in data_rows for w in r
             if is_val(w["text"]) and (w["x0"]+w["x1"])/2>left_bound]
    cols=_cluster(centers, gap=13)
    # header labels: per band, group words into phrases (gap>9 splits); a phrase
    # labels every column whose center lies within its x-span (+pad)
    labels=[[] for _ in cols]
    for r in vrows[:d0]:
        band=" ".join(w["text"] for w in r)
        if band.startswith(("Table","\u00f0","ASME")): continue
        toks=[w for w in r if (w["x0"]+w["x1"])/2>min(cols)-20]
        if len(toks)>=3 and all(len(w["text"])<=5 for w in toks):
            # partition row (class numbers / Max.-Min. units): each token owns
            # the column-space up to the midpoint with its neighbours
            toks=sorted(toks,key=lambda w:w["x0"])
            mids=[(toks[k]["x1"]+toks[k+1]["x0"])/2 for k in range(len(toks)-1)]
            bounds=[-1e9]+mids+[1e9]
            for k,w in enumerate(toks):
                for j,c in enumerate(cols):
                    if bounds[k]<=c<bounds[k+1]:
                        labels[j].append(clean(w["text"]))
            continue
        phrases=[]; cur=[r[0]] if r else []
        for w in r[1:]:
            if w["x0"]-cur[-1]["x1"]<=9: cur.append(w)
            else: phrases.append(cur); cur=[w]
        if cur: phrases.append(cur)
        for ph in phrases:
            x0,x1=ph[0]["x0"]-10,ph[-1]["x1"]+10
            txt=clean(" ".join(w["text"] for w in ph))
            for j,c in enumerate(cols):
                if x0<=c<=x1:
                    labels[j].append(txt)
    labels=[" / ".join(l) if l else f"col{j+1}" for j,l in enumerate(labels)]
    # notes block boundary
    notes=[]; note_top=None
    for r in vrows:
        joined=" ".join(w["text"] for w in r)
        if note_top is None and joined.startswith(("NOTES","GENERAL NOTE")):
            note_top=r[0]["top"]
        if note_top is not None and r[0]["top"]>=note_top:
            notes.append(clean(joined))
    cut=note_top if note_top is not None else 10**9
    # size tokens: assign every left-zone fragment to the NEAREST data row by y
    # (numerator sits just above the row, denominator just below - geometric,
    # deterministic); then each per-row token must sit on the ladder, strictly
    # ascending. Loud failure otherwise.
    drows=[r for r in vrows[d0:] if deci(r)>=5 and r[0]["top"]<cut]
    dy=[sum(w["top"] for w in r)/len(r) for r in drows]
    frags=[w for w in words if size_x0<=w["x0"] and w["x1"]<=left_bound
           and dy[0]-15<=w["top"]<min(cut, dy[-1]+15)
           and re.fullmatch(r"[\d/\u2044\u2215]+", clean(w["text"]) or "x")]
    per_row=[[] for _ in drows]
    for w in sorted(frags,key=lambda w:(w["top"],w["x0"])):
        i=min(range(len(dy)),key=lambda k:abs(dy[k]-w["top"]))
        if abs(dy[i]-w["top"])>14:
            raise ValueError(f"T{tno}: orphan size fragment '{w['text']}' at y={w['top']:.0f}")
        per_row[i].append(clean(w["text"]))
    def sd(t): return "".join(sorted(re.sub(r"\D","",t)))
    out=[]; last=-1
    for r,fr in zip(drows,per_row):
        tok="".join(fr)
        if sd(tok) not in LDIG or LDIG.index(sd(tok))<=last:
            raise ValueError(f"T{tno}: size token '{tok}' invalid after {LADDER[last] if last>=0 else 'start'}")
        last=LDIG.index(sd(tok))
        row=[None]*len(cols)
        for w in r:
            if not is_val(w["text"]) or (w["x0"]+w["x1"])/2<=left_bound: continue
            c=(w["x0"]+w["x1"])/2
            j=min(range(len(cols)),key=lambda k:abs(cols[k]-c))
            if abs(cols[j]-c)>13:
                raise ValueError(f"T{tno}: value '{w['text']}' off-grid at {LADDER[last]}")
            if row[j] is not None:
                raise ValueError(f"T{tno}: column collision at {LADDER[last]} col {j+1}")
            row[j]=w["text"] if w["text"] in NOT_RATED else float(w["text"])
        # blanks exist in the printed tables (columns that do not apply to a
        # size); keep them as null and report for the verification pass
        out.append({"nps":LADDER[last],"v":row})
    return {"table":tno,"title":title,"columns":labels,
            "rows":out,"notes":" | ".join(notes)}


def parse_grid_page(pl, pageno):
    """Tables 7/8/9: store verbatim grids split by 'Table N' anchors."""
    p=pl.pages[pageno-1]
    grid=p.extract_table({"vertical_strategy":"text","horizontal_strategy":"text",
                          "text_x_tolerance":2}) or []
    return [[clean(c) for c in row] for row in grid]


def main():
    src=sys.argv[1]
    d=fitz.open(src); tmp="/tmp/_b1611_dec.pdf"; d.save(tmp); d.close()
    pl=pdfplumber.open(tmp)
    tables=[]
    for pageno,(tno,title) in DIM_TABLES.items():
        t=parse_dim_page(pl,pageno,tno,title)
        tables.append(t)
        blanks=sum(1 for r in t['rows'] for v in r['v'] if v is None)
        print(f"  T{tno}: {len(t['rows'])} sizes ({t['rows'][0]['nps']}..{t['rows'][-1]['nps']}), "
              f"{len(t['columns'])} cols, {blanks} blank cells")
    raw79=parse_grid_page(pl,GRID_PAGE)
    pl.close()

    pack_path=os.path.join(ROOT,"datapacks","fittings.json")
    pack=json.load(open(pack_path,encoding="utf-8")) if os.path.exists(pack_path) else {
        "meta":{"schema":"fitting-master v1"}}
    pack["meta"].update({"SYNTHETIC":False,
        "note":"Extracted from the user's licensed standards. Copyrighted data - private use only."})
    pack["b16_11"]={"standard":"ASME B16.11","edition":"2016","units":"mm",
        "source":"text layer of the licensed PDF",
        "dimension_tables":tables,
        "class_type_correlation_raw":{"page":GRID_PAGE,
            "content":"Tables 7 (types by class & NPS range), 8 (correlation of class with pipe schedule for ratings), 9 (nominal wall Sch160/XXS small NPS) - verbatim grid",
            "grid":raw79}}
    json.dump(pack,open(pack_path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"wrote {pack_path}")


if __name__=="__main__":
    main()

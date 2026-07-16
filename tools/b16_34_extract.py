#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASME B16.34-2025 valve ratings extractor - coordinate-based.
Columns come from x-clusters of the class-header numbers; every value is
assigned to its physical column, so trailing blank columns (classes that stop
at high temperature) are handled exactly as printed. Standard + Special Class
sections per material group; SI tables only. Output: datapacks/valves.json.
Usage: python tools/b16_34_extract.py "<pdf>"
"""
import json, os, re, sys, warnings
warnings.filterwarnings("ignore")
import fitz, pdfplumber

ROOT="/sessions/quirky-sleepy-goldberg/mnt/pms-toolkit"
CLS=[150,300,600,900,1500,2500,4500]
NUM=re.compile(r"^\d[\d ]*(?:\.\d+)?$")

def vrows(words):
    m={}
    for w in words: m.setdefault(round(w["top"]/3.2),[]).append(w)
    return [sorted(v,key=lambda w:w["x0"]) for _,v in sorted(m.items())]

def parse_group(pl, pages, group):
    sections={}; notes=[]; specs=[]
    cur=None; cols=None
    for pg in pages:
        words=pl.pages[pg-1].extract_words(x_tolerance=1.5,y_tolerance=2.0)
        in_notes=False
        for r in vrows(words):
            j=" ".join(w["text"] for w in r)
            if in_notes or j.startswith(("NOTES","GENERAL NOTE")):
                in_notes=True; notes.append(j); continue
            m=re.match(r"^([A-C]) — (.+)$", j)
            if m:
                cur=m.group(2).strip(); sections[cur]={}; cols=None; continue
            if cur is None:
                if re.match(r"^[AB]\s?\d{3}\b", j): specs.append(j)
                continue
            # class header row: exactly the class numbers
            toks=[w["text"] for w in r]
            if cols is None:
                nums=[w for w in r if NUM.fullmatch(w["text"])
                      and float(w["text"]).is_integer() and int(float(w["text"])) in CLS]
                others=[w for w in r if w not in nums and NUM.fullmatch(w["text"])]
                if len(nums)>=5 and not others:
                    cols=[((w["x0"]+w["x1"])/2, int(float(w["text"]))) for w in nums]
                    for _,c in cols: sections[cur].setdefault(str(c),[])
                continue
            # data row: temp lead + values at column positions
            lead=r[0]["text"]
            mm=re.match(r"^min\.? to 38", j, re.I)
            if mm: temp=38.0
            elif NUM.fullmatch(lead) and float(lead)<1000 and float(lead).is_integer():
                temp=float(lead)
            else:
                continue
            body=[w for w in r[1:] if NUM.fullmatch(w["text"])]
            if mm:  # 'min. to 38 (6)' words: skip label tokens
                body=[w for w in r if NUM.fullmatch(w["text"]) and w["x0"]>cols[0][0]-25]
            if not body: continue   # footer page number etc.
            for w in body:
                c=(w["x0"]+w["x1"])/2
                k=min(range(len(cols)),key=lambda i:abs(cols[i][0]-c))
                if abs(cols[k][0]-c)>16:
                    raise ValueError(f"G{group} {cur} T{temp}: value '{w['text']}' off-grid")
                key=str(cols[k][1])
                if sections[cur][key] and sections[cur][key][-1][0]==temp:
                    raise ValueError(f"G{group} {cur} T{temp}: duplicate col {key}")
                sections[cur][key].append([temp,float(w["text"].replace(" ",""))])
    if "Standard Class" not in sections or not any(sections["Standard Class"].values()):
        raise ValueError(f"G{group}: no Standard Class data")
    return specs, sections, " | ".join(notes)

def clean_specs(specs):
    out=[]
    for s in specs:
        s=re.sub(r"\(\d+\)","",s).replace(",","").strip()
        for tok in re.split(r"(?=\b[AB]\s?\d{2,4}\b)", s):
            tok=re.sub(r"\s+"," ",tok).strip()
            if re.match(r"^[AB]\s?\d{2,4}\b", tok) and tok not in out:
                out.append(tok.replace("A ","A").replace("B ","B",1)
                           if re.match(r"^[AB]\s\d",tok) else tok)
    return out

def main():
    src=sys.argv[1]
    doc=fitz.open(src); doc.save("/tmp/b1634.pdf"); doc.close()
    doc=fitz.open("/tmp/b1634.pdf")
    si={}
    for p in range(50,208):
        t=doc[p].get_text()
        m=re.search(r"Table\s+(2-[\d.]+)\s*\n(?:ð\d+Þ\s*\n)?Ratings for Group ([\d.]+) Materials — SI", t)
        if m: si.setdefault(m.group(2), []).append(p+1)
    def pages_text(a,b):
        return [l.strip() for p in range(a,b) for l in doc[p].get_text().split("\n") if l.strip()]
    verb={"Table 1 (material specification list)":pages_text(48,56),
          "Table 3A (valve body minimum wall thickness tm, mm)":pages_text(208,213),
          "Table 4 (min wall SW/threaded ends)":pages_text(216,218)}
    doc.close()
    pl=pdfplumber.open("/tmp/b1634.pdf")
    groups=[]; n_pts=0
    for g,pages in sorted(si.items(), key=lambda x:(int(x[0].split(".")[0]),int(x[0].split(".")[1]))):
        specs,secs,notes=parse_group(pl,pages,g)
        std={c:v for c,v in secs["Standard Class"].items() if v}
        entry={"group":g,"specs":clean_specs(specs),"rating_table":f"2-{g}",
               "notes":notes,
               "max_temp_C":max(p2[0] for v in std.values() for p2 in v),
               "ratings":std}
        sp={c:v for c,v in secs.get("Special Class",{}).items() if v}
        if sp: entry["ratings_special_class"]=sp
        groups.append(entry)
        n_pts+=sum(len(v) for v in std.values())+sum(len(v) for v in sp.values())
    path=os.path.join(ROOT,"datapacks","valves.json")
    pack=json.load(open(path,encoding="utf-8")) if os.path.exists(path) else {"meta":{}}
    pack.setdefault("meta",{}).update({"schema":"valve-master v1","SYNTHETIC":False,
        "standard":"ASME B16.34","edition":"2025","pressure_units":"bar","temp_units":"C",
        "note":("Extracted from the user's licensed ASME B16.34-2025 (SI tables). "
                "Copyrighted - private use only. Standard Class ratings are "
                "engine-compatible (material_groups/ratings); Special Class per "
                "group in ratings_special_class. Blank high-temperature cells "
                "are as printed (class curve simply ends).")})
    pack["material_groups"]=groups
    pack["verbatim_tables"]=verb
    json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"wrote {path}: {len(groups)} groups, {n_pts} rating points")

if __name__=="__main__":
    main()

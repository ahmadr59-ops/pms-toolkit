import json, os, re, warnings
warnings.filterwarnings("ignore")
import fitz, pdfplumber

ROOT="/sessions/quirky-sleepy-goldberg/mnt/pms-toolkit"
NPS = ["1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4",
       "5","6","8","10","12","14","16","18","20","22","24"]+[str(n) for n in range(26,62,2)]
FRAC={re.sub(r"\D","",v):v for v in NPS if "/" in v}
INTS={v for v in NPS if "/" not in v}
RING=re.compile(r"^(R|RX|BX)-\d+$")
PAIR=re.compile(r"^([\d∕⁄/ ]+(?:\.\d+)?)\s*\((\d[\d ]*(?:\.\d+)?)\)$")
PLAIN=re.compile(r"^\d[\d ]*(?:\.\d+)?$")

def canon_nps(t):
    t=t.replace("∕","/").replace("⁄","/").replace(" ","")
    if "/" in t: return FRAC.get(re.sub(r"\D","",t))
    return t if t in INTS else None

def frac_val(s):
    s=s.replace("∕","/").replace(" ","")
    if "/" in s:
        m=re.fullmatch(r"(?:(\d+)-)?(\d+)/(\d+)",s) or re.fullmatch(r"(\d)?(\d)/(\d)",s)
        if m:
            w=int(m.group(1) or 0); return w+int(m.group(2))/int(m.group(3))
        return None
    try: return float(s)
    except ValueError: return None

def classify_pair(a_raw,b_raw,tid,key,flags):
    """a (b): mm/in dual, in/in same-unit pair, or fraction-inch pair.
    Returns [mm,in] for true duals; verbatim string otherwise (lossless)."""
    a=frac_val(a_raw); b=float(b_raw.replace(" ",""))
    if a is None: return None
    if abs(a-b*25.4)<=0.6: return [a,b]
    if abs(a-b*25.4)<=2.0:
        flags.append(f"{key}: round-off {a} vs {b}in")
        return [a,b]
    if abs(a-b)<=0.02*max(a,b,1):    # same-unit pair (in (in.)) as printed
        return f"{a_raw.strip()} ({b_raw.strip()})"
    raise ValueError(f"{tid}: cell '{a_raw} ({b_raw})' at {key}: unit check failed")

def doc_lines(doc, tid, pages):
    out=[]
    for pg in pages:
        lines=[l.strip() for l in doc[pg-1].get_text().split("\n") if l.strip()]
        start=0
        for i,l in enumerate(lines):
            if l.startswith(f"Table {tid}"): start=i; break
        seg=[]
        for l in lines[start:]:
            if l.startswith("Table ") and not l.startswith(f"Table {tid}") and seg: break
            if "U.S. Customary" in l: break
            seg.append(l)
        out+=seg
    return out

def parse_stream(doc, tid, pages, key_kind, allow_nps_cells=False):
    lines=doc_lines(doc,tid,pages)
    def is_key(l):
        return (l if RING.fullmatch(l) else None) if key_kind=="ring" else canon_nps(l)
    flags=[]
    def cell(l,key):
        if re.fullmatch(r"ASME B16\.2[01].*|\d{1,3}",l) and not PLAIN.fullmatch(l):
            return "SKIP"
        m=PAIR.fullmatch(l)
        if m: return classify_pair(m.group(1),m.group(2),tid,key,flags)
        if PLAIN.fullmatch(l):
            v=l.replace(" ","")
            return float(v)
        if l in ("…","..."): return "…"
        if allow_nps_cells:
            n=canon_nps(l)
            if n: return n
        return None
    rows=[]; headers=[]; notes=[]; in_notes=False; K=None; i=0; seen=False
    while i<len(lines):
        l=lines[i]
        if in_notes or l.startswith(("NOTES","NOTE:","GENERAL NOTE")):
            in_notes=True; notes.append(l); i+=1; continue
        if re.fullmatch(r"ASME B16\.2[01].*",l) or (seen and re.fullmatch(r"\d{1,3}",l) and K and False):
            i+=1; continue
        k=is_key(l)
        if k and i+1<len(lines) and cell(lines[i+1],k) not in (None,"SKIP"):
            vals=[]; j=i+1
            while j<len(lines):
                v=cell(lines[j],k)
                if v=="SKIP":
                    if lines[j].startswith("ASME"): j+=1; continue
                    break
                if v is None: break
                vals.append(v); j+=1
            if K is None: K=len(vals)
            if len(vals)!=K: raise ValueError(f"{tid}: {k} has {len(vals)}, expected {K}")
            rows.append({"key":k,"v":vals}); seen=True; i=j
        else:
            if not seen and not l.startswith(("ASME","Table")): headers.append(l)
            i+=1
    if not rows: raise ValueError(f"{tid}: no rows")
    keys=[r["key"] for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError(f"{tid}: dup keys "+str([x for x in keys if keys.count(x)>1][:4]))
    out={"table":tid,"n_columns":K,"rows":rows,"header_lines_raw":headers[:40],
         "notes":" | ".join(notes)}
    if flags: out["unit_roundoff_flags"]=flags
    return out

def parse_coord(pl, tid, pages, min_vals=3):
    flags=[]
    NUMv=re.compile(r"^\d[\d ]*(?:\.\d+)?$")
    data=[]; headers=[]
    for pg in pages:
        words=pl.pages[pg-1].extract_words(x_tolerance=1.5,y_tolerance=2.0)
        m={}
        for w in words: m.setdefault(round(w["top"]/3),[]).append(w)
        rws=[sorted(v,key=lambda w:w["x0"]) for _,v in sorted(m.items())]
        def cells(ws,key):
            out=[];i=0
            while i<len(ws):
                t=ws[i]["text"]
                # merge broken thousands: '1' + '009.7'
                if re.fullmatch(r"\d{1,3}",t) and i+1<len(ws) and \
                   re.fullmatch(r"\d{3}(\.\d+)?",ws[i+1]["text"]) and ws[i+1]["x0"]-ws[i]["x1"]<4:
                    t=t+ws[i+1]["text"]; x0,x1=ws[i]["x0"],ws[i+1]["x1"]; i+=2
                else:
                    x0,x1=ws[i]["x0"],ws[i]["x1"]; i+=1
                if NUMv.fullmatch(t):
                    if i<len(ws):
                        m2=re.fullmatch(r"\((\d[\d ]*(?:\.\d+)?)\)",ws[i]["text"])
                        if m2 and ws[i]["x0"]-x1<8:
                            v=classify_pair(t,m2.group(1),tid,key,flags)
                            out.append((x0/2+ws[i]["x1"]/2,v)); i+=1; continue
                    out.append(((x0+x1)/2,float(t.replace(" ","")))); continue
                if t in ("…","..."): out.append(((x0+x1)/2,"…")); continue
                if t=="[Note" and i<len(ws) and re.fullmatch(r"\(\d\)\]",ws[i]["text"]):
                    out.append((x0/2+ws[i]["x1"]/2,f"[Note {ws[i]['text'][:-1]}]")); i+=1; continue
            return out
        seen=False; drows=[]
        for r in rws:
            j=" ".join(w["text"] for w in r)
            if j.startswith(("NOTES","NOTE:","GENERAL NOTE")): break
            k0=r[0]["text"].replace("∕","/")
            k=(k0 if RING.fullmatch(k0) else canon_nps(k0))
            vs=cells(r[1:] if k else r, k or "?")
            if len(vs)>=min_vals and (k or seen):
                drows.append([k,sum(w["top"] for w in r)/len(r),vs]); seen=(seen or bool(k))
            elif not seen: headers.append(j)
        # fraction fragment keying
        frs=[w for w in words if w["x0"]<95 and
             re.fullmatch(r"[\d]*[∕/][\d]*|\d{1,2}",w["text"].replace("∕","/"))]
        if drows:
            dy=[y for _,y,_ in drows]
            per=[[] for _ in drows]
            for w in sorted(frs,key=lambda w:(w["top"],w["x0"])):
                ii=min(range(len(dy)),key=lambda k2:abs(dy[k2]-w["top"]))
                if abs(dy[ii]-w["top"])<=13: per[ii].append(w["text"].replace("∕","/"))
            LD={"".join(sorted(re.sub(r"\D","",v))):v for v in NPS}
            for idx,d in enumerate(drows):
                if d[0] is None:
                    tok="".join(per[idx])
                    kk=LD.get("".join(sorted(re.sub(r"\D","",tok)))) if tok else None
                    if not kk: raise ValueError(f"{tid}: unkeyed data row (frags={per[idx]})")
                    d[0]=kk
            data+=[(k,vs) for k,_,vs in drows]
    if not data: raise ValueError(f"{tid}: no data rows")
    def clus(vals,gap=13):
        vals=sorted(vals); g=[[vals[0]]]
        for v in vals[1:]:
            (g[-1].append(v) if v-g[-1][-1]<=gap else g.append([v]))
        return [sum(x)/len(x) for x in g]
    cents=clus([c for _,vs in data for c,_ in vs])
    K=len(cents); out=[]
    for k,vs in data:
        row=[None]*K
        for c,v in vs:
            j=min(range(K),key=lambda i2:abs(cents[i2]-c))
            if abs(cents[j]-c)>13: raise ValueError(f"{tid}: off-grid at {k}")
            if row[j] is not None: raise ValueError(f"{tid}: collision at {k}")
            row[j]=v
        out.append({"key":k,"v":row})
    keys=[r["key"] for r in out]
    if len(keys)!=len(set(keys)): raise ValueError(f"{tid}: dup keys")
    res={"table":tid,"n_columns":K,"rows":out,"header_lines_raw":headers[:40],
         "notes":"blank cells (null) reproduce blanks printed in the standard"}
    if flags: res["unit_roundoff_flags"]=flags
    return res

u="/sessions/quirky-sleepy-goldberg/mnt/uploads"
d20=fitz.open(f"{u}/ASME B16.20-2023.pdf"); d21=fitz.open(f"{u}/ASME B16.21 2021 (1).pdf")
pl20=pdfplumber.open("/tmp/b1620.pdf")
path=os.path.join(ROOT,"datapacks","gaskets.json")
pack=json.load(open(path,encoding="utf-8"))
def install(std,t):
    sec=pack[std]
    sec["dimension_tables"]=[x for x in sec["dimension_tables"] if x["table"]!=t["table"]]+[t]
    sec["verbatim_tables"].pop(t["table"],None)
    print(f"  {std} {t['table']}: {len(t['rows'])} rows x {t['n_columns']} cols "
          f"({t['rows'][0]['key']}..{t['rows'][-1]['key']})")
for tid,pages in (("4.1-1",[14]),("4.1-2",[15]),("4.1-4",[17]),("4.1-6",[18,19]),("4.1-9",[20])):
    try: install("b16_21", parse_stream(d21,tid,pages,"nps"))
    except Exception as e: print(f"  b16_21 {tid}: verbatim ({e})")
try: install("b16_20", parse_stream(d20,"RJ-5-2",[19,20,21],"ring",allow_nps_cells=True))
except Exception as e: print(f"  b16_20 RJ-5-2: verbatim ({e})")
for tid,pages,mv in (("SW-2.1-1",[30],10),("SW-2.1-5",[38],3),("SW-2.1-6",[39],3),
                     ("GM-2.1-2",[51,52],3),("GM-2.1-3",[53,54],3),("RJ-5-6",[26],3)):
    try: install("b16_20", parse_coord(pl20,tid,pages,mv))
    except Exception as e: print(f"  b16_20 {tid}: verbatim ({e})")
json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("saved")
import json, os, re, warnings
warnings.filterwarnings("ignore")
import fitz

ROOT="/sessions/quirky-sleepy-goldberg/mnt/pms-toolkit"
NPS = ["1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4",
       "5","6","8","10","12","14","16","18","20","22","24"]+[str(n) for n in range(26,62,2)]
FRAC={re.sub(r"\D","",v):v for v in NPS if "/" in v}
INTS={v for v in NPS if "/" not in v}
PAIR=re.compile(r"^([\d∕⁄/ ]+(?:\.\d+)?)\s*\((\d[\d ]*(?:\.\d+)?)\)$")
PLAIN=re.compile(r"^\d[\d ]*(?:\.\d+)?$")

def canon_nps(t):
    t=t.replace("∕","/").replace("⁄","/").replace(" ","")
    if "/" in t: return FRAC.get(re.sub(r"\D","",t))
    return t if t in INTS else None

def frac_val(s):
    s=s.replace("∕","/").replace("⁄","/").replace(" ","")
    if "/" not in s:
        try: return float(s)
        except ValueError: return None
    m=re.fullmatch(r"(\d+)-(\d+)/(\d+)",s)
    if m: return int(m.group(1))+int(m.group(2))/int(m.group(3))
    m=re.fullmatch(r"(\d+)/(\d+)",s)
    if not m: return None
    a,b=m.group(1),m.group(2)
    if len(a)>=2 and int(a[1:])<int(b):        # collapsed '11/8' = 1-1/8
        return int(a[0])+int(a[1:])/int(b)
    return int(a)/int(b)

def classify_pair(a_raw,b_raw,tid,key,flags):
    a=frac_val(a_raw); b=float(b_raw.replace(" ",""))
    if a is None: return None
    if abs(a-b*25.4)<=0.6: return [a,b]
    if abs(a-b*25.4)<=2.0:
        flags.append(f"{key}: round-off {a} vs {b}in"); return [a,b]
    if abs(a-b)<=0.02*max(a,b,0.5)+0.006:
        return f"{a_raw.strip()} ({b_raw.strip()})"   # same-unit pair, verbatim
    raise ValueError(f"{tid}: cell '{a_raw} ({b_raw})' at {key}: unit check failed")

def doc_lines(doc, tid, pages):
    out=[]
    for pg in pages:
        lines=[l.strip() for l in doc[pg-1].get_text().split("\n") if l.strip()]
        start=0
        for i,l in enumerate(lines):
            if l.startswith(f"Table {tid}"): start=i; break
        seg=[]
        for l in lines[start:]:
            if l.startswith("Table ") and not l.startswith(f"Table {tid}") and seg: break
            if "U.S. Customary" in l: break
            seg.append(l)
        out+=seg
    return out

def parse_stream(doc, tid, pages):
    lines=doc_lines(doc,tid,pages)
    flags=[]
    def cell(l,key):
        m=PAIR.fullmatch(l)
        if m: return classify_pair(m.group(1),m.group(2),tid,key,flags)
        if PLAIN.fullmatch(l): return float(l.replace(" ",""))
        if l in ("…","..."): return "…"
        return None
    def skippable(l): return l.startswith("ASME B16.2")
    rows=[]; headers=[]; notes=[]; in_notes=False; K=None; i=0; seen=False
    while i<len(lines):
        l=lines[i]
        if in_notes or l.startswith(("NOTES","NOTE:","GENERAL NOTE")):
            in_notes=True; notes.append(l); i+=1; continue
        if skippable(l): i+=1; continue
        k=canon_nps(l)
        if k and i+1<len(lines) and cell(lines[i+1],k) is not None:
            vals=[]; j=i+1
            while j<len(lines) and (K is None or len(vals)<K):
                if skippable(lines[j]): j+=1; continue
                v=cell(lines[j],k)
                if v is None: break
                vals.append(v); j+=1
            if K is None: K=len(vals)
            if len(vals)!=K: raise ValueError(f"{tid}: {k} has {len(vals)}, expected {K}")
            rows.append({"key":k,"v":vals}); seen=True; i=j
        else:
            if not seen and not l.startswith("Table"): headers.append(l)
            i+=1
    if not rows: raise ValueError(f"{tid}: no rows")
    keys=[r["key"] for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError(f"{tid}: dup keys")
    out={"table":tid,"n_columns":K,"rows":rows,"header_lines_raw":headers[:40],
         "notes":" | ".join(notes)}
    if flags: out["unit_roundoff_flags"]=flags
    return out

u="/sessions/quirky-sleepy-goldberg/mnt/uploads"
d21=fitz.open(f"{u}/ASME B16.21 2021 (1).pdf")
path=os.path.join(ROOT,"datapacks","gaskets.json")
pack=json.load(open(path,encoding="utf-8"))
for tid,pages in (("4.1-1",[14]),("4.1-2",[15]),("4.1-4",[17]),("4.1-6",[18,19]),("4.1-9",[20])):
    sec=pack["b16_21"]
    try:
        t=parse_stream(d21,tid,pages)
        sec["dimension_tables"]=[x for x in sec["dimension_tables"] if x["table"]!=tid]+[t]
        sec["verbatim_tables"].pop(tid,None)
        print(f"  4.1 {tid}: {len(t['rows'])} rows x {t['n_columns']} cols ({t['rows'][0]['key']}..{t['rows'][-1]['key']})")
    except Exception as e:
        print(f"  4.1 {tid}: verbatim ({e})")
# check SW-2.1-1 keys
sw=[x for x in pack["b16_20"]["dimension_tables"] if x["table"]=="SW-2.1-1"][0]
print("SW-2.1-1 keys:", [r["key"] for r in sw["rows"]])
json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("saved")
import json, os, re, warnings
warnings.filterwarnings("ignore")
import pdfplumber
ROOT="/sessions/quirky-sleepy-goldberg/mnt/pms-toolkit"
NPS = ["1/4","3/8","1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","3-1/2","4",
       "5","6","8","10","12","14","16","18","20","22","24"]+[str(n) for n in range(26,62,2)]
FRAC={re.sub(r"\D","",v):v for v in NPS if "/" in v}
INTS={v for v in NPS if "/" not in v}
def canon(t):
    t=t.replace("∕","/").replace(" ","")
    return FRAC.get(re.sub(r"\D","",t)) if "/" in t else (t if t in INTS else None)
pl=pdfplumber.open("/tmp/b1620.pdf")
words=pl.pages[29].extract_words(x_tolerance=1.5,y_tolerance=2.0)
m={}
for w in words: m.setdefault(round(w["top"]/3),[]).append(w)
rws=[sorted(v,key=lambda w:w["x0"]) for _,v in sorted(m.items())]
NUM=re.compile(r"^\d[\d ]*(?:\.\d+)?$")
def cells(ws):
    out=[]
    i=0
    while i<len(ws):
        t=ws[i]["text"]
        if t=="[Note" and i+1<len(ws) and re.fullmatch(r"\(\d\)\]",ws[i+1]["text"]):
            out.append((ws[i]["x0"]/2+ws[i+1]["x1"]/2,f"[Note {ws[i+1]['text'][:-1]}]")); i+=2; continue
        if NUM.fullmatch(t):
            out.append(((ws[i]["x0"]+ws[i]["x1"])/2,float(t.replace(" ","")))); i+=1; continue
        i+=1
    return out
drows=[]
for r in rws:
    if " ".join(w["text"] for w in r).startswith(("NOTES","NOTE:","GENERAL")): break
    k=canon(r[0]["text"])
    vs=cells(r[1:] if k else r)
    dec=any(isinstance(v,float) and v!=int(v) for _,v in vs)
    if len(vs)>=10 and (k or dec):
        drows.append([k,sum(w["top"] for w in r)/len(r),vs])
frs=[w for w in words if w["x0"]<95 and re.fullmatch(r"[\d]*[∕/][\d]*|\d{1,2}",w["text"].replace("∕","/"))]
dy=[y for _,y,_ in drows]; per=[[] for _ in drows]
for w in sorted(frs,key=lambda w:(w["top"],w["x0"])):
    i=min(range(len(dy)),key=lambda k2:abs(dy[k2]-w["top"]))
    if abs(dy[i]-w["top"])<=13: per[i].append(w["text"].replace("∕","/"))
LD={"".join(sorted(re.sub(r"\D","",v))):v for v in NPS}
for i,d in enumerate(drows):
    if d[0] is None:
        d[0]=canon("".join(per[i]))
        if not d[0]: raise SystemExit(f"unkeyed: {per[i]}")
def clus(vals,gap=13):
    vals=sorted(vals); g=[[vals[0]]]
    for v in vals[1:]:
        (g[-1].append(v) if v-g[-1][-1]<=gap else g.append([v]))
    return [sum(x)/len(x) for x in g]
cents=clus([c for _,_,vs in drows for c,_ in vs])
out=[]
for k,_,vs in drows:
    row=[None]*len(cents)
    for c,v in vs:
        j=min(range(len(cents)),key=lambda i2:abs(cents[i2]-c))
        if abs(cents[j]-c)>13: raise SystemExit(f"off-grid {k}")
        if row[j] is not None: raise SystemExit(f"collision {k}")
        row[j]=v
    out.append({"key":k,"v":row})
keys=[r["key"] for r in out]
assert len(keys)==len(set(keys)), keys
t={"table":"SW-2.1-1","n_columns":len(cents),"rows":out,
   "header_lines_raw":["SI Units, mm; columns: OD gasket (classes 150-600 / 900-2500), Inside Diameter by class (150,300,400,600,900,1500,2500), OD centering ring by class (150,300,400,600,900,1500,2500) - see printed header"],
   "notes":"[Note (5)] cells kept verbatim; blank cells (null) as printed"}
path=os.path.join(ROOT,"datapacks","gaskets.json")
pack=json.load(open(path,encoding="utf-8"))
sec=pack["b16_20"]
sec["dimension_tables"]=[x for x in sec["dimension_tables"] if x["table"]!="SW-2.1-1"]+[t]
sec["verbatim_tables"].pop("SW-2.1-1",None)
json.dump(pack,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("SW-2.1-1:",len(out),"rows x",len(cents),"cols keys:",keys)

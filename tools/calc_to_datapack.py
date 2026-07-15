#!/usr/bin/env python3
"""Standalone: convert a local B31.3 wall-thickness calculator's material table
into a pms-toolkit datapack (materials.json). No install required.

    python tools/calc_to_datapack.py  path/to/your_calculator.html  materials.json

Then in the dashboard: Data -> Load my data -> Material stress data.
The output holds your allowable-stress values; keep it local (git-ignored).
"""
import json, re, sys

_ARR = re.compile(r"DEFAULT_MATERIALS\s*=\s*\[(.*?)\]\s*;", re.S)
_OBJ = re.compile(r"\{(.*?)\}", re.S)
_AUST = re.compile(r"austenit|stainless|18Cr|Cr-\d*Ni|TP3\d\d|CF8|A312|A358|A403", re.I)

def field(b, n):
    m = re.search(rf'{n}\s*:\s*"([^"]*)"', b) or re.search(rf"{n}\s*:\s*(-?\d+(?:\.\d+)?)", b)
    return m.group(1) if m else None

def split_spec(spec):
    m = re.search(r"\bGr\.?\s*([A-Za-z0-9]+)", spec or "", re.I)
    if m: return spec[:m.start()].strip(), m.group(1)
    m = re.search(r"\b(TP\d+[A-Za-z]*|X\d+|P\d+|F\d+|WPB|WCB)\b", spec or "", re.I)
    if m: return re.sub(r"\s+"," ",(spec[:m.start()]+spec[m.end():]).strip().rstrip(",")), m.group(1)
    return spec, None

def parse_s(s):
    out=[]
    for p in (s or "").split(","):
        if ":" in p:
            t,v=p.split(":",1)
            try: out.append([float(t),float(v)])
            except ValueError: pass
    return out

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    src, dst = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "materials.json")
    txt = open(src, encoding="utf-8", errors="replace").read()
    m = _ARR.search(txt)
    if not m: sys.exit("DEFAULT_MATERIALS array not found in " + src)
    mats=[]
    for om in _OBJ.finditer(m.group(1)):
        b=om.group(1); spec_full=field(b,"spec")
        if not spec_full: continue
        spec,grade=split_spec(spec_full); desc=field(b,"desc") or ""
        s=parse_s(field(b,"s") or "")
        if not s: continue
        mats.append({"spec":spec,"grade":grade,
                     "family":"austenitic" if _AUST.search(spec_full+" "+desc) else "ferritic",
                     "min_temp":field(b,"minTemp"),"max_temp":field(b,"maxTemp"),"s":s})
    json.dump({"meta":{"schema":"material-master v1","stress_units":"MPa","temp_units":"C",
                       "source":"converted from local B31.3 calculator"},"materials":mats},
              open(dst,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Converted {len(mats)} materials -> {dst}")

if __name__ == "__main__":
    main()

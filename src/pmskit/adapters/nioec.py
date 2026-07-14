# -*- coding: utf-8 -*-
"""NIOEC PMS layout adapter.

Best-effort structural parse of the NIOEC Piping Material Specification. Material
and standard descriptions are preserved verbatim; nothing is inferred or
fabricated. Some rows use a merged "double-column" layout in the source tables;
for those, ``size_from``/``size_to`` may combine two sub-ranges and ``size_raw``
keeps the original tokens.
"""
from __future__ import annotations
import os
import re
from ..doc_parser import extract_text
from .base import PMSAdapter

# Full-width -> ASCII normalisation (later pages of the source use full-width
# parentheses / punctuation from the code page, which otherwise breaks parsing).
_FW = {0xFF08: "(", 0xFF09: ")", 0x201C: '"', 0x201D: '"', 0x2018: "'",
       0x2019: "'", 0xFF1A: ":", 0xFF1B: ";", 0xFF0C: ",", 0xFF0D: "-",
       0x2013: "-", 0x2014: "-"}
_FW.update({c: chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)})


def _norm(s: str) -> str:
    s = s.translate(_FW)
    # Strip control chars incl. Word field markers (0x13/0x14/0x15) that break xlsx.
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)
    s = re.sub(r"\bREF\s+_Ref\w+", "", s)     # Word cross-reference field code
    s = re.sub(r"\\[a-z]\b", "", s)            # stray field switches like \r \h
    s = s.replace("\u200e", "").replace("\u200f", "")  # LRM / RLM marks
    return re.sub(r"\s+", " ", s.replace("\x08", " ").replace("؛", ";").replace("°", "")).strip()


_DESC_RE = re.compile(
    r"ASTM|ASME|API|MSS|DIN|BS\d|GR\.|CL[\. ]?\d|SCH|SMLS|RTJ|\bRF\b|\bFF\b|"
    r"B16|B36|B31|A105|A106|A234|A53|A182|A216|SPIRAL|GRAPHITE|MONEL|INCONEL", re.I)
_PART_WORDS = (r"PIPE|ELBOW|TEE|REDUCER|CAP|COUPLING|UNION|NIPPLE|FLANGE|BLIND|OLET|"
               r"GASKET|BOLT|NUT|STUD|VALVE|PLUG|BUSHING|SWAGE|SWAGED|SPECTACLE|SPACER|"
               r"CROSS|BEND|STRAINER|TRAP|ORIFICE|SPADE|NIPOLET|SOCKOLET|WELDOLET|THREDOLET|AUXILIARY")
_PART_RE = re.compile(r"\b(?:" + _PART_WORDS + r")\b", re.I)


def _is_size(c):
    toks = c.split()
    return bool(toks) and all(re.fullmatch(r"\d+(?:-\d+)?(?:/\d+)?", x) for x in toks)


def _is_symbol(c):
    return bool(re.fullmatch(r"\([0-9A-Za-z]{1,4}\)(?:\s*\([0-9A-Za-z]{1,4}\))?", c)) and \
        re.search(r"[A-Za-z]", c) is not None


def _is_note(c):
    return bool(re.fullmatch(r"\(\d+\)", c))


def _is_desc(c):
    return bool(_DESC_RE.search(c))


def _is_partname(c):
    cc = re.sub(r"\(.*?\)", "", c).strip()
    if not cc or len(cc) > 35:
        return False
    if _is_desc(c):
        return False
    if re.search(r"\bPER\b|DWG|THREAD|OR EQUAL|ANSI|ASME|ASTM|API|\bMM\b", cc, re.I):
        return False
    return bool(_PART_RE.search(cc))


def _split_sizes(sizes):
    if not sizes:
        return None, None, sizes
    return sizes[0].split()[0], sizes[-1].split()[-1], sizes


class NIOECAdapter(PMSAdapter):
    name = "nioec"
    label = "NIOEC (National Iranian Oil Engineering & Construction Co.)"

    def parse(self, path: str, company: str | None = None):
        raw = extract_text(path)
        classes = self._parse_classes(raw)
        return self.envelope(classes, company or "NIOEC", os.path.basename(path))

    # -- internal --------------------------------------------------------
    def _parse_classes(self, raw: str):
        pages = []
        for seg in raw.split("PIPING MATERIAL SPECIFICATION")[1:]:
            m = re.search(r"LINE CLASS\s*[:\-]?\s*([A-Za-z0-9()\-/&]+)", seg)
            pages.append((m.group(1).strip() if m else "", seg))

        grouped, order = {}, []
        for name, seg in pages:
            if not name:
                continue
            grouped.setdefault(name, []).append(seg)
            if name not in order:
                order.append(name)

        pnotes = {}
        for m in re.finditer(
                r'PIPING CLASS\s*["“]?\s*([A-Za-z0-9()\-/&]+)\s*["”]?\s*PARTICULAR NOTES'
                r'(.*?)(?=PIPING MATERIAL SPECIFICATION|PIPING CLASS\s*["“]|\Z)', raw, re.S):
            pnotes.setdefault(m.group(1).strip(), _norm(m.group(2))[:2000])

        out = []
        for name in order:
            out.append(self._parse_one(name, grouped[name], pnotes.get(name)))
        return out

    def _parse_one(self, name, segs, notes):
        header = self._header(segs[0])
        comps = self._components(segs)
        return {
            "class": name,
            "service": header.get("service"),
            "main_material": header.get("material"),
            "corrosion_allowance": header.get("ca"),
            "flange_rating_face": header.get("flange"),
            "temp_C": header.get("temp"),
            "press_barg": header.get("press"),
            "particular_notes": notes,
            "components": comps,
            "component_count": len(comps),
        }

    def _header(self, page):
        cut = re.search(r"PART NAME", page, re.I)
        hflat = _norm((page[:cut.start()] if cut else page).replace("\x07", " "))
        marks = []
        for key, pat in [("service", r"\bSERVICE\b(?!\s*LIMIT)"), ("material", r"MAIN MATERIAL"),
                         ("ca", r"\bC\.\s*A\."), ("flange", r"FLANGE RATING\s*&?\s*FACE"),
                         ("limit", r"SERVICE LIMIT")]:
            m = re.search(pat, hflat, re.I)
            if m:
                marks.append((m.start(), m.end(), key))
        marks.sort()
        vals = {}
        for i, (s, e, key) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(hflat)
            vals[key] = _norm(re.sub(r"^[\s:;\-&]+", "", hflat[e:end]))
        cm = re.search(r"([0-9.]+\s*MM)", vals.get("ca", "") or "")
        out = {"service": vals.get("service"), "material": vals.get("material"),
               "ca": cm.group(1) if cm else None, "flange": vals.get("flange"),
               "temp": None, "press": None}
        sl = re.search(r"TEMP\.?\s*C?\s*([-0-9.\s]+?)\s*PRESS\.?\s*BAR[gG]?\s*([-0-9.\s]+)", hflat, re.I)
        if sl:
            out["temp"], out["press"] = sl.group(1).split(), sl.group(2).split()
        return out

    def _components(self, segs):
        comps, cur_part, pend_sym, rec = [], None, None, None

        def flush():
            nonlocal rec
            if rec and rec.get("description"):
                frm, to, sz = _split_sizes(rec["sizes"])
                entry = {"part": rec["part"], "symbol": rec["symbol"], "size_from": frm,
                         "size_to": to, "size_raw": sz, "description": _norm(rec["description"]),
                         "notes": rec["notes"]}
                if not comps or comps[-1] != entry:
                    comps.append(entry)
            rec = None

        for seg in segs:
            active = "PART NAME" not in seg.upper()
            for c in (_norm(x) for x in seg.split("\x07")):
                if not c:
                    continue
                if re.search(r"PART NAME", c, re.I):
                    active = True
                    continue
                if not active:
                    continue
                if re.search(r"MAIN MATERIAL|LINE CLASS|FLANGE RATING|C\.\s*A\.|CLASSIFICATION|"
                             r"PARTICULAR|CLASS RATING|SERVICE\s*(LIMIT|:)|PRESS\.|TEMP\.|BAR[gG]", c, re.I):
                    continue
                if re.search(r"S\s*I\s*Z\s*E|L\.?\s*SIZE|\(MTO\)|\(\s*NOTE\)|RANGE\)|SYMBOL|DESCRIPTION|PART NAME", c, re.I):
                    continue
                if re.fullmatch(r"(?:X\s*)+X", c, re.I) or c.upper() in ("REV", "SIZE"):
                    continue
                if _is_symbol(c):
                    flush()
                    rec = {"part": cur_part, "symbol": c, "sizes": [], "notes": [], "description": None}
                    pend_sym = None
                    continue
                if _is_note(c):
                    if rec:
                        rec["notes"].append(c)
                    continue
                if c in ("-", "- -", "--"):
                    continue
                if _is_size(c):
                    if rec is not None and rec["description"] is None:
                        rec["sizes"].append(c)
                    continue
                if _is_partname(c):
                    flush()
                    cur_part = re.sub(r"\s*\(.*?\)\s*", " ", c).strip()
                    sm = re.search(r"\(([0-9A-Za-z]{1,4})\)\s*$", c)
                    pend_sym = "(" + sm.group(1) + ")" if sm else None
                    continue
                if _is_desc(c):
                    if rec is None:
                        rec = {"part": cur_part, "symbol": pend_sym, "sizes": [], "notes": [], "description": None}
                    rec["description"] = ((rec["description"] or "") + " " + c).strip()
                    continue
                if rec is not None and rec.get("description"):
                    rec["description"] = (rec["description"] + " " + c).strip()
            flush()
        return comps

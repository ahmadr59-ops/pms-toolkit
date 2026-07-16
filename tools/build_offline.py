#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a single-file OFFLINE bundle of the web dashboard (or inject datapacks
into any other HTML tool, e.g. a standalone calculator).

Two jobs:
  1. Inline every local <script src="x.js"> of web/index.html into one HTML file.
  2. Embed datapacks as <script type="application/json" id="datapack-<name>">
     blocks, readable at runtime via loadEmbeddedDatapack() in web/rating.js.

Datapack preference per name: datapacks/<name>.json (private, real data) ->
examples/<name>.datapack.sample.json (synthetic). data/schedules.json and the
sample material master are embedded too so the bundle works with no server.

The output may contain YOUR licensed standard data - it is written to dist/
(git-ignored). NEVER commit or publish a bundle built from real datapacks.

Usage:
  python tools/build_offline.py                          # -> dist/pms-dashboard-offline.html
  python tools/build_offline.py --html path/to/tool.html # inject datapacks into another tool
  python tools/build_offline.py -o out.html
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = ("flanges", "flanges_b16_47", "fittings", "valves", "gaskets", "bolting", "materials")
CORE = {"schedules": os.path.join(ROOT, "data", "schedules.json"),
        "rules": os.path.join(ROOT, "rules", "conventions.json")}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def datapack_path(name):
    for p in (os.path.join(ROOT, "datapacks", f"{name}.json"),
              os.path.join(ROOT, "examples", f"{name}.datapack.sample.json")):
        if os.path.exists(p):
            return p
    return None


def datapack_blocks():
    blocks, used = [], []
    items = [(n, p, True) for n, p in CORE.items()]          # factual, public data
    items += [(n, datapack_path(n), None) for n in PACKS]
    for name, path, public in items:
        if not path or not os.path.exists(path):
            continue
        data = json.loads(_read(path))
        safe = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
        blocks.append(f'<script type="application/json" id="datapack-{name}">{safe}</script>')
        harmless = public or bool((data.get("meta") or {}).get("SYNTHETIC"))
        used.append((name, os.path.relpath(path, ROOT), harmless))
    return "\n".join(blocks), used


def inline_scripts(html, base_dir):
    def repl(m):
        src = m.group(1)
        p = os.path.join(base_dir, src)
        if not os.path.exists(p) or "://" in src:
            return m.group(0)
        js = _read(p).replace("</script>", "<\\/script>")
        return f"<script>/* inlined: {src} */\n{js}\n</script>"
    return re.sub(r'<script\s+src="([^"]+)"\s*>\s*</script>', repl, html)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--html", default=os.path.join(ROOT, "web", "index.html"),
                    help="HTML tool to bundle (default: web/index.html)")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "dist", "pms-dashboard-offline.html"))
    args = ap.parse_args()

    html = _read(args.html)
    html = inline_scripts(html, os.path.dirname(os.path.abspath(args.html)))
    blocks, used = datapack_blocks()
    marker = "<!-- OFFLINE DATAPACKS (auto-generated; may contain licensed data - do not publish) -->"
    inject = f"{marker}\n{blocks}\n"
    # strip a previous injection, then insert before the first script (or </head>)
    html = re.sub(re.escape(marker) + r".*?(?=<script(?! type=\"application/json\")|</head>)",
                  "", html, flags=re.S)
    anchor = html.find("<script")
    html = (html[:anchor] + inject + html[anchor:]) if anchor != -1 \
        else html.replace("</head>", inject + "</head>")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    real = [n for n, _, harmless in used if not harmless]
    print(f"wrote {args.out} ({os.path.getsize(args.out)//1024} KB)")
    for n, p, harmless in used:
        flag = "" if harmless else "   [REAL DATA - keep private]"
        print(f"  datapack {n:<10} <- {p}{flag}")
    if real:
        print("WARNING: bundle contains real (licensed) data - do not commit/publish it.",
              file=sys.stderr)


if __name__ == "__main__":
    main()

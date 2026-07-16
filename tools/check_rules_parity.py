#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-language parity gate: pmskit.rules (Python) vs web/rules.js (Node)
must emit identical findings for the same rule pack and inputs. Run in CI."""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pmskit.rules import run_conventions  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_rules_shadow import _cls  # noqa: E402

CASES = [
    _cls(), _cls(flange_rating_face="CL.350 RF"), _cls(flange_rating_face="CL.150"),
    _cls(flange_rating_face="CL.300 RTJ"), _cls(flange_rating_face="CL.300 FF"),
    _cls(corrosion_allowance=""),
    _cls(temp_C=["38","100","200"], press_barg=["19","17"]),
    _cls(press_barg=["17","19"]),
    _cls(components=[{"part":"GATE VALVE","description":"CL.2000 API 602"}]),
    _cls(component_count=0, components=[]),
]
fixture = os.path.join(ROOT, "tests", "fixtures", "sample_pms.json")
CASES.append(json.load(open(fixture, encoding="utf-8")))

def key(f):
    return json.dumps(f, sort_keys=True, default=str)

def main():
    py = [sorted(map(key, run_conventions(c))) for c in CASES]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(CASES, tf)
        cases_path = tf.name
    node_script = f'''
      const {{runRules}} = require({json.dumps(os.path.join(ROOT,"web","rules.js"))});
      const pack = require({json.dumps(os.path.join(ROOT,"rules","conventions.json"))});
      const cases = require({json.dumps(cases_path)});
      const out = cases.map(c => runRules(c, pack));
      console.log(JSON.stringify(out));
    '''
    js = json.loads(subprocess.check_output(["node", "-e", node_script], text=True))
    js = [sorted(map(key, findings)) for findings in js]
    bad = 0
    for i, (a, b) in enumerate(zip(py, js)):
        if a != b:
            bad += 1
            print(f"CASE {i}: MISMATCH\n  py={a}\n  js={b}")
    if bad:
        sys.exit(f"FATAL: {bad} case(s) diverge between Python and JS engines")
    print(f"parity OK: {len(CASES)} cases, Python == JS")

if __name__ == "__main__":
    main()

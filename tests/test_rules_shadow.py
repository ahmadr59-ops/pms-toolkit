# -*- coding: utf-8 -*-
"""Shadow-parity gate: the JSON rule engine must reproduce pmskit.validate
byte-for-byte on the fixtures AND on synthetic cases that exercise every rule
branch. The legacy engine stays the default until this stays green in CI."""
import json
import os

from pmskit.validate import validate_legacy as validate
from pmskit.rules import run_conventions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key(f):
    return (f["class"] or "", f["code"], f["severity"], f["message"],
            json.dumps(f["context"], sort_keys=True, default=str))


def assert_parity(data):
    old = sorted(validate(data), key=_key)
    new = sorted(run_conventions(data), key=_key)
    assert [_key(f) for f in old] == [_key(f) for f in new], (
        f"\nOLD={json.dumps(old, indent=1)}\nNEW={json.dumps(new, indent=1)}")


def test_parity_on_sample_fixture():
    with open(os.path.join(ROOT, "tests", "fixtures", "sample_pms.json"),
              encoding="utf-8") as f:
        assert_parity(json.load(f))


def _cls(**kw):
    base = {"class": "X1", "service": "", "main_material": "CS",
            "corrosion_allowance": "3.0 MM", "flange_rating_face": "CL.150 RF",
            "temp_C": ["38", "100"], "press_barg": ["19", "17"],
            "component_count": 1,
            "components": [{"part": "PIPE", "description": "SMLS BE"}]}
    base.update(kw)
    return {"classes": [base]}


def test_parity_every_branch():
    cases = [
        _cls(),                                                     # clean
        _cls(flange_rating_face="CL.350 RF"),                       # unknown class
        _cls(flange_rating_face="CL.150"),                          # facing missing
        _cls(flange_rating_face="CL.300 RTJ"),                      # RTJ low class
        _cls(flange_rating_face="CL.300 FF"),                       # FF high class
        _cls(corrosion_allowance=""),                               # CA missing
        _cls(temp_C=["38", "100", "200"], press_barg=["19", "17"]), # len mismatch
        _cls(press_barg=["17", "19"]),                              # not monotonic
        _cls(components=[{"part": "GATE VALVE",
                          "description": "CL.2000 API 602"}]),      # component CL note
        _cls(component_count=0, components=[]),                     # no components
        _cls(flange_rating_face=""),                                # no flange text
        _cls(temp_C=None, press_barg=None),                         # no PT arrays
        _cls(press_barg=["19", "abc"]),                             # unparsable P
        _cls(flange_rating_face="CL.125 FF"),                       # cast iron class ok
        _cls(components=[{"part": "FLANGE", "description": "WN CL.800"}]),  # 800 allowed
    ]
    for case in cases:
        assert_parity(case)
    # and all together in one document
    assert_parity({"classes": [c["classes"][0] for c in cases]})

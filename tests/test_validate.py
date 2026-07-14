import json, os
from pmskit.validate import validate, summarize

HERE = os.path.dirname(__file__)

def load(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return json.load(f)

def test_sample_has_no_errors():
    findings = validate(load("sample_pms.json"))
    assert summarize(findings)["error"] == 0

def test_detects_pt_length_mismatch():
    data = {"classes": [{"class": "X", "flange_rating_face": "CL.150 RF",
                         "temp_C": ["0", "100"], "press_barg": ["10"], "components": [], "component_count": 1}]}
    codes = {f["code"] for f in validate(data)}
    assert "PT_LENGTH_MISMATCH" in codes

def test_detects_non_monotonic_pt():
    data = {"classes": [{"class": "X", "flange_rating_face": "CL.150 RF",
                         "temp_C": ["0", "100"], "press_barg": ["10", "20"], "components": [], "component_count": 1}]}
    codes = {f["code"] for f in validate(data)}
    assert "PT_NOT_MONOTONIC" in codes

def test_detects_unknown_flange_class():
    data = {"classes": [{"class": "X", "flange_rating_face": "CL.175 RF", "components": [], "component_count": 1}]}
    codes = {f["code"] for f in validate(data)}
    assert "FLANGE_CLASS_UNKNOWN" in codes

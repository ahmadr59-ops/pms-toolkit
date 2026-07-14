from pmskit.compare import compare, nps

REF = {"meta": {"company": "REF"}, "classes": [{
    "class": "A1A1", "main_material": "CS", "flange_rating_face": "CL.150 RF",
    "corrosion_allowance": "3.0 MM", "temp_C": ["38"], "press_barg": ["19"],
    "components": [
        {"part": "PIPE", "size_from": "2", "size_to": "24", "description": "ASTM A106 GR.B SMLS BE ASME B36.10 SCH40"},
        {"part": "GATE VALVE", "size_from": "2", "size_to": "24", "description": "ASTM A216 WCB CL150 API600"},
    ], "component_count": 2}]}

def test_nps_parsing():
    assert nps("1/2") == 0.5
    assert nps("1 ½") == 1.5
    assert nps("1-1/2") == 1.5

def test_schedule_reduction_is_major():
    con = {"meta": {"company": "CON"}, "classes": [{
        "class": "A1A1", "main_material": "CS", "flange_rating_face": "CL.150 RF",
        "corrosion_allowance": "3.0 MM", "temp_C": ["38"], "press_barg": ["19"],
        "components": [
            {"part": "PIPE", "size_from": "2", "size_to": "24", "description": "ASTM A106 GR.B SMLS BE ASME B36.10 SCH30"},
            {"part": "GATE VALVE", "size_from": "2", "size_to": "24", "description": "ASTM A216 WCB CL150 API600"},
        ], "component_count": 2}]}
    res = compare(REF, con)
    pipe = [r for r in res["rows"] if r["component"] == "PIPE"][0]
    assert pipe["deviation"] == "Changed"
    assert pipe["severity"] == "major"
    assert "REDUCED" in pipe["remark"]

def test_removed_component_is_major():
    con = {"meta": {"company": "CON"}, "classes": [{
        "class": "A1A1", "main_material": "CS", "flange_rating_face": "CL.150 RF",
        "corrosion_allowance": "3.0 MM", "temp_C": ["38"], "press_barg": ["19"],
        "components": [
            {"part": "PIPE", "size_from": "2", "size_to": "24", "description": "ASTM A106 GR.B SMLS BE ASME B36.10 SCH40"},
        ], "component_count": 1}]}
    res = compare(REF, con)
    removed = [r for r in res["rows"] if r["deviation"] == "Removed"]
    assert any(r["component"] == "GATE VALVE" for r in removed)

def test_identical_pms_has_no_deviations():
    res = compare(REF, REF)
    assert res["summary"]["total"] == 0

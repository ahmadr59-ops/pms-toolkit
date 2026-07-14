from pmskit.specbuilder import build_spec, suggest_schedule
from pmskit.database import load_schedules, load_materials, find_material

def test_build_spec_produces_pipe_rows():
    out = build_spec(class_name="TST", material_spec="ASTM A106", grade="B",
                     service="HC", flange_rating_face="CL.150 RF", corrosion_allowance="3.0 MM",
                     temp_C=["38", "400"], press_barg=["19.6", "10.2"],
                     size_from="1/2", size_to="12")
    c = out["classes"][0]
    assert c["component_count"] >= 1
    assert all(x["part"] == "PIPE" for x in c["components"])

def test_higher_pressure_needs_thicker_schedule():
    sch = load_schedules(); mat = load_materials(); m = find_material(mat, "ASTM A106", "B")
    lo = suggest_schedule("8", [(38, 10)], m, ca=3.0, schedules=sch)
    hi = suggest_schedule("8", [(38, 80)], m, ca=3.0, schedules=sch)
    assert hi["required_mm"] > lo["required_mm"]

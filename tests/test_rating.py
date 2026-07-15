# -*- coding: utf-8 -*-
"""Tests for the P-T rating engine. Uses a small SYNTHETIC in-test datapack so
tests are hermetic; sample-datapack schema validation lives in
test_datapack_schemas.py."""
import pytest
from pmskit.rating import (find_group, rated_pressure, select_class,
                           flange_adequacy, load_flanges, load_component_pack)

PACK = {
    "meta": {"schema": "flange-master v1", "SYNTHETIC": True},
    "material_groups": [
        {"group": "1.1", "specs": ["A105", "A216 WCB", "A106 B"],
         "ratings": {
             "150": [[38, 19.0], [100, 17.0], [200, 13.0], [400, 6.0]],
             "300": [[38, 50.0], [100, 46.0], [200, 43.0], [400, 34.0]],
         }},
        {"group": "2.2", "specs": ["A182 F316", "A312 TP316"],
         "ratings": {"150": [[38, 19.0], [500, 6.0]]}},
    ],
}


def test_find_group_by_code_and_spec():
    assert find_group(PACK, "1.1")["group"] == "1.1"
    assert find_group(PACK, "ASTM A105")["group"] == "1.1"
    assert find_group(PACK, "CS / A216-WCB")["group"] == "1.1"
    assert find_group(PACK, "A312 TP316")["group"] == "2.2"
    assert find_group(PACK, "13Cr F6a") is None
    assert find_group(PACK, "") is None


def test_rated_pressure_interpolation():
    g = PACK["material_groups"][0]
    assert rated_pressure(g, 150, 38) == 19.0          # listed point
    assert rated_pressure(g, 150, 20) == 19.0          # below first temp -> constant
    assert rated_pressure(g, 150, 69) == pytest.approx(18.0, abs=1e-9)   # midpoint 38-100
    assert rated_pressure(g, 150, 300) == pytest.approx(9.5, abs=1e-9)   # midpoint 200-400
    assert rated_pressure(g, 150, 401) is None         # above last temp -> not rated
    assert rated_pressure(g, 600, 100) is None         # class not in pack
    assert rated_pressure(g, "150", 38) == 19.0        # class as str


def test_select_class():
    g = PACK["material_groups"][0]
    assert select_class(g, [(38, 19.0)]) == 150        # exactly at rating
    assert select_class(g, [(38, 19.1)]) == 300        # just above CL150
    assert select_class(g, [(100, 10.0), (400, 20.0)]) == 300   # hot point governs
    assert select_class(g, [(38, 60.0)]) is None       # beyond every listed class
    assert select_class(g, []) is None


def _pms(flange, material, temps, press):
    return {"classes": [{
        "class": "T1", "flange_rating_face": flange, "main_material": material,
        "temp_C": temps, "press_barg": press, "components": []}]}


def test_flange_adequacy_uses_sample_pack_via_loader(tmp_path):
    import json
    p = tmp_path / "flanges.json"
    p.write_text(json.dumps(PACK), encoding="utf-8")

    row = flange_adequacy(_pms("CL.150 RF", "A106 B", ["100"], ["10"]), str(p))[0]
    assert row["status"] == "adequate"
    assert row["material_group"] == "1.1"
    assert row["worst"]["rated_barg"] == 17.0
    assert row["margin_pct"] == 70.0

    row = flange_adequacy(_pms("CL.150 RF", "A106 B", ["200"], ["15"]), str(p))[0]
    assert row["status"] == "inadequate"
    assert row["suggested_class"] == 300

    # never a false pass:
    row = flange_adequacy(_pms("", "A106 B", ["100"], ["10"]), str(p))[0]
    assert row["status"] == "not-evaluated"
    row = flange_adequacy(_pms("CL.150 RF", "UNOBTANIUM", ["100"], ["10"]), str(p))[0]
    assert row["status"] == "not-evaluated"
    row = flange_adequacy(_pms("CL.150 RF", "A106 B", [], []), str(p))[0]
    assert row["status"] == "not-evaluated"
    row = flange_adequacy(_pms("CL.150 RF", "A106 B", ["450"], ["5"]), str(p))[0]
    assert row["status"] == "not-evaluated"          # above rated temp range


def test_loaders_prefer_private_pack_else_synthetic_sample():
    for name in ("flanges", "fittings", "valves", "gaskets", "bolting"):
        p = load_component_pack(name)
        assert p.get("meta"), name
        src = p["meta"].get("_source", "")
        if src.startswith("examples"):
            assert p["meta"].get("SYNTHETIC") is True, name
        else:
            assert src.startswith("datapacks"), name
    with pytest.raises(ValueError):
        load_component_pack("nope")


def test_norm_grade_class_markers():
    from pmskit.rating import _norm
    assert _norm("A350 Gr. LF2") == _norm("A350 LF2") == "A350LF2"
    assert _norm("A350 Gr. LF6 Cl. 1") == _norm("A350 LF6 Class 1") == "A350LF6CL1"
    assert _norm("A350 Gr. LF6 CI. 1") == "A350LF6CL1"   # source transcription typo
    assert _norm("A350 LF6 Cl. 1") != _norm("A350 LF6 Cl. 2")
    assert _norm("A182 Gr. F316") == _norm("A182-F316")


def test_real_b16_5_datapack_if_installed():
    """Runs only when the private B16.5 datapack is installed. Spot values are
    hand-read from the licensed ASME B16.5-2025 tables."""
    import os, pytest
    from pmskit.rating import _ROOT, rated_pressure
    if not os.path.exists(os.path.join(_ROOT, "datapacks", "flanges.json")):
        pytest.skip("no private flange datapack")
    pack = load_flanges()
    assert (pack["meta"].get("SYNTHETIC") is False and
            pack["meta"].get("standard") == "ASME B16.5")
    assert len(pack["material_groups"]) == 45
    g11 = find_group(pack, "A105")
    assert g11["group"] == "1.1"
    assert rated_pressure(g11, 150, 38) == 19.6      # Table 2-1.1
    assert rated_pressure(g11, 2500, 538) == 48.4    # Table 2-1.1
    assert rated_pressure(g11, 300, 225) == pytest.approx(42.9, abs=1e-9)  # midpoint 200-250
    assert rated_pressure(g11, 150, 600) is None     # above rated range
    assert find_group(pack, "A350 LF2")["group"] == "1.1"
    assert find_group(pack, "A182 F316")  is not None
    g27 = find_group(pack, "2.7")
    assert "150" not in g27["ratings"]               # 310H has no CL150 (per standard)

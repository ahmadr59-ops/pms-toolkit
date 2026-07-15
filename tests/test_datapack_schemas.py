# -*- coding: utf-8 -*-
"""Validate every shipped sample datapack against its JSON schema."""
import json
import os
import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS = [
    ("flanges", "flange-master"),
    ("fittings", "fitting-master"),
    ("valves", "valve-master"),
    ("gaskets", "gasket-master"),
    ("bolting", "bolting-master"),
]


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("pack,schema", PAIRS)
def test_sample_datapack_matches_schema(pack, schema):
    sample = _load(os.path.join(ROOT, "examples", f"{pack}.datapack.sample.json"))
    sch = _load(os.path.join(ROOT, "schema", "datapacks", f"{schema}.schema.json"))
    jsonschema.validate(sample, sch)
    assert sample["meta"].get("SYNTHETIC") is True, "shipped samples must be marked SYNTHETIC"


@pytest.mark.parametrize("pack,schema", PAIRS)
def test_private_datapack_matches_schema_if_present(pack, schema):
    """If the user has installed a real datapack locally, validate it too."""
    path = os.path.join(ROOT, "datapacks", f"{pack}.json")
    if not os.path.exists(path):
        pytest.skip("no private datapack installed")
    sch = _load(os.path.join(ROOT, "schema", "datapacks", f"{schema}.schema.json"))
    jsonschema.validate(_load(path), sch)


def test_flange_rating_monotonicity_of_samples():
    """Physical sanity: within a class, rated pressure must not increase with
    temperature (same convention the PMS validator uses)."""
    sample = _load(os.path.join(ROOT, "examples", "flanges.datapack.sample.json"))
    for g in sample["material_groups"]:
        for cls, curve in g["ratings"].items():
            temps = [t for t, _ in curve]
            press = [p for _, p in curve]
            assert temps == sorted(temps), f"group {g['group']} CL{cls}: temps not ascending"
            assert all(a >= b for a, b in zip(press, press[1:])), \
                f"group {g['group']} CL{cls}: pressure increases with temperature"

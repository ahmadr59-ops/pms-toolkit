import json, os
HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

def test_sample_matches_schema():
    import importlib.util
    if importlib.util.find_spec("jsonschema") is None:
        import pytest; pytest.skip("jsonschema not installed")
    import jsonschema
    with open(os.path.join(ROOT, "schema", "pms.schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    with open(os.path.join(HERE, "fixtures", "sample_pms.json"), encoding="utf-8") as f:
        data = json.load(f)
    jsonschema.validate(data, schema)

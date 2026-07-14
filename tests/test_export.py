import json, os, csv, io
from pmskit.export import flat_rows, to_csv

HERE = os.path.dirname(__file__)

def test_flat_rows_count():
    with open(os.path.join(HERE, "fixtures", "sample_pms.json"), encoding="utf-8") as f:
        data = json.load(f)
    rows = flat_rows(data)
    assert len(rows) == sum(c["component_count"] for c in data["classes"])

def test_csv_roundtrip(tmp_path):
    with open(os.path.join(HERE, "fixtures", "sample_pms.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = tmp_path / "o.csv"
    to_csv(data, str(out))
    text = out.read_text(encoding="utf-8-sig")
    reader = list(csv.reader(io.StringIO(text)))
    assert reader[0][0] == "class"
    assert len(reader) - 1 == len(flat_rows(data))

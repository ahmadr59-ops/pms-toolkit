from pmskit.normalize import normalize

def test_equivalent_descriptions_normalize_same():
    a = normalize("ASTM A234 GR.WPB SMLS LONG RADIUS BW AS PER ASME B16.9 SCH40")
    b = normalize("ASTM A234 WPB, BW, SMLS, LR, ASME B16.9 [SCH40]")
    for f in ("material", "grade", "end", "radius", "manuf", "rating_sch"):
        assert a[f] == b[f], f

def test_extracts_pipe_fields():
    n = normalize("ASTM A53 Gr.B, SMLS, PE, ASME B36.10M [SCH80]")
    assert n["material"] == "ASTM A53"
    assert n["grade"] == "B"
    assert n["end"] == "PE"
    assert n["manuf"] == "SMLS"
    assert n["rating_sch"] == "SCH80"

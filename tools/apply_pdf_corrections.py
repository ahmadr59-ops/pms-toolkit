#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply corrections transcribed from the user's original ASME PDF pages
(2026-07-15) to the private flange datapacks. Every value below was read
directly from the printed standard:

  B16.5-2025  Table 5 (pp. 114-120)  -> clean Ring-Joint mapping, grooves 11-81
  B16.47-2025 Table 41 (pp. 105-106) -> Class 600 Series B rows NPS 26-36
  B16.47-2025 Tables 36/40/41/42 General Note (h): NPS >= 38 Series B classes
              400/600/900 use the Series A dimensions; sizes printed '...' are
              not separately tabulated. A:900 covers 26-48 only (50-60 '...').
  B16.47-2025 Tables 21 & 27: the rating 'upticks' (G2.5 CL600 475C=63.7 then
              500C=64.4; G2.11 CL300 500C=34.1) are AS PRINTED -> flags become
              confirmations, data unchanged.
  B16.5-2025  Table 2-3.3 CL2500 350C=128.2 / 375C=128.3 as printed. Table 18
              first size rows are 1/2..1-1/4 (token repair confirmed).
              Table 1.1-1 'CI. 1' typo exists in the standard's own PDF text.

Run:  python tools/apply_pdf_corrections.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "user-supplied original PDF pages of the licensed standard, transcribed 2026-07-15"

# ---------------- B16.5 Table 5: Ring Joint mapping (cols 1-12) --------------
# (groove, {class: NPS}, P, E, F, R)   '(4)' kept verbatim where printed.
RTJ = [
 ("11",{"300":"1/2","600":"1/2"},34.14,5.56,7.14,0.8),
 ("12",{"1500":"1/2"},39.67,6.35,8.74,0.8),
 ("13",{"300":"3/4","600":"3/4","2500":"1/2"},42.88,6.35,8.74,0.8),
 ("14",{"1500":"3/4"},44.45,6.35,8.74,0.8),
 ("15",{"150":"1"},47.62,6.35,8.74,0.8),
 ("16",{"300":"1","600":"1","1500":"1","2500":"3/4"},50.80,6.35,8.74,0.8),
 ("17",{"150":"1-1/4"},57.15,6.35,8.74,0.8),
 ("18",{"300":"1-1/4","600":"1-1/4","1500":"1-1/4","2500":"1"},60.33,6.35,8.74,0.8),
 ("19",{"150":"1-1/2"},65.07,6.35,8.74,0.8),
 ("20",{"300":"1-1/2","600":"1-1/2","1500":"1-1/2"},68.28,6.35,8.74,0.8),
 ("21",{"2500":"1-1/4"},72.24,7.92,11.91,0.8),
 ("22",{"150":"2"},82.55,6.35,8.74,0.8),
 ("23",{"300":"2","600":"2","2500":"1-1/2"},82.55,7.92,11.91,0.8),
 ("24",{"1500":"2"},95.25,7.92,11.91,0.8),
 ("25",{"150":"2-1/2"},101.60,6.35,8.74,0.8),
 ("26",{"300":"2-1/2","600":"2-1/2","2500":"2"},101.60,7.92,11.91,0.8),
 ("27",{"1500":"2-1/2"},107.95,7.92,11.91,0.8),
 ("28",{"2500":"2-1/2"},111.12,9.53,13.49,1.5),
 ("29",{"150":"3"},114.30,6.35,8.74,0.8),
 ("30",{"300":"(4)","600":"(4)"},117.48,7.92,11.91,0.8),
 ("31",{"300":"3 (4)","600":"3 (4)","900":"3"},123.82,7.92,11.91,0.8),
 ("32",{"2500":"3"},127.00,9.53,13.49,1.5),
 ("33",{"150":"3-1/2"},131.78,6.35,8.74,0.8),
 ("34",{"300":"3-1/2","600":"3-1/2"},131.78,7.92,11.91,0.8),
 ("35",{"1500":"3"},136.52,7.92,11.91,0.8),
 ("36",{"150":"4"},149.22,6.35,8.74,0.8),
 ("37",{"300":"4","400":"4","600":"4","900":"4"},149.22,7.92,11.91,0.8),
 ("38",{"2500":"4"},157.18,11.13,16.66,1.5),
 ("39",{"1500":"4"},161.92,7.92,11.91,0.8),
 ("40",{"150":"5"},171.45,6.35,8.74,0.8),
 ("41",{"300":"5","400":"5","600":"5","900":"5"},180.98,7.92,11.91,0.8),
 ("42",{"2500":"5"},190.50,12.70,19.84,1.5),
 ("43",{"150":"6"},193.68,6.35,8.74,0.8),
 ("44",{"1500":"5"},193.68,7.92,11.91,0.8),
 ("45",{"300":"6","400":"6","600":"6","900":"6"},211.12,7.92,11.91,0.8),
 ("46",{"1500":"6"},211.14,9.52,13.49,1.5),
 ("47",{"2500":"6"},228.60,12.70,19.84,1.5),
 ("48",{"150":"8"},247.65,6.35,8.74,0.8),
 ("49",{"300":"8","400":"8","600":"8","900":"8"},269.88,7.92,11.91,0.8),
 ("50",{"1500":"8"},269.88,11.13,16.66,1.5),
 ("51",{"2500":"8"},279.40,14.27,23.01,1.5),
 ("52",{"150":"10"},304.80,6.35,8.74,0.8),
 ("53",{"300":"10","400":"10","600":"10","900":"10"},323.85,7.92,11.91,0.8),
 ("54",{"1500":"10"},323.85,11.13,16.66,1.5),
 ("55",{"2500":"10"},342.90,17.48,30.18,2.3),
 ("56",{"150":"12"},381.00,6.35,8.74,0.8),
 ("57",{"300":"12","400":"12","600":"12","900":"12"},381.00,7.92,11.91,0.8),
 ("58",{"1500":"12"},381.00,14.27,23.01,1.5),
 ("59",{"150":"14"},396.88,6.35,8.74,0.8),
 ("60",{"2500":"12"},406.40,17.48,33.32,2.3),
 ("61",{"300":"14","400":"14","600":"14"},419.10,7.92,11.91,0.8),
 ("62",{"900":"14"},419.10,11.13,16.66,1.5),
 ("63",{"1500":"14"},419.10,15.88,26.97,2.3),
 ("64",{"150":"16"},454.02,6.35,8.74,0.8),
 ("65",{"300":"16","400":"16","600":"16"},469.90,7.92,11.91,0.8),
 ("66",{"900":"16"},469.90,11.13,16.66,1.5),
 ("67",{"1500":"16"},469.90,17.48,30.18,2.3),
 ("68",{"150":"18"},517.52,6.35,8.74,0.8),
 ("69",{"300":"18","400":"18","600":"18"},533.40,7.92,11.91,0.8),
 ("70",{"900":"18"},533.40,12.70,19.84,1.5),
 ("71",{"1500":"18"},533.40,17.48,30.18,2.3),
 ("72",{"150":"20"},558.80,6.35,8.74,0.8),
 ("73",{"300":"20","400":"20","600":"20"},584.20,9.52,13.49,1.5),
 ("74",{"900":"20"},584.20,12.70,19.84,1.5),
 ("75",{"1500":"20"},584.20,17.48,33.32,2.3),
 ("80",{"150":"22"},615.95,6.35,8.74,0.8),
 ("81",{"300":"22","400":"22","600":"22"},635.00,11.13,15.09,1.5),
 ("76",{"150":"24"},673.10,6.35,8.74,0.8),
 ("77",{"300":"24","400":"24","600":"24"},692.15,11.13,16.66,1.5),
 ("78",{"900":"24"},692.15,15.88,26.97,2.3),
 ("79",{"1500":"24"},692.15,20.62,36.53,2.3),
]
RTJ_NOTES = ("NOTES (verbatim): (1) The height of the raised portion is equal to the depth "
 "of the groove dimension, E, but is not subjected to the tolerances for E. Former "
 "full-face contour may be used. (2) Use Class 600 in sizes NPS 1/2 to NPS 3-1/2 for "
 "Class 400. (3) Use Class 1500 in sizes NPS 1/2 to NPS 2-1/2 for Class 900. "
 "(4) For ring joints with lapped flanges in Classes 300 and 600, ring and groove "
 "number R30 is used instead of R31. TOLERANCES: E +0.41/-0.00 mm; F +/-0.20 mm; "
 "P +/-0.13 mm; R<=1.5: +0.8/-0.0 mm, R>1.5: +/-0.8 mm; 23 deg angle +/- 1/2 deg. "
 "Columns 13-24 of Table 5 (Diameter of Raised Portion K, Approximate Distance "
 "Between Flanges) are in the source PDF but intentionally not digitized.")

# ---------------- B16.47 Table 41: Class 600 Series B, NPS 26-36 -------------
T41_COLS = ["O.D. of Flange, O",
            "Minimum Thickness of Flange, tf [Note (1)] Weld Neck Flange",
            "Minimum Thickness of Flange, tf [Note (1)] Blind Flange",
            "Length Through Hub, Y", "Diam. of Hub, X [Note (2)]",
            "Hub Diam. Top, A [Note (3)]", "Raised Face Diam., R",
            "Drilling Diam. of Bolt Circle", "Drilling No. of Bolt Holes",
            "Drilling Diam. of Bolt Hole, in.", "Diam. of Bolt, in.",
            "Minimum Fillet Radius, r1",
            "Length of Bolts, L [Notes (4), (5)] Stud Bolts Raised Face 6.4 mm"]
T41_ROWS = [
 ("26",[889,111.3,111.3,181,698,660.4,727,806.4,28,"1-3/4","1-5/8",13,360]),
 ("28",[952,115.8,115.8,190,752,711.2,784,863.6,28,"1-7/8","1-3/4",13,375]),
 ("30",[1022,125.5,127.0,205,806,762.0,841,927.1,28,"2","1-7/8",13,395]),
 ("32",[1086,130.0,134.9,216,861,812.8,895,984.2,28,"2-1/8","2",13,415]),
 ("34",[1162,141.2,144.3,233,914,863.6,952,1054.1,24,"2-3/8","2-1/4",14,440]),
 ("36",[1213,146.0,150.9,243,968,914.4,1010,1104.9,28,"2-3/8","2-1/4",14,460]),
]
NOTE_H = ("General Note (h), verbatim: Dimensions for Classes 400, 600, and 900 NPS 38 "
          "and larger for Series B flanges are the same as for the Series A flanges.")


def main():
    # ---- B16.5 pack: replace ring_joints ------------------------------------
    p5 = os.path.join(ROOT, "datapacks", "flanges.json")
    pack = json.load(open(p5, encoding="utf-8"))
    rows = []
    for g, cls_nps, P, E, F, R in RTJ:
        vals = {f"NPS for Class {c}": n for c, n in sorted(cls_nps.items(), key=lambda x: int(x[0]))}
        vals.update({"Pitch Diameter, P": P, "Depth, E [Note (1)]": E,
                     "Width, F": F, "Radius at Bottom, R": R})
        rows.append({"groove_no": f"R{g}", "values": vals})
    pack["ring_joints"] = {"source_table": "Table 5", "keyed_by": "groove_no",
                           "source": SRC, "rows": rows, "notes": RTJ_NOTES}
    pack["meta"]["verify_flags"] = [
        {"item": "Table 2-3.3 CL2500 350C=128.2 -> 375C=128.3",
         "status": "CONFIRMED as printed in the standard (PDF checked)"},
        {"item": "Table 18 first size rows 1/2..1-1/4 (token '14' repaired to 1/2)",
         "status": "CONFIRMED against PDF"},
        {"item": "Table 1.1-1 'A350 Gr. LF6 CI. 1' transcription",
         "status": "the 'CI.' typo exists in the standard's own PDF text layer; "
                   "matching layer handles it"}]
    json.dump(pack, open(p5, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n5 = len(rows)

    # ---- B16.47 pack: T41 rows + Note (h) cross-references ------------------
    p47 = os.path.join(ROOT, "datapacks", "flanges_b16_47.json")
    pk = json.load(open(p47, encoding="utf-8"))
    d = pk["dims"]

    d["B:600"]["columns"] = T41_COLS
    d["B:600"]["rows"] = [
        {"nps": nps, "values": dict(zip(T41_COLS, vals))} for nps, vals in T41_ROWS]
    d["B:600"]["source"] = SRC
    d["B:600"].pop("DAMAGED_SOURCE", None)

    for key in ("B:400", "B:600", "B:900"):
        d[key].pop("DAMAGED_SOURCE", None)
        d[key]["nps_38_and_larger"] = ("use Series A dimensions per General Note (h); "
                                       "printed '...' in this table. " + NOTE_H)
        d[key]["cross_reference"] = f"A:{d[key]['class']}"
    d["A:900"].pop("DAMAGED_SOURCE", None)
    d["A:900"]["coverage_note"] = ("NPS 26-48 only; 50-60 are printed '...' (not "
                                   "tabulated) in the standard - confirmed from PDF.")
    pk["meta"]["verify_flags"] = [
        {"item": "Group 2.5 CL600: 475C=63.7 then 500C=64.4",
         "status": "CONFIRMED as printed in Table 21 of the standard (PDF checked); "
                   "kept verbatim"},
        {"item": "Group 2.11 CL300: 475C=33.4 then 500C=34.1",
         "status": "CONFIRMED as printed in Table 27 of the standard (PDF checked); "
                   "kept verbatim"}]
    json.dump(pk, open(p47, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"B16.5 ring_joints: {n5} grooves (clean mapping, PDF-transcribed)")
    print(f"B16.47 B:600: {len(T41_ROWS)} rows added; DAMAGED flags cleared; "
          f"Note (h) cross-references recorded")


if __name__ == "__main__":
    main()

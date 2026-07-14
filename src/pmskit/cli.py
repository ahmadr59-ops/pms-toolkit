# -*- coding: utf-8 -*-
"""pmskit command-line interface.

Examples
--------
  pmskit parse INPUT.doc -o out.json --company NIOEC
  pmskit validate out.json
  pmskit export out.json --csv out.csv --xlsx out.xlsx
  pmskit report out.json
  pmskit adapters
"""
from __future__ import annotations
import argparse
import json
import sys

from . import __version__
from .adapters import get_adapter, list_adapters
from .export import to_json, to_csv, to_xlsx
from .report import coverage_report, format_report
from .validate import validate, summarize
from .compare import compare
from .deviation_export import to_deviation_xlsx
from .thickness import required_thickness, y_coefficient
from .compliance import check_pms
from .specbuilder import build_spec


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_parse(a):
    adapter = get_adapter(a.adapter)
    data = adapter.parse(a.input, company=a.company)
    to_json(data, a.output)
    rep = coverage_report(data)
    print(f"Parsed with adapter '{adapter.name}' -> {a.output}")
    print(format_report(rep))
    return 0


def cmd_validate(a):
    data = _load(a.input)
    findings = validate(data)
    s = summarize(findings)
    for f in findings:
        if a.severity == "all" or f["severity"] == a.severity:
            print(f"[{f['severity'].upper():7}] {f['class'] or '-':10} {f['code']}: {f['message']}")
    print(f"\n{s['error']} error(s), {s['warning']} warning(s), {s['info']} info")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fp:
            json.dump(findings, fp, ensure_ascii=False, indent=1)
    return 1 if s["error"] else 0


def cmd_export(a):
    data = _load(a.input)
    if a.csv:
        to_csv(data, a.csv); print(f"CSV  -> {a.csv}")
    if a.xlsx:
        to_xlsx(data, a.xlsx); print(f"XLSX -> {a.xlsx}")
    if a.json:
        to_json(data, a.json); print(f"JSON -> {a.json}")
    if not (a.csv or a.xlsx or a.json):
        print("Nothing to export: pass --csv/--xlsx/--json", file=sys.stderr); return 2
    return 0


def cmd_report(a):
    print(format_report(coverage_report(_load(a.input))))
    return 0


def cmd_adapters(a):
    for name, label in list_adapters().items():
        print(f"{name:10} {label}")
    return 0


def cmd_deviation(a):
    ref = _load(a.reference)
    con = _load(a.contractor)
    result = compare(ref, con, include_equal=a.include_equal)
    s = result["summary"]
    print(f"Baseline (reference): {result['meta']['reference']}  |  Contractor: {result['meta']['contractor']}")
    print(f"{s['total']} deviations: {s['major']} major, {s['minor']} minor, {s['info']} info "
          f"(Added {s['added']}, Removed {s['removed']}, Changed {s['changed']})")
    if a.xlsx:
        project = {}
        for kv in (a.meta or []):
            if "=" in kv:
                k, v = kv.split("=", 1); project[k] = v
        to_deviation_xlsx(result, a.xlsx, project)
        print(f"Deviation list -> {a.xlsx}")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fp:
            json.dump(result, fp, ensure_ascii=False, indent=1)
        print(f"JSON -> {a.json_out}")
    return 0


def cmd_thickness(a):
    Y = a.Y if a.Y is not None else y_coefficient(a.family, a.temp)
    r = required_thickness(a.pressure, a.od, a.stress, E=a.E, W=a.W, Y=Y,
                           c_mm=a.allowance, mill_tol=a.mill_tol)
    print(f"ASME B31.3 304.1.2  |  P={a.pressure} barg  D={a.od} mm  S={a.stress} MPa  "
          f"E={a.E} W={a.W} Y={Y}  c={a.allowance} mm  mill_tol={a.mill_tol}")
    print(f"  pressure design thickness t   = {r['t_pressure_design_mm']} mm")
    print(f"  + allowances (t + c)          = {r['t_min_with_allowances_mm']} mm")
    print(f"  nominal wall to order (T)     = {r['T_nominal_to_order_mm']} mm")
    return 0


def cmd_check(a):
    data = _load(a.input)
    res = check_pms(data, datapack=a.datapack, E=a.E, W=a.W, mill_tol=a.mill_tol)
    s = res["summary"]
    if s.get("synthetic_stress"):
        print("WARNING: using SYNTHETIC demo allowable-stress values "
              f"({s.get('materials_source')}). Provide datapacks/materials.json for real results.\n")
    for r in res["rows"]:
        if a.only_flagged and r["status"] not in ("UNDER-THICKNESS",):
            continue
        print(f"[{r['status']:15}] {r['class']:10} {str(r['size']):6} {str(r['schedule'] or '-'):6} "
              f"req={r['required_mm']} act={r['actual_wall_mm']} margin={r['margin_mm']}")
    print(f"\nB31.3 schedule check: {s['ok']} OK, {s['under']} UNDER-THICKNESS, {s['not_evaluated']} not-evaluated "
          f"(of {s['total']})")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fp:
            json.dump(res, fp, ensure_ascii=False, indent=1)
        print(f"JSON -> {a.json_out}")
    return 1 if s["under"] else 0


def cmd_build_spec(a):
    out = build_spec(class_name=a.name, material_spec=a.material, grade=a.grade,
                     service=a.service, flange_rating_face=a.flange,
                     corrosion_allowance=a.ca, temp_C=a.temp, press_barg=a.press,
                     size_from=a.size_from, size_to=a.size_to, end=a.end,
                     datapack=a.datapack, E=a.E, W=a.W, mill_tol=a.mill_tol,
                     company=a.company)
    c = out["classes"][0]
    if out["meta"].get("synthetic_stress"):
        print("WARNING: SYNTHETIC demo stresses used. Provide a real datapack for engineering use.\n")
    print(f"Class {c['class']}  ({c['main_material']}, {c['flange_rating_face']})")
    for x in c["components"]:
        print(f"  {x['size_from']:>5} - {x['size_to']:<5}  {x['description']}")
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"\nJSON -> {a.output}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="pmskit", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"pms-toolkit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parse", help="Parse a company PMS document into canonical JSON")
    sp.add_argument("input"); sp.add_argument("-o", "--output", default="pms.json")
    sp.add_argument("--adapter", default="nioec"); sp.add_argument("--company", default=None)
    sp.set_defaults(func=cmd_parse)

    sv = sub.add_parser("validate", help="Run rule-based consistency checks")
    sv.add_argument("input"); sv.add_argument("--severity", default="all",
                                              choices=["all", "error", "warning", "info"])
    sv.add_argument("--json-out", default=None)
    sv.set_defaults(func=cmd_validate)

    se = sub.add_parser("export", help="Export JSON to CSV / XLSX / JSON")
    se.add_argument("input"); se.add_argument("--csv"); se.add_argument("--xlsx"); se.add_argument("--json")
    se.set_defaults(func=cmd_export)

    sr = sub.add_parser("report", help="Print a coverage report")
    sr.add_argument("input"); sr.set_defaults(func=cmd_report)

    sa = sub.add_parser("adapters", help="List available company adapters")
    sa.set_defaults(func=cmd_adapters)

    sd = sub.add_parser("deviation", help="Compare Reference vs Contractor PMS -> deviation list")
    sd.add_argument("reference", help="Reference (baseline) pms.json")
    sd.add_argument("contractor", help="Contractor pms.json")
    sd.add_argument("--xlsx", help="Write standard Deviation List .xlsx")
    sd.add_argument("--json-out", help="Write raw deviation result .json")
    sd.add_argument("--include-equal", action="store_true", help="Include equivalent rows")
    sd.add_argument("--meta", nargs="*", help="Project metadata k=v (project, doc_no, rev, date, title)")
    sd.set_defaults(func=cmd_deviation)

    st = sub.add_parser("thickness", help="ASME B31.3 pressure-design wall thickness (single calc)")
    st.add_argument("--pressure", type=float, required=True, help="internal design pressure, barg")
    st.add_argument("--od", type=float, required=True, help="pipe outside diameter, mm")
    st.add_argument("--stress", type=float, required=True, help="allowable stress S at design temp, MPa")
    st.add_argument("--temp", type=float, default=38, help="design temperature, C (for Y)")
    st.add_argument("--family", default="ferritic", help="ferritic|austenitic (for Y)")
    st.add_argument("--E", type=float, default=1.0); st.add_argument("--W", type=float, default=1.0)
    st.add_argument("--Y", type=float, default=None, help="override Y coefficient")
    st.add_argument("--allowance", type=float, default=0.0, help="mechanical allowances c, mm")
    st.add_argument("--mill-tol", dest="mill_tol", type=float, default=0.125)
    st.set_defaults(func=cmd_thickness)

    sc = sub.add_parser("check", help="B31.3 schedule-adequacy check over a pms.json (needs material datapack)")
    sc.add_argument("input")
    sc.add_argument("--datapack", default=None, help="path to materials datapack json")
    sc.add_argument("--E", type=float, default=1.0); sc.add_argument("--W", type=float, default=1.0)
    sc.add_argument("--mill-tol", dest="mill_tol", type=float, default=0.125)
    sc.add_argument("--only-flagged", action="store_true", help="show only UNDER-THICKNESS rows")
    sc.add_argument("--json-out", default=None)
    sc.set_defaults(func=cmd_check)

    sb = sub.add_parser("build-spec", help="Propose a pipe class from design conditions (B31.3)")
    sb.add_argument("--name", required=True, help="new class code, e.g. A1B1")
    sb.add_argument("--material", required=True, help="material spec, e.g. 'ASTM A106'")
    sb.add_argument("--grade", default=None)
    sb.add_argument("--service", default="")
    sb.add_argument("--flange", required=True, help="flange rating & face, e.g. 'CL.150 RF'")
    sb.add_argument("--ca", default="0 MM", help="corrosion allowance, e.g. '3.0 MM'")
    sb.add_argument("--temp", nargs="+", required=True, help="design temperatures (C)")
    sb.add_argument("--press", nargs="+", required=True, help="allowable pressures (barg), same order")
    sb.add_argument("--size-from", dest="size_from", required=True)
    sb.add_argument("--size-to", dest="size_to", required=True)
    sb.add_argument("--end", default="BE")
    sb.add_argument("--datapack", default=None)
    sb.add_argument("--E", type=float, default=1.0); sb.add_argument("--W", type=float, default=1.0)
    sb.add_argument("--mill-tol", dest="mill_tol", type=float, default=0.125)
    sb.add_argument("--company", default="SPEC-BUILDER")
    sb.add_argument("-o", "--output", default=None)
    sb.set_defaults(func=cmd_build_spec)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

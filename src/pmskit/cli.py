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
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

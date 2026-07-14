# pms-toolkit

[![CI](https://github.com/ahmadr59-ops/pms-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmadr59-ops/pms-toolkit/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Parse, validate and explore Piping Material Specifications (PMS) as open JSON.**

🔗 **Live dashboard demo:** https://ahmadr59-ops.github.io/pms-toolkit/ (synthetic sample data)

A PMS is the document that tells piping engineers which material, standard, schedule
and rating to use for every component in every pipe class. They are usually large,
table-heavy Word or Excel documents that are painful to search or reuse. `pms-toolkit`
turns a PMS into a clean, queryable **[Open PMS Schema](schema/README.md)** JSON — plus a
CLI, a rule-based validator, and a zero-dependency web dashboard.

> ⚠️ **Data notice.** A company's PMS is normally its proprietary/copyrighted document.
> This repository ships **only synthetic sample data**. Generate JSON from your own PMS
> locally; do not commit company PMS files or extracted data to a public repo.

## Features

- **Multiple source formats** — binary Word `.doc` and Excel `.xls`, via pluggable *adapters*.
- **Open schema** — one company-neutral JSON shape; company quirks live in adapters.
- **Validator** — consistency checks against standard engineering *conventions*
  (flange classes, facings, schedules, P–T monotonicity). **No copyrighted ASME/API
  tables are used or reproduced.**
- **Deviation list** — compare a Reference (baseline) PMS vs a Contractor PMS and produce a standard, consultant-style deviation list (Excel).
- **Exports** — JSON / CSV / XLSX.
- **Dashboard** (`web/`) — Overview, Explorer, Validate, Schema/JSON, Export, drag-drop Import.
  Static; deployable free to GitHub Pages.

## Supported PMS sources (adapters)

| Adapter | Company | Input |
|---------|---------|-------|
| `nioec` | NIOEC | Word binary `.doc` |
| `borc`  | BORC (Bandar Abbas Refinery) | Excel `.xls` |

Each company's layout lives in its own adapter; add a new one by following
[`docs/adapters.md`](docs/adapters.md). List them anytime with `pmskit adapters`.

## Install

```bash
pip install -e ".[xls,xlsx]"     # xls = read .xls (BORC), xlsx = write .xlsx
```

## CLI

```bash
# 1) Parse your PMS document into canonical JSON
pmskit parse "YourCompany PMS.doc" --adapter nioec --company YourCo -o pms.json
pmskit parse "BORC PMS.xls"        --adapter borc  --company BORC   -o borc.json

# 2) Check consistency
pmskit validate pms.json

# 3) Export
pmskit export pms.json --csv pms.csv --xlsx pms.xlsx

# Other
# Compare Reference (baseline) vs Contractor -> standard deviation list
pmskit deviation reference.json contractor.json --xlsx deviation.xlsx \
        --meta project="My Project" doc_no=PMS-DEV-001 rev=A

pmskit report pms.json      # coverage / confidence
pmskit adapters             # list available company adapters
```

## Dashboard

The dashboard is a static site in `web/`. Two ways to use it:

- **Locally:** `python -m http.server -d web` then open <http://localhost:8000>.
  Put your `pms.json` at `web/data/pms.json`, or use **Import JSON** / drag-drop.
- **GitHub Pages:** the included workflow publishes `web/` automatically. Keep the
  demo data synthetic.

## How it works

```
company .doc/.xls → adapter → pms.json (schema) → valida
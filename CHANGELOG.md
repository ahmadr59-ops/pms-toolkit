# Changelog

## 0.8.0 — 2026-07-16 — Standards datapacks + Rule Engine
- **ASME B16.34-2025 valves datapack** (`tools/b16_34_extract.py`): all 50
  material groups, 11,774 rating points, Standard + Special Class up to
  CL4500; body wall-thickness Table 3A and Table 4 verbatim. Engine-compatible
  shape; Flange Rating tab gained a B16.34 selector. Print anomalies (G2.8
  Special<Standard points, 4 monotonic upticks) confirmed against the PDF and
  listed in meta.verify_flags.
- **ASME B16.20-2023 + B16.21-2021 gaskets datapack**
  (`tools/b16_20_21_extract.py` + `_refine.py`): 19 structured tables (~350
  keyed rows) - Type R/RX/BX ring dimensions, spiral-wound OD/ID/centering and
  inner-ring tables for B16.5 & B16.47 A/B, kammprofile, and B16.21 flat-ring/
  full-face tables incl. CL150 bolting data; irregular tables kept verbatim
  and flagged. New **Gaskets** dashboard tab.
- **ASME B16.5-2025 dimension data** merged into the flange datapack:
  drilling/bolting charts (incl. stud lengths), flange dimensions for all 7
  classes, facings, ring-joint mapping (71 grooves, PDF-transcribed after the
  source-export audit). **Dimensions & bolting chart** panel in the Flange
  Rating tab.
- **PDF corrections workflow** (`tools/apply_pdf_corrections.py`,
  `B16-issues-for-PDF.xlsx`): every extraction ambiguity was resolved against
  the printed standard and either fixed or confirmed-verbatim with flags -
  nothing silently guessed.
- **Fittings tab** in the dashboard: B16.9 / B16.11 dimension lookup by table
  and size (dual-unit display, printed blanks and round-off notes surfaced).
- **Rule engine is now the default validate path** (Python wrapper with
  PMSKIT_LEGACY_VALIDATE=1 escape hatch; web Validate tab runs rules/
  conventions.json when available, built-in checks otherwise; offline bundle
  embeds the rule pack). Parity gates stay in CI.
- **JSON Rule Engine (rule-master v1, shadow mode)**: declarative rules in
  `rules/conventions.json`, mirrored engines `pmskit/rules.py` + `web/rules.js`
  (no eval; tiny structured condition dialect). Legacy `pmskit.validate` stays
  the default behind two parity gates: `tests/test_rules_shadow.py`
  (old==new, every branch) and `tools/check_rules_parity.py` (Python==JS).
- **ASME B16.9-2018 + B16.11-2016 fittings datapack** (`datapacks/fittings.json`):
  B16.9 - 11 dimension tables, 611 rows, dual-unit values with a 25.4 mm/in
  cross-check on every pair; B16.11 - 6 metric tables (coordinate-verified) +
  correlation tables verbatim. Extractors: `tools/b16_9_extract.py`,
  `tools/b16_11_extract.py`.
- **ASME B16.47-2025 datapack** (`tools/b16_47_extract.py` -> git-ignored
  `datapacks/flanges_b16_47.json`): 27 material groups (2,975 rating points,
  classes 75-900), Series A/B dimension+drilling tables (NPS 26-60), RTJ
  facings keyed by groove number, verbatim bolting sections. Damaged source
  pages are flagged `DAMAGED_SOURCE` (never silently dropped) and rating
  anomalies are listed in `meta.verify_flags`. Flange Rating tab gained a
  B16.5 / B16.47 standard selector.
- **Five component datapack formats** with JSON Schemas (`schema/datapacks/`) and
  synthetic samples (`examples/`): flanges (B16.5 P–T ratings + dimensions +
  bolting chart), fittings (B16.9/B16.11/MSS SP-97), valves (selection matrix +
  B16.10 face-to-face), gaskets (B16.20/B16.21), bolting (A193/A194/A320 +
  NACE alternatives + PCC-1 torque). Real values stay in git-ignored `datapacks/`.
- **P–T rating engine** (`pmskit.rating` + `web/rating.js` mirror): group
  resolution from material text, class rating interpolation, smallest-adequate-
  class selection, and per-pipe-class flange-rating adequacy check
  (`flange_adequacy`, never a false pass).
- **Offline bundler** `tools/build_offline.py`: single-file dashboard bundle with
  local datapacks embedded (`dist/`, git-ignored) — supports the dual
  offline/online workflow.

## 0.7.0
- Standalone **Compliance** dashboard tab (moved out of Thickness): run the B31.3
  schedule-adequacy check over the whole PMS, filter, export CSV.
- Formatted B31.3 compliance **Excel** report (title block, project meta, colored status)
  via `pmskit check pms.json --xlsx report.xlsx --meta project=... rev=...`.
- Thickness tab is now a focused single-calculation tool.

## 0.6.1
- `pmskit import-stress` (and standalone tools/calc_to_datapack.py): convert a local
  B31.3 calculator's material table into a materials.json datapack in one step.

## 0.6.0
- Dashboard onboarding: "Get started" modal — Use sample data | Load my data.
- Load-my-data shows PMS (required) + material stress data (optional) with checkmarks; Run when ready.
- Header "Import JSON" replaced by a persistent "Data" button that reopens the modal.
- Loaded stress data flows straight into Thickness & Spec Builder. Deviation keeps its own two-slot import.

## 0.5.0
- Spec Builder: propose a pipe class from design conditions — minimum adequate schedule per size via ASME B31.3.
- CLI `pmskit build-spec`; dashboard **Spec Builder** tab (form -> proposed class -> download JSON / add to loaded PMS).

## 0.4.0
- Shared engineering database: pipe schedule dimensions (data/schedules.json) + material master.
- ASME B31.3 wall-thickness engine (pmskit.thickness) — code method only, no copyrighted stress tables.
- Schedule-adequacy compliance check (pmskit.check) over a PMS, using a material datapack.
- Private datapack model for copyrighted allowable-stress values (git-ignored); synthetic demo fallback.
- CLI: `pmskit thickness` and `pmskit check`.
- Dashboard: **Thickness** tab (single calc + B31.3 schedule check on the loaded PMS).

## 0.3.0
- Deviation engine: compare a Reference (baseline) PMS vs a Contractor PMS.
- Description normalizer so comparison is on engineering fields, not raw wording.
- Standard Deviation List
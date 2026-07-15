# Changelog

## Unreleased (0.8.0 — component datapacks, Phase 0)
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
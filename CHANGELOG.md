# Changelog

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
- Standard Deviation List Excel export (consultant format) + `pmskit deviation` CLI.
- Dashboard: two-slot **Deviation** tab (Reference/Contractor) with severity filter and CSV export.
- Shared-database skeleton (data/materials.json, data/schedules.json); private datapacks gitignored.

## 0.2.0
- Add `borc` adapter: parse BORC (Bandar Abbas Refinery) Excel (.xls) PMS.
- Header extraction tolerant of merged-cell column drift.
- `xls` optional dependency (xlrd).

## 0.1.0
- Initial release.
- `doc_parser`: direct OLE `.doc` piece-table text extraction.
- `nioec` adapter: parse NIOEC PMS into the Open PMS Schema.
- `validate`: rule-based consistency checks (no copyrighted tables).
- `export`: JSON / CSV / XLSX.
- CLI: `parse`, `validate`, `export`, `report`, `adapters`.
- Static dashboard (`web/`): Overview, Explorer, Validate, Schema/JSON, Export, Import.
- Open PMS Schema (JSON Schema draft-07) + synthetic sample.

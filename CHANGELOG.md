# Changelog

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

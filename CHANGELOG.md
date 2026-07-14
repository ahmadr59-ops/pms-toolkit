# Changelog

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

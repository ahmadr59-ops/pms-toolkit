# Architecture

```
                 ┌──────────────┐
  company .doc ─▶│ doc_parser   │  OLE WordDocument piece-table → text
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │ adapter      │  company layout → canonical dict
                 │ (nioec, …)   │
                 └──────┬───────┘
                        ▼
        ┌───────────────┼────────────────┐
        ▼               ▼                 ▼
   pms.json        validate           export (csv/xlsx)
   (schema)      (rule checks)
        ▼
   web/ dashboard (Overview · Explorer · Validate · Schema · Export · Import)
```

- **`doc_parser`** — format-level extraction only; no business logic.
- **`adapters/`** — the only place with company-specific heuristics.
- **`validate`** — deterministic, standards-*convention* checks. No copyrighted tables.
- **`export`** — JSON / CSV / XLSX from the canonical shape.
- **`web/`** — static, dependency-free dashboard; deployable to GitHub Pages.

## Why parse the binary `.doc` directly?

The source PMS is a 36 MB, 850-page Word 97-2003 `.doc`. Converting it with
LibreOffice is slow and heavy. Instead `doc_parser` reads the OLE `WordDocument`
stream's piece table and reconstructs cell/paragraph structure from the control
marks (`0x07` cell, `0x0D` paragraph). This is fast and has no external runtime
dependency beyond `olefile`.

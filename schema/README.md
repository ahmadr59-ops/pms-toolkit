# Open PMS Schema

A canonical, company-agnostic data model for a **Piping Material Specification (PMS)**.
The goal is a single, portable JSON shape that any owner's or EPC's PMS can be mapped
into — so tools, scripts, and dashboards can consume PMS data without caring which
company issued it.

- Machine-readable spec: [`pms.schema.json`](./pms.schema.json) (JSON Schema draft-07)
- Reference implementation: the `pmskit` package and the `web/` dashboard in this repo.

## Top level

```jsonc
{
  "meta":   { "company": "…", "class_count": 3, "units": { … } },
  "classes": [ PipeClass, … ]
}
```

## PipeClass

| Field | Type | Meaning |
|------|------|---------|
| `class` | string | Pipe/line class code, e.g. `A1A1`, `CS150` |
| `service` | string | Fluid service(s) |
| `main_material` | string | Base material family, e.g. `CS`, `SS316`, `1-1/4CR-0.5MO` |
| `corrosion_allowance` | string | e.g. `3.0 MM` |
| `flange_rating_face` | string | e.g. `CL.150 RF` |
| `temp_C` / `press_barg` | string[] | Paired P–T rating points (same length, same order) |
| `particular_notes` | string | Class-specific notes, verbatim |
| `components` | Component[] | Material-selection rows |

## Component

| Field | Type | Meaning |
|------|------|---------|
| `part` | string | e.g. `PIPE`, `90 ELBOW`, `GATE VALVE`, `GASKET` |
| `symbol` | string | MTO/component symbol, e.g. `(P)`, `(9L)` |
| `size_from` / `size_to` | string | NPS range bounds (inch) |
| `size_raw` | string[] | Original size tokens (preserves merged/double-column layouts) |
| `description` | string | Verbatim material + standard + schedule/rating text |
| `notes` | string[] | Referenced note numbers |

## Design principles

1. **Verbatim descriptions.** The `description` field is copied exactly from the
   source. Nothing is inferred or fabricated.
2. **Company-neutral.** Company-specific quirks live in *adapters*, not the schema.
3. **Lossless-ish.** Where a clean structured value can't be guaranteed (merged size
   columns), the raw tokens are preserved so no information is lost.

## Versioning

The schema is versioned with the package (SemVer). Breaking field changes bump the
major version.

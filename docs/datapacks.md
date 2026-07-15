# Private datapacks (standard allowable-stress tables)

The **thickness** and **compliance** features need allowable-stress values
(e.g. ASME B31.3 Table A-1, S vs temperature). Those tables are **copyrighted**
and must **not** be committed to this public repository.

They are loaded at runtime from a private, git-ignored location:

```
datapacks/materials.json        # your licensed data (preferred; git-ignored)
```

If that file is absent, the tools fall back to
`examples/materials.datapack.sample.json`, which contains **synthetic, clearly
fake** stress values so the features are demonstrable. Never treat synthetic
results as real.

## Format

```jsonc
{
  "meta": { "schema": "material-master v1", "stress_units": "MPa", "temp_units": "C" },
  "materials": [
    {
      "spec": "ASTM A106", "grade": "B", "family": "ferritic",
      "min_temp": -29, "max_temp": 400,
      "s": [[38, 138], [100, 138], [200, 133], [300, 126], [400, 95]]
    }
  ]
}
```

- `family`: `ferritic` or `austenitic` (drives the B31.3 Y coefficient).
- `s`: list of `[temperature_C, allowable_stress_MPa]` points; the tools linearly
  interpolate between them.

## Building it from your own B31.3 calculator

If you already maintain a wall-thickness calculator with a materials table,
export its material list into the shape above. Keep this file **local only**.

## CLI usage

```bash
pmskit check pms.json --datapack datapacks/materials.json --only-flagged
```

Web dashboard: place `materials.json` at `web/data/materials.json` **locally**
(also git-ignored) — the Thickness tab prefers it over the synthetic sample.


## Easiest: convert from your existing B31.3 calculator

If you have a wall-thickness calculator whose HTML contains a
`DEFAULT_MATERIALS = [...]` table, generate the datapack in one command:

```bash
# with pmskit installed:
pmskit import-stress your_calculator.html -o materials.json

# or without installing anything:
python tools/calc_to_datapack.py your_calculator.html materials.json
```

Then load `materials.json` in the dashboard: **Data → Load my data → Material
stress data**. The file holds your allowable-stress values — keep it local
(it is git-ignored).

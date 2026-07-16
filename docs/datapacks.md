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

---

# Component datapacks (flanges, fittings, valves, gaskets, bolting)

Since v0.8 the same private-datapack pattern covers the remaining PMS
components. Each pack has a JSON Schema in [`schema/datapacks/`](../schema/datapacks/)
and a **synthetic** sample in [`examples/`](../examples/):

| Datapack (private, git-ignored) | Schema | Content | Source standards |
|---|---|---|---|
| `datapacks/flanges.json`  | `flange-master v1`  | P–T ratings per material group, flange dimensions, bolting chart | ASME B16.5 / B16.47 |
| `datapacks/fittings.json` | `fitting-master v1` | buttweld, SW/threaded, branch-outlet dimensions | ASME B16.9, B16.11, MSS SP-97 |
| `datapacks/valves.json`   | `valve-master v1`   | type/trim selection matrix, face-to-face | API 600/602/594/609/6D, ASME B16.10 |
| `datapacks/gaskets.json`  | `gasket-master v1`  | SW/RTJ/flat dimensions, selection rules | ASME B16.20, B16.21 |
| `datapacks/bolting.json`  | `bolting-master v1` | stud/nut pairs, temp limits, NACE alternatives, torque | ASTM A193/A194/A320, ASME PCC-1 |

Rules, identical to the material datapack:

- Real ASME/API/MSS table values are **copyrighted** — they live only in the
  git-ignored `datapacks/` directory, never in the repo.
- Always record `meta.edition` (e.g. `"2020"`) — P–T ratings differ between
  editions; never mix editions inside one pack.
- Shipped samples carry `meta.SYNTHETIC: true` and clearly fake values.
- Valve P–T ratings are **not** duplicated in the valve pack: ASME B16.34
  standard-class ratings use the same material groups as B16.5, so the rating
  engine (`pmskit.rating`, `web/rating.js`) reads the flange pack.

## Rating engine

```python
from pmskit.rating import load_flanges, find_group, rated_pressure, select_class, flange_adequacy

pack  = load_flanges()                        # private pack, else synthetic sample
group = find_group(pack, "A216 WCB")          # -> material group dict
rated_pressure(group, 300, 250)               # barg at 250 C, CL300
select_class(group, [(38, 19.6), (200, 15)])  # smallest adequate class
flange_adequacy(pms_json)                     # one adequacy row per pipe class
```

`flange_adequacy` never produces a false pass — anything unresolvable
(no `CL.###`, unknown material group, no P–T points, temperature above the
rated range) is reported `not-evaluated`.

## Offline single-file bundle

To keep an **offline** copy of the dashboard (or another HTML tool) with your
datapacks embedded:

```bash
python tools/build_offline.py                      # -> dist/pms-dashboard-offline.html
python tools/build_offline.py --html mytool.html -o dist/mytool-offline.html
```

Datapacks are embedded as `<script type="application/json" id="datapack-…">`
blocks (read them with `loadEmbeddedDatapack(name)` from `web/rating.js`).
The bundle may contain your licensed data: `dist/` is git-ignored —
**never publish a bundle built from real datapacks**.

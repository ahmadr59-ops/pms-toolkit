# Contributing

Thanks for helping improve pms-toolkit!

## Dev setup
```bash
git clone https://github.com/ahmadr59-ops/pms-toolkit
cd pms-toolkit
pip install -e ".[dev]"
pytest -q
```

## Ground rules
- **No proprietary data in the repo.** Only synthetic examples. PMS documents are
  usually copyrighted by the issuing company.
- **No copyrighted standard tables.** Validation may use public *conventions*
  (standard flange classes, facings, schedules) but must not reproduce ASME/API
  allowable-pressure tables.
- **Never fabricate engineering values.** Missing → `null`.
- Add tests for new checks/adapters. Keep `pytest` green.

## Adding a company adapter
See [`docs/adapters.md`](docs/adapters.md).

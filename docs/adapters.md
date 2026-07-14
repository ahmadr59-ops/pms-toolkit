# Writing a PMS adapter

Every company lays out its PMS differently, so parsing is split into **adapters**.
An adapter converts *one* company's document into the [Open PMS Schema](../schema/README.md).

## Interface

Subclass `pmskit.adapters.base.PMSAdapter`:

```python
from pmskit.adapters.base import PMSAdapter
from pmskit.doc_parser import extract_text   # OLE .doc text extractor (reusable)

class AcmeAdapter(PMSAdapter):
    name = "acme"
    label = "ACME Engineering"

    def parse(self, path, company=None):
        raw = extract_text(path)            # or read .docx/.xlsx/.pdf yourself
        classes = my_layout_logic(raw)
        return self.envelope(classes, company or "ACME", path)
```

Then register it in `adapters/__init__.py`:

```python
_ADAPTERS = {a.name: a for a in [NIOECAdapter, AcmeAdapter]}
```

Now it is available everywhere:

```bash
pmskit parse acme_pms.doc --adapter acme -o acme.json
```

## Guidelines

- **Never fabricate.** If a value isn't in the source, emit `null`, not a guess.
- **Preserve raw tokens** where a clean structured value isn't certain (e.g. `size_raw`).
- **Emit a coverage report** (`pmskit report`) so users can judge extraction quality.
- **Keep proprietary data out of the repo.** Ship only synthetic examples.

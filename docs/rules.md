# JSON Rule Engine (rule-master v1)

Declarative engineering rules live in `rules/*.json`; the engines are
`src/pmskit/rules.py` and its byte-parity mirror `web/rules.js`. Conditions are
a small structured dialect (never `eval`): `var, truthy, !, and, or, ==, !=,
<, <=, >, >=, in, !in, regex_match, facts+, facts+var, object`. Parsing and
physics stay in code; **policy** lives in rules. Every rule carries a `source`
citation and can be disabled with `"enabled": false`.

## Migration status (strangler pattern)

| Stage | State |
|---|---|
| `rules/conventions.json` = pmskit.validate checks | **shadow** - legacy engine is still the default |
| Parity gate old-vs-new | `tests/test_rules_shadow.py` (fixture + every rule branch) |
| Parity gate Python-vs-JS | `tools/check_rules_parity.py` (run in CI) |
| Flip default to rule engine | only after both gates stay green in CI |

Next packs (born as rules, no legacy code to migrate): compliance policies
(borderline margins, severities), branch-table selection, gasket/valve/bolting
selection matrices, and per-project override profiles (Owner deviations as an
auditable JSON overlay, not code edits).

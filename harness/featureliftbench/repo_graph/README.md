# Repository Semantic Graph

Deterministic repository fact graph (Tree-sitter) plus budgeted
**Operational Support Subgraph** queries for coding agents.

This component is retained as optional infrastructure and a historical
retrieval baseline. It is not the current benchmark or method priority; see
`docs/CURRENT_RESEARCH.md` and `reports/repo_graph_phase*/`.

## Install

```bash
python -m pip install -e '.[repo-graph]'
```

## Offline build / query

```bash
flb-rsg build --repo benchmark/tasks/sqlparse__token_tree_core__001/repo --output /tmp/sqlparse-rsg
flb-rsg self-check --graph /tmp/sqlparse-rsg
flb-rsg search --graph /tmp/sqlparse-rsg TokenList
flb-rsg inspect --graph /tmp/sqlparse-rsg python:sqlparse.sql.TokenList:class
flb-rsg support --graph /tmp/sqlparse-rsg --seed sqlparse.parse --budget-tokens 8000
flb-rsg closure --graph /tmp/sqlparse-rsg python:sqlparse.sql.TokenList:class
```

Offline support vs baselines (Phase 4 scaffold):

```bash
PYTHONPATH=harness python harness/scripts/compare_support_baselines.py \
  --repo benchmark/sanity/iniconfig__parse_config__001/repo \
  --seed IniConfig --budget-tokens 2000 \
  --output reports/repo_graph_phase3/iniconfig_support_compare.json
```

## OpenHands surface (v2)

```text
flb-rsg search
flb-rsg inspect      # bounded (default inspect_max_chars)
flb-rsg support      # Operational Support Subgraph
```

Tool use is **optional**. No mandatory task-closure, submission-check, claim,
or stopping controller on the OpenHands path.

## Phase 3 MVP relations (Python)

```text
EXPORTS, PROVIDES_MEMBER, RETURNS_TYPE, RAISES,
LOADS_RESOURCE, PACKAGED_BY,
READS_CONFIG, DEFAULT_DEFINED_BY,
REGISTERS, RESOLVES_VIA
```

Dynamic unresolved cues use `resolution=unresolved_dynamic` and feed Boundaries.

## Status

- Phase 1–2 + API smoke: done (`reports/repo_graph_phase2/`).
- Phase 3 relation families: done (fixture tests in `tests/test_repo_graph_relations.py`).
- Phase 4 offline quality: scaffold comparator landed; annotation set still open.
- ECSM / forced adoption gates: retired.

## Audit

```bash
PYTHONPATH=harness python harness/scripts/audit_repo_graph_python150.py \
  --output reports/repo_graph_phase1/python150_audit.json
```

# FeatureLiftBench

FeatureLiftBench evaluates behavior-preserving feature lifting. A task supplies a fixed source repository and a public behavioral contract. The agent delivers an independent package. Functional pass requires Build, Primary, Extended, and Isolation. Evaluation runs without the source repository.

The package provides:

- 150 Python tasks, drawn from 126 repositories and 132 pinned snapshots
- the evaluator and the frozen Full Source and Contract Only configuration
- 1,050 full-source outcomes
- source-exposure and execution-effort tables
- RRES and Copy for passing artifacts
- the Direct Source Extraction baseline
- 46 qualitative cases and their theme mapping

```bash
python scripts/reproduce_paper.py
python scripts/materialize_sources.py
python scripts/verify_source_hashes.py
```

`reproduce_paper.py` checks the published pass counts. `materialize_sources.py` restores each pinned snapshot. `verify_source_hashes.py` checks `source_tree_sha256`.

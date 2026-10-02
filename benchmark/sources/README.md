# Source registry

`registry.json` records the 126 repositories and 132 snapshots behind the 150 tasks: canonical URL, resolved commit, acquisition method, archive digest, and `source_tree_sha256`.

Restore and check the snapshots with:

```bash
python scripts/materialize_sources.py
python scripts/verify_source_hashes.py
```

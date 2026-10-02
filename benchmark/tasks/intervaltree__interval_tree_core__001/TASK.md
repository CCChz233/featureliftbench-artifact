# FeatureLift Task: IntervalTree core

Extract a task-scoped subset of `intervaltree` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Interval,
    IntervalTree,
)
```

## Required API Details

- `Interval(begin, end, data=None)` class constructor
- `IntervalTree(intervals=None)` class constructor
  - `IntervalTree.at(self, p)`
  - `IntervalTree.chop(self, begin, end, datafunc=None)`
  - `IntervalTree.envelop(self, begin, end=None)`
  - `IntervalTree.overlap(self, begin, end=None)`
  - `IntervalTree.remove_envelop(self, begin, end)`
  - `IntervalTree.remove_overlap(self, begin, end=None)`
  - `IntervalTree.__contains__(self, item)`
  - `IntervalTree.__getitem__(self, index)`

## Required Behavior

- The extracted feature must support this observable behavior: add/remove/discard intervals with set semantics and distinct data fields. Required observable cases include add and point query; remove interval; remove overlap multiple; distinct data same range; remove envelop.
- The extracted feature must support this observable behavior: point and range overlap queries via at/overlap/overlaps. Required observable cases include add and point query; overlap range; complex point query.
- The extracted feature must support this observable behavior: remove_overlap and remove_envelop bulk deletion. Required observable cases include remove interval; remove overlap multiple; envelop vs overlap; remove envelop.
- The extracted feature must support this observable behavior: chop trims overhanging intervals and optional datafunc relabeling. Required observable cases include chop splits intervals; chop datafunc.
- The extracted feature must support this observable behavior: self-balancing tree queries through Node search helpers. Required observable cases include remove overlap multiple.
- The package exposes the required task API paths `featurelifted.Interval`, `featurelifted.IntervalTree`, `featurelifted.IntervalTree.at`, `featurelifted.IntervalTree.chop`, `featurelifted.IntervalTree.envelop`, `featurelifted.IntervalTree.overlap`, `featurelifted.IntervalTree.remove_envelop`, `featurelifted.IntervalTree.remove_overlap`, `featurelifted.IntervalTree.__contains__`, `featurelifted.IntervalTree.__getitem__` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `intervaltree`.
- Do not implement upstream test harness, benchmarks, and packaging metadata.
- Do not implement original intervaltree import at runtime.
- Do not implement CLI and documentation tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: add/remove/discard intervals with set semantics and distinct data fields. Required observable cases include add and point query; remove interval; remove overlap multiple; distinct data same range; remove envelop.
- **B002** — The extracted feature must support this observable behavior: point and range overlap queries via at/overlap/overlaps. Required observable cases include add and point query; overlap range; complex point query.
- **B003** — The extracted feature must support this observable behavior: remove_overlap and remove_envelop bulk deletion. Required observable cases include remove interval; remove overlap multiple; envelop vs overlap; remove envelop.
- **B004** — The extracted feature must support this observable behavior: chop trims overhanging intervals and optional datafunc relabeling. Required observable cases include chop splits intervals; chop datafunc.
- **B005** — The extracted feature must support this observable behavior: self-balancing tree queries through Node search helpers. Required observable cases include remove overlap multiple.
- **B006** — The package exposes the required task API paths `featurelifted.Interval`, `featurelifted.IntervalTree`, `featurelifted.IntervalTree.at`, `featurelifted.IntervalTree.chop`, `featurelifted.IntervalTree.envelop`, `featurelifted.IntervalTree.overlap`, `featurelifted.IntervalTree.remove_envelop`, `featurelifted.IntervalTree.remove_overlap`, `featurelifted.IntervalTree.__contains__`, `featurelifted.IntervalTree.__getitem__` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: intervaltree.
<!-- featureliftbench:behavior-clauses:end -->

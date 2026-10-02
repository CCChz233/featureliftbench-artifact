# FeatureLift Task: DeepDiff path and exclude subset

Extract a task-scoped subset of `deepdiff` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DeepDiff,
    extract,
    parse_path,
)
```

## Required API Details

- `DeepDiff(t1: Any, t2: Any, _original_type: Optional[Any] = None, cache_purge_level: int = 1, cache_size: int = 0, cache_tuning_sample_size: int = 0, custom_operators: Optional[List[Any]] = None, cutoff_distance_for_pairs: float = 0.3, cutoff_intersection_for_pairs: float = 0.7, default_timezone: Union[datetime.timezone, ForwardRef('BaseTzInfo')] = datetime.timezone.utc, encodings: Optional[List[str]] = None, exclude_obj_callback: Optional[Callable] = None, exclude_obj_callback_strict: Optional[Callable] = None, exclude_paths: Union[str, List[str], Set[str], FrozenSet[str], NoneType] = None, exclude_regex_paths: Union[str, List[str], Pattern[str], List[Pattern[str]], NoneType] = None, exclude_types: Optional[List[type]] = None, get_deep_distance: bool = False, group_by: Union[str, Tuple[str, str], Callable, NoneType] = None, group_by_sort_key: Union[str, Callable, NoneType] = None, hasher: Optional[Callable] = None, hashes: Optional[Dict[Any, Any]] = None, ignore_encoding_errors: bool = False, ignore_nan_inequality: bool = False, ignore_numeric_type_changes: bool = False, ignore_order: bool = False, ignore_order_func: Optional[Callable] = None, ignore_private_variables: bool = True, ignore_string_case: bool = False, ignore_string_type_changes: bool = False, ignore_type_in_groups: Optional[List[Tuple[Any, ...]]] = None, ignore_type_subclasses: bool = False, ignore_uuid_types: bool = False, include_obj_callback: Optional[Callable] = None, include_obj_callback_strict: Optional[Callable] = None, include_paths: Union[str, List[str], NoneType] = None, iterable_compare_func: Optional[Callable] = None, log_frequency_in_sec: int = 0, log_scale_similarity_threshold: float = 0.1, log_stacktrace: bool = False, math_epsilon: Optional[float] = None, max_diffs: Optional[int] = None, max_passes: int = 10000000, multiprocessing: bool = False, multiprocessing_workers: Optional[int] = None, multiprocessing_threshold: Optional[int] = None, number_format_notation: Literal['f', 'e'] = 'f', number_to_string_func: Optional[Callable] = None, progress_logger: Callable[[str], NoneType] = <bound method Logger.info of <Logger diff (WARNING)>>, report_repetition: bool = False, significant_digits: Optional[int] = None, threshold_to_diff_deeper: float = 0.33, truncate_datetime: Optional[str] = None, use_enum_value: bool = False, use_log_scale: bool = False, verbose_level: int = 1, view: str = 'text', zip_ordered_iterables: bool = False, _parameters: Optional[Dict[str, Any]] = None, _shared_parameters: Optional[Dict[str, Any]] = None, **kwargs)` class constructor
  - `DeepDiff.get(self, key, default=None, /)`
  - `DeepDiff.__contains__(self, key, /)`
- `parse_path(path, root_element=('root', 'GETATTR'), include_actions=False)`
- `extract(obj, path)`

## Required Behavior

- The extracted feature must support this observable behavior: DeepDiff dict/list value changes. Required observable cases include shallow dict diff; identical nested; nested dict change; list item added.
- The extracted feature must support this observable behavior: exclude_paths and include_paths filtering. Required observable cases include exclude paths wildcard.
- The extracted feature must support this observable behavior: parse_path and extract by path expression. Required observable cases include parse path and extract.
- The package exposes the required task API paths `featurelifted.DeepDiff`, `featurelifted.DeepDiff.get`, `featurelifted.DeepDiff.__contains__`, `featurelifted.parse_path`, `featurelifted.extract` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `deepdiff`.
- Do not implement DeepSearch.
- Do not implement Delta patch.
- Do not implement original deepdiff import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: DeepDiff dict/list value changes. Required observable cases include shallow dict diff; identical nested; nested dict change; list item added.
- **B002** — The extracted feature must support this observable behavior: exclude_paths and include_paths filtering. Required observable cases include exclude paths wildcard.
- **B003** — The extracted feature must support this observable behavior: parse_path and extract by path expression. Required observable cases include parse path and extract.
- **B004** — The package exposes the required task API paths `featurelifted.DeepDiff`, `featurelifted.DeepDiff.get`, `featurelifted.DeepDiff.__contains__`, `featurelifted.parse_path`, `featurelifted.extract` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: deepdiff.
<!-- featureliftbench:behavior-clauses:end -->

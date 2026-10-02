"""Repository packaging metadata → PACKAGED_BY edges (Phase 3)."""

from __future__ import annotations

import re
from pathlib import Path

from .models import EdgeSpec, NodeSpec

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


PROVENANCE = "packaging-scanner-v1"


def add_packaging_edges(
    repository: Path,
    node_specs: dict[str, NodeSpec],
    edge_specs: list[EdgeSpec],
) -> None:
    """Attach PACKAGED_BY edges from packaging manifests to resource/module nodes."""

    root = repository.resolve()
    package_modules = {
        node.qualified_name
        for node in node_specs.values()
        if node.kind == "module" and node.language == "python"
    }
    resources = [
        node
        for node in node_specs.values()
        if node.kind == "resource"
    ]

    declared: list[tuple[str, str]] = []  # (package_or_module, resource_pattern)
    declared.extend(_from_pyproject(root))
    declared.extend(_from_manifest_in(root))
    if not declared:
        return

    for package_name, pattern in declared:
        package_id = f"python:{package_name}:module"
        if package_id not in node_specs:
            # Keep an explicit package/module placeholder so the edge is queryable.
            if package_name in package_modules:
                package_id = next(
                    node.stable_id
                    for node in node_specs.values()
                    if node.kind == "module" and node.qualified_name == package_name
                )
            else:
                node_specs[package_id] = NodeSpec(
                    package_id,
                    "module",
                    package_name.rsplit(".", 1)[-1],
                    package_name,
                    "python",
                    attributes={"from_packaging_manifest": True},
                )
        matched_resources = [
            node
            for node in resources
            if _pattern_matches(pattern, node.qualified_name) or _pattern_matches(pattern, node.name)
        ]
        if not matched_resources:
            # Still record a candidate packaging obligation with an unresolved resource.
            resource_id = f"resource:{package_name}:{pattern}:resource"
            if resource_id not in node_specs:
                node_specs[resource_id] = NodeSpec(
                    resource_id,
                    "resource",
                    Path(pattern).name or pattern,
                    pattern,
                    "python",
                    attributes={"declared_by_packaging": True},
                )
            matched_resources = [node_specs[resource_id]]
        for resource in matched_resources:
            edge_specs.append(
                EdgeSpec(
                    resource.stable_id,
                    package_id,
                    "PACKAGED_BY",
                    "exact" if resource.attributes.get("declared_by_packaging") is not True else "candidate",
                    PROVENANCE,
                    {
                        "package": package_name,
                        "pattern": pattern,
                        "risk_category": "resource_coupling",
                    },
                )
            )


def _from_pyproject(root: Path) -> list[tuple[str, str]]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    declared: list[tuple[str, str]] = []
    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    setuptools = tool.get("setuptools") if isinstance(tool.get("setuptools"), dict) else {}
    package_data = setuptools.get("package-data")
    if isinstance(package_data, dict):
        for package, patterns in package_data.items():
            if not isinstance(package, str):
                continue
            values = patterns if isinstance(patterns, list) else [patterns]
            for pattern in values:
                if isinstance(pattern, str) and pattern.strip():
                    declared.append((package, pattern.strip()))
    # Poetry / hatch include lists are optional extras.
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    include = poetry.get("include")
    if isinstance(include, list):
        for item in include:
            if isinstance(item, str) and item.strip():
                declared.append((".", item.strip()))
            elif isinstance(item, dict):
                path_value = item.get("path")
                if isinstance(path_value, str) and path_value.strip():
                    declared.append((".", path_value.strip()))
    return declared


def _from_manifest_in(root: Path) -> list[tuple[str, str]]:
    path = root / "MANIFEST.in"
    if not path.is_file():
        return []
    declared: list[tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^(?:recursive-)?include\s+(\S+)\s+(.+)$", stripped, flags=re.I)
        if not match:
            continue
        package_or_dir, patterns = match.group(1), match.group(2)
        for pattern in patterns.split():
            declared.append((package_or_dir.replace("/", ".").strip("."), pattern))
    return declared


def _pattern_matches(pattern: str, value: str) -> bool:
    if not pattern or not value:
        return False
    # Conservative glob-ish match for '*' only.
    regex = re.escape(pattern).replace(r"\*", ".*")
    return re.search(regex, value) is not None or Path(value).name == Path(pattern).name

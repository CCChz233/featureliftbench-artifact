"""High-precision static cues that suggest bounded runtime probes."""

from __future__ import annotations

from typing import Any

from .models import GraphSnapshot
from .storage import MemoryGraphIndex


DETECTOR_RULES: dict[str, dict[str, str]] = {
    "MUTABLE_GLOBAL": {
        "detector": "global_mutable_state",
        "probe": "repeated_call_state",
        "rationale": "Compare repeated calls and a fresh instance to expose retained state.",
    },
    "MODULE_STATE": {
        "detector": "module_state_candidate",
        "probe": "fresh_process_replay",
        "rationale": "Replay in a fresh process before treating module state as necessary.",
    },
    "READS_ENV": {
        "detector": "environment_dependency",
        "probe": "controlled_environment",
        "rationale": "Vary only the named environment input and compare behavior.",
    },
    "READS_CWD": {
        "detector": "working_directory_dependency",
        "probe": "controlled_working_directory",
        "rationale": "Run from repository and clean temporary working directories.",
    },
    "WRITES_CWD": {
        "detector": "working_directory_side_effect",
        "probe": "temporary_directory_side_effect",
        "rationale": "Capture files created in an isolated temporary directory.",
    },
    "LOADS_RESOURCE": {
        "detector": "package_resource_dependency",
        "probe": "clean_install_resource_lookup",
        "rationale": "Build/install the submission and resolve the resource outside the source tree.",
    },
    "PACKAGED_BY": {
        "detector": "packaging_resource_declaration",
        "probe": "clean_install_resource_lookup",
        "rationale": "Verify package_data / MANIFEST resources remain available after install.",
    },
    "READS_CONFIG": {
        "detector": "config_file_dependency",
        "probe": "controlled_config_file",
        "rationale": "Vary only the named config file contents and compare behavior.",
    },
    "REGISTERS": {
        "detector": "registry_or_decorator_coupling",
        "probe": "registry_population",
        "rationale": "Inspect registry population before and after the relevant import.",
    },
    "RESOLVES_VIA": {
        "detector": "dynamic_registry_dispatch",
        "probe": "representative_runtime_trace",
        "rationale": "Trace representative keys to observe which handler the registry selects.",
    },
    "DYNAMIC_IMPORT": {
        "detector": "dynamic_import",
        "probe": "representative_runtime_trace",
        "rationale": "Trace representative execution to observe the resolved module.",
    },
    "DYNAMIC_GETATTR": {
        "detector": "dynamic_dispatch",
        "probe": "representative_runtime_trace",
        "rationale": "Trace representative inputs to observe the selected attribute or callback.",
    },
    "IMPORT_TIME_CALL": {
        "detector": "import_time_initialization",
        "probe": "import_order",
        "rationale": "Compare clean imports and alternate import order in fresh processes.",
    },
    "INIT_TIME_CALL": {
        "detector": "init_time_initialization",
        "probe": "fresh_process_replay",
        "rationale": "Replay initialization in a fresh process and compare registered state.",
    },
}


def detect_runtime_risks(
    snapshot: GraphSnapshot,
    *,
    task_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only detector rules whose cue has an explicit, testable rationale."""

    index = MemoryGraphIndex(snapshot)
    detections = []
    for edge in snapshot.edges:
        rule = DETECTOR_RULES.get(edge.kind)
        if rule is None:
            continue
        source = index.nodes_by_id[edge.source]
        target = index.nodes_by_id.get(edge.target) if edge.target is not None else None
        detections.append(
            {
                "detector_id": f"detector:{rule['detector']}:{edge.id}",
                "detector": rule["detector"],
                "source_cue": {
                    "edge_id": edge.id,
                    "edge_kind": edge.kind,
                    "resolution": edge.resolution,
                    "source": source.stable_id,
                    "target": target.stable_id if target is not None else None,
                    "location": (
                        f"{source.span.path}:{source.span.start_line}" if source.span else None
                    ),
                },
                "suggested_probe": rule["probe"],
                "probe_rationale": rule["rationale"],
                "precision_tier": "exposed-v1",
                "claim_required": False,
            }
        )
    overlay = task_overlay or {}
    for index_number, mapping in enumerate(overlay.get("entrypoint_mapping", []), start=1):
        if not isinstance(mapping, dict):
            continue
        node = mapping.get("node") if isinstance(mapping.get("node"), dict) else {}
        detections.append(
            {
                "detector_id": f"detector:api_export_closure:{index_number}",
                "detector": "api_export_closure",
                "source_cue": {
                    "entrypoint": mapping.get("entrypoint", ""),
                    "mapping_status": mapping.get("status", "unmapped"),
                    "source": node.get("stable_id"),
                    "kind": node.get("kind"),
                },
                "suggested_probe": "output_api_import_and_call",
                "probe_rationale": "Import and exercise the declared output API from a clean submission environment.",
                "precision_tier": "exposed-v1",
                "claim_required": False,
            }
        )
    for index_number, forbidden in enumerate(overlay.get("forbidden_imports", []), start=1):
        if not isinstance(forbidden, str) or not forbidden:
            continue
        detections.append(
            {
                "detector_id": f"detector:forbidden_boundary:{index_number}",
                "detector": "forbidden_boundary",
                "source_cue": {"forbidden_import": forbidden},
                "suggested_probe": "submission_import_scan",
                "probe_rationale": "Scan runtime submission files and installed metadata for the forbidden provider.",
                "precision_tier": "exposed-v1",
                "claim_required": False,
            }
        )
    allowed_dependencies = set(
        item
        for item in overlay.get("environment_scope", {}).get("allowed_dependencies", [])
        if isinstance(item, str)
    ) if isinstance(overlay.get("environment_scope"), dict) else set()
    for edge in snapshot.edges:
        if edge.kind != "IMPORTS_MODULE" or edge.target is None:
            continue
        target = index.nodes_by_id[edge.target]
        dependency_root = target.qualified_name.split(".", 1)[0].split("/", 1)[0]
        if dependency_root not in allowed_dependencies:
            continue
        source = index.nodes_by_id[edge.source]
        detections.append(
            {
                "detector_id": f"detector:third_party_dependency:{edge.id}",
                "detector": "third_party_dependency",
                "source_cue": {
                    "edge_id": edge.id,
                    "source": source.stable_id,
                    "dependency": target.qualified_name,
                },
                "suggested_probe": "clean_install_dependency_import",
                "probe_rationale": "Install only declared dependencies and import the extracted feature in isolation.",
                "precision_tier": "exposed-v1",
                "claim_required": False,
            }
        )
    payload = {
        "schema_version": "featureliftbench.repo_graph.detectors.v1",
        "detections": detections,
        "count": len(detections),
        "unmatched_low_precision_cues_exposed": 0,
    }
    return payload

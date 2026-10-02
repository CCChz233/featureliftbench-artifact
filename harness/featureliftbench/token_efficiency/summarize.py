"""Phase E summaries, coverage bias, sensitivity, and draft figures."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from .constants import (
    ACCOUNTING_TOTAL,
    ANALYSIS_SEED,
    BOOTSTRAP_REPLICATES,
    CONFIG_ORDER,
    LIFT_TYPES,
)
from .scope import OfficialRun, load_official_runs, official_pass_counts, repo_root
from .util import iqr, median_linear, quantile_linear, write_csv, write_json


DISPLAY = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "glm-5.3-flash": "GLM-5.3-Flash",
    "qwen3.6-35b-a3b-fp8": "Qwen3.6-35B-A3B-FP8",
    "gpt-oss-120b": "GPT-OSS 120B",
}


def summarize_suite(
    *,
    metrics_rows: list[dict[str, Any]],
    runs: list[OfficialRun],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = output_dir / "figures"
    figures.mkdir(exist_ok=True)
    paper_ready = output_dir / "paper_ready"
    paper_ready.mkdir(exist_ok=True)

    by_config = _group(metrics_rows, "configuration")
    summary_config = []
    efficiency_rows = []
    claims: list[dict[str, Any]] = []
    readiness = {}
    pass_fail_rows = []
    lift_rows = []
    bias_rows = []
    sensitivity_rows = []

    official = official_pass_counts(runs)
    for model in CONFIG_ORDER:
        rows = by_config.get(model, [])
        official_success_n = official[model]
        psf_rows = [row for row in rows if _truthy(row.get("include_psf_primary"))]
        psf_vals = [_float(row.get("post_sufficiency_fraction")) for row in psf_rows]
        psf_vals = [value for value in psf_vals if value is not None]
        post_vals = [
            _float(row.get("post_sufficiency_tokens"))
            for row in psf_rows
            if _float(row.get("post_sufficiency_tokens")) is not None
        ]
        q1, med, q3 = iqr(psf_vals)
        post_q1, post_med, post_q3 = iqr(post_vals)
        lo, hi = bootstrap_median_ci(psf_vals, seed=ANALYSIS_SEED)
        summary_config.append(
            {
                "configuration": model,
                "display": DISPLAY[model],
                "assigned_n": len(rows),
                "official_success_n": official_success_n,
                "included_success_n": len(psf_rows),
                "effort_n": sum(1 for row in rows if _truthy(row.get("include_effort"))),
                "failure_history_n": sum(1 for row in rows if _truthy(row.get("include_failure_history"))),
                "exact_n": sum(1 for row in rows if row.get("sufficiency_status") == "exact"),
                "bounded_n": sum(1 for row in rows if row.get("sufficiency_status") == "bounded"),
                "never_sufficient_n": sum(1 for row in rows if row.get("sufficiency_status") == "never_sufficient"),
                "unresolved_n": sum(1 for row in rows if row.get("sufficiency_status") == "unresolved"),
                "median_psf": med,
                "psf_q1": q1,
                "psf_q3": q3,
                "psf_ci_low": lo,
                "psf_ci_high": hi,
                "median_post_tokens": post_med,
                "post_q1": post_q1,
                "post_q3": post_q3,
                "sum_post_over_sum_total": _pooled_post(psf_rows),
                "ever_pass_final_fail_n": sum(
                    1 for row in rows if _truthy(row.get("ever_pass_final_fail"))
                    and _truthy(row.get("include_failure_history"))
                ),
                "accounting_basis": ACCOUNTING_TOTAL,
            }
        )
        efficiency_rows.append(
            {
                "Configuration": DISPLAY[model],
                "Included successes n/N": (
                    f"{len(psf_rows)}/{official_success_n}" if official_success_n else "--"
                ),
                "Median post-sufficiency tokens [IQR]": _fmt_iqr(post_med, post_q1, post_q3),
                "Median PSF [95% CI]": _fmt_psf(med, lo, hi),
            }
        )
        claims.append(
            {
                "claim_id": f"{model}.included_success_n",
                "text": f"{DISPLAY[model]} primary PSF sample size",
                "configuration": model,
                "accounting_basis": ACCOUNTING_TOTAL,
                "numerator": len(psf_rows),
                "denominator": official_success_n,
                "estimate": len(psf_rows) / official_success_n if official_success_n else None,
                "lower": "",
                "upper": "",
                "source_file": "run_metrics.csv",
                "filter": "include_psf_primary=true",
                "metric": "included_success_n",
            }
        )
        if med is not None:
            claims.append(
                {
                    "claim_id": f"{model}.median_psf",
                    "text": f"{DISPLAY[model]} median post-sufficiency fraction",
                    "configuration": model,
                    "accounting_basis": ACCOUNTING_TOTAL,
                    "numerator": len(psf_rows),
                    "denominator": official_success_n,
                    "estimate": med,
                    "lower": lo,
                    "upper": hi,
                    "source_file": "run_metrics.csv",
                    "filter": "include_psf_primary=true",
                    "metric": "median_post_sufficiency_fraction",
                }
            )
        readiness[model] = {
            "effort_ready": any(_truthy(row.get("include_effort")) for row in rows),
            "artifact_history_ready": any(
                row.get("sufficiency_status") in {"exact", "bounded", "never_sufficient"}
                for row in rows
            ),
            "psf_ready": bool(psf_rows),
            "included_success_n": len(psf_rows),
            "official_success_n": official_success_n,
            "blocking_reasons": sorted(
                {
                    str(row.get("exclusion_reason_psf_primary") or "")
                    for row in rows
                    if row.get("final_pass") in {True, "true", "True"}
                    and not _truthy(row.get("include_psf_primary"))
                    and row.get("exclusion_reason_psf_primary")
                }
            ),
        }
        for passed, label in ((True, "pass"), (False, "fail")):
            subset = [row for row in rows if _truthy(row.get("final_pass")) is passed]
            effort = [row for row in subset if _truthy(row.get("include_effort"))]
            tokens = [_float(row.get("total_tokens")) for row in effort]
            tokens = [value for value in tokens if value is not None]
            steps = [
                _float(row.get("original_steps"))
                for row in subset
                if _float(row.get("original_steps")) is not None
            ]
            t_q1, t_med, t_q3 = iqr(tokens)
            s_q1, s_med, s_q3 = iqr(steps)
            pass_fail_rows.append(
                {
                    "configuration": model,
                    "outcome": label,
                    "n_assigned": len(subset),
                    "n_effort": len(effort),
                    "token_median": t_med,
                    "token_q1": t_q1,
                    "token_q3": t_q3,
                    "token_p90": quantile_linear(tokens, 0.9),
                    "steps_median": s_med,
                    "steps_q1": s_q1,
                    "steps_q3": s_q3,
                    "steps_p90": quantile_linear(steps, 0.9),
                    "accounting_basis": ACCOUNTING_TOTAL,
                }
            )
        for lift in LIFT_TYPES:
            lift_subset = [row for row in rows if row.get("lift_type") == lift]
            psf_lift = [
                _float(row.get("post_sufficiency_fraction"))
                for row in lift_subset
                if _truthy(row.get("include_psf_primary"))
                and _float(row.get("post_sufficiency_fraction")) is not None
            ]
            lift_rows.append(
                {
                    "configuration": model,
                    "lift_type": lift,
                    "n": len(lift_subset),
                    "psf_n": len(psf_lift),
                    "median_psf": median_linear(psf_lift),
                    "note": "descriptive only; not a causal difficulty effect",
                }
            )
        included_ids = {row.get("task_id") for row in psf_rows}
        for flag, name in (
            (lambda row: row.get("task_id") in included_ids, "psf_included"),
            (lambda row: row.get("task_id") not in included_ids, "psf_excluded"),
        ):
            subset = [row for row in rows if _truthy(row.get("final_pass")) and flag(row)]
            tokens = [
                _float(row.get("total_tokens"))
                for row in subset
                if _float(row.get("total_tokens")) is not None
            ]
            steps = [
                _float(row.get("original_steps"))
                for row in subset
                if _float(row.get("original_steps")) is not None
            ]
            bias_rows.append(
                {
                    "configuration": model,
                    "group": name,
                    "n": len(subset),
                    "token_median": median_linear(tokens),
                    "token_q1": quantile_linear(tokens, 0.25),
                    "token_q3": quantile_linear(tokens, 0.75),
                    "steps_median": median_linear(steps),
                }
            )
        dual = [
            row
            for row in psf_rows
            if row.get("stable_status") == "exact"
            and _float(row.get("stable_post_fraction")) is not None
            and _float(row.get("post_sufficiency_fraction")) is not None
        ]
        sensitivity_rows.append(
            {
                "configuration": model,
                "n_same_sample_first_vs_stable": len(dual),
                "median_first_post_fraction": median_linear(
                    [_float(row.get("post_sufficiency_fraction")) for row in dual]
                ),
                "median_stable_post_fraction": median_linear(
                    [_float(row.get("stable_post_fraction")) for row in dual]
                ),
                "n_dual_ledger": sum(
                    1
                    for row in rows
                    if _truthy(row.get("include_psf_primary")) and row.get("total_tokens")
                ),
                "note": "same-sample comparison only; empty when no dual-measurable runs",
            }
        )

    write_csv(
        output_dir / "summary_by_configuration.csv",
        summary_config,
        list(summary_config[0].keys()) if summary_config else ["configuration"],
    )
    write_csv(
        output_dir / "summary_by_lift_type.csv",
        lift_rows,
        list(lift_rows[0].keys()) if lift_rows else ["configuration"],
    )
    write_csv(
        output_dir / "pass_fail_effort.csv",
        pass_fail_rows,
        list(pass_fail_rows[0].keys()) if pass_fail_rows else ["configuration"],
    )
    write_csv(
        output_dir / "coverage_bias.csv",
        bias_rows,
        list(bias_rows[0].keys()) if bias_rows else ["configuration"],
    )
    write_csv(
        output_dir / "sensitivity.csv",
        sensitivity_rows,
        list(sensitivity_rows[0].keys()) if sensitivity_rows else ["configuration"],
    )
    unresolved_rows = [
        {
            "run_id": row.get("run_id"),
            "configuration": row.get("configuration"),
            "task_id": row.get("task_id"),
            "reason": row.get("sufficiency_status") or row.get("replay_status"),
            "notes": row.get("missing_reason") or row.get("notes") or "",
            "stage": "replay_eval",
        }
        for row in metrics_rows
        if str(row.get("sufficiency_status") or "") in {"unresolved"}
        or str(row.get("replay_status") or "") in {"error", "unresolved"}
    ]
    write_csv(
        output_dir / "unresolved.csv",
        unresolved_rows,
        ("run_id", "configuration", "task_id", "reason", "notes", "stage"),
    )
    write_csv(
        paper_ready / "efficiency_table.csv",
        efficiency_rows,
        (
            "Configuration",
            "Included successes n/N",
            "Median post-sufficiency tokens [IQR]",
            "Median PSF [95% CI]",
        ),
    )
    (paper_ready / "efficiency_table.tex").write_text(
        _latex_table(efficiency_rows), encoding="utf-8"
    )
    write_csv(
        paper_ready / "claim_evidence.csv",
        claims,
        (
            "claim_id",
            "text",
            "configuration",
            "accounting_basis",
            "numerator",
            "denominator",
            "estimate",
            "lower",
            "upper",
            "source_file",
            "filter",
            "metric",
        ),
    )
    write_json(paper_ready / "readiness.json", readiness)
    (paper_ready / "methods.md").write_text(_methods_md(summary_config), encoding="utf-8")
    (paper_ready / "results.md").write_text(_results_md(summary_config, readiness), encoding="utf-8")
    figure_data = _write_figures(metrics_rows, figures)
    (paper_ready / "figure_recipe.md").write_text(_figure_recipe(), encoding="utf-8")
    write_json(paper_ready / "figure_source.json", figure_data)
    write_json(output_dir / "summary.json", {"by_configuration": summary_config, "readiness": readiness})
    (output_dir / "REPORT.md").write_text(_report_md(summary_config, readiness), encoding="utf-8")
    return {"summary": summary_config, "readiness": readiness}


def bootstrap_median_ci(
    values: Sequence[float],
    *,
    seed: int = ANALYSIS_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[float | None, float | None]:
    if len(values) < 2:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    medians: list[float] = []
    for _ in range(replicates):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(median_linear(sample) or 0.0)
    medians.sort()
    lo_index = int(0.025 * (replicates - 1))
    hi_index = int(0.975 * (replicates - 1))
    return medians[lo_index], medians[hi_index]


def _write_figures(rows: list[dict[str, Any]], figures: Path) -> dict[str, Any]:
    source = {"psf_ecdf": [], "token_steps": []}
    for model in CONFIG_ORDER:
        psf = sorted(
            _float(row.get("post_sufficiency_fraction"))
            for row in rows
            if row.get("configuration") == model
            and _truthy(row.get("include_psf_primary"))
            and _float(row.get("post_sufficiency_fraction")) is not None
        )
        psf = [value for value in psf if value is not None]
        for index, value in enumerate(psf):
            source["psf_ecdf"].append(
                {
                    "configuration": model,
                    "psf": value,
                    "ecdf": (index + 1) / len(psf),
                }
            )
        for row in rows:
            if row.get("configuration") != model:
                continue
            tokens = _float(row.get("total_tokens"))
            steps = _float(row.get("original_steps"))
            if tokens is None or steps is None:
                continue
            source["token_steps"].append(
                {
                    "configuration": model,
                    "tokens": tokens,
                    "steps": steps,
                    "final_pass": _truthy(row.get("final_pass")),
                }
            )
    write_json(figures / "psf_ecdf.json", source["psf_ecdf"])
    write_json(figures / "token_steps.json", source["token_steps"])
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        (figures / "README.md").write_text(
            "matplotlib unavailable; JSON point data were written instead.\n",
            encoding="utf-8",
        )
        return source
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for model in CONFIG_ORDER:
        xs = [item["psf"] for item in source["psf_ecdf"] if item["configuration"] == model]
        ys = [item["ecdf"] for item in source["psf_ecdf"] if item["configuration"] == model]
        if xs:
            ax.step(xs, ys, where="post", label=DISPLAY[model])
    ax.set_xlabel("Post-sufficiency fraction (Ttotal − T*) / Ttotal")
    ax.set_ylabel("Cumulative proportion")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    ax.set_title("PSF ECDF (primary sample, total tokens)")
    fig.tight_layout()
    fig.savefig(figures / "psf_ecdf.png", dpi=160)
    fig.savefig(figures / "psf_ecdf.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for model in CONFIG_ORDER:
        pts = [item for item in source["token_steps"] if item["configuration"] == model]
        ax.scatter(
            [item["steps"] for item in pts if item["final_pass"]],
            [item["tokens"] for item in pts if item["final_pass"]],
            s=12,
            alpha=0.7,
            label=f"{DISPLAY[model]} pass",
        )
        ax.scatter(
            [item["steps"] for item in pts if not item["final_pass"]],
            [item["tokens"] for item in pts if not item["final_pass"]],
            s=12,
            alpha=0.4,
            marker="x",
            label=f"{DISPLAY[model]} fail",
        )
    ax.set_xlabel("Assistant steps")
    ax.set_ylabel("Total tokens")
    ax.legend(fontsize=6, ncol=2)
    ax.set_title("Token–steps (descriptive association only)")
    fig.tight_layout()
    fig.savefig(figures / "token_steps.png", dpi=160)
    fig.savefig(figures / "token_steps.pdf")
    plt.close(fig)
    return source


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "")].append(row)
    return grouped


def _truthy(value: Any) -> bool:
    return value in {True, "true", "True", "1", 1}


def _float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pooled_post(rows: list[dict[str, Any]]) -> float | None:
    posts = [_float(row.get("post_sufficiency_tokens")) for row in rows]
    totals = [_float(row.get("total_tokens")) for row in rows]
    if not posts or not totals or None in posts or None in totals:
        return None
    denom = sum(totals)  # type: ignore[arg-type]
    if not denom:
        return None
    return sum(posts) / denom  # type: ignore[arg-type]


def _fmt_iqr(med: float | None, q1: float | None, q3: float | None) -> str:
    if med is None:
        return "--"
    if q1 is None or q3 is None:
        return f"{med:.0f}"
    return f"{med:.0f} [{q1:.0f}, {q3:.0f}]"


def _fmt_psf(med: float | None, lo: float | None, hi: float | None) -> str:
    if med is None:
        return "--"
    pct = 100 * med
    if lo is None or hi is None:
        return f"{pct:.1f}%"
    return f"{pct:.1f}% [{100*lo:.1f}, {100*hi:.1f}]"


def _latex_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\caption{Offline post-sufficiency cost on the official Python-150 comparison. "
        r"PSF is $(T_{\mathrm{total}}-T^{*})/T_{\mathrm{total}}$ using provider input+output totals. "
        r"Included $n/N$ is the primary-analysis sample over official successes. "
        r"Empty cells (--) are configurations without an exact, jointly measurable T*.}",
        r"\label{tab:token-efficiency-candidate}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Configuration & Included successes $n/N$ & Median post-sufficiency tokens [IQR] & Median PSF [95\% CI] \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " {} & {} & {} & {} \\\\".format(
                row["Configuration"],
                row["Included successes n/N"],
                row["Median post-sufficiency tokens [IQR]"],
                row["Median PSF [95% CI]"].replace("%", r"\%"),
            )
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


def _methods_md(summary: list[dict[str, Any]]) -> str:
    return (
        "We retrospectively reconstruct each official Python-150 OpenHands run at "
        "tool-completion boundaries and evaluate every distinct submission tree with "
        "the frozen four-gate functional evaluator (build, public, hidden, isolation). "
        "The earliest sufficient artifact is the first reconstructed state that passes "
        "all four gates; T* is the cumulative provider input+output token total at that "
        "boundary. The post-sufficiency fraction (PSF) is (Ttotal − T*)/Ttotal on runs "
        "whose identity, final-tree re-evaluation, complete state chain, and token "
        "alignment are all exact, with Ttotal > 0. 95% CIs are task-level bootstrap "
        "percentile intervals (10,000 resamples, seed 20260916) of the per-run PSF "
        "median. This analysis is offline: no agent is re-invoked, and first-pass "
        "sufficiency is not a signal the original agent could observe.\n"
    )


def _results_md(summary: list[dict[str, Any]], readiness: dict[str, Any]) -> str:
    parts = [
        "Offline reconstruction of earliest sufficient artifacts on the official "
        "Python-150 comparison (150 tasks × 6 configurations) yields the following "
        "primary-analysis samples. Configurations without exact jointly measurable T* "
        "are reported as unavailable rather than estimated.",
        "",
    ]
    any_psf = False
    for row in summary:
        model = row["configuration"]
        n = row["included_success_n"]
        n_off = row["official_success_n"]
        if n and row["median_psf"] is not None:
            any_psf = True
            if row["psf_ci_low"] is None or row["psf_ci_high"] is None:
                ci_text = "unavailable"
            else:
                ci_text = f"{100 * row['psf_ci_low']:.1f}–{100 * row['psf_ci_high']:.1f}"
            parts.append(
                f"{row['display']}: included {n}/{n_off} official successes; "
                f"median PSF {100 * row['median_psf']:.1f}% (95% CI {ci_text})."
            )
        else:
            reasons = readiness.get(model, {}).get("blocking_reasons") or ["not measurable"]
            parts.append(
                f"{row['display']}: primary PSF not reported ({n}/{n_off}); "
                f"blocking: {', '.join(str(item) for item in reasons[:4])}."
            )
    if not any_psf:
        parts.append(
            "No configuration currently has a non-empty exact primary PSF sample; "
            "effort and artifact-history coverage should be cited instead of PSF."
        )
    parts.append(
        "An offline first pass does not mean the original agent knew it was safe to stop."
    )
    return "\n".join(parts) + "\n"


def _figure_recipe() -> str:
    return (
        "Figure (candidate, not numbered in the paper).\n\n"
        "- Sample: primary PSF rows (`include_psf_primary=true`) per configuration.\n"
        "- x: PSF = (Ttotal − T*)/Ttotal in [0,1], displayed as percent if desired.\n"
        "- y: empirical CDF (cumulative proportion of included runs).\n"
        "- Series order: Pro, Flash, Luna, GLM, Qwen, OSS.\n"
        "- Caption sketch: Empirical CDF of post-sufficiency token fraction on official "
        "successes with exact T*. Offline reconstruction; the agent did not observe the private evaluator.\n"
        "- Redraw from `figures/psf_ecdf.json` or `paper_ready/figure_source.json`.\n"
        "- The token–steps scatter is exploratory and is not required in the paper.\n"
    )


def _report_md(summary: list[dict[str, Any]], readiness: dict[str, Any]) -> str:
    lines = ["# Token efficiency report", "", "Per-configuration summary (do not pool first).", ""]
    for row in summary:
        lines.append(
            f"## {row['display']}\n\n"
            f"- assigned {row['assigned_n']}, official successes {row['official_success_n']}\n"
            f"- primary PSF n={row['included_success_n']}, exact={row['exact_n']}, "
            f"bounded={row['bounded_n']}, never_sufficient={row['never_sufficient_n']}, "
            f"unresolved={row['unresolved_n']}\n"
            f"- median PSF={row['median_psf']}, CI=({row['psf_ci_low']}, {row['psf_ci_high']})\n"
            f"- PSF ready: {readiness.get(row['configuration'], {}).get('psf_ready')}\n"
        )
    lines.append(
        "This report does not modify original experiment labels. "
        "PSF is not a ranking of models after controlling task composition.\n"
    )
    return "\n".join(lines)

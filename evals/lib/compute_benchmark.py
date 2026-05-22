#!/usr/bin/env python3
"""Aggregate grading.json files from an iteration into benchmark.json.

Handles both layouts:
  Flat (--repeat=1, default):    iter-N/eval-K/{with,without}_skill/grading.json
  Nested (--repeat>1):           iter-N/eval-K/{with,without}_skill/run-J/grading.json

For each (eval, config) pair, collects pass_rate, tokens, duration, and failed
commands across however many runs are present. Reports both mean+stddev (for
back-compat with the HTML report) and median+IQR (robust for small N).

Usage: python3 evals/lib/compute_benchmark.py <iteration-dir>
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import statistics
import sys

EXIT_PATTERN = re.compile(r"\[exit (\d+)]")
TIMEOUT_PATTERN = re.compile(r"\[timed out after")
ERROR_PATTERN = re.compile(r"\[error:")


def stats(values: list[float | None]) -> dict:
    """Return mean+stddev+median+IQR for a list of values."""
    values = [v for v in values if v is not None]
    if not values:
        return {"mean": None, "stddev": None, "median": None, "iqr": [None, None], "n": 0}
    n = len(values)
    mu = sum(values) / n
    variance = sum((x - mu) ** 2 for x in values) / n if n > 1 else 0.0
    median = statistics.median(values)
    if n >= 4:
        q1, q3 = statistics.quantiles(values, n=4)[0], statistics.quantiles(values, n=4)[2]
    else:
        # Small-N fallback: use min/max as IQR endpoints so the field is always populated
        q1, q3 = min(values), max(values)
    return {
        "mean": round(mu, 4),
        "stddev": round(math.sqrt(variance), 4),
        "median": round(median, 4),
        "iqr": [round(q1, 4), round(q3, 4)],
        "n": n,
    }


def count_failed_commands(transcript_path: str) -> dict:
    """Return {total_commands, failed_commands} from a transcript.json."""
    try:
        with open(transcript_path) as f:
            messages = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"total_commands": 0, "failed_commands": 0}

    total = 0
    failed = 0
    for msg in messages:
        if msg.get("role") == "tool":
            total += 1
            result = msg.get("content", "")
            if (
                EXIT_PATTERN.search(result)
                or TIMEOUT_PATTERN.search(result)
                or ERROR_PATTERN.search(result)
            ):
                failed += 1
    return {"total_commands": total, "failed_commands": failed}


def find_run_dirs(eval_dir: str, config: str) -> list[str]:
    """Return list of run directories for one (eval, config). Handles both layouts."""
    config_dir = os.path.join(eval_dir, config)
    if not os.path.isdir(config_dir):
        return []
    nested = sorted(glob.glob(os.path.join(config_dir, "run-*")))
    if nested:
        return [d for d in nested if os.path.isdir(d)]
    # Flat layout: the config dir itself is the run dir
    return [config_dir]


def collect_run(run_dir: str) -> dict | None:
    """Extract one data point from a single run directory. None if grading missing."""
    grading_path = os.path.join(run_dir, "grading.json")
    if not os.path.exists(grading_path):
        return None

    with open(grading_path) as f:
        g = json.load(f)
    point = {"pass_rate": g["summary"]["pass_rate"]}

    timing_path = os.path.join(run_dir, "timing.json")
    if os.path.exists(timing_path):
        with open(timing_path) as f:
            t = json.load(f)
        point["tokens"] = t.get("total_tokens", 0)
        point["duration_s"] = t.get("duration_ms", 0) / 1000
    else:
        point["tokens"] = 0
        point["duration_s"] = 0.0

    raw_path = os.path.join(run_dir, "raw_output.json")
    attribution = {}
    usage = {}
    if os.path.exists(raw_path):
        try:
            with open(raw_path) as f:
                raw = json.load(f)
            attribution = raw.get("token_attribution", {}) or {}
            usage = raw.get("usage", {}) or {}
        except (OSError, json.JSONDecodeError):
            attribution = {}
            usage = {}

    has_attribution = bool(attribution)
    input_tokens = attribution.get("input_tokens", usage.get("input_tokens", 0)) or 0
    output_tokens = attribution.get("output_tokens", usage.get("output_tokens", 0)) or 0
    task_tokens = attribution.get("task_tokens_estimated") if has_attribution else None
    eval_overhead_tokens = attribution.get("eval_overhead_tokens_estimated") if has_attribution else None
    eval_overhead_ratio = attribution.get("eval_overhead_ratio") if has_attribution else None

    categories = attribution.get("input_categories_estimated", {}) or {}
    point["input_tokens"] = input_tokens
    point["output_tokens"] = output_tokens
    point["task_tokens"] = task_tokens
    point["eval_overhead_tokens"] = eval_overhead_tokens
    point["eval_overhead_ratio"] = eval_overhead_ratio
    point["system_prompt_tokens"] = categories.get("system_prompt") if has_attribution else None
    point["harness_prompt_tokens"] = categories.get("harness_prompt") if has_attribution else None
    point["tool_schema_tokens"] = categories.get("tool_schema") if has_attribution else None
    point["assistant_history_tokens"] = categories.get("assistant_history") if has_attribution else None
    point["tool_result_tokens"] = categories.get("tool_results") if has_attribution else None
    point["provider_protocol_residual_tokens"] = categories.get("provider_protocol_residual") if has_attribution else None

    cmd_counts = count_failed_commands(os.path.join(run_dir, "transcript.json"))
    point["failed_commands"] = cmd_counts["failed_commands"]
    point["total_commands"] = cmd_counts["total_commands"]
    return point


def collect_eval(eval_dir: str, config: str) -> list[dict]:
    """All run data points for one (eval, config)."""
    points = []
    for run_dir in find_run_dirs(eval_dir, config):
        p = collect_run(run_dir)
        if p is not None:
            points.append(p)
    return points


def summarize(points: list[dict]) -> dict:
    """Compute stats across a set of run data points."""
    return {
        "pass_rate":                         stats([p["pass_rate"]       for p in points]),
        "time_seconds":                      stats([p["duration_s"]      for p in points]),
        "tokens":                            stats([p["tokens"]          for p in points]),
        "input_tokens":                      stats([p["input_tokens"]    for p in points]),
        "output_tokens":                     stats([p["output_tokens"]   for p in points]),
        "task_tokens":                       stats([p["task_tokens"]     for p in points]),
        "eval_overhead_tokens":              stats([p["eval_overhead_tokens"] for p in points]),
        "eval_overhead_ratio":               stats([p["eval_overhead_ratio"]  for p in points]),
        "system_prompt_tokens":              stats([p["system_prompt_tokens"]              for p in points]),
        "harness_prompt_tokens":             stats([p["harness_prompt_tokens"]             for p in points]),
        "tool_schema_tokens":                stats([p["tool_schema_tokens"]                for p in points]),
        "assistant_history_tokens":          stats([p["assistant_history_tokens"]          for p in points]),
        "tool_result_tokens":                stats([p["tool_result_tokens"]                for p in points]),
        "provider_protocol_residual_tokens": stats([p["provider_protocol_residual_tokens"] for p in points]),
        "failed_commands":                   stats([p["failed_commands"] for p in points]),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: compute_benchmark.py <iteration-dir>", file=sys.stderr)
        sys.exit(1)

    iter_dir = sys.argv[1]
    eval_dirs = sorted(glob.glob(os.path.join(iter_dir, "eval-*")))

    # Pool every run across every eval for the overall summary; also keep
    # per-eval breakdowns so noisy evals can be identified.
    pool = {"with_skill": [], "without_skill": []}
    per_eval = []

    for eval_dir in eval_dirs:
        if not os.path.isdir(eval_dir):
            continue
        eval_id = os.path.basename(eval_dir).removeprefix("eval-")

        with_points    = collect_eval(eval_dir, "with_skill")
        without_points = collect_eval(eval_dir, "without_skill")

        pool["with_skill"].extend(with_points)
        pool["without_skill"].extend(without_points)

        per_eval.append({
            "eval_id": eval_id,
            "with_skill":    summarize(with_points),
            "without_skill": summarize(without_points),
            "n_runs_with":    len(with_points),
            "n_runs_without": len(without_points),
        })

    with_summary    = summarize(pool["with_skill"])
    without_summary = summarize(pool["without_skill"])

    def delta(metric: str, decimals: int) -> float | None:
        with_median = with_summary[metric]["median"]
        without_median = without_summary[metric]["median"]
        if with_median is None or without_median is None:
            return None
        return round(with_median - without_median, decimals)

    benchmark = {
        "run_summary": {
            "with_skill":    with_summary,
            "without_skill": without_summary,
            "delta": {
                "pass_rate":       delta("pass_rate", 4),
                "time_seconds":    delta("time_seconds", 2),
                "tokens":          delta("tokens", 0),
                "task_tokens":     delta("task_tokens", 0),
                "eval_overhead_tokens": delta("eval_overhead_tokens", 0),
                "eval_overhead_ratio":  delta("eval_overhead_ratio", 4),
                "failed_commands": delta("failed_commands", 2),
            },
        },
        "per_eval": per_eval,
    }

    out_path = os.path.join(iter_dir, "benchmark.json")
    with open(out_path, "w") as f:
        json.dump(benchmark, f, indent=2)

    print(json.dumps(benchmark, indent=2))


if __name__ == "__main__":
    main()

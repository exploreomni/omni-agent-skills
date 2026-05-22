#!/usr/bin/env python3
"""Flatten evals/results/<skill>/*.json into a single CSV for BI tools.

Walks every published iteration file (produced by scorer.sh) and emits one row
per (skill, iteration, model, config) — so each scorer run contributes 2 rows
per skill (with_skill, without_skill). The delta is recoverable in the BI tool
by pivoting on the `config` column.

Usage:
  python3 evals/lib/publish.py [output.csv]

Default output: evals/results/eval_results_summary.csv (overwrites).

Safe to share: the resulting CSV contains only aggregated stats and
provenance — no agent prose, no transcripts, no tool-call outputs.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

EVALS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(EVALS_DIR, "results")


def get(d: dict, path: str, default=None):
    """Safe nested lookup: get(obj, 'meta.provenance.git.commit')."""
    cur = d
    for key in path.split("."):
        if cur is None or not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def row_for_config(rec: dict, config: str) -> dict:
    """Build one CSV row for a (skill, iteration, model, config) tuple."""
    rs = get(rec, f"run_summary.{config}", {}) or {}
    meta = rec.get("meta", {}) or {}
    prov = meta.get("provenance", {}) or {}
    git = prov.get("git", {}) or {}

    pr = rs.get("pass_rate", {})  or {}
    ts = rs.get("time_seconds", {}) or {}
    tk = rs.get("tokens", {})       or {}
    it = rs.get("input_tokens", {}) or {}
    ot = rs.get("output_tokens", {}) or {}
    task = rs.get("task_tokens", {}) or {}
    eval_overhead = rs.get("eval_overhead_tokens", {}) or {}
    eval_overhead_ratio = rs.get("eval_overhead_ratio", {}) or {}
    fc = rs.get("failed_commands", {}) or {}

    iteration = meta.get("iteration")
    model_slug = meta.get("model_slug", "")
    skill = meta.get("skill", "")
    run_id = f"{skill}/iter-{iteration}-{model_slug}/{config}"

    return {
        "run_id":              run_id,
        "skill":               skill,
        "iteration":           iteration,
        "config":              config,
        "model":               meta.get("model"),
        "model_slug":          model_slug,
        "provider":            meta.get("provider"),
        "reasoning_effort":    meta.get("reasoning_effort"),
        "repeat_n":            meta.get("repeat"),
        "run_date":            meta.get("run_date"),

        "pass_rate_mean":      pr.get("mean"),
        "pass_rate_stddev":    pr.get("stddev"),
        "pass_rate_median":    pr.get("median"),
        "pass_rate_iqr_low":   (pr.get("iqr") or [None, None])[0],
        "pass_rate_iqr_high":  (pr.get("iqr") or [None, None])[1],
        "pass_rate_n":         pr.get("n"),

        "time_seconds_mean":   ts.get("mean"),
        "time_seconds_median": ts.get("median"),

        "tokens_mean":         tk.get("mean"),
        "tokens_median":       tk.get("median"),
        "input_tokens_mean":   it.get("mean"),
        "input_tokens_median": it.get("median"),
        "output_tokens_mean":  ot.get("mean"),
        "output_tokens_median": ot.get("median"),
        "task_tokens_mean":    task.get("mean"),
        "task_tokens_median":  task.get("median"),
        "eval_overhead_tokens_mean":   eval_overhead.get("mean"),
        "eval_overhead_tokens_median": eval_overhead.get("median"),
        "eval_overhead_ratio_mean":    eval_overhead_ratio.get("mean"),
        "eval_overhead_ratio_median":  eval_overhead_ratio.get("median"),

        "failed_commands_mean":   fc.get("mean"),
        "failed_commands_median": fc.get("median"),

        "git_commit":          git.get("commit"),
        "git_branch":          git.get("branch"),
        "git_dirty":           git.get("dirty"),
        "plugin_version":      prov.get("plugin_version"),
        "skill_md_sha256":     prov.get("skill_md_sha256"),
        "evals_json_sha256":   prov.get("evals_json_sha256"),
        "cli_baseline_sha256": prov.get("cli_baseline_sha256"),
    }


COLUMNS = list(row_for_config({}, "with_skill").keys())


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RESULTS_DIR, "eval_results_summary.csv")

    pattern = os.path.join(RESULTS_DIR, "*", "iteration-*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No published results found under {RESULTS_DIR}/*/iteration-*.json", file=sys.stderr)
        print("Did you run ./evals/scorer.sh yet?", file=sys.stderr)
        sys.exit(1)

    rows = []
    for path in files:
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: skipping {path}: {exc}", file=sys.stderr)
            continue

        for config in ("with_skill", "without_skill"):
            if get(rec, f"run_summary.{config}") is None:
                continue
            rows.append(row_for_config(rec, config))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows from {len(files)} iteration files → {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Flatten BenchFlow eval summaries for trend reporting."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOBS_DIR = ROOT / "evals" / "workspaces" / "benchflow"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def parse_score(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


def parse_run_started_at(run_dir: Path) -> str:
    try:
        return datetime.strptime(run_dir.name, "%Y-%m-%d__%H-%M-%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return run_dir.name


def mode_row(summary_path: Path, combined: dict[str, Any], mode: str, summary: dict[str, Any]) -> dict[str, Any]:
    run_dir = summary_path.parent
    return {
        "run_started_at": parse_run_started_at(run_dir),
        "skill_name": combined.get("skill_name", run_dir.parent.name),
        "mode": mode,
        "agent": summary.get("agent", combined.get("agent")),
        "model": summary.get("model", combined.get("model")),
        "sandbox": summary.get("environment", combined.get("sandbox")),
        "cases": ",".join(str(c) for c in combined.get("cases", [])),
        "total": summary.get("total"),
        "passed": summary.get("passed"),
        "failed": summary.get("failed"),
        "errored": summary.get("errored"),
        "verifier_errored": summary.get("verifier_errored"),
        "score": summary.get("score"),
        "score_pct": parse_score(summary.get("score")),
        "elapsed_sec": summary.get("elapsed_sec"),
        "total_input_tokens": summary.get("total_input_tokens"),
        "total_output_tokens": summary.get("total_output_tokens"),
        "total_cache_read_tokens": summary.get("total_cache_read_tokens"),
        "total_cache_creation_tokens": summary.get("total_cache_creation_tokens"),
        "total_tokens": summary.get("total_tokens"),
        "total_cost_usd": summary.get("total_cost_usd"),
        "job_dir": combined.get("job_dir", str(run_dir)),
    }


def collect_rows(jobs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(jobs_dir.glob("*/*/summary.json")):
        combined = load_json(summary_path)
        if not combined.get("with_skill") and "score" in combined:
            continue
        for mode, key in (("with_skill", "with_skill"), ("baseline", "baseline")):
            summary = combined.get(key)
            if isinstance(summary, dict):
                rows.append(mode_row(summary_path, combined, mode, summary))
        if isinstance(combined.get("lift_score_points"), (int, float)):
            rows.append(
                {
                    "run_started_at": parse_run_started_at(summary_path.parent),
                    "skill_name": combined.get("skill_name", summary_path.parent.parent.name),
                    "mode": "lift",
                    "agent": combined.get("agent"),
                    "model": combined.get("model"),
                    "sandbox": combined.get("sandbox"),
                    "cases": ",".join(str(c) for c in combined.get("cases", [])),
                    "score_pct": combined.get("lift_score_points"),
                    "job_dir": combined.get("job_dir", str(summary_path.parent)),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    parser.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    args = parser.parse_args()

    rows = collect_rows(args.jobs_dir)
    if args.format == "jsonl":
        for row in rows:
            print(json.dumps(row, sort_keys=True))
        return

    fieldnames = [
        "run_started_at",
        "skill_name",
        "mode",
        "agent",
        "model",
        "sandbox",
        "cases",
        "total",
        "passed",
        "failed",
        "errored",
        "verifier_errored",
        "score",
        "score_pct",
        "elapsed_sec",
        "total_input_tokens",
        "total_output_tokens",
        "total_cache_read_tokens",
        "total_cache_creation_tokens",
        "total_tokens",
        "total_cost_usd",
        "job_dir",
    ]
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()

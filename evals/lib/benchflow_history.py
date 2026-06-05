#!/usr/bin/env python3
"""Flatten BenchFlow eval summaries for trend reporting."""

from __future__ import annotations

import argparse
import csv
import functools
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT / "evals"
DEFAULT_JOBS_DIR = EVALS_DIR / "workspaces" / "benchflow"
TOKEN_PENALTY_FREE_PER_CASE = 1_000_000
TOKEN_PENALTY_STEP = 250_000
MAX_TOKEN_PENALTY_PCT = 20.0
TIMEOUT_PENALTY_PCT = 5.0
MAX_TIMEOUT_PENALTY_PCT = 20.0


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


@functools.lru_cache(maxsize=None)
def env_local_url() -> str | None:
    env_local = EVALS_DIR / ".env.local"
    if not env_local.exists():
        return None
    for raw in env_local.read_text().splitlines():
        line = raw.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "OMNI_BASE_URL":
            return value.strip().strip('"').strip("'")
    return None


_git_sha_cache: dict[str, str | None] = {}


def git_sha_at(timestamp_str: str) -> str | None:
    if timestamp_str in _git_sha_cache:
        return _git_sha_cache[timestamp_str]
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H", f"--before={timestamp_str}", "-1"],
            capture_output=True, text=True, cwd=ROOT, timeout=5,
        )
        sha = result.stdout.strip()
        value = sha if result.returncode == 0 and sha else None
    except (OSError, subprocess.TimeoutExpired):
        value = None
    _git_sha_cache[timestamp_str] = value
    return value


def workspace_version(run_dir: Path, skill_name: str) -> str | None:
    evals_path = run_dir / "_generated" / skill_name / "evals" / "evals.json"
    data = load_json(evals_path)
    v = data.get("version")
    return str(v) if v is not None else None


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


def parse_run_started_dt(run_dir: Path) -> datetime | None:
    try:
        return datetime.strptime(run_dir.name, "%Y-%m-%d__%H-%M-%S")
    except ValueError:
        return None


def parse_duration_sec(result: dict[str, Any]) -> float | None:
    try:
        started = datetime.fromisoformat(str(result["started_at"]))
        finished = datetime.fromisoformat(str(result["finished_at"]))
    except (KeyError, ValueError):
        return None
    return (finished - started).total_seconds()


def reward_value(result: dict[str, Any]) -> float:
    value = (result.get("rewards") or {}).get("reward")
    return float(value) if isinstance(value, (int, float)) else 0.0


def result_stats(job_dir: Path, mode: str) -> dict[str, Any]:
    mode_dir = "with-skill" if mode == "with_skill" else mode
    results_dir = job_dir / "jobs" / mode_dir
    best_by_task: dict[str, dict[str, Any]] = {}
    for result_path in sorted(results_dir.rglob("result.json")):
        result = load_json(result_path)
        task_name = str(result.get("task_name") or result_path.parent.name)
        previous = best_by_task.get(task_name)
        if previous is None or reward_value(result) > reward_value(previous):
            best_by_task[task_name] = result

    results = list(best_by_task.values())
    if not results:
        return {}

    durations = [value for result in results if (value := parse_duration_sec(result)) is not None]
    total_tool_calls = sum(int(result.get("n_tool_calls") or 0) for result in results)
    total_prompts = sum(int(result.get("n_prompts") or 0) for result in results)
    timeout_count = sum(
        1
        for result in results
        if "wall-clock budget" in str(result.get("error") or "")
    )
    case_count = len(results)

    return {
        "total_tool_calls": total_tool_calls,
        "avg_tool_calls": round(total_tool_calls / case_count, 4),
        "total_prompts": total_prompts,
        "avg_prompts": round(total_prompts / case_count, 4),
        "avg_case_duration_sec": round(sum(durations) / len(durations), 4) if durations else None,
        "timeout_count": timeout_count,
    }


def per_case(value: Any, total: Any) -> float | None:
    if not isinstance(value, (int, float)) or not isinstance(total, int) or total <= 0:
        return None
    return round(value / total, 4)


def efficiency_penalty_pct(total_tokens: Any, total: Any, timeout_count: Any) -> float:
    penalty = 0.0
    tokens_per_case = per_case(total_tokens, total)
    if tokens_per_case and tokens_per_case > TOKEN_PENALTY_FREE_PER_CASE:
        overage = tokens_per_case - TOKEN_PENALTY_FREE_PER_CASE
        penalty += min(MAX_TOKEN_PENALTY_PCT, overage / TOKEN_PENALTY_STEP)
    if isinstance(timeout_count, int) and timeout_count > 0:
        penalty += min(MAX_TIMEOUT_PENALTY_PCT, timeout_count * TIMEOUT_PENALTY_PCT)
    return round(penalty, 4)


def adjusted_score_pct(score_pct: Any, penalty_pct: float) -> float | None:
    if not isinstance(score_pct, (int, float)):
        return None
    return round(max(0.0, score_pct - penalty_pct), 4)


@dataclass
class SummaryRecord:
    path: Path
    combined: dict[str, Any]
    run_id: str


def legacy_run_ids(summary_paths: list[Path]) -> dict[Path, str]:
    """Group older per-skill summaries that were started by the same `all` run."""
    parsed = [
        (path, parse_run_started_dt(path.parent))
        for path in summary_paths
    ]
    parsed.sort(key=lambda item: item[1] or datetime.min)

    grouped: dict[Path, str] = {}
    current: list[tuple[Path, datetime | None]] = []

    def flush() -> None:
        if not current:
            return
        starts = [dt for _, dt in current if dt is not None]
        if starts:
            run_id = "legacy-" + min(starts).strftime("%Y%m%dT%H%M%S")
        else:
            run_id = "legacy-" + current[0][0].parent.name
        for path, _ in current:
            grouped[path] = run_id

    for path, started_at in parsed:
        if current:
            previous = current[-1][1]
            if previous is None or started_at is None or (started_at - previous).total_seconds() > 30:
                flush()
                current = []
        current.append((path, started_at))
    flush()
    return grouped


def load_summary_records(jobs_dir: Path) -> list[SummaryRecord]:
    summary_paths = sorted(jobs_dir.glob("*/*/summary.json"))
    legacy_ids = legacy_run_ids(summary_paths)
    records: list[SummaryRecord] = []
    for summary_path in summary_paths:
        combined = load_json(summary_path)
        if not combined.get("with_skill") and "score" in combined:
            continue
        run_id = str(combined.get("run_id") or legacy_ids.get(summary_path) or summary_path.parent.name)
        records.append(SummaryRecord(summary_path, combined, run_id))
    return records


def mode_row(record: SummaryRecord, mode: str, summary: dict[str, Any]) -> dict[str, Any]:
    summary_path = record.path
    combined = record.combined
    run_dir = summary_path.parent
    total = summary.get("total")
    passed = summary.get("passed")
    total_tokens = summary.get("total_tokens")
    stats = result_stats(run_dir, mode)
    score_pct = parse_score(summary.get("score"))
    penalty_pct = efficiency_penalty_pct(total_tokens, total, stats.get("timeout_count"))
    return {
        "run_id": record.run_id,
        "run_started_at": parse_run_started_at(run_dir),
        "skill_name": combined.get("skill_name", run_dir.parent.name),
        "mode": mode,
        "agent": summary.get("agent", combined.get("agent")),
        "model": summary.get("model", combined.get("model")),
        "sandbox": summary.get("environment", combined.get("sandbox")),
        "branch": combined.get("branch"),
        "git_sha": combined.get("git_sha") or git_sha_at(parse_run_started_at(run_dir)),
        "version": combined.get("version") or workspace_version(run_dir, combined.get("skill_name", run_dir.parent.name)),
        "environment": combined.get("environment") or env_local_url(),
        "cases": ",".join(str(c) for c in combined.get("cases", [])),
        "total": summary.get("total"),
        "passed": summary.get("passed"),
        "failed": summary.get("failed"),
        "errored": summary.get("errored"),
        "verifier_errored": summary.get("verifier_errored"),
        "score": summary.get("score"),
        "score_pct": score_pct,
        "efficiency_adjusted_score_pct": adjusted_score_pct(score_pct, penalty_pct),
        "efficiency_penalty_pct": penalty_pct,
        "elapsed_sec": summary.get("elapsed_sec"),
        "total_tool_calls": stats.get("total_tool_calls"),
        "avg_tool_calls": stats.get("avg_tool_calls"),
        "total_prompts": stats.get("total_prompts"),
        "avg_prompts": stats.get("avg_prompts"),
        "avg_case_duration_sec": stats.get("avg_case_duration_sec"),
        "timeout_count": stats.get("timeout_count"),
        "total_input_tokens": summary.get("total_input_tokens"),
        "total_output_tokens": summary.get("total_output_tokens"),
        "total_cache_read_tokens": summary.get("total_cache_read_tokens"),
        "total_cache_creation_tokens": summary.get("total_cache_creation_tokens"),
        "total_tokens": summary.get("total_tokens"),
        "tokens_per_case": per_case(total_tokens, total),
        "tokens_per_pass": per_case(total_tokens, passed),
        "total_cost_usd": summary.get("total_cost_usd"),
        "job_dir": combined.get("job_dir", str(run_dir)),
    }


def collect_rows(jobs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in load_summary_records(jobs_dir):
        summary_path = record.path
        combined = record.combined
        for mode, key in (("with_skill", "with_skill"), ("baseline", "baseline")):
            summary = combined.get(key)
            if isinstance(summary, dict):
                rows.append(mode_row(record, mode, summary))
        if isinstance(combined.get("lift_score_points"), (int, float)):
            rows.append(
                {
                    "run_id": record.run_id,
                    "run_started_at": parse_run_started_at(summary_path.parent),
                    "skill_name": combined.get("skill_name", summary_path.parent.parent.name),
                    "mode": "lift",
                    "agent": combined.get("agent"),
                    "model": combined.get("model"),
                    "sandbox": combined.get("sandbox"),
                    "branch": combined.get("branch"),
                    "git_sha": combined.get("git_sha") or git_sha_at(parse_run_started_at(summary_path.parent)),
                    "version": combined.get("version") or workspace_version(summary_path.parent, combined.get("skill_name", summary_path.parent.parent.name)),
                    "environment": combined.get("environment") or env_local_url(),
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
        "run_id",
        "run_started_at",
        "skill_name",
        "mode",
        "agent",
        "model",
        "sandbox",
        "branch",
        "git_sha",
        "version",
        "environment",
        "cases",
        "total",
        "passed",
        "failed",
        "errored",
        "verifier_errored",
        "score",
        "score_pct",
        "efficiency_adjusted_score_pct",
        "efficiency_penalty_pct",
        "elapsed_sec",
        "total_tool_calls",
        "avg_tool_calls",
        "total_prompts",
        "avg_prompts",
        "avg_case_duration_sec",
        "timeout_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_cache_read_tokens",
        "total_cache_creation_tokens",
        "total_tokens",
        "tokens_per_case",
        "tokens_per_pass",
        "total_cost_usd",
        "job_dir",
    ]
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()

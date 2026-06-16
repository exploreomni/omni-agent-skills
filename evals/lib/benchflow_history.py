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
CASE_NAME_MAX_LEN = 80


def rel_job_dir(combined: dict[str, Any], run_dir: Path) -> str:
    """Return job_dir relative to the repo root so history stays portable."""
    raw = combined.get("job_dir") or str(run_dir)
    try:
        return str(Path(raw).resolve().relative_to(ROOT))
    except ValueError:
        return raw


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


@functools.lru_cache(maxsize=None)
def case_names_for_skill(skill_name: str) -> dict[str, str]:
    """Return {case_id: truncated question} from the skill's source evals.json."""
    evals_path = ROOT / "skills" / skill_name / "evals" / "evals.json"
    data = load_json(evals_path)
    names: dict[str, str] = {}
    for case in data.get("cases", []):
        case_id = str(case.get("id", ""))
        question = str(case.get("question", "")).strip()
        names[case_id] = question[:CASE_NAME_MAX_LEN]
    return names


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


def per_case_results(job_dir: Path, mode: str) -> dict[str, dict[str, Any]]:
    """Return {case_id: per-case metrics} from result.json files."""
    mode_dir = "with-skill" if mode == "with_skill" else mode
    results_dir = job_dir / "jobs" / mode_dir
    best_by_task: dict[str, dict[str, Any]] = {}
    for result_path in sorted(results_dir.rglob("result.json")):
        result = load_json(result_path)
        task_name = str(result.get("task_name") or result_path.parent.name)
        previous = best_by_task.get(task_name)
        if previous is None or reward_value(result) > reward_value(previous):
            best_by_task[task_name] = result

    out: dict[str, dict[str, Any]] = {}
    for case_id, result in best_by_task.items():
        reward = (result.get("rewards") or {}).get("reward")
        ar = result.get("agent_result") or {}
        error = str(result.get("error") or "")
        out[case_id] = {
            "passed": bool(reward is not None and float(reward) >= 1.0),
            "score": float(reward) if reward is not None else None,
            "errored": bool(error),
            "timeout": "wall-clock budget" in error,
            "tool_calls": result.get("n_tool_calls"),
            "duration_sec": parse_duration_sec(result),
            "input_tokens": ar.get("n_input_tokens"),
            "output_tokens": ar.get("n_output_tokens"),
            "cache_read_tokens": ar.get("n_cache_read_tokens"),
            "cache_creation_tokens": ar.get("n_cache_creation_tokens"),
            "total_tokens": ar.get("total_tokens"),
        }
    return out


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


def mode_rows(record: SummaryRecord, mode: str, summary: dict[str, Any]) -> list[dict[str, Any]]:
    run_dir = record.path.parent
    combined = record.combined
    skill_name = combined.get("skill_name", run_dir.parent.name)
    run_started_at = parse_run_started_at(run_dir)
    names = case_names_for_skill(skill_name)
    results = per_case_results(run_dir, mode)
    shared = {
        "run_id": record.run_id,
        "run_started_at": run_started_at,
        "skill_name": skill_name,
        "mode": mode,
        "agent": summary.get("agent", combined.get("agent")),
        "model": summary.get("model", combined.get("model")),
        "sandbox": summary.get("environment", combined.get("sandbox")),
        "branch": combined.get("branch"),
        "git_sha": combined.get("git_sha") or git_sha_at(run_started_at),
        "version": combined.get("version") or workspace_version(run_dir, skill_name),
        "omni_cli_version": combined.get("omni_cli_version"),
        "environment": combined.get("environment") or env_local_url(),
        "job_dir": rel_job_dir(combined, run_dir),
    }
    rows = []
    for case_id in combined.get("cases", []):
        case_id_str = str(case_id)
        r = results.get(case_id_str, {})
        rows.append({
            **shared,
            "case_id": case_id_str,
            "case_name": names.get(case_id_str, ""),
            "passed": r.get("passed"),
            "score": r.get("score"),
            "errored": r.get("errored"),
            "timeout": r.get("timeout"),
            "tool_calls": r.get("tool_calls"),
            "duration_sec": r.get("duration_sec"),
            "input_tokens": r.get("input_tokens"),
            "output_tokens": r.get("output_tokens"),
            "cache_read_tokens": r.get("cache_read_tokens"),
            "cache_creation_tokens": r.get("cache_creation_tokens"),
            "total_tokens": r.get("total_tokens"),
        })
    return rows


def lift_rows(record: SummaryRecord) -> list[dict[str, Any]]:
    run_dir = record.path.parent
    combined = record.combined
    if not isinstance(combined.get("with_skill"), dict) or not isinstance(combined.get("baseline"), dict):
        return []
    skill_name = combined.get("skill_name", run_dir.parent.name)
    run_started_at = parse_run_started_at(run_dir)
    names = case_names_for_skill(skill_name)
    with_results = per_case_results(run_dir, "with_skill")
    base_results = per_case_results(run_dir, "baseline")
    shared = {
        "run_id": record.run_id,
        "run_started_at": run_started_at,
        "skill_name": skill_name,
        "mode": "lift",
        "agent": combined.get("agent"),
        "model": combined.get("model"),
        "sandbox": combined.get("sandbox"),
        "branch": combined.get("branch"),
        "git_sha": combined.get("git_sha") or git_sha_at(run_started_at),
        "version": combined.get("version") or workspace_version(run_dir, skill_name),
        "omni_cli_version": combined.get("omni_cli_version"),
        "environment": combined.get("environment") or env_local_url(),
        "job_dir": rel_job_dir(combined, run_dir),
    }
    rows = []
    for case_id in combined.get("cases", []):
        case_id_str = str(case_id)
        ws = with_results.get(case_id_str, {})
        bs = base_results.get(case_id_str, {})
        ws_score = ws.get("score")
        bs_score = bs.get("score")
        lift = round(ws_score - bs_score, 4) if ws_score is not None and bs_score is not None else None
        rows.append({
            **shared,
            "case_id": case_id_str,
            "case_name": names.get(case_id_str, ""),
            "score": lift,
        })
    return rows


def collect_rows(jobs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in load_summary_records(jobs_dir):
        combined = record.combined
        for mode, key in (("with_skill", "with_skill"), ("baseline", "baseline")):
            summary = combined.get(key)
            if isinstance(summary, dict):
                rows.extend(mode_rows(record, mode, summary))
        rows.extend(lift_rows(record))
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
        "case_id",
        "case_name",
        "mode",
        "agent",
        "model",
        "sandbox",
        "branch",
        "git_sha",
        "version",
        "omni_cli_version",
        "environment",
        "passed",
        "score",
        "errored",
        "timeout",
        "tool_calls",
        "duration_sec",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
        "total_tokens",
        "job_dir",
    ]
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()

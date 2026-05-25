#!/usr/bin/env python3
"""Export existing BenchFlow runner artifacts as GEPA-ready traces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOBS_DIR = ROOT / "evals" / "workspaces" / "benchflow"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def read_text(path: Path, limit: int | None) -> str:
    if not path.exists():
        return ""
    text = path.read_text(errors="replace")
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]..."


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "case"


def case_id_from_rollout_dir(path: Path) -> str:
    return path.name.split("__", 1)[0]


def reward_from_result(result: dict[str, Any]) -> float | None:
    value = (result.get("rewards") or {}).get("reward")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def best_result_dirs(job_dir: Path) -> list[Path]:
    """Return one result directory per case, preferring the highest reward."""
    candidates: dict[str, tuple[float, float, Path]] = {}
    result_paths = sorted({*job_dir.glob("*/result.json"), *job_dir.glob("*/*/result.json")})
    for result_path in result_paths:
        result_dir = result_path.parent
        case_id = case_id_from_rollout_dir(result_dir)
        result = load_json(result_path)
        reward = reward_from_result(result)
        score = reward if reward is not None else -1.0
        mtime = result_path.stat().st_mtime
        previous = candidates.get(case_id)
        if previous is None or (score, mtime) > (previous[0], previous[1]):
            candidates[case_id] = (score, mtime, result_dir)
    return [item[2] for item in sorted(candidates.values(), key=lambda item: item[2].name)]


def resolve_run_dir(value: str, jobs_dir: Path) -> Path:
    path = Path(value)
    if path.exists():
        return path

    parts = value.split("/")
    if len(parts) == 2:
        candidate = jobs_dir / parts[0] / parts[1]
        if candidate.exists():
            return candidate
    if len(parts) == 1:
        matches = sorted(jobs_dir.glob(f"*/{value}"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SystemExit(
                f"Run {value!r} matched multiple skills; pass skill/run or an absolute path."
            )
    raise SystemExit(f"Could not find run directory: {value}")


def mode_job_dir(run_dir: Path, mode: str, combined: dict[str, Any]) -> Path | None:
    summary = combined.get(mode.replace("-", "_"))
    if isinstance(summary, dict) and summary.get("job_name"):
        candidate = run_dir / "jobs" / mode / str(summary["job_name"])
        if candidate.exists():
            return candidate

    mode_root = run_dir / "jobs" / mode
    if not mode_root.exists():
        return None
    job_dirs = [path for path in mode_root.iterdir() if path.is_dir()]
    if len(job_dirs) == 1:
        return job_dirs[0]
    if job_dirs:
        return sorted(job_dirs, key=lambda path: path.stat().st_mtime, reverse=True)[0]
    return None


def skill_text_path(run_dir: Path, skill_name: str) -> Path:
    generated = run_dir / "_generated" / skill_name / "SKILL.md"
    if generated.exists():
        return generated
    return ROOT / "skills" / skill_name / "SKILL.md"


def task_case_path(run_dir: Path, mode: str, case_id: str) -> Path:
    return run_dir / "_tasks" / mode / case_id / "tests" / "case.json"


def file_ref(path: Path, run_dir: Path) -> str:
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)


def build_trace(
    *,
    run_dir: Path,
    mode: str,
    skill_name: str,
    skill_text: str,
    result_dir: Path,
    limits: dict[str, int | None],
    include_skill_text: bool,
) -> dict[str, Any]:
    result_path = result_dir / "result.json"
    result = load_json(result_path)
    case_id = str(result.get("task_name") or case_id_from_rollout_dir(result_dir))
    case_path = task_case_path(run_dir, mode, case_id)

    trace = {
        "schema_version": "omni-gepa-trace-v1",
        "source": {
            "run_dir": str(run_dir),
            "mode": mode,
            "skill_name": skill_name,
            "result_dir": file_ref(result_dir, run_dir),
        },
        "case_id": case_id,
        "agent": result.get("agent"),
        "model": result.get("model"),
        "with_skill": mode == "with-skill",
        "score": reward_from_result(result),
        "error": result.get("error"),
        "verifier_error": result.get("verifier_error"),
        "n_tool_calls": result.get("n_tool_calls"),
        "n_prompts": result.get("n_prompts"),
        "agent_result": result.get("agent_result"),
        "timing": result.get("timing") or load_json(result_dir / "timing.json"),
        "case": load_json(case_path),
        "prompts": load_json(result_dir / "prompts.json"),
        "result": result,
        "verifier": {
            "reward_text": read_text(result_dir / "verifier" / "reward.txt", limits["verifier"]),
            "stdout": read_text(result_dir / "verifier" / "test-stdout.txt", limits["verifier"]),
            "judge_result": load_json(result_dir / "verifier" / "judge_result.json"),
        },
        "trajectory": {
            "acp_jsonl": read_text(result_dir / "trajectory" / "acp_trajectory.jsonl", limits["trajectory"]),
            "llm_jsonl": read_text(result_dir / "trajectory" / "llm_trajectory.jsonl", limits["trajectory"]),
        },
        "agent_logs": {
            path.name: read_text(path, limits["agent_log"])
            for path in sorted((result_dir / "agent").glob("*.txt"))
        },
        "skill_file": "../skill.md",
        "files": {
            "case": file_ref(case_path, run_dir),
            "result": file_ref(result_path, run_dir),
            "prompts": file_ref(result_dir / "prompts.json", run_dir),
            "timing": file_ref(result_dir / "timing.json", run_dir),
            "verifier_stdout": file_ref(result_dir / "verifier" / "test-stdout.txt", run_dir),
            "acp_trajectory": file_ref(result_dir / "trajectory" / "acp_trajectory.jsonl", run_dir),
            "llm_trajectory": file_ref(result_dir / "trajectory" / "llm_trajectory.jsonl", run_dir),
        },
    }
    if include_skill_text:
        trace["skill_text"] = skill_text
    return trace


def export_gepa_traces(
    run_dir: Path,
    output_dir: Path | None = None,
    modes: list[str] | None = None,
    trajectory_limit: int | None = 120_000,
    verifier_limit: int | None = 40_000,
    agent_log_limit: int | None = 40_000,
    include_skill_text: bool = False,
) -> Path:
    """Export traces from an existing repo runner workspace.

    The exporter does not run BenchFlow. It reads artifacts already written by
    evals/runner.sh and emits one JSON file per case/mode plus a summary.
    """
    combined = load_json(run_dir / "summary.json")
    if not combined:
        raise FileNotFoundError(f"No summary.json found in {run_dir}")

    skill_name = str(combined.get("skill_name") or run_dir.parent.name)
    selected_modes = modes or ["with-skill"]
    out_dir = output_dir or run_dir / "gepa"
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    skill_path = skill_text_path(run_dir, skill_name)
    skill_text = read_text(skill_path, None)
    if skill_text:
        (out_dir / "skill.md").write_text(skill_text)

    limits = {
        "trajectory": trajectory_limit,
        "verifier": verifier_limit,
        "agent_log": agent_log_limit,
    }
    trace_records: list[dict[str, Any]] = []
    for mode in selected_modes:
        job_dir = mode_job_dir(run_dir, mode, combined)
        if job_dir is None:
            continue
        for result_dir in best_result_dirs(job_dir):
            trace = build_trace(
                run_dir=run_dir,
                mode=mode,
                skill_name=skill_name,
                skill_text=skill_text,
                result_dir=result_dir,
                limits=limits,
                include_skill_text=include_skill_text,
            )
            filename = f"{sanitize_filename(trace['case_id'])}-{mode}.json"
            trace_path = traces_dir / filename
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
            trace_records.append(
                {
                    "case_id": trace["case_id"],
                    "mode": mode,
                    "score": trace["score"],
                    "error": trace["error"],
                    "verifier_error": trace["verifier_error"],
                    "n_tool_calls": trace["n_tool_calls"],
                    "trace_file": str(trace_path.relative_to(out_dir)),
                    "result_dir": trace["source"]["result_dir"],
                }
            )

    summary = {
        "schema_version": "omni-gepa-export-v1",
        "source_run_dir": str(run_dir),
        "skill_name": skill_name,
        "agent": combined.get("agent"),
        "model": combined.get("model"),
        "sandbox": combined.get("sandbox"),
        "run_id": combined.get("run_id"),
        "cases": combined.get("cases", []),
        "modes": selected_modes,
        "trace_count": len(trace_records),
        "skill_file": "skill.md" if skill_text else None,
        "include_skill_text": include_skill_text,
        "source_summary": combined,
        "traces": trace_records,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return out_dir


def parse_limit(value: str) -> int | None:
    if value.lower() in {"none", "full", "unlimited"}:
        return None
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("limits must be non-negative or 'full'")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run",
        help=(
            "Existing runner workspace path, skill/timestamp, or unique timestamp "
            "under evals/workspaces/benchflow."
        ),
    )
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--mode",
        action="append",
        choices=("with-skill", "baseline"),
        help="Mode to export. Repeatable. Defaults to with-skill.",
    )
    parser.add_argument("--trajectory-limit", type=parse_limit, default=120_000)
    parser.add_argument("--verifier-limit", type=parse_limit, default=40_000)
    parser.add_argument("--agent-log-limit", type=parse_limit, default=40_000)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Do not truncate trajectory, verifier, or agent-log text.",
    )
    parser.add_argument(
        "--include-skill-text",
        action="store_true",
        help="Embed the full SKILL.md text in every trace. By default it is written once as skill.md.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_dir = resolve_run_dir(args.run, args.jobs_dir)
    out_dir = export_gepa_traces(
        run_dir=run_dir,
        output_dir=args.output_dir,
        modes=args.mode or ["with-skill"],
        trajectory_limit=None if args.full else args.trajectory_limit,
        verifier_limit=None if args.full else args.verifier_limit,
        agent_log_limit=None if args.full else args.agent_log_limit,
        include_skill_text=args.include_skill_text,
    )
    summary = load_json(out_dir / "summary.json")
    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "skill_name": summary.get("skill_name"),
                "trace_count": summary.get("trace_count"),
                "modes": summary.get("modes"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

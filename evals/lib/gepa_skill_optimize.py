# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "anthropic",
#   "benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main",
#   "gepa>=0.1.1,<0.2",
#   "litellm",
# ]
# ///
"""Experiment: optimize a real SKILL.md with GEPA and BenchFlow."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Any

import gepa.optimize_anything as oa
from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig

from benchflow_runner import (
    declared_files_by_case,
    load_dotenv,
    load_eval_env,
    materialize_skill,
    parse_kv,
    provider_agent_env,
    omni_agent_env,
    run_mode,
    stage_case_files,
)
from benchflow.skill_eval import generate_tasks, load_eval_dataset


ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT / "evals"
SKILLS_DIR = ROOT / "skills"


def read_text(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(errors="replace")
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]..."


def extract_candidate(value: str | dict[str, str]) -> str:
    if isinstance(value, dict):
        return str(value.get("skill_md") or next(iter(value.values()), "")).strip()
    text = str(value).strip()
    if text.startswith("---"):
        return text
    fenced = re.search(r"```(?:markdown|md|text)?\s*(.*?)```", text, re.DOTALL)
    return fenced.group(1).strip() if fenced else text


def validate_skill_md(skill: str, candidate: str) -> list[str]:
    issues: list[str] = []
    if not candidate.startswith("---"):
        issues.append("Missing YAML frontmatter at top of SKILL.md.")
    if f"name: {skill}" not in candidate:
        issues.append(f"Frontmatter must keep `name: {skill}`.")
    frontmatter_parts = candidate.split("---", 2)
    frontmatter = frontmatter_parts[1] if len(frontmatter_parts) > 2 else ""
    if "description:" not in frontmatter:
        issues.append("Frontmatter must include a description.")
    if len(candidate) < 500:
        issues.append("Candidate is too short to be a usable full SKILL.md.")
    return issues


def average_case_reward(jobs_dir: Path) -> float:
    rewards: list[float] = []
    for result_path in sorted(jobs_dir.glob("*/*/result.json")):
        result = json.loads(result_path.read_text())
        reward = result.get("rewards", {}).get("reward")
        if isinstance(reward, int | float):
            rewards.append(float(reward))
    if not rewards:
        return 0.0
    return sum(rewards) / len(rewards)


def selected_eval_cases(skill: str, case_ids: list[str]) -> list[dict[str, Any]]:
    evals_path = SKILLS_DIR / skill / "evals" / "evals.json"
    data = json.loads(evals_path.read_text())
    wanted = {str(case_id) for case_id in case_ids}
    return [case for case in data.get("cases", []) if str(case.get("id")) in wanted]


def collect_case_feedback(jobs_dir: Path) -> list[dict[str, Any]]:
    feedback: list[dict[str, Any]] = []
    for result_path in sorted(jobs_dir.glob("*/*/result.json")):
        result = json.loads(result_path.read_text())
        case_dir = result_path.parent
        verifier = read_text(case_dir / "verifier" / "test-stdout.txt", limit=2000)
        trajectory = read_text(case_dir / "trajectory" / "acp_trajectory.jsonl", limit=5000)
        feedback.append(
            {
                "case": result.get("task_name"),
                "reward": result.get("rewards", {}).get("reward"),
                "error": result.get("error"),
                "verifier_error": result.get("verifier_error"),
                "n_tool_calls": result.get("n_tool_calls"),
                "verifier": verifier,
                "trajectory_head": trajectory,
            }
        )
    return feedback


async def evaluate_candidate_async(candidate: str, args: argparse.Namespace, run_root: Path) -> tuple[float, dict[str, Any]]:
    run_id = f"candidate-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    root = run_root / run_id
    generated = root / "_generated" / args.skill
    tasks_root = root / "_tasks"
    jobs_root = root / "jobs"
    root.mkdir(parents=True, exist_ok=True)

    eval_env = load_eval_env()
    materialize_skill(
        args.skill,
        generated,
        args.case,
        eval_env,
        omni_env_hint=not args.no_omni_env_hint,
        timeout_sec=args.timeout_sec,
    )
    (generated / "SKILL.md").write_text(candidate + "\n")

    dataset = load_eval_dataset(generated)
    files_by_case = declared_files_by_case(generated)
    generate_tasks(dataset, tasks_root / "with-skill", with_skill=True)
    stage_case_files(generated, tasks_root / "with-skill", files_by_case)

    extra_env = parse_kv(args.agent_env)
    agent_env = provider_agent_env({**omni_agent_env(), **extra_env})
    agent_env.setdefault("BENCHFLOW_SKILL_NUDGE", args.skill_nudge)

    summary = await run_mode(
        label=f"{args.skill} gepa-candidate",
        tasks_dir=tasks_root / "with-skill",
        jobs_dir=jobs_root / "with-skill",
        agent=args.agent,
        model=args.model,
        sandbox=args.sandbox,
        concurrency=1,
        agent_env=agent_env,
        max_retries=args.max_retries,
        total_cases=len(dataset.cases),
        status_interval_sec=0,
    )
    feedback = collect_case_feedback(jobs_root / "with-skill")
    score = average_case_reward(jobs_root / "with-skill")
    side_info = {
        "run_dir": str(root),
        "eval_cases": selected_eval_cases(args.skill, args.case),
        "summary": summary,
        "feedback": feedback,
    }
    return score, side_info


def build_evaluator(args: argparse.Namespace, run_root: Path):
    def evaluator(candidate_value: str | dict[str, str]) -> tuple[float, dict[str, Any]]:
        candidate = extract_candidate(candidate_value)
        issues = validate_skill_md(args.skill, candidate)
        if issues:
            for issue in issues:
                oa.log(issue)
            oa.log(f"Candidate preview:\n{candidate[:1000]}")
            return 0.0, {"validation_errors": issues, "candidate_preview": candidate[:1000]}

        score, side_info = asyncio.run(evaluate_candidate_async(candidate, args, run_root))
        oa.log(f"BenchFlow score: {score}")
        oa.log("Eval case requirements:")
        oa.log(json.dumps(side_info["eval_cases"], indent=2)[:4000])
        oa.log(json.dumps(side_info["summary"], indent=2)[:3000])
        for item in side_info["feedback"]:
            oa.log(json.dumps(item, indent=2)[:7000])
        return score, side_info

    return evaluator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize a skill with GEPA using BenchFlow evals.")
    parser.add_argument("--skill", default="omni-ai-eval")
    parser.add_argument("--case", action="append", default=[], help="Eval case id to run; repeatable.")
    parser.add_argument("--agent", default=os.environ.get("EVAL_AGENT", "claude-agent-acp"))
    parser.add_argument("--model", default=os.environ.get("EVAL_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--sandbox", default=os.environ.get("EVAL_SANDBOX", "docker"))
    parser.add_argument("--agent-env", action="append", default=[])
    parser.add_argument("--skill-nudge", default=os.environ.get("BENCHFLOW_SKILL_NUDGE", "name"))
    parser.add_argument("--max-retries", type=int, default=int(os.environ.get("EVAL_MAX_RETRIES", "1")))
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=int(os.environ.get("EVAL_TIMEOUT_SEC", "1200")),
        help="Per-case wall-clock budget passed to materialize_skill. Matches benchflow_runner default.",
    )
    parser.add_argument("--max-metric-calls", type=int, default=2)
    parser.add_argument(
        "--reflection-model",
        default=os.environ.get("GEPA_REFLECTION_MODEL", "anthropic/claude-sonnet-4-6"),
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Run directory. Defaults to a timestamped directory under evals/workspaces/gepa-skill-optimize/.",
    )
    parser.add_argument("--no-omni-env-hint", action="store_true")
    return parser


def main() -> int:
    load_dotenv(EVALS_DIR / ".env.local")
    args = build_parser().parse_args()
    if not args.case:
        args.case = ["1"]

    if not os.environ.get("OMNI_BASE_URL") or not os.environ.get("OMNI_API_TOKEN"):
        raise SystemExit("Set OMNI_BASE_URL and OMNI_API_TOKEN in evals/.env.local or the environment.")
    if not os.environ.get("ANTHROPIC_API_KEY") and args.reflection_model.startswith("anthropic/"):
        raise SystemExit("Set ANTHROPIC_API_KEY for the configured Anthropic reflection model.")

    source = SKILLS_DIR / args.skill / "SKILL.md"
    seed = source.read_text()
    run_root = (
        ROOT / args.run_dir
        if args.run_dir
        else EVALS_DIR
        / "workspaces"
        / "gepa-skill-optimize"
        / args.skill
        / datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    )
    run_root.mkdir(parents=True, exist_ok=True)

    result = oa.optimize_anything(
        seed_candidate={"skill_md": seed},
        evaluator=build_evaluator(args, run_root),
        objective=(
            f"Improve the {args.skill} SKILL.md so an agent using it passes the selected "
            "BenchFlow eval cases. Keep the skill name and frontmatter valid, preserve "
            "correct Omni CLI commands, and make only changes justified by eval feedback. "
            "Pay close attention to each case's expected_behavior: the judge rewards those "
            "behaviors, not just whether the agent returns a plausible final answer."
        ),
        background=(
            "The artifact is a full Agent Skill markdown file. It must remain a drop-in "
            "replacement for SKILL.md. Prefer precise instruction changes over broad rewrites."
        ),
        config=GEPAConfig(
            engine=EngineConfig(
                run_dir=str(run_root / "gepa-state"),
                max_metric_calls=args.max_metric_calls,
                display_progress_bar=False,
                parallel=False,
                capture_stdio=True,
                use_cloudpickle=False,
            ),
            reflection=ReflectionConfig(
                reflection_lm=args.reflection_model,
                skip_perfect_score=False,
            ),
        ),
    )

    summary = {
        "skill": args.skill,
        "cases": args.case,
        "best_idx": result.best_idx,
        "best_score": result.val_aggregate_scores[result.best_idx],
        "total_metric_calls": result.total_metric_calls,
        "run_dir": str(run_root),
        "best_candidate_path": str(run_root / "best_SKILL.md"),
    }
    best = extract_candidate(result.best_candidate)
    (run_root / "best_SKILL.md").write_text(best + "\n")
    (run_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

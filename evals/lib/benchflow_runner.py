#!/usr/bin/env python3
"""Run Omni skill evals through BenchFlow."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from benchflow.evaluation import Evaluation, EvaluationConfig, RetryConfig
    from benchflow.skill_eval import generate_tasks, load_eval_dataset
except ImportError:
    print(
        "ERROR: benchflow is not installed. Install it with `uv tool install benchflow` "
        "or run through `./evals/runner.sh`, which can use uv.",
        file=sys.stderr,
    )
    raise


ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT / "evals"
SKILLS_DIR = ROOT / "skills"

OMNI_ENV_HINT = (
    "Omni credentials are available in environment variables OMNI_BASE_URL and "
    "OMNI_API_TOKEN. If `omni config show` fails because no CLI profile exists "
    "in the sandbox, use `--base-url \"$OMNI_BASE_URL\" --token \"$OMNI_API_TOKEN\"` "
    "with Omni CLI commands instead of asking for credentials."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines into os.environ without overriding exports."""
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_eval_env() -> dict[str, str]:
    path = EVALS_DIR / "eval-env.local.json"
    if not path.exists():
        path = EVALS_DIR / "eval-env.json"
    if not path.exists():
        return {}
    return {k: str(v) for k, v in load_json(path).items() if k != "_comment"}


def substitute_vars(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def parse_kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError(f"Expected non-empty KEY in {item!r}")
        out[key] = value
    return out


def discover_skills() -> list[str]:
    return sorted(
        path.parent.parent.name
        for path in SKILLS_DIR.glob("*/evals/evals.json")
        if path.is_file()
    )


def selected_cases(cases: list[dict[str, Any]], case_ids: list[str]) -> list[dict[str, Any]]:
    if not case_ids:
        return cases
    wanted = {str(case_id) for case_id in case_ids}
    return [case for case in cases if str(case.get("id")) in wanted]


def write_default_dockerfile(skill_dir: Path) -> None:
    dockerfile = skill_dir / "evals" / "Dockerfile"
    if dockerfile.exists():
        return
    dockerfile.write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "ENV DEBIAN_FRONTEND=noninteractive",
                "RUN apt-get update \\",
                "  && apt-get install -y --no-install-recommends bash ca-certificates curl jq \\",
                "  && rm -rf /var/lib/apt/lists/*",
                "RUN curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh",
                "RUN pip install -q anthropic openai google-genai",
                "COPY eval-files/ /app/evals/",
                "WORKDIR /app",
                "",
            ]
        )
    )


def materialize_skill(
    skill: str,
    output_dir: Path,
    case_ids: list[str],
    eval_env: dict[str, str],
    omni_env_hint: bool,
) -> Path:
    source_dir = SKILLS_DIR / skill
    evals_path = source_dir / "evals" / "evals.json"
    if not evals_path.exists():
        raise FileNotFoundError(f"No evals/evals.json for skill {skill!r}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(
        source_dir,
        output_dir,
        ignore=shutil.ignore_patterns("__pycache__", ".git", ".DS_Store"),
    )

    data = load_json(output_dir / "evals" / "evals.json")
    if "cases" not in data:
        raise ValueError(f"{evals_path} must use BenchFlow's `cases` schema")

    cases = selected_cases(data["cases"], case_ids)
    if not cases:
        raise ValueError(f"No eval cases selected for {skill}")

    converted_cases = []
    for case in cases:
        converted = dict(case)
        question = substitute_vars(str(converted.get("question", "")), eval_env)
        if omni_env_hint:
            question = f"{OMNI_ENV_HINT}\n\n{question}"
        converted["question"] = question
        converted["ground_truth"] = substitute_vars(
            str(converted.get("ground_truth", "")),
            eval_env,
        )
        converted["expected_behavior"] = [
            substitute_vars(str(item), eval_env)
            for item in converted.get("expected_behavior", [])
        ]
        converted_cases.append(converted)

    data["cases"] = converted_cases
    (output_dir / "evals" / "evals.json").write_text(json.dumps(data, indent=2) + "\n")
    eval_files_dir = output_dir / "evals" / "eval-files"
    eval_files_dir.mkdir(parents=True, exist_ok=True)
    write_default_dockerfile(output_dir)
    return output_dir


def declared_files_by_case(skill_dir: Path) -> dict[str, list[str]]:
    data = load_json(skill_dir / "evals" / "evals.json")
    return {
        str(case.get("id")): [str(path) for path in case.get("files", [])]
        for case in data.get("cases", [])
    }


def stage_case_files(skill_dir: Path, tasks_dir: Path, files_by_case: dict[str, list[str]]) -> None:
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue
        case_id = task_dir.name
        files = files_by_case.get(case_id, [])
        target_dir = tasks_dir / case_id / "environment" / "eval-files"
        target_dir.mkdir(parents=True, exist_ok=True)
        for rel in files:
            src = skill_dir / rel
            if not src.is_file():
                raise FileNotFoundError(f"Declared eval input file does not exist: {src}")
            shutil.copy2(src, target_dir / src.name)


def omni_agent_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if os.environ.get("OMNI_BASE_URL"):
        env["OMNI_BASE_URL"] = os.environ["OMNI_BASE_URL"]
    if os.environ.get("OMNI_API_TOKEN"):
        env["OMNI_API_TOKEN"] = os.environ["OMNI_API_TOKEN"]
    return {k: v for k, v in env.items() if v}


def provider_agent_env(extra_env: dict[str, str]) -> dict[str, str]:
    env = dict(extra_env)
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "CODEX_ACCESS_TOKEN",
        "AWS_BEARER_TOKEN_BEDROCK",
    ):
        if os.environ.get(key):
            env.setdefault(key, os.environ[key])
    return env


async def run_mode(
    *,
    tasks_dir: Path,
    jobs_dir: Path,
    agent: str,
    model: str,
    sandbox: str,
    concurrency: int,
    agent_env: dict[str, str],
    max_retries: int,
) -> dict[str, Any]:
    evaluation = Evaluation(
        tasks_dir=str(tasks_dir),
        jobs_dir=str(jobs_dir),
        config=EvaluationConfig(
            agent=agent,
            model=model,
            environment=sandbox,
            concurrency=concurrency,
            retry=RetryConfig(max_retries=max_retries),
            agent_env=agent_env,
        ),
    )
    await evaluation.run()
    summary_path = jobs_dir / "summary.json"
    return load_json(summary_path) if summary_path.exists() else {}


def score_value(summary: dict[str, Any]) -> float:
    value = str(summary.get("score", "0")).rstrip("%")
    try:
        return float(value)
    except ValueError:
        return 0.0


async def run_skill(skill: str, args: argparse.Namespace) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    root = Path(args.jobs_dir) / skill / stamp
    generated = root / "_generated" / skill
    tasks_root = root / "_tasks"
    jobs_root = root / "jobs"
    root.mkdir(parents=True, exist_ok=True)

    eval_env = load_eval_env()
    extra_env = parse_kv(args.agent_env)
    agent_env = provider_agent_env({**omni_agent_env(), **extra_env})
    agent_env.setdefault("BENCHFLOW_SKILL_NUDGE", args.skill_nudge)

    if not agent_env.get("OMNI_BASE_URL") or not agent_env.get("OMNI_API_TOKEN"):
        raise RuntimeError(
            "Omni credentials are missing. Configure omni-cli or set "
            "OMNI_BASE_URL and OMNI_API_TOKEN."
        )

    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        if agent_env.get(key):
            os.environ.setdefault(key, agent_env[key])

    materialize_skill(
        skill,
        generated,
        args.case,
        eval_env,
        omni_env_hint=not args.no_omni_env_hint,
    )
    dataset = load_eval_dataset(generated)
    files_by_case = declared_files_by_case(generated)
    generate_tasks(dataset, tasks_root / "with-skill", with_skill=True)
    stage_case_files(generated, tasks_root / "with-skill", files_by_case)
    if not args.no_baseline:
        generate_tasks(dataset, tasks_root / "baseline", with_skill=False)
        stage_case_files(generated, tasks_root / "baseline", files_by_case)

    print(f"\n{skill}: {len(dataset.cases)} case(s)")
    print(f"  jobs: {root}")

    with_summary = await run_mode(
        tasks_dir=tasks_root / "with-skill",
        jobs_dir=jobs_root / "with-skill",
        agent=args.agent,
        model=args.model,
        sandbox=args.sandbox,
        concurrency=args.concurrency,
        agent_env=agent_env,
        max_retries=args.max_retries,
    )
    print(
        "  with_skill: "
        f"{with_summary.get('score', 'n/a')} "
        f"({with_summary.get('passed', 0)}/{with_summary.get('total', 0)}) "
        f"tokens={with_summary.get('total_tokens', 0)}"
    )

    baseline_summary: dict[str, Any] | None = None
    if not args.no_baseline:
        baseline_summary = await run_mode(
            tasks_dir=tasks_root / "baseline",
            jobs_dir=jobs_root / "baseline",
            agent=args.agent,
            model=args.model,
            sandbox=args.sandbox,
            concurrency=args.concurrency,
            agent_env=agent_env,
            max_retries=args.max_retries,
        )
        print(
            "  baseline:   "
            f"{baseline_summary.get('score', 'n/a')} "
            f"({baseline_summary.get('passed', 0)}/{baseline_summary.get('total', 0)}) "
            f"tokens={baseline_summary.get('total_tokens', 0)}"
        )

    combined = {
        "skill_name": skill,
        "agent": args.agent,
        "model": args.model,
        "sandbox": args.sandbox,
        "cases": [case.id for case in dataset.cases],
        "job_dir": str(root),
        "with_skill": with_summary,
        "baseline": baseline_summary,
    }
    if baseline_summary is not None:
        combined["lift_score_points"] = round(
            score_value(with_summary) - score_value(baseline_summary),
            4,
        )
        print(f"  lift:       {combined['lift_score_points']:+.1f} points")

    (root / "summary.json").write_text(json.dumps(combined, indent=2) + "\n")
    return combined


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Omni skill evals through BenchFlow")
    parser.add_argument("skill", help="Skill name under skills/, or `all`")
    parser.add_argument("--agent", default=os.environ.get("EVAL_AGENT", "claude-agent-acp"))
    parser.add_argument("--model", default=os.environ.get("EVAL_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--sandbox", default=os.environ.get("EVAL_SANDBOX", "docker"))
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("EVAL_CONCURRENCY", "1")))
    parser.add_argument("--jobs-dir", default=str(EVALS_DIR / "workspaces" / "benchflow"))
    parser.add_argument("--case", action="append", default=[], help="Run only this case id; repeatable")
    parser.add_argument("--agent-env", action="append", default=[], help="Extra KEY=VALUE passed to the agent")
    parser.add_argument("--skill-nudge", default=os.environ.get("BENCHFLOW_SKILL_NUDGE", "name"))
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--no-omni-env-hint", action="store_true")
    return parser


async def async_main() -> None:
    load_dotenv(EVALS_DIR / ".env.local")
    args = build_parser().parse_args()
    skills = discover_skills() if args.skill == "all" else [args.skill]
    for skill in skills:
        await run_skill(skill, args)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

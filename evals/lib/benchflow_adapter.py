#!/usr/bin/env python3
"""Generate a BenchFlow skill-eval directory from this repo's eval schema."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_eval_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {k: str(v) for k, v in data.items() if k != "_comment"}


def substitute_vars(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def select_cases(cases: list[dict], case_ids: list[str], limit: int | None) -> list[dict]:
    if case_ids:
        wanted = {str(case_id) for case_id in case_ids}
        return [case for case in cases if str(case.get("id")) in wanted]
    if limit is not None:
        return cases[:limit]
    return cases


def copy_skill_source(skill_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ignore = shutil.ignore_patterns("evals", "__pycache__", ".git", ".DS_Store")
    shutil.copytree(skill_dir, output_dir, ignore=ignore)
    (output_dir / "evals").mkdir(parents=True, exist_ok=True)


def write_default_dockerfile(output_dir: Path) -> None:
    """Add a minimal eval image with Omni CLI and judge SDKs.

    BenchFlow appends the skill COPY step for with-skill runs.
    """
    dockerfile = output_dir / "evals" / "Dockerfile"
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
                "WORKDIR /app",
                "",
            ]
        )
    )


def convert(
    skill: str,
    output_dir: Path,
    case_ids: list[str],
    limit: int | None,
    judge_model: str,
    write_dockerfile: bool,
) -> None:
    skill_dir = ROOT / "skills" / skill
    source_evals = skill_dir / "evals" / "evals.json"
    if not source_evals.exists():
        raise FileNotFoundError(f"No evals/evals.json for skill: {skill}")

    data = json.loads(source_evals.read_text())
    env_path = ROOT / "evals" / "eval-env.local.json"
    if not env_path.exists():
        env_path = ROOT / "evals" / "eval-env.json"
    values = load_eval_env(env_path)

    source_cases = data.get("evals", [])
    cases = select_cases(source_cases, case_ids, limit)
    if not cases:
        raise ValueError("No eval cases selected")

    copy_skill_source(skill_dir, output_dir)

    converted = {
        "version": "1",
        "skill_name": data.get("skill_name", skill),
        "defaults": {
            "timeout_sec": 600,
            "judge_model": judge_model,
        },
        "cases": [],
    }
    for case in cases:
        converted["cases"].append(
            {
                "id": str(case.get("id")),
                "question": substitute_vars(case.get("prompt", ""), values),
                "ground_truth": substitute_vars(case.get("expected_output", ""), values),
                "expected_behavior": [
                    substitute_vars(assertion, values)
                    for assertion in case.get("assertions", [])
                ],
                "expected_skill": data.get("skill_name", skill),
            }
        )

    (output_dir / "evals" / "evals.json").write_text(
        json.dumps(converted, indent=2) + "\n"
    )
    if write_dockerfile:
        write_default_dockerfile(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="Skill name under skills/")
    parser.add_argument("output_dir", type=Path, help="Generated BenchFlow skill dir")
    parser.add_argument("--case", action="append", default=[], help="Eval id to include")
    parser.add_argument("--limit", type=int, help="Include the first N eval cases")
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="BenchFlow LLM judge model",
    )
    parser.add_argument(
        "--no-dockerfile",
        action="store_true",
        help="Do not write evals/Dockerfile",
    )
    args = parser.parse_args()

    convert(
        skill=args.skill,
        output_dir=args.output_dir,
        case_ids=args.case,
        limit=args.limit,
        judge_model=args.judge_model,
        write_dockerfile=not args.no_dockerfile,
    )


if __name__ == "__main__":
    main()

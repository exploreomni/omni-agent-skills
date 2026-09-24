#!/usr/bin/env python3
"""Tier 1 skill eval: does each eval question route to the skill that owns it?

This is the cheapest eval in the repo that still exercises a model. It shows
Claude nothing but the skill catalog — every `name` + `description` from
`skills/*/SKILL.md`, the same text an agent sees when deciding which skill to
load — and asks which skill handles the prompt. No Omni instance, no CLI, no
tool execution, no judge: one short classification call per sample.

The cases are the ones already in `skills/*/evals/evals.json`; `expected_skill`
is the label. What it catches is the regression a docs-sync PR actually causes:
a description edit that quietly steals another skill's prompts or loses its own.

Usage:
    python3 evals/ci/routing_eval.py                     # all skills
    python3 evals/ci/routing_eval.py --skill omni-query  # one skill
    python3 evals/ci/routing_eval.py --update-baselines  # re-record baselines

Needs an Anthropic credential (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
`ant auth login` profile). Exits non-zero when accuracy falls below the gates in
evals/ci/baselines.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
EVALS_DIR = ROOT / "evals"
BASELINES_PATH = Path(__file__).resolve().parent / "baselines.json"

DEFAULT_MODEL = "claude-sonnet-5"

# USD per million tokens, for the run's cost line. Only the models this eval is
# plausibly run with; anything else reports tokens without a dollar figure.
PRICING = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-5": (5.00, 25.00),
}

SYSTEM_PREAMBLE = """You are the skill router for an agent that works with Omni Analytics.

Below is the catalog of available skills. Each entry is the skill's name and the
description the agent sees before any skill is loaded. Given a user request,
decide which single skill the agent should load to handle it.

Judge only from the descriptions below. Pick the one skill whose description
covers the request most directly. If several could apply, pick the one whose
description names the request's core action — not one that merely mentions the
same nouns. If no skill covers it, answer "none".

## Skill catalog
"""

RESPONSE_FORMAT_HINT = 'Answer with the skill name only, via the required JSON output.'


@dataclass
class Case:
    skill: str
    case_id: str
    question: str
    expected: str


def load_eval_env() -> dict[str, str]:
    path = EVALS_DIR / "eval-env.local.json"
    if not path.is_file():
        path = EVALS_DIR / "eval-env.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in data.items() if k != "_comment"}


def substitute(text: str, env: dict[str, str]) -> str:
    for key, value in env.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def read_description(skill: str) -> str:
    """Pull `description` out of the SKILL.md frontmatter.

    Deliberately the same flat parse as validate.py — if a description ever
    stops being a single-line scalar, tier 0 fails first and says why.
    """
    lines = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"skills/{skill}/SKILL.md has no frontmatter; run validate.py first")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"skills/{skill}/SKILL.md has no description; run validate.py first")


def build_catalog(skills: list[str]) -> str:
    return "\n".join(f"### {skill}\n{read_description(skill)}\n" for skill in skills)


def discover_skills() -> list[str]:
    return sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


def load_cases(skills: list[str], env: dict[str, str]) -> list[Case]:
    cases: list[Case] = []
    for skill in skills:
        path = SKILLS_DIR / skill / "evals" / "evals.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for case in data["cases"]:
            cases.append(Case(
                skill=skill,
                case_id=str(case["id"]),
                question=substitute(str(case["question"]), env),
                expected=str(case["expected_skill"]),
            ))
    return cases


def classify(client, model: str, system: list[dict], choices: list[str], question: str):
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        thinking={"type": "disabled"},
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {"skill": {"type": "string", "enum": choices}},
                    "required": ["skill"],
                    "additionalProperties": False,
                },
            },
        },
        messages=[{"role": "user", "content": f"{question}\n\n{RESPONSE_FORMAT_HINT}"}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)["skill"], response.usage


def run_case(client, model: str, system: list[dict], choices: list[str], case: Case, samples: int) -> dict:
    picks: list[str] = []
    input_tokens = output_tokens = cached_tokens = 0
    for _ in range(samples):
        pick, usage = classify(client, model, system, choices, case.question)
        picks.append(pick)
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cached_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
    majority, votes = Counter(picks).most_common(1)[0]
    return {
        "skill": case.skill,
        "case_id": case.case_id,
        "expected": case.expected,
        "picks": picks,
        "majority": majority,
        "unanimous": votes == samples,
        "passed": majority == case.expected,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_tokens,
    }


def floor2(score: float) -> float:
    """Round a score *down* to 2dp.

    A floor has to be reachable by the run that produced it. Plain round() can
    round up — 9/11 becomes a 0.82 gate that 9/11 then fails — so every recorded
    baseline truncates instead.
    """
    return math.floor(score * 100) / 100


def load_baselines() -> dict:
    if not BASELINES_PATH.is_file():
        return {"min_overall": 0.0, "skills": {}}
    return json.loads(BASELINES_PATH.read_text(encoding="utf-8"))


def write_step_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skill", action="append", default=[], help="Only run cases owned by this skill (repeatable)")
    parser.add_argument("--model", default=os.environ.get("ROUTING_EVAL_MODEL", DEFAULT_MODEL))
    parser.add_argument("--samples", type=int, default=int(os.environ.get("ROUTING_EVAL_SAMPLES", "3")),
                        help="Samples per case; the majority pick is scored (default 3)")
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("ROUTING_EVAL_CONCURRENCY", "8")))
    parser.add_argument("--json-out", type=Path, help="Write full per-case results here")
    parser.add_argument("--update-baselines", action="store_true", help="Record this run's scores as the new gate")
    parser.add_argument("--skip-if-no-key", action="store_true",
                        help="Exit 0 instead of failing when no Anthropic credential is available")
    args = parser.parse_args()

    try:
        import anthropic
    except ImportError:
        print("ERROR: the `anthropic` package is not installed (pip install -r evals/ci/requirements.txt)", file=sys.stderr)
        return 1

    has_credential = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or (Path.home() / ".config" / "anthropic").is_dir()
    )
    if not has_credential:
        message = "no Anthropic credential found (set ANTHROPIC_API_KEY or run `ant auth login`)"
        if args.skip_if_no_key:
            print(f"SKIP: {message}")
            write_step_summary(["### Tier 1 — skill routing", "", f"Skipped: {message}."])
            return 0
        print(f"ERROR: {message}", file=sys.stderr)
        return 1

    all_skills = discover_skills()
    selected = args.skill or all_skills
    unknown = sorted(set(selected) - set(all_skills))
    if unknown:
        print(f"ERROR: unknown skill(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    env = load_eval_env()
    cases = load_cases(selected, env)
    if not cases:
        print("No eval cases selected; nothing to do.")
        return 0

    # The catalog is always the full set: routing is only meaningful against
    # every skill the agent could have picked instead.
    choices = all_skills + ["none"]
    system = [{
        "type": "text",
        "text": SYSTEM_PREAMBLE + build_catalog(all_skills),
        "cache_control": {"type": "ephemeral"},
    }]

    client = anthropic.Anthropic()
    print(f"Routing {len(cases)} cases x {args.samples} samples on {args.model} "
          f"(concurrency {args.concurrency})...")

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(
            lambda case: run_case(client, args.model, system, choices, case, args.samples),
            cases,
        ))

    by_skill: dict[str, list[dict]] = {}
    for result in results:
        by_skill.setdefault(result["skill"], []).append(result)

    passed = sum(1 for result in results if result["passed"])
    overall = passed / len(results)
    flaky = [r for r in results if r["passed"] and not r["unanimous"]]
    failures = [r for r in results if not r["passed"]]

    scores = {
        skill: sum(1 for r in rows if r["passed"]) / len(rows)
        for skill, rows in sorted(by_skill.items())
    }

    print()
    for skill, score in scores.items():
        rows = by_skill[skill]
        print(f"  {skill:<24} {score:>6.0%}  ({sum(1 for r in rows if r['passed'])}/{len(rows)})")
    print(f"\nOverall: {overall:.1%} ({passed}/{len(results)})")

    if failures:
        print("\nMisroutes:")
        for result in failures:
            print(f"  {result['skill']} case {result['case_id']}: "
                  f"expected {result['expected']}, picked {result['majority']} (votes: {', '.join(result['picks'])})")
    if flaky:
        print(f"\n{len(flaky)} case(s) passed on a split vote — unstable routing, worth a look:")
        for result in flaky:
            print(f"  {result['skill']} case {result['case_id']}: {', '.join(result['picks'])}")

    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    total_cached = sum(r["cached_input_tokens"] for r in results)
    cost_line = f"{total_in:,} input tokens ({total_cached:,} cache reads), {total_out:,} output tokens"
    if args.model in PRICING:
        in_rate, out_rate = PRICING[args.model]
        cost_line += f" — about ${total_in / 1e6 * in_rate + total_out / 1e6 * out_rate:.2f}"
    print(f"\n{cost_line}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({
            "model": args.model,
            "samples": args.samples,
            "overall": overall,
            "scores": scores,
            "results": results,
        }, indent=2) + "\n", encoding="utf-8")

    if args.update_baselines:
        partial = len(selected) < len(all_skills)
        baselines = load_baselines()
        baselines["model"] = args.model
        baselines["samples"] = args.samples
        # A partial run only knows about the skills it ran. Merge those in and
        # leave the rest — and the overall gate — as they were, or one
        # `--skill x --update-baselines` would wipe every other floor.
        baselines.setdefault("skills", {}).update(
            {skill: floor2(score) for skill, score in scores.items()}
        )
        if partial:
            print(f"\nPartial run ({', '.join(sorted(selected))}); left min_overall at "
                  f"{float(baselines.get('min_overall', 0.0)):.0%}.")
        else:
            baselines["min_overall"] = floor2(overall)
        baselines["skills"] = dict(sorted(baselines["skills"].items()))
        BASELINES_PATH.write_text(json.dumps(baselines, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baselines to {BASELINES_PATH.relative_to(ROOT)}. Commit it so CI can gate on it.")
        return 0

    baselines = load_baselines()
    gate_failures: list[str] = []
    min_overall = float(baselines.get("min_overall", 0.0))
    if overall < min_overall:
        gate_failures.append(f"overall {overall:.1%} is below the baseline {min_overall:.1%}")
    for skill, score in scores.items():
        floor = baselines.get("skills", {}).get(skill)
        if floor is not None and score < float(floor):
            gate_failures.append(f"{skill} {score:.0%} is below its baseline {float(floor):.0%}")

    summary = [
        "### Tier 1 — skill routing",
        "",
        f"`{args.model}`, {args.samples} sample(s)/case — **{overall:.1%}** ({passed}/{len(results)})",
        "",
        "| Skill | Accuracy |",
        "| --- | --- |",
    ] + [f"| {skill} | {score:.0%} |" for skill, score in scores.items()]
    if failures:
        summary += ["", "**Misroutes**", ""] + [
            f"- `{r['skill']}` case {r['case_id']}: expected `{r['expected']}`, picked `{r['majority']}`"
            for r in failures
        ]
    if gate_failures:
        summary += ["", "**Below baseline**", ""] + [f"- {item}" for item in gate_failures]
    summary += ["", cost_line]
    write_step_summary(summary)

    if gate_failures:
        print("\nBelow baseline:")
        for item in gate_failures:
            print(f"  {item}")
        return 1

    if not baselines.get("skills"):
        print("\nNo baselines recorded yet — run with --update-baselines to set the gate.")
    print("\nRouting is at or above baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

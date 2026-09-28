#!/usr/bin/env python3
"""Tier 1 skill eval: does each eval question route to the skill that owns it?

This is the cheapest eval in the repo that still exercises a model. It shows
Claude nothing but the skill catalog — every `name` + `description` from
`skills/*/SKILL.md`, the same text an agent sees when deciding which skill to
load — and asks which skill handles the prompt. No Omni instance, no CLI, no
tool execution, no judge: one short classification call per sample.

Two case sources:

  * `skills/*/evals/evals.json` — every `question`, labelled by `expected_skill`.
  * `evals/ci/negative-cases.json` — out-of-scope prompts that must route to
    `none`. Without these the eval can only see a skill that stops attracting
    its own work; it is blind to a description that gets greedier.

Two modes:

  * Paired (`--compare-to REF`) — builds the catalog twice, once from the
    working tree and once from a git ref, runs every case against both, and
    reports observed differences. Gates on regressions reproduced in a fresh
    confirmation pass. Identical catalogs share results so sampling noise
    cannot create a regression when the router inputs have not changed.
  * Absolute (default) — one catalog, scored against the floors in
    `baselines.json`. This is what CI runs on `main`.

Usage:
    python3 evals/ci/routing_eval.py                            # absolute
    python3 evals/ci/routing_eval.py --compare-to origin/main   # paired
    python3 evals/ci/routing_eval.py --skill omni-query         # one skill
    python3 evals/ci/routing_eval.py --update-baselines         # re-record

Needs an Anthropic credential (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
`ant auth login` profile).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
EVALS_DIR = ROOT / "evals"
CI_DIR = Path(__file__).resolve().parent
BASELINES_PATH = CI_DIR / "baselines.json"
NEGATIVE_CASES_PATH = CI_DIR / "negative-cases.json"

DEFAULT_MODEL = "claude-sonnet-5"

# Pseudo-skill the out-of-scope cases are grouped under, in both the report and
# baselines.json. Parenthesised so it can never collide with a real skill name.
NEGATIVE_GROUP = "(negative)"

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

RESPONSE_FORMAT_HINT = "Answer with the skill name only, via the required JSON output."


@dataclass
class Case:
    skill: str
    case_id: str
    question: str
    expected: str


@dataclass
class Catalog:
    label: str
    skills: list[str]
    system: list[dict]
    choices: list[str]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


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


def extract_description(markdown: str, where: str) -> str:
    """Pull `description` out of SKILL.md frontmatter.

    Deliberately the same flat parse as validate.py — if a description ever
    stops being a single-line scalar, tier 0 fails first and says why.
    """
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"{where} has no frontmatter; run validate.py first")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{where} has no description; run validate.py first")


def discover_skills() -> list[str]:
    return sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


def discover_skills_at(ref: str) -> list[str]:
    listing = git("ls-tree", "-r", "--name-only", ref, "skills/")
    return sorted(
        line.split("/")[1]
        for line in listing.splitlines()
        if line.endswith("/SKILL.md") and line.count("/") == 2
    )


def build_catalog(label: str, skills: list[str], ref: str | None = None) -> Catalog:
    entries = []
    for skill in skills:
        path = f"skills/{skill}/SKILL.md"
        if ref is None:
            markdown = (ROOT / path).read_text(encoding="utf-8")
        else:
            markdown = git("show", f"{ref}:{path}")
        entries.append(f"### {skill}\n{extract_description(markdown, f'{path} at {label}')}\n")

    return Catalog(
        label=label,
        skills=skills,
        system=[{
            "type": "text",
            "text": SYSTEM_PREAMBLE + "\n".join(entries),
            "cache_control": {"type": "ephemeral"},
        }],
        choices=skills + ["none"],
    )


def load_cases(skills: list[str], env: dict[str, str], include_negatives: bool) -> list[Case]:
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

    if include_negatives and NEGATIVE_CASES_PATH.is_file():
        data = json.loads(NEGATIVE_CASES_PATH.read_text(encoding="utf-8"))
        for case in data["cases"]:
            cases.append(Case(
                skill=NEGATIVE_GROUP,
                case_id=str(case["id"]),
                question=substitute(str(case["question"]), env),
                expected="none",
            ))
    return cases


def classify(client, model: str, catalog: Catalog, question: str):
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=catalog.system,
        thinking={"type": "disabled"},
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {"skill": {"type": "string", "enum": catalog.choices}},
                    "required": ["skill"],
                    "additionalProperties": False,
                },
            },
        },
        messages=[{"role": "user", "content": f"{question}\n\n{RESPONSE_FORMAT_HINT}"}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)["skill"], response.usage


def run_case(client, model: str, catalog: Catalog, case: Case, samples: int) -> dict:
    picks: list[str] = []
    input_tokens = output_tokens = cached_tokens = 0
    for _ in range(samples):
        pick, usage = classify(client, model, catalog, case.question)
        picks.append(pick)
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cached_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
    majority, votes = Counter(picks).most_common(1)[0]
    return {
        "catalog": catalog.label,
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


def run_all(client, model: str, catalogs: list[Catalog], cases: list[Case],
            samples: int, concurrency: int) -> list[dict]:
    work = [(catalog, case) for catalog in catalogs for case in cases]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return list(pool.map(
            lambda item: run_case(client, model, item[0], item[1], samples),
            work,
        ))


def run_paired(client, model: str, base: Catalog, head: Catalog, cases: list[Case],
               samples: int, concurrency: int) -> tuple[list[dict], list[dict]]:
    if base.system == head.system and base.choices == head.choices:
        print("Identical catalogs: routing once and reusing results for head.")
        results = run_all(client, model, [base], cases, samples, concurrency)
        reused = [dict(r, catalog=head.label, reused_from=base.label,
                       input_tokens=0, output_tokens=0, cached_input_tokens=0)
                  for r in results]
        return results + reused, []

    results = run_all(client, model, [base, head], cases, samples, concurrency)
    index = {(r["catalog"], r["skill"], r["case_id"]): r for r in results}
    candidates = [case for case in cases
                  if index[(base.label, case.skill, case.case_id)]["passed"]
                  and not index[(head.label, case.skill, case.case_id)]["passed"]]
    confirmation = []
    if candidates:
        # Fresh votes, not pooled with the votes that selected the candidates.
        # This reduces false alarms; it is not a statistical significance test.
        confirmation_samples = max(9, samples)
        print(f"Confirming {len(candidates)} apparent regression(s) with "
              f"{confirmation_samples} fresh samples per catalog.")
        confirmation = run_all(client, model, [base, head], candidates,
                               confirmation_samples, concurrency)
    return results, confirmation


def floor2(score: float) -> float:
    """Round a score *down* to 2dp.

    A floor has to be reachable by the run that produced it. Plain round() can
    round up — 9/11 becomes a 0.82 gate that 9/11 then fails — so every recorded
    baseline truncates instead.
    """
    return math.floor(score * 100) / 100


def score_by_group(results: list[dict]) -> dict[str, float]:
    groups: dict[str, list[dict]] = {}
    for result in results:
        groups.setdefault(result["skill"], []).append(result)
    return {
        group: sum(1 for r in rows if r["passed"]) / len(rows)
        for group, rows in sorted(groups.items())
    }


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


def cost_line(results: list[dict], model: str) -> str:
    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    total_cached = sum(r["cached_input_tokens"] for r in results)
    line = f"{total_in:,} input tokens ({total_cached:,} cache reads), {total_out:,} output tokens"
    if model in PRICING:
        in_rate, out_rate = PRICING[model]
        line += f" — about ${total_in / 1e6 * in_rate + total_out / 1e6 * out_rate:.2f}"
    return line


def report_absolute(results: list[dict], args, baselines: dict) -> tuple[int, list[str]]:
    scores = score_by_group(results)
    passed = sum(1 for r in results if r["passed"])
    overall = passed / len(results)
    failures = [r for r in results if not r["passed"]]
    flaky = [r for r in results if r["passed"] and not r["unanimous"]]

    print()
    for group, score in scores.items():
        rows = [r for r in results if r["skill"] == group]
        print(f"  {group:<24} {score:>6.0%}  ({sum(1 for r in rows if r['passed'])}/{len(rows)})")
    print(f"\nOverall: {overall:.1%} ({passed}/{len(results)})")

    if failures:
        print("\nMisroutes:")
        for result in failures:
            print(f"  {result['skill']} case {result['case_id']}: "
                  f"expected {result['expected']}, picked {result['majority']} "
                  f"(votes: {', '.join(result['picks'])})")
    if flaky:
        print(f"\n{len(flaky)} case(s) passed on a split vote — unstable routing, worth a look:")
        for result in flaky:
            print(f"  {result['skill']} case {result['case_id']}: {', '.join(result['picks'])}")

    gate_failures: list[str] = []
    min_overall = float(baselines.get("min_overall", 0.0))
    if overall < min_overall:
        gate_failures.append(f"overall {overall:.1%} is below the baseline {min_overall:.1%}")
    for group, score in scores.items():
        floor = baselines.get("skills", {}).get(group)
        if floor is not None and score < float(floor):
            gate_failures.append(f"{group} {score:.0%} is below its baseline {float(floor):.0%}")

    summary = [
        "### Tier 1 — skill routing",
        "",
        f"`{args.model}`, {args.samples} sample(s)/case — **{overall:.1%}** ({passed}/{len(results)})",
        "",
        "| Skill | Accuracy |",
        "| --- | --- |",
    ] + [f"| {group} | {score:.0%} |" for group, score in scores.items()]
    if failures:
        summary += ["", "**Misroutes**", ""] + [
            f"- `{r['skill']}` case {r['case_id']}: expected `{r['expected']}`, picked `{r['majority']}`"
            for r in failures
        ]
    if gate_failures:
        summary += ["", "**Below baseline**", ""] + [f"- {item}" for item in gate_failures]

    if gate_failures:
        print("\nBelow baseline:")
        for item in gate_failures:
            print(f"  {item}")
        return 1, summary

    if not baselines.get("skills"):
        print("\nNo baselines recorded yet — run with --update-baselines to set the gate.")
    print("\nRouting is at or above baseline.")
    return 0, summary


def report_paired(results: list[dict], args, base_label: str, head_label: str,
                  confirmation: list[dict]) -> tuple[int, list[str]]:
    index = {(r["catalog"], r["skill"], r["case_id"]): r for r in results}
    confirmed = {(r["catalog"], r["skill"], r["case_id"]): r for r in confirmation}
    keys = sorted({(r["skill"], r["case_id"]) for r in results})

    regressions, unstable, fixes, churn = [], [], [], []
    base_passed = head_passed = 0
    for skill, case_id in keys:
        base = index[(base_label, skill, case_id)]
        head = index[(head_label, skill, case_id)]
        base_passed += base["passed"]
        head_passed += head["passed"]
        if base["passed"] and not head["passed"]:
            check_base = confirmed[(base_label, skill, case_id)]
            check_head = confirmed[(head_label, skill, case_id)]
            target = regressions if check_base["passed"] and not check_head["passed"] else unstable
            target.append((skill, case_id, base, head))
        elif head["passed"] and not base["passed"]:
            fixes.append((skill, case_id, base, head))
        elif base["majority"] != head["majority"]:
            churn.append((skill, case_id, base, head))

    total = len(keys)
    print()
    print(f"  base ({base_label}): {base_passed / total:.1%} ({base_passed}/{total})")
    print(f"  head:               {head_passed / total:.1%} ({head_passed}/{total})")
    print(f"  net:                {head_passed - base_passed:+d} case(s)")

    def describe(rows, heading):
        if not rows:
            return
        print(f"\n{heading}:")
        for skill, case_id, base, head in rows:
            print(f"  {skill} case {case_id}: {base['majority']} -> {head['majority']} "
                  f"(expected {head['expected']})")

    describe(regressions, "Confirmed regressions (base passes and head fails in both rounds)")
    describe(unstable, "Unconfirmed regressions (unstable; not gating)")
    describe(fixes, "Observed fixes (not confirmed)")
    describe(churn, "Changed pick, same outcome")

    summary = [
        "### Tier 1 — skill routing (paired)",
        "",
        f"`{args.model}`, {args.samples} sample(s)/case, vs `{base_label}`",
        "",
        f"| | Passing |",
        "| --- | --- |",
        f"| base (`{base_label}`) | {base_passed}/{total} ({base_passed / total:.0%}) |",
        f"| head | {head_passed}/{total} ({head_passed / total:.0%}) |",
        f"| net | {head_passed - base_passed:+d} |",
    ]
    summary += ["", "Scores above are from the initial pass. Apparent regressions are checked "
                "with fresh votes on both catalogs; confirmation reduces noise but does not "
                "establish statistical significance."]
    if any(r.get("reused_from") for r in results):
        summary += ["", "Catalogs are identical; head reuses base results."]
    for rows, heading in ((regressions, "Confirmed regressions"),
                          (unstable, "Unconfirmed regressions (not gating)"),
                          (fixes, "Observed fixes (not confirmed)"),
                          (churn, "Changed pick, same outcome")):
        if rows:
            summary += ["", f"**{heading}**", ""] + [
                f"- `{skill}` case {case_id}: `{base['majority']}` → `{head['majority']}` "
                f"(expected `{head['expected']}`)"
                for skill, case_id, base, head in rows
            ]
    if confirmation:
        summary += ["", "**Confirmation votes**", ""]
    for row in confirmation:
        detail = (f"Confirmation `{row['catalog']}` / `{row['skill']}` case {row['case_id']}: "
                  f"{', '.join(row['picks'])}")
        print(detail)
        summary.append(f"- {detail}")

    if regressions:
        print(f"\n{len(regressions)} confirmed regression(s) against {base_label}.")
        return 1, summary
    print(f"\nNo confirmed regressions against {base_label}.")
    return 0, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skill", action="append", default=[], help="Only run cases owned by this skill (repeatable)")
    parser.add_argument("--compare-to", metavar="REF",
                        help="Also build the catalog from this git ref and report what changed")
    parser.add_argument("--no-negatives", action="store_true",
                        help="Skip the out-of-scope cases in negative-cases.json")
    parser.add_argument("--model", default=os.environ.get("ROUTING_EVAL_MODEL", DEFAULT_MODEL))
    parser.add_argument("--samples", type=int, default=int(os.environ.get("ROUTING_EVAL_SAMPLES", "3")),
                        help="Samples per case; the majority pick is scored (default 3)")
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("ROUTING_EVAL_CONCURRENCY", "8")))
    parser.add_argument("--json-out", type=Path, help="Write full per-case results here")
    parser.add_argument("--update-baselines", action="store_true", help="Record this run's scores as the new gate")
    parser.add_argument("--skip-if-no-key", action="store_true",
                        help="Exit 0 instead of failing when no Anthropic credential is available")
    args = parser.parse_args()
    if args.samples < 1 or args.concurrency < 1:
        parser.error("--samples and --concurrency must be positive")

    if args.compare_to and args.update_baselines:
        print("ERROR: --update-baselines records absolute scores; drop --compare-to", file=sys.stderr)
        return 1

    try:
        import anthropic
    except ImportError:
        print("ERROR: the `anthropic` package is not installed (pip install -r evals/ci/requirements.txt)",
              file=sys.stderr)
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
    cases = load_cases(selected, env, include_negatives=not args.no_negatives)
    if not cases:
        print("No eval cases selected; nothing to do.")
        return 0

    # The catalog is always the full set: routing is only meaningful against
    # every skill the agent could have picked instead.
    head = build_catalog("head", all_skills)
    catalogs = [head]
    base_label = None
    if args.compare_to:
        base_label = "base" if args.compare_to == "head" else args.compare_to
        base_skills = discover_skills_at(args.compare_to)
        catalogs.insert(0, build_catalog(base_label, base_skills, ref=args.compare_to))
        added = sorted(set(all_skills) - set(base_skills))
        removed = sorted(set(base_skills) - set(all_skills))
        if added:
            print(f"Skills added by this change: {', '.join(added)}")
        if removed:
            print(f"Skills removed by this change: {', '.join(removed)}")

    client = anthropic.Anthropic()
    identical = (len(catalogs) == 2 and catalogs[0].system == head.system
                 and catalogs[0].choices == head.choices)
    calls = len(cases) * args.samples * (1 if identical else len(catalogs))
    print(f"Routing {len(cases)} cases x {args.samples} samples x {len(catalogs)} catalog(s) "
          f"= {calls} initial calls on {args.model} (concurrency {args.concurrency})...")

    confirmation = []
    if args.compare_to:
        results, confirmation = run_paired(client, args.model, catalogs[0], head,
                                          cases, args.samples, args.concurrency)
        exit_code, summary = report_paired(results, args, base_label, "head", confirmation)
    else:
        results = run_all(client, args.model, catalogs, cases, args.samples, args.concurrency)
        baselines = load_baselines()
        exit_code, summary = report_absolute(results, args, baselines)

    line = cost_line(results + confirmation, args.model)
    print(f"\n{line}")
    summary += ["", line]

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({
            "model": args.model,
            "samples": args.samples,
            "compare_to": args.compare_to,
            "results": results,
            "confirmation_results": confirmation,
        }, indent=2) + "\n", encoding="utf-8")

    if args.update_baselines:
        partial = len(selected) < len(all_skills)
        baselines = load_baselines()
        scores = score_by_group(results)
        baselines["model"] = args.model
        baselines["samples"] = args.samples
        # A partial run only knows about the skills it ran. Merge those in and
        # leave the rest — and the overall gate — as they were, or one
        # `--skill x --update-baselines` would wipe every other floor.
        baselines.setdefault("skills", {}).update(
            {group: floor2(score) for group, score in scores.items()}
        )
        if partial:
            print(f"\nPartial run ({', '.join(sorted(selected))}); left min_overall at "
                  f"{float(baselines.get('min_overall', 0.0)):.0%}.")
        else:
            baselines["min_overall"] = floor2(
                sum(1 for r in results if r["passed"]) / len(results)
            )
        baselines["skills"] = dict(sorted(baselines["skills"].items()))
        BASELINES_PATH.write_text(json.dumps(baselines, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baselines to {BASELINES_PATH.relative_to(ROOT)}. Commit it so CI can gate on it.")
        return 0

    write_step_summary(summary)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

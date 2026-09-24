#!/usr/bin/env python3
"""Tier 0 skill checks: structural validation with no model calls.

Runs in a couple of seconds on any PR, needs no credentials and no Omni
instance. It catches the failures that would otherwise only surface partway
through a 20-minute BenchFlow run: an eval file that does not parse, a case
pointing at a skill that no longer exists, a `{{PLACEHOLDER}}` with nothing to
substitute, a SKILL.md link that dangles.

Usage:
    python3 evals/ci/validate.py [--json]

Exits non-zero if any check fails. Warnings never fail the run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"
RULES_DIR = ROOT / "rules"
EVALS_DIR = ROOT / "evals"
NEGATIVE_CASES_PATH = ROOT / "evals" / "ci" / "negative-cases.json"

# Claude Code truncates skill descriptions past this; a longer one is silently
# clipped mid-sentence, which usually takes the "use this when ..." half with it.
MAX_DESCRIPTION_CHARS = 1024

# Jaccard overlap of description word sets. Two skills that read this similarly
# compete for the same prompts, which is how routing regressions start.
DESCRIPTION_OVERLAP_WARN = 0.30
DESCRIPTION_OVERLAP_FAIL = 0.50

CASE_REQUIRED_KEYS = ("id", "question", "ground_truth", "expected_behavior", "expected_skill")
CASE_OPTIONAL_KEYS = ("depends_on", "files")

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
STOPWORDS = {
    "a", "an", "and", "the", "or", "for", "to", "of", "in", "on", "with", "when",
    "this", "that", "use", "using", "skill", "omni", "analytics", "via", "from",
    "it", "is", "are", "as", "by", "at", "into", "also", "you", "your", "user",
    "someone", "wants", "not", "but", "e", "g", "cli", "any",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_frontmatter(path: Path, report: Report) -> dict[str, str]:
    """Read the leading `---` block as flat `key: value` pairs.

    Every frontmatter block in this repo is single-line scalars, so this stays
    stdlib-only rather than pulling PyYAML in for CI. A block that needs more
    than that should fail loudly here instead of being half-parsed.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        report.error(rel(path), "missing YAML frontmatter (file must start with ---)")
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            report.error(rel(path), f"frontmatter line is not `key: value`: {line!r}")
            continue
        key, value = line.split(":", 1)
        if key != key.strip():
            report.error(rel(path), f"frontmatter key {key.strip()!r} is indented; nested keys are not supported")
            continue
        fields[key.strip()] = value.strip().strip('"').strip("'")

    report.error(rel(path), "frontmatter block is never closed with ---")
    return fields


def discover_skills() -> list[str]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


def check_markdown_links(path: Path, report: Report) -> None:
    body = path.read_text(encoding="utf-8")
    for target in MD_LINK_RE.findall(body):
        target = target.split(" ", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            report.error(rel(path), f"link target does not exist: {target}")


def check_skill_docs(skills: list[str], report: Report) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for skill in skills:
        path = SKILLS_DIR / skill / "SKILL.md"
        fields = parse_frontmatter(path, report)

        name = fields.get("name", "")
        if not name:
            report.error(rel(path), "frontmatter is missing `name`")
        elif name != skill:
            report.error(rel(path), f"frontmatter name {name!r} does not match directory {skill!r}")

        description = fields.get("description", "")
        if not description:
            report.error(rel(path), "frontmatter is missing `description`")
        elif len(description) > MAX_DESCRIPTION_CHARS:
            report.error(
                rel(path),
                f"description is {len(description)} chars, over the {MAX_DESCRIPTION_CHARS} limit "
                "(it will be truncated before an agent reads the end of it)",
            )
        else:
            descriptions[skill] = description

        check_markdown_links(path, report)
    return descriptions


def check_agents_and_rules(report: Report) -> None:
    for path in sorted(AGENTS_DIR.glob("*.md")) if AGENTS_DIR.is_dir() else []:
        fields = parse_frontmatter(path, report)
        if fields.get("name", "") != path.stem:
            report.error(rel(path), f"frontmatter name {fields.get('name', '')!r} does not match file stem {path.stem!r}")
        if not fields.get("description"):
            report.error(rel(path), "frontmatter is missing `description`")
        check_markdown_links(path, report)

    for path in sorted(RULES_DIR.glob("*.mdc")) if RULES_DIR.is_dir() else []:
        fields = parse_frontmatter(path, report)
        for key in ("description", "globs", "alwaysApply"):
            if key not in fields:
                report.error(rel(path), f"frontmatter is missing `{key}`")
        always_apply = fields.get("alwaysApply", "")
        if always_apply and always_apply not in ("true", "false"):
            report.error(rel(path), f"alwaysApply must be true or false, got {always_apply!r}")
        globs = fields.get("globs", "")
        if globs:
            try:
                parsed = json.loads(globs)
            except json.JSONDecodeError:
                report.error(rel(path), f"globs is not a JSON list: {globs!r}")
            else:
                if not isinstance(parsed, list):
                    report.error(rel(path), f"globs must be a list, got {type(parsed).__name__}")
        check_markdown_links(path, report)


def load_eval_env(report: Report) -> set[str]:
    path = EVALS_DIR / "eval-env.json"
    if not path.is_file():
        report.error("evals/eval-env.json", "missing; placeholder substitution cannot be checked")
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(rel(path), f"is not valid JSON: {exc}")
        return set()
    return {key for key in data if key != "_comment"}


def check_eval_files(skills: list[str], env_keys: set[str], report: Report) -> int:
    known = set(skills)
    total_cases = 0

    for skill in skills:
        path = SKILLS_DIR / skill / "evals" / "evals.json"
        if not path.is_file():
            report.warn(f"skills/{skill}", "has no evals/evals.json, so nothing evaluates it")
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(rel(path), f"is not valid JSON: {exc}")
            continue

        if str(data.get("version", "")) != "1":
            report.error(rel(path), f"unexpected schema version {data.get('version')!r}, expected \"1\"")
        if data.get("skill_name") != skill:
            report.error(rel(path), f"skill_name {data.get('skill_name')!r} does not match directory {skill!r}")

        defaults = data.get("defaults", {})
        if not isinstance(defaults, dict):
            report.error(rel(path), "defaults must be an object")
            defaults = {}
        timeout = defaults.get("timeout_sec")
        if not isinstance(timeout, int) or timeout <= 0:
            report.error(rel(path), f"defaults.timeout_sec must be a positive integer, got {timeout!r}")
        if not isinstance(defaults.get("judge_model", ""), str) or not defaults.get("judge_model"):
            report.error(rel(path), "defaults.judge_model must be a non-empty string")

        cases = data.get("cases")
        if not isinstance(cases, list) or not cases:
            report.error(rel(path), "cases must be a non-empty list")
            continue

        seen_ids: set[str] = set()
        for case in cases:
            total_cases += 1
            case_id = str(case.get("id", "?"))
            where = f"{rel(path)} case {case_id}"

            if not isinstance(case, dict):
                report.error(where, "case must be an object")
                continue

            for key in CASE_REQUIRED_KEYS:
                if key not in case:
                    report.error(where, f"missing required key `{key}`")
            for key in case:
                if key not in CASE_REQUIRED_KEYS + CASE_OPTIONAL_KEYS:
                    report.error(where, f"unknown key `{key}` (BenchFlow's schema is strict)")

            if case_id in seen_ids:
                report.error(where, "duplicate case id")
            seen_ids.add(case_id)

            for key in ("question", "ground_truth"):
                if not isinstance(case.get(key), str) or not case.get(key, "").strip():
                    report.error(where, f"`{key}` must be a non-empty string")

            behaviors = case.get("expected_behavior")
            if not isinstance(behaviors, list) or not behaviors:
                report.error(where, "`expected_behavior` must be a non-empty list")
            elif not all(isinstance(item, str) and item.strip() for item in behaviors):
                report.error(where, "`expected_behavior` entries must be non-empty strings")

            expected_skill = case.get("expected_skill")
            if expected_skill not in known:
                report.error(where, f"expected_skill {expected_skill!r} is not a skill in skills/")

            depends_on = case.get("depends_on", [])
            if not isinstance(depends_on, list):
                report.error(where, "`depends_on` must be a list")
            else:
                for dep in depends_on:
                    if dep == skill:
                        report.error(where, f"depends_on lists its own skill {dep!r}")
                    elif dep not in known:
                        report.error(where, f"depends_on references unknown skill {dep!r}")

            files = case.get("files", [])
            if not isinstance(files, list):
                report.error(where, "`files` must be a list")
            else:
                for declared in files:
                    # Runner resolves declared inputs relative to the skill directory.
                    if not (SKILLS_DIR / skill / str(declared)).is_file():
                        report.error(where, f"declared input file does not exist: {declared}")

            blob = " ".join(
                [str(case.get("question", "")), str(case.get("ground_truth", ""))]
                + [str(item) for item in (behaviors if isinstance(behaviors, list) else [])]
            )
            for placeholder in sorted(set(PLACEHOLDER_RE.findall(blob))):
                if placeholder not in env_keys:
                    report.error(where, f"uses {{{{{placeholder}}}}}, which is not a key in evals/eval-env.json")

    return total_cases


def check_negative_cases(skills: list[str], env_keys: set[str], report: Report) -> int:
    """Out-of-scope cases that must route to `none`.

    These have no owning skill and no expected_behavior — they exist so tier 1
    can see a description that gets greedier, not just one that gets weaker.
    """
    if not NEGATIVE_CASES_PATH.is_file():
        report.warn("evals/ci/negative-cases.json", "missing; tier 1 cannot detect over-triggering")
        return 0

    try:
        data = json.loads(NEGATIVE_CASES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(rel(NEGATIVE_CASES_PATH), f"is not valid JSON: {exc}")
        return 0

    where_file = rel(NEGATIVE_CASES_PATH)
    if not isinstance(data, dict):
        report.error(where_file, "must be an object")
        return 0
    if str(data.get("version", "")) != "1":
        report.error(where_file, f"unexpected schema version {data.get('version')!r}, expected \"1\"")

    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        report.error(where_file, "cases must be a non-empty list")
        return 0

    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    for position, case in enumerate(cases, 1):
        where = f"{where_file} entry {position}"
        if not isinstance(case, dict):
            report.error(where, "case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            report.error(where, "`id` must be a non-empty string")
            continue
        where = f"{where_file} case {case_id}"
        for key in case:
            if key not in ("id", "question", "kind"):
                report.error(where, f"unknown key `{key}`")
        if case_id in seen_ids:
            report.error(where, "duplicate case id")
        seen_ids.add(case_id)

        question = case.get("question")
        if not isinstance(question, str) or not question.strip():
            report.error(where, "`question` must be a non-empty string")
            continue
        normalized = question.strip().lower()
        if normalized in seen_questions:
            report.error(where, "duplicate question")
        seen_questions.add(normalized)

        for placeholder in sorted(set(PLACEHOLDER_RE.findall(question))):
            if placeholder not in env_keys:
                report.error(where, f"uses {{{{{placeholder}}}}}, which is not a key in evals/eval-env.json")

        # A negative case naming a real skill is almost always a mistake: it
        # reads as in-scope work while being labelled out-of-scope.
        for skill in skills:
            if skill in question:
                report.error(where, f"names the skill {skill!r}, so it is not out-of-scope")

    return len(cases)


def tokenize(description: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", description.lower())
    return {word for word in words if word not in STOPWORDS and len(word) > 2}


def check_description_overlap(descriptions: dict[str, str], report: Report) -> list[tuple[str, str, float]]:
    scored: list[tuple[str, str, float]] = []
    names = sorted(descriptions)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            a, b = tokenize(descriptions[left]), tokenize(descriptions[right])
            if not a or not b:
                continue
            overlap = len(a & b) / len(a | b)
            scored.append((left, right, overlap))
            if overlap >= DESCRIPTION_OVERLAP_FAIL:
                report.error(
                    "skill descriptions",
                    f"{left} and {right} overlap {overlap:.0%} — they will compete for the same prompts",
                )
            elif overlap >= DESCRIPTION_OVERLAP_WARN:
                report.warn(
                    "skill descriptions",
                    f"{left} and {right} overlap {overlap:.0%}; consider sharpening the boundary between them",
                )
    return sorted(scored, key=lambda item: item[2], reverse=True)


def write_step_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results instead of text")
    args = parser.parse_args()

    report = Report()
    skills = discover_skills()
    if not skills:
        report.error("skills/", "no skills found")

    descriptions = check_skill_docs(skills, report)
    check_agents_and_rules(report)
    env_keys = load_eval_env(report)
    total_cases = check_eval_files(skills, env_keys, report)
    negative_cases = check_negative_cases(skills, env_keys, report)
    overlaps = check_description_overlap(descriptions, report)

    if args.json:
        print(json.dumps({
            "skills": skills,
            "cases": total_cases,
            "negative_cases": negative_cases,
            "errors": report.errors,
            "warnings": report.warnings,
            "top_description_overlaps": [
                {"a": a, "b": b, "overlap": round(score, 4)} for a, b, score in overlaps[:5]
            ],
        }, indent=2))
        return 1 if report.errors else 0

    print(f"Checked {len(skills)} skills, {total_cases} eval cases, "
          f"{negative_cases} out-of-scope cases.")
    if overlaps:
        a, b, score = overlaps[0]
        print(f"Closest description pair: {a} / {b} ({score:.0%} overlap)")

    for warning in report.warnings:
        print(f"WARN  {warning}")
    for error in report.errors:
        print(f"ERROR {error}")

    summary = ["### Tier 0 — skill validation", "",
               f"{len(skills)} skills, {total_cases} eval cases, {negative_cases} out-of-scope cases."]
    if report.errors:
        summary += ["", "**Errors**", ""] + [f"- {item}" for item in report.errors]
    if report.warnings:
        summary += ["", "**Warnings**", ""] + [f"- {item}" for item in report.warnings]
    if not report.errors:
        summary += ["", "All structural checks passed."]
    write_step_summary(summary)

    if report.errors:
        print(f"\n{len(report.errors)} error(s).")
        return 1
    print("\nAll structural checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

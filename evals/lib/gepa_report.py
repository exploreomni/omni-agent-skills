#!/usr/bin/env python3
"""Create a Markdown/Mermaid report from GEPA optimize_anything artifacts."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def candidate_text(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict):
        for key in ("skill_md", "current_candidate"):
            value = candidate.get(key)
            if isinstance(value, str):
                return value
        for value in candidate.values():
            if isinstance(value, str):
                return value
    return str(candidate)


def short_text(value: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def mermaid_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'").replace("\n", "<br/>")


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def normalize_candidate(value: str) -> str:
    return value.strip()


def candidate_key(value: str) -> str:
    return normalize_candidate(value)


def state_dir(run_dir: Path) -> Path:
    """Return the directory containing GEPA engine artifacts."""
    if (run_dir / "candidates.json").exists() and (run_dir / "run_log.json").exists():
        return run_dir
    nested = run_dir / "gepa-state"
    if (nested / "candidates.json").exists() and (nested / "run_log.json").exists():
        return nested
    raise FileNotFoundError(f"No GEPA candidates.json/run_log.json found in {run_dir}")


def score_map(log: list[dict[str, Any]]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for item in log:
        selected = item.get("selected_program_candidate")
        old_scores = item.get("subsample_scores") or []
        if isinstance(selected, int) and old_scores:
            scores[selected] = float(old_scores[0])
        new_idx = item.get("new_program_idx")
        new_scores = item.get("new_subsample_scores") or []
        if isinstance(new_idx, int) and new_scores:
            scores[new_idx] = float(new_scores[0])
    return scores


def mutation_summary(before: str, after: str, limit: int = 6) -> str:
    diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="selected",
            tofile="candidate",
            lineterm="",
        )
    )
    changed = [
        line
        for line in diff
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith(("+++", "---"))
    ]
    if not changed:
        return "No textual change detected."
    excerpt = changed[:limit]
    if len(changed) > limit:
        excerpt.append(f"... {len(changed) - limit} more changed lines")
    return "<br>".join(markdown_escape(line) for line in excerpt)


def mutation_label(seed: str, candidate: str, limit: int = 100) -> str:
    if seed == candidate:
        return short_text(candidate, limit)
    diff = list(
        difflib.unified_diff(
            seed.splitlines(),
            candidate.splitlines(),
            fromfile="seed",
            tofile="candidate",
            lineterm="",
        )
    )
    changed = [
        line
        for line in diff
        if line.startswith("+")
        and not line.startswith("+++")
        and line[1:].strip()
    ]
    if changed:
        return short_text(" ".join(line[1:].strip() for line in changed[:3]), limit)
    return short_text(candidate, limit)


def reward_from_result(result: dict[str, Any]) -> float | None:
    value = (result.get("rewards") or {}).get("reward")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def collect_metric_calls(run_dir: Path, candidates: list[str]) -> list[dict[str, Any]]:
    candidate_index = {
        candidate_key(text): idx
        for idx, text in enumerate(candidates)
    }
    calls: list[dict[str, Any]] = []
    for skill_path in sorted(run_dir.glob("candidate-*/_generated/*/SKILL.md")):
        candidate_dir = skill_path.parents[2]
        candidate_text_value = candidate_key(skill_path.read_text(errors="replace"))
        idx = candidate_index.get(candidate_text_value)
        if idx is None:
            idx = len(candidates)
            candidates.append(normalize_candidate(skill_path.read_text(errors="replace")))
            candidate_index[candidate_text_value] = idx
        result_paths = sorted(candidate_dir.glob("jobs/with-skill/*/*/result.json"))
        for result_path in result_paths:
            result = load_json(result_path)
            calls.append(
                {
                    "candidate": idx,
                    "candidate_dir": candidate_dir.name,
                    "case": result.get("task_name"),
                    "score": reward_from_result(result),
                    "n_tool_calls": result.get("n_tool_calls"),
                    "error": result.get("error"),
                    "verifier_error": result.get("verifier_error"),
                    "result_path": result_path,
                }
            )
    return calls


def build_report(run_dir: Path) -> str:
    gepa_dir = state_dir(run_dir)
    candidates = [candidate_text(item) for item in load_json(gepa_dir / "candidates.json")]
    log = load_json(gepa_dir / "run_log.json")
    summary_path = run_dir / "summary.json"
    summary = load_json(summary_path) if summary_path.exists() else {}
    scores = score_map(log)
    seed = candidates[0] if candidates else ""
    metric_calls = collect_metric_calls(run_dir, candidates)
    measured_scores: dict[int, list[float]] = {}
    for call in metric_calls:
        idx = call.get("candidate")
        score = call.get("score")
        if isinstance(idx, int) and isinstance(score, float):
            measured_scores.setdefault(idx, []).append(score)
    best_idx = summary.get("best_idx")
    best_score = summary.get("best_score")
    if isinstance(best_idx, int) and best_idx in scores and isinstance(best_score, (int, float)):
        if scores[best_idx] != float(best_score):
            best_note = (
                "GEPA's run log scores are mutation-time subsample scores; "
                "summary best_score is the aggregate validation score."
            )
        else:
            best_note = ""
    else:
        best_note = ""

    lines: list[str] = [
        "# GEPA Optimization Trace",
        "",
        f"- Run directory: `{run_dir}`",
        f"- GEPA state directory: `{gepa_dir}`",
    ]
    if summary:
        for key in ("skill", "cases", "best_idx", "best_score", "total_metric_calls"):
            if key in summary:
                lines.append(f"- {key}: `{summary[key]}`")
    if best_note:
        lines.append(f"- note: {best_note}")
    lines.extend(["", "## Candidate Flow", "", "```mermaid", "flowchart LR"])

    for idx, text in enumerate(candidates):
        score = scores.get(idx)
        mutation_score_text = "n/a" if score is None else f"{score:g}"
        measured = measured_scores.get(idx, [])
        measured_text = ",".join(f"{item:g}" for item in measured) if measured else "n/a"
        focus = "seed" if idx == 0 else mutation_label(seed, text, 80)
        label = mermaid_escape(
            f"C{idx}\\nGEPA={mutation_score_text}\\nevals={measured_text}\\n{focus}"
        )
        lines.append(f'  C{idx}["{label}"]')

    for item in log:
        selected = item.get("selected_program_candidate")
        new_idx = item.get("new_program_idx")
        if not isinstance(selected, int) or not isinstance(new_idx, int):
            continue
        iteration = int(item.get("i", 0)) + 1
        old_score = (item.get("subsample_scores") or ["?"])[0]
        new_score = (item.get("new_subsample_scores") or ["?"])[0]
        lines.append(f"  C{selected} -->|iter {iteration}: subsample {old_score} to {new_score}| C{new_idx}")

    for call_num, call in enumerate(metric_calls, start=1):
        idx = call.get("candidate")
        if not isinstance(idx, int):
            continue
        score = call.get("score")
        score_text = "n/a" if score is None else f"{score:g}"
        label = mermaid_escape(f"E{call_num}\\ncase {call.get('case')}\\nscore={score_text}")
        lines.append(f'  E{call_num}["{label}"]')
        lines.append(f"  C{idx} -.->|metric call {call_num}| E{call_num}")

    if isinstance(best_idx, int) and 0 <= best_idx < len(candidates):
        lines.append(f"  class C{best_idx} best")
        lines.append("  classDef best fill:#d9fbe5,stroke:#137333,stroke-width:2px")
    lines.extend(["```", ""])

    lines.extend(
        [
            "## Candidates",
            "",
            "| Candidate | GEPA score | Measured eval scores | Text excerpt |",
            "|---|---:|---:|---|",
        ]
    )
    for idx, text in enumerate(candidates):
        score = scores.get(idx)
        score_text = "" if score is None else f"{score:g}"
        measured_text = ", ".join(f"{item:g}" for item in measured_scores.get(idx, []))
        focus = "seed candidate" if idx == 0 else mutation_label(seed, text, 220)
        lines.append(f"| C{idx} | {score_text} | {measured_text} | {markdown_escape(focus)} |")

    if metric_calls:
        lines.extend(
            [
                "",
                "## Metric Calls",
                "",
                "| Call | Candidate | Case | Score | Tool calls | Result path |",
                "|---:|---:|---:|---:|---:|---|",
            ]
        )
        for call_num, call in enumerate(metric_calls, start=1):
            idx = call.get("candidate")
            candidate = "?" if idx is None else f"C{idx}"
            score = call.get("score")
            score_text = "" if score is None else f"{score:g}"
            result_path = call["result_path"]
            try:
                result_ref = result_path.relative_to(run_dir)
            except ValueError:
                result_ref = result_path
            lines.append(
                "| "
                f"{call_num} | {candidate} | {call.get('case')} | {score_text} | "
                f"{call.get('n_tool_calls') or ''} | `{markdown_escape(str(result_ref))}` |"
            )

    lines.extend(
        [
            "",
            "## Mutations",
            "",
            "| Iteration | Selected | New candidate | Score change | Text diff excerpt |",
            "|---:|---:|---:|---:|---|",
        ]
    )
    for item in log:
        selected = item.get("selected_program_candidate")
        new_idx = item.get("new_program_idx")
        if not isinstance(selected, int) or not isinstance(new_idx, int):
            continue
        iteration = int(item.get("i", 0)) + 1
        old_score = (item.get("subsample_scores") or ["?"])[0]
        new_score = (item.get("new_subsample_scores") or ["?"])[0]
        diff = mutation_summary(candidates[selected], candidates[new_idx])
        lines.append(f"| {iteration} | C{selected} | C{new_idx} | {old_score} -> {new_score} | {diff} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output Markdown file. Defaults to <run_dir>/gepa_report.md.",
    )
    args = parser.parse_args()

    output = args.output or args.run_dir / "gepa_report.md"
    report = build_report(args.run_dir)
    output.write_text(report + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run Omni skill evals through BenchFlow."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT / "evals"
SKILLS_DIR = ROOT / "skills"
STATUS_INTERVAL_SEC = 30

OMNI_ENV_HINT = (
    "Omni credentials are available in environment variables OMNI_BASE_URL and "
    "OMNI_API_TOKEN. If `omni config show` fails because no CLI profile exists "
    "in the sandbox, use `--base-url \"$OMNI_BASE_URL\" --token \"$OMNI_API_TOKEN\"` "
    "with Omni CLI commands instead of asking for credentials."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def benchflow_import_error() -> None:
    print(
        "ERROR: benchflow is not installed. Install it with `uv tool install benchflow` "
        "or run through `./evals/runner.sh`, which can use uv.",
        file=sys.stderr,
    )


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


def selected_case_count(skill: str, case_ids: list[str]) -> int:
    evals_path = SKILLS_DIR / skill / "evals" / "evals.json"
    data = load_json(evals_path)
    return len(selected_cases(data.get("cases", []), case_ids))


def selected_case_ids(skill: str, case_ids: list[str]) -> set[str]:
    evals_path = SKILLS_DIR / skill / "evals" / "evals.json"
    data = load_json(evals_path)
    return {
        str(case.get("id"))
        for case in selected_cases(data.get("cases", []), case_ids)
    }


def job_case_id(job_dir: Path) -> str:
    return job_dir.name.split("__", 1)[0]


def result_reward(result: dict[str, Any]) -> float:
    value = (result.get("rewards") or {}).get("reward")
    return float(value) if isinstance(value, (int, float)) else 0.0


def result_tokens(result: dict[str, Any]) -> int:
    agent_result = result.get("agent_result") or {}
    value = agent_result.get("total_tokens") or result.get("total_tokens")
    return int(value) if isinstance(value, int) else 0


def progress_snapshot(jobs_dir: Path, total_cases: int) -> dict[str, Any]:
    attempts = [
        path
        for path in jobs_dir.glob("*/*")
        if path.is_dir() and "__" in path.name
    ]
    results_by_case: dict[str, dict[str, Any]] = {}
    active_cases: set[str] = set()

    for attempt_dir in attempts:
        case_id = job_case_id(attempt_dir)
        result_path = attempt_dir / "result.json"
        if result_path.exists():
            try:
                result = load_json(result_path)
            except (OSError, json.JSONDecodeError):
                continue
            previous = results_by_case.get(case_id)
            if previous is None or result_reward(result) >= result_reward(previous):
                results_by_case[case_id] = result
        else:
            active_cases.add(case_id)

    done_cases = set(results_by_case)
    active_cases -= done_cases
    errors = sum(1 for result in results_by_case.values() if result.get("error"))
    tokens = sum(result_tokens(result) for result in results_by_case.values())
    passed = sum(1 for result in results_by_case.values() if result_reward(result) >= 1.0)
    partial = sum(1 for result in results_by_case.values() if 0.0 < result_reward(result) < 1.0)

    return {
        "done": len(done_cases),
        "total": total_cases,
        "active": sorted(active_cases, key=lambda item: (not item.isdigit(), int(item) if item.isdigit() else item)),
        "errors": errors,
        "passed": passed,
        "partial": partial,
        "tokens": tokens,
    }


def format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"


def format_progress(label: str, snapshot: dict[str, Any], started_at: datetime, status: str = "running") -> str:
    active = ",".join(snapshot["active"]) if snapshot["active"] else "-"
    return (
        f"  {label}: {status} "
        f"{snapshot['done']}/{snapshot['total']} done "
        f"active={active} "
        f"pass={snapshot['passed']} partial={snapshot['partial']} "
        f"errors={snapshot['errors']} "
        f"tokens={snapshot['tokens']} "
        f"elapsed={format_elapsed((datetime.now() - started_at).total_seconds())}"
    )


async def print_progress_until_done(
    label: str,
    jobs_dir: Path,
    total_cases: int,
    interval_sec: int,
    started_at: datetime,
) -> None:
    last_line = ""
    while True:
        line = format_progress(label, progress_snapshot(jobs_dir, total_cases), started_at)
        if line != last_line:
            print(line, flush=True)
            last_line = line
        await asyncio.sleep(interval_sec)


def allocate_concurrency(skills: list[str], case_counts: dict[str, int], budget: int) -> dict[str, int]:
    """Allocate a global case-concurrency budget across skills."""
    if budget < 1:
        raise ValueError("--concurrency must be at least 1")
    allocations = {skill: 0 for skill in skills}
    remaining = [skill for skill in skills if case_counts.get(skill, 0) > 0]
    slots = budget

    while slots > 0 and remaining:
        next_remaining = []
        for skill in remaining:
            if slots <= 0:
                next_remaining.append(skill)
                continue
            allocations[skill] += 1
            slots -= 1
            if allocations[skill] < case_counts[skill]:
                next_remaining.append(skill)
        remaining = next_remaining

    return {skill: max(1, allocations[skill]) for skill in skills}


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
    timeout_sec: int,
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
    data.setdefault("defaults", {})["timeout_sec"] = timeout_sec

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


def expose_judge_reasoning(tasks_dir: Path) -> None:
    """Patch generated judges to preserve reasoning and score full rollouts."""
    needle = (
        '        Path("/tests/judge_result.json").write_text(json.dumps(result, indent=2))\n'
        "        return max(0.0, min(1.0, score))"
    )
    replacement = (
        '        Path("/tests/judge_result.json").write_text(json.dumps(result, indent=2))\n'
        '        Path("/logs/verifier/judge_result.json").write_text(json.dumps(result, indent=2))\n'
        '        print("Judge result: " + json.dumps(result, indent=2))\n'
        "        return max(0.0, min(1.0, score))"
    )
    for judge_path in tasks_dir.glob("*/tests/judge.py"):
        text = judge_path.read_text()
        if "Judge result:" not in text and needle in text:
            judge_path.write_text(text.replace(needle, replacement))
            text = judge_path.read_text()

        truncation_needle = (
            "    if len(text) > MAX_TRAJECTORY_CHARS:\n"
            "        text = text[:MAX_TRAJECTORY_CHARS] + f\"\\n\\n[TRUNCATED — {len(text)} chars total, showing first {MAX_TRAJECTORY_CHARS}]\"\n"
            "    return text"
        )
        truncation_replacement = (
            "    if len(text) > MAX_TRAJECTORY_CHARS:\n"
            "        total_chars = len(text)\n"
            "        head_chars = MAX_TRAJECTORY_CHARS // 3\n"
            "        tail_chars = MAX_TRAJECTORY_CHARS - head_chars\n"
            "        text = (\n"
            "            text[:head_chars]\n"
            "            + f\"\\n\\n[TRUNCATED — {total_chars} chars total, showing first {head_chars} and last {tail_chars}]\\n\\n\"\n"
            "            + text[-tail_chars:]\n"
            "        )\n"
            "    return text"
        )
        if "showing first {head_chars} and last {tail_chars}" not in text and truncation_needle in text:
            judge_path.write_text(text.replace(truncation_needle, truncation_replacement))
            text = judge_path.read_text()

        read_start = text.find("def read_trajectory() -> str:")
        read_end = text.find("\ndef call_llm", read_start)
        if (
            read_start != -1
            and read_end != -1
            and "def compact_trajectory_event" not in text
        ):
            compact_reader = '''def shorten_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\\n[TRUNCATED {len(value)} chars to {limit}]"


def collect_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\\n".join(part for part in (collect_text(item) for item in value) if part)
    if isinstance(value, dict):
        parts = []
        for key in ("text", "command", "content"):
            if key in value:
                part = collect_text(value[key])
                if part:
                    parts.append(part)
        return "\\n".join(parts)
    return ""


def compact_trajectory_event(event: dict) -> str:
    kind = event.get("type", "event")
    if kind == "tool_call":
        title = event.get("title") or event.get("kind") or "tool"
        status = event.get("status", "")
        output = shorten_text(collect_text(event.get("content", "")), 2500)
        return f"[tool_call] {title} status={status}\\n{output}"
    if kind == "agent_message":
        return "[agent_message]\\n" + shorten_text(str(event.get("text", "")), 6000)
    if kind == "user_message":
        return "[user_message]\\n" + shorten_text(str(event.get("text", "")), 4000)
    if kind == "agent_thought":
        return "[agent_thought]\\n" + shorten_text(str(event.get("text", "")), 500)
    return f"[{kind}]\\n" + shorten_text(json.dumps(event, indent=2), 1200)


def read_trajectory() -> str:
    """Read all available trajectory data as compact evidence for the judge."""
    parts = []
    acp_traj = Path("/logs/agent/acp_trajectory.jsonl")
    if acp_traj.exists():
        for line in acp_traj.read_text().strip().splitlines():
            try:
                event = json.loads(line)
                parts.append(compact_trajectory_event(event))
            except json.JSONDecodeError:
                parts.append(shorten_text(line, 1200))

    for log_file in sorted(Path("/logs/agent").glob("*.txt")):
        parts.append(f"--- {log_file.name} ---\\n{shorten_text(log_file.read_text(), 4000)}")

    text = "\\n\\n".join(parts) if parts else "NO TRAJECTORY FOUND"

    if len(text) > MAX_TRAJECTORY_CHARS:
        total_chars = len(text)
        head_chars = MAX_TRAJECTORY_CHARS // 3
        tail_chars = MAX_TRAJECTORY_CHARS - head_chars
        text = (
            text[:head_chars]
            + f"\\n\\n[TRUNCATED — {total_chars} chars total, showing first {head_chars} and last {tail_chars}]\\n\\n"
            + text[-tail_chars:]
        )
    return text

'''
            judge_path.write_text(text[:read_start] + compact_reader + text[read_end + 1 :])

    test_needle = "cp /tests/reward.txt /logs/verifier/reward.txt\n"
    test_replacement = (
        "cp /tests/reward.txt /logs/verifier/reward.txt\n"
        "if [ -f /tests/judge_result.json ]; then\n"
        "  cp /tests/judge_result.json /logs/verifier/judge_result.json\n"
        "fi\n"
    )
    for test_path in tasks_dir.glob("*/tests/test.sh"):
        text = test_path.read_text()
        if "judge_result.json" in text:
            continue
        if test_needle in text:
            test_path.write_text(text.replace(test_needle, test_replacement))


def omni_agent_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if os.environ.get("OMNI_BASE_URL"):
        env["OMNI_BASE_URL"] = os.environ["OMNI_BASE_URL"]
    if os.environ.get("OMNI_API_TOKEN"):
        env["OMNI_API_TOKEN"] = os.environ["OMNI_API_TOKEN"]
    return {k: v for k, v in env.items() if v}


def run_omni_json(args: list[str], omni_env: dict[str, str]) -> tuple[Any | None, str | None]:
    if not omni_env.get("OMNI_BASE_URL") or not omni_env.get("OMNI_API_TOKEN"):
        return None, "OMNI_BASE_URL and OMNI_API_TOKEN are required for eval preflight checks"
    cmd = [
        "omni",
        *args,
        "--base-url",
        omni_env["OMNI_BASE_URL"],
        "--token",
        omni_env["OMNI_API_TOKEN"],
        "-o",
        "json",
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except FileNotFoundError:
        return None, "Omni CLI is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return None, "Omni CLI preflight command timed out after 45 seconds"

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."
        return None, detail or f"Omni CLI exited with status {completed.returncode}"
    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        detail = completed.stdout.strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."
        return None, f"Omni CLI returned invalid JSON: {exc}; output={detail!r}"


def extract_query_presentations(document: Any) -> list[dict[str, Any]]:
    queue = [document]
    seen = 0
    while queue and seen < 50:
        seen += 1
        candidate = queue.pop(0)
        if isinstance(candidate, dict) and isinstance(candidate.get("queryPresentations"), list):
            return [item for item in candidate["queryPresentations"] if isinstance(item, dict)]
        if isinstance(candidate, dict):
            queue.extend(candidate.values())
        elif isinstance(candidate, list):
            queue.extend(candidate)
    return []


def extract_yaml_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    files = payload.get("files")
    if isinstance(files, dict):
        return "\n".join(str(value) for value in files.values())
    if isinstance(files, list):
        parts = []
        for item in files:
            if isinstance(item, dict):
                parts.append(str(item.get("content", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    for key in ("content", "yaml", "text"):
        if isinstance(payload.get(key), str):
            return payload[key]
    return json.dumps(payload)


def check_content_builder_case2(eval_env: dict[str, str], omni_env: dict[str, str]) -> list[str]:
    document_id = eval_env.get("EVAL_DASHBOARD_TILES")
    if not document_id or document_id.startswith("<"):
        return ["EVAL_DASHBOARD_TILES is missing from eval-env.local.json"]

    document, error = run_omni_json(["documents", "get", document_id], omni_env)
    if error:
        return [f"Could not read EVAL_DASHBOARD_TILES ({document_id}): {error}"]

    presentations = extract_query_presentations(document)
    names = [str(item.get("name", "")).strip() for item in presentations]
    if names != ["Revenue by Month"]:
        found = ", ".join(repr(name) for name in names) or "no tiles"
        return [
            "EVAL_DASHBOARD_TILES is not in the clean setup state for "
            f"omni-content-builder case 2. Expected exactly one tile named "
            f"'Revenue by Month'; found {found}. Recreate the Sales Performance "
            "dashboard from evals/SETUP.md and update eval-env.local.json before running."
        ]
    return []


def extract_user_attribute_names(payload: Any) -> set[str]:
    names: set[str] = set()
    candidates: list[Any] = []
    if isinstance(payload, dict):
        for key in ("records", "Resources", "userAttributes"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        if not candidates:
            candidates.append(payload)
    elif isinstance(payload, list):
        candidates.extend(payload)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ("name", "key", "id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                names.add(value)
    return names


def check_admin_cases(selected: set[str], omni_env: dict[str, str]) -> list[str]:
    if "4" not in selected:
        return []
    attrs, error = run_omni_json(["user-attributes", "list"], omni_env)
    if error:
        return [f"Could not list Omni user attributes for omni-admin case 4: {error}"]
    names = extract_user_attribute_names(attrs)
    if "region" not in names:
        return [
            "omni-admin case 4 requires a custom user attribute definition named "
            "'region', but this Omni instance does not expose one via "
            "`omni user-attributes list`. Create it in Settings -> User Attributes "
            "before running this eval; SCIM can set a value only after the "
            "attribute definition exists."
        ]
    return []


def check_model_builder_cases(
    selected: set[str],
    eval_env: dict[str, str],
    omni_env: dict[str, str],
) -> list[str]:
    model_id = eval_env.get("EVAL_MODEL_ID")
    if not model_id or model_id.startswith("<"):
        return ["EVAL_MODEL_ID is missing from eval-env.local.json"]

    errors: list[str] = []
    order_items, error = run_omni_json(
        ["models", "yaml-get", model_id, "--filename", "public/order_items.view"],
        omni_env,
    )
    if error:
        errors.append(f"Could not read public/order_items.view from EVAL_MODEL_ID ({model_id}): {error}")
    elif "1" in selected and "eval_completed_revenue:" in extract_yaml_text(order_items):
        errors.append(
            "omni-model-builder case 1 is not in the clean setup state: "
            "public/order_items.view already contains eval_completed_revenue. "
            "Remove that field from the eval model or use a fresh eval instance before running."
        )

    if "2" in selected:
        for filename in ("public/customer_segments.view", "customer_segments.view"):
            segments, segment_error = run_omni_json(
                ["models", "yaml-get", model_id, "--filename", filename],
                omni_env,
            )
            if not segment_error and "customer_segments" in extract_yaml_text(segments):
                errors.append(
                    "omni-model-builder case 2 is not in the clean setup state: "
                    f"{filename} already exists. Remove that eval-created view "
                    "or use a fresh eval instance before running."
                )
    if "4" in selected:
        _, topic_error = run_omni_json(
            ["models", "get-topic", model_id, "order_items"],
            omni_env,
        )
        if topic_error:
            errors.append(
                "omni-model-builder case 4 cannot inspect the model topic before "
                f"running: {topic_error}. Fix model access or dynamic environment "
                "routing first; otherwise the agent will loop on infrastructure "
                "errors instead of evaluating schema-refresh impact handling."
            )
    return errors


def run_preflight(skills: list[str], args: argparse.Namespace) -> None:
    eval_env = load_eval_env()
    omni_env = {**omni_agent_env(), **parse_kv(args.agent_env)}
    errors: list[str] = []
    checked = 0

    for skill in skills:
        selected = selected_case_ids(skill, args.case)
        if skill == "omni-admin" and "4" in selected:
            checked += 1
            errors.extend(check_admin_cases(selected, omni_env))
        if skill == "omni-content-builder" and "2" in selected:
            checked += 1
            errors.extend(check_content_builder_case2(eval_env, omni_env))
        if skill == "omni-model-builder" and selected.intersection({"1", "2", "4"}):
            checked += 1
            errors.extend(check_model_builder_cases(selected, eval_env, omni_env))

    if errors:
        print("\npreflight failed; no BenchFlow tasks were started:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            "\nSuggested cleanup:\n"
            "  1. Run ./evals/reset.sh for best-effort automated cleanup.\n"
            "  2. Rerun this command with --preflight-only.\n"
            "  3. If failures remain, fix any Omni connectivity or credential issue, "
            "then follow the specific fixture instructions above and evals/SETUP.md.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if checked:
        print(f"preflight: {checked} remote fixture check(s) passed")


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
    label: str,
    tasks_dir: Path,
    jobs_dir: Path,
    agent: str,
    model: str,
    sandbox: str,
    concurrency: int,
    agent_env: dict[str, str],
    max_retries: int,
    total_cases: int,
    status_interval_sec: int,
) -> dict[str, Any]:
    try:
        from benchflow.evaluation import Evaluation, EvaluationConfig, RetryConfig
    except ImportError:
        benchflow_import_error()
        raise

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
    started_at = datetime.now()
    progress_task: asyncio.Task[None] | None = None
    if status_interval_sec > 0:
        progress_task = asyncio.create_task(
            print_progress_until_done(label, jobs_dir, total_cases, status_interval_sec, started_at)
        )
    try:
        await evaluation.run()
    finally:
        if progress_task is not None:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
    print(format_progress(label, progress_snapshot(jobs_dir, total_cases), started_at, "done"), flush=True)
    summary_path = jobs_dir / "summary.json"
    return load_json(summary_path) if summary_path.exists() else {}


def score_value(summary: dict[str, Any]) -> float:
    value = str(summary.get("score", "0")).rstrip("%")
    try:
        return float(value)
    except ValueError:
        return 0.0


async def run_skill(skill: str, args: argparse.Namespace) -> dict[str, Any]:
    try:
        from benchflow.skill_eval import generate_tasks, load_eval_dataset
    except ImportError:
        benchflow_import_error()
        raise

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
        timeout_sec=args.timeout_sec,
    )
    dataset = load_eval_dataset(generated)
    files_by_case = declared_files_by_case(generated)
    generate_tasks(dataset, tasks_root / "with-skill", with_skill=True)
    stage_case_files(generated, tasks_root / "with-skill", files_by_case)
    expose_judge_reasoning(tasks_root / "with-skill")
    if not args.no_baseline:
        generate_tasks(dataset, tasks_root / "baseline", with_skill=False)
        stage_case_files(generated, tasks_root / "baseline", files_by_case)
        expose_judge_reasoning(tasks_root / "baseline")

    print(f"\n{skill}: {len(dataset.cases)} case(s)")
    print(f"  jobs: {root}")

    with_summary = await run_mode(
        label=f"{skill} with_skill",
        tasks_dir=tasks_root / "with-skill",
        jobs_dir=jobs_root / "with-skill",
        agent=args.agent,
        model=args.model,
        sandbox=args.sandbox,
        concurrency=args.concurrency,
        agent_env=agent_env,
        max_retries=args.max_retries,
        total_cases=len(dataset.cases),
        status_interval_sec=STATUS_INTERVAL_SEC,
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
            label=f"{skill} baseline",
            tasks_dir=tasks_root / "baseline",
            jobs_dir=jobs_root / "baseline",
            agent=args.agent,
            model=args.model,
            sandbox=args.sandbox,
            concurrency=args.concurrency,
            agent_env=agent_env,
            max_retries=args.max_retries,
            total_cases=len(dataset.cases),
            status_interval_sec=STATUS_INTERVAL_SEC,
        )
        print(
            "  baseline:   "
            f"{baseline_summary.get('score', 'n/a')} "
            f"({baseline_summary.get('passed', 0)}/{baseline_summary.get('total', 0)}) "
            f"tokens={baseline_summary.get('total_tokens', 0)}"
        )

    combined = {
        "run_id": args.run_id,
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


async def run_all_skills(skills: list[str], args: argparse.Namespace) -> list[dict[str, Any]]:
    case_counts = {skill: selected_case_count(skill, args.case) for skill in skills}
    empty = [skill for skill, count in case_counts.items() if count == 0]
    if empty:
        raise ValueError(f"No eval cases selected for: {', '.join(empty)}")

    allocations = allocate_concurrency(skills, case_counts, args.concurrency)
    max_parallel_skills = min(len(skills), args.concurrency)
    queue: asyncio.Queue[str] = asyncio.Queue()
    for skill in skills:
        queue.put_nowait(skill)

    print(
        f"\nall: {len(skills)} skill(s), "
        f"{sum(case_counts.values())} case(s) per mode, "
        f"concurrency budget={args.concurrency}"
    )
    print(
        "  skill slots: "
        + ", ".join(f"{skill}={allocations[skill]}" for skill in skills)
    )

    results: list[dict[str, Any]] = []

    async def worker() -> None:
        while True:
            try:
                skill = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                skill_args = argparse.Namespace(**vars(args))
                skill_args.concurrency = allocations[skill]
                results.append(await run_skill(skill, skill_args))
            finally:
                queue.task_done()

    tasks = [asyncio.create_task(worker()) for _ in range(max_parallel_skills)]
    await asyncio.gather(*tasks)
    return results


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
    parser.add_argument("--timeout-sec", type=int, default=int(os.environ.get("EVAL_TIMEOUT_SEC", "1200")))
    parser.add_argument("--max-retries", type=int, default=int(os.environ.get("EVAL_MAX_RETRIES", "1")))
    parser.add_argument("--run-id", default=os.environ.get("EVAL_RUN_ID"), help="Stable id shared by all skill runs in this invocation")
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--no-omni-env-hint", action="store_true")
    parser.add_argument("--preflight-only", action="store_true", help="Check remote fixtures and exit")
    return parser


async def async_main() -> None:
    load_dotenv(EVALS_DIR / ".env.local")
    args = build_parser().parse_args()
    if args.concurrency < 1:
        raise ValueError("--concurrency must be at least 1")
    if not args.run_id:
        args.run_id = datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    print(f"run_id: {args.run_id}")
    skills = discover_skills() if args.skill == "all" else [args.skill]
    run_preflight(skills, args)
    if args.preflight_only:
        return
    if args.skill == "all":
        await run_all_skills(skills, args)
    else:
        await run_skill(skills[0], args)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

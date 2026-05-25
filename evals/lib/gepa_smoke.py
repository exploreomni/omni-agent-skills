"""Cheap GEPA smoke test for the eval harness.

This intentionally uses a deterministic local reflection callable. It verifies
that GEPA can consume an evaluator with Actionable Side Information and evolve a
text artifact, without spending model tokens or running Omni.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
import json
from pathlib import Path

import gepa.optimize_anything as oa
from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig


ROOT = Path(__file__).resolve().parents[2]


REQUIRED_TERMS = ["OMNI_BASE_URL", "OMNI_API_TOKEN", "--base-url", "--token"]


def score_candidate(candidate: str) -> tuple[float, dict[str, str]]:
    found = [item for item in REQUIRED_TERMS if item in candidate]
    missing = [item for item in REQUIRED_TERMS if item not in candidate]

    oa.log(f"Found required terms: {', '.join(found) if found else 'none'}")
    oa.log(f"Missing required terms: {', '.join(missing) if missing else 'none'}")

    score = len(found) / len(REQUIRED_TERMS)
    return score, {
        "Found": ", ".join(found),
        "Missing": ", ".join(missing),
        "Feedback": (
            "Higher score when the candidate names env vars and CLI flags "
            "agents need to authenticate to Omni in a sandbox."
        ),
    }


def _prompt_text(prompt: str | list[dict[str, str]]) -> str:
    if isinstance(prompt, str):
        return prompt
    return "\n".join(str(msg.get("content", "")) for msg in prompt)


# Two candidate bodies the stateful stub returns in sequence. The first scores
# 2/4 (mentions env vars but no CLI flags), the second 4/4. Returning the
# partial answer first forces GEPA to evaluate it, prefer it over the seed via
# its candidate selector, and only *then* converge on the full answer — which
# is what a real reflection loop has to do.
_PARTIAL_BODY = (
    "Use the OMNI_BASE_URL environment variable when invoking the Omni CLI.\n"
    "Also set OMNI_API_TOKEN before running commands."
)
_FULL_BODY = (
    "Omni credentials are available as OMNI_BASE_URL and OMNI_API_TOKEN.\n"
    "When the sandbox has no local Omni CLI profile, pass them explicitly:\n"
    'omni <command> --base-url "$OMNI_BASE_URL" --token "$OMNI_API_TOKEN"'
)


def _wrap(body: str) -> str:
    return f"```text\n{body}\n```"


class StatefulReflectionStub:
    """Deterministic reflection LM that improves over multiple calls and validates each prompt.

    On every call this stub asserts:
      1. GEPA filled the `<curr_param>` and `<side_info>` template placeholders.
      2. The evaluator's ASI markers (`Found`/`Missing`/`Feedback` + log lines) reached the prompt.
      3. The text of the candidate this stub returned last time is now present in the prompt —
         which is how we know GEPA's candidate selector kept the higher-scoring proposal and
         threaded it back into the next reflection round.

    Then it returns an improving candidate so the engine actually exercises
    selection across iterations rather than locking in a one-shot win.
    """

    def __init__(self, seed: str) -> None:
        self._calls = 0
        # First reflection prompt is built against the seed candidate.
        self._expected_in_next_prompt = seed

    def __call__(self, prompt: str | list[dict[str, str]]) -> str:
        text = _prompt_text(prompt)

        for placeholder in ("<curr_param>", "<side_info>"):
            if placeholder in text:
                raise AssertionError(
                    f"Reflection prompt still contains unfilled placeholder {placeholder!r}; "
                    "GEPA did not assemble the template as expected."
                )

        for marker in ("Missing required terms", "Found required terms", "Feedback"):
            if marker not in text:
                raise AssertionError(
                    f"Reflection prompt is missing evaluator side_info marker {marker!r}; "
                    "ASI did not reach the reflection step."
                )

        # First non-trivial line of the previous candidate should appear in the prompt.
        snippet = next(
            (line.strip() for line in self._expected_in_next_prompt.splitlines() if line.strip()),
            "",
        )[:60]
        if snippet and snippet not in text:
            raise AssertionError(
                f"Reflection prompt does not contain text from the previous candidate "
                f"(expected snippet {snippet!r}). GEPA may not be threading the selected "
                "candidate back into <curr_param>."
            )

        self._calls += 1
        body = _PARTIAL_BODY if self._calls == 1 else _FULL_BODY
        self._expected_in_next_prompt = body
        return _wrap(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a cheap local GEPA smoke test.")
    parser.add_argument(
        "--run-dir",
        default="",
        help="Directory for GEPA run artifacts. Defaults to a timestamped workspace.",
    )
    parser.add_argument(
        "--max-metric-calls",
        type=int,
        default=6,
        help=(
            "Metric-call budget for the smoke test. Default of 6 is enough to "
            "score the seed, evaluate two reflection proposals, and exercise "
            "candidate selection between them."
        ),
    )
    parser.add_argument(
        "--keep-run-dir",
        action="store_true",
        help="Reuse the existing GEPA run directory instead of starting fresh.",
    )
    parser.add_argument(
        "--reflection-model",
        default=None,
        help=(
            "Optional LiteLLM-compatible model string for GEPA's reflection step "
            "(e.g. 'anthropic/claude-sonnet-4-6' or 'openai/gpt-5.1'). When omitted, "
            "a deterministic local stub is used and no API tokens are spent. "
            "Pass --reflection-model \"$EVAL_MODEL\" to match the model benchflow runs with."
        ),
    )
    args = parser.parse_args()

    # Bridge to benchflow's EVAL_MODEL: if --reflection-model wasn't given but the
    # caller explicitly opted in by setting GEPA_USE_EVAL_MODEL=1, inherit the same
    # model benchflow uses. We require the explicit opt-in so that simply having
    # EVAL_MODEL in env (the common case) doesn't silently turn the smoke test
    # into a real-API run.
    if args.reflection_model is None and os.environ.get("GEPA_USE_EVAL_MODEL") == "1":
        eval_model = os.environ.get("EVAL_MODEL")
        if not eval_model:
            raise SystemExit(
                "GEPA_USE_EVAL_MODEL=1 was set but EVAL_MODEL is empty. "
                "Either set EVAL_MODEL or pass --reflection-model explicitly."
            )
        args.reflection_model = eval_model
        print(f"[gepa_smoke] Using EVAL_MODEL={eval_model!r} for reflection LM.")

    run_dir = (
        ROOT / args.run_dir
        if args.run_dir
        else ROOT / "evals" / "workspaces" / "gepa-smoke" / datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    )
    if run_dir.exists() and not args.keep_run_dir:
        raise SystemExit(f"Run directory already exists: {run_dir}. Pass --keep-run-dir to reuse it.")
    run_dir.mkdir(parents=True, exist_ok=True)

    seed = "Use the local Omni CLI profile if one exists."
    # Default to the deterministic local stub; only fall back to a real LiteLLM
    # model when the caller explicitly opted in via --reflection-model or
    # GEPA_USE_EVAL_MODEL=1. A string here is consumed by GEPA's make_litellm_lm.
    reflection_lm = args.reflection_model if args.reflection_model else StatefulReflectionStub(seed)
    result = oa.optimize_anything(
        seed_candidate=seed,
        evaluator=score_candidate,
        objective=(
            "Improve a short instruction for agents running Omni CLI commands "
            "inside an isolated eval sandbox."
        ),
        background=(
            "Eval sandboxes start with no Omni CLI auth profile on disk. Two "
            "environment variables are injected: OMNI_BASE_URL points at the "
            "instance, OMNI_API_TOKEN is the API token. The Omni CLI accepts "
            "--base-url and --token flags to consume these explicitly, e.g. "
            "`omni queries run --base-url \"$OMNI_BASE_URL\" --token \"$OMNI_API_TOKEN\"`."
        ),
        config=GEPAConfig(
            engine=EngineConfig(
                run_dir=str(run_dir),
                max_metric_calls=args.max_metric_calls,
                display_progress_bar=False,
                # parallel=False and use_cloudpickle=False keep the local reflection
                # closure usable without pickling and keep log ordering deterministic.
                parallel=False,
                capture_stdio=True,
                use_cloudpickle=False,
            ),
            reflection=ReflectionConfig(reflection_lm=reflection_lm),
        ),
    )

    best_score = result.val_aggregate_scores[result.best_idx]
    summary = {
        "best_idx": result.best_idx,
        "best_score": best_score,
        "total_metric_calls": result.total_metric_calls,
        "best_candidate": result.best_candidate,
        "run_dir": str(run_dir),
    }
    print(json.dumps(summary, indent=2))

    # Regression guards: a green run must prove the loop actually iterated,
    # produced a non-seed best candidate, and reached the perfect score.
    if result.total_metric_calls <= 1:
        print("FAIL: GEPA only ran one metric call; reflection never fired.")
        return 1
    if result.best_candidate == seed:
        print("FAIL: best candidate equals the seed; reflection did not win.")
        return 1
    if best_score < 1.0:
        print(f"FAIL: best_score={best_score} did not reach 1.0.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Cheap GEPA smoke test for the eval harness.

This intentionally uses a deterministic local reflection callable. It verifies
that GEPA can consume an evaluator with Actionable Side Information and evolve a
text artifact, without spending model tokens or running Omni.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

import gepa.optimize_anything as oa
from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig


ROOT = Path(__file__).resolve().parents[2]


def score_candidate(candidate: str) -> tuple[float, dict[str, str]]:
    required = [
        "OMNI_BASE_URL",
        "OMNI_API_TOKEN",
        "--base-url",
        "--token",
    ]
    found = [item for item in required if item in candidate]
    missing = [item for item in required if item not in candidate]

    oa.log(f"Found required terms: {', '.join(found) if found else 'none'}")
    oa.log(f"Missing required terms: {', '.join(missing) if missing else 'none'}")
    oa.log("Goal: tell agents to use env-backed Omni CLI credentials in sandboxes.")

    score = len(found) / len(required)
    return score, {
        "found": ", ".join(found),
        "missing": ", ".join(missing),
        "hint": (
            "The candidate should mention OMNI_BASE_URL and OMNI_API_TOKEN and "
            "show the Omni CLI flags --base-url and --token."
        ),
    }


def local_reflection_lm(prompt: str | list[dict[str, str]]) -> str:
    """Return a valid GEPA candidate from the reflection prompt contract."""
    return """```text
Omni credentials are available as OMNI_BASE_URL and OMNI_API_TOKEN.
When the sandbox has no local Omni CLI profile, pass them explicitly:
omni <command> --base-url "$OMNI_BASE_URL" --token "$OMNI_API_TOKEN"
```"""


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
        default=3,
        help="Small metric-call budget for the smoke test.",
    )
    parser.add_argument(
        "--keep-run-dir",
        action="store_true",
        help="Reuse the existing GEPA run directory instead of starting fresh.",
    )
    args = parser.parse_args()

    run_dir = (
        ROOT / args.run_dir
        if args.run_dir
        else ROOT / "evals" / "workspaces" / "gepa-smoke" / datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    )
    if run_dir.exists() and not args.keep_run_dir:
        raise SystemExit(f"Run directory already exists: {run_dir}. Pass --keep-run-dir to reuse it.")
    run_dir.mkdir(parents=True, exist_ok=True)

    result = oa.optimize_anything(
        seed_candidate="Use the local Omni CLI profile if one exists.",
        evaluator=score_candidate,
        objective=(
            "Improve a short instruction for agents running Omni CLI commands "
            "inside an isolated eval sandbox."
        ),
        config=GEPAConfig(
            engine=EngineConfig(
                run_dir=str(run_dir),
                max_metric_calls=args.max_metric_calls,
                display_progress_bar=False,
                parallel=False,
                capture_stdio=True,
                use_cloudpickle=False,
            ),
            reflection=ReflectionConfig(reflection_lm=local_reflection_lm),
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
    return 0 if best_score >= 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

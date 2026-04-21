#!/usr/bin/env python3
"""Aggregate grading.json files from an iteration into benchmark.json.

Usage: python3 evals/compute_benchmark.py <iteration-dir>
"""

import glob
import json
import math
import os
import sys


def mean_stddev(values: list[float]) -> dict:
    if not values:
        return {"mean": 0.0, "stddev": 0.0}
    n = len(values)
    mu = sum(values) / n
    variance = sum((x - mu) ** 2 for x in values) / n if n > 1 else 0.0
    return {"mean": round(mu, 4), "stddev": round(math.sqrt(variance), 4)}


def collect(iter_dir: str, config: str) -> tuple[list, list, list]:
    rates, tokens, durations = [], [], []

    pattern = os.path.join(iter_dir, "eval-*", config, "grading.json")
    for grading_path in sorted(glob.glob(pattern)):
        run_dir = os.path.dirname(grading_path)

        with open(grading_path) as f:
            g = json.load(f)
        rates.append(g["summary"]["pass_rate"])

        timing_path = os.path.join(run_dir, "timing.json")
        if os.path.exists(timing_path):
            with open(timing_path) as f:
                t = json.load(f)
            tokens.append(t.get("total_tokens", 0))
            durations.append(t.get("duration_ms", 0) / 1000)  # ms → s

    return rates, tokens, durations


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: compute_benchmark.py <iteration-dir>", file=sys.stderr)
        sys.exit(1)

    iter_dir = sys.argv[1]

    with_rates, with_tokens, with_durations = collect(iter_dir, "with_skill")
    without_rates, without_tokens, without_durations = collect(iter_dir, "without_skill")

    with_pr = mean_stddev(with_rates)["mean"]
    without_pr = mean_stddev(without_rates)["mean"]
    with_t = mean_stddev(with_durations)["mean"]
    without_t = mean_stddev(without_durations)["mean"]
    with_tok = mean_stddev(with_tokens)["mean"]
    without_tok = mean_stddev(without_tokens)["mean"]

    benchmark = {
        "run_summary": {
            "with_skill": {
                "pass_rate": mean_stddev(with_rates),
                "time_seconds": mean_stddev(with_durations),
                "tokens": mean_stddev(with_tokens),
            },
            "without_skill": {
                "pass_rate": mean_stddev(without_rates),
                "time_seconds": mean_stddev(without_durations),
                "tokens": mean_stddev(without_tokens),
            },
            "delta": {
                "pass_rate": round(with_pr - without_pr, 4),
                "time_seconds": round(with_t - without_t, 2),
                "tokens": round(with_tok - without_tok, 0),
            },
        }
    }

    out_path = os.path.join(iter_dir, "benchmark.json")
    with open(out_path, "w") as f:
        json.dump(benchmark, f, indent=2)

    print(json.dumps(benchmark, indent=2))


if __name__ == "__main__":
    main()

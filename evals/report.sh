#!/usr/bin/env bash
# evals/report.sh — Generate an HTML report from an iteration workspace
#
# Usage:
#   ./evals/report.sh <iteration-dir> [--open]
#
# Example:
#   ./evals/report.sh evals/workspaces/omni-query/iteration-1-sonnet-4-6 --open
#
# Reads:  benchmark.json, meta.json, eval-*/with_skill|without_skill/{grading,timing,raw_output}.json
# Writes: <iteration-dir>/report.html

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SCRIPT_DIR/report-template.html"

OPEN_BROWSER=false
ITER_DIR=""

for arg in "$@"; do
  case "$arg" in
    --open) OPEN_BROWSER=true ;;
    *)
      if [[ -z "$ITER_DIR" ]]; then ITER_DIR="$arg"
      else echo "Error: unexpected argument '$arg'" >&2; exit 1
      fi ;;
  esac
done

[[ -z "$ITER_DIR" ]]           && { echo "Usage: $0 <iteration-dir> [--open]" >&2; exit 1; }
ITER_DIR="$(cd "$ITER_DIR" && pwd)"
[[ -f "$ITER_DIR/benchmark.json" ]] || { echo "Error: benchmark.json not found in $ITER_DIR" >&2; exit 1; }
[[ -f "$ITER_DIR/meta.json" ]]      || { echo "Error: meta.json not found in $ITER_DIR" >&2; exit 1; }
[[ -f "$TEMPLATE" ]]                || { echo "Error: template not found at $TEMPLATE" >&2; exit 1; }
command -v jq >/dev/null 2>&1       || { echo "Error: jq is required" >&2; exit 1; }

META=$(cat "$ITER_DIR/meta.json")
BENCHMARK=$(cat "$ITER_DIR/benchmark.json")

SKILL=$(echo "$META"             | jq -r '.skill')
MODEL=$(echo "$META"             | jq -r '.model')
ITERATION=$(echo "$META"         | jq -r '.iteration')
RUN_DATE=$(echo "$META"          | jq -r '.run_date')
REASONING_EFFORT=$(echo "$META"  | jq -r '.reasoning_effort // ""')

# Eval prompts from the skill's evals.json (best-effort)
EVALS_FILE="$ROOT_DIR/skills/$SKILL/evals/evals.json"

# ── Build per-eval array ─────────────────────────────────────────────────────

EVALS_JSON="[]"

for eval_dir in "$ITER_DIR"/eval-*/; do
  [[ -d "$eval_dir" ]] || continue
  eval_id="${eval_dir%/}"; eval_id="${eval_id##*eval-}"

  PROMPT=""
  if [[ -f "$EVALS_FILE" ]]; then
    PROMPT=$(jq -r \
      ".evals[] | select((.id | tostring) == \"$eval_id\") | .prompt" \
      "$EVALS_FILE" 2>/dev/null || true)
  fi

  # Look up aggregated stats for this eval from benchmark.json's per_eval array.
  # When per_eval isn't present (older runs), this just yields nulls and the template
  # falls back to its flat-layout behavior.
  PER_EVAL_STATS=$(echo "$BENCHMARK" | jq \
    --arg id "$eval_id" \
    '.per_eval // [] | map(select(.eval_id == $id)) | first // null')

  CONFIGS_JSON="{}"
  for config in with_skill without_skill; do
    config_dir="$eval_dir$config"
    [[ -d "$config_dir" ]] || continue

    # Find the source run dir: nested run-1/ if present, otherwise the config dir itself.
    first_run=$(find "$config_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null | sort -V | head -1)
    if [[ -n "$first_run" ]]; then
      run_dir="$first_run"
      n_runs=$(find "$config_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null | wc -l | tr -d ' ')
    else
      run_dir="$config_dir"
      n_runs=1
    fi

    RESULT=""; ASSERTIONS="[]"; PASS_RATE="null"; DURATION_S="null"; TOKENS="null"

    [[ -f "$run_dir/raw_output.json" ]] && \
      RESULT=$(jq -r '.result // ""' "$run_dir/raw_output.json" 2>/dev/null || true)

    if [[ -f "$run_dir/grading.json" ]]; then
      ASSERTIONS=$(jq '.assertion_results' "$run_dir/grading.json" 2>/dev/null || echo "[]")
      PASS_RATE=$(jq '.summary.pass_rate' "$run_dir/grading.json" 2>/dev/null || echo "null")
    fi

    if [[ -f "$run_dir/timing.json" ]]; then
      DURATION_S=$(jq '(.duration_ms / 1000)' "$run_dir/timing.json" 2>/dev/null || echo "null")
      TOKENS=$(jq '.total_tokens' "$run_dir/timing.json" 2>/dev/null || echo "null")
    fi

    # Pull aggregated stats (median/iqr/n) for this (eval, config) from per_eval.
    AGG_STATS=$(echo "$PER_EVAL_STATS" | jq --arg c "$config" '.[$c] // null')

    CONFIG_OBJ=$(jq -n \
      --argjson pass_rate  "$PASS_RATE" \
      --argjson duration_s "$DURATION_S" \
      --argjson tokens     "$TOKENS" \
      --argjson n_runs     "$n_runs" \
      --arg     result     "$RESULT" \
      --argjson assertions "$ASSERTIONS" \
      --argjson agg        "$AGG_STATS" \
      '{pass_rate: $pass_rate, duration_s: $duration_s, tokens: $tokens,
        n_runs: $n_runs, result: $result, assertions: $assertions, agg: $agg}')

    CONFIGS_JSON=$(echo "$CONFIGS_JSON" | jq \
      --arg     k "$config" \
      --argjson v "$CONFIG_OBJ" \
      '. + {($k): $v}')
  done

  EVAL_OBJ=$(jq -n \
    --arg     id     "$eval_id" \
    --arg     prompt "$PROMPT" \
    --argjson ws     "$(echo "$CONFIGS_JSON" | jq '.with_skill    // null')" \
    --argjson wo     "$(echo "$CONFIGS_JSON" | jq '.without_skill // null')" \
    '{id: $id, prompt: $prompt, with_skill: $ws, without_skill: $wo}')

  EVALS_JSON=$(echo "$EVALS_JSON" | jq --argjson e "$EVAL_OBJ" '. + [$e]')
done

# ── Combine and inject ───────────────────────────────────────────────────────

TMPFILE=$(mktemp /tmp/eval-report-XXXXXX.json)
trap 'rm -f "$TMPFILE"' EXIT

jq -n \
  --arg     skill             "$SKILL" \
  --arg     model             "$MODEL" \
  --argjson iteration         "$ITERATION" \
  --arg     run_date          "$RUN_DATE" \
  --arg     reasoning_effort  "$REASONING_EFFORT" \
  --argjson run_summary       "$(echo "$BENCHMARK" | jq '.run_summary')" \
  --argjson evals             "$EVALS_JSON" \
  '{skill: $skill, model: $model, iteration: $iteration, run_date: $run_date,
    reasoning_effort: (if $reasoning_effort == "" then null else $reasoning_effort end),
    run_summary: $run_summary, evals: $evals}' \
  > "$TMPFILE"

OUTPUT_FILE="$ITER_DIR/report.html"

# Python handles JSON injection safely (avoids awk backslash/newline issues)
python3 - "$TEMPLATE" "$TMPFILE" "$OUTPUT_FILE" <<'PYEOF'
import sys
template = open(sys.argv[1]).read()
data     = open(sys.argv[2]).read()
marker   = '<script id="eval-data" type="application/json"></script>'
replaced = template.replace(
    marker,
    '<script id="eval-data" type="application/json">' + data + '</script>'
)
open(sys.argv[3], 'w').write(replaced)
PYEOF

echo "Report generated: $OUTPUT_FILE"

if [[ "$OPEN_BROWSER" == true ]]; then
  if   [[ "$(uname)" == "Darwin" ]]; then open "$OUTPUT_FILE"
  elif command -v xdg-open &>/dev/null;  then xdg-open "$OUTPUT_FILE"
  else echo "Open manually: $OUTPUT_FILE"
  fi
fi

#!/usr/bin/env bash
# evals/scorer.sh — Grade assertions and produce grading.json + benchmark.json
#
# For each eval case in an iteration workspace, reads the agent's output and
# grades each assertion using an LLM judge. Writes grading.json to each run
# directory and aggregates results into benchmark.json for the iteration.
#
# Usage:
#   ./evals/scorer.sh <skill> <iteration-dir>
#
# Example:
#   ./evals/scorer.sh omni-query evals/workspaces/omni-query/iteration-1
#
# Optional env:
#   GRADER_MODEL   Claude model for grading (default: claude-sonnet-4-6)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GRADER_MODEL="${GRADER_MODEL:-claude-sonnet-4-6}"

# ── Helpers ───────────────────────────────────────────────────────────────────

substitute_vars() {
  local text="$1"
  local config="$SCRIPT_DIR/eval-env.local.json"
  [[ -f "$config" ]] || config="$SCRIPT_DIR/eval-env.json"
  [[ -f "$config" ]] || { echo "$text"; return; }
  while IFS= read -r pair; do
    local key="${pair%%=*}" value="${pair#*=}"
    text=$(echo "$text" | sed "s|{{${key}}}|${value}|g")
  done < <(jq -r 'to_entries[] | select(.key != "_comment") | "\(.key)=\(.value)"' "$config")
  echo "$text"
}

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") <skill|all> [iteration-dir]

Grades assertions against agent output and writes grading.json + benchmark.json.
When skill is "all", scores the latest iteration for every skill in workspaces/.

  GRADER_MODEL env var   Model for LLM grading (default: claude-sonnet-4-6)

Examples:
  ./evals/scorer.sh all
  ./evals/scorer.sh omni-query evals/workspaces/omni-query/iteration-1-sonnet-4-6
EOF
  exit 1
}

check_deps() {
  local missing=()
  command -v claude  >/dev/null 2>&1 || missing+=(claude)
  command -v jq      >/dev/null 2>&1 || missing+=(jq)
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  if (( ${#missing[@]} > 0 )); then
    echo "ERROR: Missing required tools: ${missing[*]}" >&2
    exit 1
  fi
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set" >&2
    exit 1
  fi
}

extract_output_text() {
  # Extract the agent's text response from the claude --output-format json envelope
  jq -r '.result // ""' "$1" 2>/dev/null || echo ""
}

# ── LLM grading ───────────────────────────────────────────────────────────────

grade_assertion() {
  local assertion="$1" output_text="$2"

  # Delegate to the Python helper to avoid bash quoting complexity
  local payload
  payload=$(jq -n \
    --arg assertion "$assertion" \
    --arg output "$output_text" \
    '{"assertion": $assertion, "output": $output}')

  echo "$payload" | python3 "$SCRIPT_DIR/grade_assertion.py" "$GRADER_MODEL" \
    2>/dev/null || echo '{"passed":false,"evidence":"Grading call failed"}'
}

grade_run() {
  local run_dir="$1" evals_file="$2" eval_id="$3"

  if [[ ! -f "$run_dir/raw_output.json" ]]; then
    echo "    WARNING: no raw_output.json in $run_dir" >&2
    echo '{"assertion_results":[],"summary":{"passed":0,"failed":0,"total":0,"pass_rate":0}}' \
      > "$run_dir/grading.json"
    return
  fi

  local output_text
  output_text=$(extract_output_text "$run_dir/raw_output.json")

  # Fetch assertions for this eval id (id may be a number or string)
  local assertions_json
  assertions_json=$(jq -c \
    "[.evals[] | select(.id == ($eval_id | tonumber? // .) or (.id | tostring) == \"$eval_id\") | .assertions // []] | first // []" \
    "$evals_file" 2>/dev/null || echo "[]")

  local n_assertions
  n_assertions=$(echo "$assertions_json" | jq 'length')

  if (( n_assertions == 0 )); then
    echo "    WARNING: no assertions found for eval $eval_id" >&2
    echo '{"assertion_results":[],"summary":{"passed":0,"failed":0,"total":0,"pass_rate":0}}' \
      > "$run_dir/grading.json"
    return
  fi

  local results_arr="[]"
  local n_passed=0

  for i in $(seq 0 $(( n_assertions - 1 ))); do
    local assertion
    assertion=$(substitute_vars "$(echo "$assertions_json" | jq -r ".[$i]")")

    local preview="${assertion:0:55}"
    [[ ${#assertion} -gt 55 ]] && preview="${preview}..."
    printf "      [%d/%d] %s " $(( i + 1 )) "$n_assertions" "$preview"

    local grade
    grade=$(grade_assertion "$assertion" "$output_text")

    local is_passed
    is_passed=$(echo "$grade" | jq -r '.passed' 2>/dev/null || echo "false")
    [[ "$is_passed" == "true" ]] && (( n_passed++ )) || true

    local verdict="FAIL"
    [[ "$is_passed" == "true" ]] && verdict="PASS"
    printf "%s\n" "$verdict"

    local entry
    entry=$(jq -n \
      --arg text "$assertion" \
      --argjson grade "$grade" \
      '{text: $text, passed: $grade.passed, evidence: ($grade.evidence // "")}')

    results_arr=$(echo "$results_arr" | jq -c ". + [$entry]")
  done

  local n_failed=$(( n_assertions - n_passed ))
  local pass_rate
  pass_rate=$(python3 -c "print(round($n_passed / $n_assertions, 4))")

  jq -n \
    --argjson results "$results_arr" \
    --argjson passed "$n_passed" \
    --argjson failed "$n_failed" \
    --argjson total "$n_assertions" \
    --argjson rate "$pass_rate" \
    '{assertion_results: $results, summary: {passed: $passed, failed: $failed, total: $total, pass_rate: $rate}}' \
    > "$run_dir/grading.json"
}

# ── Score one skill ───────────────────────────────────────────────────────────

score_skill() {
  local skill="$1" iter_dir="$2"
  local evals_file="$ROOT_DIR/skills/$skill/evals/evals.json"

  if [[ ! -f "$evals_file" ]]; then
    echo "ERROR: $evals_file not found" >&2; return 1
  fi

  echo ""
  echo "Scoring $skill — $(basename "$iter_dir")  (grader: $GRADER_MODEL)"
  echo ""

  for eval_dir in "$iter_dir"/eval-*/; do
    [[ -d "$eval_dir" ]] || continue
    local eval_id="${eval_dir%/}"; eval_id="${eval_id##*eval-}"

    echo "  eval $eval_id:"
    for config in with_skill without_skill; do
      echo "    [$config]"
      grade_run "$eval_dir/$config" "$evals_file" "$eval_id"
    done
    echo ""
  done

  echo "  Computing benchmark..."
  python3 "$SCRIPT_DIR/compute_benchmark.py" "$iter_dir"

  # Publish merged result to evals/results/<skill>/iteration-N-<slug>.json
  local results_dir="$SCRIPT_DIR/results/$skill"
  mkdir -p "$results_dir"

  local meta_file="$iter_dir/meta.json"
  local benchmark_file="$iter_dir/benchmark.json"
  local dest

  if [[ -f "$meta_file" ]]; then
    local iter_num model_slug
    iter_num=$(jq -r '.iteration' "$meta_file")
    model_slug=$(jq -r '.model_slug' "$meta_file")
    dest="$results_dir/iteration-${iter_num}-${model_slug}.json"
    jq -s '.[0] * {meta: .[1]}' "$benchmark_file" "$meta_file" > "$dest"
  else
    dest="$results_dir/$(basename "$iter_dir").json"
    cp "$benchmark_file" "$dest"
  fi

  echo ""
  echo "Done"
  echo "  benchmark: $benchmark_file"
  echo "  published: $dest"
}

# ── Entry point ───────────────────────────────────────────────────────────────

check_deps

SKILL="${1:-}"
[[ -z "$SKILL" ]] && usage

if [[ "$SKILL" == "all" ]]; then
  WORKSPACES_DIR="$SCRIPT_DIR/workspaces"
  if [[ ! -d "$WORKSPACES_DIR" ]]; then
    echo "ERROR: no workspaces directory found at $WORKSPACES_DIR" >&2; exit 1
  fi
  for skill_dir in "$WORKSPACES_DIR"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill=$(basename "$skill_dir")
    # Pick the latest iteration directory
    iter_dir=$(ls -d "$skill_dir"iteration-* 2>/dev/null | sort -V | tail -1)
    if [[ -z "$iter_dir" ]]; then
      echo "WARNING: no iteration dir for $skill, skipping" >&2
      continue
    fi
    score_skill "$skill" "$(cd "$iter_dir" && pwd)"
  done
else
  ITER_DIR="${2:-}"
  if [[ -z "$ITER_DIR" ]]; then
    # Auto-detect latest iteration for this skill
    ITER_DIR=$(ls -d "$SCRIPT_DIR/workspaces/$SKILL/iteration-"* 2>/dev/null | sort -V | tail -1)
    [[ -z "$ITER_DIR" ]] && { echo "ERROR: no iteration dir found for $SKILL" >&2; exit 1; }
    echo "Auto-detected: $ITER_DIR"
  fi
  ITER_DIR="$(cd "$ITER_DIR" && pwd)"
  score_skill "$SKILL" "$ITER_DIR"
fi

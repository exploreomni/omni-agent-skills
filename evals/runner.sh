#!/usr/bin/env bash
set -euo pipefail

# ─── Skill Eval Runner ───────────────────────────────────────────────────────
# Spawns headless Claude Code agents to evaluate skill impact.
# Runs each scenario with and without the skill, then scores results.
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ─── Dependency checks ───────────────────────────────────────────────────────

check_dependencies() {
  if ! command -v yq &>/dev/null; then
    echo "Error: yq is required but not installed."
    echo "Install with: brew install yq"
    exit 1
  fi
  if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed."
    echo "Install with: brew install jq"
    exit 1
  fi
  if ! command -v claude &>/dev/null; then
    echo "Error: claude CLI is required but not installed."
    echo "See: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
  fi
}

# ─── Defaults from config.yaml ───────────────────────────────────────────────

load_defaults() {
  local config_file="$SCRIPT_DIR/config.yaml"
  if [[ ! -f "$config_file" ]]; then
    echo "Error: config.yaml not found at $config_file"
    exit 1
  fi
  DEFAULT_RUNS=$(yq '.defaults.runs_per_config' "$config_file")
  DEFAULT_MODEL=$(yq '.defaults.model' "$config_file")
  DEFAULT_PERMISSION_MODE=$(yq '.defaults.permission_mode' "$config_file")
  DEFAULT_OUTPUT_DIR=$(yq '.defaults.output_dir' "$config_file")
}

# ─── Usage ────────────────────────────────────────────────────────────────────

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --skill <name>                Skill to evaluate (e.g. omni-model-explorer)
  --all                         Run all scenarios in evals/scenarios/
  --scenario <id>               Run a specific scenario by id
  --runs <N>                    Number of runs per config (default: $DEFAULT_RUNS)
  --config-only <config>        Only run with-skill or without-skill
  --model <model>               Model to use (default: $DEFAULT_MODEL)
  --output-dir <path>           Output directory (default: $DEFAULT_OUTPUT_DIR)
  -h, --help                    Show this help message

Examples:
  $(basename "$0") --skill omni-model-explorer
  $(basename "$0") --skill omni-model-explorer --scenario list-models --runs 5
  $(basename "$0") --all
EOF
  exit 0
}

# ─── Parse CLI args ──────────────────────────────────────────────────────────

parse_args() {
  SKILL=""
  RUN_ALL=false
  SCENARIO_FILTER=""
  RUNS=""
  CONFIG_ONLY=""
  MODEL=""
  OUTPUT_DIR=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skill) SKILL="$2"; shift 2 ;;
      --all) RUN_ALL=true; shift ;;
      --scenario) SCENARIO_FILTER="$2"; shift 2 ;;
      --runs) RUNS="$2"; shift 2 ;;
      --config-only) CONFIG_ONLY="$2"; shift 2 ;;
      --model) MODEL="$2"; shift 2 ;;
      --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
      -h|--help) usage ;;
      *) echo "Unknown option: $1"; usage ;;
    esac
  done

  # Apply defaults
  RUNS="${RUNS:-$DEFAULT_RUNS}"
  MODEL="${MODEL:-$DEFAULT_MODEL}"
  OUTPUT_DIR="${OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"

  # Resolve relative output dir against repo root
  if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR="$ROOT_DIR/$OUTPUT_DIR"
  fi

  if [[ "$RUN_ALL" == false && -z "$SKILL" ]]; then
    echo "Error: --skill <name> or --all is required."
    usage
  fi

  if [[ -n "$CONFIG_ONLY" && "$CONFIG_ONLY" != "with-skill" && "$CONFIG_ONLY" != "without-skill" ]]; then
    echo "Error: --config-only must be 'with-skill' or 'without-skill'"
    exit 1
  fi
}

# ─── Find scenario files ────────────────────────────────────────────────────

find_scenario_files() {
  local skill="$1"
  local scenario_dir="$SCRIPT_DIR/scenarios"
  local pattern="${skill}.eval.yaml"

  if [[ ! -f "$scenario_dir/$pattern" ]]; then
    echo "Error: No scenario file found at $scenario_dir/$pattern"
    exit 1
  fi

  echo "$scenario_dir/$pattern"
}

find_all_scenario_files() {
  local scenario_dir="$SCRIPT_DIR/scenarios"
  find "$scenario_dir" -name "*.eval.yaml" -type f | sort
}

# ─── Run a single scenario+config+run ───────────────────────────────────────

run_single() {
  local skill="$1"
  local scenario_id="$2"
  local prompt="$3"
  local config="$4"
  local run_num="$5"
  local run_dir="$6"
  local skill_file="$ROOT_DIR/skills/$skill/SKILL.md"

  local output_file="$run_dir/run-${run_num}.json"

  echo "  Running scenario '$scenario_id' [$config] run $run_num/$RUNS..."

  local claude_args=(-p --output-format json --verbose --bare)
  claude_args+=(--permission-mode "$DEFAULT_PERMISSION_MODE")
  claude_args+=(--model "$MODEL")

  if [[ "$config" == "with-skill" ]]; then
    if [[ ! -f "$skill_file" ]]; then
      echo "    Warning: Skill file not found at $skill_file"
    fi
    claude_args+=(--append-system-prompt-file "$skill_file")
  fi

  # Run claude and capture output; continue on failure
  if claude "${claude_args[@]}" "$prompt" > "$output_file" 2>"${output_file%.json}.stderr" ; then
    echo "    Completed successfully."
  else
    echo "    Warning: claude exited with non-zero status. Output saved."
    # Ensure the file exists even on failure
    if [[ ! -s "$output_file" ]]; then
      echo '{"error": "claude exited with non-zero status", "result": ""}' > "$output_file"
    fi
  fi
}

# ─── Run all scenarios for a skill ──────────────────────────────────────────

run_skill() {
  local scenario_file="$1"
  local skill
  skill=$(yq '.skill' "$scenario_file")
  local timestamp
  timestamp=$(date +%Y-%m-%d)
  local result_base="$OUTPUT_DIR/${timestamp}-${skill}"
  local scenario_count
  scenario_count=$(yq '.scenarios | length' "$scenario_file")

  echo "═══════════════════════════════════════════════════════════"
  echo "Evaluating skill: $skill"
  echo "Scenarios: $scenario_count | Runs per config: $RUNS | Model: $MODEL"
  echo "Results: $result_base/"
  echo "═══════════════════════════════════════════════════════════"

  local configs=("with-skill" "without-skill")
  if [[ -n "$CONFIG_ONLY" ]]; then
    configs=("$CONFIG_ONLY")
  fi

  for i in $(seq 0 $((scenario_count - 1))); do
    local scenario_id
    scenario_id=$(yq ".scenarios[$i].id" "$scenario_file")
    local prompt
    prompt=$(yq ".scenarios[$i].prompt" "$scenario_file")

    # Apply scenario filter if specified
    if [[ -n "$SCENARIO_FILTER" && "$scenario_id" != "$SCENARIO_FILTER" ]]; then
      continue
    fi

    echo ""
    echo "─── Scenario: $scenario_id ───"

    for config in "${configs[@]}"; do
      local run_dir="$result_base/$scenario_id/$config"
      mkdir -p "$run_dir"

      for run_num in $(seq 1 "$RUNS"); do
        run_single "$skill" "$scenario_id" "$prompt" "$config" "$run_num" "$run_dir"
      done
    done
  done

  echo ""
  echo "═══════════════════════════════════════════════════════════"
  echo "All runs complete. Scoring results..."
  echo "═══════════════════════════════════════════════════════════"
  echo ""

  # Run scorer
  "$SCRIPT_DIR/scorer.sh" "$result_base" "$scenario_file"
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
  check_dependencies
  load_defaults
  parse_args "$@"

  if [[ "$RUN_ALL" == true ]]; then
    while IFS= read -r scenario_file; do
      run_skill "$scenario_file"
    done < <(find_all_scenario_files)
  else
    local scenario_file
    scenario_file=$(find_scenario_files "$SKILL")
    run_skill "$scenario_file"
  fi
}

main "$@"

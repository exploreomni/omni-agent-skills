#!/usr/bin/env bash
#
# Generate an HTML eval report from a results directory.
#
# Usage:
#   ./evals/report.sh <results-dir> [--open]
#
# The results directory should contain:
#   scores.json           – benchmark scores (required)
#   with-skill/           – run output JSON files (optional)
#   without-skill/        – run output JSON files (optional)
#
# Outputs:
#   <results-dir>/report.html

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/report-template.html"

# ── Args ──────────────────────────────────────────────────
OPEN_BROWSER=false
RESULTS_DIR=""

for arg in "$@"; do
  case "$arg" in
    --open) OPEN_BROWSER=true ;;
    *)
      if [[ -z "$RESULTS_DIR" ]]; then
        RESULTS_DIR="$arg"
      else
        echo "Error: unexpected argument '$arg'" >&2
        echo "Usage: $0 <results-dir> [--open]" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$RESULTS_DIR" ]]; then
  echo "Usage: $0 <results-dir> [--open]" >&2
  exit 1
fi

if [[ ! -d "$RESULTS_DIR" ]]; then
  echo "Error: '$RESULTS_DIR' is not a directory" >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Error: template not found at '$TEMPLATE'" >&2
  exit 1
fi

SCORES_FILE="$RESULTS_DIR/scores.json"
if [[ ! -f "$SCORES_FILE" ]]; then
  echo "Error: scores.json not found in '$RESULTS_DIR'" >&2
  exit 1
fi

# ── Collect run outputs ──────────────────────────────────
# Build a JSON object: { "scenario": { "config": [ run1, run2, ... ] } }
collect_outputs() {
  local dir="$1"
  local result="{}"

  for config_dir in "$dir/with-skill" "$dir/without-skill"; do
    [[ -d "$config_dir" ]] || continue
    local config_name
    config_name="$(basename "$config_dir")"

    for scenario_dir in "$config_dir"/*/; do
      [[ -d "$scenario_dir" ]] || continue
      local scenario_name
      scenario_name="$(basename "$scenario_dir")"

      # Collect all JSON files in the scenario dir as runs
      local runs="[]"
      for run_file in "$scenario_dir"*.json; do
        [[ -f "$run_file" ]] || continue
        local run_content
        run_content="$(cat "$run_file")"
        runs="$(echo "$runs" | jq --argjson r "$run_content" '. + [$r]')"
      done

      result="$(echo "$result" | jq \
        --arg scn "$scenario_name" \
        --arg cfg "$config_name" \
        --argjson runs "$runs" \
        '.[$scn][$cfg] = $runs'
      )"
    done
  done

  echo "$result"
}

echo "Collecting data..."

# Check for jq
if ! command -v jq &>/dev/null; then
  echo "Warning: jq not found. Outputs tab will have no data." >&2
  OUTPUTS="{}"
else
  OUTPUTS="$(collect_outputs "$RESULTS_DIR")"
fi

# Build combined data object
SCORES_CONTENT="$(cat "$SCORES_FILE")"
if command -v jq &>/dev/null; then
  COMBINED="$(jq -n \
    --argjson scores "$SCORES_CONTENT" \
    --argjson outputs "$OUTPUTS" \
    '{ scores: $scores, outputs: $outputs }'
  )"
else
  # Fallback without jq: just use scores
  COMBINED="{\"scores\":$SCORES_CONTENT,\"outputs\":{}}"
fi

# ── Inject into template ─────────────────────────────────
OUTPUT_FILE="$RESULTS_DIR/report.html"

# Use awk to replace the empty script tag content
# The template has: <script id="eval-data" type="application/json"></script>
# We want:          <script id="eval-data" type="application/json">...DATA...</script>
awk -v data="$COMBINED" '
  /<script id="eval-data" type="application\/json">/ {
    print $0
    print data
    getline  # skip the closing </script> — we will print it
    print $0
    next
  }
  { print }
' "$TEMPLATE" > "$OUTPUT_FILE"

echo "Report generated: $OUTPUT_FILE"

# ── Open in browser ──────────────────────────────────────
if [[ "$OPEN_BROWSER" == true ]]; then
  ABS_PATH="$(cd "$(dirname "$OUTPUT_FILE")" && pwd)/$(basename "$OUTPUT_FILE")"
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$ABS_PATH"
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$ABS_PATH"
  else
    echo "Cannot detect browser opener. Open manually: $ABS_PATH"
  fi
fi

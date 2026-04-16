#!/usr/bin/env bash
set -euo pipefail

# ─── Skill Eval Scorer ───────────────────────────────────────────────────────
# Reads run JSON + scenario YAML, evaluates assertions, computes metrics.
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Usage ────────────────────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <results-dir> [scenario-file]"
  echo ""
  echo "  <results-dir>    Path to results directory (e.g. evals/results/2026-04-15-omni-model-explorer)"
  echo "  [scenario-file]  Path to scenario YAML (auto-detected from results dir if omitted)"
  exit 1
fi

RESULTS_DIR="$1"
SCENARIO_FILE="${2:-}"

if [[ ! -d "$RESULTS_DIR" ]]; then
  echo "Error: Results directory not found: $RESULTS_DIR"
  exit 1
fi

# Auto-detect scenario file from skill name in results dir
if [[ -z "$SCENARIO_FILE" ]]; then
  local_skill=$(basename "$RESULTS_DIR" | sed 's/^[0-9-]*-//')
  SCENARIO_FILE="$SCRIPT_DIR/scenarios/${local_skill}.eval.yaml"
  if [[ ! -f "$SCENARIO_FILE" ]]; then
    echo "Error: Could not auto-detect scenario file. Pass it as the second argument."
    exit 1
  fi
fi

SKILL=$(yq '.skill' "$SCENARIO_FILE")
MODEL=$(yq '.model // "unknown"' "$SCENARIO_FILE")

# ─── Assertion evaluators ───────────────────────────────────────────────────

# Extract output text from run JSON
extract_output() {
  local json_file="$1"
  jq -r '.result // ""' "$json_file" 2>/dev/null || echo ""
}

# Extract all tool calls (Bash commands) from run JSON
extract_tool_calls() {
  local json_file="$1"
  # Look for tool use in the messages array - Bash tool inputs
  jq -r '
    [.. | objects | select(.tool_name == "Bash" or .type == "tool_use") |
      (.input.command // .content // "")] |
    join("\n")
  ' "$json_file" 2>/dev/null || echo ""
}

# Extract metadata from run JSON
extract_cost() {
  local json_file="$1"
  jq -r '.cost_usd // 0' "$json_file" 2>/dev/null || echo "0"
}

extract_duration() {
  local json_file="$1"
  jq -r '.duration_ms // 0' "$json_file" 2>/dev/null || echo "0"
}

extract_num_turns() {
  local json_file="$1"
  jq -r '.num_turns // 0' "$json_file" 2>/dev/null || echo "0"
}

# Evaluate a single assertion against output and tool calls
eval_assertion() {
  local assertion_json="$1"
  local output="$2"
  local tool_calls="$3"
  local num_turns="$4"

  local atype
  atype=$(echo "$assertion_json" | jq -r '.type')

  case "$atype" in
    tool_called)
      local pattern
      pattern=$(echo "$assertion_json" | jq -r '.pattern')
      if echo "$tool_calls" | grep -qi "$pattern" 2>/dev/null; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    output_contains)
      local value
      value=$(echo "$assertion_json" | jq -r '.value')
      if echo "$output" | grep -qi "$value" 2>/dev/null; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    output_contains_all)
      local all_pass=true
      local count
      count=$(echo "$assertion_json" | jq '.values | length')
      for vi in $(seq 0 $((count - 1))); do
        local val
        val=$(echo "$assertion_json" | jq -r ".values[$vi]")
        if ! echo "$output" | grep -qi "$val" 2>/dev/null; then
          all_pass=false
          break
        fi
      done
      if $all_pass; then echo "PASS"; else echo "FAIL"; fi
      ;;

    output_contains_any)
      local any_pass=false
      local count
      count=$(echo "$assertion_json" | jq '.values | length')
      for vi in $(seq 0 $((count - 1))); do
        local val
        val=$(echo "$assertion_json" | jq -r ".values[$vi]")
        if echo "$output" | grep -qi "$val" 2>/dev/null; then
          any_pass=true
          break
        fi
      done
      if $any_pass; then echo "PASS"; else echo "FAIL"; fi
      ;;

    output_not_contains)
      local value
      value=$(echo "$assertion_json" | jq -r '.value')
      if echo "$output" | grep -qi "$value" 2>/dev/null; then
        echo "FAIL"
      else
        echo "PASS"
      fi
      ;;

    output_regex)
      local pattern
      pattern=$(echo "$assertion_json" | jq -r '.pattern')
      if echo "$output" | grep -iE "$pattern" 2>/dev/null; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    output_count_gte)
      local pattern min_count actual_count
      pattern=$(echo "$assertion_json" | jq -r '.pattern')
      min_count=$(echo "$assertion_json" | jq -r '.min_count')
      actual_count=$(echo "$output" | grep -oi "$pattern" 2>/dev/null | wc -l | tr -d ' ')
      if [[ "$actual_count" -ge "$min_count" ]]; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    llm_judge)
      local criteria
      criteria=$(echo "$assertion_json" | jq -r '.criteria')
      local truncated_output
      truncated_output=$(echo "$output" | head -c 8000)
      local judge_prompt="Score PASS or FAIL. Criteria: ${criteria}

Agent output:
${truncated_output}

Respond with exactly: PASS or FAIL"
      local verdict
      verdict=$(claude -p --model claude-haiku-4-5-20251001 --bare "$judge_prompt" 2>/dev/null || echo "FAIL")
      # Extract just PASS or FAIL from response
      if echo "$verdict" | grep -q "PASS"; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    step_count_lte)
      local max_steps
      max_steps=$(echo "$assertion_json" | jq -r '.max_steps')
      if [[ "$num_turns" -le "$max_steps" ]]; then
        echo "PASS"
      else
        echo "FAIL"
      fi
      ;;

    *)
      echo "UNKNOWN"
      ;;
  esac
}

# ─── Score all runs ──────────────────────────────────────────────────────────

# Build the scores JSON incrementally
SCORES_JSON=$(jq -n \
  --arg skill "$SKILL" \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg model "$MODEL" \
  '{skill: $skill, timestamp: $timestamp, model: $model, summary: {}, scenarios: {}}')

scenario_count=$(yq '.scenarios | length' "$SCENARIO_FILE")

# Accumulators for summary stats
declare -A config_pass_rates
declare -A config_tokens
declare -A config_times
config_pass_rates=()
config_tokens=()
config_times=()

for si in $(seq 0 $((scenario_count - 1))); do
  scenario_id=$(yq ".scenarios[$si].id" "$SCENARIO_FILE")
  assertion_count=$(yq ".scenarios[$si].assertions | length" "$SCENARIO_FILE")

  echo "─── Scoring: $scenario_id ($assertion_count assertions) ───"

  for config in with-skill without-skill; do
    config_key="${config//-/_}"
    run_dir="$RESULTS_DIR/$scenario_id/$config"

    if [[ ! -d "$run_dir" ]]; then
      echo "  Skipping $config (no results directory)"
      continue
    fi

    run_results="[]"
    assertion_pass_counts=()
    # Initialize assertion pass counts
    for ai in $(seq 0 $((assertion_count - 1))); do
      assertion_pass_counts[$ai]=0
    done

    total_runs=0
    total_passed=0
    total_assertions=0
    sum_tokens=0
    sum_time=0

    for run_file in "$run_dir"/run-*.json; do
      [[ -f "$run_file" ]] || continue
      total_runs=$((total_runs + 1))
      run_num=$(basename "$run_file" | sed 's/run-//;s/.json//')

      output=$(extract_output "$run_file")
      tool_calls=$(extract_tool_calls "$run_file")
      cost=$(extract_cost "$run_file")
      duration_ms=$(extract_duration "$run_file")
      num_turns=$(extract_num_turns "$run_file")
      duration_s=$(echo "scale=1; $duration_ms / 1000" | bc 2>/dev/null || echo "0")

      # Extract token counts from JSON
      tokens=$(jq '.total_tokens // .usage.total_tokens // 0' "$run_file" 2>/dev/null || echo "0")
      sum_tokens=$((sum_tokens + tokens))
      sum_time=$(echo "$sum_time + $duration_s" | bc 2>/dev/null || echo "$sum_time")

      run_passed=0
      run_total=0
      run_assertion_results="{}"

      for ai in $(seq 0 $((assertion_count - 1))); do
        assertion_json=$(yq -o=json ".scenarios[$si].assertions[$ai]" "$SCENARIO_FILE")
        assertion_desc=$(echo "$assertion_json" | jq -r '.description // .type')
        verdict=$(eval_assertion "$assertion_json" "$output" "$tool_calls" "$num_turns")

        run_total=$((run_total + 1))
        if [[ "$verdict" == "PASS" ]]; then
          run_passed=$((run_passed + 1))
          assertion_pass_counts[$ai]=$((${assertion_pass_counts[$ai]} + 1))
        fi

        run_assertion_results=$(echo "$run_assertion_results" | jq \
          --arg desc "$assertion_desc" \
          --arg verdict "$verdict" \
          '. + {($desc): $verdict}')
      done

      total_passed=$((total_passed + run_passed))
      total_assertions=$((total_assertions + run_total))

      local_pass_rate=0
      if [[ $run_total -gt 0 ]]; then
        local_pass_rate=$(echo "scale=4; $run_passed / $run_total" | bc)
      fi

      run_entry=$(jq -n \
        --arg run "$run_num" \
        --argjson pass_rate "$local_pass_rate" \
        --argjson passed "$run_passed" \
        --argjson total "$run_total" \
        --argjson cost "$cost" \
        --argjson duration_s "$duration_s" \
        --argjson num_turns "$num_turns" \
        --argjson tokens "$tokens" \
        --argjson assertions "$run_assertion_results" \
        '{run: $run, pass_rate: $pass_rate, passed: $passed, total: $total, cost_usd: $cost, duration_seconds: $duration_s, num_turns: $num_turns, tokens: $tokens, assertions: $assertions}')

      run_results=$(echo "$run_results" | jq --argjson entry "$run_entry" '. + [$entry]')
    done

    # Compute per-scenario pass rate for this config
    scenario_pass_rate=0
    if [[ $total_assertions -gt 0 ]]; then
      scenario_pass_rate=$(echo "scale=4; $total_passed / $total_assertions" | bc)
    fi

    mean_tokens=0
    mean_time=0
    if [[ $total_runs -gt 0 ]]; then
      mean_tokens=$((sum_tokens / total_runs))
      mean_time=$(echo "scale=1; $sum_time / $total_runs" | bc 2>/dev/null || echo "0")
    fi

    # Build per-assertion pass rates
    assertion_summary="{}"
    for ai in $(seq 0 $((assertion_count - 1))); do
      assertion_desc=$(yq -o=json ".scenarios[$si].assertions[$ai]" "$SCENARIO_FILE" | jq -r '.description // .type')
      arate=0
      if [[ $total_runs -gt 0 ]]; then
        arate=$(echo "scale=4; ${assertion_pass_counts[$ai]} / $total_runs" | bc)
      fi
      assertion_summary=$(echo "$assertion_summary" | jq \
        --arg desc "$assertion_desc" \
        --argjson rate "$arate" \
        '. + {($desc): {pass_rate: $rate}}')
    done

    # Add scenario config to SCORES_JSON
    SCORES_JSON=$(echo "$SCORES_JSON" | jq \
      --arg sid "$scenario_id" \
      --arg ck "$config_key" \
      --argjson pass_rate "$scenario_pass_rate" \
      --argjson runs "$run_results" \
      --argjson assertions "$assertion_summary" \
      '.scenarios[$sid][$ck] = {pass_rate: $pass_rate, runs: $runs, assertions: $assertions}')

    # Accumulate for summary
    config_pass_rates["$config_key"]="${config_pass_rates["$config_key"]:-} $scenario_pass_rate"
    config_tokens["$config_key"]="${config_tokens["$config_key"]:-} $mean_tokens"
    config_times["$config_key"]="${config_times["$config_key"]:-} $mean_time"

    echo "  $config: pass_rate=$scenario_pass_rate ($total_passed/$total_assertions) | tokens=$mean_tokens | time=${mean_time}s"
  done
done

# ─── Compute summary ────────────────────────────────────────────────────────

compute_mean_std() {
  local values="$1"
  local n=0 sum=0 sumsq=0
  for v in $values; do
    sum=$(echo "$sum + $v" | bc)
    sumsq=$(echo "$sumsq + $v * $v" | bc)
    n=$((n + 1))
  done
  if [[ $n -eq 0 ]]; then
    echo "0 0"
    return
  fi
  local mean
  mean=$(echo "scale=4; $sum / $n" | bc)
  local variance
  variance=$(echo "scale=4; $sumsq / $n - $mean * $mean" | bc)
  # Handle negative variance from floating point
  local std
  std=$(echo "scale=4; if ($variance < 0) 0 else sqrt($variance)" | bc 2>/dev/null || echo "0")
  echo "$mean $std"
}

compute_mean() {
  local values="$1"
  local n=0 sum=0
  for v in $values; do
    sum=$(echo "$sum + $v" | bc)
    n=$((n + 1))
  done
  if [[ $n -eq 0 ]]; then echo "0"; return; fi
  echo "scale=1; $sum / $n" | bc
}

for config_key in with_skill without_skill; do
  if [[ -z "${config_pass_rates[$config_key]:-}" ]]; then continue; fi

  read -r pr_mean pr_std <<< "$(compute_mean_std "${config_pass_rates[$config_key]}")"
  mt=$(compute_mean "${config_tokens[$config_key]}")
  mtime=$(compute_mean "${config_times[$config_key]}")

  SCORES_JSON=$(echo "$SCORES_JSON" | jq \
    --arg ck "$config_key" \
    --argjson pr_mean "$pr_mean" \
    --argjson pr_std "$pr_std" \
    --argjson mt "$mt" \
    --argjson mtime "$mtime" \
    '.summary[$ck] = {pass_rate: {mean: $pr_mean, std: $pr_std}, mean_tokens: $mt, mean_time_seconds: $mtime}')
done

# Compute deltas
ws_pr=$(echo "$SCORES_JSON" | jq '.summary.with_skill.pass_rate.mean // 0')
wos_pr=$(echo "$SCORES_JSON" | jq '.summary.without_skill.pass_rate.mean // 0')
ws_tok=$(echo "$SCORES_JSON" | jq '.summary.with_skill.mean_tokens // 0')
wos_tok=$(echo "$SCORES_JSON" | jq '.summary.without_skill.mean_tokens // 0')
ws_time=$(echo "$SCORES_JSON" | jq '.summary.with_skill.mean_time_seconds // 0')
wos_time=$(echo "$SCORES_JSON" | jq '.summary.without_skill.mean_time_seconds // 0')

delta_pr=$(echo "scale=4; $ws_pr - $wos_pr" | bc)
delta_tok=$(echo "scale=0; $ws_tok - $wos_tok" | bc)
delta_time=$(echo "scale=1; $ws_time - $wos_time" | bc)

SCORES_JSON=$(echo "$SCORES_JSON" | jq \
  --argjson dpr "$delta_pr" \
  --argjson dtok "$delta_tok" \
  --argjson dtime "$delta_time" \
  '.summary.delta = {pass_rate: $dpr, tokens: $dtok, time_seconds: $dtime}')

# ─── Write scores.json ──────────────────────────────────────────────────────

SCORES_FILE="$RESULTS_DIR/scores.json"
echo "$SCORES_JSON" | jq '.' > "$SCORES_FILE"
echo ""
echo "Scores written to: $SCORES_FILE"

# ─── Print summary table ────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     EVAL SUMMARY                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║ %-20s │ %15s │ %15s ║\n" "Metric" "With Skill" "Without Skill"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║ %-20s │ %15s │ %15s ║\n" "Pass Rate" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.with_skill.pass_rate | "\(.mean) ± \(.std)"')" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.without_skill.pass_rate | "\(.mean) ± \(.std)"')"
printf "║ %-20s │ %15s │ %15s ║\n" "Mean Tokens" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.with_skill.mean_tokens')" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.without_skill.mean_tokens')"
printf "║ %-20s │ %15s │ %15s ║\n" "Mean Time (s)" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.with_skill.mean_time_seconds')" \
  "$(echo "$SCORES_JSON" | jq -r '.summary.without_skill.mean_time_seconds')"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║ %-20s │ %33s ║\n" "Delta Pass Rate" "$delta_pr"
printf "║ %-20s │ %33s ║\n" "Delta Tokens" "$delta_tok"
printf "║ %-20s │ %33s ║\n" "Delta Time (s)" "$delta_time"
echo "╚══════════════════════════════════════════════════════════════╝"

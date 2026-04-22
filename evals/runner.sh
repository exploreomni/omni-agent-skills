#!/usr/bin/env bash
# evals/runner.sh — Run eval cases for one or all Omni skills
#
# For each eval case in skills/<skill>/evals/evals.json, runs two isolated
# agent sessions via run_agent.py: one with the skill's SKILL.md as the system
# prompt (with_skill) and one without (without_skill). Supports any
# LiteLLM-compatible provider (Anthropic, OpenAI, Gemini, Bedrock, ...).
#
# Usage:
#   ./evals/runner.sh <skill|all> [--provider PROVIDER] [--model MODEL] [--iteration N]
#
# Output:
#   evals/workspaces/<skill>/iteration-N-<model-slug>/
#     eval-<id>/
#       with_skill/    outputs/  raw_output.json  timing.json
#       without_skill/ outputs/  raw_output.json  timing.json
#
# API keys are read from env by LiteLLM:
#   Anthropic  → ANTHROPIC_API_KEY
#   OpenAI     → OPENAI_API_KEY
#   Gemini     → GEMINI_API_KEY

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACES_DIR="$SCRIPT_DIR/workspaces"

PROVIDER="${EVAL_PROVIDER:-anthropic}"
MODEL="${EVAL_MODEL:-claude-sonnet-4-6}"
REASONING_EFFORT="${EVAL_REASONING_EFFORT:-}"
FORCE_ITERATION=""

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
Usage: $(basename "$0") <skill|all> [--provider PROVIDER] [--model MODEL] [--iteration N]

Options:
  --provider PROVIDER          LiteLLM provider (default: anthropic, or \$EVAL_PROVIDER)
                               e.g. anthropic, openai, gemini, bedrock
  --model MODEL                Model name for the provider (default: claude-sonnet-4-6, or \$EVAL_MODEL)
                               e.g. claude-sonnet-4-6, gpt-4o, gemini-2.0-flash
  --reasoning-effort EFFORT    OpenAI reasoning effort: low, medium, high, xhigh (or \$EVAL_REASONING_EFFORT)
  --iteration N                Force a specific iteration number (default: auto-increment)

Examples:
  ./evals/runner.sh omni-query
  ./evals/runner.sh omni-query --provider openai --model gpt-4o
  ./evals/runner.sh all --provider anthropic --model claude-haiku-4-5-20251001
  ./evals/runner.sh omni-admin --iteration 2
EOF
  exit 1
}

check_deps() {
  local missing=()
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  command -v jq      >/dev/null 2>&1 || missing+=(jq)
  if (( ${#missing[@]} > 0 )); then
    echo "ERROR: Missing required tools: ${missing[*]}" >&2
    exit 1
  fi
  if ! python3 -c "import litellm" 2>/dev/null; then
    echo "ERROR: litellm not installed. Run: pip install litellm" >&2
    exit 1
  fi
}

model_slug() {
  # Produce a short filesystem-safe token from the model name.
  # claude-sonnet-4-6        -> sonnet-4-6
  # claude-haiku-4-5-20251001 -> haiku-4-5
  # gpt-4o                   -> gpt-4o
  # gemini-2.0-flash         -> gemini-2-0-flash
  echo "$1" \
    | sed 's/^claude-//' \
    | sed 's/-[0-9]\{8\}$//' \
    | tr '.' '-' \
    | tr '[:upper:]' '[:lower:]'
}

next_iteration() {
  local dir="$WORKSPACES_DIR/$1"
  [[ -n "$FORCE_ITERATION" ]] && echo "$FORCE_ITERATION" && return
  [[ ! -d "$dir" ]] && echo 1 && return
  local max=0
  for d in "$dir"/iteration-*/; do
    [[ -d "$d" ]] || continue
    local n="${d%/}"; n="${n##*iteration-}"; n="${n%%-*}"
    [[ "$n" =~ ^[0-9]+$ ]] && (( n > max )) && max=$n
  done
  echo $(( max + 1 ))
}

# ── Omni env injection ───────────────────────────────────────────────────────
# Export OMNI_BASE_URL and OMNI_API_TOKEN from the active omni-cli profile so
# that agents can authenticate even if they check env vars instead of the
# config file (common with non-Claude models).

inject_omni_env() {
  local config="$HOME/.config/omni-cli/config.json"
  [[ -f "$config" ]] || return 0

  local profile
  profile=$(jq -r '.defaultProfile // ""' "$config")
  [[ -z "$profile" ]] && return 0

  local endpoint api_key
  endpoint=$(jq -r --arg p "$profile" '.profiles[$p].apiEndpoint // ""' "$config")
  api_key=$(jq -r --arg p "$profile" '.profiles[$p].apiKey // ""' "$config")

  [[ -n "$endpoint" ]] && export OMNI_BASE_URL="$endpoint"
  [[ -n "$api_key"  ]] && export OMNI_API_TOKEN="$api_key"
}

inject_omni_env

# ── Core run ─────────────────────────────────────────────────────────────────

run_agent() {
  local prompt="$1" skill_md="$2" out_dir="$3"

  local args=(
    --provider "$PROVIDER"
    --model    "$MODEL"
    --prompt   "$prompt"
  )

  if [[ -n "$skill_md" ]]; then
    args+=(--system-prompt-file "$skill_md")
  fi

  if [[ -n "$REASONING_EFFORT" ]]; then
    args+=(--reasoning-effort "$REASONING_EFFORT")
  fi

  args+=(--working-dir "$out_dir/outputs")

  local exit_code=0
  python3 "$SCRIPT_DIR/run_agent.py" "${args[@]}" \
    > "$out_dir/raw_output.json" 2>"$out_dir/stderr.log" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    echo "    WARNING: run_agent.py exited $exit_code (see stderr.log)" >&2
  fi
}

run_eval_case() {
  local skill="$1" eval_id="$2" eval_prompt="$3" files_json="$4"
  local iter_dir="$5" skill_md="$6"

  local eval_dir="$iter_dir/eval-$eval_id"
  mkdir -p "$eval_dir/with_skill/outputs" "$eval_dir/without_skill/outputs"

  # Copy any declared input files into both run directories
  local n_files
  n_files=$(echo "$files_json" | jq 'length')
  if (( n_files > 0 )); then
    while IFS= read -r f; do
      local src="$ROOT_DIR/skills/$skill/$f"
      if [[ -f "$src" ]]; then
        cp "$src" "$eval_dir/with_skill/outputs/"
        cp "$src" "$eval_dir/without_skill/outputs/"
      else
        echo "    WARNING: input file not found: $src" >&2
      fi
    done < <(echo "$files_json" | jq -r '.[]')
  fi

  # Task prompt — includes outputs dir and asks agent to list commands run,
  # which makes tool-call assertions reliably gradeable from the text output.
  local base_task
  base_task="$(cat <<TASK
Execute this task using the available tools.

Task: ${eval_prompt}

After completing the task, write a brief summary that lists:
1. The exact CLI commands you ran (copy-paste each command line)
2. The key result or output of each command

Save any output files to: OUTPUTS_DIR
TASK
)"

  for config in with_skill without_skill; do
    local run_dir="$eval_dir/$config"
    local task="${base_task/OUTPUTS_DIR/$run_dir/outputs/}"
    local active_skill_md=""
    if [[ "$config" == "with_skill" ]]; then
      active_skill_md="$skill_md"
    else
      active_skill_md="$SCRIPT_DIR/cli-baseline.md"
    fi

    printf "    [%-13s] running..." "$config"

    local t0 t1
    t0=$(python3 -c "import time; print(int(time.time() * 1000))")
    run_agent "$task" "$active_skill_md" "$run_dir"
    t1=$(python3 -c "import time; print(int(time.time() * 1000))")

    local duration_ms=$(( t1 - t0 ))

    # Extract total tokens from the JSON result envelope
    local tokens
    tokens=$(jq -r '((.usage.input_tokens // 0) + (.usage.output_tokens // 0))' \
      "$run_dir/raw_output.json" 2>/dev/null || echo 0)

    jq -n \
      --argjson tokens "$tokens" \
      --argjson duration "$duration_ms" \
      '{"total_tokens": $tokens, "duration_ms": $duration}' \
      > "$run_dir/timing.json"

    printf " %6d tokens  %5dms\n" "$tokens" "$duration_ms"
  done
}

# ── Skill runner ──────────────────────────────────────────────────────────────

run_skill() {
  local skill="$1"
  local evals_file="$ROOT_DIR/skills/$skill/evals/evals.json"
  local skill_md="$ROOT_DIR/skills/$skill/SKILL.md"

  if [[ ! -f "$evals_file" ]]; then
    echo "ERROR: No evals/evals.json for skill '$skill'" >&2; return 1
  fi
  if [[ ! -f "$skill_md" ]]; then
    echo "ERROR: No SKILL.md for skill '$skill'" >&2; return 1
  fi

  local iter iter_dir slug
  iter=$(next_iteration "$skill")
  slug=$(model_slug "$MODEL")
  iter_dir="$WORKSPACES_DIR/$skill/iteration-${iter}-${slug}"
  mkdir -p "$iter_dir"

  # Write metadata so scorer can record model in published results
  jq -n \
    --arg provider "$PROVIDER" \
    --arg model "$MODEL" \
    --arg slug "$slug" \
    --arg skill "$skill" \
    --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg reasoning_effort "$REASONING_EFFORT" \
    --argjson iter "$iter" \
    '{provider: $provider, model: $model, model_slug: $slug, skill: $skill, iteration: $iter,
      run_date: $date, reasoning_effort: (if $reasoning_effort == "" then null else $reasoning_effort end)}' \
    > "$iter_dir/meta.json"

  local n_evals
  n_evals=$(jq '.evals | length' "$evals_file")

  echo ""
  echo "┌── $skill  (iteration $iter · $n_evals evals · $MODEL)"

  for i in $(seq 0 $(( n_evals - 1 ))); do
    local eval_id eval_prompt files_json
    eval_id=$(jq -r ".evals[$i].id" "$evals_file")
    eval_prompt=$(substitute_vars "$(jq -r ".evals[$i].prompt" "$evals_file")")
    files_json=$(jq -c ".evals[$i].files // []" "$evals_file")

    local preview="${eval_prompt:0:68}"
    [[ ${#eval_prompt} -gt 68 ]] && preview+="..."
    echo "│"
    echo "│  eval $eval_id: $preview"

    run_eval_case "$skill" "$eval_id" "$eval_prompt" "$files_json" "$iter_dir" "$skill_md"
  done

  echo "│"
  echo "└── done → $iter_dir"
}

# ── Entry point ───────────────────────────────────────────────────────────────

check_deps

SKILL="${1:-}"
[[ -z "$SKILL" ]] && usage
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)          PROVIDER="$2"; shift 2 ;;
    --model)             MODEL="$2"; shift 2 ;;
    --reasoning-effort)  REASONING_EFFORT="$2"; shift 2 ;;
    --iteration)         FORCE_ITERATION="$2"; shift 2 ;;
    -h|--help)   usage ;;
    *)           echo "Unknown flag: $1" >&2; usage ;;
  esac
done

if [[ "$SKILL" == "all" ]]; then
  while IFS= read -r skill_dir; do
    s=$(basename "$skill_dir")
    [[ -f "$ROOT_DIR/skills/$s/evals/evals.json" ]] && run_skill "$s"
  done < <(find "$ROOT_DIR/skills" -mindepth 1 -maxdepth 1 -type d | sort)
else
  run_skill "$SKILL"
fi

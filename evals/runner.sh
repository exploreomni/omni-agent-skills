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
REPEAT="${EVAL_REPEAT:-1}"

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
  --repeat N                   Run each eval N times for per-eval variance (default: 1, or \$EVAL_REPEAT)

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

# ── Provenance ───────────────────────────────────────────────────────────────
# Captures the inputs that determine eval reproducibility: which code, which
# skill prompt, which baseline, which eval set. Embedded into meta.json so
# every result can be traced back to an exact repo state.

sha256_file() {
  [[ -f "$1" ]] || { echo ""; return; }
  python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1" 2>/dev/null || echo ""
}

sha256_dir() {
  # Deterministic hash of every file under a directory (sorted by relative path).
  # Empty string if dir doesn't exist or contains no files.
  local dir="$1"
  [[ -d "$dir" ]] || { echo ""; return; }
  python3 - "$dir" <<'PYEOF' 2>/dev/null || echo ""
import hashlib, os, sys
root = sys.argv[1]
h = hashlib.sha256()
files = []
for dirpath, _, filenames in os.walk(root):
    for f in filenames:
        files.append(os.path.relpath(os.path.join(dirpath, f), root))
if not files:
    print(""); sys.exit(0)
for rel in sorted(files):
    h.update(rel.encode())
    h.update(b"\0")
    h.update(open(os.path.join(root, rel), "rb").read())
print(h.hexdigest())
PYEOF
}

provenance_block() {
  local skill_md="$1" evals_file="$2"
  local git_commit git_branch git_dirty plugin_version

  git_commit=$(git -C "$ROOT_DIR"  rev-parse HEAD 2>/dev/null  || echo "unknown")
  git_branch=$(git -C "$ROOT_DIR"  rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  if git -C "$ROOT_DIR" diff --quiet 2>/dev/null && git -C "$ROOT_DIR" diff --cached --quiet 2>/dev/null; then
    git_dirty=false
  else
    git_dirty=true
  fi

  if [[ -f "$ROOT_DIR/.claude-plugin/plugin.json" ]]; then
    plugin_version=$(jq -r '.version // "unknown"' "$ROOT_DIR/.claude-plugin/plugin.json")
  else
    plugin_version="unknown"
  fi

  local skill_dir
  skill_dir=$(dirname "$skill_md")

  jq -n \
    --arg     commit          "$git_commit" \
    --arg     branch          "$git_branch" \
    --argjson dirty           "$git_dirty" \
    --arg     plugin          "$plugin_version" \
    --arg     skill_sha       "$(sha256_file "$skill_md")" \
    --arg     evals_sha       "$(sha256_file "$evals_file")" \
    --arg     baseline_sha    "$(sha256_file "$SCRIPT_DIR/cli-baseline.md")" \
    --arg     refs_sha        "$(sha256_dir "$skill_dir/references")" \
    '{git: {commit: $commit, branch: $branch, dirty: $dirty},
      plugin_version:      $plugin,
      skill_md_sha256:     $skill_sha,
      evals_json_sha256:   $evals_sha,
      cli_baseline_sha256: $baseline_sha,
      references_sha256:   $refs_sha}'
}

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
  args+=(--transcript-file "$out_dir/transcript.json")

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
  mkdir -p "$eval_dir"

  local n_files
  n_files=$(echo "$files_json" | jq 'length')

  copy_input_files() {
    # Copy any declared input files into a given outputs/ directory.
    local target_outputs="$1"
    if (( n_files > 0 )); then
      while IFS= read -r f; do
        local src="$ROOT_DIR/skills/$skill/$f"
        if [[ -f "$src" ]]; then
          cp "$src" "$target_outputs/"
        else
          echo "    WARNING: input file not found: $src" >&2
        fi
      done < <(echo "$files_json" | jq -r '.[]')
    fi
  }

  copy_references() {
    # Copy the skill's references/ dir into the agent's cwd so SKILL.md's
    # relative paths like `references/foo.md` resolve. Called for with_skill
    # runs only — without_skill is meant to be a clean baseline.
    local target_outputs="$1"
    local refs="$ROOT_DIR/skills/$skill/references"
    if [[ -d "$refs" ]]; then
      cp -R "$refs" "$target_outputs/"
    fi
  }

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
    local config_dir="$eval_dir/$config"
    local active_skill_md=""
    if [[ "$config" == "with_skill" ]]; then
      active_skill_md="$skill_md"
    else
      active_skill_md="$SCRIPT_DIR/cli-baseline.md"
    fi

    for k in $(seq 1 "$REPEAT"); do
      # Flat layout when REPEAT=1 (backwards compatible); nested run-K dirs otherwise.
      local run_dir
      if (( REPEAT == 1 )); then
        run_dir="$config_dir"
      else
        run_dir="$config_dir/run-$k"
      fi
      mkdir -p "$run_dir/outputs"
      copy_input_files "$run_dir/outputs"
      if [[ "$config" == "with_skill" ]]; then
        copy_references "$run_dir/outputs"
      fi

      local task="${base_task/OUTPUTS_DIR/$run_dir/outputs/}"

      if (( REPEAT == 1 )); then
        printf "    [%-13s] running..." "$config"
      else
        printf "    [%-13s run %d/%d] running..." "$config" "$k" "$REPEAT"
      fi

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
    --arg     provider         "$PROVIDER" \
    --arg     model            "$MODEL" \
    --arg     slug             "$slug" \
    --arg     skill            "$skill" \
    --arg     date             "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg     reasoning_effort "$REASONING_EFFORT" \
    --argjson iter             "$iter" \
    --argjson repeat           "$REPEAT" \
    --argjson provenance       "$(provenance_block "$skill_md" "$evals_file")" \
    '{provider: $provider, model: $model, model_slug: $slug, skill: $skill, iteration: $iter,
      repeat: $repeat,
      run_date: $date,
      reasoning_effort: (if $reasoning_effort == "" then null else $reasoning_effort end),
      provenance: $provenance}' \
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
    --repeat)            REPEAT="$2"; shift 2 ;;
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

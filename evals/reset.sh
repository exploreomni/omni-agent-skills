#!/usr/bin/env bash
# evals/reset.sh — Reset mutable Omni instance state between eval runs.
#
# Cleans up artifacts left by evals so re-runs start from a known state. Reads
# instance identifiers from eval-env.local.json (falls back to eval-env.json).
#
# Resets handled:
#   - omni-admin eval 1: deletes the `newanalyst@company.com` test user
#   - omni-content-explorer eval 3: removes `finance` label from EVAL_DASHBOARD_LABEL
#   - omni-model-builder / omni-ai-optimizer: deletes non-baseline model branches
#     on EVAL_MODEL_ID (branches with names starting with "eval-" are protected
#     by convention — adjust below if you use a different naming pattern).
#
# Not handled (still requires manual cleanup or admin UI):
#   - omni-admin eval 3: schedules created on EVAL_DASHBOARD_SCHEDULE
#     (no CLI delete; remove via admin UI)
#
# Usage:
#   ./evals/reset.sh           # reset everything
#   ./evals/reset.sh --dry-run # show what would be reset, no changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 1 ;;
  esac
done

# ── Config loading ────────────────────────────────────────────────────────────

CONFIG="$SCRIPT_DIR/eval-env.local.json"
[[ -f "$CONFIG" ]] || CONFIG="$SCRIPT_DIR/eval-env.json"
[[ -f "$CONFIG" ]] || { echo "ERROR: no eval-env config found" >&2; exit 1; }

get() { jq -r --arg k "$1" '.[$k] // ""' "$CONFIG"; }

MODEL_ID=$(get EVAL_MODEL_ID)
DASHBOARD_LABEL=$(get EVAL_DASHBOARD_LABEL)
TEST_USER="newanalyst@company.com"

# ── Helpers ───────────────────────────────────────────────────────────────────

run() {
  # Print and (unless dry-run) execute. Failure is non-fatal — reset is best-effort.
  echo "  $*"
  if ! $DRY_RUN; then
    eval "$@" 2>&1 | sed 's/^/    /' || true
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 is required" >&2; exit 1; }
}

# ── Pre-flight ────────────────────────────────────────────────────────────────

require_cmd omni
require_cmd jq

echo ""
echo "Reset target: $CONFIG"
$DRY_RUN && echo "Mode: DRY RUN (no changes will be made)"
echo ""

# ── 1. Delete test user ───────────────────────────────────────────────────────

echo "1. Deleting test user: $TEST_USER"
USER_ID=$(omni users list 2>/dev/null \
  | jq -r --arg e "$TEST_USER" '.records[]? | select(.email==$e) | .id' \
  | head -1)

if [[ -n "$USER_ID" ]]; then
  run "omni users delete $USER_ID"
else
  echo "  (not present — skipping)"
fi
echo ""

# ── 2. Remove eval label from EVAL_DASHBOARD_LABEL ────────────────────────────

echo "2. Removing 'finance' label from EVAL_DASHBOARD_LABEL"
if [[ -n "$DASHBOARD_LABEL" && "$DASHBOARD_LABEL" != "replace-with-dashboard-identifier" ]]; then
  run "omni documents remove-label $DASHBOARD_LABEL finance"
else
  echo "  (EVAL_DASHBOARD_LABEL not configured — skipping)"
fi
echo ""

# ── 3. Delete non-baseline model branches ─────────────────────────────────────

echo "3. Deleting model branches on EVAL_MODEL_ID (excluding 'eval-comparison-branch')"
if [[ -n "$MODEL_ID" && "$MODEL_ID" != "replace-with-shared-model-id" ]]; then
  BRANCH_IDS=$(omni models list --include activeBranches 2>/dev/null \
    | jq -r --arg m "$MODEL_ID" '
        .records[]?
        | select(.id==$m)
        | .activeBranches[]?
        | select(.name | startswith("eval-comparison-branch") | not)
        | .id
      ')

  if [[ -z "$BRANCH_IDS" ]]; then
    echo "  (no non-baseline branches present — skipping)"
  else
    while IFS= read -r bid; do
      [[ -n "$bid" ]] || continue
      run "omni models delete-branch $MODEL_ID --body '{\"branchId\":\"$bid\"}'"
    done <<< "$BRANCH_IDS"
  fi
else
  echo "  (EVAL_MODEL_ID not configured — skipping)"
fi
echo ""

echo "Reset complete."
$DRY_RUN && echo "(Dry-run — no changes made)"

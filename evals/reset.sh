#!/usr/bin/env bash
# evals/reset.sh — Reset mutable Omni instance state between eval runs.
#
# Cleans up artifacts left by evals so re-runs start from a known state. Reads
# instance identifiers from eval-env.local.json (falls back to eval-env.json).
#
# Resets handled:
#   - omni-admin eval 1: deletes the `newanalyst@company.com` test user
#   - omni-content-builder eval 2: recreates the Sales Performance dashboard
#     and updates EVAL_DASHBOARD_TILES in eval-env.local.json
#   - omni-content-explorer eval 3: removes `finance` label from EVAL_DASHBOARD_LABEL
#   - omni-model-builder eval 2: deletes `public/customer_segments.view`
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

LOCAL_CONFIG="$SCRIPT_DIR/eval-env.local.json"
TEMPLATE_CONFIG="$SCRIPT_DIR/eval-env.json"
CONFIG="$LOCAL_CONFIG"
[[ -f "$CONFIG" ]] || CONFIG="$TEMPLATE_CONFIG"
[[ -f "$CONFIG" ]] || { echo "ERROR: no eval-env config found" >&2; exit 1; }

get() { jq -r --arg k "$1" '.[$k] // ""' "$CONFIG"; }

MODEL_ID=$(get EVAL_MODEL_ID)
DASHBOARD_LABEL=$(get EVAL_DASHBOARD_LABEL)
DASHBOARD_TILES=$(get EVAL_DASHBOARD_TILES)
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

# ── 1. Delete test user (via SCIM) ────────────────────────────────────────────

echo "1. Deleting test user: $TEST_USER"
USER_ID=$(omni scim users-list -o json 2>/dev/null \
  | jq -r --arg e "$TEST_USER" '.Resources[]? | select(.emails[]?.value == $e) | .id' \
  | head -1)

if [[ -n "$USER_ID" ]]; then
  run "omni scim users-delete $USER_ID"
else
  echo "  (not present — skipping)"
fi
echo ""

# ── 2. Recreate Sales Performance dashboard ──────────────────────────────────

echo "2. Recreating Sales Performance dashboard for EVAL_DASHBOARD_TILES"
if [[ "$CONFIG" != "$LOCAL_CONFIG" ]]; then
  echo "  (eval-env.local.json is missing — cannot update local dashboard identifier)"
elif [[ -z "$MODEL_ID" || "$MODEL_ID" == "replace-with-shared-model-id" ]]; then
  echo "  (EVAL_MODEL_ID not configured — skipping)"
else
  if $DRY_RUN; then
    echo "  omni documents create --body <Sales Performance fixture>"
    echo "  jq update EVAL_DASHBOARD_TILES in $CONFIG"
    if [[ -n "$DASHBOARD_TILES" && "$DASHBOARD_TILES" != "replace-with-dashboard-identifier" ]]; then
      echo "  omni documents delete $DASHBOARD_TILES"
    fi
  else
    SALES_BODY=$(jq -n --arg m "$MODEL_ID" '{
      modelId: $m,
      name: "Sales Performance",
      queryPresentations: [
        {
          name: "Revenue by Month",
          topicName: "order_items",
          prefersChart: true,
          visType: "basic",
          fields: ["order_items.created_at[month]", "order_items.total_revenue"],
          query: {
            table: "order_items",
            join_paths_from_topic_name: "order_items",
            fields: ["order_items.created_at[month]", "order_items.total_revenue"],
            sorts: [{column_name: "order_items.created_at[month]", sort_descending: false}],
            limit: 24,
            visConfig: {chartType: "area"}
          },
          config: {}
        }
      ]
    }')
    if CREATE_OUTPUT=$(omni documents create --body "$SALES_BODY" -o json 2>&1); then
      if ! NEW_DASHBOARD_TILES=$(jq -r '.workbook.identifier // .identifier // ""' <<< "$CREATE_OUTPUT" 2>/dev/null); then
        echo "  (created document but Omni returned non-JSON output — skipping config update)"
        echo "$CREATE_OUTPUT" | sed 's/^/    /'
      elif [[ -z "$NEW_DASHBOARD_TILES" || "$NEW_DASHBOARD_TILES" == "null" ]]; then
        echo "  (created document but could not parse identifier — skipping config update)"
        echo "$CREATE_OUTPUT" | sed 's/^/    /'
      else
        TMP_CONFIG=$(mktemp "${CONFIG}.tmp.XXXXXX")
        jq --arg id "$NEW_DASHBOARD_TILES" '.EVAL_DASHBOARD_TILES = $id' "$CONFIG" > "$TMP_CONFIG"
        mv "$TMP_CONFIG" "$CONFIG"
        echo "  updated EVAL_DASHBOARD_TILES: $NEW_DASHBOARD_TILES"
        if [[ -n "$DASHBOARD_TILES" && "$DASHBOARD_TILES" != "replace-with-dashboard-identifier" && "$DASHBOARD_TILES" != "$NEW_DASHBOARD_TILES" ]]; then
          run "omni documents delete $DASHBOARD_TILES"
        fi
      fi
    else
      echo "  (failed to create Sales Performance dashboard — skipping)"
      echo "$CREATE_OUTPUT" | sed 's/^/    /'
    fi
  fi
fi
echo ""

# ── 3. Remove eval label from EVAL_DASHBOARD_LABEL ────────────────────────────

echo "3. Removing 'finance' label from EVAL_DASHBOARD_LABEL"
if [[ -n "$DASHBOARD_LABEL" && "$DASHBOARD_LABEL" != "replace-with-dashboard-identifier" ]]; then
  run "omni documents remove-label $DASHBOARD_LABEL finance"
else
  echo "  (EVAL_DASHBOARD_LABEL not configured — skipping)"
fi
echo ""

# ── 4. Delete model-builder shared-model fixtures ─────────────────────────────

echo "4. Deleting model-builder eval-created shared model files"
if [[ -n "$MODEL_ID" && "$MODEL_ID" != "replace-with-shared-model-id" ]]; then
  if $DRY_RUN; then
    echo "  omni models yaml-delete $MODEL_ID --filename public/customer_segments.view --mode extension"
  else
    if omni models yaml-get "$MODEL_ID" --filename public/customer_segments.view -o json 2>/dev/null \
      | jq -e '.files["public/customer_segments.view"]? // "" | contains("customer_segments")' >/dev/null; then
      run "omni models yaml-delete $MODEL_ID --filename public/customer_segments.view --mode extension"
    else
      echo "  (public/customer_segments.view not present — skipping)"
    fi
  fi
else
  echo "  (EVAL_MODEL_ID not configured — skipping)"
fi
echo ""

# ── 5. Delete non-baseline model branches ─────────────────────────────────────

echo "5. Deleting model branches on EVAL_MODEL_ID (excluding 'eval-comparison-branch')"
if [[ -n "$MODEL_ID" && "$MODEL_ID" != "replace-with-shared-model-id" ]]; then
  BRANCH_NAMES=$(omni models list --include activeBranches -o json 2>/dev/null \
    | jq -r --arg m "$MODEL_ID" '
        .records[]?
        | select(.id==$m)
        | (.activeBranches // [])[]?
        | select(.name | startswith("eval-comparison-branch") | not)
        | .name
      ')

  if [[ -z "$BRANCH_NAMES" ]]; then
    echo "  (no non-baseline branches present — skipping)"
  else
    while IFS= read -r bname; do
      [[ -n "$bname" ]] || continue
      run "omni models delete-branch $MODEL_ID '$bname'"
    done <<< "$BRANCH_NAMES"
  fi
else
  echo "  (EVAL_MODEL_ID not configured — skipping)"
fi
echo ""

echo "Reset complete."
if $DRY_RUN; then
  echo "(Dry-run — no changes made)"
fi

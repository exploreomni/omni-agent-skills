# Eval Instance Setup

This guide covers setting up a dedicated Omni instance for running skill evals. Use a dedicated instance — model-writing skills create and merge branches, and admin skills create users and schedules.

## Prerequisites

- Omni CLI installed and configured (`omni config use <profile>`)
- Connection Admin or Modeler permissions on the instance
- BenchFlow installed (`uv tool install 'benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main'`) or `uv` available for the runner
- Model credentials in `evals/.env.local` (for example `ANTHROPIC_API_KEY`)

## 1. Database

Connect a database with a standard e-commerce schema. The Omni demo dataset (PostgreSQL or Snowflake) works out of the box. The evals expect these tables:

| Table | Key columns |
|---|---|
| `order_items` | `id`, `created_at`, `sale_price`, `status`, `inventory_item_id`, `user_id` |
| `users` | `id`, `first_name`, `last_name`, `email` |
| `inventory_items` | `id`, `product_category`, `product_name`, `product_brand` |
| `products` | `id`, `category`, `name` |

Status values in `order_items` should include `complete`, `cancelled`, `processing`, `returned`, `shipped`. Data should span at least 12 months with a few thousand rows for meaningful query results.

## 2. Build the Shared Model

Run these commands against your shared model ID. Find it with `omni models list` — use the model with `modelKind: SHARED`.

```bash
MODEL_ID="your-shared-model-id"
```

### Add revenue measures to order_items

```bash
omni models yaml-create "$MODEL_ID" --body "$(jq -n \
  --arg fileName "public/order_items.view" \
  --arg mode "extension" \
  --arg commitMessage "Add revenue measures" \
  --arg yaml 'measures:
  total_revenue:
    sql: "${sale_price}"
    aggregate_type: sum
    format: currency_2
    description: Sum of sale_price across all orders.
  completed_revenue:
    sql: "${sale_price}"
    aggregate_type: sum
    format: currency_2
    description: Revenue from completed orders only.
    filters:
      status:
        is: complete
' '{fileName: $fileName, yaml: $yaml, mode: $mode, commitMessage: $commitMessage}')"
```

### Add full_name to users

```bash
omni models yaml-create "$MODEL_ID" --body "$(jq -n \
  --arg fileName "public/users.view" \
  --arg mode "extension" \
  --arg commitMessage "Add full_name dimension" \
  --arg yaml 'dimensions:
  full_name:
    sql: "${first_name} || '"'"' '"'"' || ${last_name}"
    description: Customer full name.
    label: Full Name
' '{fileName: $fileName, yaml: $yaml, mode: $mode, commitMessage: $commitMessage}')"
```

> **Dialect note**: The `||` concat operator works for PostgreSQL and Snowflake. For BigQuery use `CONCAT(${first_name}, " ", ${last_name})`.

### Create the order_items topic

```bash
omni models yaml-create "$MODEL_ID" --body "$(jq -n \
  --arg fileName "order_items.topic" \
  --arg commitMessage "Create order_items topic with AI context" \
  --arg yaml 'base_view: order_items
label: Orders
description: Order line items with product, inventory, and customer data. Use for revenue, sales performance, and customer analysis.

joins:
  users: {}
  inventory_items:
    products: {}

ai_context: |
  Use this topic for revenue, sales, and order analysis.
  "revenue" and "sales" map to total_revenue (sum of sale_price).
  "completed revenue" or "completed orders" maps to completed_revenue (status = complete only).
  "orders" and "count" map to the count measure.
  "customers" and "users" map to users.count or users.id.
  Product category and brand come from inventory_items (joined via inventory_item_id).
  Status values: complete, cancelled, processing, returned, shipped.
  All monetary values are in USD.

sample_queries:
  revenue_by_month:
    prompt: "What month had the highest revenue?"
    ai_context: "Use total_revenue grouped by order_items.created_at month, sorted descending, limit 1"
    query:
      base_view: order_items
      topic: order_items
      fields:
        - order_items.created_at[month]
        - order_items.total_revenue
      sorts:
        - field: order_items.total_revenue
          desc: true
      limit: 1

  top_customers_by_revenue:
    prompt: "Who are our top 10 customers by revenue?"
    ai_context: "Group by users.full_name, sort total_revenue descending, limit 10"
    query:
      base_view: order_items
      topic: order_items
      fields:
        - users.full_name
        - order_items.total_revenue
      sorts:
        - field: order_items.total_revenue
          desc: true
      limit: 10
' '{fileName: $fileName, yaml: $yaml, commitMessage: $commitMessage}')"
```

### Validate

```bash
omni models validate "$MODEL_ID"
# Should return []
```

## 3. Create Labels

```bash
omni labels create finance
omni labels create sales
```

## 4. Create Dashboards

Run these commands and note the `identifier` from each response — you'll need them for `eval-env.local.json` in step 6.

```bash
MODEL_ID="your-shared-model-id"

# Revenue Overview — 2 tiles (content-explorer eval 2: inspect query fields)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{
  modelId: $m, name: "Revenue Overview",
  queryPresentations: [
    {name: "Monthly Revenue Trend", topicName: "order_items", prefersChart: true, visType: "basic",
     fields: ["order_items.created_at[month]", "order_items.total_revenue"],
     query: {table: "order_items", join_paths_from_topic_name: "order_items",
             fields: ["order_items.created_at[month]", "order_items.total_revenue"],
             sorts: [{column_name: "order_items.created_at[month]", sort_descending: false}],
             limit: 100, visConfig: {chartType: "lineColor"}}, config: {}},
    {name: "Top 10 Customers by Revenue", topicName: "order_items", prefersChart: false, visType: "basic",
     fields: ["users.full_name", "order_items.total_revenue"],
     query: {table: "order_items", join_paths_from_topic_name: "order_items",
             fields: ["users.full_name", "order_items.total_revenue"],
             sorts: [{column_name: "order_items.total_revenue", sort_descending: true}],
             limit: 10}, config: {}}
  ]
}')" | jq '{name: "Revenue Overview", identifier: .workbook.identifier}'

# Q1 Sales Report — 2 tiles (content-explorer eval 4: download as PDF)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{
  modelId: $m, name: "Q1 Sales Report",
  queryPresentations: [
    {name: "Total Revenue Q1", topicName: "order_items", prefersChart: true, visType: "omni-kpi",
     fields: ["order_items.total_revenue"],
     query: {table: "order_items", join_paths_from_topic_name: "order_items",
             fields: ["order_items.total_revenue"],
             filters: {"order_items.created_at": "this quarter"}, limit: 1}, config: {}},
    {name: "Revenue by Status", topicName: "order_items", prefersChart: true, visType: "basic",
     fields: ["order_items.status", "order_items.total_revenue"],
     query: {table: "order_items", join_paths_from_topic_name: "order_items",
             fields: ["order_items.status", "order_items.total_revenue"],
             sorts: [{column_name: "order_items.total_revenue", sort_descending: true}],
             limit: 10, visConfig: {chartType: "bar"}}, config: {}}
  ]
}')" | jq '{name: "Q1 Sales Report", identifier: .workbook.identifier}'

# Sales Performance — 1 existing tile (content-builder eval 2: add tile, preserve existing)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{
  modelId: $m, name: "Sales Performance",
  queryPresentations: [
    {name: "Revenue by Month", topicName: "order_items", prefersChart: true, visType: "basic",
     fields: ["order_items.created_at[month]", "order_items.total_revenue"],
     query: {table: "order_items", join_paths_from_topic_name: "order_items",
             fields: ["order_items.created_at[month]", "order_items.total_revenue"],
             sorts: [{column_name: "order_items.created_at[month]", sort_descending: false}],
             limit: 24, visConfig: {chartType: "area"}}, config: {}}
  ]
}')" | jq '{name: "Sales Performance → EVAL_DASHBOARD_TILES", identifier: .workbook.identifier}'

# Order Analysis — empty (content-builder eval 4: workbook model)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{modelId: $m, name: "Order Analysis"}')" \
  | jq '{name: "Order Analysis → EVAL_DASHBOARD_WORKBOOK", identifier: .workbook.identifier}'

# Executive Summary — empty (admin eval 2: set group permissions)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{modelId: $m, name: "Executive Summary"}')" \
  | jq '{name: "Executive Summary → EVAL_DASHBOARD_PERMISSIONS", identifier: .workbook.identifier}'

# Weekly Metrics — empty (admin eval 3: create schedule)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{modelId: $m, name: "Weekly Metrics"}')" \
  | jq '{name: "Weekly Metrics → EVAL_DASHBOARD_SCHEDULE", identifier: .workbook.identifier}'

# Finance Overview — empty (content-explorer eval 3: add label)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{modelId: $m, name: "Finance Overview"}')" \
  | jq '{name: "Finance Overview → EVAL_DASHBOARD_LABEL", identifier: .workbook.identifier}'

# Customer Dashboard — empty (embed eval 1: generate signed embed URL)
omni documents create --body "$(jq -n --arg m "$MODEL_ID" '{modelId: $m, name: "Customer Dashboard"}')" \
  | jq '{name: "Customer Dashboard → EVAL_DASHBOARD_EMBED", identifier: .workbook.identifier}'
```

### Finance dashboards (content-explorer eval 1: find most recently updated by label)

Create 3 dashboards labeled `finance`. Having different creation times gives the "most recently updated" assertion something to test.

```bash
for name in "Finance P&L" "Finance Orders by Status" "Finance Customer Report"; do
  ID=$(omni documents create --body "$(jq -n --arg m "$MODEL_ID" --arg n "$name" \
    '{modelId: $m, name: $n}')" | jq -r '.workbook.identifier')
  omni documents add-label "$ID" finance
  echo "$name → $ID"
done
```

## 5. Create a Model Branch for AI Evals

The `omni-ai-eval` skill compares the main model against a branch (eval 2). Create a persistent branch to use as the comparison target:

```bash
omni models create-branch "$MODEL_ID" --body '{"name": "eval-comparison-branch"}' \
  | jq '{branchId: .model.id, name: .model.name}'
```

Note the returned `branchId` — this goes into `eval-env.local.json` as `EVAL_BRANCH_ID`.

## 6. Configure Local Eval Files

Copy the template and fill in all identifiers collected above:

```bash
cp evals/eval-env.json evals/eval-env.local.json
cp evals/.env.example evals/.env.local
```

Edit `evals/eval-env.local.json`:

```json
{
  "EVAL_MODEL_ID":              "<your shared model ID — `omni models list` then pick modelKind: SHARED>",
  "EVAL_DASHBOARD_PERMISSIONS": "<Executive Summary identifier>",
  "EVAL_DASHBOARD_SCHEDULE":    "<Weekly Metrics identifier>",
  "EVAL_DASHBOARD_TILES":       "<Sales Performance identifier>",
  "EVAL_DASHBOARD_WORKBOOK":    "<Order Analysis identifier>",
  "EVAL_DASHBOARD_LABEL":       "<Finance Overview identifier>",
  "EVAL_DASHBOARD_EMBED":       "<Customer Dashboard identifier>",
  "EVAL_BRANCH_ID":             "<eval-comparison-branch model ID>",
  "EVAL_EXISTING_USER":         "<email of a user that exists in the instance>",
  "EVAL_EMBED_USER":            "<externalId of a configured embed user>"
}
```

Then put local runtime credentials in `evals/.env.local`:

```dotenv
ANTHROPIC_API_KEY=...
EVAL_AGENT=claude-agent-acp
EVAL_MODEL=claude-sonnet-4-6
EVAL_SANDBOX=docker
```

Also set Omni credentials for the BenchFlow sandbox:

```dotenv
OMNI_BASE_URL=https://your-instance.example/
OMNI_API_TOKEN=...
```

`eval-env.local.json` is gitignored and never committed.

## 7. Manual Setup (Omni UI or SCIM)

These items require either the Omni admin UI or your IdP's SCIM integration:

**User attributes** (Settings → User Attributes):
- `region` — used by admin eval 4. Create the definition only; the eval sets
  `region = West Coast` on `EVAL_EXISTING_USER` through SCIM.
- `brand` — used by embed eval 1 for row-level security. Create the definition
  only; no stored user value is required for the eval because the signed embed
  URL passes `userAttributes: { brand: ["Acme"] }` at signing time.

**Users and groups** (Settings → Users or via SCIM):
- At least one regular user whose email goes into `EVAL_EXISTING_USER`
- A group named `Analytics Team` — used by admin eval 2

**Embed** (Settings → Embed):
- Enable embed and configure your embed domain
- Create an embed user with a known `externalId` — this goes into `EVAL_EMBED_USER`

## 8. Verify

Smoke-test the model is working before running evals:

```bash
omni query run --body "$(jq -n --arg m "$MODEL_ID" '{
  query: {modelId: $m, table: "order_items",
          join_paths_from_topic_name: "order_items",
          fields: ["order_items.total_revenue", "order_items.count"],
          limit: 1},
  resultType: "csv"
}')"
# Should return a single row with revenue and count values
```

## After Each Eval Run (Cleanup)

Some evals write state. Reset before re-running:

| Eval | What it creates | How to clean up |
|---|---|---|
| omni-admin eval 1 | Creates `newanalyst@company.com` user | Delete via SCIM or admin UI |
| omni-admin eval 3 | Creates a schedule on `EVAL_DASHBOARD_SCHEDULE` | Delete via admin UI or `omni schedules delete` |
| omni-content-builder eval 2 | Adds a tile to `EVAL_DASHBOARD_TILES` | `./evals/reset.sh` recreates Sales Performance and updates `eval-env.local.json` |
| omni-content-builder eval 10 | Creates its own throwaway model branch (with an `eval_branch_avg_price` measure) and a branch-bound draft on it | Branch-cleanup command below removes it and its draft — the branch name does not start with `eval-`, so the filter catches it. Leaves `EVAL_BRANCH_ID`/`eval-comparison-branch` untouched. |
| omni-content-explorer eval 3 | Adds `finance` label to `EVAL_DASHBOARD_LABEL` | `omni documents remove-label <id> finance` |
| omni-model-builder evals 1–4 | Creates model branches | `omni models list --include activeBranches` then `omni models delete-branch` |
| omni-ai-optimizer evals 1–3 | Creates model branches | Same as above |

The eval runner enforces a small read-only preflight before starting BenchFlow
for cases with known mutable remote fixtures. If preflight fails, no LLM tasks
are started. Run `./evals/reset.sh` first, rerun preflight, then manually clean
or recreate any fixture that still fails.

Do not rerun content-builder eval 2 against a dashboard that was already
modified by a previous attempt. A mutated dashboard can contain extra tiles or
filters that make the next run test cleanup/debugging behavior instead of the
intended "add one KPI tile while preserving existing tiles" workflow. Reset
recreates this dashboard and repoints `EVAL_DASHBOARD_TILES`.

Model-builder evals should not be merged into the shared model during normal
runs. If a previous run accidentally shipped a field to production, either
remove it manually or use a fresh eval instance; otherwise future runs may
correctly detect that the requested field already exists and skip the branch
workflow the eval is intended to test.

Branch cleanup command:

```bash
MODEL_ID="your-shared-model-id"
omni models list --include activeBranches 2>/dev/null \
  | jq -r '.records[].activeBranches[]? | select(.name | startswith("eval-") | not) | .id' \
  | xargs -I{} omni models delete-branch "$MODEL_ID" --body '{"branchId": "{}"}'
```

> Adjust the `startswith` filter to protect your `eval-comparison-branch` from cleanup.

---
name: omni-model-builder
description: Create and edit Omni Analytics semantic model definitions — views, topics, dimensions, measures, relationships, and query views — using YAML through the Omni CLI. Use this skill whenever someone wants to add a field, create a new dimension or measure, define a topic, set up joins between tables, modify the data model, build a new view, add a calculated field, create a relationship, edit YAML, work on a branch, promote model changes, or any variant of "model this data", "add this metric", "create a view for", or "set up a join between". Also use for migrating modeling patterns since Omni's YAML is conceptually similar to other semantic layer definitions.
---

# Omni Model Builder

Create and modify Omni's semantic model through the YAML API — views, topics, dimensions, measures, relationships, and query views.

> **Tip**: Always use `omni-model-explorer` first to understand the existing model.

## Prerequisites

```bash
command -v omni >/dev/null || curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh
```

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

You need **Modeler** or **Connection Admin** permissions.

## Omni's Layered Modeling Architecture

Omni uses a **layered approach** where each layer builds on top of the previous:

1. **Schema Layer** — Auto-generated from your database. Reflects tables, views, columns, and their types. Kept in sync via schema refresh.

2. **Shared Model Layer** — Your governed semantic model. Where you define dimensions, measures, joins, and topics that are reusable across the organization.

3. **Workbook Model Layer** — Ad hoc extensions within individual workbooks. Used for experimental fields before promotion to shared model.

4. **Branch Layer** — Intermediate development layer. Used when working in branches before merging changes to shared model.

**Key concept**: The schema layer is the foundation and source of truth for table/column structure. When your database schema changes (new tables, deleted columns, type changes), you refresh the schema to keep Omni in sync. All user-created content (dimensions, measures, relationships, topics) flows through the shared model layer.

**Development workflow**: When building or modifying the model, you work in **branches** (see "Safe Development Workflow" below). Branches are isolated copies where you can safely experiment before merging changes back to shared model. This skill covers creating and editing model definitions in both branches and shared models.

## Determine SQL Dialect

Before writing any SQL expressions, confirm the dialect from the connection — don't guess from the connection name:

```bash
# 1. List models to find connectionId
omni models list

# 2. Look up the connection's dialect
omni connections list
# → find your connectionId and read the "dialect" field
# → e.g. "bigquery", "postgres", "snowflake", "databricks"
```

Use dialect-appropriate functions in your SQL (e.g. `SAFE_DIVIDE` for BigQuery, `NULLIF(a/b)` for Postgres/Snowflake).

## Schema Refresh: Syncing with Database Changes

The **schema layer** is auto-generated from your database. When your database schema changes (new/deleted/renamed columns, type changes), refresh Omni's schema layer to stay in sync.

**When to trigger:**
- New tables added to your database
- Column added/renamed/deleted in existing tables
- Creating a new view from scratch and want auto-generated base dimensions
- Model is out of sync with database

**What it does:**
- Introspects your data warehouse
- Auto-generates base dimensions for all columns with correct types and timeframes
- Detects deletions and broken references
- Runs as a background job (can take several minutes)

**Side effect:** May auto-generate dimensions for columns you don't need. Suppress with `hidden: true` in your extension layer.

**Trigger via API:**

```bash
omni models refresh <modelId>

# With branch:
omni models refresh <modelId> --branch-id <branchId>
```

Requires **Connection Admin** permissions.

## Discovering Commands

```bash
omni models --help              # List all model operations
omni models yaml-create --help  # Show flags for writing YAML
```

## Safe Development Workflow

Always work in a branch. Never write directly to production.

### Step 0: Create a Branch

```bash
omni models create-branch <modelId> --name "my-feature-branch"
```

The response `model.id` is your `branchId` — a UUID you'll pass to all subsequent API calls. To list existing branches at any time:

```bash
omni models list --include activeBranches
```

> **Git-connected models**: If your model is connected to a git repo (`omni models git-get <modelId>` returns an `sshUrl`), merging an Omni branch will automatically commit the changes back to your git `baseBranch`. Choose one workflow and stick to it — either edit via the Omni branch API (then `git pull` to sync local files), or edit local files and push via git. Mixing both leads to conflicts.

### Step 1: Write YAML to a Branch

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "my_new_view.view",
  "yaml": "dimensions:\n  order_id:\n    primary_key: true\n  status:\n    label: Order Status\nmeasures:\n  count:\n    aggregate_type: count",
  "mode": "extension",
  "branchId": "{branchId}",
  "commitMessage": "Add my_new_view with status dimension and count measure"
}'
```

> **Note**: The `branchId` parameter must be a UUID from the server (Step 0). Passing a string name instead will return `400 Bad Request: Unrecognized key: "branchName"`.

### Step 2: Validate

```bash
omni models validate <modelId> --branch-id <branchId>
```

Returns validation errors and warnings with `message`, `yaml_path`, and sometimes `auto_fix`.

### Step 3: Merge the Branch

> **Important**: Always ask the user for confirmation before merging. Merging applies changes to the production model and cannot be easily undone.

```bash
omni models merge-branch <modelId> <branchName>
```

If git with required PRs is configured, merge through your git workflow instead.

## YAML File Types

| Type | Extension | Purpose |
|------|-----------|---------|
| View | `.view` | Dimensions, measures, filters for a table |
| Topic | `.topic` | Joins views into a queryable unit |
| Relationships | (special) | Global join definitions |

Write with `mode: "extension"` (shared model layer). To delete a file, send empty `yaml`.

## Writing Views

> **Every view MUST have a `primary_key: true` dimension.** Without a primary key, queries that join to this view will produce fanout errors or incorrect aggregations. Use the table's natural unique identifier (e.g., `id`, `order_id`, `user_id`). If the table has no single unique column, create a composite key with a SQL expression: `sql: ${schema_name} || '-' || ${table_name}`.

### Basic View

```yaml
dimensions:
  order_id:
    primary_key: true
  status:
    label: Order Status
  created_at:
    label: Created Date
measures:
  count:
    aggregate_type: count
  total_revenue:
    sql: ${sale_price}
    aggregate_type: sum
    format: currency_2
```

### Understanding Schema Layer vs Extension Layer

When you create a view, Omni separates **schema** (database structure) from **model** (your business logic):

- **Schema layer**: Auto-generated base dimensions, one per column. Types come from the database. Read-only, synced via schema refresh.
- **Extension layer**: Your custom YAML. Can override base dimensions, add new dimensions/measures, hide columns, add business logic.

When both layers exist for a field with the same name, **your extension definition wins** but **type information comes from the schema layer**.

**Example**: Table has columns `created_at` (DATE) and `revenue` (NUMERIC).

```yaml
# Schema layer (auto-generated)
dimensions:
  created_at: {}  # type: DATE, auto-generates timeframes
  revenue: {}     # type: NUMERIC

# Extension layer (your YAML)
dimensions:
  created_at:
    label: "Order Created"
    description: "When the order was placed"

  revenue:
    hidden: true  # Hide the raw column

measures:
  total_revenue:
    sql: SUM(${revenue})
    aggregate_type: sum
    format: currency_2
```

Result: `created_at` inherits its type from schema layer (DATE with automatic week/month/year granularities) but gets your label. The raw `revenue` column is hidden, only exposed through the `total_revenue` measure.

**Key insight**: If your extension layer defines a dimension but there's no schema layer base dimension to provide type information, Omni can't infer granularities or types. Solution: trigger schema refresh to auto-generate the schema layer (see "Schema Refresh" section above).

### Dimension Parameters

See `references/modelParameters.md` for the complete list of 35+ dimension parameters, format values, and timeframes.

Most common parameters:
- `sql` — SQL expression using `${field_name}` references
- `label` — display name · `description` — help text (also used by Blobby)
- `primary_key: true` — unique key (critical for aggregations)
- `hidden: true` — hides from picker, still usable in SQL
- `format` — `number_2`, `currency_2`, `percent_2`, `id`
- `group_label` — groups fields in the picker
- `synonyms` — alternative names for AI matching (e.g., `[client, account, buyer]`)

### Measure Parameters

See `references/modelParameters.md` for the complete list of 24+ measure parameters and all 13 aggregate types.

Measure filters restrict rows before aggregation:

```yaml
measures:
  completed_orders:
    aggregate_type: count
    filters:
      status:
        is: complete
  california_revenue:
    sql: ${sale_price}
    aggregate_type: sum
    filters:
      state:
        is: California
```

Filter conditions: `is`, `is_not`, `greater_than`, `less_than`, `contains`, `starts_with`, `ends_with`

## Writing Topics

See [Topics setup](https://docs.omni.co/modeling/topics/setup.md) for complete YAML examples with joins, fields, and ai_context, and [Topic parameters](https://docs.omni.co/modeling/topics/parameters.md) for all available options.

Key topic elements:
- `base_view` — the primary view for this topic
- `joins` — nested structure for join chains (e.g., `users: {}` or `inventory_items: { products: {} }`)
- `ai_context` — guides Blobby's field mapping (e.g., "Map 'revenue' → total_revenue")
- `default_filters` — applied to all queries unless removed
- `always_where_sql` — non-removable filters
- `fields` — field curation: `[order_items.*, users.name, -users.internal_id]`

## Writing Relationships

```yaml
- join_from_view: order_items
  join_to_view: users
  on_sql: ${order_items.user_id} = ${users.id}
  relationship_type: many_to_one
  join_type: always_left
```

| Type | When to Use |
|------|-------------|
| `many_to_one` | Orders → Users |
| `one_to_many` | Users → Orders |
| `one_to_one` | Users → User Settings |
| `many_to_many` | Tags ↔ Products (rare) |

Getting `relationship_type` right prevents fanout and symmetric aggregate errors.

## Query Views

Virtual tables defined by a saved query. Like regular views, query views **must include a `primary_key: true` dimension** to be joinable:

```yaml
schema: PUBLIC
query:
  fields:
    order_items.user_id: user_id
    order_items.count: order_count
    order_items.total_revenue: lifetime_value
  base_view: order_items
  topic: order_items

dimensions:
  user_id:
    primary_key: true
  order_count: {}
  lifetime_value:
    format: currency_2
```

Or with raw SQL:

```yaml
schema: PUBLIC
sql: |
  SELECT user_id, COUNT(*) as order_count, SUM(sale_price) as lifetime_value
  FROM order_items GROUP BY 1
```

## Common Validation Errors

| Error | Fix |
|-------|-----|
| "No view X" | Check view name spelling |
| "No join path from X to Y" | Add a relationship |
| "Duplicate field name" | Remove duplicate or rename (or suppress with `hidden: true` if one is auto-generated) |
| "Invalid YAML syntax" | Check indentation (2 spaces, no tabs) |
| Fanout / incorrect aggregations on joins | Add `primary_key: true` to the joined view — every view that participates in a join must have a primary key |
| Column reference error (e.g., "Column `X` not found") | Check that the table exists and your Omni connection has access |

## Troubleshooting: Model Out of Sync with Database

If your model doesn't reflect the database (missing columns, broken references, wrong types), trigger a schema refresh (see "Schema Refresh" section above). Then validate:

```bash
omni models validate <modelId>
```

Common issues and fixes:

| Issue | Cause | Fix |
|-------|-------|-----|
| **Broken column references** | Column no longer exists in database | Remove or update the `sql` reference |
| **Field name collision** | Auto-generated dimension conflicts with your measure | Suppress with `hidden: true` or rename |
| **Unknown field types** | Type info not available from schema | Verify column exists and connection has access |
| **Missing tables** | Table not in schema after refresh | Verify table exists and connection includes its database/schema |

## Docs Reference

- [Model YAML API](https://docs.omni.co/api/models.md) · [Views](https://docs.omni.co/modeling/views.md) · [Topics](https://docs.omni.co/modeling/topics/parameters.md) · [Dimensions](https://docs.omni.co/modeling/dimensions.md) · [Measures](https://docs.omni.co/modeling/measures.md) · [Relationships](https://docs.omni.co/modeling/relationships.md) · [Query Views](https://docs.omni.co/modeling/query-views.md) · [Branch Mode](https://docs.omni.co/finding-content/drafting-publishing/branch-mode.md)

## Related Skills

- **omni-model-explorer** — understand the model before modifying
- **omni-ai-optimizer** — add AI context after building topics
- **omni-query** — test new fields

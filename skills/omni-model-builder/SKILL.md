---
name: omni-model-builder
description: Create and edit Omni Analytics semantic model definitions — views, topics, dimensions, measures, relationships, and query views — using YAML through the Omni CLI. Use this skill whenever someone wants to add a field, create a new dimension or measure, define a topic, set up joins between tables, modify the data model, build a new view, add a calculated field, create a relationship, edit YAML, work on a branch, promote model changes, or any variant of "model this data", "add this metric", "create a view for", or "set up a join between". Also use for migrating modeling patterns since Omni's YAML is conceptually similar to other semantic layer definitions.
---

# Omni Model Builder

Create and modify Omni's semantic model through the YAML API — views, topics, dimensions, measures, relationships, and query views.

> **Tip**: Always use `omni-model-explorer` first to understand the existing model.

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>
```

You need **Modeler** or **Connection Admin** permissions.

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

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
- Column added, renamed, or deleted in an existing table
- Creating a new view from scratch and you want auto-generated base dimensions
- Model is out of sync with the database

**What it does:** Introspects your data warehouse, auto-generates base dimensions with correct types and timeframes, detects deletions and broken references. Runs as a background job (can take several minutes).

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

> **Git-connected models**: If your model is connected to a git repo, prefer pushing branch changes through a pull request (Step 3 below) rather than merging directly. Choose one workflow and stick to it — either edit via the Omni branch API (then `git pull` to sync local files), or edit local files and push via git. Mixing both leads to conflicts.

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

### Step 2: Validate and Test

Every YAML write must be validated and tested before merging. Silent failures are common — a field can be syntactically valid YAML but produce wrong results or broken queries.

**2a. Run model validation:**

```bash
omni models validate <modelId> --branchid <branchId>
```

Check the response:
- If any issue has `is_warning: false`, it's an error — fix before proceeding
- Common errors: broken column references, duplicate field names, invalid SQL syntax, missing join paths
- If `auto_fix` is present, review the suggestion before applying

**2b. Test new/modified fields with a query:**

Run a query that exercises the fields you just created or modified:

```bash
omni query run --body '{
  "query": {
    "modelId": "<modelId>",
    "table": "your_view",
    "fields": ["your_view.new_dimension", "your_view.new_measure"],
    "limit": 10,
    "join_paths_from_topic_name": "your_topic"
  },
  "branchId": "<branchId>"
}'
```

> **Two complementary validation tools:**
> - `omni query run` — structured validation using explicit field expressions; use to precisely test specific dimensions, measures, and join paths
> - `omni ai job-submit --branch-id <branchId> --topic-name <topicName>` — natural language validation; use to confirm the topic answers business questions correctly against live branch data. `omni ai generate-query --run-query true` does not resolve branch-only topics at execution time and should not be used for branch validation.

**What to check:**
- **No error in response** — if the query returns an error, the field SQL is broken (bad column reference, wrong aggregate, dialect mismatch)
- **`summary.row_count` > 0** — confirms the field resolves to actual data
- **Values look correct** — spot-check that a `sum` isn't returning a `count`, that a boolean dimension returns true/false (not 0/1 unexpectedly), etc.
- **Joins work** — if your field references another view (e.g., `${users.id}`), include fields from both views to confirm the join resolves

**2c. If you modified a relationship or topic join, test the join path:**

```bash
omni query run --body '{
  "query": {
    "modelId": "<modelId>",
    "table": "base_view",
    "fields": ["base_view.id", "joined_view.some_field"],
    "limit": 10,
    "join_paths_from_topic_name": "your_topic"
  }
}'
```

A working join returns rows with data from both views. A broken join returns an error or null values in the joined columns.

**2d. Verify the field appears in the model:**

```bash
# Check the topic to confirm new fields are listed
omni models get-topic <modelId> <topicName> --branch-id <branchId>

# Or read back the YAML you just wrote
omni models yaml-get <modelId> --filename your_view.view --branchid <branchId>

```

Confirm your new fields are listed in the response. If they're missing, the YAML write may have silently failed (e.g., wrong `fileName`, malformed YAML string) — or the view may live in an offloaded schema that `yaml-get` doesn't surface. Before concluding a view doesn't exist, run the lazy-load fallback (see "Fallback: View Missing from yaml-get" below).

### Step 3: Ship the Branch

> **Important**: Always ask the user for confirmation before shipping. Changes applied to the production model cannot be easily undone. Only ship after validation and testing pass (Step 2).

First, check whether the model is git-connected — this determines which path to take:

```bash
omni models git-get <modelId>
```

- **Returns a config with `sshUrl` / `baseBranch`** → git-connected → use **Path A** (open/update a PR).
- **Returns 404 or no config** → not git-connected → use **Path B** (merge directly in Omni).

#### Path A — Git-connected: open or update a PR

Push the branch contents to git. Creates a new git branch + PR if one doesn't exist; otherwise updates the existing PR:

```bash
omni models commit <modelId> --body '{
  "branch_id": "<branchId>",
  "commit_message": "Add my_new_view with status dimension and count measure"
}'
```

Surface the returned `pr_url` to the user. The reviewer merges the PR in your git host; changes flow back to `baseBranch` on the next sync. Run `omni models commit --help` for optional body flags (`allow_branch_exists`, `require_branch_exists`) when you need to enforce open-only or update-only behavior.

#### Path B — Not git-connected: merge in Omni

```bash
omni models merge-branch <modelId> <branchName>
```

After merging, run one final validation against the production model to confirm the merge didn't introduce conflicts:

```bash
omni models validate <modelId>
```

## YAML File Types

| Type | Extension | Purpose |
|------|-----------|---------|
| View | `.view` | Dimensions, measures, filters for a table |
| Topic | `.topic` | Joins views into a queryable unit |
| Relationships | (special) | Global join definitions |

Write with `mode: "extension"` (shared model layer). To delete a file, send empty `yaml`.

## Writing Views

> **Every view that participates in joins MUST have a real `primary_key: true` dimension.** Without a genuine row-unique primary key, queries that join to this view can produce fanout errors or incorrect aggregations. Use the table's natural unique identifier (e.g., `id`, `order_id`, `user_id`). If no single column is unique, build a composite key from row-level columns that are jointly unique, for example `sql: ${order_id} || '-' || ${line_number}`. If you cannot define a row-unique expression, do not mark a dimension as `primary_key: true` yet; fix the grain first or avoid joining the view until a real key exists.

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
    sql: ${revenue}
    aggregate_type: sum
    format: currency_2
```

Result: `created_at` inherits its type from the schema layer (DATE with automatic week/month/year granularities) but gets your label. The raw `revenue` column is hidden, only exposed through the `total_revenue` measure.

**Key insight**: If your extension defines a dimension but there's no schema layer base dimension to provide type information, Omni can't infer granularities or types. Trigger a schema refresh to auto-generate the schema layer first.

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

Measure filters restrict rows before aggregation using the YAML filter condition syntax. See `references/yaml-filter-syntax.md` for the complete operator reference and measure filter examples.

### Cross-View Fields in Views

Avoid defining cross-view fields (dimensions or measures whose `sql` references `${other_view.field}`) directly in a view file. These fields depend on another view being joined, which is not guaranteed in every topic that includes this view. In topics where the referenced view isn't present, the field will be omitted — but more importantly, the model validator will throw errors for any topic that includes this view without also joining the referenced view. This can create a cascade of validator errors across topics that are otherwise valid but happen to include only a subset of the involved views.

**In the vast majority of cases, cross-view fields should be defined in the topic's `views:` block** (see "Topic-Scoped View Definitions"), where the join context is explicit and controlled.

Only define a cross-view field in the view file itself when you are certain the referenced view will always be joined in every topic that includes this view — for example, when the join is defined globally and the two views are inseparable by design.

## Fallback: View Missing from yaml-get

Before concluding that a view doesn't exist, always run this two-step check. `yaml-get` only returns views from currently-loaded schemas — views in offloaded or inactive schemas won't appear, but they're still available.

```bash
# 1. List all schemas the connection knows about (loaded, offloaded, and inactive)
omni models get-schemas <modelId>
# → {"schemas": ["ANALYTICS", "PUBLIC", "STAGING", ...]}

# 2. If the target schema appears in the list, load it explicitly
omni models yaml-get <modelId> --includeschemas PUBLIC
```

**Rules for `--includeschemas`:**
- Accepts exactly **one schema name** per call — commas are rejected. Load schemas one at a time.
- The response will contain only views from that schema; relationships to other schemas are preserved.
- To scope to a branch, add `--branchid <id>` to `yaml-get` or `--branch-id <id>` to `get-schemas` (flag names differ per command).

If the schema isn't in the `get-schemas` list at all, the connection likely doesn't have access or the schema isn't synced — check with a Connection Admin.

## Writing Topics

> **Before writing a topic, verify all views you plan to reference actually exist.** Run `omni models yaml-get <modelId>` and confirm each view appears. If a view is missing, run the lazy-load fallback above before concluding it doesn't exist — it may simply be in an offloaded schema.

See [Topics setup](https://docs.omni.co/modeling/topics/setup.md) for complete YAML examples with joins, fields, and ai_context, and [Topic parameters](https://docs.omni.co/modeling/topics/parameters.md) for all available options.

Key topic elements:
- `base_view` — the primary view for this topic
- `joins` — nested structure for join chains (e.g., `users: {}` or `inventory_items: { products: {} }`)
- `ai_context` — guides Blobby's field mapping (e.g., "Map 'revenue' → total_revenue")
- `default_filters` — applied to all queries unless removed
- `always_where_sql` — non-removable WHERE filter using a SQL expression (cannot be removed by users)
- `always_where_filters` — non-removable WHERE filter using filter specifications (cannot be removed by users)
- `always_having_sql` — non-removable HAVING filter using a SQL expression, applied after aggregation (cannot be removed by users)
- `always_having_filters` — non-removable HAVING filter using filter specifications, applied after aggregation (cannot be removed by users)
- `fields` — field curation: `[order_items.*, users.name, -users.internal_id]`

### Filter Expressions for Topics

When configuring `default_filters`, `always_where_filters`, or `always_having_filters` on a topic, use the YAML filter condition syntax — the same syntax used in measure filters. See `references/yaml-filter-syntax.md` for the complete reference.

If the right filter configuration for a given use case isn't obvious, use the Omni AI CLI to search the docs:

```bash
omni ai search-omni-docs "how do I configure always_where_filters on a topic in Omni?"
```

Use targeted questions to get precise YAML examples for your specific filtering need before writing the model YAML.

## Writing Relationships

### Global Relationships

Global relationships are defined in the shared relationships file and are available across all topics. Use these for standard, reusable joins.

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

### Topic-Scoped Relationships

> **Before defining, check the global relationships file** for a join between the same two views in either direction. Same `on_sql` → redundant, use `joins:` only. Different `on_sql` → default to the extended views pattern below rather than a silent override. Confirm intent with the modeler.

Use topic-scoped relationships for one-off joins not in the shared model, or joining the same table multiple times under different conditions.

```yaml
# .topic file
relationships:
  - join_from_view: order_items
    join_to_view: users
    on_sql: ${order_items.user_id} = ${users.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  users: {}
```

> **`joins` vs `relationships`:** `joins` declares which views are in the topic and their hierarchy; `relationships` defines the join conditions. A topic using only global relationships needs only `joins`. A topic with a one-off join needs both.

#### Extended Views: Joining the Same Table Multiple Ways

When the same table needs multiple joins (e.g., `users` as buyer and seller), use the **extended views** pattern — not `join_to_view_as`. Two variants:

**Variant 1 — Global (reusable):** Create a standalone `.view` file with `extends:`, a role-descriptive name, and a `description:`. Define the relationship globally — any topic can then join it like any other view.

**Variant 2 — Topic-scoped (inline):** Define the alias in the topic's `views:` block with its relationship in the same file. Use when the alias is not generally applicable in other topics.

See `references/topic-scoped-relationships.md` for full YAML examples of both variants.

> If you see a `relationship alias duplicates view name` error, this pattern is the fix.

### Topic-Scoped View Definitions

Topics can define or override views inline using a `views:` block — controlling `display_order`, overriding `label`, adding topic-specific filtered measures or derived dimensions, defining cross-view fields, and joining the same view multiple ways with per-alias conditions.

> **Before adding any topic-scoped field to an existing view:**
> 1. Read the view YAML (`omni models yaml-get`) and confirm the field doesn't already exist. If it does with the same definition, skip it.
> 2. If a field with the same name exists but uses different SQL, this is an override. Confirm explicitly with the modeler — queries through this topic will use the topic-scoped definition; all other topics keep the shared one.

```yaml
# Example: display order + topic-specific filtered measure
views:
  order_items:
    display_order: 0
    measures:
      us_revenue:
        sql: ${sale_price}
        aggregate_type: sum
        format: currency_2
        filters:
          users.country:
            is: US
```

See `references/topic-scoped-views.md` for a full pattern gallery (label overrides, derived dimensions, cross-view fields, multi-join lifecycle, topic-scoped query views).

> **Cross-view fields in `views:` blocks:** Before writing `${view_name.field_name}` references, confirm every referenced view is declared in the topic's `joins:` block — the model validator throws errors for any reference to a view that isn't joined.

**Joining the same view multiple ways** (e.g., ARR at Start / Current / End): Use `extends:` inside the topic's `views:` block to create named aliases, each with its own `on_sql` in `relationships:`. Each alias inherits all base view fields and can override labels independently. For a full YAML example, see `references/topic-scoped-views.md`.

**Topic-scoped query views:** A query view can also be defined inside a topic's `views:` block, scoping it to that topic only. Same primary key rules apply (`primary_key: true` or `custom_compound_primary_key_sql`). Include a `relationships:` entry and a `joins:` entry for the new view — see Query Views section above, and `references/topic-scoped-views.md` for a complete example.

## Query Views

Virtual tables defined by a saved query. A query view must have a primary key or it cannot be joined without producing fanout errors. **Before writing, confirm which field uniquely identifies each row — unless the primary key can be clearly inferred from the query itself and the involved views** (e.g. a query that selects `user_id` from a `users` view where `user_id` is the known primary key).

There are two ways to define the primary key:

**Option 1 — Single unique field:** Mark exactly one dimension `primary_key: true` in the `dimensions:` block.

**Option 2 — Compound key:** When no single field is unique but a combination is, set `custom_compound_primary_key_sql: [field_a, field_b]` at the view level — no `primary_key: true` dimension needed.

Both options work with either a `query:` block (field-mapped virtual table) or a `sql:` block (raw SELECT). In `sql:` blocks, use `${view_name}` to reference a view's underlying table rather than a hard-coded `CATALOG.SCHEMA.TABLE` path — it's preferred and stays correct if the table moves. See `references/query-view-examples.md` for complete YAML for each variant.

> If the user is unsure which field is unique, ask before writing the view. A query view without a primary key will trigger a "Joins fan out the data without a primary key" error when joined. See: https://community.omni.co/t/why-am-i-getting-the-error-joins-fan-out-the-data-without-a-primary-key/37

Query views can also be defined inline within a topic's `views:` block, scoping the virtual table to that topic only. See `references/topic-scoped-views.md` for an example.

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

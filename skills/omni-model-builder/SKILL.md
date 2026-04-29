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

> **Note**: `omni query run` does not currently support `branchId` — queries always run against the production model. This means you can only fully test new fields after merging. Use model validation (2a) and field verification (2d) as your pre-merge safety net, and run query tests immediately after merging.

```bash
omni query run --body '{
  "query": {
    "modelId": "<modelId>",
    "table": "your_view",
    "fields": ["your_view.new_dimension", "your_view.new_measure"],
    "limit": 10,
    "join_paths_from_topic_name": "your_topic"
  }
}'
```

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

### Step 3: Merge the Branch

> **Important**: Always ask the user for confirmation before merging. Merging applies changes to the production model and cannot be easily undone. Only merge after validation and testing pass (Step 2).

```bash
omni models merge-branch <modelId> <branchName>
```

If git with required PRs is configured, merge through your git workflow instead.

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

See `references/yaml-filter-syntax.md` for the complete operator reference covering conditional, numeric, string, and date/time operators, negation, array values, and boolean handling.

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

Relationships can also be defined inline within a topic file using the `relationships:` parameter. These are scoped to that topic only and do not affect other topics.

**When to use topic-scoped instead of global:**
- One-off joins that don't belong in the shared model
- Aliasing the same table multiple times in one topic (e.g., joining `users` twice under different roles)
- Different join conditions for the same views depending on topic context

```yaml
# In a .topic file
relationships:
  - join_from_view: order_items
    join_to_view: users
    on_sql: ${order_items.user_id} = ${users.id}
    relationship_type: many_to_one
    join_type: always_left
```

User attributes can be used in `on_sql` for access-filtered joins:

```yaml
on_sql: ${orders.region} = '{{ omni_attributes.user_region }}'
```

### Joining the Same Table Twice: Extended Views

When you need to join the same table multiple times with different logic or field labels (e.g., a `users` table joined once as the buyer and once as the seller), use the **extended views** pattern rather than `join_to_view_as`. Extended views create a named alias that inherits all fields from the base view and allows full metadata customization.

Define the extended view inline in the topic file using a `views:` block:

```yaml
# .topic file
base_view: order_items

views:
  sellers:
    extends: [users]
    display_order: 1
    dimensions:
      name:
        label: Seller Name

relationships:
  - join_from_view: order_items
    join_to_view: sellers
    on_sql: ${order_items.seller_id} = ${sellers.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  sellers: {}
  users: {}
```

The extended view (`sellers`) inherits all dimensions and measures from `users` and can override labels, display order, or any field metadata. The relationship and joins then reference the extended view name directly.

> If you see a `relationship alias duplicates view name` error, this pattern is the fix — it avoids the naming conflict by creating a proper named view rather than an alias.

### `joins` vs `relationships` in a Topic

These are two distinct parameters that work together:

- **`joins`** — declares *which* views are included in the topic and their hierarchy. Follows existing global (or topic-scoped) relationship definitions. Nesting reflects the join path.
- **`relationships`** — defines the join conditions themselves, scoped to this topic. Required when the join doesn't exist globally.

A topic that uses only global relationships needs only `joins`. A topic with a one-off join needs both `relationships` (to define the join) and `joins` (to include the view in the topic hierarchy):

```yaml
# .topic file with a topic-scoped relationship
base_view: order_items

relationships:
  - join_from_view: order_items
    join_to_view: promotions
    on_sql: ${order_items.promo_id} = ${promotions.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  promotions: {}
  users: {}
```

### Topic-Scoped View Definitions

Topics can define or override views inline using a `views:` block. This is how the extended views pattern works, but it applies more broadly — any dimension, measure, label, or field metadata can be overridden within the topic without touching the shared view file:

```yaml
views:
  order_items:
    dimensions:
      status:
        label: Fulfillment Status
    measures:
      topic_specific_count:
        aggregate_type: count
        filters:
          region:
            is: US
```

Topic-scoped view definitions only affect queries run through this topic. Use them when a field label or metric should differ from the global default for a specific business context.

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

# Omni's Layered Modeling Architecture

Omni uses a layered approach where each layer builds on top of the previous:

1. Schema Layer — Auto-generated from your database. Reflects tables, views, columns, and their types. Kept in sync via schema refresh.
2. Shared Model Layer — Your governed semantic model. Where you define dimensions, measures, joins, and topics that are reusable across the organization.
3. Workbook Model Layer — Ad hoc extensions within individual workbooks. Used for experimental fields before promotion to shared model.
4. Branch Layer — Intermediate development layer. Used when working in branches before merging changes to shared model.

The schema layer is the source of truth for table/column structure (refreshed when the database changes); all user-created content (dimensions, measures, relationships, topics) flows through the shared model layer. You build and modify it in branches (see [Safe Development Workflow](../SKILL.md#safe-development-workflow) in SKILL.md) before merging back to the shared model.

## Understanding Schema Layer vs Extension Layer

When you create a view, Omni separates schema (database structure) from model (your business logic):

- Schema layer: Auto-generated base dimensions, one per column. Types come from the database. Read-only, synced via schema refresh.
- Extension layer: Your custom YAML. Labels, describes or hides base dimensions, and adds new dimensions, measures and business logic.

When both layers define a field with the same name, your extension's keys win and the type comes from the schema layer.

Example: Table has columns `created_at` (DATE) and `revenue` (NUMERIC).

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

If your extension defines a dimension but there's no schema layer base dimension to provide type information, Omni can't infer granularities or types. Trigger a schema refresh to auto-generate the schema layer first.

### Changing the values of a schema dimension

Don't set `sql:` on a dimension the schema layer generates, in any layer: shared model, extension, branch, workbook model or a topic's `views:` block. Every field, filter and dashboard that uses the dimension would silently get the new values (an `is null` filter stops matching once nulls become 'Unknown'), and the stored value would no longer be available as a field.

In place, set only keys that leave the values unchanged, such as `label`, `group_label`, `description`, `hidden`, `format`, `synonyms`, `ai_context`, `drill_fields` and `primary_key`. A change to the values (replacing nulls, CASE buckets, trimming, padding, casting) goes in a new dimension whose `sql:` references the column, with its own label and description. Hiding the column is optional.

```yaml
dimensions:
  state:                 # schema dimension: keys that leave its values unchanged
    group_label: Customer
  state_or_unknown:
    sql: COALESCE(${state}, 'Unknown')
    label: State (with Unknown)
    group_label: Customer
    description: Customer state, with 'Unknown' where none was recorded.
```

When a model already sets `sql:` on a schema dimension, report it to the user. Removing it ([Removing an override](editing-existing-files.md#removing-an-override)) changes what existing content shows, so that is the user's call.

Reading back what you wrote — `--mode`. `yaml-get` returns the combined result by default: the schema base merged with your extension. To see only the deltas you authored, without the auto-generated base columns, read with `--mode extension`:

```bash
# What you authored (deltas only)
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId> --mode extension

# What the model actually resolves to (schema + extension merged) — the default
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId> --mode combined
```

Use `extension` to confirm *what you changed*, and `combined` to confirm *what the model resolves to*. When the model is git-integrated, the combined output mirrors what's written to the repository — which is why committed `*.view.yaml` files carry the schema-layer `table_name:` and base columns, while the extension layer holds only your deltas. For a shared extension model synced to git, the files hold only the extension layer, what `--mode extension` returns. Other `--mode` values: `staged` returns the branch model only; `merged` returns the branch merged with the shared model, in the same form as `extension`; `fully-resolved` returns `combined` with the `extends` chain expanded (the same as `--mode combined --fully-resolved true`).

## File types

| Type | Extension | Purpose |
|------|-----------|---------|
| View | `.view` | Dimensions, measures, filters for a table |
| Topic | `.topic` | Joins views into a queryable unit |
| Relationships | (special) | Global join definitions |
| Composite topic | `.composite_topic` | Joins two or more topics on shared dimensions (see [composite-topics.md](composite-topics.md)) |

## Inspecting a branch

To inspect a branch, `yaml-get` without `--file-name` enumerates the whole model — `--mode extension` for just the branch's changed files (your deltas), `--mode combined` for the full composed model (schema + shared + branch); then drill into any file by its exact path.

## Branches on dbt-connected models

`omni models branch-dbt-get <modelId> <branchName>` (CLI ≥ 1.1.2) reads the dbt environment a branch resolves to, including the dbt git branch it compiles against. A branch with no environment of its own resolves to the connection's default (production) environment, reported with `is_default_environment: true`.

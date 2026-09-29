# Omni's Layered Modeling Architecture

Omni uses a **layered approach** where each layer builds on top of the previous:

1. **Schema Layer** — Auto-generated from your database. Reflects tables, views, columns, and their types. Kept in sync via schema refresh.
2. **Shared Model Layer** — Your governed semantic model. Where you define dimensions, measures, joins, and topics that are reusable across the organization.
3. **Workbook Model Layer** — Ad hoc extensions within individual workbooks. Used for experimental fields before promotion to shared model.
4. **Branch Layer** — Intermediate development layer. Used when working in branches before merging changes to shared model.

**Key concept**: The schema layer is the source of truth for table/column structure (refreshed when the database changes); all user-created content (dimensions, measures, relationships, topics) flows through the shared model layer. You build and modify it in **branches** (see [Safe Development Workflow](../SKILL.md#safe-development-workflow) in SKILL.md) before merging back to the shared model.

## Understanding Schema Layer vs Extension Layer

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

**Reading back what you wrote — `--mode`.** `yaml-get` returns your **extension** layer by default — just the deltas you authored, *not* the auto-generated base columns. To see the **fully-composed** result (schema base + your extension merged), read with `--mode combined`:

```bash
# What you authored (deltas only) — default
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId> --mode extension

# What the model actually resolves to (schema + extension merged)
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId> --mode combined
```

Use `extension` to confirm *what you changed*, and `combined` to confirm *what the model resolves to*. When the model is git-integrated, the **combined** output mirrors what's written to the repository — which is why committed `*.view.yaml` files carry the schema-layer `table_name:` and base columns, while the extension layer holds only your deltas. (Other `--mode` values: `staged`, `merged`, `history`.)

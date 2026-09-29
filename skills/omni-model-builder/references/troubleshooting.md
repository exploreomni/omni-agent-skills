# Troubleshooting

## Fallback: View Missing from yaml-get

Before concluding that a view doesn't exist, always run this two-step check. `yaml-get` only returns views from currently-loaded schemas — views in offloaded or inactive schemas won't appear, but they're still available.

```bash
# 1. List all schemas the connection knows about (loaded, offloaded, and inactive)
omni models get-schemas <modelId>
# → {"schemas": ["ANALYTICS", "PUBLIC", "STAGING", ...]}

# 2. If the target schema appears in the list, load it explicitly
omni models yaml-get <modelId> --include-schemas PUBLIC
```

**Rules for `--include-schemas`:**
- Accepts exactly **one schema name** per call — commas are rejected. Load schemas one at a time.
- The response will contain only views from that schema; relationships to other schemas are preserved.
- To scope to a branch, add `--branch-id <id>` to `yaml-get` or `--branch-id <id>` to `get-schemas` (flag names differ per command).

If the schema isn't in the `get-schemas` list at all, the connection likely doesn't have access or the schema isn't synced — check with a Connection Admin.

## Common Validation Errors

| Error | Fix |
|-------|-----|
| "No view X" | Check view name spelling |
| "No join path from X to Y" | Add a relationship |
| "Duplicate field name" | Remove duplicate or rename (or suppress with `hidden: true` if one is auto-generated) |
| "Invalid YAML syntax" | Check indentation (2 spaces, no tabs) |
| Fanout / incorrect aggregations on joins | Add `primary_key: true` to the joined view — every view that participates in a join must have a primary key |
| Column reference error (e.g., "Column `X` not found") | Check that the table exists and your Omni connection has access |
| Duplicate view appeared at the repo root after an edit | You wrote with a bare `fileName` instead of the file's full path. Delete the stray root file (send empty `yaml` to it) and re-write using the exact `files` key, including its folder prefix (e.g. `MARTS/`) |

## Troubleshooting: Model Out of Sync with Database

If the model doesn't reflect the database (missing columns/tables, wrong types, broken references), trigger a schema refresh (see [Schema Refresh](../SKILL.md#schema-refresh-syncing-with-database-changes) in SKILL.md), then `omni models validate <modelId>`. Field-name collisions and broken column references are usually fixed with `hidden: true` or a rename (see [Common Validation Errors](#common-validation-errors)); persistent missing tables mean the connection lacks access to that database/schema.

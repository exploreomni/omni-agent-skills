# Validation & Testing

Every dashboard build or update must include validation before and after creation. Broken tiles, bad field references, and misconfigured viz specs are silent failures — the dashboard renders but tiles show "Chart unavailable" or "No data" with no API-level error.

## Step 1: Validate the Model

Before building any queries, confirm the underlying model is healthy:

```bash
omni models validate <modelId>
```

Check the response for errors (not just warnings). If `is_warning` is `false` on any issue, the field or join may be broken and queries referencing it will fail silently on the dashboard.

## Step 2: Test Every Query via Execution

Run each planned query through `omni query run` **before** including it in a dashboard. This is the single most important validation step.

```bash
omni query run --body '{
  "query": {
    "modelId": "your-model-id",
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "filters": { "order_items.created_at": "last 90 days" },
    "limit": 10,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

**What to check in the response:**
- **No error field** — if the response contains an `error` key, the query is broken. Fix before proceeding.
- **`summary.row_count` > 0** — a query that returns zero rows will render as an empty tile. This may be correct (no data for the filter range) but is worth flagging.
- **Include your dashboard filters** — pass the same filters you plan to use in `filterConfig` as query-level filters here. This catches bad filter expressions (e.g., wrong field name, unsupported syntax) before they become dashboard-level problems.
- **Long-running queries** — if the response includes `remaining_job_ids`, poll with `omni query wait --jobids <ids>` until complete, then check the final result for errors.

Do this for **every** query you plan to include as a tile. A dashboard with 5 tiles needs 5 validated queries.

## Step 3: Validate Viz Spec Consistency

Before assembling `queryPresentations`, check each tile's viz configuration against these rules. Mismatches cause "No chart available" or silent fallback to table rendering.

**Required consistency checks:**

| Rule | What to check |
|------|---------------|
| `prefersChart` must be `true` for charts | If `false` or omitted, Omni renders a table regardless of other viz settings |
| Spec lives in `visConfig.config` | The rendering spec must be in `visConfig.config` at the queryPresentation level — a bare top-level `config` is silently dropped |
| `chartType` set at the presentation level | The chart type enum value must be a queryPresentation-level `chartType` (not only `query.visConfig.chartType`) |
| `visType` must match chart category | `"omni-kpi"` for KPI, `"basic"` for cartesian/pie/heatmap/boxplot, `"funnel"`/`"sankey"`/`"map"` for those, `"omni-table"` for tables |
| `chartType` must be a valid enum value | e.g. `table`, `kpi`, `line`/`lineColor`, `column`/`columnStacked`, `bar`/`barStacked`, `area`/`areaStacked`, `point`/`pointColor`, `pie`, `heatmap`, `boxplot`, `funnel`, `sankey`, `map`, `regionMap`. **NOT** `barColor`/`areaColor`/`stackedBarColor`/`scatter` |
| `config` fields must match chart family | Cartesian (line/column/bar/area/point) require `mark`, `series`, `tooltip`, `behaviors`, `configType: "cartesian"`, `_dependentAxis`; pie uses `configType: "polar"`; heatmap `"heatmap"`; boxplot `"boxplot"`; funnel/sankey/map have no `configType` |
| `_dependentAxis` must match orientation | `"y"` for vertical charts (line, **column**, area, scatter), `"x"` for horizontal **bar** charts |
| `mark.type` must match the chart | `line`/`lineColor` → `"line"`; `column*`/`bar*` → `"bar"`; `area*` → `"area"`; `point*` → `"point"` |
| `series[].yAxis` or `series[].xAxis` | Use `yAxis: "y"` for vertical charts, `xAxis: "x"` for horizontal bars |
| Stack/group dimension is pivoted | The `color.field` used for stacking must also be in `query.pivots` |
| KPI tiles need `markdownConfig` | `visConfig.config.markdownConfig` array with at least one entry referencing a field from the query |
| `fields` must be duplicated | The `fields` array must appear at the `queryPresentation` level AND inside the `query` object |
| Every query must have a measure | Queries with only dimensions produce empty/broken tiles |

> **Tip**: When unsure about a viz config and the user did not explicitly require a chart type, default to `"prefersChart": false` with `"visConfig": { "config": {}, "visType": "omni-table", "fields": [...] }` to render as a table. If the user did request a chart, use the complete chart examples in the references. Always read the document back afterward (`omni unstable documents-export`) and confirm the persisted `visConfig.spec` is non-empty.

See [visConfig.md](visConfig.md) and [queryPresentations.md](queryPresentations.md) for the full config shapes by chart family.

## Step 4: Post-Creation Verification

After creating or updating a dashboard, always read it back and verify the tiles work:

**4a. Read back the document:**

```bash
omni documents get <documentIdentifier>
```

Check that:
- The response includes all expected `queryPresentations` (count matches what you sent)
- No `queryPresentations` entries have null or missing `query` objects
- The `identifier` is present (you'll need it for the share link)

**4b. Execute the dashboard's queries to verify they run:**

```bash
# Extract the queries powering the dashboard tiles
omni documents get-queries <documentIdentifier>
```

This returns the query objects for each tile. Run each one to confirm they execute without errors:

```bash
# For each query returned, execute it
omni query run --body '{
  "query": <query-object-from-get-queries>,
  "resultType": "csv"
}'
```

For every tile, print or record a concrete verification line with the tile name,
query status, and row count. Use `summary.row_count` when present, otherwise
use `cache_metadata.num_rows`. Do not leave post-build verification as silent
command output.

Using `"resultType": "csv"` makes it easy to spot-check that the data looks reasonable (correct columns, non-empty rows, expected value ranges).

**What to check:**
- Every tile's query executes without error
- `summary.row_count` > 0 for tiles that should show data
- No unexpected `remaining_job_ids` (which might indicate query timeout issues)

**4c. If any query fails:** The dashboard has a broken tile. Either update the document to fix the query (via `omni documents put <identifier>`) or flag the issue to the user before sharing the link. Do not enter an open-ended repair loop; after one failed corrected update attempt, report the blocker and stop.

## Validation Checklist Summary

| Phase | Check | Tool |
|-------|-------|------|
| Pre-build | Model has no errors | `omni models validate <modelId>` |
| Pre-build | Each query executes successfully | `omni query run` per query |
| Pre-build | Each query returns rows | Check `summary.row_count` |
| Pre-build | Filters parse correctly | Include filters in `omni query run` |
| Pre-build | Viz specs are internally consistent | Check against the rules above |
| Post-build | Document has all expected tiles | `omni documents get` and count `queryPresentations` |
| Post-build | All tile queries execute on the dashboard | `omni documents get-queries` + `omni query run` each |
| Post-build | Data looks correct | Spot-check CSV output for reasonableness |

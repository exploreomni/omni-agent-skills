# Validation & Testing

Every dashboard build or update must include validation before and after creation. Broken tiles, bad field references, and misconfigured viz specs are silent failures — the dashboard renders but tiles show "Chart unavailable" or "No data" with no API-level error. The v2 draft flow gives you a critical safety net: **nothing goes live until `v2-publish-draft`**, so validate the draft first — a bad draft is discarded with zero impact.

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

(Standalone `query run` bodies take a `modelId`; **tile** queries inside v2 documents must not — the server anchors tiles to the document's workbook model.)

**What to check in the response:**
- **No error field** — if the response contains an `error` key, the query is broken. Fix before proceeding.
- **`summary.row_count` > 0** — a query that returns zero rows will render as an empty tile. This may be correct (no data for the filter range) but is worth flagging.
- **Include your dashboard filters** — pass the same filters you plan to wire up as dashboard controls as query-level filters here. This catches bad filter expressions (e.g., wrong field name, unsupported syntax) before they become dashboard-level problems.
- **Long-running queries** — if the response includes `remaining_job_ids`, poll with `omni query wait --jobids <ids>` until complete, then check the final result for errors.

Do this for **every** query you plan to include as a tile. A dashboard with 5 tiles needs 5 validated queries.

> **`generate-query --run-query false` is NOT this step.** It only confirms Blobby can *propose* a query with those field names — it never executes the query **you authored**, so it cannot catch a mangled measure/calc (e.g. a measure stored as `sql: /` from an unquoted `${a}/${b}`, or a bare-`${}`-omitted field ref). Only `query run` executes your query and surfaces the warehouse compile error (`unexpected '/'`, `no such column`, …). Don't conflate "shape-checked" with "executed."
> **When you are instructed to explicitly not run queries against an instance**, you can't run Step 2. Substitute: (a) **read back the stored YAML** of any measure/dim whose `sql` contains `${}` — confirm the refs survived (`models validate` does **not** catch `${}` mangling); (b) `models validate`; (c) prototype the exact pattern on a query-allowed sandbox and port; (d) ask the owner to run one query. On a *query-allowed* sandbox, there is no excuse — run it.

**Then check the tile-query shape**: before a query goes into a patch body, confirm it carries the full required collection-field set — `table`, `fields`, `limit`, `join_paths_from_topic_name`, plus `sorts[]`, `filters{}`, `calculations[]`, `column_totals{}`, `row_totals{}`, `fill_fields[]`, `pivots[]`, `userEditedSQL` (empty values are fine) — and **no `modelId`**. Missing collection fields are a 400 with per-field errors.

## Step 3: Validate Viz Spec Consistency

Before assembling `queryPresentations`, check each tile's viz configuration against these rules. Mismatches cause "No chart available" or silent fallback to table rendering.

**Required consistency checks:**

| Rule | What to check |
|------|---------------|
| `prefersChart` must be `true` for charts | If `false` or omitted, Omni renders a table regardless of other viz settings |
| Spec lives in `visConfig.visConfig.config` on WRITE | The rendering spec must be nested under `config` inside the inner `visConfig` when you send it. **It reads back flat** (spec fields beside `visType`) — never round-trip the flat GET shape; a flat-sent spec is silently dropped |
| `chartType` and `fields` sit at the outer `visConfig` level | `visConfig: { chartType, fields, version, visConfig: {…} }` — not at the tile's top level |
| `visType` must match chart category | `"omni-kpi"` for KPI, `"basic"` for cartesian/pie/heatmap/boxplot, `"funnel"`/`"sankey"`/`"map"` for those, `"omni-table"` for tables |
| `chartType` must be a valid enum value | e.g. `table`, `kpi`, `line`/`lineColor`, `column`/`columnStacked`, `bar`/`barStacked`, `area`/`areaStacked`, `point`/`pointColor`, `pie`, `heatmap`, `boxplot`, `funnel`, `sankey`, `map`, `regionMap`. **NOT** `barColor`/`areaColor`/`stackedBarColor`/`scatter` |
| `config` fields must match chart family | Cartesian (line/column/bar/area/point) require `mark`, `series`, `tooltip`, `behaviors`, `configType: "cartesian"`, `_dependentAxis`; pie uses `configType: "polar"`; heatmap `"heatmap"`; boxplot `"boxplot"`; funnel/sankey/map have no `configType` |
| `_dependentAxis` must match orientation | `"y"` for vertical charts (line, **column**, area, scatter), `"x"` for horizontal **bar** charts |
| `mark.type` must match the chart | `line`/`lineColor` → `"line"`; `column*`/`bar*` → `"bar"`; `area*` → `"area"`; `point*` → `"point"` |
| `series[].yAxis` or `series[].xAxis` | Use `yAxis: "y"` for vertical charts, `xAxis: "x"` for horizontal bars |
| Stack/group dimension is pivoted | The `color.field` used for stacking must also be in `query.pivots` |
| KPI tiles need `markdownConfig` | `visConfig.visConfig.config.markdownConfig` array with at least one entry referencing a field from the query |
| `fields` live in `visConfig.fields` | v2 presentations have no top-level `fields` — the vis field list is `visConfig.fields`, alongside `query.fields` |
| Every query must have a measure | Queries with only dimensions produce empty/broken tiles |

> **Tip**: When unsure about a viz config and the user did not explicitly require a chart type, default to a table: `"prefersChart": false` with `"visConfig": { "chartType": "table", "fields": […], "version": 0, "visConfig": { "visType": "omni-table", "config": {} } }`. If the user did request a chart, use the complete chart examples in the references. Always read the draft back afterward (`v2-get-draft`) and confirm the persisted inner vis config is non-empty.

See [visConfig.md](visConfig.md) and [queryPresentations.md](queryPresentations.md) for the full config shapes by chart family.

## Step 4: Validate the Draft Before Publishing

This is the big v2 win: edits land on a draft, and nothing goes live until `v2-publish-draft`. Validate here — a bad draft is discarded via `omni documents discard-draft <identifier>` with zero impact on the published dashboard.

**4a. Read back the state:**

```bash
omni documents v2-get-draft <identifier> <draftIdentifier>   # draft state (identifier first, then draft id)
omni documents v2-get <identifier>                           # published state
```

Check that:
- **Tile count matches**: the length of `queryPresentations.order` AND the set of keys in `queryPresentations.data` both match what you expect — check both agree with each other.
- No `queryPresentations.data` entries have null or missing `query` objects.
- Each tile you wrote read back with a non-empty inner vis config (it reads back *flat* — that's expected; see Step 3).
- Every tile in `order` is referenced by a `containers` stack — stored-but-unplaced tiles render nowhere.

**4b. Execute the dashboard's queries to verify they run:**

```bash
# Extract the queries powering the dashboard tiles
omni documents get-queries <documentIdentifier>
```

Works on v2 documents; the returned queries include the workbook `modelId`, so they are directly runnable:

```bash
# For each query returned, execute it
omni query run --body '{
  "query": <query-object-from-get-queries>,
  "resultType": "csv"
}'
```

For tiles that exist only on the draft, take the query object from the `v2-get-draft` readback and run it with `modelId` set to the draft's `workbookModelId` (from `omni documents list-drafts <identifier>`).

For every tile, print or record a concrete verification line with the tile name,
query status, and row count. Use `summary.row_count` when present, otherwise
use `cache_metadata.num_rows`. Do not leave post-build verification as silent
command output.

Using `"resultType": "csv"` makes it easy to spot-check that the data looks reasonable (correct columns, non-empty rows, expected value ranges).

**What to check:**
- Every tile's query executes without error
- `summary.row_count` > 0 for tiles that should show data
- No unexpected `remaining_job_ids` (which might indicate query timeout issues)

**4c. If any query fails:** the draft has a broken tile. Fix it with one corrected `omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier>` at most; if that also fails, `omni documents discard-draft <identifier>` and report the blocker — the published dashboard was never touched. Do not enter an open-ended repair loop, and do not publish a draft with a known-broken tile.

**4d. Publish, then spot-check:** after `v2-publish-draft`, a final `omni documents v2-get <identifier>` confirms the published state matches the validated draft.

## Validation Checklist Summary

| Phase | Check | Tool |
|-------|-------|------|
| Pre-build | Model has no errors | `omni models validate <modelId>` |
| Pre-build | Each query executes successfully | `omni query run` per query |
| Pre-build | Each query returns rows | Check `summary.row_count` |
| Pre-build | Filters parse correctly | Include filters in `omni query run` |
| Pre-build | Tile queries carry all required collection fields, no `modelId` | Check against the Step 2 list |
| Pre-build | Viz specs are internally consistent | Check against the rules above |
| Pre-publish | Draft has all expected tiles | `v2-get-draft` — `order` length and `data` keys both match |
| Pre-publish | All tile queries execute | `omni documents get-queries` + `omni query run` each |
| Pre-publish | Data looks correct | Spot-check CSV output for reasonableness |
| Post-publish | Published state matches the draft | `omni documents v2-get <identifier>` |

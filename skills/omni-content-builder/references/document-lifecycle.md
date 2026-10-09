# Document Lifecycle

Creating, renaming, deleting, moving, and duplicating documents, and the end-to-end build workflows. Editing an existing dashboard goes through the draft flow in [updating-dashboards.md](updating-dashboards.md).

## Contents

- [Create Document (Name Only)](#create-document-name-only)
- [Create Document with Queries and Visualizations](#create-document-with-queries-and-visualizations)
- [Rename Document](#rename-document)
- [Delete Document](#delete-document)
- [Move Document](#move-document)
- [Duplicate Document](#duplicate-document)
- [Build Workflows](#build-workflows)

## Create Document (Name Only)

```bash
omni documents v2-create <model-id> "Q1 Revenue Report"
# optional flags: --identifier, --description, --folder-id
```

- `<model-id>` is the **shared** model; the server mints a per-document workbook model.
- The document is **created and published immediately**. The response returns only `{identifier, name, description}`; `omni documents v2-get <identifier>` then returns the envelope, including `workbookModelId`.
- `--folder-id` omitted → the document lands in the creator's personal "My documents" (requires personal-content permission). Pass a folder ID to place it in a shared folder.

## Create Document with Queries and Visualizations

Pass the full envelope via `--body`. Tiles are keyed — write tile `"1"` explicitly to replace the server's seed tile:

```bash
omni documents v2-create --body '{
  "modelId": "your-shared-model-id",
  "name": "Q1 Revenue Report",
  "queryPresentations": {
    "data": {
      "1": {
        "name": "Monthly Revenue Trend",
        "type": "query",
        "topicName": "order_items",
        "prefersChart": true,
        "automaticVis": false,
        "query": {
          "table": "order_items",
          "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
          "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
          "filters": {
            "order_items.created_at": {
              "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
              "left_side": "6 months ago", "right_side": "6 months"
            }
          },
          "limit": 100,
          "join_paths_from_topic_name": "order_items",
          "calculations": [], "column_totals": {}, "row_totals": {},
          "fill_fields": [], "pivots": [], "userEditedSQL": ""
        },
        "visConfig": {
          "chartType": "lineColor",
          "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
          "version": 0,
          "visConfig": {
            "visType": "basic",
            "config": {
              "x": { "field": { "name": "order_items.created_at[month]" } },
              "mark": { "type": "line" },
              "color": {},
              "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }],
              "tooltip": [
                { "field": { "name": "order_items.created_at[month]" } },
                { "field": { "name": "order_items.total_revenue" } }
              ],
              "configType": "cartesian",
              "_dependentAxis": "y"
            }
          }
        }
      }
    },
    "order": ["1"]
  }
}'
```

> **The rendering spec goes in `visConfig.visConfig.config`** (visType beside it, spec nested under `config`). `chartType` and `fields` sit at the outer `visConfig` level. See [references/queryPresentations.md](queryPresentations.md) and [references/visConfig.md](visConfig.md) for the structures and per-chart-type configs.

**Key points:**
- Tile keys are strings `"1"`, `"2"`, … and must appear in `order` to be tabs. A create with no `containers` auto-places every tile; send `containers` to set the layout yourself, and then reference every tile that should be visible ([references/containers.md](containers.md)).
- `prefersChart` must be `true` to render a chart; set `automaticVis: false` when you author an explicit vis config.
- The `query` needs the full collection-field set (see *Known Issues & Safe Defaults* in SKILL.md) and **no `modelId`**.
- `controls` and `settings` slices can be included in the same create body — see [controls.md](controls.md#filters-and-controls-in-a-create-body).

**To learn the exact structure for a chart type**, start from the recipes in [visConfig.md](visConfig.md). For a chart type with no recipe, find an existing dashboard that uses it (`omni documents list`, or the `omni-content-explorer` skill) and read it back with `omni documents v2-get <identifier>`; tiles come back in the shape you write, so they can be reused as is. If no dashboard uses it, ask the user for one.

## Rename Document

```bash
omni documents v2-patch-draft <identifier> --name "Q1 Revenue Report (Updated)" --summary "rename"
omni documents v2-publish-draft <identifier>
```

`--summary` is written to the document's history audit trail. (There is no `clearExistingDraft` in the v2 flow — if a draft already exists, patch it directly with `v2-patch-draft-by-identifier`, or discard it first.)

## Delete Document

```bash
omni documents delete <identifier>
```

Soft-deletes the document (moves to Trash).

## Move Document

```bash
omni documents move <identifier> "/Marketing/Reports" --scope organization
```

Use `"null"` as the folder path to move to root. `--scope` is optional — auto-computed from the destination folder.

## Duplicate Document

```bash
omni documents duplicate <identifier> "Copy of Q1 Revenue Report" --folder-path "/Marketing/Reports"
```

Only published documents can be duplicated. Draft documents return 404.

## Build Workflows

### API-First (Full Programmatic Creation)

1. **Discover fields** — use `omni-model-explorer` to find topic + fields
2. **Validate model** — run `omni models validate <modelId>` and check for errors
3. **Test each query** — run every query you plan to include via `omni query run` (using `omni-query`) before building the dashboard. Include the same filters you plan to use as controls to confirm they parse correctly. This catches field name typos, missing join paths, bad filter expressions, and permission errors before they become broken tiles.
4. **Validate viz specs** — check each tile's `chartType`/`visType`/inner `config`/`prefersChart` against the consistency rules before assembling the payload
5. **Create document** — single `omni documents v2-create` with `queryPresentations` + `controls` + `settings` in one body (add `containers` only to set the layout yourself)
6. **Verify the dashboard** — read it back with `omni documents v2-get`, confirm all tiles are present and placed, then run each tile's query via `omni documents get-queries` + `omni query run` to verify no broken tiles
7. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user (only after verification passes)

# Documents v2 API Reference

The `omni documents v2-*` commands are an **experimental** surface for building and editing documents with an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`. They give you direct control over layout and dashboard controls that the v1 (`documents create`/`put`) path does not.

> **Experimental.** These commands and their payload shapes can change. Prefer v1 (`documents create`/`put`, see [SKILL.md](../SKILL.md)) unless you specifically need programmatic control over containers (layout) or interactive controls (field/timeframe switchers). Always read your result back with `v2-get` and verify.

## Commands

| Command | Purpose |
|---|---|
| `v2-create` | Create + publish a document live |
| `v2-get <identifier>` | Read published document state |
| `v2-get-draft <draftIdentifier> <identifier>` | Read a draft's state |
| `v2-patch <identifier>` | One-shot: find-or-create a draft, apply, publish |
| `v2-patch-draft <identifier>` | Create a draft (optionally on a branch) and patch it |
| `v2-patch-draft-by-identifier <draftIdentifier> <identifier>` | Patch an existing draft |

## Envelope

```jsonc
{
  "modelId": "<SHARED model id>",          // create-only; server mints a per-doc workbook model
  "name": "…",
  "description": "…",
  "queryPresentations": {                   // the tiles (queries + their viz)
    "data": { "<tileKey>": { /* tile */ } },
    "order": ["1", "2", …]
  },
  "controls": {                             // dashboard filters + interactive controls
    "data": { "<controlId>": { "config": {…}, "map": {…} } },
    "order": ["…"]
  },
  "containers": [ /* layout tree — see containers.md */ ],
  "settings": { /* document settings */ }
}
```

### Patch is a diff

`v2-patch*` applies only the slices you send. To change one tile, send just `{"queryPresentations":{"data":{"3": <tile>}}}` — the rest is preserved. `containers`, however, is a **full replacement** of the layout tree (send the whole tree, with your edit applied).

### The server mints the workbook model

On create, the server creates a per-document **workbook** model and rewrites every tile's `query.modelId` to it. Read the document back to get the real ids; do not assume your input `modelId` survives on the tiles.

## Tile (queryPresentation) shape

```jsonc
{
  "name": "Metric 3",                       // authoring label; NOT shown via mustache (see below)
  "type": "query",
  "topicName": "orders",
  "prefersChart": true,
  "automaticVis": false,                    // see the warning below
  "query": { /* see required fields */ },
  "visConfig": { "chartType": "kpi", "fields": [...], "version": 0, "visConfig": { /* inner */ } },
  "resultConfig": { /* table display, conditional formatting */ },
  "subTitle": "…"
}
```

### Required query collection fields

A tile `query` **must include all of these or the request 400s** (empty values are fine):

```
modelId, table, fields, join_paths_from_topic_name, limit,
sorts[], filters{}, pivots[], calculations[],
column_totals{}, row_totals{}, fill_fields[], userEditedSQL
```

`join_paths_from_topic_name` is the **topic name** (e.g. `"orders"`), not the base view name.

## Three behaviors to design around

These are current, reproducible behaviors of the experimental surface. Code against them.

### 1. GET returns vis config flat; PATCH only persists it nested

A `v2-get` returns each tile's inner vis config **flattened** (the config fields sit next to `visType`). But a patch only persists vis config that is **nested under `config`**:

```jsonc
// what GET returns (flat):
"visConfig": { "visType": "omni-kpi", "markdownConfig": [...], "alignment": "left" }

// what you must SEND for it to persist:
"visConfig": { "visType": "omni-kpi", "config": { "markdownConfig": [...], "alignment": "left" } }
```

**Consequence:** echoing a tile straight from a GET back into a patch — even for an unrelated change like a **rename** — silently drops its vis config (KPI loses its number, a chart loses its `mark`/`series`, a markdown tile goes blank). **Always re-author the inner vis config nested under `config`; never round-trip a GET's flat shape back.**

### 2. An interactive control's per-tile `map` does not scope via the API

A **filter's** `map` works (e.g. `{ "<tileKey>": false }` excludes that tile). But an **interactive control's** `map` (a `FIELD_SELECTION` field/timeframe switcher) is currently a no-op through the API — the switcher applies to every tile that uses its field, and you cannot disconnect it programmatically. Scope interactive controls in the **UI Mapping panel** instead. (See [controls.md](controls.md).)

### 3. Auto-layout only places the seed tile

`v2-create` accepts N tiles but the auto-generated `containers` only places the first (seed) tile. Tiles 2…N are stored and queryable but render **nowhere**, with no warning. You must author the full `containers` tree yourself. (See [containers.md](containers.md).)

## Running queries to verify tiles

Verify each tile's query against the model before/after building:

```bash
omni query run --body '{"query": { … same query object … }}'   # NOTE: wrapped in {"query": …}
```

- The body must be wrapped in a top-level `query` object.
- `run` returns `{"jobs_submitted": {"<jobId>": "<clientId>"}}` — the query runs **async**.
- Poll with `omni query wait --jobids <jobId>`.
- The completed result's `result` field is **base64-encoded Arrow IPC** — decode with pyarrow (`pa.ipc.open_stream(io.BytesIO(base64.b64decode(result))).read_all()`).
- Branch-authored fields (measures added on a model branch) resolve against the **workbook model id**, not the shared model id — query with the tile's actual `query.modelId`.

## Branch-bound drafts

```bash
omni models create-branch <sharedModelId> --name <branch>
omni documents v2-patch-draft <identifier> --body '{ "branchId": "<branchId>", … }'   # creates the draft
omni documents v2-patch-draft-by-identifier <draftIdentifier> <identifier> --body '{ … }'  # update it
omni documents list-drafts <identifier>   # find the draft + its workbookModelId
```

The clone path correctly re-stamps each tile's `query.modelId` to the draft's new workbook model — **do not** hand-send a stale `modelId` from an earlier GET, or tiles point at a dead model and restricted viewers see "Invalid model". Let create/clone stamp it, or set it to the current draft `workbookModelId` from `list-drafts`.

### Draft conflicts: 405 and 409

`v2-patch` on a *published* doc transparently runs find-or-create-draft + publish. Two ways that bites:

- **409 "a draft already exists"** — a prior one-shot `v2-patch` can leave an orphan draft; the next `v2-patch` then 409s. Pass `options.clearExistingDraft: true` (nested under `options`, not top-level) to discard it — or patch the existing draft directly.
- **405 "Unexpected Server Error"** — if a **UI draft is open** on the doc (the editor shows "Draft / Publish / Leave draft" and the URL is a *draft* identifier, not the published one), `v2-patch` against the published id fails with 405. **Patch the draft you're in**: `v2-patch-draft-by-identifier <draftIdentifier> <identifier>`. Get the draft id from the URL or `list-drafts`.

## See also

- [containers.md](containers.md) — the layout tree (grid, tile stacks, groups, control placement)
- [controls.md](controls.md) — filters and interactive controls
- [visConfig.md](visConfig.md) — per-tile visualization config, incl. the markdown metric-switch pattern

# Documents v2 API Reference

The `omni documents v2-*` commands are the **primary** surface for creating and editing documents — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow. Lifecycle operations (list, delete, move, duplicate, discard-draft) and model writes stay on v1 commands — see the command boundary table in [SKILL.md](../SKILL.md). Always read your result back with `v2-get` / `v2-get-draft` and verify.

## Commands

| Command | Purpose |
|---|---|
| `v2-create` | Create + publish a document live |
| `v2-get <identifier>` | Read document state (draft state if a draft exists, else published) |
| `v2-get-draft <draftIdentifier> <identifier>` | Read a draft's state |
| `v2-patch-draft <identifier>` | Create a draft (optionally branch-bound) and apply a patch |
| `v2-patch-draft-by-identifier <draftIdentifier> <identifier>` | Patch an existing draft |
| `v2-publish-draft <identifier>` | Publish the document's **main** draft |

- Draft commands take the **draft identifier first**: `<draftIdentifier> <identifier>`.
- There is **no one-shot patch** — every edit is patch-draft → verify → publish-draft.
- Patch responses return `{identifier, name, description, draftIdentifier}` — capture `draftIdentifier` for `v2-get-draft`, `v2-patch-draft-by-identifier`, and the draft URL.

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

`v2-patch-draft*` applies only the slices you send, merging by key. To change one tile, send just `{"queryPresentations":{"data":{"3": <tile>}}}` — the rest is preserved. Also:

- Setting a key to `null` **deletes** it (e.g. `"data": {"2": null}` removes tile 2 — also drop it from `order`).
- `order` arrays are replaced **wholesale** — send the complete order.
- `containers` is a **full replacement** of the layout tree (send the whole tree, with your edit applied).
- A `queryPresentations` patch is capped at **48 entries**.

### The server anchors tiles to the workbook model

On create, the server mints a per-document **workbook** model extending the shared `modelId` you pass. Tile queries carry **no `modelId`** — reads never expose one, and a `modelId` or `model_extension_id` you send in a tile query is **silently rewritten** to the workbook model (verified live), so omit them. The workbook model id comes from v1 `documents get` (top-level `modelId`) — and it **rotates**: each draft clones the workbook model (extensions carried along), and publishing swaps the document to the clone, so the id changes after **every** publish. Never cache it; re-fetch after each publish.

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

Always send the full set (empty values are fine):

```
table, fields, join_paths_from_topic_name, limit,
sorts[], filters{}, pivots[], calculations[],
column_totals{}, row_totals{}, fill_fields[], userEditedSQL
```

All but `limit` and `join_paths_from_topic_name` are schema-required — omitting any of those returns a 400 listing each missing field (verified live). Send `limit` and `join_paths_from_topic_name` anyway: an unbounded query and broken topic joins are worse than a 400. `join_paths_from_topic_name` is the **topic name** (e.g. `"orders"`), not the base view name. Do **not** include `modelId` or `model_extension_id` (see above).

## Three behaviors to design around

These are reproducible behaviors, re-verified against the GA surface. Code against them.

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

A **filter's** `map` works — re-verified in GA (e.g. `{ "<tileKey>": false }` persisted and excluded that tile). But an **interactive control's** `map` (a `FIELD_SELECTION` field/timeframe switcher) is a no-op through the API — the switcher applies to every tile that uses its field, and you cannot disconnect it programmatically. Scope interactive controls in the **UI Mapping panel** instead. (See [controls.md](controls.md).)

### 3. Auto-layout only places the seed tile

`v2-create` accepts N tiles but the auto-generated `containers` only places the first (seed) tile. Tiles 2…N are stored and queryable but render **nowhere**, with no warning. You must author the full `containers` tree yourself. (See [containers.md](containers.md).)

Related: tile `"1"` in a create body **merges over the server's seed tile**, and some seed properties can win — verified: `automaticVis` flipped back to `true` on tile `"1"` while tile `"2"` kept `false`. If tile `"1"`'s exact fields matter, read the document back and re-patch it after create.

## Running queries to verify tiles

Verify each tile's query against the model before/after building:

```bash
omni query run --body '{"query": { … same query object … }}'   # NOTE: wrapped in {"query": …}
```

- The body must be wrapped in a top-level `query` object.
- `run` returns `{"jobs_submitted": {"<jobId>": "<clientId>"}}` — the query runs **async**.
- Poll with `omni query wait --jobids <jobId>`.
- The completed result's `result` field is **base64-encoded Arrow IPC** — decode with pyarrow (`pa.ipc.open_stream(io.BytesIO(base64.b64decode(result))).read_all()`).
- To verify a built document's tiles, `omni documents get-queries <identifier>` returns each tile's query **with the workbook `modelId` filled in** — directly runnable via `query run`. (Tile queries inside the v2 envelope carry no `modelId`; standalone `query run` bodies need one.)

## Branch-bound drafts

To bind a draft to a model branch, put `branchId` **in the `v2-patch-draft` body**. It cannot go via `--branch-id` when you also pass `--body` — the CLI silently ignores **all** shorthand flags whenever `--body` is present (verified in source and live). `--branch-id` alone (no body) works. Full flow, including publishing via branch merge: [branch-bound-drafts.md](branch-bound-drafts.md).

## Error map

| Error | Cause | What to do |
|---|---|---|
| 404 "Document draft does not exist" on `v2-publish-draft` | No **main** draft — also returned when only a **branch** draft exists (`v2-publish-draft` only sees the main draft; branch drafts publish via the branch merge) | Create a main draft first, or merge the branch |
| 422 "This document uses the classic dashboard layout, which the documents API does not support. Upgrade the dashboard to the advanced layout before editing it through the API." | Classic-layout dashboard — returned by **every** v2 endpoint | No API fallback — ask the user to upgrade the layout in the Omni UI, then retry |
| 400 "Unrecognized key: …" | Unknown top-level envelope key (e.g. v1 keys like `filterConfig`) | Use the v2 slice names |
| 400 with per-field query errors | Tile query missing required collection fields | Send the full set (above) |
| 404 not-found | Nonexistent document — also what `v2-patch-draft` returns if you pass a **draft** identifier (use `v2-patch-draft-by-identifier` for drafts) | Check which identifier you're holding |

Discarding: v1 `omni documents discard-draft <publishedIdentifier>` discards the **main** draft (404s if only a branch draft exists).

## See also

- [containers.md](containers.md) — the layout tree (grid, tile stacks, groups, control placement)
- [controls.md](controls.md) — filters and interactive controls
- [visConfig.md](visConfig.md) — per-tile visualization config, incl. the markdown metric-switch pattern
- [branch-bound-drafts.md](branch-bound-drafts.md) — drafts bound to a model branch

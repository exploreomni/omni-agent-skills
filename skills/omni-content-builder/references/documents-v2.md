# Documents v2 API Reference

The `omni documents v2-*` commands are the **only** surface for creating, reading, and editing documents — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow. Never fall back to the v1 `documents create`/`get`/`put`/`update` path. A few document-management operations (list, delete, move, duplicate, discard-draft, get-queries, downloads) have no v2 form and are the only command for that job — see the command list in [SKILL.md](../SKILL.md). Always read your result back with `v2-get` / `v2-get-draft` and verify.

## Commands

| Command | Purpose |
|---|---|
| `v2-create` | Create + publish a document live |
| `v2-get <identifier>` | Read document state (draft state if a draft exists, else published) |
| `v2-get-draft <identifier> <draftIdentifier>` | Read a draft's state |
| `v2-patch-draft <identifier>` | Create a draft (optionally branch-bound) and apply a patch |
| `v2-patch-draft-by-identifier <identifier> <draftIdentifier>` | Patch an existing draft |
| `v2-publish-draft <identifier>` | Publish the document's **main** draft |

- Draft commands take the **document identifier first, then the draft identifier**: `<identifier> <draftIdentifier>`.
- There is **no one-shot patch** — every edit is patch-draft → verify → publish-draft.
- Patch responses return `{identifier, name, description, draftIdentifier}` — capture `draftIdentifier` for `v2-get-draft`, `v2-patch-draft-by-identifier`, and the draft URL.

> **Which patch command:** use **`v2-patch-draft`** to *open* a draft (the first patch — it creates the draft and applies your changes); use **`v2-patch-draft-by-identifier`** for *every subsequent* patch to that same draft (pure apply, no new draft). Calling `v2-patch-draft` again creates *another* draft; passing a draft identifier to `v2-patch-draft` 404s.

## Envelope

The annotated shapes below exist for the **gotchas** — the field-level detail (every key, its type, which are required) is authoritative from the CLI itself: `omni documents v2-create --schema` (`--depth 1` for a top-level overview, `--field queryPresentations.data` to drill into a tile). When this doc and `--schema` disagree on a field, `--schema` wins; the prose here is for the behaviors `--schema` can't express.

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

### Pass the body as one JSON object — never stringify the slices

`--body` takes a **single JSON object**. `queryPresentations`, `controls`, and `settings` are **nested objects**, not JSON strings. Stringifying any slice yields `400 … expected object, received string`.

```bash
# CORRECT — slices are nested objects
omni documents v2-create <SHARED_MODEL_ID> "My Dashboard" --body '{
  "queryPresentations": { "data": { "1": { /* tile: query + viz */ } }, "order": ["1"] },
  "controls": { "data": {}, "order": [] },
  "settings": {}
}'

# WRONG — a slice passed as a stringified JSON (→ 400 "expected object, received string")
#   --body '{"queryPresentations":"{\"data\":{...}}"}'
```

For anything non-trivial, write the body to a file and pass `--body "$(cat body.json)"` — inline shell-escaping of nested JSON is the usual cause of this error.

### Patch is a diff

`v2-patch-draft*` applies only the slices you send, merging by key. To change one tile, send just `{"queryPresentations":{"data":{"3": <tile>}}}` — the rest is preserved. Also:

- Setting a key to `null` **deletes** it (e.g. `"data": {"2": null}` removes tile 2 — also drop it from `order`).
- `order` arrays are replaced **wholesale** — send the complete order.
- `containers` is a **full replacement** of the layout tree (send the whole tree, with your edit applied).
- A `queryPresentations` patch is capped at **48 entries**.

> **Send only the tiles you changed — not the whole document echoed back.** Beyond the flat-config round-trip drop, re-sending the *entire* `queryPresentations.data` (all tiles read from `v2-get`) can hard-`400` with `"queryPresentations: Invalid input: expected string, received undefined"` if **any** existing tile doesn't round-trip cleanly (e.g. a legacy/scratch tile whose read shape isn't write-valid). The misleading part: the error names the top-level slice, not the offending tile. Because patch merges by key, the fix is to send **only the new/edited tiles** in `data` (plus the full `order` and full `containers`) — untouched tiles are preserved and never re-validated.

### The server anchors tiles to the workbook model

On create, the server mints a per-document **workbook** model extending the shared `modelId` you pass. Tile queries carry **no `modelId`** — reads never expose one, and a `modelId` or `model_extension_id` you send in a tile query is **silently rewritten** to the workbook model, so omit them. When you need the workbook model id (to write model YAML), read it from the draft's `workbookModelId` via `documents list-drafts` — and it **rotates**: each draft clones the workbook model (extensions carried along), and publishing swaps the document to the clone, so the id changes after **every** publish. Never cache it; read it fresh from `list-drafts` each time.

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

All but `limit` and `join_paths_from_topic_name` are schema-required — omitting any of those returns a 400 listing each missing field. Send `limit` and `join_paths_from_topic_name` anyway: an unbounded query and broken topic joins are worse than a 400. `join_paths_from_topic_name` is the **topic name** (e.g. `"orders"`), not the base view name. Do **not** include `modelId` or `model_extension_id` (see above).

## Behaviors to design around

These are reproducible behaviors — code against them.

### 1. GET returns vis config flat; PATCH only persists it nested

A `v2-get` returns each tile's inner vis config **flattened** (the config fields sit next to `visType`). But a patch only persists vis config that is **nested under `config`**:

```jsonc
// what GET returns (flat):
"visConfig": { "visType": "omni-kpi", "markdownConfig": [...], "alignment": "left" }

// what you must SEND for it to persist:
"visConfig": { "visType": "omni-kpi", "config": { "markdownConfig": [...], "alignment": "left" } }
```

**Consequence:** echoing a tile straight from a GET back into a patch — even for an unrelated change like a **rename** — silently drops its vis config (KPI loses its number, a chart loses its `mark`/`series`, a markdown tile goes blank). **Always re-author the inner vis config nested under `config`; never round-trip a GET's flat shape back.**

### 2. Per-tile `map` scopes both filters and interactive controls

A `map` exclusion (`{ "<tileKey>": false }`) or remap (`{ "<tileKey>": "<field>" }`) is honored for **both** a filter and an interactive `FIELD_SELECTION` switcher — the switcher stops rewriting (or remaps) the excluded tile, just like a filter. (See [controls.md](controls.md).)

### 3. Auto-layout only places the seed tile

`v2-create` accepts N tiles but the auto-generated `containers` only places the first (seed) tile. Tiles 2…N are stored and queryable but render **nowhere**, with no warning. You must author the full `containers` tree yourself. (See [containers.md](containers.md).)

Related: tile `"1"` in a create body **merges over the server's seed tile**, and some seed properties can win: `automaticVis` flipped back to `true` on tile `"1"` while tile `"2"` kept `false`. If tile `"1"`'s exact fields matter, read the document back and re-patch it after create.

### 4. `query.filters` needs the object form, not the shorthand string

A tile `query.filters` value must be a **filter object**, not the relative-date shorthand. Sending `{ "ecomm__order_items.created_at": "last 6 months" }` throws a 500 (`Cannot use 'in' operator to search for 'query_id' in last 6 months` — the value is parsed as a filter object and the string fails). Use the object form:

```jsonc
"filters": {
  "ecomm__order_items.created_at": {
    "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
    "left_side": "6 months ago", "right_side": "6 months"
  }
}
```

(String/number: `{ "kind": "EQUALS", "type": "string", "values": ["…"] }`.)

### 5. Inline tile filters get auto-materialized into dashboard controls

When a tile's `query.filters` carries a filter, the resolver **materializes it into a dashboard filter control** (a new `controls.data` entry with a generated id) and auto-places it in the tile, scoped to that tile via `map`. This is expected — it's how an inline tile filter becomes a real, adjustable control. Don't be surprised by extra control ids appearing in a read-back after you patch a tile that has inline filters.

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
| 400 "queryPresentations/controls/settings: expected object, received string" | A slice was passed as stringified JSON inside `--body` | Send one JSON object with nested objects; don't stringify slices (above) |
| 400 with per-field query errors | Tile query missing required collection fields | Send the full set (above) |
| 404 not-found | Nonexistent document — also what `v2-patch-draft` returns if you pass a **draft** identifier (use `v2-patch-draft-by-identifier` for drafts) | Check which identifier you're holding |

Discarding: v1 `omni documents discard-draft <publishedIdentifier>` discards the **main** draft (404s if only a branch draft exists).

## See also

- [containers.md](containers.md) — the layout tree (grid, tile stacks, groups, control placement)
- [controls.md](controls.md) — filters and interactive controls
- [visConfig.md](visConfig.md) — per-tile visualization config
- [markdown-tiles.md](markdown-tiles.md) — markdown-tile recipes (sizing, responsive fonts, metric-switch, funnel)
- [branch-bound-drafts.md](branch-bound-drafts.md) — drafts bound to a model branch

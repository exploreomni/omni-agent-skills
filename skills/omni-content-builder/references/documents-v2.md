# Documents v2 API Reference

The `omni documents v2-*` commands are the **only** surface for creating, reading, and editing documents — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow. Never fall back to the v1 `documents create`/`get` path (v1 `put`/`update` were removed in CLI 1.2.2). A few document-management operations (list, delete, move, duplicate, discard-draft, get-queries, downloads) have no v2 form and are the only command for that job — see the command list in [SKILL.md](../SKILL.md). Always read your result back with `v2-get` / `v2-get-draft` and verify.

## Contents

- [Commands](#commands)
- [Envelope](#envelope)
- [Tile (queryPresentation) shape](#tile-querypresentation-shape)
- [Apps (alpha, CLI ≥ 1.4.0)](#apps-alpha-cli--140)
- [Behaviors to design around](#behaviors-to-design-around)
- [Running queries to verify tiles](#running-queries-to-verify-tiles)
- [Branch-bound drafts](#branch-bound-drafts)
- [Error map](#error-map)
- [See also](#see-also)

## Commands

| Command | Purpose |
|---|---|
| `v2-create` | Create + publish a document live |
| `v2-get <identifier>` | Read the **published** state, without draft edits. To read a draft, use `v2-get-draft` or pass the draft's own identifier |
| `v2-get-draft <identifier> <draftIdentifier>` | Read a draft's state |
| `v2-patch-draft <identifier>` | Create a draft (optionally branch-bound) and apply a patch |
| `v2-patch-draft-by-identifier <identifier> <draftIdentifier>` | Patch an existing draft |
| `v2-publish-draft <identifier>` | Publish the document's **main** draft |
| `v2-bind-query-model <identifier> <draftIdentifier> <queryKey>` | Bind a tile to a query model on a draft (CLI ≥ 1.1.2) |
| `v2-unbind-query-model <identifier> <draftIdentifier> <queryKey>` | Unbind a tile from its query model, keeping its query (CLI ≥ 1.1.2) |
| `v2-update-identifier <identifier>` | Rename a published document's identifier (slug); body `{"identifier": "new-slug"}` |

- Draft commands take the **document identifier first, then the draft identifier**: `<identifier> <draftIdentifier>`.
- There is **no one-shot patch** — every edit is patch-draft → verify → publish-draft.
- `v2-get` also accepts a **draft's own identifier**. The response then carries `draftOf`, naming the published document the draft belongs to — the way to build the `<identifier> <draftIdentifier>` argument pair when all you were handed is a draft.
- Patch responses return `{identifier, name, description, draftIdentifier}` — capture `draftIdentifier` for `v2-get-draft`, `v2-patch-draft-by-identifier`, and the draft URL.

> **Which patch command:** use **`v2-patch-draft`** to *open* a draft (the first patch — it creates the draft and applies your changes); use **`v2-patch-draft-by-identifier`** for *every subsequent* patch to that same draft (pure apply, no new draft). Calling `v2-patch-draft` again creates *another* draft; passing a draft identifier to `v2-patch-draft` 404s.

## Envelope

The annotated shapes below show behaviors that `--schema` can't. For field-level detail (every key, its type, which are required), run `omni documents v2-create --schema` (`--depth 1` for a top-level overview, `--field queryPresentations.data` for a tile). `--schema` reflects the **installed CLI release**, so keep the CLI current. When this doc and `--schema` disagree on a field, treat it as a version difference and confirm with a live write and a read-back.

```jsonc
{
  "modelId": "<SHARED model id>",          // required on create; returned on GET; can't be changed
  "workbookModelId": "<per-doc model id>",  // GET only, read-only; per draft — never cache it
  "draftOf": { "identifier": "…" },         // GET of a draft's own identifier only; read-only
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
- `containers` is a **full replacement** of the layout tree (send the whole tree, with your edit applied). Omit it to keep the current layout and let the server auto-place any tiles you add (behavior 3 below).
- A `queryPresentations` patch is capped at **48 entries**.

> **Send only the tiles you changed.** A full GET body is accepted as a PATCH, but every tile you send is validated again and counts against the 48-entry cap. Because a patch merges by key, send only the new or edited tiles in `data`, plus the full `order`, and `containers` only when you change the layout. Tiles you leave out are kept.

### The server anchors tiles to the workbook model

On create, the server mints a per-document **workbook** model extending the shared `modelId` you pass. Tile queries carry **no `modelId`** — reads never expose one, and a `modelId` or `model_extension_id` you send in a tile query is **rewritten** to the workbook model with no warning, so omit them. The workbook model id is returned as `workbookModelId` by `v2-get` (the published document's), by `v2-get-draft` (that draft's), and by `documents list-drafts`. It **changes**: each draft copies the workbook model (extensions included), and publishing switches the document to that copy, so the id is different after **every** publish. Don't cache it; read it each time. Reads include `modelId` and `workbookModelId` so that a GET body can be sent back as a PATCH: the same values change nothing, and a different value is rejected. `draftOf` works the same way; naming a different document returns 409.

Since the binding is server-owned on the PATCH surface, changing a tile's query-model binding goes through the dedicated draft-scoped commands (CLI ≥ 1.1.2): `v2-bind-query-model <identifier> <draftIdentifier> <queryKey>` (body carries the `queryModelId` — see `--schema`) and `v2-unbind-query-model` (no body; keeps the tile's query). The `queryModelId` must be a live query model layered on this draft's workbook model and not already bound to another tile — a query model is dedicated to a single query. A LINKED tile inherits its query model from its source and can't be bound directly. Because each draft re-clones its query models, bind against a draft you have already read.

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

## Apps (alpha, CLI ≥ 1.4.0)

An **app** is HTML content in place of a dashboard. A document carries at most one of a dashboard or an app — never both; workbook-only is valid. The HTML and its `settings` live only at the app commands below; `v2-get` carries an `app` slice that points here and accepts it back only as it was read.

| Command | Purpose |
|---|---|
| `get-app <identifier>` | Read the published HTML + `settings` |
| `get-draft-app <identifier> <draftIdentifier>` | Read a named draft's app |
| `get-main-draft-app <identifier>` | Read the main draft's app (404 if there is no main draft) |
| `put-app <identifier> <draftIdentifier>` | Replace the HTML on a draft, creating the app if the draft is workbook-only |
| `patch-app <identifier> <draftIdentifier>` | Apply `htmlEdits` (substring search/replace) without resending the HTML |
| `remove-app <identifier> <draftIdentifier>` | Drop the app, leaving a workbook-only document |
| `put-app-auto-draft` / `patch-app-auto-draft` `<identifier>` | The same two writes, creating-or-reusing the main draft in one call |

- Create an app document with `omni documents v2-create <SHARED_MODEL_ID> "My App" --body '{"app": {"html": "…"}}'` — `model-id` and `name` are still required, and the `app` slice is mutually exclusive with `containers`, `controls`, and `settings`. Creation is gated on the org app toggle, and a user-scoped key needs the role's `allowCreateApps` on the model (or on its parent SHARED model) — otherwise a bare 403.
- Writes are draft-only and never auto-publish. `v2-publish-draft` publishes the **main** draft only, so an app written to a branch-bound draft goes live through the branch merge instead (see [branch-bound-drafts.md](branch-bound-drafts.md)).
- `PUT` creates the app; `PATCH` never does. The two PATCH variants differ on what they check: `patch-app` 409s against a draft with no app, while `patch-app-auto-draft` 409s when the **document has no published app** — so the create-then-edit-before-first-publish path must use `patch-app`, not the auto-draft form.
- `PUT` is last-write-wins with no version precondition. `PATCH`'s `htmlEdits` are all-or-nothing and content-addressed: an edit matching zero times, or more than once without `replaceAll`, rejects the whole request. That catches a **stale read**, not a concurrent writer — serialize writes to one app when it matters.
- **Writes never reject on host policy.** An external `<script src>` / `<link rel="stylesheet">` host outside the org's app policy comes back as a non-blocking `warnings` entry on an otherwise-200 response, and the render-time CSP leaves it inert until an admin allows the host — so a CDN-loading app can "succeed" and render blank. The same array warns when `settings.allowDefaultMapProviders` is on but the org's app policy turns map providers off: the setting saves, and no map tile loads until an admin turns providers back on. Read `warnings` before reporting success.
- HTML is capped at **2 MiB** on write; apps saved before the cap can read back larger and then fail on the way back in.
- A dashboard document can't become an app in place — drop the dashboard first (`v2-remove-dashboard <identifier> <draftIdentifier>`), since a draft carrying a dashboard can never carry an app. Also avoid naming a draft `app`: the route ranks that literal above `{draftIdentifier}`, making the draft unaddressable on these commands.
- The command names lost their `v2-` prefix in CLI 1.4.0 (the paths and payloads did not change). On 1.2.2–1.3.1 the same eight commands are spelled `documents v2-get-app`, `v2-put-app`, and so on.
- Alpha — the app sub-resource may change shape without a deprecation cycle. Run `--help` / `--schema` on the command before your first write.

## Behaviors to design around

These are reproducible behaviors — code against them.

### 1. The inner vis config has one shape on read and write

`v2-get` and `v2-get-draft` return each tile's inner vis config as `{ "visType": …, "config": { …spec } }`, the same shape you write, so a tile read back can be edited and patched back as is, including for renames, restores, and duplicates:

```jsonc
"visConfig": { "visType": "omni-kpi", "config": { "markdownConfig": [...], "alignment": "left" } }
```

A spec sent **flat** beside `visType` (the shape older reads returned) is also accepted and moved under `config` on write. Write it nested, and read the tile back afterwards to confirm `visConfig.visConfig.config` is non-empty.

### 2. Per-tile `map` scopes both filters and interactive controls

A `map` exclusion (`{ "<tileKey>": false }`) or remap (`{ "<tileKey>": "<field>" }`) is honored for **both** a filter and an interactive `FIELD_SELECTION` switcher — the switcher stops rewriting (or remaps) the excluded tile, just like a filter. (See [controls.md](controls.md).)

### 3. New tiles are auto-placed unless you send `containers`

`v2-create`, and every patch that carries **no `containers`**, auto-places each new dashboard-eligible tile on the first page (csv / dataset / query-view / dbt tabs are stored but not placed). Containers created this way are removed when their tile is deleted. When you send `containers`, it fully defines the layout and nothing is auto-placed — tiles it doesn't reference are stored but render nowhere. On a workbook-only document (no layout yet) tiles are stored without placement. (See [containers.md](containers.md).)

Related: tile `"1"` in a create body **is merged into the server's seed tile**, which keeps `automaticVis: true` even when you send `false`; tiles `"2"` onward keep `false`. If tile `"1"`'s `automaticVis` matters, patch it again on a draft after create.

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

### 5. A control is hidden by leaving it unplaced

A filter or control is shown only where a container places it (the filter bar, a page, a tile). To hide one, leave it out of every container; it keeps applying its value. (See [controls.md](controls.md).)

## Running queries to verify tiles

Verify each tile's query against the model before/after building:

```bash
omni query run --body '{"query": { … same query object … }}'   # NOTE: wrapped in {"query": …}
```

- The body must be wrapped in a top-level `query` object.
- `run` returns `{"jobs_submitted": {"<jobId>": "<clientId>"}}` — the query runs **async**.
- Poll with `omni query wait --job-ids <jobId>`.
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
| 400 "controls.data[…].config carries `hidden` … not supported" | `hidden` sent on a filter/control config | Remove the key; place or unplace the control via `containers` |
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

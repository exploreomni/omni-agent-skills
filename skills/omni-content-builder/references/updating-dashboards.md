# Updating an Existing Dashboard

Edits go through the **v2 draft flow**: read the published state, author a merge-by-key patch, apply it to a draft, validate the draft, publish. The published dashboard is untouched until `v2-publish-draft` — a bad draft is discarded with zero impact.

> **Advanced layout only.** Classic-layout dashboards return **422** from the v2 endpoints: *"This document uses the classic dashboard layout, which the documents API does not support. Upgrade the dashboard to the advanced layout before editing it through the API."* There is no API fallback — ask the user to upgrade the layout in the Omni UI, then retry.

## The five-step loop

**Step 1 — Read** the current state:

```bash
omni documents v2-get <identifier> > doc.json
```

Returns the envelope: `name`, `description`, `queryPresentations {data, order}`, `controls {data, order}`, `containers`, `settings`. The response carries no `identifier`/`modelId` — keep the identifier you queried with. If a draft already exists, `v2-get` returns the draft state.

**Step 2 — Author the patch.** Patches **merge by key** (semantics below) — send only what you're changing. Include a `summary` string in the body; it is written to the document's history audit trail.

**Step 3 — Create the draft and apply it**:

```bash
omni documents v2-patch-draft <identifier> --body - < patch.json
# → {identifier, name, description, draftIdentifier}
```

Capture `draftIdentifier` from the response.

**Step 4 — Validate the draft** before anything goes live (see [validation-and-testing.md](validation-and-testing.md)):

```bash
omni documents v2-get-draft <identifier> <draftIdentifier>          # identifier first, then draft id
```

Check tile counts (`queryPresentations.order` vs `data` keys), viz specs, and run the affected queries. Iterate with:

```bash
omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body '…'   # identifier first, then draft id
```

**Step 5 — Publish**:

```bash
omni documents v2-publish-draft <identifier>
```

Publishes the **main** draft only. Publishing swaps the document to the draft's workbook model — the workbook model id changes; if you need it afterwards, open a new draft and read `workbookModelId` from `omni documents list-drafts <identifier>`.

## Merge-by-key semantics

- `queryPresentations.data` and `controls.data` merge **by key**: keys you send are written, keys you omit are preserved, a key set to `null` is deleted.
- The `order` arrays are **full replacements** — always send the complete ordered list.
- `containers` is a **full replacement** of the layout tree — send the whole tree with your edit applied.
- `settings` is shallow-merged — send only the keys you're changing.
- A single patch's `queryPresentations` is capped at **48 entries** — split larger edits across multiple patches to the same draft.

## Recipes

All go in a `v2-patch-draft` (or `…-by-identifier`) body, alongside a `summary`.

**Add a tile** — new key in `data`, append to `order`, add a tile stack to `containers` (full tree):

```json
{
  "summary": "add revenue KPI",
  "queryPresentations": {
    "data": { "5": { /* full tile — see queryPresentations.md */ } },
    "order": ["1", "2", "3", "4", "5"]
  },
  "containers": [ /* existing tree + a stack referencing tile 5 — see containers.md */ ]
}
```

**Edit a tile** — send only that key, but send the **complete tile** with its inner vis config **re-authored nested under `config`**. Never echo the flat shape `v2-get` returned — a flat-sent vis config is silently dropped (only `visType` survives):

```json
{
  "summary": "switch trend tile to area",
  "queryPresentations": { "data": { "2": {
    "name": "Revenue Trend", "type": "query", "topicName": "order_items",
    "prefersChart": true, "automaticVis": false,
    "query": { /* full query incl. every collection field — see below */ },
    "visConfig": { "chartType": "area", "fields": ["…"], "version": 0,
      "visConfig": { "visType": "basic", "config": { /* re-authored spec */ } } }
  } } }
}
```

**Delete a tile** — set its key to `null`, remove it from `order`, remove its stack from `containers`:

```json
{
  "summary": "remove tile 2",
  "queryPresentations": { "data": { "2": null }, "order": ["1", "3"] },
  "containers": [ /* full tree without tile 2's stack */ ]
}
```

**Rename a tab** — a tab is a tile; its label is the tile's `name`. Even for a rename, send the complete tile with the inner vis config re-nested under `config` — echoing the flat GET shape drops the vis config.

**Reorder tabs** — send the full `order` array; it replaces wholesale: `{"queryPresentations": {"order": ["3", "1", "2"]}}`. Verify by readback.

**Patch one control** — `{"controls": {"data": {"date_filter": {"config": {…}, "map": {…}}}}}` — merges by key like tiles; include `order` only when adding/removing controls.

**Patch one setting** — `{"settings": {"refreshInterval": 300}}` — shallow merge; other settings untouched.

**Metadata-only edits** — shorthand flags work *when there is no `--body`*:

```bash
omni documents v2-patch-draft <identifier> --name "New Name" --summary "rename"
```

## The `--body` vs flags gotcha

When `--body` is present, the CLI **silently ignores every shorthand flag** (`--name`, `--summary`, `--branch-id`, …) — verified in the CLI source (the body short-circuits before flag assembly) and live. With `--body`, put everything in the JSON. Flags-only (no `--body`) works for metadata edits.

## Errors

| Status | Trigger | Notes |
|---|---|---|
| 400 | Unrecognized top-level key | clean per-key message, e.g. `"Unrecognized key: filterConfig"` |
| 400 | Tile query missing collection fields | per-field errors; `sorts`, `filters`, `calculations`, `column_totals`, `row_totals`, `fill_fields`, `pivots`, `userEditedSQL` are required (empty values fine) alongside `table` and `fields` — and always send `limit` and `join_paths_from_topic_name` too |
| 404 | Nonexistent document | |
| 404 | `v2-publish-draft` with no **main** draft | `"Document draft does not exist"` — including when only a *branch-bound* draft exists ([branch-bound-drafts.md](branch-bound-drafts.md)) |
| 404 | Patching a draft identifier as if it were published | plain not-found |
| 422 | Classic dashboard layout | exact message above; no API fallback — upgrade in the UI |

## Failure handling

Edits live on a draft, so rollback is trivial — the published document is never touched:

```bash
omni documents discard-draft <identifier>     # targets the MAIN draft
```

- If a patch fails validation, make **one corrected retry at most**, then discard the draft and report the exact error and what was preserved (everything — the published doc is unchanged).
- Do not probe with repeated filter syntaxes, and do not fall back to `omni unstable documents-import` — import creates a *new* document.
- Broken query-level filters: validate the unfiltered base query once; if a dashboard-level control can satisfy the request, use that instead and verify by readback; never persist a filter that fails `omni query run` parsing.

## See also

- [documents-v2.md](documents-v2.md) — envelope, tile shape, the flat-read/nested-write vis-config gotcha
- [containers.md](containers.md) — authoring the layout tree
- [validation-and-testing.md](validation-and-testing.md) — validating the draft before publishing
- [branch-bound-drafts.md](branch-bound-drafts.md) — drafts bound to a model branch

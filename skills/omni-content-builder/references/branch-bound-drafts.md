# Branch-Bound Document Drafts

How to build a dashboard tile whose query references a field that is **not in the published shared model** — a field that lives only on a model **branch** that hasn't merged yet. These tiles ride on a document **draft bound to the branch**.

> **When you need this:** if the field already exists in the published shared model, you don't need any of this — use the normal draft flow ([updating-dashboards.md](updating-dashboards.md)). A field that lives only in the document's **workbook model** needs a draft but not a branch (see [Workbook-model fields on a draft](#workbook-model-fields-on-a-draft)). You only need branch binding when the field exists *only on a branch*.

## v2 removed the old `modelId` gotcha

The v1 problem — `documents create` stamping the shared model onto every tile's `query.modelId`, producing a spurious restricted-querier *"Invalid model"* warning on drafts that had to be fixed by re-`put`ting with the workbook model id — is **gone in the v2 path**. v2 tile queries carry **no `modelId` at all** (`modelId`/`model_extension_id` are not in the tile-query schema); the server anchors every tile to the draft's workbook model. There is nothing to stamp and nothing to fix.

## Creating a branch-bound draft

Two commands:

```bash
# 1) create the model branch (or reuse an existing one)
omni models create-branch <sharedModelId> --name <branch>
#    → response is the branch model; its model.id is the branchId

# 2) open a draft bound to the branch, applying the tile patch in the same call
omni documents v2-patch-draft <identifier> --body '{
  "branchId": "<branch model id>",
  "summary": "add branch-field tile",
  "queryPresentations": { "data": { "4": { /* tile using the branch-only field */ } }, "order": ["…"] },
  "containers": [ /* full layout tree */ ]
}'
# → response includes draftIdentifier
```

> **CRITICAL: `branchId` must go INSIDE the body.** When `--body` is present, the CLI silently drops `--branch-id` and every other shorthand flag (verified in the CLI source and live). `--branch-id` alone — flags-only, no `--body` — does work.

### Verify the binding — always

```bash
omni documents list-drafts <identifier>
# each draft: {identifier, publishedIdentifier, branch: {id, name}, workbookModelId, draftOutOfDate, status, …}
```

- A bound draft shows `branch: {id, name}`; an unbound draft shows `branch: null`.
- **Check this immediately after creating the draft.** A draft that failed to bind is a silently-**mainline** draft — publishing it would publish to main with the branch fields unresolvable. This exact mistake happened in live testing when `--branch-id` was combined with `--body`.

`list-drafts` is keyed off the **published** document, so it's also your lookup for the draft's `identifier` and `workbookModelId`.

## Iterating on the draft

Same as any draft — document identifier first, then draft id:

```bash
omni documents v2-get-draft <identifier> <draftIdentifier>
omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body '{ … }'
```

The draft's workbook model extends the **branch** model, so branch-only fields resolve on the draft's tiles with no per-tile model wiring. To verify a branch field runs, take the tile's query and run it via `omni query run` with `modelId` set to the draft's `workbookModelId` (from `list-drafts`) — branch-authored fields resolve against the workbook model, not the shared model.

## Publishing: branch drafts can't be CLI-published

- `omni documents v2-publish-draft <identifier>` only sees the **main** draft. When only a branch-bound draft exists, it returns **404 "Document draft does not exist"**.
- A branch-bound draft goes live by **merging the model branch** (so the field lands in the shared model) and publishing the draft — that merge + publish close-out happens in the Omni UI. The CLI builds and verifies the draft; it cannot finish the job.
- `omni documents discard-draft <identifier>` likewise targets the **main** draft and 404s when only a branch draft exists. Deleting the model branch does **not** auto-discard the branch draft (verified). The CLI has no verified way to discard a branch-bound draft — abandon it in the UI.

### Tell the creator it's a branch-bound draft

A branch-bound draft is **not a live, published dashboard** — it exists only as a draft tied to its branch. When you hand one back, say so explicitly — don't present it as a finished dashboard. State plainly:

- that the result is a **draft**, and the link points to the draft (not a published dashboard);
- the **branch it depends on**, and that the tile relies on a field that isn't in the published shared model yet;
- that it **publishes only when that branch is merged** and the draft is published in the UI — until then, others (especially Viewers/Restricted Queriers) won't see it as a normal dashboard.

This sets expectations and names the one action that finishes the job (merge + publish), which the CLI can't do.

## Workbook-model fields on a draft

> The general flow — `omni models yaml-create <workbookModelId>` with `"mode": "extension"`, YAML body with no `views:` wrapper — lives in *Updating a Dashboard's Model* in SKILL.md. This section covers what changes on a draft.

**Each draft has its own cloned workbook model**, with a different id from the published doc's. Get it straight from `list-drafts` (`workbookModelId` on the draft record). Then:

```bash
# 1) write the field into the DRAFT's workbook model
omni models yaml-create <draftWorkbookModelId> --body '{
  "fileName": "<view>.view", "yaml": "…", "mode": "extension"
}'

# 2) patch the tile referencing the field into the draft (no modelId in the tile query)
omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body '{ … }'
```

When the draft is also branch-bound, its workbook model extends the branch — one model resolves branch-only fields **and** workbook fields together, even in the same tile.

**Workbook-model rotation:** every draft → publish cycle **mints a new workbook model id**. Extensions written to a draft's workbook model are carried into the published doc and later drafts, but a given draft's model is a different id — never cache one across a publish. Read it fresh from `list-drafts` (the draft's `workbookModelId`) each time. **Within a single *unpublished* draft the id is stable, though**: repeated `v2-patch-draft-by-identifier` edits keep the same `workbookModelId`, and re-invoking `v2-patch-draft` reuses the open draft rather than minting a second clone — so the write-field-then-patch-tile sequence above is safe. Rotation happens **only at the publish boundary**.

> These recipes wire the field into the right model; the tile still needs a valid `visConfig` to render. A query that runs cleanly via `query run` can still show "No chart available" if the viz spec is off. See [validation-and-testing.md](validation-and-testing.md).

## Table calculations ride along

Running totals, moving averages, etc. work on these tiles unchanged — they compute on the result set, independent of branch/model wiring. Put the calc in `query.calculations[]` and list its `calc_name` in `query.fields` and `visConfig.fields`.

A calc entry is `{ "calc_name": "<name>", "sql_expression": <AST> }`, where the AST is a nested `{ "type": "call", "operator": "Omni.<FN>", "operands": [...] }` tree — **not** a workbook-style `{name, formula}` string. A running total of `order_items.count`, for example, wraps the field in `Omni.OMNI_FX_SUM(Omni.OMNI_OFFSET_MULTI(...))`. The full operator catalog and AST shapes are owned by the **`omni-query`** skill — consult it for anything beyond a simple running total. 

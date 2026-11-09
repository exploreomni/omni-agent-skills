# Branch-Bound Document Drafts

How to build a dashboard tile whose query references a field that is **not in the published shared model** — a field that lives only on a model **branch** that hasn't merged yet. These tiles ride on a document **draft bound to the branch**.

> **When you need this:** if the field already exists in the published shared model, you don't need any of this — use the normal draft flow ([updating-dashboards.md](updating-dashboards.md)). A field that lives only in the document's **workbook model** needs a draft but not a branch (see [Workbook-model fields on a draft](#workbook-model-fields-on-a-draft)). You only need branch binding when the field exists *only on a branch*.

## v2 removed the old `modelId` gotcha

The v1 problem — `documents create` stamping the shared model onto every tile's `query.modelId`, producing a spurious restricted-querier *"Invalid model"* warning on drafts that had to be fixed by re-`put`ting with the workbook model id — is **gone in the v2 path**. v2 tile queries carry **no `modelId`**, and `model_extension_id` is server-owned (ignored on write); the server anchors every tile to the draft's workbook model. There is nothing to stamp and nothing to fix.

## Creating a branch-bound draft

Two commands:

```bash
# 1) create the model branch. Reuse an existing branch instead when the model change this draft depends on is already on it.
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

> **Put `branchId` inside the body.** The CLI rejects `--branch-id` combined with `--body`; `--branch-id` works only when there is no `--body`. `branchId` is accepted only by `v2-patch-draft`, the call that creates the draft. `v2-patch-draft-by-identifier` rejects it, so a draft's branch is fixed when the draft is created.

### Verify the binding — always

```bash
omni documents list-drafts <identifier>
# each draft: {identifier, publishedIdentifier, branch: {id, name}, workbookModelId, draftOutOfDate, status, …}
```

- A bound draft shows `branch: {id, name}`; an unbound draft shows `branch: null`.
- **Check this immediately after creating the draft.** A draft that failed to bind is a silently-**mainline** draft — publishing it would publish to main with the branch fields unresolvable.

`list-drafts` is keyed off the **published** document, so it's also your lookup for the draft's `identifier` and `workbookModelId`.

## Iterating on the draft

Same as any draft — document identifier first, then draft id:

```bash
omni documents v2-get-draft <identifier> <draftIdentifier>
omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body '{ … }'
```

The draft's workbook model extends the **branch** model, so branch-only fields resolve on the draft's tiles with no per-tile model wiring. To verify a branch field runs, take the tile's query and run it via `omni query run` with `modelId` set to the draft's `workbookModelId` (from `list-drafts`) — branch-authored fields resolve against the workbook model, not the shared model.

## Publishing: branch drafts publish with the branch merge

- `omni documents v2-publish-draft <identifier>` only sees the **main** draft. When only a branch-bound draft exists, it returns **404 "Document draft does not exist"**.
- A branch-bound draft goes live by **merging the model branch**: `omni models merge-branch` publishes the branch's drafts by default (body `publish_drafts`, see `--schema`) and reports `published_drafts_count` / `failed_drafts_count`. Check both. Merging is a separate decision the user confirms (see `omni-model-builder`).
- `omni documents discard-draft <identifier>` likewise targets the **main** draft and 404s when only a branch draft exists. Deleting the model branch does **not** auto-discard the branch draft (verified). The CLI has no verified way to discard a branch-bound draft — abandon it in the UI.

### Tell the creator it's a branch-bound draft

A branch-bound draft is **not a live, published dashboard** — it exists only as a draft tied to its branch. When you hand one back, say so explicitly — don't present it as a finished dashboard. State plainly:

- that the result is a **draft**, and the link points to the draft (not a published dashboard);
- the **branch it depends on**, and that the tile relies on a field that isn't in the published shared model yet;
- that it **publishes only when that branch is merged** — until then, others (especially Viewers/Restricted Queriers) won't see it as a normal dashboard.

This sets expectations and names the one action that finishes the job: merging the branch.

## Workbook-model fields on a draft

> The general flow — `omni models yaml-create <workbookModelId>` with the whole file as read with `--mode combined`, `"mode": "combined"`, and no `views:` wrapper — is in [workbook-model.md](workbook-model.md). This section covers what changes on a draft.

**Each draft has its own copy of the workbook model**, with a different id from the published document's. Read it from the draft's record in `list-drafts` (`workbookModelId`); that call needs only the published document's identifier and also shows each draft's branch. A `v2-get-draft` response carries the same field. Then:

```bash
# 1) write the field into the DRAFT's workbook model
omni models yaml-create <draftWorkbookModelId> --body '{
  "fileName": "<view>.view", "yaml": "<whole file>", "mode": "combined"
}'

# 2) patch the tile referencing the field into the draft (no modelId in the tile query)
omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body '{ … }'
```

When the draft is also branch-bound, its workbook model extends the branch — one model resolves branch-only fields **and** workbook fields together, even in the same tile.

**Workbook-model rotation:** every draft → publish cycle **mints a new workbook model id**. Extensions written to a draft's workbook model are carried into the published doc and later drafts, but a given draft's model is a different id — never cache one across a publish. Read it fresh from `list-drafts` (the draft's `workbookModelId`) each time. **Within a single *unpublished* draft the id is stable, though**: repeated `v2-patch-draft-by-identifier` edits keep the same `workbookModelId` (a second `v2-patch-draft` on the same branch is a 409, not a new clone) — so the write-field-then-patch-tile sequence above is safe. Rotation happens **only at the publish boundary**.

> These recipes wire the field into the right model; the tile still needs a valid `visConfig` to render. A query that runs cleanly via `query run` can still show "No chart available" if the viz spec is off. See [validation-and-testing.md](validation-and-testing.md).

## Table calculations ride along

Running totals, moving averages, etc. work on these tiles unchanged — they compute on the result set, independent of branch/model wiring. Put the calc in `query.calculations[]` and list its `calc_name` in `query.fields` and `visConfig.fields`. Calc shapes (`sql_expression` AST, or a lone `original_formula` the server parses) are owned by **`omni-query`** → `references/table-calculations.md`.

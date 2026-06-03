# Branch-Bound Document Drafts

How to build a dashboard tile whose query references a field that is **not in the published shared model** — either a field that lives only on a model **branch** that hasn't merged yet, or a field you added to the document's **workbook model**. These tiles need a branch-attached **draft**, plus one non-obvious `modelId` fix, or restricted-role users see a spurious "Invalid model" warning.

> **When you need this:** the field already exists in the published shared model → you don't need any of this; build the tile normally (see the main SKILL.md). You only need a branch-bound draft when the field exists *only* on a branch or *only* in the workbook model.

## The core gotcha: `create` stamps the base model on every tile query

- A document has its own **workbook model**, which *extends* the shared model. `omni documents get` returns it as the top-level `modelId`.
- **`omni documents create` (including create-with-`queryPresentations`) stamps each tile's `query.modelId` with the shared/base model you passed at the document level — not the workbook model it just created server-side.** The UI itself resolves the workbook model correctly, so the tile still renders for an admin.
- The cost shows up on **drafts**: the restricted-querier visibility check runs only for drafts and flags every tile — even shared-field ones — with:

  > *Users with Viewer or Restricted Querier access will not see this chart: Invalid model*

  This is a restricted-role **visibility warning**, not a broken tile — an admin still sees the chart. But it's noise, and it hides genuine visibility problems.
- **Fix:** set each tile's `query.modelId` to the document's **workbook model** (the top-level `modelId` from `omni documents get`). Same draft, `modelId` = shared → warning; `modelId` = workbook model → clean.
- **Why you can't fix it in one shot:** the workbook model doesn't exist until `create` runs server-side, so a one-shot `create`-with-the-tile always stamps the shared model. `omni documents put` *is* caller-fixable — you pass the workbook-model id as the top-level `modelId` and on each tile's `query.modelId`. So the pattern is always **create (or create-draft) first, then `put` with the right `modelId`**.

## Validated recipes

### 1. New doc, all queries use shared-model fields
No draft needed. A single `omni documents create` (`modelId` = shared model) with the tiles inline. Shared fields → no warning.

### 2. New doc whose tile uses an only-on-branch field (genesis)
The field doesn't exist in the published shared model yet, so you must provision a workbook model and bind the draft to the branch:

```bash
# a) empty create — provisions the workbook model
omni documents create --body '{ "modelId": "<sharedModelId>", "name": "..." }'

# b) open a branch-bound draft off the published shell
omni documents create-draft <documentId> --body '{ "branchId": "<branchId>" }'

# c) read the DRAFT to get its workbook model id
omni documents get <draftId>
#    → top-level "modelId" = the draft's workbook model

# d) put the tile into the draft, stamping the workbook model
omni documents put <draftId> --body '{
  "modelId": "<draftWorkbookModelId>",
  "branchId": "<branchId>",
  "name": "...",
  "queryPresentations": [ { "query": { "modelId": "<draftWorkbookModelId>", ... } } ]
}'
```

Result: a warning-free draft carrying the branch-only field.

### 3. Existing published doc (no branch dependency) + a new branch-field tile
Keep the published doc clean; carry the branch tile only on a draft:

```bash
omni documents create-draft <documentId> --body '{ "branchId": "<branchId>" }'
omni documents get <draftId>          # → draft workbook model id
omni documents put <draftId> --body '{
  "modelId": "<draftWorkbookModelId>",
  "branchId": "<branchId>",
  "queryPresentations": [ <existing tiles...>, <new branch-field tile> ]
}'
```

The published document stays warning-free; the draft carries the new tile.

### Lifecycle: review → merge → publish
Once the draft looks right, **merge the model branch** (so the field lands in the shared model) and **publish the draft**. The field is now in the shared model and the published document picks up the tile — at which point it no longer needs to be a branch-bound draft at all.

> **Publishing is a UI/workflow action — there is no CLI publish-draft command** (`documents` exposes `create-draft` and `discard-draft`, not publish). The CLI steps above build and verify the draft; the merge + publish close-out happens in the Omni UI.

### Tell the creator it's a branch-bound draft

A branch-bound draft is **not a live, published dashboard** — it exists only as a draft tied to its branch, and it goes live when that branch is merged and the draft is published (a UI step). When you hand one back, say so explicitly — don't present it as a finished dashboard. State plainly:

- that the result is a **draft**, and the link points to the draft (not a published dashboard);
- the **branch it depends on**, and that the tile relies on a field that isn't in the published shared model yet;
- that it **publishes only when that branch is merged** (and the draft is published in the UI) — until then, others (especially Viewers/Restricted Queriers) won't see it as a normal dashboard.

This sets the creator's expectations and tells them the one action that finishes the job (merge + publish), which the CLI can't do for them.

## Workbook-model fields on a draft

> The general rules for a workbook-model field — the workbook model is created by `documents create`, you add the field with `yaml-create … mode: extension`, and the **tile's `query.modelId` must be that workbook model or the query fails outright** — live in *Updating a Dashboard's Model* in SKILL.md. This section covers only what changes when the tile is on a **draft**.

The wrinkle: **a draft has its own workbook model**, with a different id than the published doc's. Write the field into the model the *draft's* tiles point at — the **draft's** workbook model. Get the draft's identifier from the **`create-draft` response** and its workbook model from the **top-level `modelId` of `documents get <draftId>`** — no `list-drafts` needed (that's a review/enumeration tool, covered below, and ships only in newer CLI builds).

**A draft's workbook model extends its branch.** When the draft is bound to a branch (`create-draft --body '{"branchId":"<branch>"}'`), its workbook model extends the *branch* model — so a single `query.modelId` = the draft's workbook model resolves branch-only fields **and** workbook-model fields together, even both in the same tile. You don't need (or get) separate models for the two.

### Recipes

**Branch field *and* workbook field (new doc).**
1. empty `documents create` → published shell.
2. `documents create-draft <id> --body '{"branchId":"<branch>"}'` → response returns the draft `identifier`.
3. `documents get <draftId>` → top-level `modelId` = the **draft's** workbook model.
4. `yaml-create <draftWorkbookModelId>` `mode: extension` → write the workbook field into the **draft's** workbook model.
5. `documents put <draftId>` — top-level `modelId` and **every tile's `query.modelId`** = the draft workbook model, `branchId` set. The branch-field tile and the workbook-field tile both use that one model.

**Existing published (non-branch) doc + a new tile using a branch field and a workbook field.**
Same as above, starting from the existing published doc. In the `put`, switch the existing tiles' `query.modelId` to the draft workbook model too (so the draft has no shared-stamped tiles to flag), and add the new tile — which can reference the branch field and the workbook field **in the same tile**.

> These recipes wire the field into the right model; the tile still needs a valid `visConfig` to render. A query that runs cleanly via `query run` can still show "No chart available" if the viz spec is off (e.g. `chartType: "table"` requires `visType: "omni-table"`). See [validation-and-testing.md](validation-and-testing.md).

Running totals and other calculations ride along exactly as in the shared-field case.

## Branch / draft mechanics

- `branchId` on `create` / `put` / `create-draft` associates the document with a model branch. It is stored on the **draft record**, not the published shell — `omni documents get` and `omni unstable documents-export` do **not** surface it.
- `omni documents create` **always publishes** (`isDraft: false`, `publishedAt` set), even when you pass `branchId`. There is no one-shot "unpublished draft" via the API; a never-published draft-only document comes only from the UI "new doc on a branch" flow.
- `omni documents create-draft` **requires a published base**: it returns `400 "Document is not eligible for publishing workflow"` on a draft-only doc, and `404` on a missing id.

## Reviewing drafts: `list-drafts`

```bash
omni documents list-drafts <publishedIdentifier>
```

Returns an array of drafts, each with `branch {id,name}`, the draft `identifier`, `publishedIdentifier`, `workbookModelId`, `draftOutOfDate`, and `status`. It's keyed off the **published** document, so a never-published draft-only doc returns `404 "Published document … does not exist"` — itself a reliable "no published version" signal.

## Table calculations ride along

Running totals, moving averages, etc. work on these tiles unchanged — they compute on the result set, independent of the `modelId` fix. Put the calc in `calculations[]` and list its `calc_name` in both `query.fields` and the queryPresentation `fields`. See the calculation shape in the `omni-query` skill.

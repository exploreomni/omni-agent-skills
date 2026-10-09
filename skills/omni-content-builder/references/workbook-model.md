# Adding Fields to a Dashboard's Workbook Model

Each document has a **workbook model** that extends the shared model. This reference covers where a new field belongs, how to write it to the workbook model, and how to build a tile on it.

> **First decide where a new field belongs.** Don't default to the lowest-friction path — choose the field's right home, gated by what your access actually allows.
>
> **Step 0 — check your access.** Run `omni whoami whoami --model-id <sharedModelId>` and read `rolesByModel[<id>].permissions`:
> - **`QUERY_FULL_MODEL` present** (Querier / Modeler / Admin) → you can create a branch → **prefer a shared-model branch** for anything reusable. If **`UPDATE`** is *also* present (Modeler / Admin) you can merge it yourself (with the creator's OK); if it's absent (Querier), open the branch and **request a merge** — a Querier can branch and modify but not promote.
> - **`QUERY_FULL_MODEL` absent but you can still create content** (Restricted Querier — has **`USE_WORKBOOKS`**) → you can't branch → use the **workbook model** (extension); the write is authorized against the shared model's permissions, which is exactly the restricted-but-workbook-capable case. (A **Viewer** lacks `USE_WORKBOOKS` and can't author a dashboard at all, so they never reach this decision — content creation presupposes `USE_WORKBOOKS`.) **Scope ceiling for a Restricted Querier:** their workbook-model writes are limited to **`.view` extensions** (new dimensions/measures on an existing view) + **decoration edits** — *not* `.topic` (topics/joins), the `model`/`relationships` files, or **access grants** (those need `QUERY_FULL_MODEL` on a branch). Keep the build **view-scoped**; planning a topic/join/grant change for a restricted querier 403s mid-build and can strand the doc. (Canonical: `omni-admin` → *Model Roles & Caller Access*.)
>
> The permission→capability map behind these signals (and why a shared-model-scoped `whoami` doesn't list branch ability as its own entry) is the canonical access check in **`omni-admin` → Model Roles & Caller Access** — this skill just applies it. In short: `QUERY_FULL_MODEL` = the proxy for "can branch"; `UPDATE` = "can merge/promote to shared."
>
> Then place the field. In order:
> 1. **Can it be a calculation?** A table calculation is scoped to a **single query/tile** (computed on the result set). Prefer one for logic local to one query — but lean to a model field (→ #2/#3) when (a) the **query shape rules a calc out**, or (b) you're building **multiple queries at once** and the same logic spans them and can be expressed as a dimension/measure. **Window-shaped logic** (running total, moving average, % change) should almost always stay a calc — it runs post-query on the result set, not in-warehouse; only reach for an in-warehouse field when the window must span rows *outside* the result set. (See `omni-query`'s table-calculation guidance.)
> 2. **Reusable elsewhere *and* you can branch (`QUERY_FULL_MODEL`)?** Add it to a **branch on the shared model** and follow **`omni-model-builder`** to create, validate, and ship it — merge it yourself only if you have `UPDATE`, otherwise open a PR / request a merge.
> 3. **One-off for this dashboard (and not a calculation) — *or* reusable but you can't branch (no `QUERY_FULL_MODEL`)?** Add it to the **workbook model** — see [Building a tile that queries a workbook-model field](#building-a-tile-that-queries-a-workbook-model-field) below.
> 4. **Unsure** (or reusable + can-branch, but the creator may not want a shared-model change)? Ask the creator where the field should live.
> 5. **Never write to the schema model** — it's auto-generated and read-only.
>
> **If the field isn't in the *published* shared model yet** — it lives only on a model **branch** that hasn't merged — put the tile on a **branch-bound draft**. See **[references/branch-bound-drafts.md](branch-bound-drafts.md)**.

Push custom dimensions and measures to a specific dashboard by writing to its workbook model. Each workbook has its own model that **extends** the shared model — so the ID you write YAML to is a model ID, not a separate "workbook ID". Because every edit goes through a draft, and the field has to exist before a tile can reference it, the whole flow stays in the v2 draft path:

**Step 1 — open a draft and read its workbook model ID:**

```bash
omni documents v2-patch-draft <identifier> --summary "add workbook field"   # creates the draft
omni documents list-drafts <identifier>
# use the draft record's "workbookModelId" (also on v2-get-draft); write the YAML to that model
```

> **Note**: The workbook model (which extends the shared model) is what you pass to `omni models yaml-create`. Each draft has its **own** clone of it, and the ID **changes on every draft → publish cycle** — always read it fresh from `list-drafts`; never reuse a cached value.

**Step 2 — POST YAML to the draft's workbook model with `mode: "extension"`:**

```bash
omni models yaml-create <draftWorkbookModelId> --body '{
  "fileName": "order_items.view",
  "yaml": "dimensions:\n  is_high_value:\n    sql: \"${sale_price} > 100\"\n    label: High Value Order\nmeasures:\n  high_value_count:\n    sql: \"${order_items.id}\"\n    aggregate_type: count_distinct\n    label: High Value Orders",
  "mode": "extension"
}'
```

> **Critical**: Always pass `"mode": "extension"` when editing an existing view in a workbook model. The default is `"combined"`, which treats your YAML body as the *complete* view definition and marks every field you didn't include as `ignored: true` — silently breaking queries that depend on fields from the shared base view. Extension mode layers your new dimensions and measures on top of the inherited view.

`fileName` must be `"model"`, `"relationships"`, or end with `.view` or `.topic`. The `yaml` value is a YAML string (not a JSON object) containing the view's *contents* — no `views:` wrapper. Writing to a workbook model skips git sync entirely — authorization is still checked against the underlying shared model's permissions.

> **The YAML you write here is ordinary model YAML — don't improvise it.** For the exact shape of dimensions, measures (incl. **filtered measures** like a count over a boolean flag), aggregate types, formats, and topics, follow **`omni-model-builder`** → `references/modelParameters.md`, and for filter conditions `references/yaml-filter-syntax.md`. A filtered measure's `filters:` value is always an **operator object** (`{ is: true }`, `{ greater_than: 100 }`), never a bare scalar — `is_flag: true` and `status: "complete"` are rejected as invalid filter specs.

## Building a tile that *queries* a workbook-model field

v2 tile queries carry **no `modelId`** — the server anchors each tile to the draft's workbook model, so the field just has to exist in that model before the tile references it. The order is fixed:

1. **`documents v2-create`** — provisions the workbook model. Skip this step when the document already exists; its workbook model is already there.
2. **`documents v2-patch-draft <identifier>`** — open the draft (a `--summary`-only patch is enough to create it).
3. **`documents list-drafts <identifier>`** → the draft's `workbookModelId`.
4. **`models yaml-create <draftWorkbookModelId>` with `mode: "extension"`** → add the field (above).
5. **`documents v2-patch-draft-by-identifier <identifier> <draftIdentifier>`** adding the tile that references the field — no `modelId` anywhere in the tile query.
6. **`documents v2-publish-draft <identifier>`** — the field and tile go live together.

After publishing, the workbook model ID has **changed** — open a new draft and re-read `workbookModelId` from `list-drafts` before any further `yaml-create`.

## Verify the Extension Worked

After writing, confirm the base view's fields are still available by querying one against the draft's workbook model:

```bash
omni query run --body '{
  "query": {
    "modelId": "<draftWorkbookModelId>",
    "table": "order_items",
    "fields": ["order_items.id", "order_items.high_value_count"],
    "limit": 1,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

(Standalone `query run` bodies still take a `modelId` — only **tile** queries inside v2 documents omit it.) If the response errors on a field that exists in the shared model (e.g. `order_items.id`), your write likely used combined mode and ignored the inherited fields. Re-run Step 2 with `"mode": "extension"`.

# Editing existing model files

The rule is in `SKILL.md` Step 1: read the whole file with `--mode combined`, change it, write the whole file back with `"mode": "combined"`, and read it back both ways. This page has the detail and the exceptions.

## Why the whole file, in combined mode

**⚠️ Editing an existing file: read the whole file with `--mode combined`, change it, and write the whole file back with `"mode": "combined"`.** `yaml-create` **replaces** the layer's copy of the file (no field-by-field merge), and Omni stores only what differs from the layers below it. This is how the IDE saves. It works on a shared model, a branch, a shared extension, and a workbook model, for changed, added and removed fields, and it is the only mode in which leaving a field out of the file removes it.

- **Send the whole file.** A partial file in `combined` mode marks every field you left out `ignored: true`. In `extension` mode a partial file replaces the layer's copy, so earlier changes in that file are lost, and an inherited field you leave out is kept, not removed.
- **Read it back both ways:** `--mode extension` for what the layer stores (only your change), `--mode combined` for what the model resolves to.

## File names

`fileName` is the file's **exact path** (not a regex, unlike on read) — reuse the full-path key verbatim, folder prefix included (e.g. `MARTS/fct_ai_events.view`); a non-matching name doesn't error, it **silently creates a duplicate** at that path (`success: true`). (Schema base columns live in the schema layer, so they're unaffected.) To inspect a branch's files: [model-layers.md](references/model-layers.md#inspecting-a-branch).

## Exceptions

- **Inherited `sql:` query views:** in an extension, workbook, or branch, when the view's SQL returns a column the view doesn't declare as a dimension, or you remove one of its dimensions, a write can store a full copy of the parent's `sql:` in the layer, and that layer stops picking up later changes to the parent's SQL. Prefer declaring a dimension for every column in the parent. Otherwise write that file with `"mode": "extension"` (still the whole file as read with `--mode combined`) for changes and additions, and don't remove its dimensions in the child. A view-level `sql:` in `--mode extension` that you didn't write is such a copy: report it rather than editing around it.
- **`relationships`:** when the connection has dbt-generated relationships, any write to the file also stores them in the layer, without their dbt provenance comments. Expect them on read-back; sending empty `yaml` with `"mode": "extension"` removes the layer's copy.
- **`extends`** (in the model file, a view, a field, or a topic's inline views): `--mode combined` shows a file's own content and the schema, not what `extends` brings in. Read it and write the whole file back with `"mode": "combined"`, as above; that stores only your change and keeps following the extended definitions. To see what `extends` brings in, read with `--mode fully-resolved`, and if you write that content back, send `"fullyResolved": true` with it: `combined` mode keeps anything you send that the extended definition already provides, as an override in this layer, and only the flag drops it. The flag isn't accepted yet for files with field-level `extends` or `extends` on a topic's inline views, or to change a view's own `extends:` line; edit those from the combined read. Never mix the two: fully-resolved content sent without the flag copies the inherited definitions into the layer (including a query view's `query:` or `sql:`), and the flag sent with content read in combined mode damages the file.
- **Don't write with `"mode": "merged"`.** Published models refuse it; on branches it can store schema-layer properties (`table_name`, base columns, dbt descriptions) in the branch.
- **New file:** send it as written, in either mode. A view the schema already generates is not new: read and edit it as above.
- **Delete a file:** send empty `yaml` with `"mode": "extension"`. In `combined` mode an empty file hides the inherited file instead.

**Declare a dimension for every column a `sql:` query view's SQL returns.** When a column is left undeclared, edits to the view in an extension, workbook, or branch can store a copy of the parent's `sql:`, and that layer stops picking up later changes to the SQL (see Step 1). This applies to CTEs that end in `SELECT *` too. For a `query:` view, changing dimensions in a child layer stores only the change; changing the `query:` block itself (its `fields`, `base_view` or `topic`) stores the whole block in that layer, which then stops following the parent's query.

## Hub-and-spoke setups

**Hub-and-spoke setups (shared extensions, models that `extends` another): write to the shared model ID you were given.** Whether it's the hub, a shared extension, or a model that extends another, that model (through a branch of it) is where the change goes. Don't move a change to the hub or to another extension because it seems to belong there; say so if it does, and still write where you were pointed unless told otherwise.

## Branches of a shared extension

**Branches of a shared extension.** An extension either shares its base shared model's branches or has isolated branches of its own (set when it was created; no read endpoint returns the setting). Find out which before you write:
- `omni models list --base-model-id <extensionId> --model-kind BRANCH` lists the extension's own branches. If any come back, it has **isolated branches**: use the extension's ID with one of those branch IDs. (`--include activeBranches` on the extension doesn't list them.)
- If none come back, list the base shared model's branches the same way (`--base-model-id <sharedModelId>`). With **shared branches** the extension has no branch of its own: use the extension's ID with the shared model's branch ID, and Omni stores the change for the extension on that branch.
- `omni models create-branch <extensionId>` also tells you: the new branch's `baseModelId` is the extension (isolated) or the shared model (shared).
- Read back with the same pair: `omni models yaml-get <extensionId> --branch-id <branchId>`. Reading the shared model with that branch ID doesn't show the extension's changes. A branch ID that doesn't belong to the extension this way fails with a 404 (`Branch does not exist`).

## Field, view and topic commands

- **Don't make model edits with the field, view and topic commands — use `yaml-create`.** (`create-field`, `update-field`, `update-view`, `update-topic`, `models update`). Each takes only some properties, and several cases return `success: true` without making the change: a key the command doesn't apply is dropped (for example `aggregateType` on `update-field`, or anything but `name` on `models update`), `update-view` drops `aiContext`, and a rename with `newFieldName` leaves the original field in place.

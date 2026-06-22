# Content Validator: Propagating Renames Across Saved Content

Renaming or removing a view, field, or topic in the model **does not** update the dashboards and workbooks that reference it — those saved queries keep pointing at the old name and silently break. The content validator is the tool that (a) finds every piece of saved content referencing a model object, and (b) bulk-rewrites those references to the new name.

Two operations, both under `omni models`:

| Command | Direction | Purpose |
|---------|-----------|---------|
| `content-validator-get` | read | Detect broken references / blast radius. Returns the documents that reference a target view/field/topic, plus any validation issues. |
| `content-validator-replace` | write | Find-and-replace a reference across all in-scope content. |

> **Detect first.** `content-validator-get` is also surfaced by `omni-model-explorer` for impact analysis. Always run it to preview the blast radius **before** replacing.

## Safety — read before replacing

- **Prefer a branch.** With `branch_id`, replacements are written as branch-attached **drafts** and only published when the branch merges — fully reversible by not merging. Without a branch, the replace mutates **published** content directly.
- **There is no undo.** A main-branch (no `branch_id`) replace cannot be rolled back in-product. Recovery means running the reverse replace by hand. Confirm with the user before any non-branch replace.
- **Always `content-validator-get` first**, report the blast radius, and get confirmation before the write.
- Documents requiring a pull request to publish are skipped on a non-branch replace (reported in `skipped_pr_required_count`).

## Detect: `content-validator-get`

```bash
omni models content-validator-get <modelId> --branch-id <branchId>
```

Verify flags with `omni models content-validator-get --help`. Scope filters:

| Flag | Meaning |
|------|---------|
| `--branch-id` | Validate against a branch (draft + published merged). |
| `--content-filter-mode` | `ALL` (default) \| `WITH_ISSUES` (only docs with a query/filter issue or document error) \| `NO_ISSUES`. |
| `--find` + `--find-type` | Scope to content referencing one object. `--find-type` is `VIEW`, `FIELD`, or `TOPIC`; both flags must be supplied together. `FIELD` values must be `view_name.field_name`. |
| `--folder-paths` | Prefix-match folders, e.g. `/Finance` matches `/Finance/Reports`. |
| `--labels` | Comma-separated label names (unknown label → 400). |
| `--include-personal-folders` | Include users' personal folders. |
| `--userid` | Act on behalf of a membership (org-scoped API keys only). |

An empty `content` array means no saved content references the target — i.e. no breakage.

## Propagate: `content-validator-replace`

The replace operation takes a **JSON `--body`** (not per-field flags). Verify with `omni models content-validator-replace --help`.

```bash
omni models content-validator-replace <modelId> --body '{
  "find": "order_items.sale_price",
  "replacement": "order_items.unit_price",
  "find_or_replace_type": "FIELD",
  "branch_id": "<branchId>"
}'
```

Body fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `find` | string | ✅ | What to find. For `FIELD`, must be `view.field` dotted notation. |
| `replacement` | string | ✅ | The new value. For `FIELD`, also `view.field`. |
| `find_or_replace_type` | `FIELD` \| `VIEW` \| `TOPIC` | ✅ | `VIEW` renames a view ref; `FIELD` a `view.field` ref; `TOPIC` a topic ref. |
| `branch_id` | string | – | **Strongly recommended** — writes drafts, published at merge. Omit only for an irreversible direct-to-published replace. |
| `creator_id` | string (UUID) | – | Limit to documents created by this membership (unknown → 400). |
| `folder_paths` | string **array** | – | Limit to these folder prefixes. Note: native JSON array here (the GET REST endpoint takes a URL-encoded string instead). |
| `include_personal_folders` | boolean | – | Default `false`. |
| `labels` | string (comma-separated) | – | Limit to documents carrying any of these labels. |
| `only_in_workbook_id` | string | – | Replace within a single workbook only. |

The response reports counts: `replaced_queries_count`, `replaced_documents_count`, `replaced_workbook_models_count`, `replaced_dashboard_filters_count`, `skipped_pr_required_count`.

**Validation:** `FIELD` requires a `.` in **both** `find` and `replacement`. Unknown `creator_id` / `labels` return 400.

## Workflow: rename a model field and propagate it

1. **Branch + rename in the model.** Create a branch and make the rename in YAML (see the main skill's Safe Development Workflow), then `omni models validate`.
2. **Detect.** `content-validator-get <modelId> --branch-id <branchId> --find order_items.sale_price --find-type FIELD` — report which documents reference the old field.
3. **Propagate on the branch.** `content-validator-replace <modelId> --body '{"find":"order_items.sale_price","replacement":"order_items.unit_price","find_or_replace_type":"FIELD","branch_id":"<branchId>"}'`.
4. **Confirm.** Report the replace counts and ask before shipping. Ship the branch the usual way (`omni models commit` for git-connected, else `omni models merge-branch` after confirmation) — the drafts publish on merge.

Scope a large rename with `folder_paths` / `labels` / `creator_id` / `only_in_workbook_id` when the user only wants part of the content rewritten.

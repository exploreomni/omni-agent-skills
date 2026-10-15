# Model Roles & Caller Access

## Determining what a caller can do — run before deciding where model/content changes live

This is the canonical access check other skills defer to (e.g. `omni-content-builder` / `omni-model-builder` deciding whether a new field goes on a **branch** vs a **workbook model**). Run `omni whoami whoami --model-id <modelId>` and read `rolesByModel[<id>].permissions`. Gate on the **presence of permissions**, not the role *name* — names can be renamed custom roles and surface as internal codes (e.g. `QUERY_TOPICS`):

| Permission (in `whoami`) | Capability |
|---|---|
| `QUERY_TOPICS` | query curated topics (Restricted Querier and up) |
| `QUERY_FULL_MODEL` | full-model + SQL access — and the **observable proxy for "can create/use a branch"** (Querier, Modeler, Admin) |
| `UPDATE` (shared-model-scoped) | **merge/promote** changes to the shared model (Modeler, Admin) |
| `USE_WORKBOOKS` | create content (workbooks/dashboards). A **Viewer lacks this and cannot author at all.** |

Decision shortcuts:
- **Where should a new model field live?** `QUERY_FULL_MODEL` present → a **shared-model branch** (merge it yourself if you *also* have `UPDATE`, otherwise open a PR / request a merge — a Querier can branch and modify but not promote); `QUERY_FULL_MODEL` absent but `USE_WORKBOOKS` present (Restricted Querier) → the document's **workbook model** (extension). A Viewer can't author content, so they never reach this choice.
- **What a Restricted Querier can change *in* the workbook model — view-scoped only:** add dimensions/measures to an **existing view** (extension mode) and edit **decorations** on existing fields (label/format/description/hidden/synonyms). They **cannot** modify a **topic** in any way (expose a field, change joins/topic config, create a topic) or change **access grants** / other governance — those need `QUERY_FULL_MODEL` on a shared-model branch. So don't plan a topic-scope, join, or grant change for a restricted querier's workbook model; it 403s mid-build and can leave the document half-modeled.
- **What a Restricted Querier can *query* — topics only.** `QUERY_TOPICS` without `QUERY_FULL_MODEL` means every query they author must be **topic-based** (`table` = the topic's base view + `join_paths_from_topic_name`). A **bare base-view query** or a **raw-SQL `userEditedSQL`** tile needs `QUERY_FULL_MODEL` (full-model + SQL access) — so it isn't an option for a restricted-querier author; build every tile on a topic. (Distinct from *visibility*: even a Querier-authored non-topic tile is hidden from restricted/Viewer *audiences* unless Access-Boosted.)
- A shared-model-scoped `whoami` does **not** list branch ability as its own entry — branch create/use is a separate capability granted to Querier+ — so use `QUERY_FULL_MODEL` as the proxy. (Holds for base roles; a custom role could grant one without the other — confirm when it matters.)

## Assigning roles

```bash
# Roles are keyed by the MEMBERSHIP id, NOT the user id (a user id → 404 "Membership … not found").
# Get it — yourself: whoami → user.membershipId · another user: scim users-list (its `id` IS the membershipId, see note below)
omni users get-model-roles <membershipId> --model-id <modelId>
omni users assign-model-role <membershipId> --body '{ "modelId": "<modelId>", "roleName": "<roleName>" }'

# Group variants
omni users user-groups-get-model-roles <groupId> --model-id <modelId>
omni users user-groups-assign-model-role <groupId> --body '{ "modelId": "<modelId>", "roleName": "<roleName>" }'
```

> **Resolving *another* user's membershipId needs the org key.** `whoami → user.membershipId` is self-only. For someone else, `omni scim users-list --filter 'userName eq "them@company.com"'` returns the membership as its **`id`** (which is the membershipId — *not* the user's `user.id`). But the **SCIM API accepts only the org-level API key**: a user-scoped PAT/OAuth is rejected with *"User-scoped API keys are not allowed to access the SCIM API."* The `get`/`assign-model-role` calls above work with a user PAT — only this lookup needs the org key.

- The body key is **`roleName`** (not `role`), and the path id is the **membership id** (a user id returns 404).
- `roleName` is a **server-validated, instance-specific** string — base roles (e.g. `QUERY_TOPICS`, `QUERIER`, `CONNECTION_ADMIN`) **plus** any org custom roles. The valid set is **not** discoverable via `--schema` (the field is a bare string, no enum) or any list command; an unknown value returns `422 "Invalid role"`. Discover a valid code by reading `get-model-roles` on a membership that already holds the target role.
- There is **no un-assign command** — to revert an override, re-assign the prior role.

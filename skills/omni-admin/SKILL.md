---
name: omni-admin
description: Administer an Omni Analytics instance — manage connections, users, groups, user attributes, permissions, schedules, and schema refreshes via the Omni CLI. Use this skill whenever someone wants to manage users or groups, set up permissions on a dashboard or folder, configure user attributes, create or modify schedules, manage database connections, refresh a schema, set up access controls, provision users, or any variant of "add a user", "give access to", "set up permissions", "who has access", "configure connection", "refresh the schema", or "schedule a delivery".
---

# Omni Admin

Manage your Omni instance — connections, users, groups, user attributes, permissions, schedules, and schema refreshes.

> **Tip**: Most admin endpoints require an **Organization API Key** (not a Personal Access Token).

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule for profile setup (`omni config init --auth oauth`) and discovering command and request-body shapes with `--schema`.

If no CLI profile exists but the environment provides credentials, pass them explicitly:

```bash
omni <command> --base-url "$OMNI_BASE_URL" --token "$OMNI_API_TOKEN"
```

## Discovering Commands

```bash
omni scim --help             # User and group management
omni schedules --help        # Schedule operations
omni connections --help      # Connection management
omni documents --help        # Document permissions
omni folders --help          # Folder permissions
omni scim users-create --schema   # Print a command's args, flags, body schema + example, and response shape (no token)
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Safe Admin Defaults

- For create operations, first try the requested create. If the API returns a conflict because the resource already exists, look it up and verify it exactly matches the requested state before reporting success.
- Prefer read-after-write checks that inspect the specific created or changed resource, not just a successful status response.
- Use the content role names the permission APIs take (`NO_ACCESS`, `VIEWER`, `EXPLORER`, `EDITOR`, `MANAGER`, `OWNER`) when updating content access. `OWNER` can be granted only to users.

## Connections

```bash
# List connections
omni connections list

# Schema refresh schedules
omni connections schedules-list <connectionId>

# Connection environments (create, update <id>, delete <id>)
omni connections connection-environments-create --schema
```

### Commit Signing Key Rotation (CLI ≥ 1.1.2)

Rotating invalidates the previous key — confirm with the user before running, and re-register the new public key wherever the old one was trusted.

```bash
# Rotate a connection's dbt commit signing key
omni connections dbt-rotate-signing-key <connectionId>

# Rotate a model's git commit signing key
omni models git-rotate-signing-key <modelId>
```

## User Management (SCIM 2.0)

> The `--body` blocks below are worked examples. For the authoritative field list (types, required, enums), run the command with `--schema` — e.g. `omni scim users-create --schema` — rather than relying on these shapes to be exhaustive.

```bash
# List users
omni scim users-list

# Find by email
omni scim users-list --filter 'userName eq "user@company.com"'

# Create user
omni scim users-create --body '{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "userName": "newuser@company.com",
  "displayName": "New User",
  "active": true,
  "emails": [{ "primary": true, "value": "newuser@company.com" }]
}'

# Deactivate user
omni scim users-update <userId> --body '{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "Operations": [{ "op": "replace", "path": "active", "value": false }]
}'

# Delete user
omni scim users-delete <userId>
```

## Group Management (SCIM 2.0)

```bash
# List groups
omni scim groups-list

# Create group
omni scim groups-create --body '{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
  "displayName": "Analytics Team",
  "members": [{ "value": "user-uuid-1" }]
}'

# Add members
omni scim groups-update <groupId> --body '{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
  "Operations": [{ "op": "add", "path": "members", "value": [{ "value": "new-user-uuid" }] }]
}'
```

## User Attributes

```bash
# List attributes (system + custom)
omni user-attributes list

# Create a custom attribute definition (CLI ≥ 1.4.0)
omni user-attributes create --body '{
  "name": "region",
  "label": "Region",
  "type": "String",
  "description": "User region for row-level security filtering",
  "default_value": "us-east"
}'

omni user-attributes update <id> --body '{ "default_value": "us-west" }'
omni user-attributes delete <id>

# Find the user by email before setting an attribute
omni scim users-list --filter 'userName eq "user@company.com"'

# Set attribute on user (via SCIM)
omni scim users-update <userId> --body '{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "Operations": [{
    "op": "replace",
    "path": "urn:omni:params:1.0:UserAttribute:region",
    "value": "West Coast"
  }]
}'
```

User attributes work with `access_filters` in topics for row-level security.
SCIM can set values only for attribute definitions that already exist. Use
`omni user-attributes list` to confirm the requested attribute definition exists
before setting a value, but do not use it as proof that a specific user's value
changed. If the definition is missing, create it with `omni user-attributes
create` (CLI ≥ 1.4.0) and confirm the create before assigning values; do not
keep retrying SCIM paths or claim the value was set from an empty
`User attributes set: {}` response.

Managing definitions needs the **Manage User Attributes** permission; the naming
and type rules are in `--help` and fail loudly. Two behaviors do not:

- **`delete <id>` reaches past the definition, and the response does not say so.**
  Every user value goes with it, embed SSO logins still passing the name fail
  outright (an embed lockout), model SQL referencing it breaks, and a connection
  selecting its environment by that name silently falls back to the default
  connection. Search the model for the name and confirm with the user first.
- **`Number` values are stored as strings**, and a JSON number past 2^53 - 1 is
  silently rounded on the way in — a `default_value` of `9007199254740993` is
  stored, and returned, as `"9007199254740992"`. Send large numbers as strings.

When the user explicitly asks to set or update a user attribute, converge the
user record with a SCIM update even if the initial user lookup already shows the
requested value. This keeps the operation idempotent while still honoring the
requested admin action.

## Model Roles & Caller Access

Before deciding where a model or content change goes, run `omni whoami whoami --model-id <modelId>` and decide from the permissions in `rolesByModel[<id>].permissions`, since a role can appear under a custom name or an internal code: `QUERY_FULL_MODEL` is the signal that the caller can create a branch, `UPDATE` that they can merge to the shared model (without it, open a PR or request a merge), and `USE_WORKBOOKS` that they can create content. A caller with `USE_WORKBOOKS` and no `QUERY_FULL_MODEL` (a Restricted Querier) can change only existing views in the document's workbook model and must build every tile on a topic, so do not plan topic, join, or access-grant changes for them. The full permission table, the decision rules, and the role-assignment commands (keyed by membership id, with the body key `roleName`) are in [references/model-roles.md](references/model-roles.md).

## Document Permissions

```bash
# Document settings, plus one user's permits when --user-id (a membership id) is given
omni documents get-permissions <documentId> --user-id <membershipId>

# List document access principals
omni documents access-list <documentId>

# Add direct access for a group
omni documents add-permits <documentId> --body '{
  "userGroupIds": ["group-uuid"],
  "role": "VIEWER"
}'

# Add direct access for a user
omni documents add-permits <documentId> --body '{
  "userIds": ["<membershipId>"],
  "role": "EDITOR"
}'
```

`role` is one of `NO_ACCESS`, `VIEWER`, `EXPLORER`, `EDITOR`, `MANAGER` or `OWNER`, and `OWNER` can be granted only to users. `userIds` are membership ids, not user ids; [model-roles.md](references/model-roles.md) shows how to look one up.

### Access Boost

**Access Boost** lets Viewer / Restricted Querier roles view a dashboard built on **non-topic content** — a raw-SQL (`userEditedSQL`) tile or a bare base-view query — which those roles otherwise can't see.

**Dashboard-only:** Access Boost lifts the restriction on the **dashboard** view of those tiles. It does **not** extend to the underlying **workbook** — a restricted role still can't open the workbook's non-topic or SQL tabs (or see the query behind the tile) regardless of Access Boost.

**⚠️ Confirm before boosting — it loosens access controls.** Access Boost deliberately exposes content that restricted roles can't otherwise see, and non-topic / raw-SQL tiles bypass topic-scoped governance (access filters, `always_where`) — so boosting can surface data those controls would normally withhold. **Do not apply Access Boost autonomously or as a reflexive fix for "they can't see it."** First:
1. **Understand what the document exposes** — what data the boosted tiles show, at what grain, and whether any of it is sensitive.
2. **Confirm intent with the requester** — that they really mean to grant *these specific* Viewer / Restricted Querier users or groups visibility into that content. State the implication back to them and get an explicit go-ahead before running the command.
3. **Prefer the narrowest scope** — boost specific users/groups (`add-permits`) over `organizationAccessBoost`, which boosts everyone in the organization on this document; use it only when that's explicitly what's wanted.
4. **Note the governance interaction** — model access grants still apply unless a grant sets `access_boostable: true`; don't treat that as a safety net, confirm intent regardless.

**Prerequisite (org capability, not in the CLI):** the org must have `allowsDocumentAccessBoost` enabled (on by default), and `allowsMemberToProvisionAccessBoost` (off by default) for non-admins to grant it. These are organization settings. When boost is off, or the caller isn't allowed to grant it, a request that sets `accessBoost` or `organizationAccessBoost` to `true` is rejected with 403. It's a gate; it does **not** itself turn Access Boost on anywhere.

Once you've confirmed intent, there are two activation levers, both **scoped to a single document**:

```bash
# Boost specific users/groups on this document (add-permits / update-permits)
omni documents add-permits <documentId> --body '{
  "userGroupIds": ["group-uuid"],
  "role": "VIEWER",
  "accessBoost": true
}'

# Boost the "everyone in the org" principal on this document
omni documents update-permission-settings <documentId> --body '{
  "organizationAccessBoost": true,
  "organizationRole": "VIEWER"
}'
```

`update-permission-settings` (PUT) also carries the document's other toggles — `canAnalyze`, `canDownload`, `canDrill`, `canDuplicate`, `canRequestAccess`, `canSaveSpreadsheets`, `canSchedule`, `canUpload`, `canUseDashboardAi`, `canUseTimezoneOverride`, `canViewWorkbook`, `requirePullRequestToPublish`. Note `organizationAccessBoost` boosts the org-default principal on **this** document only — it is not an org-wide switch.

## Folder Permissions

```bash
# Get all permits (needs MANAGER on the folder), or one user's with --user-id <membershipId>
omni folders get-permissions <folderId>

# Grant
omni folders add-permissions <folderId> --body '{
  "userGroupIds": ["group-uuid"],
  "role": "VIEWER"
}'
```

The body matches documents `add-permits`: `role`, membership-id `userIds` and/or `userGroupIds`, and an optional `accessBoost`. `update-permissions` changes existing permits, `revoke-permissions` removes them, and `update-permission-settings` sets the folder's `organizationRole` and `organizationAccessBoost`.

## Schedules

```bash
# List schedules
omni schedules list

# Create schedule
omni schedules create --body '{
  "identifier": "dashboard-identifier",
  "name": "Weekly Dashboard - Monday 9am PT",
  "schedule": "0 9 ? * MON *",
  "timezone": "America/Los_Angeles",
  "destinationType": "email",
  "content": "dashboard",
  "format": "pdf",
  "subject": "Weekly dashboard",
  "recipients": ["team@company.com"]
}'

# Manage recipients for an existing schedule
omni schedules recipients-get <scheduleId>

omni schedules add-recipients <scheduleId> --body '{ "recipients": ["team@company.com"] }'
```

> **`schedules update` is a full replacement, not a patch**, and it returns
> `"success": true` either way. Any optional property you leave out is reset to
> its default — filter values cleared, **the alert condition removed**,
> `maxRowLimit` and the presentation flags back to defaults. `--help` lists
> every property that resets.
>
> **You cannot round-trip `schedules get` into it.** The read shape is not the
> write shape: the GET nests presentation options under `metadata` and
> recipients under `destinations[]`, while the update body wants `subject`,
> `maxRowLimit`, `recipients` and `destinationType` flat — feeding the GET
> straight back 400s on `destinationType`. Build the body from
> `omni schedules update --schema` and carry across every value you mean to
> keep.

**Email-only users** are the recipients that exist only to receive deliveries:
`omni users list-email-only` / `create-email-only` / `create-email-only-bulk`,
and `delete-email-only-bulk` (CLI ≥ 1.4.0). The bulk delete is **partially
successful by design** — a 200 carries `deleted[]` alongside
`notFound: {emails: [], userIds: []}`, so check those two arrays, not the
status, before reporting it done.

## AI Credits

The `omni ai credit-controls-*` commands read and update AI credit controls for the organization, for users, and for entity groups; the `omni ai credit-usage-*` commands read usage for the current billing period, and `credit-usage-users-read` takes membership ids. Required permissions, CLI versions, feature flags, and examples: [references/ai-credits.md](references/ai-credits.md).

## Color Palettes

`omni color-palettes` manages the organization's custom chart palettes (CLI ≥ 1.3.1); writes need the **Manage Config** permission. An update recolors every chart that uses the palette, a delete sends those charts back to the org default palette, and neither reports which charts changed. Examples and naming rules: [references/color-palettes.md](references/color-palettes.md).

## Uploads

`omni uploads` lists, creates, replaces, and deletes the CSV and spreadsheet files users upload to query alongside warehouse data; `create` and `replace-data` take the file path with `--file`. `replace-data` keeps the upload id, so views and document tabs serve the new data without model or document changes; compare headers first, because renamed or removed columns can break content that uses them. Flags, the `--body` form, and examples: [references/uploads.md](references/uploads.md).

## Verification After Changes

Admin operations can silently fail or partially apply. Always read back the state after any write to confirm the change took effect.

### After User Operations

```bash
# After creating or updating a user, verify they exist with correct state
omni scim users-list --filter 'userName eq "newuser@company.com"'
```

Check that: `active` matches what you set, `displayName` is correct, and the user ID was returned (not an error).

### After Group Operations

```bash
# After creating a group or modifying members, verify membership
omni scim groups-list
```

Check that: the group exists with the expected `displayName`, and `members` array contains the expected user UUIDs.

### After Permission Changes

```bash
# After setting document permissions, verify the principal and role
omni documents access-list <documentId>

# For a specific user, also check their permits (--user-id takes a membership id)
omni documents get-permissions <documentId> --user-id <membershipId>

# After setting folder permissions, verify
omni folders get-permissions <folderId>
```

Check that: the principal is listed and the `role` matches what you set (`VIEWER`, `EDITOR`, etc.).

### After User Attribute Changes

```bash
# Verify the user's assigned attribute value was set
omni scim users-list --filter 'userName eq "user@company.com"'
```

Check that: the response contains the target user, the user's
`urn:omni:params:1.0:UserAttribute` object includes the requested attribute name,
and the value exactly matches what you set.

After a definition change (`user-attributes create` / `update` / `delete`),
read it back with `omni user-attributes list` — `Number` defaults come back as
strings, so compare them as strings.

If the attribute is used for row-level security (`access_filters`), test it by running a query as the target user:

```bash
omni query run --body '{ "query": { ... }, "userId": "<target-user-uuid>" }'
```

Verify the results are correctly filtered — the user should only see rows matching their attribute value.

### After Schedule Operations

```bash
# Verify schedule was created with correct settings
omni schedules list -o json

# Verify recipients were added
omni schedules recipients-get <scheduleId>
```

Check that: the created schedule id appears in the list and the returned fields match the requested `schedule` cron, `timezone`, `destinationType`, `content`, `format`, and dashboard `identifier`. If the list/get response shape is not parseable, report that schedule setting verification was inconclusive instead of silently treating an empty parser result as success. Always verify recipients with `recipients-get`.

## Cache and Validation

`omni models cache-reset` resets a model's cache policy, `omni models content-validator-get` finds broken field references across dashboards and tiles (with `--branch-id`, it shows what a branch change would break), and `omni models git-get` returns a model's git configuration. Examples and the full-validation flag: [references/cache-and-validation.md](references/cache-and-validation.md).

## Docs Reference

- [Connections](https://docs.omni.co/api/connections.md) · [Users (SCIM)](https://docs.omni.co/api/users.md) · [Groups (SCIM)](https://docs.omni.co/api/user-groups.md) · [User Attributes](https://docs.omni.co/api/user-attributes.md) · [Document Permissions](https://docs.omni.co/api/document-permissions.md) · [Folder Permissions](https://docs.omni.co/api/folder-permissions.md) · [Schedules](https://docs.omni.co/api/schedules.md) · [Schedule Recipients](https://docs.omni.co/api/schedule-recipients.md) · [Content Validator](https://docs.omni.co/api/content-validator.md) · [API Authentication](https://docs.omni.co/api/authentication.md)

## Related Skills

- **omni-model-builder** — edit the model that access controls apply to
- **omni-content-explorer** — find documents before setting permissions
- **omni-content-builder** — create dashboards before scheduling delivery
- **omni-embed** — manage embed users and user attributes for embedded dashboards

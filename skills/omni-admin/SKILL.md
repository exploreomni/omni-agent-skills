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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

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
omni scim users-create --schema   # Print any body command's JSON schema + filled example (no token)
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Safe Admin Defaults

- For create operations, first try the requested create. If the API returns a conflict because the resource already exists, look it up and verify it exactly matches the requested state before reporting success.
- Prefer read-after-write checks that inspect the specific created or changed resource, not just a successful status response.
- Use the role names returned by Omni permission APIs (`VIEWER`, `EXPLORER`, `EDITOR`, `MANAGER`) when updating content access.

## Connections

```bash
# List connections
omni connections list

# Schema refresh schedules
omni connections schedules-list <connectionId>

# Connection environments
omni connections connection-environments-list
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
# List attributes
omni user-attributes list

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
changed. If the definition is missing, report that it must be created in
Admin -> User Attributes before values can be assigned; do not keep retrying
SCIM paths or claim the value was set from an empty `User attributes set: {}`
response.

When the user explicitly asks to set or update a user attribute, converge the
user record with a SCIM update even if the initial user lookup already shows the
requested value. This keeps the operation idempotent while still honoring the
requested admin action. After the update, read back the same user and verify the
value under `urn:omni:params:1.0:UserAttribute`.

## Model Roles

```bash
# Get/set model roles for a user
omni users get-model-roles <userId>

omni users assign-model-role <userId> --body '{ "modelId": "{modelId}", "role": "VIEWER" }'

# Get/set model roles for a group
omni users user-groups-get-model-roles <groupId>

omni users user-groups-assign-model-role <groupId> --body '{ "modelId": "{modelId}", "role": "VIEWER" }'
```

## Document Permissions

```bash
# Check effective permissions for a user (userId required)
omni documents get-permissions <documentId> --userid <userId>

# List document access principals
omni documents access-list <documentId>

# Add direct access for a group
omni documents add-permits <documentId> --body '{
  "userGroupIds": ["group-uuid"],
  "role": "VIEWER"
}'

# Add direct access for a user
omni documents add-permits <documentId> --body '{
  "userIds": ["user-uuid"],
  "role": "EDITOR"
}'
```

`role` is one of `NO_ACCESS`, `VIEWER`, `EDITOR`, `MANAGER`.

### Access Boost

**Access Boost** lets Viewer / Restricted Querier roles view a dashboard built on **non-topic content** — a raw-SQL (`userEditedSQL`) tile or a bare base-view query — which those roles otherwise can't see. (Model **access grants** still apply unless the grant sets `access_boostable: true`.)

**Dashboard-only:** Access Boost lifts the restriction on the **dashboard** view of those tiles. It does **not** extend to the underlying **workbook** — a restricted role still can't open the workbook's non-topic or SQL tabs (or see the query behind the tile) regardless of Access Boost.

**⚠️ Confirm before boosting — it loosens access controls.** Access Boost deliberately exposes content that restricted roles can't otherwise see, and non-topic / raw-SQL tiles bypass topic-scoped governance (access filters, `always_where`) — so boosting can surface data those controls would normally withhold. **Do not apply Access Boost autonomously or as a reflexive fix for "they can't see it."** First:
1. **Understand what the document exposes** — what data the boosted tiles show, at what grain, and whether any of it is sensitive.
2. **Confirm intent with the requester** — that they really mean to grant *these specific* Viewer / Restricted Querier users or groups visibility into that content. State the implication back to them and get an explicit go-ahead before running the command.
3. **Prefer the narrowest scope** — boost specific users/groups (`add-permits`) over the org-wide `organizationAccessBoost`; reach for org-wide only when that's explicitly what's wanted.
4. **Note the governance interaction** — model access grants still apply unless a grant sets `access_boostable: true`; don't treat that as a safety net, confirm intent regardless.

**Prerequisite (org capability, not in the CLI):** the org must have `allowsDocumentAccessBoost` enabled (and `allowsMemberToProvisionAccessBoost` for non-admins to grant it). This is an instance/admin setting — if it's off, the document-level flags below are silently cleared. It's a gate; it does **not** itself turn Access Boost on anywhere.

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

`update-permission-settings` (PUT) also carries the document's other toggles — `canDownload`, `canDrill`, `canSchedule`, `canUpload`, `canUseDashboardAi`, `canUseTimezoneOverride`, `canViewWorkbook`, `requirePullRequestToPublish`. Note `organizationAccessBoost` boosts the org-default principal on **this** document only — it is not an org-wide switch.

## Folder Permissions

```bash
# Get
omni folders get-permissions <folderId>

# Set
omni folders add-permissions <folderId> --body '{
  "permissions": [{ "type": "group", "id": "group-uuid", "access": "view" }]
}'
```

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

# For a specific user, also check effective permissions
omni documents get-permissions <documentId> --userid <userId>

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
and the value exactly matches what you set. `omni user-attributes list` only
verifies that the attribute definition exists.

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

### Verification Checklist

| Operation | Verify With | What to Check |
|-----------|-------------|---------------|
| Create/update user | `omni scim users-list --filter ...` | User exists, `active` status correct |
| Create/update group | `omni scim groups-list` | Group exists, members list correct |
| Set document permissions | `omni documents get-permissions` | Access level and target correct |
| Set folder permissions | `omni folders get-permissions` | Access level and target correct |
| Set user attribute | `omni scim users-list --filter ...` | User attribute extension contains requested value |
| User attribute + access filter | `omni query run` with `userId` | Row-level filtering works |
| Create schedule | `omni schedules list` | Schedule settings correct |
| Add recipients | `omni schedules recipients-get` | All recipients listed |

## Cache and Validation

```bash
# Reset cache policy
omni models cache-reset <modelId> <policyName> --body '{ "resetAt": "2025-01-30T22:30:52.872Z" }'

# Content validator (find broken field references across all dashboards and tiles)
# Useful for blast-radius analysis: remove a field on a branch, then run the
# validator against that branch to see what content would break.
# See the Field Impact Analysis section in omni-model-explorer for the full workflow.
omni models content-validator-get <modelId>

# Run against a specific branch (e.g., after removing a field)
omni models content-validator-get <modelId> --branch-id <branchId>

# Git configuration
omni models git-get <modelId>
```

## Docs Reference

- [Connections](https://docs.omni.co/api/connections.md) · [Users (SCIM)](https://docs.omni.co/api/users.md) · [Groups (SCIM)](https://docs.omni.co/api/user-groups.md) · [User Attributes](https://docs.omni.co/api/user-attributes.md) · [Document Permissions](https://docs.omni.co/api/document-permissions.md) · [Folder Permissions](https://docs.omni.co/api/folder-permissions.md) · [Schedules](https://docs.omni.co/api/schedules.md) · [Schedule Recipients](https://docs.omni.co/api/schedule-recipients.md) · [Content Validator](https://docs.omni.co/api/content-validator.md) · [API Authentication](https://docs.omni.co/api/authentication.md)

## Related Skills

- **omni-model-builder** — edit the model that access controls apply to
- **omni-content-explorer** — find documents before setting permissions
- **omni-content-builder** — create dashboards before scheduling delivery
- **omni-embed** — manage embed users and user attributes for embedded dashboards

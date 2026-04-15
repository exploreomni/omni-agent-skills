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
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

## Discovering Commands

```bash
omni scim --help             # User and group management
omni schedules --help        # Schedule operations
omni connections --help      # Connection management
omni documents --help        # Document permissions
omni folders --help          # Folder permissions
```

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
# Get permissions for a user (userId required)
omni documents get-permissions <documentId> --user-id <userId>

# Set permissions
omni documents update-permission-settings <documentId> --body '{
  "permissions": [
    { "type": "group", "id": "group-uuid", "access": "view" },
    { "type": "user", "id": "user-uuid", "access": "edit" }
  ]
}'
```

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
  "documentId": "dashboard-identifier",
  "frequency": "weekly",
  "dayOfWeek": "monday",
  "hour": 9,
  "timezone": "America/Los_Angeles",
  "format": "pdf"
}'

# Manage recipients
omni schedules recipients-get <scheduleId>

omni schedules add-recipients <scheduleId> --body '{ "recipients": [{ "type": "email", "value": "team@company.com" }] }'
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
# After setting document permissions, verify for the target user
omni documents get-permissions <documentId> --user-id <userId>

# After setting folder permissions, verify
omni folders get-permissions <folderId>
```

Check that: the permission `access` level matches what you set (`view`, `edit`), and the target user/group ID is listed.

### After User Attribute Changes

```bash
# Verify the attribute value was set
omni user-attributes list
```

If the attribute is used for row-level security (`access_filters`), test it by running a query as the target user:

```bash
omni query run --body '{ "query": { ... }, "userId": "<target-user-uuid>" }'
```

Verify the results are correctly filtered — the user should only see rows matching their attribute value.

### After Schedule Operations

```bash
# Verify schedule was created with correct settings
omni schedules list

# Verify recipients were added
omni schedules recipients-get <scheduleId>
```

Check that: `frequency`, `dayOfWeek`, `hour`, `timezone`, and `format` match what you set, and all intended recipients are listed.

### Verification Checklist

| Operation | Verify With | What to Check |
|-----------|-------------|---------------|
| Create/update user | `omni scim users-list --filter ...` | User exists, `active` status correct |
| Create/update group | `omni scim groups-list` | Group exists, members list correct |
| Set document permissions | `omni documents get-permissions` | Access level and target correct |
| Set folder permissions | `omni folders get-permissions` | Access level and target correct |
| Set user attribute | `omni user-attributes list` | Attribute value set |
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

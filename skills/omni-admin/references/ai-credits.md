# AI Credits

Read and manage AI credit controls and usage (entity-group commands and usage reads require CLI ≥ 1.1.2). Org-level controls require the AI-admin permission; per-user controls and usage require manage-user-attributes; entity-group controls and usage require add/remove-users. Per-user and per-entity-group limits are also behind instance feature flags.

```bash
# Org-level credit controls
omni ai credit-controls-get
omni ai credit-controls-update --body '{ ... }'   # run with --schema for the body shape

# Per-user and per-entity-group limits
omni ai credit-controls-users-list
omni ai credit-controls-users-update --body '{ ... }'
omni ai credit-controls-entity-groups-list
omni ai credit-controls-entity-groups-update --body '{ ... }'

# Usage for the current billing period (reads work even when controls editing is disabled)
omni ai credit-usage-users-read --body '{ "userIds": ["<membershipId>"] }'
omni ai credit-usage-entity-groups-read --body '{ ... }'
```

> **Gotcha**: `credit-usage-users-read` takes **membership ids** (the user's membership in this organization), not base user ids — an unknown id 404s the whole request, naming the offending id. At most 1000 ids per request, no duplicates; users with no usage report 0.

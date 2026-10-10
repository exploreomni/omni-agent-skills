# Access Boost

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

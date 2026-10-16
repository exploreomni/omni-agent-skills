---
name: omni-content-explorer
description: Find, browse, and organize content in Omni Analytics — dashboards, workbooks, folders, and labels — using the Omni CLI. Use this skill whenever someone wants to find an existing dashboard, search for content, list workbooks, browse folders, see what dashboards exist, find popular reports, download a dashboard as PDF or PNG, set an alert on a dashboard tile, favorite content, manage labels on documents, or any variant of "find the dashboard about", "what reports do we have", "show me our dashboards", "where is the sales report", "download this dashboard", or "alert me when this changes". This skill locates and organizes content; to inspect what a dashboard tile actually queries — its fields, filters, and sorts — use omni-query.
---

# Omni Content Explorer

Find, browse, and organize Omni content — dashboards, workbooks, and folders — through the Omni CLI.

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

## Discovering Commands

```bash
omni content --help     # Content operations
omni documents --help   # Document operations
omni folders --help     # Folder operations
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Known Issues & Safe Defaults

- `omni content list --labels <name>[,<name>]` filters **dashboards and apps** by label (CLI ≥ 1.5.0). For workbook-only documents, which `content list` does not return, fall back to `omni documents list --include labels -o json` and filter client-side on the `labels` array.
- Some dashboard exports can fail before a job is created, for example with `Cannot use 'in' operator to search for 'query_id' in ...`. If `omni dashboards download` returns an error and no job ID, do not call `download-status` or claim the export completed. Report the dashboard identifier, the exact API error, and that no downloadable job was created.

## Searching Content

For "find the dashboard about X", reach for free-text search first (CLI ≥ 1.1.2):

```bash
omni content search --q "revenue" --limit 25
```

`--q` keywords are matched against dashboard names, descriptions, query names, folder names, labels, and creator names. `--limit` caps results at 1–25. Each result carries `identifier`, `name`, `description`, `folderPath`, `tileNames`, `verified`, and a ready-made `url` — link the user straight to it. Search covers **dashboards only** — workbook-only documents don't surface here, so fall back to `omni content list` / `omni documents list` filtering when the target may not have a dashboard.

## Browsing Content

### List All Content

```bash
omni content list
```

### With Counts and Labels

```bash
omni content list --include '_count,labels'
```

### Filter and Sort

```bash
# By label (CLI ≥ 1.5.0) — comma-separated label names.
# Covers dashboards and apps; workbook-only documents are not returned by content list,
# so for those fall back to `omni documents list --include labels -o json` + client-side filter.
omni content list --labels "Weekly Digest,Finance"

# By scope
omni content list --scope organization

# Sort by popularity or recency
omni content list --sort-field favorites

omni content list --sort-field updatedAt
```

### Pagination

Responses include `pageInfo` with cursor-based pagination. Fetch next page:

```bash
omni content list --cursor <nextCursor>
```

## Working with Documents

### List Documents

```bash
omni documents list

# Filter by creator
omni documents list --creator-id <userId>
```

Each document includes: `identifier`, `name`, `type`, `scope`, `owner`, `folder`, `labels`, `updatedAt`, `hasDashboard`.

> **Important**: Always use the `identifier` field for API calls, not `id`. The `id` field is null for workbook-type documents and will cause silent failures.

### Get Document Queries

Retrieve query definitions powering a dashboard's tiles:

```bash
omni documents get-queries <identifier>
```

Useful for understanding what a dashboard computes and re-running queries via `omni-query`.

## Folders

```bash
# List
omni folders list

# List only the caller's favorited folders (CLI ≥ 1.5.0; org-scoped keys must also pass --user-id)
omni folders list --include onlyFavorites

# Get a single folder (CLI ≥ 1.5.0). Returns the fields the API can set;
# owner and access still come from `omni folders get-permissions <folderId>`.
omni folders get <folderId>

# Create
omni folders create "Q1 Reports" --scope organization
```

## Labels

```bash
# List labels
omni labels list

# Find documents with a label
omni documents list --include labels -o json

# Add label to document
omni documents add-label <identifier> <labelName>

# Remove label
omni documents remove-label <identifier> <labelName>

# Add/remove labels on a folder in one atomic call (CLI ≥ 1.1.2).
# Labels must already exist in the organization.
omni folders bulk-update-labels <folderId> --body '{ "add": ["Q1"], "remove": ["Draft"] }'
```

## Favorites

```bash
# Favorite a document
omni documents add-favorite <identifier>

# Unfavorite a document
omni documents remove-favorite <identifier>

# Favorite a folder (CLI ≥ 1.5.0). Both calls are idempotent.
omni folders add-favorite <folderId>
omni folders remove-favorite <folderId>
```

## Dashboard and App Downloads

```bash
# Start download (async)
omni dashboards download <identifier> --body '{ "format": "pdf" }'

# Poll job status only after the start command returns a job ID
omni dashboards download-status <identifier> <jobId>
```

Formats: `pdf`, `png`

**Apps download separately** (CLI ≥ 1.5.0). `omni dashboards download` renders dashboards; a published app uses the parallel `omni apps` family. Same `download` → `download-status` → `download-file` async flow and the same body shape as `dashboards download`; a job is visible only to the user it runs as, so pass the same `--user-id` through all three calls when using an org-scoped API key.

```bash
omni apps download <identifier> --body '{ "format": "pdf" }'
omni apps download-status <identifier> <jobId>
omni apps download-file <identifier> <jobId>
```

Formats: `pdf`, `png`, `xlsx`, `csv` (full-app `csv` is a ZIP of one CSV per query).

## Alerts

An alert is a schedule with a condition on one tile of an existing dashboard: it runs on its cron and delivers only when the condition holds. Any user who can schedule the dashboard can create one; it needs no admin rights. Add `conditionType` (`RESULTS_PRESENT`, `RESULTS_MISSING`, `RESULTS_CHANGED`, `RESULTS_UNCHANGED`) and `conditionQueryMapKey` (the watched tile's key in `queryPresentations.data`) to the `schedules create` body; each requires the other. Confirm field names with `omni schedules create --schema` first.

- **An alert sends messages to people.** Confirm the recipients with the user before creating one.
- **The tile decides whether the alert is useful.** Shaping it is builder work: `omni-content-builder` → *Tiles an alert can watch*.

The condition table, a create example, and cron timing: [references/alerts.md](references/alerts.md). For plain scheduled deliveries and recipients, see **`omni-admin`** → *Schedules*; to build or change the watched tile, see **`omni-content-builder`**.

## URL Patterns

Construct direct links to content:

```
Dashboard: {OMNI_BASE_URL}/dashboards/{identifier}
Workbook:  {OMNI_BASE_URL}/w/{identifier}
```

The `identifier` comes from the document's `identifier` field in API responses. Always provide the user a clickable link after finding content.

## Search Patterns

When scanning all documents for field references (e.g., for impact analysis), paginate with cursor and call `omni documents get-queries <identifier>` for each document. Launch multiple query-fetch calls in parallel for efficiency. For field impact analysis, prefer the content-validator approach in `omni-model-explorer`.

## Docs Reference

- [Content API](https://docs.omni.co/api/content.md) · [Documents API](https://docs.omni.co/api/documents.md) · [Folders API](https://docs.omni.co/api/folders.md) · [Labels API](https://docs.omni.co/api/labels.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Schedules API](https://docs.omni.co/api/schedules.md)

## Related Skills

- **omni-query** — run queries behind dashboards you've found
- **omni-content-builder** — create or update dashboards
- **omni-embed** — embed dashboards you've found in external apps
- **omni-admin** — manage permissions on documents and folders

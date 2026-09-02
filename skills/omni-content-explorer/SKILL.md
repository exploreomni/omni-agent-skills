---
name: omni-content-explorer
description: Find, browse, and organize content in Omni Analytics — dashboards, workbooks, folders, and labels — using the Omni CLI. Use this skill whenever someone wants to find an existing dashboard, search for content, list workbooks, browse folders, see what dashboards exist, find popular reports, download a dashboard as PDF or PNG, favorite content, manage labels on documents, or any variant of "find the dashboard about", "what reports do we have", "show me our dashboards", "where is the sales report", or "download this dashboard".
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

- `omni content list` does not currently support a `--labels` filter. For dashboards, `omni content search --q <labelName>` matches labels. For an exhaustive by-label listing (including workbook-only documents), use `omni documents list --include labels -o json`, paginate with `--cursor`, then filter records whose `labels` array contains the target label.
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
# By label: list documents with labels, then filter the JSON results client-side.
# Paginate with --cursor until pageInfo.hasNextPage is false.
omni documents list --include labels -o json

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
# Favorite
omni documents add-favorite <identifier>

# Unfavorite
omni documents remove-favorite <identifier>
```

## Dashboard Downloads

```bash
# Start download (async)
omni dashboards download <identifier> --body '{ "format": "pdf" }'

# Poll job status only after the start command returns a job ID
omni dashboards download-status <identifier> <jobId>
```

Formats: `pdf`, `png`

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

- [Content API](https://docs.omni.co/api/content.md) · [Documents API](https://docs.omni.co/api/documents.md) · [Folders API](https://docs.omni.co/api/folders.md) · [Labels API](https://docs.omni.co/api/labels.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md)

## Related Skills

- **omni-query** — run queries behind dashboards you've found
- **omni-content-builder** — create or update dashboards
- **omni-embed** — embed dashboards you've found in external apps
- **omni-admin** — manage permissions on documents and folders

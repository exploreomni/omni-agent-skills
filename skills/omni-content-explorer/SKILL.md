---
name: omni-content-explorer
description: Find, browse, and organize content in Omni Analytics — dashboards, workbooks, folders, and labels — using the Omni CLI. Use this skill whenever someone wants to find an existing dashboard, search for content, list workbooks, browse folders, see what dashboards exist, find popular reports, download a dashboard as PDF or PNG, favorite content, manage labels on documents, or any variant of "find the dashboard about", "what reports do we have", "show me our dashboards", "where is the sales report", or "download this dashboard".
---

# Omni Content Explorer

Find, browse, and organize Omni content — dashboards, workbooks, and folders — through the Omni CLI.

## Prerequisites

```bash
command -v omni >/dev/null || curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh
```

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

## Discovering Commands

```bash
omni content --help     # Content operations
omni documents --help   # Document operations
omni folders --help     # Folder operations
```

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
# By label
omni content list --labels finance,marketing

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
omni folders create --body '{ "name": "Q1 Reports", "scope": "organization" }'
```

## Labels

```bash
# List labels
omni labels list

# Add label to document
omni documents add-label <identifier> <labelName>

# Remove label
omni documents remove-label <identifier> <labelName>
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
omni dashboards download <dashboardId> --body '{ "format": "pdf" }'

# Poll job status
omni dashboards download-status <dashboardId> <jobId>
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

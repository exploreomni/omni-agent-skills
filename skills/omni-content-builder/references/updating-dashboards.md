# Updating an Existing Dashboard

Update the tiles, queries, filters, and visualizations on an existing dashboard with **`omni documents put <identifier>`** — a **full replacement**: you pass the complete desired state of the document, not just the fields you want to change. Any tile you omit from `queryPresentations` is removed.

> **Dashboard documents only.** `documents put` works on dashboard documents; workbook-only documents return 400.
>
> **`put` vs `update`.** `omni documents put` does the full-document replacement described here. `omni documents update` is a partial update for `name`/`description`/`identifier` only — it does not touch tiles or filters.

## Update Workflow

**Step 1 — Read the existing document** to get its current state:

```bash
omni documents get <identifier>
```

This returns the full document including `queryPresentations`, `filterConfig`, `filterOrder`, `modelId`, `name`, and other fields. Use this as your starting point.

**Step 2 — Modify the response** as needed:

- **Add a tile**: append a new entry to `queryPresentations` (keep all existing entries you want to retain).
- **Remove a tile**: drop it from `queryPresentations`.
- **Edit a tile**: modify the entry's `query`, `visConfig`, `fields`, etc.
- **Update filters**: modify `filterConfig` and `filterOrder`.

**Step 3 — Write it back** with a full document body:

```bash
omni documents put <identifier> --body '{
  "modelId": "your-model-id",
  "name": "Q1 Revenue Report",
  "facetFilters": false,
  "refreshInterval": null,
  "filterConfig": {},
  "filterOrder": [],
  "clearExistingDraft": true,
  "queryPresentations": [ ... ]
}'
```

The `queryPresentations` array uses the same structure as document creation — see [queryPresentations.md](queryPresentations.md). To add tiles without losing any, include the existing tiles **plus** the new ones (this is how you build a dashboard up additively even though `put` is a full replacement).

**Step 4 — Read back and verify** (see [validation-and-testing.md](validation-and-testing.md)). Confirm each tile's `visConfig` persisted (non-empty `spec` for charts); if a write saved the query but dropped `visType`/`config`/`fields`, treat it as a failed partial write, not success.

## Required Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `modelId` | string | Model ID for query transformation |
| `name` | string | Document name (1–254 characters) |
| `facetFilters` | boolean | Enable facet filters on the dashboard |
| `refreshInterval` | integer or null | Auto-refresh interval in seconds (min 60), or `null` to disable |
| `filterConfig` | object | Dashboard filter configuration — pass `{}` for no filters |
| `filterOrder` | array | Ordered filter IDs — pass `[]` for no filters |
| `queryPresentations` | array | At least one query presentation required (same structure as document creation) |

## Optional Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `clearExistingDraft` | boolean | Discard existing draft before updating. **Required when the published document has a draft** — otherwise returns 409 Conflict. |
| `documentMetadata` | object | Presentation settings including filter collapsibility |

## Caveats

- **Full replacement**: every `queryPresentation` you include becomes a tile; any tile you omit is removed. Always start from the existing document's `queryPresentations` and modify from there.
- **Draft conflict**: published documents with existing drafts return 409 unless `clearExistingDraft: true` is set.
- **Import is not an update fallback**: `omni unstable documents-import` creates a separate document, so it is not a safe way to add tiles to an existing dashboard identifier.
- See also [Caveats When Reusing queryPresentations](queryPresentations.md#caveats-when-reusing-querypresentations) (e.g., stripping `model_extension_id`).

## Failure Handling

**Broken query-level filter.** If query validation fails before the update with a server-side filter parsing error, do not save that broken filter into the dashboard. Validate the unfiltered base query once to prove the fields/model are correct. If the request can be satisfied with a dashboard-level `filterConfig` instead of a tile-level query filter, use that path and verify `filterConfig`, `filterOrder`, and the tile queries by reading the dashboard back. Otherwise report that the requested filtered tile is blocked by query-filter parsing and that the dashboard was left unchanged.

**Server-side document/filter error on write.** If the `put` fails with a server-side filter or document validation error, do not keep probing with multiple filter strings or `documents-import` — these errors can be triggered by pre-existing dashboard filters in the stored document even when the new tile is valid. Preserve the original dashboard, report the exact error, and ask the user whether to rebuild/clean the dashboard state.

**Partial write (viz fields dropped).** After the update succeeds, read the document back before declaring success. If the API saved the tile query but returned `null`/omitted required presentation fields such as `visType`, `fields`, or `config`, treat it as a failed partial write. This applies even if the original tile also omits those fields in readback; chart/KPI tiles need their own renderer/config fields to be observable. Make one bounded rollback attempt by restoring the original document payload from Step 1, then report the exact missing fields and whether rollback succeeded. Do not leave a known-broken table/KPI fallback in place and call it done. `omni documents get-queries` and `omni query run` verify the data query only; they do **not** prove Omni persisted the visualization renderer/config, so do not use them to override a `documents get` readback that shows missing presentation fields.

# Request-level options (outside `query`)

These keys sit at the **top level** of the body, beside `query`, not inside it. **The `query` object is permissive — a key you misplace inside `query` (e.g. `resultType`, `branchId`, `cache`) is silently dropped, not rejected**, so the call "succeeds" while ignoring your option. The tell-tale for a misplaced `resultType` is getting the base64-Arrow envelope back when you asked for JSON/CSV.

| Option | Description |
|--------|-------------|
| `resultType` | Output format: `csv`, `xlsx`, or `json`. **Top-level only** — inside `query` it's silently ignored and you get Arrow. Omit for the default base64 Arrow response. |
| `cache` | Cache policy: `Standard` (default), `SkipRequery`, `SkipCache`, `SkipCacheAndRebuildExtracts` (also rebuilds the extracts the query reads from). |
| `userId` | Run as another user (org-scoped API keys); also the `--user-id` flag. |
| `branchId` | Run against a model **branch** (validate draft model changes on live data). Must be a branch of the same shared model. |
| `planOnly` | Return the execution plan **without running** the query (validate/debug at no warehouse cost). Cannot combine with `resultType`. |
| `formatResults` | On exports, emit **formatted** values (e.g. `$1,234.56`) vs. raw. Requires `resultType`; ignored for Arrow. |
| `timezone` | Per-request timezone override (IANA id). Requires the connection setting `allowsUserSpecificTimezones` **and** the org setting `allowsDocumentCanUseTimezoneOverride`; silently no-ops if either is off. |
| `workbookUrl` | Also create an ephemeral workbook for the query, so the user gets an "open in Omni" link. On CLI ≥ 1.3.0 pass `--workbook` instead of setting it by hand. The link comes back in a response **header**, not the body: the CLI prints it under human output, or as `{"workbookUrl": …}` on **stderr** in JSON mode. If the (target) user lacks the workbooks permission on the model, the query still succeeds and the link is **silently omitted** — no link means no permission, not a failure to retry. |

## Confirming an aggregate table was used

When the model declares aggregate tables (`materialized_query`), plan the query with `planOnly: true` and `cache: SkipCache` and read `summary.display_sql`. A query served from an aggregate table is headed `-- Query rewritten to use materialized view "<view>"` with the original SQL commented out beneath; no header means the fact table was used. On a composite topic each member query is matched separately and the header names the first table used, so read the SQL for the other members. Why a query misses is covered in `omni-model-builder`'s aggregate-awareness reference.

## Showing results to a person (CLI ≥ 1.3.0)

In human mode `query run` renders a formatted table using the model's labels and number formats, and polls unfinished jobs itself. `--chart` draws the same result as a terminal bar table (`--chart-value` picks measures, `--chart-rows` caps rows); it still draws when piped, at 80 columns, so it fits a chat code block. `--chart` drops a `resultType` from the body and is refused with `-o json`. Neither view carries the job envelope — **validate with a JSON-mode run** (see [Handling and Validating Results](../SKILL.md#handling-and-validating-results) in SKILL.md), then render for the user.

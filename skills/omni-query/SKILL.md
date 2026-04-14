---
name: omni-query
description: Run queries against Omni Analytics' semantic layer using the Omni CLI, interpret results, and chain queries for multi-step analysis. Use this skill whenever someone wants to query data through Omni, run a report, get metrics, pull numbers, analyze data, ask "how many", "what's the trend", "show me the data", retrieve dashboard query results, or perform any data retrieval through Omni's query engine. Also use when someone wants to programmatically extract data from an existing Omni dashboard or workbook.
---

# Omni Query

Run queries against Omni's semantic layer via the Omni CLI. Omni translates field selections into optimized SQL — you specify what you want (dimensions, measures, filters), not how to get it.

> **Tip**: Use `omni-model-explorer` first if you don't know the available topics and fields.

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

You also need a **model ID** and knowledge of available **topics and fields**.

## Discovering Commands

```bash
omni query --help              # List query operations
omni query run --help          # Show flags for running a query
omni ai --help                 # AI-powered query generation
```

## Running a Query

### Basic Query

```bash
omni query run --body '{
  "query": {
    "modelId": "your-model-id",
    "table": "order_items",
    "fields": [
      "order_items.created_at[month]",
      "order_items.total_revenue"
    ],
    "limit": 100,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

### Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `modelId` | Yes | UUID of the Omni model |
| `table` | Yes | Base view name (the `FROM` clause) |
| `fields` | Yes | Array of `view.field_name` references |
| `join_paths_from_topic_name` | Recommended | Topic for join resolution |
| `limit` | No | Row limit (default 1000, max 50000, `null` for unlimited) |
| `sorts` | No | Array of sort objects |
| `filters` | No | Filter object |
| `pivots` | No | Array of field names to pivot on |

### Field Naming

Fields use `view_name.field_name`. Date fields support timeframe brackets:

```
users.created_at[date]      — Daily
users.created_at[week]      — Weekly
users.created_at[month]     — Monthly
users.created_at[quarter]   — Quarterly
users.created_at[year]      — Yearly
```

### Sorts

```json
"sorts": [
  { "column_name": "order_items.total_revenue", "sort_descending": true }
]
```

### Filters

```json
"filters": {
  "order_items.created_at": "last 90 days",
  "order_items.status": "complete",
  "users.state": "California,New York"
}
```

Expressions: `"last 90 days"`, `"this quarter"`, `"2024-01-01 to 2024-12-31"`, `"not California"`, `"null"`, `"not null"`, `">100"`, `"between 10 and 100"`, `"contains sales"`, `"starts with A"`. See [references/filter-expressions.md](references/filter-expressions.md) for the complete expression syntax reference.

### Pivots

```json
{
  "query": {
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.count"],
    "pivots": ["order_items.status"],
    "join_paths_from_topic_name": "order_items"
  }
}
```

## Handling and Validating Results

Default response: base64-encoded Apache Arrow table. Arrow results are binary — you cannot parse individual row data from the raw response. To verify a query returned data, check `summary.row_count` in the response.

For human-readable results, request CSV instead:

```json
{ "query": { ... }, "resultType": "csv" }
```

### Result Validation

Every query response should be checked before trusting the results or presenting them to the user.

**Check for errors:**
- If the response contains an `error` key, the query failed. Common causes: bad field name, missing join path, malformed filter expression, permission error.
- If the response contains `remaining_job_ids`, the query is still running — poll with `omni query wait` before checking results.

**Check row count:**
- `summary.row_count == 0` — the query returned no data. This may be valid (e.g., no data in the filter range) but is worth flagging to the user. Common causes: overly restrictive filters, wrong date range, field that doesn't match any rows.
- `summary.row_count` equals the `limit` you set — results may be truncated. If the user needs complete data, re-run with a higher limit or `null` for unlimited.

**Spot-check data with CSV:**

When accuracy matters, request CSV and scan the output:

```bash
omni query run --body '{
  "query": { ... },
  "resultType": "csv"
}'
```

Check that:
- Column headers match the fields you requested
- Values are in expected ranges (e.g., revenue isn't negative, dates aren't in the future)
- Aggregations make sense (e.g., a count isn't returning a sum)

**Validate filter behavior:**

If your query includes filters, verify they're being applied:

```bash
# Run the same query without filters
omni query run --body '{ "query": { ... (no filters) ... }, "resultType": "csv" }'

# Compare row counts — filtered should be <= unfiltered
```

If both queries return the same row count, the filter may not be binding (wrong field name, unsupported expression, or the known bug where boolean filters are dropped with pivots).

### Validation Checklist

| Check | How | When |
|-------|-----|------|
| No error in response | Check for `error` key | Every query |
| Data was returned | `summary.row_count > 0` | Every query |
| Results not truncated | `row_count < limit` | When completeness matters |
| Columns are correct | CSV column headers match requested fields | When building dashboards or reports |
| Values are reasonable | Spot-check CSV output | When presenting to users |
| Filters are applied | Compare filtered vs unfiltered row counts | When using filters |
| Long-running query completed | No `remaining_job_ids` in final response | Queries on large tables |

### Decoding Arrow Results

```python
import base64, pyarrow as pa
arrow_bytes = base64.b64decode(response["data"])
reader = pa.ipc.open_stream(arrow_bytes)
df = reader.read_all().to_pandas()
```

### Long-Running Queries

If the response includes `remaining_job_ids`, poll until complete:

```bash
omni query wait --job-ids job-id-1,job-id-2
```

## Running Queries from Dashboards

Extract and re-run queries powering existing dashboards:

```bash
# Get all queries from a dashboard
omni documents get-queries <dashboardId>

# Run as a specific user
omni query run --body '{ "query": { ... }, "userId": "user-uuid-here" }'

# Cache policy (valid values: Standard, SkipRequery, SkipCache)
omni query run --body '{ "query": { ... }, "cache": "SkipCache" }'
```

## AI-Powered Query Generation

Instead of constructing query JSON manually, you can describe what you want in natural language and let Omni's AI generate the query.

### Generate Query (synchronous)

The fastest path — returns a generated query JSON synchronously. Pass `--run-query false` to get only the query structure without executing it (default runs the query).

```bash
# Just generate the query JSON (no execution)
omni ai generate-query your-model-id "Show me revenue by month" --run-query false
```

Response:

```json
{
  "query": {
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "table": "order_items",
    "filters": {},
    "sorts": [{"column_name": "order_items.created_at[month]", "sort_descending": false}],
    "limit": 500
  },
  "topic": "order_items",
  "error": null
}
```

```bash
# Generate and execute in one call
omni ai generate-query your-model-id "Top 10 customers by lifetime spend"
```

Optional flags:
- `--branch-id` — test against a specific model branch
- `--current-topic-name` — constrain topic selection to a specific topic

### Pick Topic

Check which topic the AI would select for a question, without generating a full query:

```bash
omni ai pick-topic your-model-id "How many users signed up last month?"
```

### Agentic Queries (async)

For the full Blobby experience — multi-step analysis, tool use, and topic selection as the AI would actually behave in production. This is async: submit a job, poll for status, then retrieve the result.

```bash
# 1. Submit a job
omni ai job-submit your-model-id "Analyze revenue trends and identify our fastest growing product category"
# → returns { "jobId": "job-uuid", "conversationId": "conv-uuid" }

# 2. Poll for completion (QUEUED → EXECUTING → COMPLETE)
omni ai job-status <jobId>

# 3. Get the result
omni ai job-result <jobId>
```

The result contains an `actions` array with each step the AI took — look for actions with `type: "generate_query"` to extract the generated queries. The response also includes `resultSummary` with the AI's narrative interpretation.

Additional job commands:
- `omni ai job-cancel <jobId>` — cancel a running job
- `omni ai job-visualization <jobId>` — get the visualization output

### When to Use Which Approach

| Approach | Best For |
|----------|----------|
| `omni query run` | You know exactly which fields, filters, and sorts you need |
| `omni ai generate-query` | Translating a natural language question into a single query |
| `omni ai job-submit` | Complex questions that may need multiple queries or multi-step reasoning |

## Multi-Step Analysis Pattern

For complex analysis, chain queries:

1. **Broad query** — understand the shape of the data
2. **Inspect results** — identify interesting segments or patterns
3. **Focused follow-ups** — filter based on findings
4. **Synthesize** — combine results into a narrative

## Common Query Patterns

**Time Series**: fields + date dimension + ascending sort + date filter

**Top N**: fields + metric + descending sort + limit

**Aggregation with Breakdown**: multiple dimensions + multiple measures + descending sort by key metric

## Known Bugs

- **`IS_NOT_NULL` filter generates `IS NULL`** (reported Omni bug) — workaround: invert the filter logic or use the base view to apply the filter differently.
- **Boolean filters may be silently dropped** when a `pivots` array is present — if boolean filters aren't applying, remove the pivot and test again.

## Linking to Results

Queries are ephemeral — there is no persistent URL for a query result. To give the user a shareable link:

- **For existing dashboards**: `{OMNI_BASE_URL}/dashboards/{identifier}` (the `identifier` comes from the document API response)
- **For new analysis**: Create a document via `omni-content-builder` with the query as a `queryPresentation`, then share `{OMNI_BASE_URL}/dashboards/{identifier}`

## Docs Reference

- [Query API](https://docs.omni.co/api/queries.md) · [Running Document Queries](https://docs.omni.co/guides/run-document-queries.md) · [Querying Documentation](https://docs.omni.co/analyze-explore/querying.md) · [Filter Syntax](https://docs.omni.co/modeling/filters.md)

## Related Skills

- **omni-model-explorer** — discover fields and topics before querying
- **omni-content-explorer** — find dashboards whose queries you can extract
- **omni-content-builder** — turn query results into dashboards
- **omni-ai-eval** — benchmark and test AI query generation accuracy

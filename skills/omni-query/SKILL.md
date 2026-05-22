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
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>
```

You also need a **model ID** and knowledge of available **topics and fields**.

## Discovering Commands

```bash
omni query --help              # List query operations
omni query run --help          # Show flags for running a query
omni ai --help                 # AI-powered query generation
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

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

**Pivoted queries reject `limit: null`** — pass an explicit numeric limit (e.g., `5000`). Unlimited is only allowed when `pivots[]` is empty.

### Table Calculations

Post-query computed columns (running totals, % of total, ratios, conditionals). Authored as AST objects in `calculations[]`. The query API requires the parsed AST — it does **not** accept the workbook-frontend `{name, formula}` shape.

Minimum-viable calc:

```json
{
  "query": {
    "fields": ["orders.month", "orders.total_revenue", "calc_pct"],
    "calculations": [{
      "calc_name": "calc_pct",
      "label": "% of Total",
      "format": "0.0%",
      "sql_expression": {
        "type": "call",
        "operator": "Omni.OMNI_PERCENT_OF_TOTAL",
        "operands": [
          { "type": "field", "field_name": "orders.total_revenue", "for_calc": true }
        ]
      }
    }]
  }
}
```

**The #1 gotcha:** `calc_name` must also appear in `query.fields` (and the outer `queryPresentation.fields` for dashboard tiles). A calc defined in `calculations[]` but absent from `fields` is computed but never rendered.

The five quick-template operators (each takes one `field` operand with `for_calc: true`):
`Omni.OMNI_PERCENT_OF_TOTAL`, `Omni.OMNI_PERCENT_OF_PREVIOUS`, `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `Omni.OMNI_RUNNING_TOTAL`, `Omni.OMNI_RANK`.

At execution, calcs compile into an outer `SELECT` wrapping the base aggregation; window-style operators emit `... OVER (...)` there, so the shared data model never needs window functions to support them. In pivoted queries, template operators auto-partition by the pivot column for per-segment series; set `outside_pivot: true` and wrap an aggregator around `OMNI_PIVOT_OFFSET` for a row-summary that sweeps across pivot columns.

For arithmetic, conditionals, chained calcs, the full operator catalog (`Omni.*` and `SqlStdOperatorTable.*`), AST node types, validation rules, and the recommended round-trip strategy for unfamiliar calcs, see [references/table-calculations.md](references/table-calculations.md).

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
omni query wait --jobids job-id-1,job-id-2
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

### Using Job Results in a Dashboard

The query object inside a job result is **not directly usable** as a dashboard `queryPresentation` — it requires a transformation. The key issue is that Blobby co-emits a `userEditedSQL` string alongside the structured `calculations[]` on most responses. When both are present, `userEditedSQL` takes precedence and shadows the structured calc. Additionally, `userEditedSQL` uses `${TopicDisplayName}` token substitution (e.g. `${Order Items}`) which is not supported by the dashboard tile renderer.

**Transformation algorithm:**

```python
def job_result_to_presentation(name, topic_display_name, view_name, job_result):
    gqs = [a for a in job_result["actions"] if a["type"] == "generate_query"]
    q = gqs[-1]["result"]["query"]

    # 1. Strip presentation cruft that shouldn't carry into a new document
    for k in ("metadata", "parsed", "model_extension_id"):
        q.pop(k, None)

    # 2. Handle userEditedSQL
    if q.get("calculations"):
        # Structured calc exists — strip userEditedSQL so it renders
        q.pop("userEditedSQL", None)
    else:
        # No structured calc — keep userEditedSQL but fix the topic-name token
        # (dashboard tile renderer doesn't resolve topic display names)
        if q.get("userEditedSQL"):
            q["userEditedSQL"] = q["userEditedSQL"].replace(
                f"${{{topic_display_name}}}", f"${{{view_name}}}"
            )

    return {
        "name": name,
        "topicName": topic_display_name,
        "prefersChart": False,
        "visType": "basic",
        "fields": q.get("fields", []),
        "query": q,
        "config": {},
    }
```

**Why conditional:** when `calculations[]` is empty, Blobby routes the entire calc through `userEditedSQL` and names the output column in `fields[]` using the `view_name.column_name` convention (e.g. `ecomm__order_items.revenue_label`). Stripping `userEditedSQL` in this case causes a "No such field" error because the backing calc definition is missing. Keeping `userEditedSQL` (with the token fix) is the safe path.

**The `${TopicDisplayName}` substitution asymmetry:** `omni query run` and `omni ai job-submit` both resolve topic display names in `userEditedSQL` (e.g. `${Order Items}`), but the dashboard tile renderer only resolves view names (e.g. `${ecomm__order_items}`). Always rewrite the token when keeping `userEditedSQL` for dashboard use.

### When to Use Which Approach

| Approach | Best For |
|----------|----------|
| `omni query run` | You know exactly which fields, filters, and sorts you need |
| `omni ai generate-query --run-query=false` | Getting a query AST shape to inspect or hand-edit before running |
| `omni ai generate-query --run-query=true` | Simple dimension/measure queries where you want a synchronous response |
| `omni ai job-submit` | **Any query involving calculations — prefer this for reliability.** Also best for complex multi-step questions. |

**Prefer `job-submit` over `generate-query` when calculations are involved.** A 22-prompt bake-off across table-calculation scenarios found the two endpoints produce identical structured `calculations[]` output on 14/22 prompts. On the 8 divergences, `job-submit` was more reliable: its SQL fallback (`userEditedSQL`) catches cases where the structured calc has wrong operands (e.g. DATEDIF operand order) and would silently return blanks. `generate-query` occasionally picks a more idiomatic operator but at the cost of more silent failures. When the formatting bug ([#51752](https://github.com/exploreomni/omni/issues/51752)) is fixed, `job-submit` will be the clear default for any calc-bearing prompt.

`generate-query --run-query=false` remains useful as a "draft AST" tool when you want to inspect or modify the query structure before executing — see eval #6.

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

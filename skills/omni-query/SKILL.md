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

## Known Issues & Safe Defaults

- When the user asks for a **calculated column**, **table calculation**, **running total**, **moving average**, **percent change**, **row total**, **tier label**, **VLOOKUP**, **SUMIF**, or **date difference**, satisfy it with a `calculations[]` table calc selected in `query.fields`. Do not substitute an existing model field, `userEditedSQL`, client-side math, or a narrative-only explanation unless the user explicitly asks for that alternative.
- For table-calc prompts, keep the final answer auditable: include a compact query JSON excerpt showing `query.fields`, `calculations[]`, relevant `pivots[]`/`limit`, and the validation result. Long CSV output can bury the important query shape; show a few result rows and the reusable query shape.
- Do not paraphrase `sql_expression` in the final answer with placeholders such as `{ "OMNI_OFFSET_MULTI over": "field" }` or prose like "computed via `OMNI_RUNNING_TOTAL`." If you include reusable query JSON, copy the actual executed `calculations[]` object with operators and operands intact, or explicitly say you are omitting the full JSON for brevity.
- Do not call a table-calc task complete until your final answer names the calc column and shows that same `calc_name` in both `query.fields` and `calculations[]`. This applies even for simple built-in operators like `OMNI_RUNNING_TOTAL`.
- If a calc query succeeds but the calc column is blank, treat it as a failed calc until proven otherwise. Re-check operand order, `for_calc`, date truncation, `outside_pivot`, and whether the `calc_name` appears in `query.fields`.
- Prefer the documented Omni calc operators over lower-level raw SQL/window ASTs when a template exists. For example, use `Omni.OMNI_RUNNING_TOTAL`, `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, and `Omni.OMNI_FX_AVERAGE(Omni.OMNI_OFFSET_MULTI(...))` for moving averages instead of hand-authored `window_call`/`LAG` when the prompt asks for a table calculation.

## Build queries on a topic

Prefer building every query **on a topic**, not a bare base view. Topics carry the governed joins, labels, and access — and **a query not built on a topic is not accessible to restricted queriers/viewers** (it works for you as a modeler/admin but silently fails for restricted roles). Set the query `table` to the topic's base view and pass `join_paths_from_topic_name: <topic>`.

**How the join map resolves joined-view fields.** `table` stays the topic's **base view**; `join_paths_from_topic_name` lets the topic's join map reach *joined*-view fields from it — e.g. to select `users.state` on an `order_items`-based topic, `table` stays `order_items` and the join comes from the topic; you do **not** set `table: users`. Omit `join_paths_from_topic_name` (or point `table` at a non-base view) and joined-view fields may fail to resolve or join wrong. Confirm the base view and every reachable join with `omni models get-topic <modelId> <topic>` — its `base_view_name` and `join_via_map` show the base view and the join path to each reachable view. (This is the canonical topic-query shape; `omni-content-builder` tiles and `omni-model-builder` validation queries use it too.)

**Decide where the query should come from:**
1. **An existing topic answers it** (its base view + a join-reachable view) → query that topic.
2. **The field is on a join-reachable view but the topic doesn't expose it / lacks the join** → propose *extending* the topic (add the relationship/join), then build it via `omni-model-builder`.
3. **Fundamentally different subject, constraints, or audience** → propose a *new* topic (see the "new topic vs extend" criteria in `omni-model-builder`). Prompt the requestor first, and build it on a branch.

**Fallback:** a query can run on a bare base view with no topic — it traverses joins via the global `relationships` file — but in a dashboard that tile is **invisible to restricted queriers/viewers**. Use only when no topic fits *and* the audience isn't restricted.

When the conclusion is "build or modify a topic," hand off to **`omni-model-builder`** to do it right.

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

If a date filter string fails with an API error like `Cannot use 'in' operator
to search for 'query_id' in last 12 months`, keep the query semantic and retry
with the typed date-filter object shape instead of dropping the filter:

```json
"filters": {
  "order_items.created_at": {
    "type": "date",
    "kind": "TIME_FOR_INTERVAL_DURATION",
    "left_side": "12 months ago",
    "right_side": "12 months",
    "ui_type": "PAST"
  }
}
```

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

When reporting a successful table-calc query, include the minimal query JSON or an explicit field list that shows both `query.fields` and `calculations[]`. Do not only show the calculation object; the user needs to verify that the calc column was actually requested in `fields`. Keep result output short enough that the AST proof remains visible.

The five quick-template operators (each takes one `field` operand with `for_calc: true`):
`Omni.OMNI_PERCENT_OF_TOTAL`, `Omni.OMNI_PERCENT_OF_PREVIOUS`, `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `Omni.OMNI_RUNNING_TOTAL`, `Omni.OMNI_RANK`.

For these template operators, the final answer should include the exact selected
calc shape, not just the result table. Show `fields: [..., "<calc_name>"]` and
`calculations: [{ "calc_name": "...", "sql_expression": { "operator": "...",
"operands": [{ "field_name": "...", "for_calc": true }] } }]` so the user can
reuse or audit the query.

Use `omni query run` with a hand-authored or copied AST when the user explicitly asks for a calculated column/table calculation. Do not route simple table-calc prompts through `omni ai job-submit`; agentic jobs can fall back to `userEditedSQL`, omit calc metadata, or leave a generated query pending. Reserve `job-submit` for requests that explicitly ask for the async agentic workflow or for broad multi-step analysis.

Query tasks are read-only unless the user explicitly asks to change the model.
If a field appears missing, inspect topics/dashboard queries and use the right
model/topic/branch or report the missing-field blocker. Do not create branches,
add measures, or edit YAML just to make a query work. Do not compute requested
table calculations client-side after the fact; the result must come from
`calculations[]` selected in `query.fields`, or you should report why the Omni
calc could not run. If the model already contains an equivalent field such as
`users.tier_label` or `order_items.days_to_ship`, do not use it to satisfy a
request for a calculated column; build and validate the table calc unless the
user explicitly asks to use the existing model field.

Quick recipes for common calc requests:

- **Percent of total**: add a calc using `Omni.OMNI_PERCENT_OF_TOTAL` with one `for_calc: true` operand pointing at the selected measure field; set `format: "0.0%"`; include the calc name in `query.fields`.
- **Running total**: add a calc using `Omni.OMNI_RUNNING_TOTAL` with one `for_calc: true` field operand. Sort the time dimension ascending before presenting values; do not sort descending and then reverse/recompute the running total outside Omni. In the final answer, include a compact query shape that shows the running-total `calc_name` in `fields` and the `OMNI_RUNNING_TOTAL` `calculations[]` entry; a result table plus prose is not enough for a reusable query answer.
- **Trailing 3-period moving average**: if you are unsure of the exact AST, first call `omni ai generate-query <modelId> "monthly revenue with a trailing 3-month moving average" --run-query=false`, copy the structured calculation, then run it directly. The expected shape is `Omni.OMNI_FX_AVERAGE` over `Omni.OMNI_OFFSET_MULTI(field, -2, 0, 3, 1)`. If the helper returns a raw `window_call`, rewrite it to this canonical Omni calc shape unless the user specifically asked for a custom SQL window not expressible with Omni calc operators.
- **Month-over-month % change**: add a calc using `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS` with the same single `for_calc: true` revenue operand; sort the date field ascending; set `format: "0.0%"`; do not use `omni_period_pivot`, raw SQL, or a hand-authored `LAG` window when the template operator fits.
- **Row total across pivot columns**: for a pivoted query, set a numeric `limit` and add a calc with `outside_pivot: true`, `Omni.OMNI_FX_SUM`, and `Omni.OMNI_PIVOT_OFFSET(field, 0, 0, 1, 50)` to sweep across pivot columns. Include the row-total `calc_name` in `query.fields`; a pivoted query with `limit: null` is invalid.
- **Multi-branch tier labels**: use `Omni.OMNI_FX_IFS`, not an existing model field or `SqlStdOperatorTable.CASE`, for prompts like `High if revenue > 10000, Mid if > 1000, else Low`. `OMNI_FX_IFS` operands alternate `(condition, value)`. Represent the default branch as a final tautology such as `SqlStdOperatorTable.EQUALS(1, 1)` followed by `"Low"`. Build labels like `"High - Acme Corp"` with nested binary `Omni.OMNI_FX_AMPERSAND` calls: `(tier & " - ") & <name field>`. If the tier depends on a grouped measure, create two calcs: one for the tier and one for the concatenated label.
- **SUMIF-style filtered total broadcast on every row**: use `Omni.OMNI_FX_SUM_IF` (underscore between `SUM` and `IF`). Both the criteria range and sum range must be full-column `Omni.OMNI_OFFSET_MULTI` calls with `(field, -536870911, 0, 1073741823, 1)`. The criterion is a string literal like `"Complete"`, not a SQL predicate.
- **VLOOKUP-style in-result lookup**: first attempt `Omni.OMNI_FX_VLOOKUP` with four operands: lookup value, key field, full-column `OMNI_OFFSET_MULTI` over the key field, and a 1-based column number into `query.fields` starting at the key column. Use literal nodes for static lookup values and column numbers. Validate the query. If a static string lookup like `"Complete"` fails with `No referenced query with id Complete found in query`, report that this Omni deployment is treating the string as a query reference, stop retrying VLOOKUP variants, and use the `OMNI_FX_SUM_IF` broadcast pattern when the user needs a single status revenue repeated on every row. Do not replace this with `userEditedSQL`.
- **Date difference**: use `Omni.OMNI_FX_DATEDIF` in AST order `(unit_literal, start_date, end_date)`, with the unit literal `"DAY"` and date-truncated operands such as `created_at[date]` and `shipped_at[date]`. Do not substitute a native model field unless the user asked for that existing field rather than a calculated column. A bare timestamp operand can produce blank values under `swallow_errors`; select `[date]` timeframes or cast to DATE. Filter out or separately explain null shipped dates so the validated diff column contains populated integer values.

For exact JSON AST examples, use [references/table-calculations.md](references/table-calculations.md), especially the sections on running totals, moving averages, conditional labels, pivot row totals, DATEDIF, SUM_IF, and VLOOKUP. Keep `SKILL.md` as the workflow guardrail and the reference file as the source of detailed shapes.

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

Before presenting an async job answer, inspect the `actions[]` entries. A job can reach `COMPLETE` while an individual `generate_query` action has `status: "pending"` or no `csvResult`; the narrative may then describe a query that was generated but not executed. If a required action is pending, do not treat the job summary as final. Run or regenerate that specific query, or continue the same analysis with another async job, then present only validated results.

Additional job commands:
- `omni ai job-cancel <jobId>` — cancel a running job
- `omni ai job-visualization <jobId>` — get the visualization output

### Using Job Results in a Dashboard

The query object inside a job result is **not directly usable** as a dashboard `queryPresentation` — it requires a transformation. Key rules:

- **Always strip `userEditedSQL`** — keeping it silently bypasses `always_where_sql`, `always_where_filters`, and row-level access controls. The `${Order Items}` topic-name token it contains also fails outside the job execution context.
- **When `calculations[]` is non-empty**, stripping `userEditedSQL` is sufficient — the structured calc renders correctly.
- **When `calculations[]` is empty**, Blobby authored the calc as inline SQL. The parsed AST is available in `csvResultFields` (at `result` level, not inside `result["query"]`) and can be reconstructed as a proper `calculations[]` entry. Fields whose top-level expr operator is an aggregate (`SUM`, `COUNT`, etc.) cannot be reconstructed as table calcs — add them to the model as filtered measures instead.

For the complete transformation algorithm, discriminator logic, field-ref injection, aggregate-skip handling, and sanity-check approach, see [references/job-result-to-presentation.md](references/job-result-to-presentation.md).

### When to Use Which Approach

| Approach | Best For |
|----------|----------|
| `omni query run` | You know exactly which fields, filters, and sorts you need |
| `omni query run` with `calculations[]` | Explicit table-calculation requests where you know or can copy the AST shape |
| `omni ai generate-query --run-query=false` | Getting a query AST shape to inspect or hand-edit before running |
| `omni ai generate-query --run-query=true` | Simple dimension/measure queries where you want a synchronous response |
| `omni ai job-submit` | Requests that explicitly ask for the async agentic workflow, or broad multi-step questions where Blobby should plan and execute analysis |

For explicit table-calculation work, prefer `omni query run` with `calculations[]`. If you need help discovering an unfamiliar AST shape, use `omni ai generate-query --run-query=false` to draft the query, then inspect and copy the structured `calculations[]` into a direct `query run`. Treat `job-submit` results as analysis output, not as the safest source for reusable calc JSON: job results may include `userEditedSQL`, pending generated queries, or SQL fallbacks that do not satisfy a request for a real table calc.

`generate-query --run-query=false` remains useful when you want to inspect or hand-edit the query structure before executing — see eval #6.

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
- **Some natural-language date filter strings can hit `query_id` parser errors** — retry with the typed date filter object shape shown above before abandoning the filter.

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

---
name: omni-query
description: Run queries against Omni Analytics' semantic layer using the Omni CLI, interpret results, and chain queries for multi-step analysis. Use this skill whenever someone wants to query data through Omni, run a report, get metrics, pull numbers, analyze data, ask "how many" / "what's the trend" / "show me the data", retrieve dashboard query results, extract data from an existing dashboard, or inspect the query definition behind a tile. Also use for table calculations and computed columns (running totals, percent-of-total, month-over-month / period-over-period change, moving averages, rankings), open-ended multi-step analysis via agentic AI jobs, and running raw SQL through the semantic layer — even when the user doesn't say "query" (e.g. "add a running total column", "what's our MoM growth", "analyze revenue trends"). For building or editing a dashboard or chart use omni-content-builder; for adding a field or measure to the model use omni-model-builder — this skill retrieves and computes over data.
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

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule for profile setup (`omni config init --auth oauth`) and discovering command and request-body shapes with `--schema`.

You also need a **model ID** and knowledge of available **topics and fields**.

## Discovering Commands

```bash
omni query --help              # List query operations
omni query run --help          # Show flags for running a query
omni query run --schema        # Body schema + example — but the query object renders free-form; for its shape use the examples below
omni ai --help                 # AI-powered query generation
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Known Issues & Safe Defaults

- **When handed SQL, default to reproducing its intent on a topic** — read what the SQL does (grain, measures, filters, joins), then check whether a topic can express it (`omni-model-explorer`; `omni ai pick-topic` / `omni ai generate-query --run-query=false`). Reach for raw `userEditedSQL` only when no topic fits, or when the user explicitly asks to run their SQL as-is. See *Running Raw SQL*. Don't passthrough SQL by reflex (you're not a text-to-SQL generator), and don't force-fit a topic that doesn't match.
- When the user asks for a **calculated column**, **table calculation**, **running total**, **moving average**, **percent change**, **row total**, **tier label**, **VLOOKUP**, **SUMIF**, or **date difference**, satisfy it with a `calculations[]` table calc selected in `query.fields`. Do not substitute an existing model field, `userEditedSQL`, client-side math, or a narrative-only explanation unless the user explicitly asks for that alternative.
- **Keep table-calc answers auditable.** Don't call the task complete until the final answer names the calc column and shows that same `calc_name` in **both** `query.fields` and `calculations[]` (true even for simple operators like `OMNI_RUNNING_TOTAL`). Include a compact query-JSON excerpt — `query.fields`, the real `calculations[]` object with operators/operands intact, relevant `pivots[]`/`limit`, and the validation result — not a paraphrase like `{ "OMNI_OFFSET_MULTI over": "field" }` or "computed via `OMNI_RUNNING_TOTAL`." Long CSV can bury the query shape; show a few rows plus the reusable shape, or say you're omitting the full JSON for brevity.
- If a calc query succeeds but the calc column is blank, treat it as a failed calc until proven otherwise. Re-check operand order, `for_calc`, date truncation, `outside_pivot`, and whether the `calc_name` appears in `query.fields`.
- **Don't swallow calc errors while authoring or validating.** Keep `swallow_errors: false` (the default) so a bad calc fails loudly with the real message. With `swallow_errors: true`, the column silently shows `#ERROR!` and the query still returns `COMPLETE` — easy to misread as data, a blank calc, or an engine bug. If you see `#ERROR!`, re-run with `swallow_errors: false` to surface the cause (often a referenced field missing from `query.fields`). When re-running a calc query you pulled from a document, dashboard tile, or `omni ai` job, run it **verbatim** — dropping a field the calc references manufactures an error that isn't the calc's fault. Reserve `swallow_errors: true` for a finalized tile that needs per-cell resilience, and validate it with `false` first. See `references/table-calculations.md` §5.11 & §6.5.
- Prefer the documented Omni calc operators over lower-level raw SQL/window ASTs when a template exists. For example, use `Omni.OMNI_RUNNING_TOTAL`, `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, and `Omni.OMNI_FX_AVERAGE(Omni.OMNI_OFFSET_MULTI(...))` for moving averages instead of hand-authored `window_call`/`LAG` when the prompt asks for a table calculation.
- **To read result rows, set `resultType:"json"` (or `"csv"`) at the body's TOP LEVEL — not inside `query`.** Misplacing it inside `query` is **silently ignored**: you get the default base64-Arrow streaming envelope back (unreadable rows) and waste a round trip. See *Handling and Validating Results*.

## Build queries on a topic

Prefer building every query **on a topic**, not a bare base view. Topics carry the governed joins, labels, and access — and **a query not built on a topic is not accessible to restricted queriers/viewers** (it works for you as a modeler/admin but silently fails for restricted roles). Set the query `table` to the topic's base view and pass `join_paths_from_topic_name: <topic>`. **And if *you* are a Restricted Querier** (`QUERY_TOPICS`, no `QUERY_FULL_MODEL` — check `whoami`), topic-based isn't just preferred, it's the **only** option: a bare base-view query or a raw-SQL `userEditedSQL` query needs `QUERY_FULL_MODEL`, so **every query you author and place into content must be topic-based.**

**How the join map resolves joined-view fields.** `table` stays the topic's **base view**; `join_paths_from_topic_name` lets the topic's join map reach *joined*-view fields from it — e.g. to select `users.state` on an `order_items`-based topic, `table` stays `order_items` and the join comes from the topic; you do **not** set `table: users`. Omit `join_paths_from_topic_name` (or point `table` at a non-base view) and joined-view fields may fail to resolve or join wrong. Confirm the base view and every reachable join with `omni models get-topic <modelId> <topic>` — its `base_view_name` and `join_via_map` show the base view and the join path to each reachable view. (This is the canonical topic-query shape; `omni-content-builder` tiles and `omni-model-builder` validation queries use it too.)

**Decide where the query should come from:**
1. **An existing topic answers it** (its base view + a join-reachable view) → query that topic.
2. **The field is on a join-reachable view but the topic doesn't expose it / lacks the join** → propose *extending* the topic (add the relationship/join), then build it via `omni-model-builder`.
3. **Fundamentally different subject, constraints, or audience** → propose a *new* topic (see the "new topic vs extend" criteria in `omni-model-builder`). Prompt the requestor first, and build it on a branch.

**Fallback — non-topic query pathways.** Two pathways run *outside* any topic: a **bare base view** (`table:` + the global `relationships` file for joins) and **raw SQL** (`userEditedSQL`, see "Running Raw SQL"). Both share the same caveat: topic-scoped controls — **access filters** (row-level) and **always_where** — are not applied, and in a dashboard the tile is **invisible to Viewer / Restricted Querier roles by default** (handling a restricted audience is a content-permission concern — see **`omni-content-builder`**). The two pathways differ on **object-level access grants**: a bare-view query still enforces them, but raw SQL bypasses them too (it's the most permissive pathway). Prefer a topic when one fits; reach for a non-topic pathway only when nothing else expresses the query.

When the conclusion is "build or modify a topic," hand off to **`omni-model-builder`** to do it right.

**Composite topics.** A composite (`is_composite: true` in `list-topics`) has no base view: send `join_paths_from_topic_name: <composite>` and **no `table`**. Address fields as `@_shared_dimensions_.<name>[timeframe]`, `@_shared_views_.<view>.<field>`, and `@<topic>.<view>.<measure>`; a filter keyed `@<topic>.` applies to that member topic only; the `@` is required. A dimension that belongs to one member topic can be filtered but not selected under the composite's default `unrelated_dimension_handling` — make it a shared dimension if it must be grouped on, or expect the composite to declare `null_fill` (other members' measures land on a null row) or `repeat` (they repeat on every row). `get-topic` on the composite lists the addressable surface.

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

`modelId` goes inside `query` on every `query run` (for a branch or workbook model, use that model's id), and a date field supports a timeframe in brackets: `[date]`, `[week]`, `[month]`, `[quarter]`, or `[year]`. Pivoted queries reject `limit: null`, so give them a numeric `limit`; `transposed_measures` takes an array of measure names, and `true` returns an empty result. [query-parameters.md](references/query-parameters.md) has the full parameter list, sorts, pivots, and common query patterns.

### Filters

Each `query.filters` entry maps a field name to a typed object such as `{ "type": "string", "kind": "EQUALS", "values": ["California"] }`, and a boolean filter uses `is_negative` with no `kind` or `values`. An object with the wrong properties for its type is silently ignored, so confirm that the filter bound in `summary.display_sql` (with `cache: "SkipCache"`) or by a changed row count. Operators by type are in [query-parameters.md](references/query-parameters.md#filters), and every filter type is in [filter-expressions.md](references/filter-expressions.md).

### Table Calculations

Table calculations are AST objects in `calculations[]`, and each `calc_name` must also be in `query.fields`, or the column never shows. Copy each request's AST from [table-calculations.md](references/table-calculations.md#table-calculations); after lifting a calc from an agentic job's `actions[].generate_query`, re-run your assembled query and compare its values with the job's `csvResult`. Query tasks are read-only unless the user explicitly asks to change the model: when a field seems missing, find the right model, topic, or branch or report the missing field, and do not create branches, add measures, or edit YAML to make a query work.

## Running Raw SQL (`userEditedSQL`)

Use `userEditedSQL` only when no topic can express the query or the user asks to run their SQL as-is; it is the most permissive non-topic pathway, so keep it to ad-hoc reads by privileged users and strip it from any reused or dashboard query. A `${}`-templated `userEditedSQL` from `generate-query` does not run through `query run`; treat it as a sign that the topic lacks a measure. An unbounded raw query stops at 50,000 rows whatever the envelope `limit`, so put `LIMIT` in the SQL; [raw-sql.md](references/raw-sql.md) has the body shape and options.

## Request-level options (outside `query`)

Request options such as `resultType`, `cache`, `userId`, `branchId`, and `planOnly` go at the top level of the body beside `query`; a key placed inside `query` is silently dropped. Validate with a JSON-mode run before showing the human-mode table or `--chart` view, and when `workbookUrl` or `--workbook` returns no link, the user lacks the workbooks permission, so do not retry. [request-options.md](references/request-options.md) lists every option and how to confirm an aggregate table served a query.

## Handling and Validating Results

> **`omni query run` streams NDJSON — it is NOT one JSON object.** In JSON mode (pass `-o json` when parsing — a human default from `config set-format` or `OMNI_OUTPUT_FORMAT` applies even when piped, and prints a table instead) the CLI prints **multiple JSON objects, one per line**: first a `{"jobs_submitted":{…}}` line, then one or more `{"job_id":…,"status":"COMPLETE","summary":{…}}` job lines (and, with `resultType`, the result payload). A naive `json.loads(entire_stdout)` throws `JSONDecodeError: Extra data`. **Don't write a single-object parser** — iterate lines and pick the one you need, or slurp with `jq -s` / read the **last** non-empty line. `--compact` puts each object on one tidy line.

Default response: base64-encoded Apache Arrow table. Arrow results are binary — you cannot parse individual row data from the raw response. The row count is at **`cache_metadata.num_rows`** (not `summary.row_count`). The `summary` object holds validation metadata: `invalid_calculations`, `missing_fields`, `display_sql` (the compiled SQL), `omni_sql_parse_failed`. (`--schema` won't show any of this — it describes the request body only; response shape comes from a live response. See the [`omni-api-conventions`](../../rules/omni-api-conventions.mdc) rule.)

**To read rows yourself, always set `resultType: "json"` (or `"csv"`) at the body's TOP LEVEL — then stdout is a clean, directly-parseable JSON array (or CSV), with none of the Arrow/NDJSON envelope to unpack.** This is the single reliable way to spot-check values; reaching for the default Arrow path and trying to decode rows from it is the common time-waster.

```json
{ "query": { ... }, "resultType": "csv" }
```

`resultType: "xlsx"` is also valid, but it returns a **binary** `.xlsx` file (zip-based) — like the default Arrow blob, you can't read it inline without a spreadsheet app or a library. Use it only to **deliver a file** to a person, not to inspect results. For agent-side reading, stick to `csv`/`json`.

Check every response before trusting or presenting it, using the checklist below, and flag an empty result to the user. [handling-results.md](references/handling-results.md) has the commands for each check and for decoding Arrow.

### Validation Checklist

| Check | How | When |
|-------|-----|------|
| No error in response | Check for `error` key | Every query |
| Calcs/fields valid | `summary.invalid_calculations` and `summary.missing_fields` empty | Every query (esp. with calculations) |
| Data was returned | `cache_metadata.num_rows > 0` | Every query |
| Results not truncated | `cache_metadata.num_rows < limit` | When completeness matters |
| Columns are correct | CSV column headers match requested fields | When building dashboards or reports |
| Values are reasonable | Spot-check CSV output | When presenting to users |
| Filters are applied | Compare filtered vs unfiltered row counts | When using filters |
| Long-running query completed | No `remaining_job_ids` in final response | Queries on large tables |

### Long-Running Queries

If the response includes `remaining_job_ids`, poll until complete:

```bash
omni query wait --job-ids job-id-1,job-id-2
```

JSON mode never polls for you: the stream ends at the wait window and the footer's `remaining_job_ids` is the only sign the result is incomplete. (Human-mode output on CLI ≥ 1.3.0 does poll.)

## Running Queries from Dashboards

Extract and re-run queries powering existing dashboards:

```bash
# Get all queries from a dashboard
omni documents get-queries <dashboardId>

# Run as a specific user
omni query run --body '{ "query": { ... }, "userId": "user-uuid-here" }'

# Cache policy (valid values: Standard, SkipRequery, SkipCache, SkipCacheAndRebuildExtracts)
omni query run --body '{ "query": { ... }, "cache": "SkipCache" }'
```

## AI-Powered Query Generation

Instead of constructing query JSON manually, you can describe what you want in natural language and let Omni's AI generate the query.

`omni ai generate-query <modelId> "<question>"` generates and runs a query (`--run-query false` returns only the query JSON), and `omni ai pick-topic` shows the topic the AI would pick for a question; see [ai-query-generation.md](references/ai-query-generation.md) for the response shape and flags.

### Agentic Queries (async)

Submit with `omni ai job-submit`, poll `omni ai job-status` on its `state` field, and read `omni ai job-result` (`resultSummary` is the narrative; `actions[]` holds each step). The poll loop must stop on every terminal state (`COMPLETE`, `FAILED`, `CANCELLED`) and never be a fixed-count loop that breaks only on success; before presenting the answer, check each `actions[]` entry, and if a required `generate_query` action is pending, partial, or failed, the summary is not final, so run or regenerate that query and present only validated results. [ai-query-generation.md](references/ai-query-generation.md#agentic-queries-async) has the loop code and the follow-up commands (submit feedback once per job).

### Using Job Results in a Dashboard

Before a job's query becomes a dashboard `queryPresentation`, always strip `userEditedSQL`. When `calculations[]` is empty, rebuild the calc from the result's `csvResultFields`, except aggregates such as `SUM`, which become filtered measures in the model; [job-result-to-presentation.md](references/job-result-to-presentation.md#using-job-results-in-a-dashboard) has the full algorithm.

### When to Use Which Approach

Use `omni ai job-submit` for anything non-trivial, including generating a table calc or reusable query AST (append "as a table calculation" to the prompt when you want one), and `omni ai generate-query` for simple queries or for shape-only drafts when query execution isn't permitted. The comparison table is in [ai-query-generation.md](references/ai-query-generation.md#when-to-use-which-approach).

## Multi-Step Analysis Pattern

For complex analysis, chain queries:

1. **Broad query** — understand the shape of the data
2. **Inspect results** — identify interesting segments or patterns
3. **Focused follow-ups** — filter based on findings
4. **Synthesize** — combine results into a narrative

## Known Bugs

- **Bare-string filter expressions are rejected.** `"filters": { "field": "complete" | "last 90 days" | "not null" }` returns `400 "Unable to parse data stream"` as of August 2026 (older builds returned `500 "Cannot use 'in' operator to search for 'query_id' in <value>"` — the query-reference/`field_name_in_query` probe). **Use the typed filter object** (see *Filters* above). Reproduced for value, date, null-string, number, and boolean forms.

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

# AI-Powered Query Generation

Generate a query from a natural-language question with `omni ai generate-query`, check topic selection with `omni ai pick-topic`, or run an agentic job with `omni ai job-submit`.

## Generate Query (synchronous)

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

## Pick Topic

Check which topic the AI would select for a question, without generating a full query:

```bash
omni ai pick-topic your-model-id "How many users signed up last month?"
```

## Agentic Queries (async)

For the full Blobby experience — multi-step analysis, tool use, and topic selection as the AI would actually behave in production. This is async: submit a job, poll for status, then retrieve the result.

```bash
# 1. Submit a job
JID=$(omni ai job-submit your-model-id "Analyze revenue trends; identify our fastest growing category" -o json \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["jobId"])')

# 2. Poll with EARLY EXIT on any terminal state — break on success AND on failure
while :; do
  S=$(omni ai job-status "$JID" -o json | python3 -c 'import json,sys;print((json.load(sys.stdin).get("state") or "").lower())')
  case "$S" in
    complete*)             break ;;                       # done → go fetch the result
    fail*|cancel*|error*)  echo "job $S"; break ;;        # terminal failure → STOP, do not keep sleeping
    *)                     sleep 5 ;;                      # only the non-terminal branch sleeps
  esac
done

# 3. Get the result (resultSummary = narrative; actions[] = structured output)
omni ai job-result "$JID" -o json
```

> **Poll loops must early-exit on every terminal state — never a fixed-count `for … sleep … done` that only breaks on success.** If the success filter is wrong (`status` vs `state`, `COMPLETE` vs `COMPLETED`) or the job errors, such a loop runs to the end. Use the `while :; … case … break` form above: sleep **only** in the default branch, break the instant the state is terminal (complete\* **or** fail/cancel/error). Read the field tolerantly (`state ?? status`, lowercased; `startswith("complete")` = done) so one loop survives the cross-job spelling differences below.

> **Job-status shape.** Poll **`state`** — `omni ai job-status` has **no `status` field**. States: `QUEUED` → `EXECUTING` → `DELIVERING` → terminal **`COMPLETE`** / `FAILED` / `CANCELLED`. Note it's `COMPLETE`, **not** `COMPLETED` — the model-refresh (`completed`) and `models jobs-get-status` (`COMPLETED`) flows spell it differently, so a poll loop reused across job types needs a **tolerant terminal check**: read the field as `state ?? status`, lowercase it, treat `startswith("complete")` as done and `{failed, cancelled, error}` as failed. The answer text is **`resultSummary`**; structured output is under **`actions[]`** (`type: "generate_query"` → `result.query`).

The result contains an `actions` array with each step the AI took — look for actions with `type: "generate_query"` to extract the generated queries. The response also includes `resultSummary` with the AI's narrative interpretation.

Before presenting an async job answer, inspect the `actions[]` entries. A job can reach `COMPLETE` while an individual `generate_query` action has `status: "pending"` or no `csvResult`; the narrative may then describe a query that was generated but not executed. Each action's `status` says how that step ended — `complete`, `partial` (did some of what was asked and says what is missing), `skipped`, or `failed` — and is separate from `result.status` (`success` / `error`), which only says whether the generated query ran. A `partial` action with `result.status: "success"` still answered less than was asked. If a required action is pending, partial, or failed, do not treat the job summary as final. Run or regenerate that specific query, or continue the same analysis with another async job, then present only validated results.

Additional job commands:
- `omni ai job-cancel <jobId>` — cancel a running job
- `omni ai job-visualization <jobId>` — get the visualization output
- `omni ai job-feedback-submit <jobId> --body '{"rating":"good"}'` — record a thumbs up/down on a finished job (CLI ≥ 1.2.2). `rating` is **required** (`good` / `bad`); `comment` is optional free text. Only once the poll reports `COMPLETE`/`FAILED` — any other state is a 409. Append-only and never read back, so submit once per job. With an org-scoped key, pass `--user-id` to attribute the feedback to the user the job was submitted with.

## When to Use Which Approach

| Approach | Best For |
|----------|----------|
| `omni query run` | You know exactly which fields, filters, and sorts you need |
| `omni query run` with `calculations[]` | Explicit table-calculation requests where you know or can copy the AST shape |
| `omni ai generate-query --run-query=false` | Drafting a **simple** query AST to inspect/hand-edit; **or shape-only when query execution isn't permitted** (the fallback when you can't run an agentic job) |
| `omni ai generate-query --run-query=true` | Simple dimension/measure queries where you want a synchronous response |
| `omni ai job-submit` | **Anything non-trivial** — multi-step analysis, **or generating a table calc / reusable query AST**. Lift the structured query/`calculations` from `actions[].generate_query`, then validate with `query run` |

**Steer the prompt when you know the shape:** when a table calculation is the desired or known-correct output, say so in the prompt — append "… *as a table calculation*", or name the semantics ("running total" / "% of total" / "moving average") — so the agentic job emits a real calc in `actions[].generate_query` rather than a `userEditedSQL`/SQL fallback. (The agentic-vs-`generate-query` split and the "lift the AST from `actions[].generate_query`, then validate with `query run`" rule are in the table above and in [table-calculations.md](table-calculations.md#table-calculations).)

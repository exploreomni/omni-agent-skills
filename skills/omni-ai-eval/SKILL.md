---
name: omni-ai-eval
description: Evaluate Omni AI query generation accuracy by running test prompts through the Omni CLI, comparing generated query JSON against expected results, and scoring accuracy. Use this skill whenever someone wants to evaluate Omni AI, benchmark Blobby, run regression tests, compare AI output across branches or configurations, test prompt variations, measure AI quality, run A/B tests on model changes, assess impact of context changes, or any variant of "run evals", "test Blobby", "benchmark query generation", "compare AI results", "regression test", "how accurate is the AI", or "measure the impact of my changes".
---

# Omni Eval

Run evals against Omni's AI query generation APIs — submit test prompts, capture the generated query JSON, compare it against expected results, and score accuracy across dimensions.

> **Tip**: Use `omni-ai-optimizer` to improve scores after identifying failures, and `omni-model-explorer` to discover available topics and fields for building eval cases.

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

You also need a **model ID** and an **eval set** — a file of test cases with prompts and expected query structures. See the [Eval Design Guide](https://docs.omni.co/ai/eval-design-guide) for best practices on building eval sets.

## Discovering Commands

```bash
omni ai --help    # AI operations (generate-query, jobs, pick-topic)
```

## Eval Input Format

Each eval case pairs a natural language prompt with the expected query structure. JSONL (one JSON object per line) works well for bulk runs:

```jsonl
{"id": "rev-by-month", "prompt": "Show me revenue by month", "modelId": "your-model-id", "expected": {"topic": "order_items", "fields": ["order_items.created_at[month]", "order_items.total_revenue"], "filters": {}, "sorts": [{"column_name": "order_items.created_at[month]", "sort_descending": false}]}, "tags": ["time-series"]}
{"id": "top-customers", "prompt": "Top 10 customers by spend", "modelId": "your-model-id", "expected": {"topic": "order_items", "fields": ["users.name", "order_items.total_revenue"], "filters": {}, "sorts": [{"column_name": "order_items.total_revenue", "sort_descending": true}]}, "tags": ["top-n"]}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the eval case |
| `prompt` | Yes | Natural language question to send to AI |
| `modelId` | Yes | Target model UUID |
| `expected` | Yes | Object with `topic`, `fields`, `filters`, `sorts` |
| `branchId` | No | Branch to test against |
| `currentTopicName` | No | Constrain to a specific topic |
| `tags` | No | Array of tags for filtering/grouping results |

> **Note**: JSONL is shown here, but any structured format works — CSV, JSON arrays, YAML — as long as you can iterate over cases and extract these fields.

## Running Evals: Fast Path (Generate Query API)

The synchronous generate-query endpoint is the fastest way to eval query generation. Pass `--run-query false` to get only the generated query JSON without executing it against the database.

### Single Eval Call

```bash
omni ai generate-query your-model-id "Show me revenue by month" --run-query false
```

### Response Structure

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

### Request Parameters

| Arg/Flag | Required | Description |
|----------|----------|-------------|
| `<model-id>` | Yes | UUID of the Omni model (positional arg) |
| `<prompt>` | Yes | Natural language question (positional arg) |
| `--run-query` | No | Set `false` to skip query execution (faster, default `true`) |
| `--branch-id` | No | Branch UUID for branch-specific testing |
| `--current-topic-name` | No | Constrain topic selection to a specific topic |

### Batch Loop (bash)

```bash
while IFS= read -r line; do
  id=$(echo "$line" | jq -r '.id')
  prompt=$(echo "$line" | jq -r '.prompt')
  model_id=$(echo "$line" | jq -r '.modelId')
  branch_id=$(echo "$line" | jq -r '.branchId // empty')

  branch_flag=""
  if [ -n "$branch_id" ]; then
    branch_flag="--branch-id $branch_id"
  fi

  result=$(omni ai generate-query "$model_id" "$prompt" --run-query false $branch_flag --compact)

  echo "{\"id\": \"$id\", \"generated\": $result}" >> eval_results.jsonl
done < eval_cases.jsonl
```

## Running Evals: Agentic Path (AI Jobs API)

Use the async AI Jobs API when you want to test the full agentic workflow — multi-step analysis, tool use, and topic selection as Blobby would actually behave in production.

### Submit a Job

```bash
omni ai job-submit your-model-id "Show me revenue by month"
```

Response:

```json
{
  "jobId": "job-uuid",
  "conversationId": "conv-uuid",
  "omniChatUrl": "https://yourorg.omniapp.co/chat/..."
}
```

### Poll for Completion

```bash
omni ai job-status <jobId>
```

Status progression: `QUEUED` → `EXECUTING` → `COMPLETE` (or `FAILED`). Poll with backoff (e.g., 2s, 4s, 8s) until the `state` is terminal.

### Get Result

```bash
omni ai job-result <jobId>
```

The result contains an `actions` array. Look for actions with `type: "generate_query"` to extract the query JSON:

```json
{
  "actions": [
    {
      "type": "generate_query",
      "message": "Querying revenue by month...",
      "result": {
        "queryName": "Revenue by Month",
        "query": { "fields": [...], "table": "...", "filters": {...} },
        "status": "success",
        "totalRowCount": 12
      }
    }
  ],
  "topic": "order_items",
  "resultSummary": "Here are the monthly revenue figures..."
}
```

### When to Use Which Path

| Criterion | Generate Query (Fast) | AI Jobs (Agentic) |
|-----------|----------------------|-------------------|
| Speed | Synchronous, fast | Async, slower |
| Volume | High-volume runs | Lower volume |
| Scope | Query generation only | Full agent workflow |
| Use case | Field/filter accuracy | End-to-end behavior |
| Multi-step | Single query | May generate multiple queries |

## Testing Topic Selection

Eval topic selection independently with the pick-topic endpoint:

```bash
omni ai pick-topic your-model-id "How many users signed up last month?"
```

Response:

```json
{
  "topicId": "users"
}
```

This lets you score topic selection accuracy as a separate dimension — useful when topic selection is a known weak point.

## Scoring: Structural Query Comparison

Compare the generated query JSON against the expected query across four dimensions:

| Dimension | Comparison Method | Scoring |
|-----------|------------------|---------|
| `topic` | Exact string match | pass/fail |
| `fields` | Set comparison (order-independent) | pass/fail + similarity score |
| `filters` | Key-value match (key present + value match) | pass/fail per filter key |
| `sorts` | Ordered array comparison | pass/fail |

### Example Comparison Logic (TypeScript)

```typescript
function scoreEval(expected: any, generated: any) {
  // Topic: exact match
  const topicPass = generated.topic === expected.topic;

  // Fields: set comparison (order-independent)
  const expectedFields = new Set(expected.fields);
  const generatedFields = new Set(generated.query.fields);
  const missing = [...expectedFields].filter(f => !generatedFields.has(f));
  const extra = [...generatedFields].filter(f => !expectedFields.has(f));
  const fieldsPass = missing.length === 0 && extra.length === 0;

  // Filters: key-value match
  const expectedFilters = expected.filters || {};
  const generatedFilters = generated.query.filters || {};
  const missingKeys = Object.keys(expectedFilters).filter(k => !(k in generatedFilters));
  const wrongValues = Object.keys(expectedFilters)
    .filter(k => k in generatedFilters && generatedFilters[k] !== expectedFilters[k]);
  const filtersPass = missingKeys.length === 0 && wrongValues.length === 0;

  // Sorts: ordered comparison
  const sortsPass = JSON.stringify(expected.sorts || []) ===
    JSON.stringify(generated.query.sorts || []);

  return {
    topic: topicPass,
    fields: { pass: fieldsPass, missing, extra },
    filters: { pass: filtersPass, missingKeys, wrongValues },
    sorts: sortsPass,
    allPass: topicPass && fieldsPass && filtersPass && sortsPass,
  };
}
```

### Aggregate Scoring

Compute pass rates across all eval cases:

```
Eval Results: 47/50 passed (94.0%)
  Topic:   49/50 (98.0%)
  Fields:  47/50 (94.0%)
  Filters: 48/50 (96.0%)
  Sorts:   50/50 (100.0%)
```

Per-dimension rates help pinpoint where accuracy is weakest — if topic accuracy is high but filter accuracy is low, focus `ai_context` improvements on filter-related guidance.

## A/B Comparison

Run the same eval suite with one variable changed to measure impact. This is the core workflow for understanding whether a change improves or degrades AI accuracy.

### Common Variables to Compare

- **Model branches** — pass different `--branch-id` values to test context changes on a branch before merging
- **Topic scope** — `--current-topic-name "orders"` vs omitted (auto-select)
- **Model context changes** — `ai_context`, `sample_queries`, field descriptions (apply via `omni-model-builder` on a branch, then eval against that branch)
- **Prompt wording** — same expected query, different prompt text
- **AI configuration** — model type, thinking level, or other AI parameters

### Workflow

1. Run eval suite with configuration A → save as `results_a.jsonl`
2. Run eval suite with configuration B → save as `results_b.jsonl`
3. Score both result sets
4. Compare side-by-side, checking for regressions

### Example Comparison Output

```
A/B Comparison: main vs branch/new-context
                      A (main)    B (new-context)    Delta
Overall pass rate:    88.0%       94.0%              +6.0%
Topic accuracy:       96.0%       98.0%              +2.0%
Field accuracy:       90.0%       94.0%              +4.0%
Filter accuracy:      88.0%       96.0%              +8.0%

Regressions (passed in A, failed in B):
  - rev-by-quarter: fields missing order_items.total_revenue

Improvements (failed in A, passed in B):
  - customer-count: topic now correctly selects users
  - top-products: filters now include status=complete
```

> **Important**: Always check for regressions, not just overall improvement. A net improvement that breaks previously-correct cases may indicate an `ai_context` conflict.

## Snapshotting Model State

Before running evals, snapshot the model definition so results are reproducible:

```bash
# Save model YAML
omni models yaml-get <modelId> --compact > model_snapshot_$(date +%Y%m%d).json

# Validate model integrity
omni models validate <modelId>
```

Version your eval set alongside model snapshots so you can trace which model state produced which scores.

## Known Issues & Gotchas

- **Filter comparison can be complex** — Omni supports rich filter expressions (`"last 7 days"`, `"between 10 and 100"`, `"not null"`). The structural comparison above uses exact string match on filter values. If the AI produces semantically equivalent but syntactically different expressions, you may see false failures. Consider normalizing common patterns or using a Jaccard threshold.
- **AI Jobs are async** — poll with exponential backoff. Don't hammer the status endpoint.
- **Rate limiting** — for high-volume eval runs, add a small delay between calls or batch requests.
- **`limit` field may vary** — the AI may choose different limits than expected. Consider excluding `limit` from strict comparison if it's not critical to your eval.
- **`table` vs `topic`** — the generate-query response returns `topic` as a top-level field and `table` inside the query object. These usually match but aren't always identical. Compare against the top-level `topic`.

## Docs Reference

- [AI API](https://docs.omni.co/api/ai.md) · [Query API](https://docs.omni.co/api/queries.md) · [Models API](https://docs.omni.co/api/models.md) · [Optimizing Models for AI](https://docs.omni.co/ai/optimize-models.md)

## Related Skills

- **omni-query** — run golden queries to validate expected results
- **omni-model-explorer** — discover topics and fields for building eval cases
- **omni-ai-optimizer** — improve AI accuracy based on eval findings
- **omni-model-builder** — apply context changes on branches before A/B testing

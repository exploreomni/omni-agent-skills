---
name: omni-ai-optimizer
description: Optimize your Omni Analytics model for Blobby, the Omni Agent — configure ai_context, ai_fields, sample_queries, and create AI-specific topic extensions. Use this skill whenever someone wants to improve AI accuracy in Omni, make Blobby smarter, configure AI context, add example questions, tune AI responses, set up sample queries, curate fields for AI, create AI-optimized topics, troubleshoot why Blobby gives wrong answers, or any variant of "make the AI better", "Blobby isn't answering correctly", "add context for AI", "optimize for AI", or "teach the AI about our data".
---

# Omni AI Optimizer

Optimize your Omni semantic model so Blobby (the Omni Agent) returns accurate, contextual answers.

> **Tip**: Use `omni-model-explorer` to inspect current AI context before making changes.

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

Requires **Modeler** or **Connection Admin** permissions.

## Discovering Commands

```bash
omni models --help                    # List all model operations
omni models yaml-create --help        # Show flags for writing YAML
```

## How Blobby Works

Blobby generates queries by examining:

1. **Topic structure** — which views and fields are joined
2. **Field labels and descriptions** — how fields are named
3. **`synonyms`** — alternative names for fields
4. **`ai_context`** — explicit instructions you write
5. **`ai_fields`** — which fields are visible to AI
6. **`sample_queries`** — example questions with correct queries
7. **Hidden fields** — `hidden: true` fields are excluded
8. **`ai_chat_topics`** — which topics are included/excluded from AI chat (model-level)

Impact order: ai_context > ai_fields > sample_queries > synonyms > field descriptions.

## Writing ai_context

Add via the YAML API:

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "order_transactions.topic",
  "yaml": "base_view: order_items\nlabel: Order Transactions\nai_context: |\n  Map \"revenue\" → total_revenue. Map \"orders\" → count.\n  Map \"customers\" → unique_users.\n  Status values: complete, pending, cancelled, returned.\n  Only complete orders for revenue unless specified otherwise.",
  "mode": "extension",
  "commitMessage": "Add AI context to order transactions topic"
}'
```

### What Makes Good ai_context

**Terminology mapping** — map business language to field names:

```yaml
ai_context: |
  "revenue" or "sales" → order_items.total_revenue
  "orders" → order_items.count
  "customers" → users.count or order_items.unique_users
  "AOV" → order_items.average_order_value
```

**Data nuances** — explain what isn't obvious from field names:

```yaml
ai_context: |
  Each row is a line item, not an order. One order has multiple line items.
  total_revenue already excludes returns and cancellations.
  Dates are in UTC.
```

**Behavioral guidance** — direct common patterns:

```yaml
ai_context: |
  For trends, default to weekly granularity, sort ascending.
  For "top N", sort descending and limit to 10.
```

**Persona prompting** — set the analytical perspective:

```yaml
ai_context: |
  You are the head of finance analyzing customer payment data.
  Default to monetary values in USD with 2 decimal places.
```

### Keeping Context Concise

Every token in `ai_context`, `description`, and `label` is sent to the AI on every query. Verbose values waste context window and push out other fields.

- Target 1-2 sentences per `ai_context` entry. Focus on disambiguation and gotchas, not general explanation.
- Keep labels short and human-readable — avoid redundant qualification (e.g., "Order Total Revenue Amount" → "Total Revenue").
- Rewrite long `description` values to be direct. If a description restates the field name, remove it.

## Curating Fields with ai_fields

The AI context window holds ~550 fields before truncation. If a topic approaches this limit, use `ai_fields` to curate which fields are included.

Reduce noise for large models:

```yaml
ai_fields:
  - all_views.*
  - -tag:internal
  - -distribution_centers.*

# Or explicit list
ai_fields:
  - order_items.created_at
  - order_items.total_revenue
  - order_items.count
  - users.name
  - users.state
  - products.category
```

Same operators as topic `fields`: wildcard (`*`), negation (`-`), tags (`tag:`).

## Controlling Topic Visibility with ai_chat_topics

`ai_chat_topics` is a model-level property that controls which topics Blobby can see:

- **No `ai_chat_topics` property** (default) — Blobby can query across all topics.
- **`ai_chat_topics: []`** (empty list) — Blobby cannot query any topics. This effectively disables AI chat for the model.
- **Explicit list** — only the listed topics (or tag matches) are available. Supports `all_topics`, tag selectors (`tag:customer_facing`), and negation (`-tag:internal`, `-staging_events`).

Check this first — if a topic isn't in `ai_chat_topics`, no amount of `ai_context` or `ai_fields` on it will matter. Use `omni-model-builder` to modify this property.

## Adding sample_queries

Teach Blobby by example. Build the correct query in a workbook, retrieve its structure, then add to the topic YAML:

```yaml
sample_queries:
  revenue_by_month:
    prompt: "What month has the highest revenue?"
    ai_context: "Use total_revenue grouped by month, sorted descending, limit 1"
    query:
      base_view: order_items
      fields:
        - order_items.created_at[month]
        - order_items.total_revenue
      topic: order_transactions
      limit: 1
      sorts:
        - field: order_items.total_revenue
          desc: true
```

> **Note**: When exporting queries from Omni's workbook, you'll get JSON with `table`, `join_paths_from_topic_name`, and `sorts` using `column_name`/`sort_descending`. Map these to YAML as follows:
> - `table` → `base_view`
> - `join_paths_from_topic_name` → `topic`
> - `column_name` → `field`, `sort_descending` → `desc`
> - Workbook JSON includes `filters`, `pivots`, `limit`, `column_limit` which you can include in YAML (though filter syntax requires consulting the [Model YAML API docs](https://docs.omni.co/api/models.md) directly)

Focus on questions users actually ask — check Analytics > AI usage in Omni.

## AI-Specific Topic Extensions

Create a curated topic variant for Blobby using `extends`:

```yaml
# ai_order_transactions.topic
extends: [order_items]
label: AI - Order Transactions

fields:
  - order_items.created_at
  - order_items.status
  - order_items.total_revenue
  - order_items.count
  - users.name
  - users.state
  - products.category

ai_context: |
  Curated view of order data for AI analysis.
  [detailed context here]

sample_queries:
  top_categories_last_month:
    prompt: "Top selling categories last month?"
    query:
      base_view: order_items
      fields:
        - products.category
        - order_items.total_revenue
      topic: ai_order_transactions
      limit: 10
      sorts:
        - field: order_items.total_revenue
          desc: true
```

## Improving Field Descriptions

```yaml
dimensions:
  status:
    label: Order Status
    description: >
      Current fulfillment status. Values: complete, pending, cancelled, returned.
      Use 'complete' for revenue calculations.
```

Good descriptions help both Blobby and human analysts.

### Enumerating Values for Categorical Fields

For closed-set enums, use `all_values` so Blobby knows every valid filter value:

```yaml
dimensions:
  status:
    all_values: [complete, pending, cancelled, returned]
  payment_method:
    all_values: [credit_card, debit_card, bank_transfer, paypal, gift_card]
```

For open-ended categoricals where a full list isn't practical, use `sample_values` to give representative examples:

```yaml
dimensions:
  product_category:
    sample_values: [Electronics, Clothing, Home & Garden, Sports, Books]
  city:
    sample_values: [New York, Los Angeles, Chicago, Houston, Phoenix]
```

## Adding synonyms

Map alternative names, abbreviations, and domain-specific terminology so Blobby matches user queries to the correct field. Works on both dimensions and measures.

```yaml
dimensions:
  customer_name:
    synonyms: [client, account, buyer, purchaser]
  order_date:
    synonyms: [purchase date, transaction date, order timestamp]

measures:
  total_revenue:
    synonyms: [sales, income, earnings, gross revenue, top line]
  average_order_value:
    synonyms: [AOV, avg order, basket size]
```

**Synonyms vs ai_context**: Use `synonyms` for field-level name mapping. Use `ai_context` for topic-level behavioral guidance, data nuances, and multi-field relationships.

**Pruning caveat**: When the model is large and context is tight, synonyms are pruned before descriptions. Reserve synonyms for high-value fields where users commonly use alternative names.

**Avoid redundancy**: Don't add synonyms that duplicate the field's label or field name — they add no signal and waste tokens.

## Avoiding Duplication

`ai_context` and `description` serve different audiences. `description` is human-facing (shown in the field picker and docs). `ai_context` is an AI-only hint. Don't put the same text in both — `ai_context` should add guidance the description doesn't cover (disambiguation, gotchas, when to use one field over another).

**Consolidate shared context at the view level.** If multiple fields in a view share the same `ai_context` (e.g., "all monetary values are in USD"), move it to the view-level `ai_context` instead of repeating it on each field. Field-level `ai_context` should be specific to that field.

**Example — before:**

```yaml
dimensions:
  gross_revenue:
    ai_context: "Monetary value in USD. This is revenue before refunds."
    description: "Monetary value in USD. This is revenue before refunds."
  net_revenue:
    ai_context: "Monetary value in USD. This is revenue after refunds."
    description: "Monetary value in USD. This is revenue after refunds."
```

**After:**

```yaml
ai_context: "All monetary values in this view are in USD."

dimensions:
  gross_revenue:
    ai_context: "Revenue before refunds."
    description: "Total revenue before refunds and cancellations are applied."
  net_revenue:
    ai_context: "Revenue after refunds. Use this for profitability analysis."
    description: "Total revenue after refunds and cancellations."
```

## Optimization Checklist

Prioritize high-impact changes. Improve wording without changing semantics.

1. Inspect current state with `omni-model-explorer`
2. Check model-level `ai_chat_topics` — ensure the right topics are visible to AI
3. Check AI usage dashboard for real user questions
4. Count fields — curate with `ai_fields` if approaching 550
5. Write `ai_context` mapping business terms to fields (keep to 1-2 sentences)
6. Add `synonyms` to key dimensions and measures (skip if they duplicate the label)
7. Improve field `description` and `label` values
8. Add `all_values`/`sample_values` for categorical fields
9. Add `sample_queries` for top 3-5 questions
10. Remove duplication between `ai_context` and `description`; consolidate shared context at view level
11. Consider `extends` for AI-specific topic variants
12. Test iteratively — ask Blobby and refine

## Docs Reference

- [Optimizing Models for AI](https://docs.omni.co/ai/optimize-models.md) · [Synonyms](https://docs.omni.co/modeling/dimensions/parameters/synonyms) · [Topic Parameters](https://docs.omni.co/modeling/topics/parameters.md) · [Model YAML API](https://docs.omni.co/api/models.md) · [Omni AI Overview](https://docs.omni.co/ai.md)

## Related Skills

- **omni-model-explorer** — inspect existing AI context
- **omni-model-builder** — modify views and topics
- **omni-query** — test queries to verify Blobby's output

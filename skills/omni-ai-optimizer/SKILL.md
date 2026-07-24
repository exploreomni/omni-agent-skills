---
name: omni-ai-optimizer
description: Optimize your Omni Analytics model for Blobby, the Omni Agent — configure ai_context, ai_fields, synonyms, sample_queries, and AI-specific topic extensions. Use this skill whenever someone wants to improve AI accuracy in Omni, make Blobby smarter, add AI context or example questions, curate which fields the AI sees, personalize AI context by user attribute, scope context to a model tier or agent, diagnose context-window pruning or truncation, control which topics AI can reach, troubleshoot why Blobby gives wrong answers, or any variant of "make the AI better", "Blobby isn't answering correctly", "optimize for AI", or "teach the AI about our data".
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
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

Requires **Modeler** or **Connection Admin** permissions.

## Discovering Commands

```bash
omni models --help                    # List all model operations
omni models yaml-create --help        # Show flags for writing YAML
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Safe Model Write Defaults

- **Branch first** — never write AI optimization YAML directly to the shared model unless the user explicitly asks for a production change. Create or use a model branch, then pass the branch id to `omni models yaml-create`.
- **Read before writing** — inspect the current topic/view YAML before adding `ai_context`, `ai_fields`, `sample_queries`, descriptions, or synonyms. If the requested optimization already exists, report that it is already configured instead of duplicating it.
- **Topic requests stay on topics** — when the user asks to improve a topic, prefer topic-level `ai_context`, `ai_fields`, or `sample_queries`. Use field-level `synonyms` only when the request is clearly about alternate names for one specific field.
- **Do not add "supporting" synonyms after a complete topic mapping** — for requests like "Blobby confuses revenue with order count" or "map these terms correctly", if topic-level `ai_context` already maps the business terms to the correct fields and includes the needed negative guardrails, stop and report that no duplicate write is needed. Adding field-level synonyms in that case is redundant and increases prompt/token surface.
- **Create branches with `--name`** — `omni models create-branch <model-id> --name <branch-name>` does not accept a JSON `--body`.

## How Blobby Works

### Context priority order

Omni assembles the context window in this order:

1. **Context and tuning pre-built by Omni Engineering**
2. **`ai_context`** on the model, topics, and views
3. **Topic `description`**
4. **Topic `name` and `base_view`**
5. **Prioritized field properties** — `name` (fully qualified, `view.field`) and field `ai_context`. Never pruned.
6. **Pruned field properties** — everything else, dropped in the order below when space runs short.

`hidden: true` fields are excluded entirely. `ai_chat_topics` (model-level) controls which topics Blobby can see at all.

### Pruning order

When a topic's metadata exceeds its allotment, Omni removes properties **lowest priority first**, clearing each one from *every* field before moving to the next:

`all_values` → `sql` → `sample_values` → `description` → `group_label` → `label` → `aggregate_type` → `data_type` → `synonyms`

Two consequences worth internalizing:

- **`all_values` goes first**, because the AI can fetch a field's values on demand. **`synonyms` go last**, because they do the most work matching user phrasing to fields.
- **`ai_context` is never pruned** when Omni assembles context for a specific topic — at any level (model, topic, view, field). If it still doesn't fit, Omni drops whole views from model search, and past that the **request fails with an error**. Bloated `ai_context` is not a soft cost — it can starve field metadata and break queries outright. The one exception is *topic selection*, where view-level `ai_context` is trimmed first (see the caps table below).

### Context is guidance, not instruction

All context is passed to the LLM together, and the LLM decides how to weight it:

- **Model-level `ai_context` does not reliably override topic-level `ai_context`.** Don't design around precedence that isn't guaranteed.
- Instructions may be followed partially or not at all, especially when complex or self-contradictory.
- **Behavior is non-deterministic** — the same question can pull different context on different runs.

Prefer few, unambiguous, non-conflicting instructions over exhaustive rulebooks. Debug what the AI actually received with the [workbook inspector](https://docs.omni.co/analyze-explore/workbook-inspector#ai-messages).

### Where context applies

Not just Omni Agent — also embedded chat (including topic selection and model search), Workbook Agent query/SQL generation, Dashboard Agent summaries, AI visualization and summary generation, AI filter generation, and the Modeling Agent. A context change affects all of them.

## Writing ai_context

Add via the YAML API:

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "order_transactions.topic",
  "yaml": "base_view: order_items\nlabel: Order Transactions\nai_context: |\n  Map \"revenue\" → total_revenue. Map \"orders\" → count.\n  Map \"customers\" → unique_users.\n  Status values: complete, pending, cancelled, returned.\n  Only complete orders for revenue unless specified otherwise.",
  "mode": "extension",
  "branchId": "{branchId}",
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

For "map these terms correctly" or "Blobby confuses X with Y", the fix is a **positive mapping in topic-level `ai_context`** — synonyms alone can't arbitrate between two competing measures. If synonyms already exist but the topic context only says what *not* to use, add the missing positive mapping rather than more synonyms.

Good:

```yaml
ai_context: |
  "revenue" or "sales" -> order_items.total_revenue
  "order count" or "number of orders" -> order_items.count
  Never use order_items.count when the user asks for revenue.
```

Avoid stopping at:

```yaml
measures:
  total_revenue:
    synonyms: [revenue, sales]
  count:
    synonyms: [order count, orders]
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

`ai_context` is the one property Omni can't reclaim under pressure, so it is the scarcest budget in the model — not the most generous. Verbose entries evict field metadata first and can ultimately fail the request.

- Target 1-2 sentences per `ai_context` entry. Focus on disambiguation and gotchas, not general explanation.
- Keep labels short and human-readable — avoid redundant qualification (e.g., "Order Total Revenue Amount" → "Total Revenue").
- Rewrite long `description` values to be direct. If a description restates the field name, remove it.

## Model-Level Context

Model-level [`ai_context`](https://docs.omni.co/modeling/models/ai-context) carries guidance shared across every topic, and also informs **topic selection** — useful when Blobby picks the wrong topic rather than the wrong field.

Use it for instance-wide conventions (currency, fiscal calendar, tone, privacy rules) and keep topic-specific mappings on the topic.

There is also a model-level [`sample_queries`](https://docs.omni.co/modeling/models/sample-queries) parameter for example queries that span the model's topics.

## Advanced ai_context Templating

These apply to `ai_context` at the **model, topic, and view levels only**.

### Personalize with user attributes

`{{omni_attributes.<attribute_name>}}` is substituted with the current user's [attribute value](https://docs.omni.co/administration/users/attributes) at query time:

```yaml
ai_context: |
  You are a sales analyst. When someone asks about their team or pipeline,
  always filter by account.segment = {{omni_attributes.segment}}
  and account.region = {{omni_attributes.region}}.
```

> **Caveat**: Not supported in dimension or measure `ai_context` — there the value is used verbatim, un-substituted. Field references and filter conditions are also unsupported and raise a validation warning.

### Target specific model tiers with omni_llm

Scope instructions to the AI model tier — `smartest`, `standard`, or `fastest` — so expensive reasoning instructions don't burden fast models. Sections use Mustache syntax: `{{# ... }}` for "when", `{{^ ... }}` for "when not".

```yaml
ai_context: |
  This topic focuses on financial transactions.

  {{# omni_llm.smartest }}
  For complex multi-table queries, consider indirect relationships and provide rationale for join path selection.
  {{/ omni_llm.smartest }}

  {{# omni_llm.fastest }}
  Prefer single-table queries when possible.
  {{/ omni_llm.fastest }}
```

### Target specific agents with omni_agent

Scope context to the agent that will read it, so bulky agent-specific content doesn't inflate the window for the others:

- `analyze` — model search and query generation
- `build` — topic metadata generation, learn-from-conversation
- `simple_summarize` — tile/visualization summaries, query metadata

```yaml
ai_context: |
  {{# omni_agent.build }}
  Modeling conventions: Always define primary keys. Use snake_case for field names.
  {{/ omni_agent.build }}

  {{^ omni_agent.build }}
  Keep queries focused and efficient.
  {{/ omni_agent.build }}
```

`{{ omni_agent.name }}` interpolates the reading agent's name.

### Reuse blocks with constants

Define [`constants`](https://docs.omni.co/modeling/models/constants#reusable-ai-context) once and reference them with `@{constant_name}` across model, topic, view, and sample-query `ai_context` — the fix for the same tone/privacy/domain paragraph duplicated in a dozen places:

```yaml
constants:
  tone:
    value: "Keep responses concise and professional."
  privacy_high:
    value: "Never show individual customer names or emails."

ai_context: |
  @{tone} @{privacy_high}
```

## Curating Fields with ai_fields

### The real limits

Omni caps how much of the context window model metadata may consume. These caps — not the model's full context window — are what trigger pruning:

| Cap | Value | What happens past it |
|---|---|---|
| A topic's field definitions | ~75K characters | Field properties are pruned in the [pruning order](#pruning-order) |
| Topic-selection summaries (all topics) | ~100K characters | View metadata trimmed first (including view-level `ai_context`), then sample queries, then topic metadata as a last resort. Trimmed detail is recovered once a topic is selected. |
| Searches outside a topic | 100 fields per search | The AI runs narrower repeat searches rather than pruning properties. Applies when [`query_all_views_and_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/query-all-views-and-fields) is enabled. |

> **Do not optimize against a field count.** A lightly annotated field costs ~100 characters; one with a rich description, sample values, and `ai_context` costs several times that, so the number of fields that fits varies widely. Check the [workbook inspector](https://docs.omni.co/analyze-explore/workbook-inspector#ai-messages) to see the context actually delivered instead of estimating.

Conversation history is budgeted separately — see [`conversation_prune_length`](https://docs.omni.co/modeling/models/parameters/ai-settings/conversation-prune-length).

### Curating

Curate for precision, not just for size: a smaller, well-described field set gives the AI fewer chances to pick the wrong field. Reduce noise for large models:

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

Tagging is the most maintainable pattern — tag the fields users actually ask about, then curate with a single selector:

```yaml
ai_fields: [tag:use_for_ai]
```

## Controlling Topic Visibility with ai_chat_topics

`ai_chat_topics` is a model-level property that controls which topics Blobby can see:

- **No `ai_chat_topics` property** (default) — Blobby can query across all topics.
- **`ai_chat_topics: []`** (empty list) — Blobby cannot query any topics. This effectively disables AI chat for the model.
- **Explicit list** — only the listed topics (or tag matches) are available. Supports `all_topics`, tag selectors (`tag:customer_facing`), and negation (`-tag:internal`, `-staging_events`).

Check this first — if a topic isn't in `ai_chat_topics`, no amount of `ai_context` or `ai_fields` on it will matter. Use `omni-model-builder` to modify this property.

## Adding sample_queries

Teach Blobby by example. Especially effective for recurring questions and for date-filter patterns Blobby tends to get wrong.

The supported authoring path is through the workbook: build a query that returns the correct answer, then **Model > Save as sample query to topic**. Check **Include in AI context** (otherwise it only shows on the topic overview and never reaches the AI), and fill in the optional **Prompt** and **AI context** fields.

To write one directly in YAML instead — build the correct query in a workbook, retrieve its structure, then add it to the topic:

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

Focus on questions users actually ask — if you don't know which those are, ask the user rather than guessing at plausible-sounding ones.

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
```

The extended topic inherits the base topic's joins and filters, so add only what differs: a narrower field set, extra `ai_context`, or `sample_queries` (same shape as above).

## Improving Field Descriptions

Keep the value list in `all_values` and the AI-only rule in `ai_context` — a description that restates either is paying twice for one fact:

```yaml
dimensions:
  status:
    label: Order Status
    description: Current fulfillment status of the order.
    all_values: [complete, pending, cancelled, returned]
    ai_context: Use 'complete' for revenue calculations.
```

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

> **Note**: `all_values` is pruned first, so don't count on it surviving in a context-tight topic — put anything load-bearing in `ai_context` instead.

When the [dbt integration](https://docs.omni.co/integrations/dbt/setup) is enabled, dbt `accepted_values` tests are ingested as `all_values` automatically — check before hand-authoring them.

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

**When to add them** — synonyms earn their place when users genuinely say a word the model doesn't contain (`AOV`, `top line`, `basket size`). They do not earn it by restating the field's label or name, or by reinforcing a mapping topic-level `ai_context` already makes. Adding synonyms to a field whose disambiguation is already handled on the topic is the most common wasted write in this skill — see [Safe Model Write Defaults](#safe-model-write-defaults).

**Pruning**: `synonyms` are pruned **last**, after `description` and `label`. So for a field that genuinely needs alternate vocabulary, synonyms are the most durable place to put it — but that survivability is a reason to choose synonyms *over* a description for that purpose, never a reason to add more of them.

## Avoiding Duplication

`ai_context` and `description` serve different audiences. `description` is human-facing (shown in the field picker and docs). `ai_context` is an AI-only hint. Don't put the same text in both — `ai_context` should add guidance the description doesn't cover (disambiguation, gotchas, when to use one field over another).

**Consolidate shared context at the view level.** If multiple fields in a view share the same `ai_context` (e.g., "all monetary values are in USD"), move it to the view-level `ai_context` instead of repeating it on each field. Field-level `ai_context` should be specific to that field.

Shared fact hoisted to the view, `description` and `ai_context` each carrying only what the other doesn't:

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
3. Curate with `ai_fields` down to the fields users actually ask about, rather than to a field count
4. Write `ai_context` mapping business terms to fields (keep to 1-2 sentences; it is never pruned)
5. Add `synonyms` to key dimensions and measures (skip if they duplicate the label)
6. Improve field `description` and `label` values
7. Add `all_values`/`sample_values` for categorical fields
8. Add `sample_queries` for top 3-5 questions
9. Remove duplication between `ai_context` and `description`; consolidate shared context at view level, and shared blocks into `constants`
10. Consider `extends` for AI-specific topic variants
11. Scope tier- or agent-specific instructions with `omni_llm` / `omni_agent` rather than paying for them on every request
12. Test iteratively — ask Blobby and refine

> **Troubleshooting order** when Blobby answers wrong: confirm the topic is reachable (`ai_chat_topics`) → confirm the field is in context (workbook inspector; check it wasn't pruned or excluded by `ai_fields`/`hidden`) → then add or sharpen `ai_context`. Writing more context for a field the AI never received fixes nothing.

## Docs Reference

- [Optimize models for Omni AI](https://docs.omni.co/modeling/develop/ai-optimization)
- `ai_context` reference: [model](https://docs.omni.co/modeling/models/ai-context) · [topic](https://docs.omni.co/modeling/topics/parameters/ai-context) · [view](https://docs.omni.co/modeling/views/parameters/ai-context)
- Topic parameters: [`ai_fields`](https://docs.omni.co/modeling/topics/parameters/ai-fields) · [`sample_queries`](https://docs.omni.co/modeling/topics/parameters/sample-queries) · [`extends`](https://docs.omni.co/modeling/topics/parameters/extends) · [all topic parameters](https://docs.omni.co/modeling/topics/parameters.md)
- Model parameters: [`ai_chat_topics`](https://docs.omni.co/modeling/models/ai-chat-topics) · [`constants`](https://docs.omni.co/modeling/models/constants#reusable-ai-context) · [`sample_queries`](https://docs.omni.co/modeling/models/sample-queries) · [`query_all_views_and_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/query-all-views-and-fields) · [`conversation_prune_length`](https://docs.omni.co/modeling/models/parameters/ai-settings/conversation-prune-length)
- [Synonyms](https://docs.omni.co/modeling/dimensions/parameters/synonyms) · [User attributes](https://docs.omni.co/administration/users/attributes) · [Workbook inspector](https://docs.omni.co/analyze-explore/workbook-inspector#ai-messages)
- [Model YAML API](https://docs.omni.co/api/models.md) · [Omni AI Overview](https://docs.omni.co/ai.md) · [AI data security](https://docs.omni.co/ai/security)

## Related Skills

- **omni-model-explorer** — inspect existing AI context
- **omni-model-builder** — modify views and topics
- **omni-query** — test queries to verify Blobby's output

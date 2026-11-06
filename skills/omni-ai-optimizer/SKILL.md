---
name: omni-ai-optimizer
description: Optimize an Omni Analytics model for Blobby, the Omni Agent — configure ai_context, ai_fields, synonyms, sample_queries, and ai_settings. Use this skill whenever someone wants to improve AI accuracy in Omni, make Blobby smarter, add AI context or example questions, curate which fields the AI sees, personalize AI context by user attribute, diagnose context-window pruning or truncation, raise a topic's AI context budget, control which topics AI can reach, troubleshoot why Blobby gives wrong answers, or any variant of "make the AI better", "Blobby isn't answering correctly", "optimize for AI", or "teach the AI about our data".
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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule for profile setup (`omni config init --auth oauth`) and discovering command and request-body shapes with `--schema`.

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
- **Do not add "supporting" synonyms after a complete topic mapping** — for requests like "Blobby confuses revenue with order count" or "map these terms correctly", if topic-level `ai_context` already maps the business terms to the correct fields and includes the needed negative guardrails, stop and report that no duplicate write is needed. Adding field-level synonyms in that case is redundant and makes the prompt longer.
- **Create branches with `--name`** — `omni models create-branch <model-id> --name <branch-name>` does not accept a JSON `--body`.

## How Blobby Works

Omni fills the AI's context window in a fixed priority order and leaves `hidden: true` fields out. When a topic's metadata is over budget, Omni drops lower-priority field properties from every field, value lists first and `format` last. It never prunes `ai_context`. The full priority and pruning orders: [references/context-window.md](references/context-window.md).

### The LLM weighs all context together

All context is passed to the LLM at once, and the LLM decides how much weight each part gets:

- **Model-level `ai_context` does not reliably override topic-level `ai_context`.** Don't design around precedence that isn't guaranteed.
- **Global and personal context reach the agent too**, from outside the model, with no guaranteed precedence over it.
- Instructions may be followed partially or not at all, especially when complex or self-contradictory.
- **Behavior is non-deterministic**: the same question can pull different context on different runs.

Prefer few, unambiguous, non-conflicting instructions over exhaustive rulebooks.

### Where context applies

The same context also feeds embedded chat (including topic selection and model search), Workbook Agent query and SQL generation, Chat with Content summaries, AI visualization and summary generation, AI filter generation, and the Modeling Agent. A context change affects all of them.

## Writing ai_context

Add via the YAML API:

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "order_transactions.topic",
  "yaml": "base_view: order_items\nlabel: Order Transactions\nai_context: |\n  Map \"revenue\" → total_revenue. Map \"orders\" → count.\n  Map \"customers\" → unique_users.\n  Status values: complete, pending, cancelled, returned.\n  Only complete orders for revenue unless specified otherwise.",
  "mode": "combined",
  "branchId": "{branchId}",
  "commitMessage": "Add AI context to order transactions topic"
}'
```

This body creates the topic file. To add `ai_context` to an existing topic, read it with `--mode combined`, add the key, and send the whole file back (see `omni-model-builder` → Step 1).

### Where ai_context Goes

| Level | Put here | Example |
|---|---|---|
| Model | Conventions for every topic, and which topic answers which kind of question | "Fiscal year starts in February. Use Order Transactions for revenue questions." |
| Topic | Business terms mapped to fields, and guardrails | "revenue" → `order_items.total_revenue` |
| View | Facts every field in the view shares: grain, units, time zone | "One row per order line. Amounts in USD." |
| Field | One field's gotcha, or when to pick it over a sibling | "Excludes refunds; use for profitability." |

Put each fact once, at the highest level where it is true.

### What Makes Good ai_context

**Terminology mapping.** Map business terms to field names:

```yaml
ai_context: |
  "revenue" or "sales" → order_items.total_revenue
  "orders" → order_items.count
  "customers" → users.count or order_items.unique_users
  "AOV" → order_items.average_order_value
```

**Data nuances.** Explain what the field names don't make clear:

```yaml
ai_context: |
  Each row is a line item, not an order. One order has multiple line items.
  total_revenue already excludes returns and cancellations.
  Dates are in UTC.
```

For "map these terms correctly" or "Blobby confuses X with Y", the fix is a **positive mapping in topic-level `ai_context`**: synonyms alone can't choose between two competing measures. If synonyms already exist but the topic context only says what *not* to use, add the missing positive mapping rather than more synonyms.

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

**Behavioral guidance** (common patterns such as default granularity or "top N") and **persona prompting** (the analytical perspective) also belong here. Examples: [references/ai-context-examples.md](references/ai-context-examples.md).

### Keeping Context Concise

Omni never prunes `ai_context`, so every character of it stays in the context and pushes field metadata out first. Long entries can make the request fail.

- Aim for 1–2 sentences per entry, covering what the field names don't make clear.
- Keep labels short: "Order Total Revenue Amount" → "Total Revenue".
- Rewrite long `description` values to be direct. If a description restates the field name, remove it.

## Model-Level Context

Model-level [`ai_context`](https://docs.omni.co/modeling/models/ai-context) carries guidance shared across every topic, and also informs **topic selection**, so use it when Blobby picks the wrong topic rather than the wrong field.

Use it for model-wide conventions (currency, fiscal calendar, tone, privacy rules) and keep topic-specific mappings on the topic.

On a branch, Omni stores a model-level `ai_context` change as an `ai_context_patch` next to the text. Omni manages the patch: edit `ai_context` from a `combined` read and leave `ai_context_patch` as it is.

Model-level [`sample_queries`](https://docs.omni.co/modeling/models/sample-queries) are the only examples the agent sees while choosing a topic. Put the full example on the topic, and add a model copy only for a question where Blobby picks the wrong topic. Model-level `ai_settings` holds the AI switches (context budget, views outside topics, disabled tools): [references/ai-settings.md](references/ai-settings.md).

## Advanced ai_context Templating

Model, topic (including composite), view and sample-query `ai_context` can insert the current user's attribute values (`{{omni_attributes.<attribute_name>}}`) and reuse `constants` (`@{constant_name}`); dimension and measure `ai_context` is used as written. Take attribute names from `omni user-attributes list`. `omni_llm` sections are ignored (the validator warns) and `omni_agent` sections are deprecated, so add neither. Syntax and examples: [references/ai-context-templating.md](references/ai-context-templating.md).

## Curating Fields with ai_fields

### Limits

Omni caps how much of the context window model metadata may use. A topic's field definitions get 75,000 characters by default (10,000–200,000 with the topic's `ai_prune_characters` or the model's `ai_settings.topic_prune_characters`); past that, field properties are pruned. All the caps: [references/context-window.md](references/context-window.md#limits).

> **Size by characters, not field count.** A lightly annotated field costs ~100 characters; one with a long description, sample values and `ai_context` costs several times that. The one fixed count is 2,000 fields per topic: past it, Omni sends the remaining views without their fields and tells the agent to search them, and only `ai_fields` (or a smaller topic) fixes that. Instead of estimating, run `omni models validate` and read any `topic_ai_context_too_large` warning ([which topics it checks](references/context-window.md#the-validator-estimate)).

### Curating

Curate for accuracy as well as size: fewer, well-described fields give the AI fewer wrong fields to pick. For large models:

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

Same operators as topic `fields`: wildcard (`*`), negation (`-`), tags (`tag:`), and tags within one view (`order_items:tag:use_for_ai`). `ai_fields` applies after `fields` and changes only what the AI reads: users can still query every field in `fields`, and so can the agent when a user names one.

Tags are the easiest to maintain: tag the fields users ask about, then select the tag:

```yaml
ai_fields: [tag:use_for_ai]
```

## Controlling Topic Visibility with ai_chat_topics

`ai_chat_topics` is a model-level property that controls which topics Blobby can see:

- **No `ai_chat_topics` property** (default): Blobby can query every topic.
- **`ai_chat_topics: []`** (empty list): Blobby can't query any topic, which turns off AI chat for the model.
- **Explicit list**: only the listed topics (or tag matches) are available. Supports `all_topics`, tag selectors (`tag:customer_facing`), and negation (`-tag:internal`, `-staging_events`). A composite topic matches on its own name or tag, not its members'.

It doesn't apply to the Workbook Agent. Like `ai_fields`, it changes only what the AI sees.

Check this first: the Omni Agent never reads the `ai_context` or `ai_fields` of a topic that `ai_chat_topics` leaves out. Use `omni-model-builder` to change it.

## Adding sample_queries

Sample queries teach Blobby by example. They help most with recurring questions and with date filters Blobby gets wrong.

Build the query that returns the correct answer in a workbook, retrieve its structure, then add it to the topic. The key is the name users and the agent see, and a topic's sample query must use that topic's `topic` and `base_view`. The agent sees a calculation's name and label, never its formula, so say what each one computes in the sample query's `ai_context`.

```yaml
# order_transactions.topic (base_view: order_items)
sample_queries:
  "Highest Revenue Month":
    description: "Month with the highest revenue"
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

Every kind of sample query, what each one teaches and where users see it, its keys and validation: [references/sample-queries.md](references/sample-queries.md). Only topic sample queries are validated; run any other once before relying on it.

Use questions users really ask. If you don't know them, ask the user instead of guessing, and confirm each question's wording before writing it. To find candidates in usage data and the most-used dashboard tiles: [references/sample-queries.md](references/sample-queries.md#choosing-sample-queries).

## Improving Field Descriptions

Put the values in `sample_values` and the AI-only rule in `ai_context`, and don't repeat either in the description:

```yaml
dimensions:
  status:
    label: Order Status
    description: Current fulfillment status of the order.
    sample_values: [complete, pending, cancelled, returned]
    ai_context: Use 'complete' for revenue calculations.
```

### Enumerating Values for Categorical Fields

Use `sample_values` for categorical fields (`all_values` is deprecated). Details and examples: [references/categorical-values.md](references/categorical-values.md).

> **Note**: value lists are pruned first. If the agent must know a value, put it in `ai_context`.

When the [dbt integration](https://docs.omni.co/integrations/dbt/setup) is enabled, dbt `accepted_values` tests are ingested as `all_values` automatically (as `sample_values` when the test has a `where:` config), so check for them before writing your own.

## Adding synonyms

Map alternative names, abbreviations, and domain-specific terminology so Blobby matches user queries to the correct field. Works on dimensions, measures and filter-only fields. Examples: [references/synonyms.md](references/synonyms.md).

**Synonyms vs ai_context**: Use `synonyms` for field-level name mapping. Use `ai_context` for topic-level behavioral guidance, data nuances, and multi-field relationships.

**When to add them.** Add a synonym only for a word users say that the model doesn't contain (`AOV`, `top line`, `basket size`). Skip words that repeat the field's name or label, and mappings the topic's `ai_context` already makes ([Safe Model Write Defaults](#safe-model-write-defaults)).

**Pruning.** `synonyms` are pruned second to last, after `description` and `label`; only `format` is kept longer. Put a field's alternate names in `synonyms` rather than its description.

## Avoiding Duplication

`ai_context` and `description` serve different audiences. `description` is shown to people in the field picker and is also sent to the agent, but Omni prunes it early when space runs short. `ai_context` is sent only to the agent and never pruned. Don't repeat text between them: `ai_context` adds what the description doesn't (disambiguation, gotchas, when to use one field over another).

**Consolidate shared context at the view level.** If multiple fields in a view share the same `ai_context` (e.g., "all monetary values are in USD"), move it to the view-level `ai_context` instead of repeating it on each field. Field-level `ai_context` should be specific to that field.

Here the shared fact sits on the view, and each field's `description` and `ai_context` say different things:

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
2. Check that model-level `ai_chat_topics` includes the right topics
3. Curate with `ai_fields` to the fields users ask about, not to a target count
4. Write `ai_context` mapping business terms to fields (keep to 1-2 sentences; it is never pruned)
5. Add `synonyms` to key dimensions, measures and filter-only fields (skip if they duplicate the label)
6. Improve field `description` and `label` values
7. Add `sample_values` for categorical fields
8. Add `sample_queries` for top 3-5 questions
9. Remove duplication between `ai_context` and `description`; consolidate shared context at view level, and shared blocks into `constants`
10. Remove `omni_llm` sections (ignored, so their tier-only text never reaches the AI) and don't add `omni_agent` ones (deprecated)
11. Measure before and after on the branch with `omni-ai-eval`, then refine

> **Troubleshooting order** when Blobby answers wrong: confirm the topic is reachable (`ai_chat_topics`) → confirm the field is in context (check it isn't excluded by `ai_fields`/`hidden`, and that `omni models validate` doesn't flag the topic as over budget) → then add or sharpen `ai_context`. Context on a field the AI never receives has no effect.

## AI Model Suggestions

Omni can also suggest model changes from recent chat feedback on a shared model (CLI ≥ 1.1.2, `omni ai-model-suggestions --help`). Review each suggestion before applying it. Commands and limits: [references/ai-model-suggestions.md](references/ai-model-suggestions.md).

## Docs Reference

Omni docs pages for each AI setting: [docs-links.md](references/docs-links.md).

## Related Skills

- **omni-model-explorer** — inspect existing AI context
- **omni-model-builder** — modify views and topics
- **omni-query** — test queries to verify Blobby's output
- **omni-ai-eval** — score Blobby's answers before and after a change

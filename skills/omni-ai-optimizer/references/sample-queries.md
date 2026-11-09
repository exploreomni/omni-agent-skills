# Sample Queries

The reference for every kind of sample query: on a topic, a composite topic, or the model.

## Contents

- [Where they live](#where-they-live)
- [Composite topic sample queries](#composite-topic-sample-queries)
- [Choosing sample queries](#choosing-sample-queries)
- [Cost, and how many to add](#cost-and-how-many-to-add)
- [Keys](#keys)
- [What the agent receives](#what-the-agent-receives)
- [The query](#the-query)
- [Inheritance](#inheritance)
- [Mapping workbook JSON to YAML](#mapping-workbook-json-to-yaml)

## Where they live

| Placement | `query.topic` and `query.base_view` | When the agent sees it | What the validator checks |
|---|---|---|---|
| Topic (`<topic>.topic`) | The topic's name and the topic's base view | With that topic's metadata: when the agent searches the topic, and in the context Omni injects when a chat starts on it | A mismatched `topic` or `base_view` is an error (`sample_query_wrong_topic`, with an autofix). Warnings for fields that don't exist (`sample_query_field_not_found`), can't be queried in the topic (`sample_query_field_not_in_topic`) or form an invalid query (`sample_query_invalid`), and for `ai_context` templates |
| Composite topic (`<name>.composite_topic`) | The composite's name, for both; fields use composite addresses ([below](#composite-topic-sample-queries)) | With the composite's metadata, the same way | Nothing: a wrong `topic` or a missing field saves without a warning |
| Model (`model` file) | The topic it runs on | In the topic-selection summary of every topic, and appended to the context injected when a chat starts on one topic | Only the deprecated-`omni_llm` warning on its `ai_context`: a missing topic or field saves without a warning |

- **Topic and composite sample queries teach how to query the topic.** The agent gets them only after it has chosen that topic, so they show which fields, filters, calculations and date patterns to use there. They are never trimmed.
- **Model sample queries steer topic choice.** They are the only sample queries the agent sees while choosing a topic. They are also added when a chat starts on one topic, so they show query shape too. They share the topic-selection summary's ~100K-character cap and are trimmed early when it's tight: after view metadata and composite-topic text, before topic metadata ([context window](context-window.md#limits)).
- **Put the full example on the topic.** Add a model copy only for a question where the agent picks the wrong topic.
- **Where users see them.** An empty workbook tab shows the sample queries of its topic or composite topic as starter cards, and the model's when no topic is chosen. The AI chat offers up to five as starter prompts: the chosen topic's, or the model's when there is no topic or it has none.
- **None of them count against a topic's field budget** (`ai_prune_characters`).
- **Check what the validator doesn't.** For a composite or model sample query, run the query once (`omni-query`) before relying on it.
- **Saving from a workbook** writes the sample query to that workbook's model layer. Other users get it only once the workbook's model changes are promoted.

## Composite topic sample queries

A composite's sample query differs from a topic's in two ways: `base_view` is the composite's name rather than a real view, and fields use composite addresses.

```yaml
# order_transactions.topic: a topic sample query
sample_queries:
  "Orders by Status":
    query:
      base_view: order_items            # the topic's base view
      topic: order_transactions         # the topic's name
      fields: [order_items.status, order_items.count]

# sales_vs_returns.composite_topic: a composite sample query
sample_queries:
  "Sales and Returns by Month":
    query:
      base_view: sales_vs_returns       # the composite's name, not a view
      topic: sales_vs_returns           # the composite's name
      fields:
        - "@_shared_dimensions_.reporting_date[month]"
        - "@sales.order_items.total_sale_price"
        - "@returns.order_items.count"
```

- **Addresses**: `@_shared_dimensions_.<name>`, `@_shared_views_.<view>.<field>`, and `@<member topic>.<view>.<field>` for a member topic's measure. Quote them: a plain YAML value can't start with `@`. Inside a calculation's `sql`, write `${@<member topic>.<view>.<field>}`.
- **Write the `@` on every field.** Without it, a member-topic field is refused when you save, and any other field saves but fails when the sample query runs in a workbook, even when only one member topic has it. `omni query run` accepts the shorter forms; saved sample queries don't.
- Saving a composite query from a workbook writes this same shape.

## Choosing sample queries

Start with the five or so questions users ask most, taken from AI usage analytics or from stakeholders. Tiles on widely used dashboards are another source: each is a query people already rely on, though its title may not state the business question.

1. **Find the questions and tiles that matter.**
   - With usage analytics (needs an Organization Admin and the **Usage analytics** setting in AI Hub), ask the Omni Agent, or call the MCP server's `queryUsageAnalytics` tool with `analytics_getData` and a plain-language prompt: the questions users asked the AI, the most-run dashboard tiles on the topic, and the most-viewed dashboards. Tile results carry the tile name, its topic and how often it ran.
   - Without it, `omni documents list --sort-field visits --sort-direction desc` ranks documents by visits.
   - `omni documents get-queries <dashboardId>` returns each tile's `name` and its query.
2. **Turn each one into a business question.** A tile's title often isn't the question ("Query 1", "MTD Sales"), so read its fields, filters and sorts. Skip tiles with no question behind them, such as headers. From AI prompts, keep only data questions; drop follow-ups like "yes" and requests to change the model.
3. **Confirm with the user.** Show each tile or prompt next to the proposed question, and have the user confirm or rewrite it. Write only confirmed questions.
4. **Write the sample query.** The key and `prompt` are the confirmed question, and `query` is the tile's query or one you build in a workbook ([mapped to YAML](#mapping-workbook-json-to-yaml)). For a tile, `description` names the dashboard and tile it reproduces. Put it on its topic, and add a model copy only when the agent picks the wrong topic for that question.
5. **Decide what users see.** Leave a good starter question visible. Set `hidden: true` on an example meant only to teach the agent (an edge case, a date pattern, an odd phrasing). Set `exclude_from_ai_context: true` on a starter question the agent shouldn't copy.

## Cost, and how many to add

- **Size**: each sample query reaches the agent as one JSON line: its name, `prompt`, `description`, `ai_context` and the query. A typical one is 430–670 characters; many filters or calculations make it longer.
- **Topic and composite-topic sample queries** are sent with their topic on every turn that uses it, with no cap and no pruning. They don't count against `ai_prune_characters`, so they never push field metadata out, but each one adds credit cost and latency to every turn and makes conversation pruning start sooner.
- **Model sample queries** share the topic-selection summary's ~100K-character cap and are trimmed there when it's tight.
- **Add only distinct examples.** Each sample query should cover a question the agent gets wrong or users ask often. Near-duplicates add cost and can make the agent copy one query shape where it shouldn't.
- **Measure the effect**: on a branch, run `omni-ai-eval` with a prompt set that mixes each sample query's exact question with adjacent ones: the same shape with another metric, period, filter or grouping. Exact questions show the agent reproduces the example; adjacent ones show whether the example helps it answer similar questions. Add sample queries in small batches, and stop when a batch no longer improves the adjacent questions.

## Keys

```yaml
sample_queries:
  "Orders by Status, Last Month":      # the name: shown in the UI and sent to the agent
    query: { … }                       # see The query
    description: Order count by status
    prompt: How many orders by status last month?
    ai_context: Use count, not sale_price.
    exclude_from_ai_context: false
    hidden: false
```

| Key | Meaning |
|---|---|
| *the map key* | The sample query's name, shown in the UI and sent to the agent. Use a Title Case name that reads like the question, quoted when it holds punctuation. |
| `query` | The query. An entry without one saves, but the agent skips it. |
| `description` | A human-readable summary, also sent to the agent. Optional in YAML; the workbook's save dialog requires one. |
| `prompt` | How a user would ask for it. The AI chat's starter prompts show it; a sample query without one isn't offered there. |
| `ai_context` | What the example demonstrates. Takes `{{omni_attributes.<name>}}` and `@{constant_name}` ([templating](ai-context-templating.md)). An unknown constant is a warning on a topic sample query, and passes silently on a model one. |
| `exclude_from_ai_context: true` | Keeps it away from the agent and out of the AI chat's starter prompts. It still shows on the empty workbook tab. |
| `hidden: true` | Drops it from the starter cards and prompts shown to users. It still reaches the agent. |
| `ignored: true` | Removes a sample query of the same name inherited from a parent topic or model layer. |
| `vis_config` | The chart a workbook copies along with the query. Never sent to the agent. |

## What the agent receives

Each sample query that has a `query` and isn't excluded goes to the agent as one JSON line: `name`, `prompt`, `description`, `context` (its `ai_context`) and the query. Omni tells the agent to treat model sample queries as verified examples and learn their structure, intent and vocabulary. Make every sample query a known-correct answer.

## The query

```yaml
query:
  base_view: order_items
  topic: order_transactions
  fields: [order_items.status, order_items.count]
  filters:
    order_items.created_at:
      time_for_duration: [1 complete months ago, 1 months]
  sorts:
    - field: order_items.count
      desc: true
  limit: 10
```

- **Keys**: `base_view`, `topic`, `fields`, `calculations`, `filters`, `sorts` (`field`, `desc`), `pivots`, `limit` and `column_limit`.
- **Fields** are `view.field`, with a timeframe in brackets where one applies (`order_items.created_at[month]`).
- **Filters** take the YAML filter syntax: [docs](https://docs.omni.co/modeling/filters), or `references/yaml-filter-syntax.md` in the `omni-model-builder` skill.
- **Use relative dates** (`time_for_duration: [1 complete months ago, 1 months]`), here and in `ai_context`. A fixed date goes stale and teaches the agent the wrong default period.
- **Calculations** are written `calculations: <name>: sql: …` with an optional `label`, and the name listed in `fields`. `sql:` takes Omni function text with `${view.field}` references, the form Omni writes when it saves a workbook query: `OMNI_FX_SAFE_DIVIDE(${a}, ${b})`, `OMNI_PERCENT_OF_TOTAL(${a})`, `OMNI_RUNNING_TOTAL(${a})`, `OMNI_PERCENT_CHANGE_FROM_PREVIOUS(${a})`, `OMNI_FX_AVERAGE(OMNI_OFFSET(${a}, -2, 0, 3, 1))`, `OMNI_FX_IFS(${a} > 1000000, 'High', ${a} > 100000, 'Mid', 1 = 1, 'Low')`. A spreadsheet formula (`=B1/C1`) saves but fails when the query runs, and the validator doesn't check a sample query's calculations, so run it once. Rule 9 of Validation rules and gotchas in `omni-query`'s `references/table-calculations.md` has the form each surface takes.
- **The agent never sees a calculation's formula**, only its name and `label`; saving from a workbook drops the spreadsheet formula too. Say what each calculation computes in the sample query's `ai_context` (the tier cut-offs, what's divided by what). Without it, an agent asked a similar question has to guess.
- **A calculation users keep asking for** belongs in the model as a measure, where the agent sees its definition.

## Inheritance

- **Topic `extends`**: the extending topic inherits the parent topic's sample queries, re-pointed to itself (`topic` becomes the extending topic's name). A sample query with the same name in the extending topic replaces the parent's; `ignored: true` drops it.
- **Branches and other layers** merge the same way, for topic and model sample queries: same name replaces, `ignored: true` removes.

## Mapping workbook JSON to YAML

A workbook query's JSON has `table`, `join_paths_from_topic_name`, and `sorts` with `column_name`/`sort_descending`. Map them to YAML:

- `table` → `base_view`
- `join_paths_from_topic_name` → `topic`
- `column_name` → `field`, `sort_descending` → `desc`
- `filters`, `pivots`, `limit` and `column_limit` carry over; write filters in the YAML [filter syntax](https://docs.omni.co/modeling/filters)

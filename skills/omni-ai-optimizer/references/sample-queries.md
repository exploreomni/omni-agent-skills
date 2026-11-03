# Sample Queries

The reference for every kind of sample query: on a topic, a composite topic, or the model.

## Contents

- [Where they live](#where-they-live)
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
| Composite topic (`<name>.composite_topic`) | The composite's name, for both | With the composite's metadata, the same way | Nothing: a wrong `topic` or a missing field saves without a warning |
| Model (`model` file) | The topic it runs on | In the topic-selection summary of every topic, and appended to the context injected when a chat starts on one topic | Only the deprecated-`omni_llm` warning on its `ai_context`: a missing topic or field saves without a warning |

- **Pick the placement by what the example teaches.** Topic and composite sample queries reach the agent only after it has chosen that topic. The model's are the only ones it sees while choosing, so an example meant to steer topic choice belongs on the model.
- **Model sample queries are trimmed early.** When the topic-selection summary passes its ~100K-character cap, they go after view metadata and composite-topic text, before topic metadata ([context window](context-window.md#the-real-limits)).
- **None of them count against a topic's field budget** (`ai_prune_characters`).
- **Check what the validator doesn't.** For a composite or model sample query, run the query once (`omni-query`) before relying on it.

## Choosing sample queries

The best sample queries reproduce the dashboard tiles people already rely on, phrased as the business question each tile answers.

1. **Find the tiles and questions that matter.**
   - With usage analytics (an Organization Admin, with the **Usage analytics** setting on in AI Hub > Features), ask the Omni Agent, or call the MCP server's `queryUsageAnalytics` tool with `analytics_getData` and a plain-language prompt: the most-run dashboard tiles on the topic, the most-viewed dashboards, and the questions users asked the AI. Tile results carry the tile name, its topic and how often it ran.
   - Without it, `omni documents list --sort-field visits --sort-direction desc` ranks documents by visits.
   - `omni documents get-queries <dashboardId>` returns each tile's `name` and its query.
2. **Draft the business question each tile answers.** A tile's title often isn't the question ("Query 1", "MTD Sales"), so read its fields, filters and sorts. Skip tiles with no question behind them, such as headers. From AI prompts, keep only data questions; drop follow-ups like "yes" and requests to change the model.
3. **Confirm with the user.** Show each tile next to the proposed question, and have the user confirm or rewrite it. Write only confirmed questions.
4. **Write the sample query.** The key and `prompt` are the confirmed question, `description` names the dashboard and tile it reproduces, and `query` is the tile's query ([mapped to YAML](#mapping-workbook-json-to-yaml)). Put it on the tile's topic, and also on the model when the agent picks the wrong topic for that question.
5. **Decide what users see.** Leave a good starter question visible. Set `hidden: true` on an example meant only to teach the agent (an edge case, a date pattern, an odd phrasing). Set `exclude_from_ai_context: true` on a starter question the agent shouldn't copy.

## Cost, and how many to add

- **Size**: each sample query reaches the agent as one JSON line: its name, `prompt`, `description`, `ai_context` and the query. Across 52 dashboard tiles measured, each came to 430–670 characters, about 110–170 tokens; tiles with many filters or calculations cost more.
- **Topic and composite-topic sample queries** go with their topic on every turn it's in play, with no cap and no pruning. They don't count against `ai_prune_characters`, so they never push field metadata out, but every one adds tokens and latency to each turn and brings conversation pruning sooner.
- **Model sample queries** share the topic-selection summary's ~100K-character cap and are trimmed there when it's tight.
- **Returns diminish.** A sample query earns its place by covering a distinct question the agent gets wrong or users ask often. Near-duplicates of a pattern it already handles add cost and can anchor it on one shape.
- **Measure, don't guess**: on a branch, run `omni-ai-eval` with a prompt set that mixes each sample query's exact question with adjacent ones: the same shape with another metric, period, filter or grouping. Exact questions show the agent reproduces the example; adjacent ones show whether the example helps it answer similar questions. Add sample queries in small batches, and stop when a batch no longer improves the adjacent questions.

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
| *the map key* | The sample query's name, shown in the UI and sent to the agent. There is no `label:`. Use a Title Case name that reads like the question, quoted when it holds punctuation. |
| `query` | The query. An entry without one saves, but the agent skips it. |
| `description` | A human-readable summary, also sent to the agent. |
| `prompt` | How a user would ask for it. |
| `ai_context` | What the example demonstrates. Takes `{{omni_attributes.<name>}}` and `@{constant_name}` ([templating](ai-context-templating.md)). An unknown constant is a warning on a topic sample query, and passes silently on a model one. |
| `exclude_from_ai_context: true` | Keeps it away from the agent. |
| `hidden: true` | Drops it from the example list shown to users. It still reaches the agent. |
| `ignored: true` | Removes a sample query of the same name inherited from a parent topic or model layer. |
| `vis_config` | The chart a workbook copies along with the query. Never sent to the agent. |

## What the agent receives

Each sample query that has a `query` and isn't excluded goes to the agent as one JSON line: `name`, `prompt`, `description`, `context` (its `ai_context`) and the query. Model sample queries come with an instruction to treat them as a verified golden dataset and learn structure, intent and vocabulary from them. Write every sample query as a known-correct answer.

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

## Inheritance

- **Topic `extends`**: the extending topic inherits the parent topic's sample queries, re-pointed to itself (`topic` becomes the extending topic's name). A sample query with the same name in the extending topic replaces the parent's; `ignored: true` drops it.
- **Branches and other layers** merge the same way, for topic and model sample queries: same name replaces, `ignored: true` removes.

## Mapping workbook JSON to YAML

When exporting queries from Omni's workbook, you'll get JSON with `table`, `join_paths_from_topic_name`, and `sorts` using `column_name`/`sort_descending`. Map these to YAML as follows:

- `table` → `base_view`
- `join_paths_from_topic_name` → `topic`
- `column_name` → `field`, `sort_descending` → `desc`
- Workbook JSON includes `filters`, `pivots`, `limit`, `column_limit` which you can include in YAML (filters take the YAML [filter syntax](https://docs.omni.co/modeling/filters), not the workbook JSON shape)

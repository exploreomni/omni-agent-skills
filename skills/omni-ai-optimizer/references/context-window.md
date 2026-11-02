# The AI Context Window

How Omni orders, prunes, and caps the context it sends to the AI.

## Context priority order

Omni assembles the context window in this order:

1. **Context and tuning pre-built by Omni Engineering**
2. **`ai_context`** on the model, topics, and views
3. **Topic `description`**
4. **Topic `name` and `base_view`**
5. **Prioritized field properties** — `name` (listed under its view's name, so the AI reads `view.field`), field `ai_context`, and a custom calendar's timeframe names. Never pruned.
6. **Pruned field properties** — everything else, dropped in the order below when space runs short.

`hidden: true` fields are excluded entirely. `ai_chat_topics` (model-level) controls which topics Blobby can see at all.

## Pruning order

When a topic's metadata exceeds its allotment, Omni removes properties **lowest priority first**, clearing each one from *every* field before moving to the next:

`all_values` → `sql` → `links` → `enum_fill` → `sample_values` → `description` → `required_fields` → `group_label` → `label` → `aggregate_type` → `data_type` → `synonyms` → `format`

`sql` is sent for measures only, and `enum_fill` is a flag Omni adds to grouped and binned dimensions. The value list pruned first is a field's `all_values` (deprecated, but an existing one still goes out as the complete list); when that isn't set, it is a grouped or binned dimension's group or bin names, or a filter `suggestion_list` of up to 25 values (a longer list goes out as its first 25, as `sample_values`).

Two consequences worth internalizing:

- **Value lists go first**, because the AI can fetch a field's values on demand; `sample_values` follow a few steps later. **`synonyms` go second to last**, because they do the most work matching user phrasing to fields; only `format` outlasts them, so the AI doesn't restate a value in the wrong currency.
- **`ai_context` is never pruned** when Omni assembles context for a specific topic — at any level (model, topic, view, field). If it still doesn't fit, Omni drops whole views from model search, and past that the **request fails with an error**. Bloated `ai_context` is not a soft cost — it can starve field metadata and break queries outright. The one exception is *topic selection*, where view-level `ai_context` is trimmed first (see the caps table below).

## The real limits

Omni caps how much of the context window model metadata may consume. These caps — not the model's full context window — are what trigger pruning:

| Cap | Value | What happens past it |
|---|---|---|
| A topic's field definitions | 75,000 characters by default (~19K tokens) | Field properties are pruned in the [pruning order](#pruning-order). If every property is gone and it still doesn't fit, Omni keeps the views that fit (at least one) and tells the AI which views it left out. |
| Fields fetched for one topic | 2,000 | Views past the limit come back without their fields. The agent is told which views were cut and has to search them separately; dashboard filter and control builders look a cut field up by its exact name. Only `ai_fields` (or a narrower topic) fixes this; a bigger character budget doesn't. |
| Topic-selection summaries (all topics) | ~100K characters | Trimmed in this order: view metadata (`description`, `label`, view-level `ai_context`), composite-topic `description` and `ai_context`, model-level sample queries, the whole views section, then topic metadata, with topic `ai_context` last. Topics themselves are never dropped. Trimmed detail is recovered once a topic is selected. |
| Searches outside a topic | 100 fields per search | The AI runs narrower repeat searches rather than pruning properties. Applies when [`query_all_views_and_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/query-all-views-and-fields) is enabled. |

Set the topic budget with [`ai_prune_characters`](https://docs.omni.co/modeling/topics/parameters/ai-prune-characters) on the topic, or for every topic with [`ai_settings.topic_prune_characters`](https://docs.omni.co/modeling/models/parameters/ai-settings/topic-prune-characters) on the model. The topic's value wins. Either must be between 10,000 and 200,000; a value outside that range is a validator error.

```yaml
# topic file
ai_prune_characters: 100000
```

Conversation history is budgeted separately — see [`conversation_prune_length`](https://docs.omni.co/modeling/models/parameters/ai-settings/conversation-prune-length).

## The validator estimate

`omni models validate <modelId> --branch-id <branchId>` warns with `topic_ai_context_too_large` when a topic's estimated field context exceeds its budget or the topic has more than 2,000 fields. The message gives the estimated characters and tokens. It is an estimate, not a measurement.

The check only runs for a topic that:

- sets `ai_prune_characters`; or
- is named in `ai_chat_topics`; or
- isn't excluded by `ai_chat_topics`, when the model sets `ai_settings.topic_prune_characters`.

So on a model with neither setting and no `ai_chat_topics`, no topic is checked. To check every AI-visible topic, validate a branch that sets `ai_settings.topic_prune_characters: 75000` (the default budget).

The warning carries an autofix that raises `ai_prune_characters` to the estimate plus headroom. It doesn't offer one when the topic is over 2,000 fields or the raise would pass 200,000. Before raising the budget, check whether `ai_fields` can cut the topic instead: a bigger budget costs tokens on every request.

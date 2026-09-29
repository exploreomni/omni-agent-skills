# The AI Context Window

How Omni orders, prunes, and caps the context it sends to the AI.

## Context priority order

Omni assembles the context window in this order:

1. **Context and tuning pre-built by Omni Engineering**
2. **`ai_context`** on the model, topics, and views
3. **Topic `description`**
4. **Topic `name` and `base_view`**
5. **Prioritized field properties** — `name` (fully qualified, `view.field`) and field `ai_context`. Never pruned.
6. **Pruned field properties** — everything else, dropped in the order below when space runs short.

`hidden: true` fields are excluded entirely. `ai_chat_topics` (model-level) controls which topics Blobby can see at all.

## Pruning order

When a topic's metadata exceeds its allotment, Omni removes properties **lowest priority first**, clearing each one from *every* field before moving to the next:

`all_values` → `sql` → `sample_values` → `description` → `group_label` → `label` → `aggregate_type` → `data_type` → `synonyms`

Two consequences worth internalizing:

- **`all_values` goes first**, because the AI can fetch a field's values on demand. **`synonyms` go last**, because they do the most work matching user phrasing to fields.
- **`ai_context` is never pruned** when Omni assembles context for a specific topic — at any level (model, topic, view, field). If it still doesn't fit, Omni drops whole views from model search, and past that the **request fails with an error**. Bloated `ai_context` is not a soft cost — it can starve field metadata and break queries outright. The one exception is *topic selection*, where view-level `ai_context` is trimmed first (see the caps table below).

## The real limits

Omni caps how much of the context window model metadata may consume. These caps — not the model's full context window — are what trigger pruning:

| Cap | Value | What happens past it |
|---|---|---|
| A topic's field definitions | ~75K characters | Field properties are pruned in the [pruning order](#pruning-order) |
| Topic-selection summaries (all topics) | ~100K characters | View metadata trimmed first (including view-level `ai_context`), then sample queries, then topic metadata as a last resort. Trimmed detail is recovered once a topic is selected. |
| Searches outside a topic | 100 fields per search | The AI runs narrower repeat searches rather than pruning properties. Applies when [`query_all_views_and_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/query-all-views-and-fields) is enabled. |

> **Do not optimize against a field count.** A lightly annotated field costs ~100 characters; one with a rich description, sample values, and `ai_context` costs several times that, so the number of fields that fits varies widely. Check the [workbook inspector](https://docs.omni.co/analyze-explore/workbook-inspector#ai-messages) to see the context actually delivered instead of estimating.

Conversation history is budgeted separately — see [`conversation_prune_length`](https://docs.omni.co/modeling/models/parameters/ai-settings/conversation-prune-length).

# Model ai_settings

`ai_settings` sits in the model file. Each key inherits from the parent model layer when it isn't set.

```yaml
ai_settings:
  topic_prune_characters: 100000
  query_all_views_and_fields: disabled
```

| Key | Values (default) | What it does |
|---|---|---|
| [`topic_prune_characters`](https://docs.omni.co/modeling/models/parameters/ai-settings/topic-prune-characters) | integer, 10,000–200,000 (75,000) | Character budget for each topic's field context before pruning. A topic's own `ai_prune_characters` overrides it. Setting it also turns on the size check for every topic `ai_chat_topics` doesn't exclude ([details](context-window.md#the-validator-estimate)). |
| [`query_all_views_and_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/query-all-views-and-fields) | `enabled`, `disabled`, `default` (enabled) | Lets the Omni Agent and Workbook Agent query views that aren't in any topic. |
| [`conversation_prune_length`](https://docs.omni.co/modeling/models/parameters/ai-settings/conversation-prune-length) | `short`, `medium`, `long`, `max` (long) | How much conversation history is kept before older messages are pruned. |
| [`disabled_tools`](https://docs.omni.co/modeling/models/parameters/ai-settings/disabled-tools) | list of tool names | Hides chat tools such as `create_dashboard_from_chat`, `learn_from_conversation` or `visualize`. Core query tools can't be disabled; unknown names are ignored. |
| [`allow_custom_fields`](https://docs.omni.co/modeling/models/parameters/ai-settings/allow-custom-fields) | `always`, `never`, `not_for_restricted_queriers` (always) | Whether AI-generated queries may define fields the model doesn't have. The docs strongly discourage turning it off. |
| [`allow_ctes`](https://docs.omni.co/modeling/models/parameters/ai-settings/allow-ctes) | `always`, `never`, `not_for_restricted_queriers` (always) | Whether AI-generated queries may use CTEs and derived tables. |
| [`show_progress_narration`](https://docs.omni.co/modeling/models/parameters/ai-settings/show-progress-narration) | `enabled`, `disabled`, `default` (enabled) | How much of its working narration the agent shows. Display only. |

`analyze_configuration`, `build_configuration` and `simple_summarize_configuration` are accepted but ignored: the organization's LLM settings, or the user's choice in chat, set the LLM and thinking level. Don't add them.

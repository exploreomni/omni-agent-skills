# Advanced ai_context Templating

These apply to `ai_context` on the **model, topics (including composite topics), views and sample queries**.

## Personalize with user attributes

`{{omni_attributes.<attribute_name>}}` is substituted with the current user's [attribute value](https://docs.omni.co/administration/users/attributes) at query time:

```yaml
ai_context: |
  You are a sales analyst. When someone asks about their team or pipeline,
  always filter by account.segment = {{omni_attributes.segment}}
  and account.region = {{omni_attributes.region}}.
```

A multi-value attribute is joined with commas.

> **Caveat**: Not supported in dimension or measure `ai_context` — there the value is used verbatim, un-substituted. The filter and field references that work in SQL, such as `{{ filters.view.field.value }}`, `{{ view.field.in_query }}` and `{{# view.field.filter }}` sections, are not supported in any `ai_context` and raise a validation warning.

## Reuse blocks with constants

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

Constants are substituted first, so a constant's value can itself hold an `{{omni_attributes.<attribute_name>}}` reference. An unknown `@{name}` stays in the text as written, and the validator warns (`ai_context_unknown_constant`). Dimension and measure `ai_context` doesn't substitute constants either.

## Deprecated: omni_llm

`{{# omni_llm.<tier> }}` sections no longer select anything: Omni always renders a section's else branch (`{{^ omni_llm.<tier> }}`) and never its `{{# }}` branch, and `{{ omni_llm.model }}` renders empty. The validator warns on every use (`ai_context_deprecated_omni_llm`). The LLM is now chosen in the organization's LLM settings, not in the model.

When you find one, move any text the AI still needs out of the section and delete the tags. Text inside a `{{# omni_llm.* }}` section is not reaching the AI today.

## Deprecated: omni_agent

`omni_agent` sections still render, but the docs mark them deprecated and say Omni will ignore them in a future release, so don't add new ones. In existing context:

- `{{# omni_agent.<name> }}…{{/ omni_agent.<name> }}` renders only for that agent, and `{{^ omni_agent.<name> }}` for every other.
- `{{ omni_agent.name }}` renders the reading agent's name, or nothing when no agent is named.
- The names are `analyze` (chat, model search and query generation), `build` (the Modeling Agent and learn-from-conversation) and `simple_summarize` (tile and query summaries).

```yaml
ai_context: |
  {{# omni_agent.build }}
  Modeling conventions: Always define primary keys. Use snake_case for field names.
  {{/ omni_agent.build }}
```

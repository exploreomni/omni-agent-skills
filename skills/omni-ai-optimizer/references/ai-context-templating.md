# Advanced ai_context Templating

User attributes and constants work in `ai_context` on the **model, topics (including composite topics), views and sample queries**.

## Personalize with user attributes

`{{omni_attributes.<attribute_name>}}` is replaced with the current user's [attribute value](https://docs.omni.co/administration/users/attributes) at query time. Use only attributes that exist: `omni user-attributes list` returns each one's `name`.

```yaml
ai_context: |
  You are a sales analyst. When someone asks about their team or pipeline,
  always filter by account.segment = {{omni_attributes.segment}}
  and account.region = {{omni_attributes.region}}.
```

A multi-value attribute is joined with commas.

> **Dimension and measure `ai_context`** is used as written, with no substitution. The filter and field templates that work in SQL (`{{ filters.view.field.value }}`, `{{ view.field.in_query }}`, `{{# view.field.filter }}` sections) don't work in any `ai_context`, and the validator warns on them.

## Reuse blocks with constants

Define [`constants`](https://docs.omni.co/modeling/models/constants#reusable-ai-context) once and reference them with `@{constant_name}` across model, topic, view and sample-query `ai_context`, so a paragraph used in many places (tone, privacy rules) is written once:

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

`{{# omni_llm.<tier> }}` sections no longer select anything: Omni always renders a section's else branch (`{{^ omni_llm.<tier> }}`) and never its `{{# }}` branch, and `{{ omni_llm.model }}` renders empty. The validator warns on every use (`ai_context_deprecated_omni_llm`). The organization's LLM settings now choose the LLM.

When you find one, move any text the AI needs out of the `{{# }}` branch and delete the tags.

## Deprecated: omni_agent

`omni_agent` sections still render but are deprecated, so don't add new ones. To read existing ones:

- `{{# omni_agent.<name> }}…{{/ omni_agent.<name> }}` renders only for that agent, and `{{^ omni_agent.<name> }}` for every other.
- `{{ omni_agent.name }}` renders the reading agent's name, or nothing when no agent is named.
- The names are `analyze` (chat, model search and query generation), `build` (the Modeling Agent and learn-from-conversation) and `simple_summarize` (tile and query summaries).

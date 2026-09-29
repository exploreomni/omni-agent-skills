# Advanced ai_context Templating

These apply to `ai_context` on the **model, topics, views and sample queries**.

## Personalize with user attributes

`{{omni_attributes.<attribute_name>}}` is substituted with the current user's [attribute value](https://docs.omni.co/administration/users/attributes) at query time:

```yaml
ai_context: |
  You are a sales analyst. When someone asks about their team or pipeline,
  always filter by account.segment = {{omni_attributes.segment}}
  and account.region = {{omni_attributes.region}}.
```

> **Caveat**: Not supported in dimension or measure `ai_context` — there the value is used verbatim, un-substituted. The filter and field references that work in SQL, such as `{{ filters.view.field.value }}`, `{{ view.field.in_query }}` and `{{# view.field.filter }}` sections, are not supported in any `ai_context` and raise a validation warning.

## Target specific model tiers with omni_llm

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

## Target specific agents with omni_agent

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

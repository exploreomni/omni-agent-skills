# Writing Topics

## New topic vs extend an existing one

When a query can't be answered by an existing topic, first check whether you should simply **extend** one rather than create a new one. Extending is usually right when the request's base view (the FROM) matches an existing topic's base view — e.g. add a relationship/join so a needed view becomes reachable, or add a field/label. **Create a new topic** when any of these is fundamentally different:

- **Subject / object** — a different base view (FROM). What is the query fundamentally describing — orders? users? *time* (dates)? A different core entity warrants its own topic.
- **Constraints** — conditions that are *always* applied (e.g. an `always_where` that excludes test users from order data). Different always-on filters → a different topic.
- **Audience** — the same fields but different labels/terminology for a different consumer; jargon that differs by audience justifies a separate topic.

Prompt the requestor when it's a judgment call, and build new topics on a branch (see the [Safe Development Workflow](../SKILL.md#safe-development-workflow) in SKILL.md). Note that querying on a topic (vs a bare base view) is also what makes the result accessible to restricted queriers/viewers.

See [Topics setup](https://docs.omni.co/modeling/topics/setup.md) for complete YAML examples with joins, fields, and ai_context, and [Topic parameters](https://docs.omni.co/modeling/topics/parameters.md) for all available options.

Key topic elements:
- `base_view` — the primary view for this topic
- `joins` — nested structure for join chains (e.g., `users: {}` or `inventory_items: { products: {} }`)
- `ai_context` — guides Blobby's field mapping (e.g., "Map 'revenue' → total_revenue")
- `default_filters` — applied to all queries unless removed
- `always_where_sql` — non-removable WHERE filter using a SQL expression (cannot be removed by users)
- `always_where_filters` — non-removable WHERE filter using filter specifications (cannot be removed by users)
- `always_having_sql` — non-removable HAVING filter using a SQL expression, applied after aggregation (cannot be removed by users)
- `always_having_filters` — non-removable HAVING filter using filter specifications, applied after aggregation (cannot be removed by users)
- `fields` — field curation: `[order_items.*, users.name, -users.internal_id]`

## Filter Expressions for Topics

When configuring `default_filters`, `always_where_filters`, or `always_having_filters` on a topic, use the YAML filter condition syntax — the same syntax used in measure filters. See `references/yaml-filter-syntax.md` for the complete reference.

If the right filter configuration for a given use case isn't obvious, use the Omni AI CLI to search the docs:

```bash
omni ai search-omni-docs "how do I configure always_where_filters on a topic in Omni?"
```

Use targeted questions to get precise YAML examples for your specific filtering need before writing the model YAML.

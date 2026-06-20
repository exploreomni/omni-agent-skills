# Topic-Scoped View Definitions — Extended Examples

> **Note for contributors:** This file is a YAML example gallery for human reference. It is not loaded at agent runtime. All procedural guidance and directives live in `SKILL.md` under "Writing Relationships → Topic-Scoped View Definitions."

See [Topic views parameter](https://docs.omni.co/modeling/topics/parameters/views.md) for the full reference.

## Controlling View Display Order

```yaml
views:
  order_items:
    display_order: 0
  users:
    display_order: 1
  products:
    display_order: 2
```

## Overriding a Field Label

```yaml
views:
  order_items:
    dimensions:
      status:
        label: Fulfillment Status
```

## Topic-Specific Filtered Measure

```yaml
views:
  order_items:
    measures:
      us_revenue:
        sql: ${sale_price}
        aggregate_type: sum
        format: currency_2
        filters:
          users.country:
            is: US
```

## Topic-Specific Ratio Measure

Derived measures that divide two other measures use `sql:` referencing those measures — no `aggregate_type`.

```yaml
views:
  order_items:
    measures:
      avg_revenue_per_user:
        sql: "${total_revenue} / NULLIF(${users.count}, 0)"
        format: currency_2
        label: Avg Revenue per User
```

> **Quote the `sql` when writing via the YAML API.** Written through `models yaml-create`/`yaml-update`, an **unquoted** `sql` with `${…}` (especially two refs around an operator, e.g. `${a} / NULLIF(${b}, 0)`) collides with YAML flow-map syntax — the `${…}` tokens get parsed away and the value stores as a broken fragment (literally `sql: /`), which throws a warehouse `unexpected '/'` SQL error at query time. `models validate` does **not** catch it. Always quote (`sql: "${a} / NULLIF(${b}, 0)"`) and read the YAML back to confirm the refs survived. Ratio-of-measures is fully supported — the failure is purely YAML quoting.

## Topic-Specific Derived Dimension

```yaml
views:
  order_items:
    dimensions:
      is_high_value:
        sql: CASE WHEN ${sale_price} > 500 THEN TRUE ELSE FALSE END
        type: boolean
        label: High Value Order
```

## Cross-View Fields

Cross-view field references use `${view_name.field_name}` syntax and are only valid when the referenced views are joined in the topic.

```yaml
views:
  order_items:
    measures:
      revenue_per_user:
        sql: ${total_revenue} / NULLIF(${users.count}, 0)
        aggregate_type: number
        format: currency_2
        label: Revenue per User

      seller_margin:
        sql: ${sale_price} - ${sellers.cost}
        aggregate_type: sum
        format: currency_2
        label: Seller Margin
```

## Joining the Same View Multiple Ways (Multi-Join Lifecycle)

Extending a fact view multiple times with different join conditions to analyze the same metrics at different points in a lifecycle.

```yaml
views:
  contract_start_facts:
    extends: [contract_line_item_facts]
    display_order: 1
    measures:
      arr:
        label: ARR at Start

  contract_current_facts:
    extends: [contract_line_item_facts]
    display_order: 2
    measures:
      arr:
        label: ARR (Current)

  contract_end_facts:
    extends: [contract_line_item_facts]
    display_order: 3
    measures:
      arr:
        label: ARR at End

relationships:
  - join_from_view: opportunities
    join_to_view: contract_start_facts
    on_sql: ${opportunities.id} = ${contract_start_facts.opportunity_id}
      AND ${contract_start_facts.date} = ${opportunities.start_date}
    relationship_type: one_to_many
    join_type: always_left
  - join_from_view: opportunities
    join_to_view: contract_current_facts
    on_sql: ${opportunities.id} = ${contract_current_facts.opportunity_id}
      AND ${contract_current_facts.date} = CURRENT_DATE
    relationship_type: one_to_many
    join_type: always_left
  - join_from_view: opportunities
    join_to_view: contract_end_facts
    on_sql: ${opportunities.id} = ${contract_end_facts.opportunity_id}
      AND ${contract_end_facts.date} = ${opportunities.end_date}
    relationship_type: one_to_many
    join_type: always_left
```

## Topic-Scoped Query View

A query view defined inside a topic's `views:` block, scoped entirely to that topic. Requires `primary_key: true` on one dimension (or `custom_compound_primary_key_sql` at the view level), plus a `relationships:` entry and a `joins:` entry.

```yaml
# .topic file
base_view: order_items

views:
  user_lifetime_value:
    query:
      fields:
        order_items.user_id: user_id
        order_items.total_revenue: lifetime_value
      base_view: order_items
      topic: order_items
    dimensions:
      user_id:
        primary_key: true
      lifetime_value:
        format: currency_2

relationships:
  - join_from_view: order_items
    join_to_view: user_lifetime_value
    on_sql: ${order_items.user_id} = ${user_lifetime_value.user_id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  user_lifetime_value: {}
```

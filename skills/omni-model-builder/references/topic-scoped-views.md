# Topic-Scoped View Definitions — Extended Examples

> **Note for contributors:** This file is an extended YAML example gallery for human reference. It is not loaded at agent runtime. Procedural guidance and agent directives live in `SKILL.md` under "Writing Relationships → Topic-Scoped View Definitions."

See [Topic views parameter](https://docs.omni.co/modeling/topics/parameters/views.md) for the full reference.

Topics can define or override views inline using a `views:` block. This is how the extended views pattern works, but it applies more broadly — any dimension, measure, label, display order, or field metadata can be overridden within the topic without touching the shared view file. The `views:` parameter is a map of view names to topic-specific customizations; configurable properties include `display_order`, `extends`, `dimensions`, and `measures`.

Topic-scoped view definitions only affect queries run through this topic.

> **Before adding any topic-scoped field to an existing view:**
> 1. **Check for redundancy** — read the existing view YAML (`omni models yaml-get`) and confirm the field doesn't already exist at the view level. If it does and the definition is identical, there is no need to redefine it in the topic.
> 2. **Check for conflicts** — if a field with the same name exists but uses different SQL or a different filter expression, this is an override of the shared definition. Confirm explicitly with the modeler that they intend to override it in this topic's context, and make sure they understand the impact: queries through this topic will use the topic-scoped definition, while all other topics continue to use the shared view definition.

## Common Use Cases

**Controlling view display order in the field picker:**
```yaml
views:
  order_items:
    display_order: 0
  users:
    display_order: 1
  products:
    display_order: 2
```

**Overriding a field label for business context:**
```yaml
views:
  order_items:
    dimensions:
      status:
        label: Fulfillment Status
```

**A topic-specific filtered measure (only meaningful in this topic's context):**
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

**A topic-specific dimension not in the shared model (e.g. a derived flag only relevant to this topic):**
```yaml
views:
  order_items:
    dimensions:
      is_high_value:
        sql: CASE WHEN ${sale_price} > 500 THEN TRUE ELSE FALSE END
        type: boolean
        label: High Value Order
```

**Cross-view fields — measures or dimensions that reference fields from multiple joined views. These are almost always topic-specific because they depend on a particular join being present:**
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

Cross-view field references use `${view_name.field_name}` syntax and are only valid when the referenced views are joined in the topic. Define these in the topic's `views:` block rather than the shared view file — they'll break in any topic where that join isn't present.

> **Before writing cross-view fields:** confirm that every view referenced in a `${view_name.field_name}` expression is also declared in the topic's `joins:` block. The model validator will throw errors for any reference to a view that isn't joined — even if the relationship exists globally.

**Joining the same view multiple ways — extending a fact view multiple times with different join conditions to analyze the same metrics at different points in a lifecycle:**
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

Each extended view inherits all fields from the base fact view but surfaces them under a context-specific label (ARR at Start, ARR (Current), ARR at End). The topic's `relationships:` block joins each alias with a different date condition, enabling the same underlying view to be joined multiple ways within a single topic for side-by-side comparison.

**Topic-scoped query views — defining a virtual table inline within the topic:**

Query views can also be defined inside a topic's `views:` block, scoping the virtual table entirely to that topic. As with global query views, a `primary_key: true` dimension is required for the view to be joinable.

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

Use this when the virtual table is only meaningful in the context of this specific topic and doesn't need to be reusable across the model.

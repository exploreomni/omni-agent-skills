# Topic-Scoped Relationships — Extended Examples

> **Note for contributors:** This file is a YAML example gallery for human reference. It is not loaded at agent runtime. All procedural guidance and directives live in `SKILL.md` under "Writing Relationships."

## Basic Topic-Scoped Relationship

```yaml
# .topic file
base_view: order_items

relationships:
  - join_from_view: order_items
    join_to_view: promotions
    on_sql: ${order_items.promo_id} = ${promotions.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  promotions: {}
  users: {}
```

## Extended Views: Variant 1 — Global (reusable across topics)

A standalone `.view` file that uses `extends:` to inherit from the base view. Named to reflect its role; includes a `description`. The relationship is defined globally so any topic can join it.

```yaml
# sellers.view
extends: [users]
description: Represents the selling party on a transaction. Extends the users view with seller-specific field labels.

dimensions:
  name:
    label: Seller Name
  email:
    label: Seller Email
measures:
  count:
    label: Seller Count
```

```yaml
# relationships file
- join_from_view: order_items
  join_to_view: sellers
  on_sql: ${order_items.seller_id} = ${sellers.id}
  relationship_type: many_to_one
  join_type: always_left
```

```yaml
# any .topic file that needs it
joins:
  sellers: {}
  users: {}
```

## Extended Views: Variant 2 — Topic-scoped (inline)

The extended view, its relationship, and its joins are all defined inside the topic file. The alias is entirely scoped to this topic.

```yaml
# .topic file
base_view: order_items

views:
  sellers:
    extends: [users]
    display_order: 1
    dimensions:
      name:
        label: Seller Name

relationships:
  - join_from_view: order_items
    join_to_view: sellers
    on_sql: ${order_items.seller_id} = ${sellers.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  sellers: {}
  users: {}
```

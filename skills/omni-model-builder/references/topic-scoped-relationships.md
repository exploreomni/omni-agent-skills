# Topic-Scoped Relationships

Relationships can be defined inline within a topic file using the `relationships:` parameter. These are scoped to that topic only and do not affect other topics.

> **Before defining a topic-scoped relationship, check the global relationships file** for any existing relationship between the same two views in either direction (`join_from_view` → `join_to_view` or the reverse):
>
> 1. **Same views, same `on_sql`** — the topic-scoped relationship is redundant. Omit it, use the global relationship via `joins:`, and inform the modeler that the global definition already covers this case.
> 2. **Same views, different `on_sql`** — do not silently override the global relationship. The right approach in the vast majority of cases is the **extended views / join same view multiple ways** pattern (see below), which creates a named alias rather than replacing the global join. Confirm with the modeler before proceeding — if the intent is unclear, ask explicitly whether they want a topic-specific variant (extended views) or a true replacement of the global join for this topic.

**When to use topic-scoped instead of global:**
- One-off joins that don't belong in the shared model
- Joining the same table multiple times in one topic under different conditions (use extended views)
- Access-filtered joins via user attributes in `on_sql`

```yaml
# In a .topic file
relationships:
  - join_from_view: order_items
    join_to_view: users
    on_sql: ${order_items.user_id} = ${users.id}
    relationship_type: many_to_one
    join_type: always_left
```

User attributes can be used in `on_sql` for access-filtered joins:

```yaml
on_sql: ${orders.region} = '{{ omni_attributes.user_region }}'
```

## Joining the Same Table Twice: Extended Views

When you need to join the same table multiple times with different logic or field labels (e.g., a `users` table joined once as the buyer and once as the seller), use the **extended views** pattern rather than `join_to_view_as`. Extended views create a named alias that inherits all fields from the base view and allows full metadata customization.

There are two variants depending on whether the join should be reusable across topics or scoped to one topic.

### Variant 1: Global extended view (reusable across topics)

Create a standalone `.view` file that uses `extends:` to inherit from the base view. **Name the file to reflect its specific role** (e.g. `sellers.view` rather than `users_alias.view`), and **include a `description`** so that the purpose of the extended view is immediately apparent when inspecting the model. Add any context-specific labels, dimensions, or measures to the file. Then define the relationship globally, pointing to the new view by name. Any topic can then join this extended view just like any other global view.

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

Use this variant when the aliased join and its customizations are meaningful across multiple topics.

### Variant 2: Topic-scoped extended view (inline in the topic file)

Define the extended view inline in the topic file using a `views:` block, with the relationship and joins in the same file. This keeps the alias entirely scoped to the topic.

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

Use this variant when the aliased join is specific to this topic's context and is not generally applicable in other topics.

In both variants, the extended view inherits all dimensions and measures from the base view and can override labels, display order, or any field metadata. The relationship and joins reference the extended view name directly.

> If you see a `relationship alias duplicates view name` error, this pattern is the fix — it avoids the naming conflict by creating a proper named view rather than an alias.

## `joins` vs `relationships` in a Topic

These are two distinct parameters that work together:

- **`joins`** — declares *which* views are included in the topic and their hierarchy. Follows existing global (or topic-scoped) relationship definitions. Nesting reflects the join path.
- **`relationships`** — defines the join conditions themselves, scoped to this topic. Required when the join doesn't exist globally.

A topic that uses only global relationships needs only `joins`. A topic with a one-off join needs both `relationships` (to define the join) and `joins` (to include the view in the topic hierarchy):

```yaml
# .topic file with a topic-scoped relationship
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

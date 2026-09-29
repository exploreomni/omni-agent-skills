# Topic-Scoped Definitions

## Cross-View Fields in Views

Cross-view fields (dimensions or measures whose `sql` references `${other_view.field}`) in a global view file are evaluated in every topic that exposes the host view. A global relationship can make the dependency reachable in topics that inherit the global join graph, but it does not override a topic's explicit/frozen `joins:` map. If that map omits the dependency, validation returns a blocking `field_broken_in_topic` issue and queries using the field fail to plan.

**Placement follows intended availability and resolved join context, not field namespace.** Define the field in the topic's `views.<host_view>` block (see "Topic-Scoped View Definitions") when it is meaningful only in that topic or depends on a topic-specific, aliased, or frozen join. The field remains queryable as `<host_view>.<field>`; topic scoping limits where it is available, not the namespace the user requested.

Use the global view file when the field is universally meaningful and its dependency resolves unambiguously in every topic that exposes the host view. Before choosing, list those topics and inspect each resolved `get-topic` `join_via_map` — not only the global relationships file — then validate the branch and query at least one topic for each distinct join context. Topics without explicit joins may inherit a global relationship; topics with explicit joins may exclude it.

## Topic-Scoped Relationships

> **Before defining, check the global relationships file** for a join between the same two views in either direction. Same `on_sql` → redundant, use `joins:` only. Different `on_sql` → default to the extended views pattern below rather than a silent override. Confirm intent with the modeler.

Use topic-scoped relationships for one-off joins not in the shared model, or joining the same table multiple times under different conditions.

```yaml
# .topic file
relationships:
  - join_from_view: order_items
    join_to_view: users
    on_sql: ${order_items.user_id} = ${users.id}
    relationship_type: many_to_one
    join_type: always_left

joins:
  users: {}
```

> **`joins` vs `relationships`:** `joins` declares which views are in the topic and their hierarchy; `relationships` defines the join conditions. A topic using only global relationships needs only `joins`. A topic with a one-off join needs both.
>
> **Silent footgun — both are required, and omitting `joins` passes validation.** If you add the `relationships` entry but forget the view's `joins` entry, the model still **validates clean** (no error) — but the joined view's fields are silently **not exposed** in the topic (a query/markdown referencing them comes back empty). Don't trust `validate` for this; confirm the fields are actually exposed with `get-topic` (see [validation-and-testing.md](validation-and-testing.md)). (Topic file shapes vary: some list views under a `joins:` map, others as top-level `<view>: {}` entries — match the existing file's form.)

### Extended Views: Joining the Same Table Multiple Ways

When the same table needs multiple joins (e.g., `users` as buyer and seller), use the **extended views** pattern — not `join_to_view_as`. Two variants:

**Variant 1 — Global (reusable):** Create a standalone `.view` file with `extends:`, a role-descriptive name, and a `description:`. Define the relationship globally — any topic can then join it like any other view.

**Variant 2 — Topic-scoped (inline):** Define the alias in the topic's `views:` block with its relationship in the same file. Use when the alias is not generally applicable in other topics.

See `references/topic-scoped-relationships.md` for full YAML examples of both variants.

> If you see a `relationship alias duplicates view name` error, this pattern is the fix.

## Topic-Scoped View Definitions

Topics can define or override views inline using a `views:` block — controlling `display_order`, overriding `label`, adding topic-specific filtered measures or derived dimensions, defining cross-view fields, and joining the same view multiple ways with per-alias conditions.

> **Before adding any topic-scoped field to an existing view:**
> 1. Read the view YAML (`omni models yaml-get`) and confirm the field doesn't already exist. If it does with the same definition, skip it.
> 2. If a field with the same name exists but uses different SQL, this is an override. Confirm explicitly with the modeler — queries through this topic will use the topic-scoped definition; all other topics keep the shared one.

```yaml
# Example: display order + topic-specific filtered measure
views:
  order_items:
    display_order: 0
    measures:
      us_revenue:
        sql: ${sale_price}
        aggregate_type: sum
        format: currency_2
        filters:
          users.country:
            is: US
```

See `references/topic-scoped-views.md` for a full pattern gallery (label overrides, derived dimensions, cross-view fields, multi-join lifecycle, topic-scoped query views).

> **Cross-view fields in `views:` blocks:** Before writing `${view_name.field_name}` references, confirm every referenced view is declared in the topic's `joins:` block — the model validator throws errors for any reference to a view that isn't joined.

**Joining the same view multiple ways** (e.g., ARR at Start / Current / End): Use `extends:` inside the topic's `views:` block to create named aliases, each with its own `on_sql` in `relationships:`. Each alias inherits all base view fields and can override labels independently. For a full YAML example, see `references/topic-scoped-views.md`.

**Topic-scoped query views:** A query view can also be defined inside a topic's `views:` block, scoping it to that topic only. Same primary key rules apply (`primary_key: true` or `custom_compound_primary_key_sql`). Include a `relationships:` entry and a `joins:` entry for the new view — see [query-views.md](query-views.md), and [topic-scoped-views.md](topic-scoped-views.md) for a complete example.

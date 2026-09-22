# Composite Topics

A composite topic joins two or more topics on dimensions they share, so one query can place measures from different facts, or two views of the same fact, side by side. Each member topic is queried on its own; the per-topic results are joined with a FULL OUTER JOIN on the shared dimensions (a CROSS JOIN when none are selected), and shared-dimension values are coalesced. Sorts, limits, pivots, and calculations apply to the joined result.

Docs: [Composite topics](https://docs.omni.co/modeling/topics/composite-topics) · Guide: [Thin dimensional spine for multi-fact event analysis](https://docs.omni.co/guides/patterns/thin-dimension-spine), the established alternative when the facts share only a date or a key

## Is it a composite? The cardinality test

A metric that aggregates one fact and filters on another is not automatically a composite. How the summed fact reaches the filter table decides the shape:

| The filter table is | Example | Shape |
|---|---|---|
| Many-to-one from the summed fact | `order_items` revenue filtered on `users.country` | A regular topic. Join it like a dimension and put the condition in the measure's `filters:`. |
| One-to-many from the summed fact | `users` counted where any of their `order_items` has `status = 'Returned'` | A regular topic plus a query view that rolls the many side up to the summed grain (one row per user, `MAX(CASE …)` flags), joined one-to-one. Filter on the flag. |
| Not joined at all, only shared dimensions | `inventory_items` received next to `order_items` sold, by product and month | A composite: one topic per fact, shared views for the conformed dimensions. |

Most cross-fact requests are the first row. Only the third needs a composite.

## The file

A composite lives in its own file, `<name>.composite_topic`, and is authored through `yaml-create` like any other model file.

```yaml
# sales_vs_returns.composite_topic
topics: [ sales, returns ]
label: Sales vs Returns

shared_views: [ users, products ]

shared_dimensions:
  reporting_date:
    label: Reporting Date
    mappings:
      sales:
        field: order_items.created_at
      returns:
        field: order_items.returned_at
```

| Parameter | Meaning |
|---|---|
| `topics` | The member topics, a list. |
| `shared_views` | Views present in every member topic. Their dimensions are selectable once for the whole composite; each member topic joins the view through its own relationship, so a view can be joined on a different key per topic. |
| `shared_dimensions` | Named dimensions with a `mappings:` entry per topic pointing at that topic's field. The join keys between member topics. |
| `shared_measures` | Measures computed over the joined result from the member topics' measures. Syntax and limits below. |
| `unrelated_dimension_handling` | What a member topic's own dimensions (neither shared dimensions nor on a shared view) can do in a query: `filter_only` (default), `null_fill`, or `repeat`. Below. |
| `always_join_all_topics` | By default only topics with selected fields are included in the join; `true` includes every member. |
| `fields`, `ai_context`, `sample_queries`, `required_access_grants` | As on a regular topic. |

Constraints:

- A composite file has no `views:` block. Labels for shared views come from the first topic in `topics`; label them in the member topics.
- `extends` on a topic is a list (`extends: [ sales ]`), and a composite may include a topic and its own extends-child as two members.
- Every shared-dimension mapping must name a field that exists in that topic; validation reports a dangling mapping, and a mapping for a topic outside `topics` is an error at query time.
- Share conformed dimension tables with `shared_views` first: a view joined to every member topic (users, products, a date table) is shared wholesale, every field on it is selectable once, and nothing needs restating when a column is added. Reach for a `shared_dimensions` mapping only where the member topics reach a concept through *different* fields (an order date on one fact, an invoice date on the other). Under the default `unrelated_dimension_handling`, a dimension that belongs to one topic only can be filtered but not selected.
- A shared view or a mapped dimension aligns only the topics that join it. Nothing warns when a shared dimension covers some members and not others, so decide coverage deliberately and check the first query.

## Same fact, two lenses

Comparing one fact under two conditions (current vs prior period, all orders vs shipped orders) is a composite over a topic and an `extends` alias of it. The alias needs nothing but the parent; repeat the parent's `joins:` so the join map is explicit.

```yaml
# sales_b.topic
extends: [ sales ]
hidden: true
label: Sales B
joins:
  users: {}
```

```yaml
# sales_two_lens.composite_topic
topics: [ sales, sales_b ]
shared_views: [ users ]
shared_dimensions:
  reporting_date:
    mappings:
      sales:   { field: order_items.created_at }
      sales_b: { field: order_items.created_at }
```

Each member topic is then filtered independently in the query (below). For an aligned prior-period comparison, give the alias a topic-scoped relationship to a date-mapping query view and map the shared dimension to the mapped date on that member.

## Shared measures

A metric that spans member topics is a `shared_measures` entry: arithmetic in `sql:` over the members' own measures, addressed as `${<topic>.<view>.<measure>}` (the topic name, no `@`; the `@` form used in queries is also accepted). No `aggregate_type`; the member queries already aggregated.

```yaml
shared_measures:
  return_rate:
    label: Return Rate
    sql: ${returns.order_items.count} / NULLIF(${sales.order_items.count}, 0)
    format: percent_2
```

Selecting only a shared measure still aligns every member topic it references. Three limits:

- A `filters:` block on a shared measure validates but is not applied. Put the condition on a member measure (a filtered measure inside the member topic) and reference that.
- A shared measure aggregates member measures only. Referencing a member dimension does not aggregate it; it becomes a group-by column and changes the grain of every other measure.
- A shared measure does not reference another shared measure. Restate the arithmetic in terms of member measures.

## Topic-specific dimensions: `unrelated_dimension_handling`

Every dimension that is neither a shared dimension nor on a shared view belongs to one member topic. The composite's `unrelated_dimension_handling` decides what happens when a query selects one:

| Value | The dimension | Other topics' measures | Reach for it when |
|---|---|---|---|
| `filter_only` (default) | Filterable, not selectable | Never meet it | The composite exists to stitch on the shared views. The safe default for reporting. |
| `null_fill` | Selectable | Land on one extra row where the dimension is null | The unattributed total should be visible but kept apart. |
| `repeat` | Selectable | Repeat on every row of the dimension | An order-level amount should repeat across line detail, and readers of the grid expect it. |

Under `repeat`, a topic that does not join a shared view shows its grand total on every row of that view's dimensions. Correct for the header-across-detail case and wrong anywhere else; keep the default unless the repeat is wanted.

Under `repeat` each member topic is aggregated on its own — the header topic's query `GROUP BY state`, the line topic's query `GROUP BY state, line_number` — and the two are full-outer-joined on the shared keys, so the header query's `GROUP BY` never sees the line dimension and the header row fans across the line rows in the join. There is no fan-out to undo, unlike a header measure held inside a single topic with `level_of_detail` (see [level-of-detail.md](level-of-detail.md)). Check it with `planOnly`: two aggregate subqueries and a `FULL JOIN`, not one joined surface.

## Querying a composite

The request names the composite in `join_paths_from_topic_name` and carries no `table`. Fields use composite addressing:

| Address | Meaning |
|---|---|
| `@_shared_dimensions_.<name>[timeframe]` | A shared dimension. Timeframes apply as on any date. |
| `@_shared_views_.<view>.<field>` | A dimension of a shared view. |
| `@<topic>.<view>.<field>` | A measure of one member topic, or a filter on one member topic. |
| `@_shared_measures_.<name>` | A shared measure. |

The `@` is required in query field specs and filter keys (a spec without it is rejected as an invalid field specification); it is optional only in model SQL, where `${<topic>.<view>.<field>}` and `${@<topic>.<view>.<field>}` both resolve.

```json
{
  "query": {
    "modelId": "<modelId>",
    "fields": ["@_shared_dimensions_.reporting_date[month]",
               "@_shared_views_.users.country",
               "@sales.order_items.total_sale_price",
               "@sales_b.order_items.total_sale_price"],
    "join_paths_from_topic_name": "sales_two_lens",
    "filters": {
      "@sales.order_items.created_at":   {"type": "date", "kind": "BETWEEN", "values": ["2025-01-01", "2026-01-01"]},
      "@sales_b.order_items.created_at": {"type": "date", "kind": "BETWEEN", "values": ["2024-01-01", "2025-01-01"]}
    },
    "limit": 50
  }
}
```

- A filter keyed `@<topic>.` applies to that member topic only; a filter on a shared dimension or shared view applies to every member.
- Selecting a topic-specific dimension (`@sales.order_items.status`) fails under the default `unrelated_dimension_handling` with a message to move it to filters or make it a shared dimension; `null_fill` and `repeat` make it selectable (above).
- `omni models get-topic <modelId> <composite>` lists the composite's field surface with these addresses; fields consumed by a shared-dimension mapping are folded into the shared dimension.
- The validation query for a new composite is one shared dimension plus one measure per member topic; confirm every member's measure comes back non-null for at least one row.

## Aggregate tables and composites

Each member query of a composite is matched against its member topic's aggregate tables on its own, so a table declared on a member topic's base view serves that member's query under the same rules as a regular query, including `filters:` pins: two members can read two different pinned tables. Declare aggregate tables on the base views, with no `topic:` in the declaration. See [aggregate-awareness.md](aggregate-awareness.md).

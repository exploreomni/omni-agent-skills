# Level of Detail (LOD)

Docs: [Level of detail](https://docs.omni.co/modeling/dimensions/parameters/level-of-detail) · Guides: [Choosing between LOD fields, window functions, CTEs, and Excel](https://docs.omni.co/guides/patterns/level-of-detail-build-comparison) · [Cohort analysis with level of detail](https://docs.omni.co/guides/patterns/build-cohort-analysis-using-level-of-detail)

`level_of_detail` computes an aggregate at a grain **independent of the query's grouping**, then makes it available to your query. It is available on **dimensions** and **measures**. If you know Tableau LOD expressions, `fixed` / `always_include` / `always_exclude` map to `FIXED` / `INCLUDE` / `EXCLUDE`.

## Grouping strategies

| Form | Grain of the aggregate | Empty list |
|------|------------------------|------------|
| `fixed: [dims]` | Exactly these dims. The query's own dims still decide which rows land in each cell — see *Grain matching* below | `fixed: []` → single grand total on every row |
| `always_include: [dims]` | Query grain **plus** these dims (finer) | `always_include: []` → follows the query grain exactly |
| `always_exclude: [dims]` | Query grain **minus** these dims (coarser) | — |

All three lists take individual field references (`view.field`). There is no view-level or wildcard form — `always_exclude: [order_items.*]` fails validation with `Invalid field specified in always_exclude`.

## Authoring: `aggregate_type` lives inside `level_of_detail`

The aggregation is supplied by `aggregate_type` **inside** the `level_of_detail` block, applied to the **bare field** in `sql`. Two common mistakes:

- **Don't also write `max()`/`sum()` in `sql`.** That double-aggregates — e.g. an outer `sum` wrapped around your `max(date)` produces `SUM(MAX(date))` → `"Invalid argument types for SUM: TIMESTAMP"`.
- **`aggregate_type` is a child of `level_of_detail`**, not a sibling of `sql` at the dimension level (placing it at the dimension level errors with `"Invalid property name"`).

```yaml
# RIGHT — bare field, aggregate_type inside level_of_detail
first_order_date:
  sql: ${created_at}
  level_of_detail: { aggregate_type: min, fixed: [users.id] }
```

The inner `sql` must be **row-level**, not a composite measure. For a LOD that sums a field, define it on the view where that field is row-level (e.g. `order_items.sale_price`), not on a parent view that references it cross-view — there it collapses to the MIN per parent row.

## Dimension LOD vs. measure LOD

The structural tell is **how many aggregations** are in play:

- **LOD dimension — one `aggregate_type`** (inside `level_of_detail`). Computes the aggregate at the declared grain and **attaches it to every row** at that grain. Still a dimension: group by it, filter on it, bucket on it.
- **LOD measure — two `aggregate_type`s** (an outer one on the measure + an inner one in `level_of_detail`). An **aggregate of an aggregate** that collapses to a single number at the query grain. Cannot be grouped by.

```yaml
# Dimension: max age per country, attached to every user row in that country
max_age_in_country:
  sql: ${users.age}
  level_of_detail: { aggregate_type: max, fixed: [country] }

# Measure: average of each customer's total spend (inner SUM per user -> outer AVG)
avg_customer_lifetime_spend:
  sql: ${orders.amount}
  aggregate_type: average                                          # outer
  level_of_detail: { aggregate_type: sum, fixed: [customers.id] }  # inner
```

A measure whose `sql` is a bare reference to an LOD dimension (`sql: ${fee_per_order}` with an outer `sum`) compiles correctly and dedupes on the LOD grain. Wrapping the LOD dimension in a `CASE` inside a measure's `sql` does not — the LOD grain is pulled into the measure's own grouping and a `sum` becomes a sum of per-grain minimums. Put conditions in the measure's `filters:` instead.

## When to use each grain

- **`fixed: [entity]`** — an absolute grain attached back to rows. Cohort analysis (first-order date per user), customer-lifetime-value on each order row. `fixed: []` gives a grand total for percent-of-total math without a table calculation.
- **`always_include: [dims]`** — one grain finer; the cure for "average of averages." Summarize a finer aggregate than the report is grouped by (e.g. average *per customer* while grouped by channel).
- **`always_exclude: [dims]`** — one grain coarser; share-of-subtotal math, an all-time baseline beside per-period values, or holding an amount at a coarser grain while finer dims are on the report (below).

## Grain matching: `fixed:` has to name the grain the report actually uses

`fixed: [X]` computes the value once per X and then re-aggregates it **inside each cell of the query**. The result is flat across every dimension that is *not* in the list — however many get added — as long as X itself is on the report. Two consequences:

- **A superset re-splits the measure.** On a report grouped by `state`, `fixed: [state]` holds the state total flat down a line-number column; `fixed: [state, customer]` on the *same* report falls with each line, because the level became finer and cells now lose customer keys that have no row there. Gluing two fields into one key (`${state} || ${customer_id}`) behaves identically to listing both.
- **A grain the report does not use returns wrong totals.** `fixed: [state]` on a report grouped by `customer` returns state totals summed per customer cell.

`always_include` cannot cap a level — it only adds to it. Naming a field the report already groups by is a no-op, and naming the order key reproduces the per-order-then-resum behaviour you were trying to avoid.

## `always_exclude`: adapts, tolerates over-listing, needs `max`

Excluding the dimensions that must *not* split a measure leaves the level as whatever else the report has, so one definition adapts: the same measure holds per state on a state report and per customer on a customer report, with nothing reconfigured.

- **Excluding a field that is not on the report is a no-op.** Over-list deliberately; a missed field lets the measure split on it; an extra one costs nothing.
- **Use an idempotent outer aggregate — `max`, `min` or `average` — not `sum`.** The excluded value is the same coarser total on every finer row. With an outer `sum` it is re-added once per row: on a report whose only dimensions are excluded ones, nothing is left to group by and a `sum` returns the total multiplied by the row count. `max` returns the correct total in that case and every other.
- **`fixed:` wants the opposite.** With `fixed:` the grain key already dedupes, so `sum` is correct and rolls subtotals up properly, while `max` collapses any total above the fixed grain to a single group's value.

```yaml
# Order-level amount that must not split by anything below the order
shipping_fee_total:
  sql: ${orders.shipping_fee}
  aggregate_type: max
  level_of_detail:
    aggregate_type: sum
    always_exclude: [ order_items.line_number, order_items.sku, order_items.ship_method ]
```

Every selectable field below the order has to be named; two ways to shrink or remove the list follow.

## Where to define it: cross-view lists belong in the topic

An LOD list that names a field from another view is a cross-view reference. Written in a global view file, it breaks every topic that exposes the host view without joining the other one (`Field ... is broken in the context of topic ...`). Define the measure in the topic's `views:` block instead — the dependency is then only evaluated where the join exists, and it is not a new topic.

## Header amounts across line detail: LOD or composite

When a report needs a header-level measure (an order's shipping fee) to repeat across a line-level dimension (order line number) while line measures break out, there are two routes:

| Route | Header measure | Cost |
|---|---|---|
| One topic joining header to lines | `always_exclude` of every line-level field, outer `max` | The list, and its upkeep as columns are added |
| Two topics and a composite with `unrelated_dimension_handling: repeat` | A plain `sum` on the header topic — no `level_of_detail` at all | Splitting an established topic into member topics and naming the shared views |

The composite computes each member query at its own grain and stitches them, so the header query's `GROUP BY` never sees the line dimension and there is no fan-out to undo. Reach for it when the model can be arranged that way; reach for `always_exclude` when a wide topic already serving content has to keep doing so. Authoring and query shape: [composite-topics.md](composite-topics.md).

## A grain chosen per query

`fixed:` accepts a dimension whose `sql` is a `CASE` over a filter-only field, so the grain can follow a control on the report:

```yaml
header_grain:
  hidden: true
  sql: |
    CASE {{ filters.controls.header_grain.value }}
      WHEN 'Customer' THEN ${users.id}
      ELSE ${users.state}
    END

shipping_fee_total:
  sql: ${orders.shipping_fee}
  aggregate_type: sum
  level_of_detail: { aggregate_type: sum, fixed: [ header_grain ] }
```

One grain per query, not per series, and someone has to set the control. Declaring the filter-only field: [templated-filters.md](templated-filters.md).

## Reusing an exclusion list across measures

Write the list once on a template measure and inherit it with field-level `extends`. A `template: true` view needs no `schema` or `table_name`.

```yaml
# order_level_template.view
template: true
measures:
  order_level_metric:
    sql: "0"              # typed placeholder — see below
    aggregate_type: max
    level_of_detail:
      aggregate_type: sum
      always_exclude: [ order_items.line_number, order_items.sku, order_items.ship_method ]
```

```yaml
# in the consuming view or topic
shipping_fee_total:
  extends: [ order_level_template.order_level_metric ]
  sql: ${orders.shipping_fee}
  format: currency_2
```

The child inherits `aggregate_type` and the whole `level_of_detail` block and overrides only `sql`; the list is stored once. YAML anchors (`&list` / `*list`) are not an alternative — they are expanded on save into independent copies.

**Give the template a typed placeholder, not `NULL`.** A `min`/`max` child takes its result type from the parent's `sql` expression rather than its own, and formatting follows type: a `max` child of a `sql: "NULL"` parent returns unformatted numbers even with `format: currency_2` declared, while a `sum` child of the same parent formats correctly. `sql: "0"` avoids it. The same applies to any field-level `extends` where a `min`/`max` child aggregates a different type than its parent.

## Related: `omni_dimensionalize()`

`level_of_detail` and the `omni_dimensionalize()` table function express the same re-aggregation:

- A bare `level_of_detail: { aggregate_type: agg, always_include: [] }` is equivalent to a hand-written `omni_dimensionalize(agg(${x}))` — both **follow the live query grain**.
- Use `level_of_detail` to express `include` / `exclude` / `fixed` grains (the documented, declarative surface). Use `omni_dimensionalize()` directly for the bare "follow the query grain" case — most often **semi-additive measures** (flag the rows on the latest date, then sum only those).

## Verifying what a LOD does

- **See the compiled SQL without running it:** `omni query run --body '{"query":{...},"planOnly":true}'` returns `summary.display_sql`. A `fixed:` measure shows an intermediate `GROUP BY (query dims, "$lod_grain_key_0")`; a header measure mixed with a line measure compiles to `UNION ALL` grouping sets discriminated by a flag column.
- **See what `extends` resolves to:** `omni models yaml-get <model> --mode combined --fully-resolved true --filename <view>`. Without `--fully-resolved true` you are reading the authored layer, not what runs.
- **Check the number two ways:** the same measure at the fixed grain and one grain coarser must reconcile (the coarser total equals the sum of the finer values). A `max` outer aggregate on `fixed:` fails this test; a `sum` outer aggregate on `always_exclude` fails it by orders of magnitude.

## Related references

- `references/modelParameters.md` — full dimension/measure parameter and aggregate-type lists.
- `references/composite-topics.md` — the two-topic route for header amounts across line detail.
- `references/templated-filters.md` — declaring the filter-only field behind a per-query grain.
- `references/topic-scoped-views.md` — query views, the fanout-proof alternative when a LOD won't fit.

# Omni → MetricFlow Field Mapping

Use the effective Omni `combined` YAML. Do not export fields with dbt provenance comments. The legacy YAML below is based on the tested `sem_order_items.yml` and `metrics_omni_order_items.yml` export. It passed `dbt parse`, `mf validate-configs`, `mf query --explain`, and a pull into Omni.

Use [YAML-REFERENCE.md](./YAML-REFERENCE.md) for the equivalent dbt 1.12 flattened form.

## Entities and View Mapping

```yaml
# Omni relationship
- join_from_view: omni_dbt_ecomm__order_items
  join_to_view: omni_dbt_ecomm__users
  relationship_type: assumed_many_to_one
  on_sql: ${omni_dbt_ecomm__order_items.user_id} = ${omni_dbt_ecomm__users.id}
```

```yaml
# models/semantic-models/sem_order_items.yml
semantic_models:
  - name: sem_order_items
    model: ref('order_items')
    entities:
      - name: order_item_id
        type: primary
        expr: id
      - name: user_id
        type: foreign
        expr: user_id
```

The many side gets the foreign entity. The one side gets the primary entity. Use the FK column name when it is unambiguous. A composite primary key needs a stable dbt expression.

## Dimensions

```yaml
# Omni
dimensions:
  status:
    sql: '"STATUS"'
  created_at:
    type: time
    timeframes: [raw, date, week, month, quarter, year]
```

```yaml
# Tested legacy output
defaults:
  agg_time_dimension: created_at
dimensions:
  - name: status
    type: categorical
  - name: created_at
    type: time
    type_params:
      time_granularity: day
```

Use the finest matching timeframe. `raw` and `date` map to `day`. Calendar parts such as `month_name` have no MetricFlow equivalent.

For a same-view computed dimension, use a dbt expression.

```yaml
dimensions:
  - name: status_complete
    type: categorical
    expr: "case when status = 'Complete' then true else false end"
```

Do not map a cross-view expression.

## Dimension Overrides and Measures

Measure `expr` is written against dbt model columns. It is not written against a model-layer Omni dimension override.

```yaml
# Omni extension
dimensions:
  sale_price:
    sql: '"SALE_PRICE" * 0.95'
```

> ✋ **STOP** — If a measure references `sale_price`, show this override. Choose one of these options:
>
> 1. Move the override into dbt model SQL or a dbt derived dimension. Export the measure against that dbt definition.
> 2. Inline the override into the dbt measure `expr` for dbt correctness. Record that the Omni dimension override must be removed before pull-back.
> 3. Skip the measure.

Never inline an override silently. If the dbt expression is `sale_price * 0.95` and Omni still defines `sale_price` as `"SALE_PRICE" * 0.95`, the returned measure evaluates `SUM("SALE_PRICE" * 0.95 * 0.95)`.

The tested source used option 2:

```yaml
measures:
  - name: total_sale_price
    label: Total Sale Price
    description: Total USD amount sold
    agg: sum
    expr: sale_price * 0.95
    create_metric: true
```

It is a valid dbt example. It is safe to pull back only after the matching Omni dimension override has been removed.

## Aggregations

```yaml
# Tested source
measures:
  - name: total_sale_price
    label: Total Sale Price
    description: Total USD amount sold
    agg: sum
    expr: sale_price * 0.95
    create_metric: true
  - name: order_id_count_distinct
    label: Order Count
    agg: count_distinct
    expr: order_id
    create_metric: true
  - name: order_item_count
    agg: count
    expr: 1
```

| Omni `aggregate_type` | MetricFlow `agg` | Note |
|---|---|---|
| `sum` | `sum` | Use dbt-column expression. |
| `count` | `count` | Use `expr: 1` when Omni has no SQL. |
| `count_distinct` | `count_distinct` | Use the dbt column. |
| `average` | `average` | Use an atomic measure for a filtered metric. |
| `min`, `max`, `median` | same | Supported aggregation. |
| `percentile` | `percentile` | Convert 0–100 to 0–1 in `agg_params.percentile`. |
| `sum_distinct_on`, `average_distinct_on`, `median_distinct_on`, `percentile_distinct_on` | none | Skip and report. Omni dedupes by `custom_primary_key_sql`; MetricFlow has no equivalent. |
| `list` | none | Skip and report. |
| measure with `sql` and no `aggregate_type` (custom aggregate) | none | Skip and report unless the SQL is plain arithmetic over other measures (derived metric). |

## Filtered Aggregate → Simple Metric

Use an atomic measure plus a user-facing metric. This example is from the tested files.

```yaml
# sem_order_items.yml
measures:
  - name: average_sale_price
    agg: average
    expr: sale_price * 0.95

# metrics_omni_order_items.yml
metrics:
  - name: sale_price_average
    label: Sale Price Average (For Complete Orders)
    description: Average price per item across completed orders
    type: simple
    type_params:
      measure:
        name: average_sale_price
        filter: |
          {{ Dimension('order_item_id__status') }} = 'Complete'
```

### Re-import result

When no extension field with the same name exists, Omni imports this simple metric as a hidden filter dimension and a measure:

```yaml
dimensions:
  _filter_sale_price_average:
    # Produced by the dbt semantic layer integration
    sql: ${omni_dbt_ecomm__order_items.status} = 'Complete'
    description: Intermediate filter dimension for measure sale_price_average
    hidden: true

measures:
  sale_price_average:
    # Measure is defined by the 'sale_price_average' dbt metric (models/semantic-models/metrics_omni_order_items.yml)
    sql: ${omni_dbt_ecomm__order_items.sale_price} * 0.95
    aggregate_type: average
    filters: {_filter_sale_price_average: true}
```

In the live test the extension already had `sale_price_average`, so its `sql` and `label` keys won and only the comment and `filters` came from dbt. An existing extension can mask individual keys in this returned measure. The provenance comment is still added. A field marked `ignored: true` in the extension does not appear in combined output.

## Filter Operators

| Omni operator | MetricFlow form |
|---|---|
| `is: value` | `{{ Dimension('entity__dim') }} = 'value'` |
| `is: [a, b]` | `{{ Dimension('entity__dim') }} IN ('a', 'b')` |
| `not: value` / `not: [a, b]` | `<> 'value'` / `NOT IN ('a', 'b')` |
| `is: true` / `is: false` / `is: null` | `IS TRUE` / `IS FALSE` / `IS NULL` |
| `not: null` | `IS NOT NULL` |
| `falsey: true` | `(x IS FALSE OR x IS NULL)` |
| `greater_than`, `greater_than_or_equal_to`, `less_than`, `less_than_or_equal_to` | `>`, `>=`, `<`, `<=` |
| `between: [a, b]` | `BETWEEN a AND b` |
| `contains: x` / `not_contains: x` | `LIKE '%x%'` / `NOT LIKE '%x%'` |
| `starts_with: x` / `not_starts_with: x` / `ends_with: x` | `LIKE 'x%'` / `NOT LIKE 'x%'` / `LIKE '%x'` |
| `case_insensitive: true` modifier | use `ILIKE` (or `LOWER()` on both sides) |
| `and: [...]` / `or: [...]` | `( ... AND ... )` / `( ... OR ... )` |
| `before`, `on_or_after`, `between_dates` with literal dates | `{{ TimeDimension('entity__dim', 'day') }} < '<date>'`, `>= '<date>'`, `BETWEEN '<a>' AND '<b>'` |

Use the entity of the filtered view. Do not use a semantic-model name.

```yaml
# Wrong
filter: "{{ Dimension('sem_users__state') }} = 'California'"

# Right for the order-items → users relationship
filter: "{{ Dimension('user_id__state') }} = 'California'"
```

```yaml
filter: |
  {{ Dimension('order_item_id__status') }} IN ('Complete', 'Shipped')
  AND {{ Dimension('order_item_id__is_returned') }} IS TRUE
  AND {{ TimeDimension('order_item_id__created_at', 'day') }} >= '2024-01-01'
```

Quote strings and dates with single quotes. Double embedded single quotes. Do not interpolate fetched Omni text into Jinja.

Skip and report: `time_for_duration` and `date_offset_from_query` (relative dates); `day_of_week`, `day_of_month`, `month_of_year`, `quarter_of_year` and other calendar parts; user-attribute filters; `field_name_in_query` and `field_name_not_in_query` (query-result filters); `cancel_query_filter`.

## Ratio and Derived Metrics

```yaml
# metrics_omni_order_items.yml
metrics:
  - name: price_per_order
    label: Price per Order
    type: ratio
    type_params:
      numerator: total_sale_price
      denominator: order_id_count_distinct
  - name: taxed_amount
    label: Taxed Amount
    type: derived
    type_params:
      expr: total_sale_price * 1.07
      metrics:
        - name: total_sale_price
```

Ratios become `type: ratio`. Arithmetic over measures becomes `type: derived`. Do not give an atomic measure and a user-facing metric different definitions under the same name.

## Topic Extras

```yaml
saved_queries:
  - name: monthly_sales
    query_params:
      metrics: [total_sale_price]
      group_by: [metric_time__month]
```

Map compatible topic defaults and sample queries to saved queries. Drop table calculations, pivots, and unsupported query logic.

## Unsupported Constructs

Skip and report these constructs:

- cross-view dimension expressions;
- templated SQL;
- unsupported joins;
- filter-only fields;
- relative time filters;
- time and period comparison logic; and
- dbt objects the importer does not support, including conversion and cumulative metrics.

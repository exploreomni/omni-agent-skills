# dbt MetricFlow YAML Reference

Use the YAML shape already used by the dbt project. The legacy example reflects the tested `sem_order_items.yml` and `metrics_omni_order_items.yml` export. It passed `dbt parse`, `mf validate-configs`, `mf query --explain`, and a round trip into Omni.

## Legacy spec: `semantic_models` and `metrics`

```yaml
# models/semantic-models/sem_order_items.yml
semantic_models:
  - name: sem_order_items
    model: ref('order_items')
    defaults:
      agg_time_dimension: created_at
    entities:
      - name: order_item_id
        type: primary
        expr: id
      - name: user_id
        type: foreign
        expr: user_id
    dimensions:
      - name: status
        type: categorical
      - name: status_complete
        type: categorical
        expr: "case when status = 'Complete' then true else false end"
      - name: created_at
        type: time
        type_params:
          time_granularity: day
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
      - name: average_sale_price
        agg: average
        expr: sale_price * 0.95
      - name: order_item_count
        agg: count
        expr: 1

# models/semantic-models/metrics_omni_order_items.yml
metrics:
  - name: sale_price_average
    label: Sale Price Average (For Complete Orders)
    description: Average price per item across completed orders
    type: simple
    type_params:
      measure:
        name: average_sale_price
        filter: "{{ Dimension('order_item_id__status') }} = 'Complete'"
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

The `sale_price * 0.95` examples are valid dbt YAML. Before pull-back, follow the dimension-override rule in [FIELD-MAPPING.md](./FIELD-MAPPING.md). Remove the Omni `sale_price` override or the calculation applies twice.

## dbt 1.12 flattened spec

Add these keys to the existing dbt model entry. Do not create a second `models:` entry for a model that already exists in `_schema.yml`.

```yaml
models:
  - name: order_items                 # existing dbt model entry (often already in _schema.yml — add keys there, do not duplicate the model)
    semantic_model:
      enabled: true
      name: order_items               # optional; only name/enabled/group/config are allowed here
    agg_time_dimension: created_at    # MODEL-LEVEL key in 1.12.4 (not under semantic_model:)
    columns:
      - name: id
        entity: { type: primary, name: order_item_id }
      - name: user_id
        entity: { type: foreign, name: user_id }
      - name: status
        dimension: { type: categorical }
      - name: created_at
        granularity: day
        dimension: { type: time }
    derived_semantics:
      dimensions:
        - { name: status_complete, type: categorical, expr: "case when status = 'Complete' then true else false end" }
    metrics:
      - { name: total_sale_price, type: simple, agg: sum, expr: sale_price, label: Total Sale Price }
      - { name: sale_price_average, type: simple, agg: average, expr: sale_price, filter: "{{ Dimension('order_item_id__status') }} = 'Complete'" }
      - { name: order_item_count, type: simple, agg: count, expr: 1, hidden: true }   # hidden → manifest is_private
metrics:                               # ratio/derived/cumulative/conversion stay top-level
  - name: price_per_order
    type: ratio
    numerator: total_sale_price
    denominator: order_id_count_distinct
  - name: taxed_amount
    type: derived
    expr: total_sale_price * 1.07
    input_metrics: [{ name: total_sale_price }]
saved_queries: [...]                   # top-level, not under models[]
```

### How the two specs compile

Legacy populates manifest `semantic_models[].measures` and `metrics[].type_params.measure`. Flattened YAML leaves `semantic_models[].measures` empty. Its aggregation is on `metrics[].type_params.metric_aggregation_params` with `semantic_model`, `agg`, `agg_params`, and `agg_time_dimension`, plus `type_params.expr`.

Omni's importer reads both paths. dbt 1.12.4 emits no deprecation warning for the legacy spec. `dbt-autofix deprecations --semantic-layer` converts legacy YAML to flattened YAML. It renames semantic models to the model name, turns measures without a metric into `hidden: true` metrics, and does not rewrite filter qualifiers.

## Aggregate Type Mapping

| Omni `aggregate_type` | MetricFlow `agg` |
|---|---|
| `sum` | `sum` |
| `count` | `count` with `expr: 1` when Omni has no SQL |
| `count_distinct` | `count_distinct` |
| `average` | `average` |
| `min` | `min` |
| `max` | `max` |
| `median` | `median` |
| `percentile` | `percentile`; convert 0–100 to 0–1 in `agg_params.percentile` |
| `sum_distinct_on`, `average_distinct_on`, `median_distinct_on`, `percentile_distinct_on`, `list` | unsupported |
| measure with `sql` and no `aggregate_type` | unsupported, unless it is arithmetic over measures (derived metric) |

## Metric Type Mapping

| Omni construct | Legacy | Flattened |
|---|---|---|
| unfiltered aggregate | measure with `create_metric: true` | model-level simple metric |
| aggregate with filters | atomic measure plus simple metric | model-level simple metric with `agg`, `expr`, and `filter` |
| division of measures | ratio metric | top-level ratio metric |
| arithmetic over measures | derived metric | top-level derived metric |
| compatible topic extra | saved query | top-level saved query |
| time or period comparison | unsupported | unsupported |

## What Omni Imports Back

| dbt object | Omni result |
|---|---|
| primary entity | `primary_key` when the schema view has none |
| foreign entity | hidden `_entity_<name>` dimension and supported relationship |
| categorical dimension | dimension; `expr` becomes SQL when present |
| time dimension | dimension; granularity does not create Omni timeframes |
| supported aggregation | aggregation measure |
| simple metric with one `Dimension` filter | measure plus hidden `_filter_<metric>` dimension |
| ratio metric | measure on the denominator view |
| derived metric | measure on the first input view |
| `TimeDimension`, `Metric`, `sum_boolean`, non-additive dimension | unsupported |
| offset window | dropped |
| cumulative, conversion, `fill_nulls_with` | unsupported |
| saved queries, `meta`, config, topic, AI context | not generated |

Omni imports the compiled manifest. Run `dbt parse`, push the configured Git branch, and inspect the sync result.

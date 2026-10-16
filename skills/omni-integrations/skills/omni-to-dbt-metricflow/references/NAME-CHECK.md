# Checking the dbt Project for Existing Names

## Searches

```bash
# Names: match block style (- name: x) and inline flow-map style (- { name: x, ... }).
rg -n "name:\s*['\"]?(total_sale_price|sale_price_average|order_item_id)\b" models/
# Semantic models on the same dbt model: legacy ref() with either quote style, and the flattened `semantic_model:` key on the models[] entry.
rg -n "model:\s*ref\(['\"]order_items['\"]\)" models/
rg -n -B1 -A3 "^\s*-\s*name:\s*['\"]?order_items\b" models/ | rg -n "semantic_model:"
```

The flattened spec attaches the semantic model to the `models:` entry, so the second search alone misses it. Treat a `semantic_model:` hit under the target model as an existing semantic model.

## Options for each match

| Situation | Options to offer |
|---|---|
| Semantic model already exists for the same `ref()` | Extend it (default). Never add a second one. |
| Same-named measure or metric with the **same** aggregation and expression | Reuse it. Do not write a duplicate. |
| Same-named measure or metric with a **different** definition | Rename the export (suggest `<name>_omni`), replace the dbt definition (only if the user owns it), or skip the field. |
| Same-named dimension or entity with a different `expr` | Rename or skip. A renamed entity must be renamed on both sides of the join. |
| Name matches a column on the dbt model | Skip. Omni skips a dbt measure or metric whose name matches an existing dimension (`ConflictsWithExistingDimension`). |

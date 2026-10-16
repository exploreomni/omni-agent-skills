# Enumerating Values for Categorical Fields

For closed-set enums, use `all_values` so Blobby knows every valid filter value:

```yaml
dimensions:
  status:
    all_values: [complete, pending, cancelled, returned]
  payment_method:
    all_values: [credit_card, debit_card, bank_transfer, paypal, gift_card]
```

For open-ended categoricals where a full list isn't practical, use `sample_values` to give representative examples:

```yaml
dimensions:
  product_category:
    sample_values: [Electronics, Clothing, Home & Garden, Sports, Books]
  city:
    sample_values: [New York, Los Angeles, Chicago, Houston, Phoenix]
```

> **Note**: `all_values` is pruned first, so don't count on it surviving in a context-tight topic — put anything load-bearing in `ai_context` instead.

When the [dbt integration](https://docs.omni.co/integrations/dbt/setup) is enabled, dbt `accepted_values` tests are ingested as `all_values` automatically — check before hand-authoring them.

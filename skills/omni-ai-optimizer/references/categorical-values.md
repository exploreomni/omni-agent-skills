# Enumerating Values for Categorical Fields

Use `sample_values` so Blobby knows the values a field holds. For a small closed set, list every value; for an open-ended categorical, give representative examples:

```yaml
dimensions:
  status:
    sample_values: [complete, pending, cancelled, returned]
  payment_method:
    sample_values: [credit_card, debit_card, bank_transfer, paypal, gift_card]
  product_category:
    sample_values: [Electronics, Clothing, Home & Garden, Sports, Books]
  city:
    sample_values: [New York, Los Angeles, Chicago, Houston, Phoenix]
```

`all_values` is deprecated. An existing `all_values` still loads and still reaches the agent as the field's complete value list, which can make it treat any other value as invalid. Don't add new ones, and don't set both on one field: when Omni writes the field back, it keeps only `sample_values`.

Fields that already define their values don't need either: a grouped or binned dimension sends its group or bin names, and a filter `suggestion_list` of up to 25 values is sent as the field's values ([context window](context-window.md#pruning-order)).

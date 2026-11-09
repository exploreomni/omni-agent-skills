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

`all_values` is deprecated. An existing one still reaches the agent as the field's complete value list, so the agent may treat any other value as invalid. To replace it, move its values to `sample_values`; when a field has both, Omni keeps only `sample_values` the next time it writes the field.

Fields that already define their values don't need either: a grouped or binned dimension sends its group or bin names, and a filter `suggestion_list` of up to 25 values is sent as the field's values ([context window](context-window.md#pruning-order)).

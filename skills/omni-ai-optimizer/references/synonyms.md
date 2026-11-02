# Synonyms Examples

`synonyms` works on dimensions, measures and filter-only fields (a view's `filters:`):

```yaml
dimensions:
  customer_name:
    synonyms: [client, account, buyer, purchaser]
  order_date:
    synonyms: [purchase date, transaction date, order timestamp]

measures:
  total_revenue:
    synonyms: [sales, income, earnings, gross revenue, top line]
  average_order_value:
    synonyms: [AOV, avg order, basket size]

filters:
  region_filter:
    type: string
    synonyms: [territory, market]
```

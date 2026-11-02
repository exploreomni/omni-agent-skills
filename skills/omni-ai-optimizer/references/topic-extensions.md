# AI-Specific Topic Extension Example

A curated topic variant for Blobby, built with `extends`:

```yaml
# ai_order_transactions.topic
extends: [order_items]
label: AI - Order Transactions

fields:
  - order_items.created_at
  - order_items.status
  - order_items.total_revenue
  - order_items.count
  - users.name
  - users.state
  - products.category

ai_context: |
  Curated view of order data for AI analysis.
  [detailed context here]
```

`fields` narrows the topic for everyone who uses it. To narrow only what the AI sees, use `ai_fields` instead, for example `ai_fields: [tag:use_for_ai]`.

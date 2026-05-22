# Job Result → queryPresentation Transformation

Converts an `omni ai job-submit` result into a `queryPresentation` object suitable for use in `omni documents create` or a dashboard PUT.

## Why transformation is required

Blobby co-emits `userEditedSQL` alongside `calculations[]` on most job responses. When both are present, `userEditedSQL` takes precedence and shadows the structured calc. More critically, `userEditedSQL` silently bypasses topic-level `always_where_sql`, `always_where_filters`, and row-level access controls — the query executes as raw SQL against the base view, ignoring all topic filters. It must always be stripped.

The `${Order Items}` topic-display-name token inside `userEditedSQL` resolves only in the jobs API execution context. It fails in `omni query run` and in the dashboard tile renderer and is not a safe rewrite target.

## Algorithm

```python
AGGREGATE_OPS = {
    "SqlStdOperatorTable.SUM", "SqlStdOperatorTable.COUNT",
    "SqlStdOperatorTable.AVG", "SqlStdOperatorTable.MIN",
    "SqlStdOperatorTable.MAX",
}

def extract_field_refs(expr):
    """Recursively collect all field_name references in an AST expr."""
    refs = set()
    if not expr: return refs
    if expr.get("type") == "field":
        refs.add(expr["field_name"])
    for op in expr.get("operands", []):
        refs |= extract_field_refs(op)
    return refs

def job_result_to_presentation(name, topic_display_name, job_result):
    gqs = [a for a in job_result["actions"] if a["type"] == "generate_query"]
    result = gqs[-1]["result"]
    q = result["query"]
    crf = result.get("csvResultFields", {})   # at result level, not inside query

    # 1. Strip presentation cruft and the SQL override — always
    for k in ("metadata", "parsed", "model_extension_id", "userEditedSQL"):
        q.pop(k, None)

    # 2. When calculations[] is empty, reconstruct invented fields from csvResultFields.
    #    Signal: extension_model_id set + expr.type == "call".
    #    Skip fields whose top-level expr operator is an aggregate (SUM, COUNT, etc.) —
    #    those are filtered measures, not table calcs, and cannot be reconstructed here.
    if not q.get("calculations"):
        rebuilt, new_fields = [], []
        for field_ref in q.get("fields", []):
            meta = crf.get(field_ref, {})
            expr = meta.get("expr") or {}
            if meta.get("extension_model_id") and expr.get("type") == "call":
                if expr.get("operator") in AGGREGATE_OPS:
                    continue  # filtered measure — add to model instead
                calc_name = meta["field_name"]  # e.g. "revenue_label", no view prefix
                rebuilt.append({
                    "calc_name": calc_name,
                    "label": calc_name.replace("_", " ").title(),
                    "sql_expression": expr,
                })
                new_fields.append(calc_name)
            else:
                new_fields.append(field_ref)

        # 3. Ensure every field referenced inside a calc expr is present in fields[].
        #    Missing refs cause "field referenced by calculation must be included" errors.
        for calc in rebuilt:
            for ref in extract_field_refs(calc["sql_expression"]):
                if ref not in new_fields:
                    new_fields.insert(new_fields.index(calc["calc_name"]), ref)

        if rebuilt:
            q["calculations"] = rebuilt
            q["fields"] = new_fields

    fields = q.get("fields", [])
    return {
        "name": name,
        "topicName": topic_display_name,
        "prefersChart": False,
        "visType": "basic",
        "fields": fields,
        "query": q,
        "config": {},
    }
```

## How the discriminator works

Blobby-invented fields (CASE labels, DATEDIFF columns, ROUND, CONCAT, etc.) are parsed from SQL and stored in a transient query extension model during job execution. The `extension_model_id` flag on a `csvResultFields` entry identifies them. Real model fields — even if they also appear in `csvResultFields` — have `expr.type` of `"field"` or `"reference"`, not `"call"`.

The query extension model is only live during the job run. The reconstructed `calculations[]` entry is self-contained — its `sql_expression` references only real model fields and works in any document context without the extension model.

### Concrete example (05-case CASE label)

Raw job result `query` object (before transformation):

```json
{
  "fields": [
    "ecomm__order_items.created_at[month]",
    "ecomm__order_items.total_revenue",
    "ecomm__order_items.revenue_label"
  ],
  "calculations": [],
  "userEditedSQL": "SELECT ..., CASE WHEN ... END AS revenue_label FROM ${Order Items}",
  "model_extension_id": "dde0e393-f305-4bd8-9f60-1185010dcc3e"
}
```

`csvResultFields` entries for the three field refs:

| field_ref | `extension_model_id` | `expr.type` | result |
|---|---|---|---|
| `ecomm__order_items.created_at[month]` | absent | `"reference"` | pass through |
| `ecomm__order_items.total_revenue` | present | `"field"` | pass through (model alias) |
| `ecomm__order_items.revenue_label` | present | `"call"` | reconstruct |

After transformation:

```json
{
  "fields": [
    "ecomm__order_items.created_at[month]",
    "ecomm__order_items.total_revenue",
    "revenue_label"
  ],
  "calculations": [{
    "calc_name": "revenue_label",
    "label": "Revenue Label",
    "sql_expression": {
      "type": "call",
      "operator": "SqlStdOperatorTable.CASE",
      "operands": [
        {
          "type": "call",
          "operator": "SqlStdOperatorTable.GREATER_THAN",
          "operands": [
            {"type": "field", "field_name": "ecomm__order_items.total_revenue"},
            {"type": "literal", "value": 1000000}
          ]
        },
        {"type": "literal", "value": "high"},
        {"type": "literal", "value": "low"}
      ]
    }
  }]
}
```

## Aggregate calcs (SUMIF, COUNTIF patterns)

When the top-level `expr` operator is an aggregate function (`SUM`, `COUNT`, etc.), Blobby authored a filtered aggregate — not a post-aggregation table calc. Adding the referenced fields to `fields[]` would change the query grain. These are skipped by the algorithm. Add them to the model as filtered measures instead:

```yaml
measures:
  complete_revenue:
    aggregate_type: sum
    sql: ${sale_price}
    filters:
      - field: status
        value: Complete
```

## Field ref injection

When a calc's `expr` references a field not already in `fields[]` — e.g. ROUND referencing `total_revenue` that was the only non-invented field and got elided, or DATEDIFF referencing `created_at` at a different timeframe granularity than what appears in `fields[]` — the missing ref is injected ahead of the calc. This may introduce an extra column in the output but is otherwise correct.

## Topic security

The structured path (no `userEditedSQL`) routes through `join_paths_from_topic_name`, applying `always_where_sql`, `always_where_filters`, and row-level access controls correctly. Confirmed: a topic with `always_where_sql: "${status} = 'Complete'"` produces the correct `WHERE "STATUS" = 'Complete'` clause through the reconstructed path; `userEditedSQL` with a view-name FROM clause returns all rows with no WHERE.

## Sanity checking via extension model YAML

Each job result's `model_extension_id` points to a query extension model containing the invented field definitions as standard view YAML. The `sql:` field in that YAML matches `csvResultFields[field].sql` exactly — they are the same source of truth, and `csvResultFields[field].expr` is simply the parsed AST of that SQL string. To inspect:

```bash
omni models yaml-get <model_extension_id> --filename "<view_name>.view" -o json
```

# Handling and Validating Results

How to check a query response before trusting or presenting it, and how to decode the default Arrow response.

## Result Validation

Every query response should be checked before trusting the results or presenting them to the user.

**Check for errors:**
- If the response contains an `error` key, the query failed. Common causes: bad field name, missing join path, malformed filter expression, permission error.
- If the response contains `remaining_job_ids`, the query is still running — poll with `omni query wait` before checking results.

**Check row count** (field is `cache_metadata.num_rows`):
- `cache_metadata.num_rows == 0` — the query returned no data. This may be valid (e.g., no data in the filter range) but is worth flagging to the user. Common causes: overly restrictive filters, wrong date range, field that doesn't match any rows.
- `cache_metadata.num_rows` equals the `limit` you set — results may be truncated. If the user needs complete data, re-run with a higher limit or `null` for unlimited.

**Spot-check data with CSV:**

When accuracy matters, request CSV and scan the output:

```bash
omni query run --body '{
  "query": { ... },
  "resultType": "csv"
}'
```

Check that:
- Column headers match the fields you requested
- Values are in expected ranges (e.g., revenue isn't negative, dates aren't in the future)
- Aggregations make sense (e.g., a count isn't returning a sum)

**Validate filter behavior:**

If your query includes filters, verify they're being applied:

```bash
# Run the same query without filters
omni query run --body '{ "query": { ... (no filters) ... }, "resultType": "csv" }'

# Compare row counts — filtered should be <= unfiltered
```

If both queries return the same row count, the filter may not be binding — check the field name, and that the filter object matches its field type (a `boolean` needs `is_negative`, not `kind`/`values` — a mismatch is silently ignored). Confirm the condition appears in `summary.display_sql` (`cache:"SkipCache"`).

## Decoding Arrow Results

```python
import base64, pyarrow as pa
arrow_bytes = base64.b64decode(response["data"])
reader = pa.ipc.open_stream(arrow_bytes)
df = reader.read_all().to_pandas()
```

## Streaming large results in chunks (CLI ≥ 1.5.0)

For a result too large to hold in one response — or when a connection drops mid-download — split the result off from completion with `--completion-only true` and fetch it afterwards with `omni query results`. The job lines from `query run` / `query wait` then omit `result`; the Arrow IPC bytes come back as base64 slices you append and parse once `stream_stats.next_offset` is `null`. Results stay readable for roughly an hour after the job completes.

```bash
# 1. Wait for completion without downloading the payload
omni query wait --job-ids "$JID" --completion-only true

# 2. Read the result in slices (resume on drop by passing the previous next_offset)
omni query results --job-id "$JID" --offset 0
```

On `omni query run`, set `"completionOnly": true` at the body's top level for the same effect. Cannot combine with `resultType`.

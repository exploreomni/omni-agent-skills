# Validating and Testing Branch Changes

Full reference for Step 2 of the model-builder workflow. Every YAML write must be validated and tested before merging — silent failures are common: a field can be valid YAML yet produce wrong results or broken queries.

## Run model validation

```bash
omni models validate <modelId> --branchid <branchId>
```

Check the response:
- If any issue has `is_warning: false`, it's an error — fix before proceeding
- Common errors: broken column references, duplicate field names, invalid SQL syntax, missing join paths
- If `auto_fix` is present, review the suggestion before applying

## Test new/modified fields with a query

Run a query that exercises the fields you just created or modified:

```bash
omni query run --body '{
  "query": {
    "modelId": "<modelId>",
    "table": "your_view",
    "fields": ["your_view.new_dimension", "your_view.new_measure"],
    "limit": 10,
    "join_paths_from_topic_name": "your_topic"
  },
  "branchId": "<branchId>"
}'
```

> **Two complementary validation tools:**
> - `omni query run` — structured validation using explicit field expressions; use to precisely test specific dimensions, measures, and join paths
> - `omni ai job-submit --branch-id <branchId> --topic-name <topicName>` — natural language validation; use to confirm the topic answers business questions correctly against live branch data. `omni ai generate-query --run-query true` does not resolve branch-only topics at execution time and should not be used for branch validation.

**What to check:**
- **No error in response** — if the query returns an error, the field SQL is broken (bad column reference, wrong aggregate, dialect mismatch)
- **`summary.row_count` > 0** — confirms the field resolves to actual data
- **Values look correct** — spot-check that a `sum` isn't returning a `count`, that a boolean dimension returns true/false (not 0/1 unexpectedly), etc.
- **Joins work** — if your field references another view (e.g., `${users.id}`), include fields from both views to confirm the join resolves

## Test the join path (if you modified a relationship or topic join)

Build the validation query **on the topic** — `table` = base view + `join_paths_from_topic_name` (joined-view fields resolve through the topic's join map). For the full query shape and how the join map works, see **`omni-query`**'s *Build queries on a topic*.

```bash
omni query run --body '{
  "query": {
    "modelId": "<modelId>",
    "table": "base_view",
    "fields": ["base_view.id", "joined_view.some_field"],
    "limit": 10,
    "join_paths_from_topic_name": "your_topic"
  }
}'
```

A working join returns rows with data from both views. A broken join returns an error or null values in the joined columns.

## Verify the field appears in the model

```bash
# Check the topic to confirm new fields are listed
omni models get-topic <modelId> <topicName> --branch-id <branchId>

# Or read back the YAML you just wrote
omni models yaml-get <modelId> --filename your_view.view --branchid <branchId>

```

Confirm your new fields are listed in the response. If they're missing, the YAML write may have silently failed (e.g., wrong `fileName`, malformed YAML string) — or the view may live in an offloaded schema that `yaml-get` doesn't surface. Before concluding a view doesn't exist, run the lazy-load fallback (see SKILL.md → "Fallback: View Missing from yaml-get").

> **Confirm you didn't create a duplicate.** `success: true` means accepted, not that it hit the intended file (see SKILL.md → Step 1). Re-list files and check the same view name doesn't now exist at two paths (e.g. `MARTS/foo.view` and `foo.view`); if it does, delete the stray one (empty `yaml`) and re-write with the full-path key.

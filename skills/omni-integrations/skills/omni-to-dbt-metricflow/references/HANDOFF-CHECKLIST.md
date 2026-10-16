# Export Handoff Checklist

Before handing off an Omni-to-dbt export, report these facts:

- the export scope (fields, view, or topic) and the dbt model for each exported view;
- the selected YAML shape;
- every primary and foreign entity;
- the aggregate time dimension;
- each atomic measure and its user-facing metric;
- every filter qualifier and fixed-date `TimeDimension`;
- each model-layer dimension override and the selected option;
- every field skipped and its reason;
- the semantic-model and metrics file paths;
- `dbt parse` status;
- `mf validate-configs` status (say whether warehouse checks ran);
- the `mf query --explain` result for new filter patterns; and
- the grouped parity results (transformed measures, filtered counts) and each saved-query run.

For Step 10, also report the dbt environment, resolved Git branch, exact merged file key, removed extension keys, validation result, query result, and whether promotion is still pending.

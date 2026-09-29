# Parity Checks

Static checks do not prove that the numbers match. Run these comparisons against the warehouse and show the user the values side by side:

| Check | How | What must match |
|---|---|---|
| Result parity for a transformed measure | `mf query --metrics <metric> --group-by <entity>__<dimension>` and the same grouping in Omni (`omni query run`) | Every group value, for any measure whose dimension carried an Omni override |
| Grouped parity for a filtered metric | Query the filtered metric alone, then together with an unfiltered one, grouped, on data where some group has no matching rows | With the predicate inside `expr`, the empty group is present in both queries: 0 for `count`, `count_distinct`, `sum`, NULL for the others. With a cross-view metric `filter`, the group is absent alone and NULL together; report it |
| Saved queries run | `mf query --saved-query <name>` | Rows return; `group_by` uses object syntax (`TimeDimension('metric_time', 'month')`, `Dimension('<entity>__<dim>')`), not the CLI form `metric_time__month` |

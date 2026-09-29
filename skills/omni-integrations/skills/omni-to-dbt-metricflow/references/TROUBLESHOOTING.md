# Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| MetricFlow cannot resolve a filter | Wrong qualifier | Use `entity__dimension`. Run `mf query --explain`. |
| `dbt-sync` fails with no detail in `jobs-get-status` | The Git branch was not applied (production environment ignores `--dbt-git-branch`), or the dbt project does not compile | Check `branch-dbt-get`. For an unmerged dbt branch, bind a non-production environment. Read the IDE dbt Sync page for compile errors. |
| Branch write succeeds but changes nothing | Used `mode: extension` | Read and write the flat branch file key with `mode: merged`. |
| dbt field is missing from combined output | Extension has `ignored: true` | Find that extension entry. Remove `ignored` only with user approval. |
| Imported field retains Omni label, SQL, or filters | Extension key wins during merge | Remove only the conflicting extension key. dbt-only keys still fill in. |
| `column "<dim>" not found` or `invalid identifier` at query time (DuckDB: `Binder Error`), but `mf validate-configs --skip-dw` passed | A measure `expr` names a semantic dimension | Use the physical column, or materialize the transform in the dbt model SQL. Run `mf validate-configs` without `--skip-dw`. |
| A filtered metric shows NULL, or omits a group, where Omni shows the group | Metric `filter` drops the group before aggregation | For a same-view predicate, put it inside `expr` (Step 6 table). For a cross-view predicate, report the difference. |
| `mf query --explain`: `does not match any of the available group-by-items` on a metric `filter`, but `dbt parse` and `mf validate-configs` passed | The filtered dimension was not exported, usually dropped as `hidden: true` | Export the dimension. Step 4 keeps every dimension a kept measure filters on. |
| Weekly groupings differ between MetricFlow and Omni | Omni `week_start_day` is not Monday; MetricFlow `week` is Monday (Snowflake: `WEEK_START`) | Add a custom granularity to the time spine (Week start day in FIELD-MAPPING.md) and group by `metric_time__<name>` instead of `metric_time__week`. |
| `dbt parse`: `ParseJinjaObjectException` on `{{metric_time__month}}` | Saved query `group_by` used the CLI form | Use `"TimeDimension('metric_time', 'month')"`. |
| `WARNING … fix_proxy_metrics: Metric <name> should not have an expr set if it's proxy from measures` on `dbt parse` | `create_metric: true` on a measure with a non-trivial `expr` | Ignore. Validation and results are unaffected. |
| `Invalid name 'day' - names cannot match reserved time granularity keywords` | Dimension named after a granularity | Rename the dimension and set `expr` to the column. |
| Measure applies a discount twice | dbt expr and Omni dimension both transform it | Move logic to dbt, remove the Omni dimension override in Step 10, or skip the measure. |
| dbt parse reports a mapping error after append | Existing YAML lacked trailing newline | Check `tail -c1 <file> | xxd`; add a newline before appending. |
| Query result is base64 Arrow | `resultType` was omitted or nested under `query` | Put `"resultType": "json"` at the top level. |
| Legacy spec warning is expected | Assumed dbt 1.12 always warns | dbt 1.12.4 did not warn. Use the project format. |

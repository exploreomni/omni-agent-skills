# Make Omni Fall Back to the dbt Definition

Use this procedure after the exported YAML is in dbt. Omni brings the dbt semantic layer in on schema refresh or dbt sync, but an Omni model-layer field with the same name still wins. This procedure removes that override so the dbt definition shows through. Work on an Omni branch. Do not promote without user confirmation.

Worked example. The examples below use an e-commerce model: Omni view `omni_dbt_ecomm__order_items` backed by dbt model `order_items`, joined to `omni_dbt_ecomm__users` on `user_id`. Replace the view, model, column, and entity names with your own.

## How the Sync Works

Omni compiles the dbt manifest from the configured Git branch and dbt environment. A connection schema refresh (Refresh now, the schedule, or `omni models refresh`) also runs a dbt sync.

Prefer the narrowest trigger:

| Trigger | Scope | Use when |
|---|---|---|
| `omni models dbt-sync <modelId> --branch-id <branchId>` | dbt manifest only, no database scan | Only the dbt YAML changed (the normal case for this skill) |
| `omni models refresh <modelId> --hard-refresh false --schemas <schema> --tables <t1,t2>` | Listed schemas and tables only; additive (dropped objects stay) | The warehouse tables behind the exported views also changed |
| `omni models refresh <modelId>` | Every schema, hard refresh | Not for this workflow. It pulls every warehouse change into the model and is slow on large warehouses |

`--schemas` and `--tables` take comma-separated names; `*` wildcards work (`ORDER_*`). Both need `--hard-refresh false`. Always pass `--schemas` with `--tables`: a table filter alone scans every schema and takes about three times longer. Lowercase names are accepted. The job status reports only `COMPLETED`; it does not say how many objects matched, so a misspelled name refreshes nothing without an error. Read the view back with `yaml-get` to confirm. Add `--branch-id` only when the connection has branch-based schema refresh enabled; if it is not enabled the API rejects `branch_id`, and the refresh writes to the shared schema model, not the branch. Check with `omni models refresh --help`. If the dbt YAML is already merged to the default dbt branch, the next refresh brings it in and you can skip the environment binding below. If it is still on a dbt branch, push that branch and use `dbt-sync` on an Omni branch bound to it. `dbt-sync` starts a background job.

```bash
omni models dbt-sync <modelId> --branch-id <branchId>
omni models jobs-get-status <jobId>
```

`jobs-get-status` returns only `job_id`, `job_type: "dbt_sync"`, and `status`. Poll until the job reaches a terminal status. A default environment ignores `--dbt-git-branch`. The sync job then fails with no detail in `jobs-get-status`. Inspect sync failures on the IDE dbt Sync page. The CLI has no command that reports those issues.

## Layer Precedence and Merge Behavior

The precedence order is:

```text
schema/dbt < model extension < topic-scoped fields: override < workbook model
```

Omni merges a same-named field key by key. Extension keys win. dbt-only keys fill in. A dbt provenance comment is added even when a key is masked.

For example, an extension can retain `sql`, tags, format, synonyms, and `ai_context`. The dbt import can still add a description or an `sql` key that the extension does not define.

Fields marked `ignored: true` in the extension never appear in combined output. An extension can hide an imported dbt measure this way.

## Branch Procedure

This procedure follows `omni-model-builder` → Safe Development Workflow (Steps 0–3) for every Omni model write. Only steps 2–4 below are dbt-specific. The other steps repeat the model-builder rules with the dbt-branch differences called out. Before you start, run `omni whoami whoami --model-id <modelId>`: `QUERY_FULL_MODEL` lets you branch; `UPDATE` lets you merge.

1. Create a unique Omni branch (`omni-model-builder` Step 0). The response `model.id` is the `branchId`. Do not delete a branch you did not create.

   ```bash
   omni models create-branch <modelId> --name <unique-branch>
   ```

2. Decide which dbt environment the branch needs. The Omni branch isolates the Omni-side change on its own. The environment only picks the dbt Git branch that gets compiled. If the dbt YAML is merged to the default dbt branch, keep the production environment and skip step 3. If the YAML is still on an unmerged dbt branch, list the environments and pick an existing one with `isDefaultEnvironment: false`. Do not create a dbt environment without asking the user.

   ```bash
   omni connections dbt-environments-list <connectionId>
   ```

3. (Unmerged dbt branch only.) Bind the non-production environment and the dbt Git branch. Read it back. `branch-dbt-get` must show the requested Git branch and `is_default_environment: false` before you sync.

   ```bash
   omni models branch-dbt <modelId> <branchName> <nonProdDbtEnvId> --dbt-git-branch <git-branch>
   omni models branch-dbt-get <modelId> <branchName>
   ```

   The production/default environment ignores `--dbt-git-branch`. `branch-dbt` returns success, but `branch-dbt-get` still shows the default Git branch and `is_default_environment: true`. That is fine when the YAML is merged. For an unmerged dbt branch, use a non-production environment instead.

4. Run `dbt-sync`. Poll to a terminal status. Do not infer sync details from the status response.

   ```bash
   omni models dbt-sync <modelId> --branch-id <branchId>
   omni models jobs-get-status <jobId>
   ```

5. Read the branch override file (`omni-model-builder` Step 1 read-modify-write) with `--mode merged`. Read the topic for higher-layer `fields:` overrides. Read the workbook model if the field exists only there.

   ```bash
   omni models yaml-get <modelId> --branch-id <branchId> --mode merged --file-name <exact-file-key>
   omni models yaml-get <modelId> --branch-id <branchId> --mode merged --file-name <topic>.topic
   ```

   On a branch, `--mode extension` returns only the branch delta layer, usually `model` and `relationships`. Do not use it as the view override file.

   File keys differ by mode. Combined output uses `<schema>/<view>.view`. Merged and extension output use `<schema>__<view>.view`. Reuse the key exactly as returned.

6. Identify the exact key that blocks dbt. Remove only the needed model-layer field. Preserve other authored content. If the imported measure depends on an Omni dimension override, follow the dimension-override rule before writing.

   ```yaml
   # Remove this override before importing a measure whose dbt expr already applies it.
   dimensions:
     sale_price:
       sql: '"SALE_PRICE" * 0.95'
   ```

7. Write the complete merged file. `yaml-create` is a whole-file write. On a branch, use the flat returned key and `mode: "merged"` in the body.

   ```json
   {
     "fileName": "omni_dbt_ecomm__order_items.view",
     "yaml": "<full merged file minus the one field>",
     "mode": "merged",
     "branchId": "<id>"
   }
   ```

   ```bash
   omni models yaml-create <modelId> --body @file.json
   ```

   A branch write with `mode: extension` can store a stub that does not change the merged or combined view. Do not use it for this write.

8. Read the composed result. Make sure the dbt provenance comment is present. Re-sync only if the dbt manifest changed. Removing a conflicting extension key does not require a second sync.

   ```bash
   omni models yaml-get <modelId> --branch-id <branchId> --mode combined --file-name <combined-file-key>
   ```

9. Run `models validate` on the branch (`omni-model-builder` Step 2). The command returns a bare JSON list of issues. Do not expect an object with an `issues` key.

   ```bash
   omni models validate <modelId> --branch-id <branchId>
   ```

10. Run a branch query. Put `branchId` and `resultType: "json"` at the top level. Put `modelId`, `table`, `fields`, `limit`, `sorts`, and `join_paths_from_topic_name` in `query`. Without top-level `resultType`, the response is base64 Arrow.

    ```json
    {
      "branchId": "<branchId>",
      "resultType": "json",
      "query": {
        "modelId": "<modelId>",
        "table": "omni_dbt_ecomm__order_items",
        "fields": ["omni_dbt_ecomm__order_items.total_sale_price"],
        "limit": 10,
        "sorts": [],
        "join_paths_from_topic_name": "<topic>"
      }
    }
    ```

    ```bash
    omni query run --body @query.json
    ```

11. Check the promotion path (`omni-model-builder` Step 3, Path A or Path B).

    > ✋ **STOP** — Both commands change shared state. Ask the user before either action.

    ```bash
    omni models git-get <modelId>
    omni models commit <modelId> --body '{"branch_id":"<branchId>","commit_message":"Let dbt definition win"}'
    omni models merge-branch <modelId> <branchName>
    ```

## Worked example: before and after

Remove only the extension field that blocks the dbt definition. In this worked example, that field is `total_sale_price` in the merged branch file.

```yaml
# Before: extension wins
measures:
  total_sale_price:
    sql: ${omni_dbt_ecomm__order_items.sale_price}
    tags: [use_for_AI]
    format: BIGCURRENCY_2
    synonyms: [Revenue, Total Sales]
    ai_context: Use for financial trends.
```

```yaml
# After: dbt definition appears in combined YAML
measures:
  total_sale_price:
    # Measure is defined by the 'total_sale_price' dbt metric (models/semantic-models/sem_order_items.yml)
    sql: ${omni_dbt_ecomm__order_items.sale_price} * 0.95
    description: Total USD amount sold
    aggregate_type: sum
```

Removing the extension field lets the dbt definition supply its SQL, description, and aggregation. It also removes extension-only tags, format, synonyms, and AI context.

General rule: remove a dimension override when an imported measure's dbt expression already applies that transformation. In this example, keeping the `sale_price` override makes the branch query compute `SUM("SALE_PRICE" * 0.95 * 0.95)`. Step 6 of the Branch Procedure removes that override too.

## Importer Support Matrix

| dbt object | Omni result |
|---|---|
| primary entity | primary key when the schema view has none |
| foreign entity | hidden `_entity_<name>` dimension and supported relationship |
| dimension with `expr` | Omni dimension |
| time granularity | no Omni timeframe mapping |
| supported aggregation | aggregation measure |
| simple metric with one `Dimension` filter | separate measure and hidden `_filter_<metric>` dimension |
| existing model-extension field | keys merge; extension wins per key; dbt-only keys fill in |
| extension field with `ignored: true` | field is absent from combined output |
| `TimeDimension`, `Metric`, `sum_boolean`, non-additive dimension | unsupported |
| ratio metric | measure on the denominator view |
| derived metric | measure on the first input view |
| offset window | dropped |
| cumulative, conversion, fill-null behavior | unsupported |
| saved queries, meta, config, topic, AI context | not generated |

## Verification Checklist

- The dbt branch is pushed.
- `branch-dbt-get` shows the requested Git branch and a non-default environment.
- The branch write used the exact merged file key and `mode: "merged"`.
- Combined YAML has the expected provenance comment.
- `omni models validate` was parsed as a bare list.
- One `omni query run` completed with top-level `resultType: "json"`.
- No promotion occurred without user confirmation.

## Adapt to your project

| Substitute | Use in your project |
|---|---|
| Omni view name | `<schema>__<view>` |
| dbt model name | The model name in `ref('<model>')` |
| Semantic model name | `sem_<model>` or the project convention |
| Entity names | FK column names on the many side |
| Aggregate time dimension | The model's time dimension for `agg_time_dimension` |
| dbt project YAML layout | Legacy or flattened |
| dbt YAML file layout | `models/semantic-models/` or the project's semantic-YAML location |
| Omni file keys | `<schema>/<view>.view` in combined mode; `<schema>__<view>.view` in merged mode |

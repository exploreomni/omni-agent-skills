# Pull the dbt Semantic Layer into Omni

Use this procedure to inspect a dbt semantic-layer import and let a dbt definition replace an Omni model-layer override. Work on an Omni branch. Do not promote without user confirmation.

## How the Sync Works

Omni compiles the dbt manifest from the configured Git branch and dbt environment. Push the dbt branch before sync. `dbt-sync` starts a background job.

```bash
omni models dbt-sync <modelId> --branch-id <branchId>
omni models jobs-get-status <jobId>
```

`jobs-get-status` returns only `job_id`, `job_type: "dbt_sync"`, and `status`. A live sync completed in about 30 seconds. A default-environment sync failed after about 150 seconds with no CLI error detail. Inspect sync failures on the IDE dbt Sync page. The CLI has no command that reports those issues.

## Layer Precedence and Merge Behavior

The precedence order is:

```text
schema/dbt < model extension < topic-scoped fields: override < workbook model
```

Omni merges a same-named field key by key. Extension keys win. dbt-only keys fill in. A dbt provenance comment is added even when a key is masked.

For example, an extension can retain `sql`, tags, format, synonyms, and `ai_context`. The dbt import can still add a description or an `sql` key that the extension does not define.

Fields marked `ignored: true` in the extension never appear in combined output. This is how the demo hides four dbt measures.

## Branch Procedure

1. Create a unique Omni branch. Record its ID. Do not delete a branch you did not create.

   ```bash
   omni models create-branch <modelId> --name <unique-branch>
   ```

2. List dbt environments for the connection. Select an existing environment with `is_default: false`. Do not create a dbt environment without asking the user.

   ```bash
   omni connections dbt-environments-list <connectionId>
   ```

3. Bind the selected non-production environment and the dbt Git branch. Read it back. `branch-dbt-get` must show the requested Git branch and `is_default_environment: false` before you sync.

   ```bash
   omni models branch-dbt <modelId> <branchName> <nonProdDbtEnvId> --dbt-git-branch <git-branch>
   omni models branch-dbt-get <modelId> <branchName>
   ```

   A production/default environment ignores `--dbt-git-branch`. `branch-dbt` returns success, but `branch-dbt-get` continues to show `git_branch: main` and `is_default_environment: true`. Stop and choose an existing non-production environment.

4. Run `dbt-sync`. Poll to a terminal status. Do not infer sync details from the status response.

   ```bash
   omni models dbt-sync <modelId> --branch-id <branchId>
   omni models jobs-get-status <jobId>
   ```

5. Read the branch override file with `--mode merged`. Read the topic for higher-layer `fields:` overrides. Read the workbook model if the field exists only there.

   ```bash
   omni models yaml-get <modelId> --branch-id <branchId> --mode merged --file-name <exact-file-key>
   omni models yaml-get <modelId> --branch-id <branchId> --mode merged --file-name <topic>.topic
   ```

   On a branch, `--mode extension` returns only the branch delta layer, usually `model` and `relationships`. Do not use it as the view override file.

   File keys differ by mode. Combined output can use `omni_dbt_ecomm/order_items.view`. Merged and extension output can use `omni_dbt_ecomm__order_items.view`. Reuse the key exactly as returned.

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

   `mode: extension` silently stored a stub on the branch in the live test. It changed nothing in the merged or combined view. Do not use it for this write.

8. Read the composed result. Make sure the dbt provenance comment is present. Re-sync only if the dbt manifest changed. In the live test, the removal of a conflicting extension key did not need a second sync.

   ```bash
   omni models yaml-get <modelId> --branch-id <branchId> --mode combined --file-name <combined-file-key>
   ```

9. Run `models validate` on the branch. The command returns a bare JSON list of issues. Do not expect an object with an `issues` key.

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

11. Check the promotion path.

    > ✋ **STOP** — Both commands change shared state. Ask the user before either action.

    ```bash
    omni models git-get <modelId>
    omni models commit <modelId> --body '{"branch_id":"<branchId>","commit_message":"Let dbt definition win"}'
    omni models merge-branch <modelId> <branchName>
    ```

## Tested Before and After

The live test removed only the extension `total_sale_price` from the merged branch file.

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

The removal of the extension field let the dbt definition supply its SQL, description, and aggregation. It also removed the extension-only tags, format, synonyms, and AI context.

The live test left the `sale_price` dimension override in place. The branch query then computed `SUM("SALE_PRICE" * 0.95 * 0.95)`. Step 6 removes that override too.

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

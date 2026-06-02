# Schema Refresh: Syncing with Database Changes

The schema layer is auto-generated from your database. Trigger a refresh with `omni models refresh <modelId>` (add `--branch-id <branchId>` to scope to a branch; requires **Connection Admin** permissions).

**When to trigger:** new/renamed/deleted tables or columns, a new view that needs auto-generated base dimensions, or any time the model is out of sync with the database.

**What it does:** Introspects your data warehouse, auto-generates base dimensions with correct types and timeframes, detects deletions and broken references. Runs as a background job (can take several minutes).

**Side effect:** May auto-generate dimensions for columns you don't need. Suppress with `hidden: true` in your extension layer.

**Trigger via API:**

```bash
omni models refresh <modelId>

# With branch:
omni models refresh <modelId> --branch-id <branchId>
```

Requires **Connection Admin** permissions.

**Deleted or renamed columns:** If the user says a database column was deleted or renamed but does not name the exact table/column, do not stop immediately for clarification. First create a branch, refresh the schema on that branch, validate the branch, and run the content validator to identify broken model fields, dashboards, and tiles:

```bash
omni models create-branch <modelId> --name "schema-refresh-impact-check"
omni models refresh <modelId> --branch-id <branchId>
omni models validate <modelId> --branchid <branchId>
omni models content-validator-get <modelId> --branch-id <branchId>
```

Some connections do not support branch-based schema refresh. If `omni models refresh <modelId> --branch-id <branchId>` returns that `branch_id is not allowed`, run `omni models refresh <modelId>` without a branch ID, then continue with branch-scoped validation and content validation where the CLI supports it. State that schema refresh was shared because the connection does not support branch refresh.

Report the blast radius from validation and content-validator results before recommending any merge. Ask for the deleted table/column only if the refresh and validator output are too broad or ambiguous to identify the affected field.

If refresh and content validation complete successfully and the content validator returns no broken dashboards or tiles, say that no dashboard breakage was found in the checked model state. Do not turn that into a blocker; only ask for the specific deleted table/column if the user wants you to remove or hide a particular model field after the impact check.

Distinguish validation warnings from dashboard breakage. A warning such as `No join path from ...` should be reported as a model validation warning, but do not infer that it was caused by the deleted column unless validation or the content validator identifies the missing table/column directly.

If model/topic reads fail with an infrastructure error such as `This connection uses dynamic environments and you don't have a value set for the required user attribute`, stop after confirming the error on one direct model read. Report the credential or connection-environment blocker and the exact command that failed. Do not spend time probing unrelated admin APIs or trying to reconfigure connection environments unless the user explicitly asked you to administer the instance; the schema-impact workflow cannot produce a reliable blast radius until the model is readable.

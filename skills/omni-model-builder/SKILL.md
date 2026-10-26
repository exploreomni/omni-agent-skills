---
name: omni-model-builder
description: Create and edit Omni Analytics semantic model definitions — views, topics, dimensions, measures, relationships, query views, composite topics, and aggregate tables (materialized_query) — using YAML through the Omni CLI. Use this skill whenever someone wants to add a field, create a new dimension or measure, define a topic, set up joins between tables, modify the data model, build a new view, add a calculated field, create a relationship, edit YAML, work on a branch, promote model changes, or any variant of "model this data", "add this metric", "create a view for", or "set up a join between". Also use for migrating modeling patterns since Omni's YAML is conceptually similar to other semantic layer definitions.
---

# Omni Model Builder

Create and modify Omni's semantic model through the YAML API — views, topics, dimensions, measures, relationships, and query views.

> Use `omni-model-explorer` first to understand the existing model.

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: if `whoami` or any call returns **401**, ask the user to run `! omni config login <profile>`. Profile setup, when you may run the login yourself, and `--schema`: the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule.

You need **Modeler** or **Connection Admin** permissions. Add `-o json` to any command to force structured output for parsing (default `auto` is human in a TTY, JSON when piped).

## Omni's Layered Modeling Architecture

Omni composes a model from the schema layer (generated from the database), the shared model (governed fields, relationships, and topics), workbook models (ad hoc fields in one workbook), and branches, where shared-model changes are made before a merge: [model-layers.md](references/model-layers.md).

## Determine SQL Dialect

Before writing any SQL expression, look up the connection's dialect: find the model's `connectionId` with `omni models list`, then read its `dialect` from `omni connections list` (the connection name is not a reliable guide). `omni models delete` also trashes the workbooks, dashboards, and child extension models built on the model; confirm that with the user before running it. Commands, and creating a new SHARED model: [sql-dialect.md](references/sql-dialect.md).

## Schema Refresh: Syncing with Database Changes

When the database schema changes (new, deleted or renamed columns, type changes), refresh the schema layer with `omni models refresh <modelId>` (`--branch-id <branchId>` scopes it to a branch; requires **Connection Admin**). When to run it, its side effects, the impact check for deleted or renamed columns, and connection errors: [schema-refresh.md](references/schema-refresh.md).

## Known Issues & Safe Defaults

> ## 🛑 HARD STOP: never merge/promote a branch on your own initiative
>
> **`omni models merge-branch` (and any merge / promote / ship to the shared model) is a SEPARATE, USER-INITIATED step. Do not run it unless the user has told you — *in this conversation* — to merge, ship, publish, promote, or "make it live."** Preparing a branch (create → write YAML → validate → test) is the *whole* job for a "build / add / model this" request; shipping it is a distinct decision the user owns.
>
> **None of these count as merge permission — do not let them talk you past this gate:**
> - "the change is additive / small / low-risk / can't break anything"
> - "the spec (or ticket, or doc) says to model it and publish"
> - "the user gave a broad 'build the whole thing' directive"
> - "it's required for the deliverable to work" / "the dashboard won't resolve until I merge"
> - "it's just a playground / sandbox / non-git model"
>
> When the field/view is needed for downstream content but not yet merged, the correct move is a **branch-bound draft** (`omni-content-builder` → *branch-bound drafts*), **not** a merge. When a merge is genuinely needed, **stop and ask** ("Ready for me to merge `<branch>` into the shared model?") and wait for an explicit yes. If a harness/permission layer blocks the merge, that is the guardrail working — surface it and ask; do not look for another path around it.

- **Confirm the branch still exists at the start of each session and after any gap** — `omni models list --model-id <sharedModelId> --include activeBranches`. Someone else may have merged it; writes then fail with `Branch does not exist`, and drafts bound to it may already be published (check `omni documents list-drafts <identifier>`). If it was merged, diff your local YAML against the shared model and start a new branch for further changes.
- **Profile the data before modelling it.** Check grain (`COUNT(*)` vs `COUNT(DISTINCT <key>)` on every fact), implied units (value ÷ quantity per category, to catch a "hours" column that holds money), and where history starts (older records may need an opening balance). Ask the business owner what an ambiguous term ("fee type", "status") means before building on a guess.
- **Keep eval-created files on branches until confirmed** — when you create fields/views for validation, report the branch name/id, validation status, and test-query result; merging is governed by the HARD STOP above.
- **Edit with `yaml-create`, not `create-field`, `update-field`, `update-view`, `update-topic` or `models update`:** they can report success without making the change ([details](references/editing-existing-files.md#field-view-and-topic-commands)).
- **Known bug: a child layer can store a copy of an inherited `sql:` query view's SQL** (extension, workbook model, branch) and stop following the parent. Cause: an undeclared column (assume one for `SELECT *` or CTEs) or a removed dimension. Until fixed ([removing a copy](references/editing-existing-files.md#inherited-sql-query-views)):
  1. Read `--mode extension` first: a view-level `sql:` you didn't write is that copy; an `ignored: true` dimension means any write stores one. Tell the user.
  2. Otherwise write the whole `--mode combined` read back with `"mode": "extension"` (in `combined` mode the second edit copies it). Change, add or hide (`hidden: true`); never remove. Re-check as in step 1.

## Discovering Commands

```bash
omni models --help                # List all model operations
omni models yaml-create --help    # Show flags for writing YAML
omni models yaml-create --schema  # Print the body's JSON schema + a filled example (no token)
```

## Safe Development Workflow

> **Always work in a branch — never write directly to production — and first check you *can* branch.** Branching requires full-model access. Run `omni whoami whoami --model-id <modelId>`: `QUERY_FULL_MODEL` present → you can create a branch (and `UPDATE` present → you can merge/promote it, else open a PR / request a merge); absent → you can't branch — a one-off field belongs in the document's workbook model instead (`omni-content-builder` → *Updating a Dashboard's Model*). Full permission→capability map: **`omni-admin` → Model Roles & Caller Access**.

> **Hub-and-spoke: write to the model ID you were given**; don't re-route the change ([details](references/editing-existing-files.md#hub-and-spoke-setups)).

### Step 0: Create a Branch

```bash
omni models create-branch <modelId> --name "my-feature-branch"
```

The response `model.id` is your `branchId` — a UUID you'll pass to all subsequent API calls. To list existing branches at any time:

```bash
omni models list --include activeBranches
```

> **Shared extensions:** pair the extension's ID with a branch from `omni models list --base-model-id <extensionId> --model-kind BRANCH`, else the shared model's branch ([details](references/editing-existing-files.md#branches-of-a-shared-extension)).

> **⚠️ On a git-connected model, never hand-edit model YAML in git.** Author through Omni on a branch and ship with `omni models commit` (Step 3); Omni's next sync deletes model files that exist only in git. Files that aren't model content (OWNERS, CI config, docs) can be committed directly: [git-connected-models.md](references/git-connected-models.md).

### Step 1: Write YAML to a Branch

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "my_new_view.view",
  "yaml": "dimensions:\n  order_id:\n    primary_key: true\n  status:\n    label: Order Status\nmeasures:\n  count:\n    aggregate_type: count",
  "mode": "combined",
  "branchId": "{branchId}",
  "commitMessage": "Add my_new_view with status dimension and count measure"
}'
```

> **⚠️ Editing an existing file: read it whole with `--mode combined`, write it whole with `"mode": "combined"`, read it back in both modes.** Exceptions ([details](references/editing-existing-files.md#exceptions)):
> - **Inherited `sql:` query view with an undeclared column:** see *Known Issues*.
> - **`relationships`:** edit on a branch with `"mode": "merged"`; other modes copy in dbt's relationships ([steps](references/editing-existing-files.md#relationships)).
> - **`extends`:** edit from the combined read; fully-resolved content needs `"fullyResolved": true` (not yet for field or topic inline-view `extends`).
> - **No other `"mode": "merged"` writes.** New file: either mode. Delete: empty `yaml` with `"mode": "extension"`.
>
> `fileName` is the file's **exact path** (reuse the `yaml-get` key, folder prefix included); a mismatch silently creates a duplicate ([inspect a branch](references/model-layers.md#inspecting-a-branch)).

On a dbt-connected model, `omni models branch-dbt-get` shows the dbt environment a branch compiles against: [model-layers.md](references/model-layers.md#branches-on-dbt-connected-models).

### Step 2: Validate and Test

Every YAML write must be validated and tested before merging — a field can be valid YAML yet produce wrong results or broken queries.

```bash
# 1. Validate: a new is_warning:false issue in a file you changed blocks; fix it first
omni models validate <modelId> --branch-id <branchId>

# 2. Query the changed fields: no error, and cache_metadata.num_rows > 0 (there is no summary.row_count)
omni query run --body '{"query":{"modelId":"<modelId>","table":"your_view","fields":["your_view.new_dimension","your_view.new_measure"],"limit":10,"join_paths_from_topic_name":"your_topic"},"branchId":"<branchId>"}'

# 3. Read it back: the field is present, and not duplicated at a second path
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId>
```

Spot-check that values look right (a `sum` isn't returning a `count`; booleans read true/false), and if a field references another view include fields from both to confirm the join resolves. Triage of errors that predate your change, join-path tests, natural-language validation and the full checklist: [validation-and-testing.md](references/validation-and-testing.md).

> **Running totals, moving averages, period-over-period change, percent-of-total and ranks are table calculations** on the query result: **`omni-query` → `references/table-calculations.md`**. Model an in-warehouse field only when the window must span rows outside the result set.

### Step 3: Ship the Branch

> Ask the user to confirm before shipping. Changes applied to the production model cannot be easily undone. Only ship after validation and testing pass (Step 2).

Check `omni models git-get <modelId>`: a git-connected model ships as a PR with `omni models commit`; otherwise merge in Omni with `omni models merge-branch <modelId> <branchName>`. Both paths: [shipping-a-branch.md](references/shipping-a-branch.md).

#### After the merge — verify net-new topics and views (both paths)

After either path, confirm new topics and views resolve against the production model (no `--branch-id`): list the views, `get-topic` the topic, validate, and run a query whose `summary.missing_fields` is `[]`. If anything is missing, re-author it through Omni and never patch it by hand in git: [post-merge-verification.md](references/post-merge-verification.md).

## YAML File Types

Model files are views (`.view`), topics (`.topic`), composite topics (`.composite_topic`) and the relationships file: [model-layers.md](references/model-layers.md#file-types). Writing and deleting: Step 1.

## Writing Views

> **Every view that participates in joins MUST have a real `primary_key: true` dimension.** Without a row-unique primary key, queries that join to this view can produce fanout errors or incorrect aggregations. Use the table's natural unique identifier (e.g., `id`, `order_id`, `user_id`). If no single column is unique, build a composite key from row-level columns that are jointly unique, for example `sql: ${order_id} || '-' || ${line_number}`. If you cannot define a row-unique expression, do not mark a dimension as `primary_key: true` yet; fix the grain first or avoid joining the view until a real key exists. Why: [troubleshooting.md](references/troubleshooting.md#why-the-primary-key-matters-symmetric-aggregates).

### Basic View

```yaml
dimensions:
  order_id:
    primary_key: true
  status:
    label: Order Status
  created_at:
    label: Created Date
measures:
  count:
    aggregate_type: count
  total_revenue:
    sql: ${sale_price}
    aggregate_type: sum
    format: currency_2
```

### Understanding Schema Layer vs Extension Layer

Your extension YAML can override a schema-layer field of the same name, and the field keeps its schema-layer type; when a column has no schema-layer base dimension yet, refresh the schema first. Examples and `yaml-get --mode` read-back: [model-layers.md](references/model-layers.md#understanding-schema-layer-vs-extension-layer).

### Dimension Parameters

See [modelParameters.md](references/modelParameters.md) for the complete list of 35+ dimension parameters, format values, and timeframes.

Two gotchas: a raw column **auto-maps by name** (no `sql:` needed); there is **no `${TABLE}` construct** — `${TABLE}.column` errors `Column "__omni_scoped" not found` at validate/query time (reference fields via `${field}`/`${view.field}`).

### Measure Parameters

See `references/modelParameters.md` (24+ params, all 13 aggregate types) and `references/yaml-filter-syntax.md` (filter operators + measure-filter examples). **Prefer a measure `filters:` block** for filtered aggregates over `CASE WHEN`/`WHERE` in `sql` — keep `sql` focused on the value being aggregated.

### Filter-only fields and dynamic fields

**Reach for a filter-only field** when one user choice should change *how a field is computed* rather than *which rows are kept*: report by created date or shipped date, show revenue or order count in the same KPI, apply a threshold the viewer sets. **Don't** reach for it to hide or show fields (use topic `fields:`), to filter rows (an ordinary filter), or when the two variants deserve their own topics (see "new topic vs extend"). Shapes, binding, validation: [templated-filters.md](references/templated-filters.md).

### Aggregate tables (aggregate awareness)

**Reach for an aggregate table** when the same fact rollup is queried repeatedly at a coarser grain than the table (daily or monthly tiles over an event-level fact) and a pre-aggregated table exists or can be built. Declare it with a `materialized_query` block on a view, one per table, described against the base view; Omni reads it when a query fits and falls back to the fact table when not. Confirm with a `planOnly` query headed `-- Query rewritten to use materialized view`. **Never map** a window-function field (`ROW_NUMBER`, `RANK`, `LAG`, a running total) or a `*_distinct_on` measure, and never set `limit` or `offset` in `materialized_query`: each returns wrong results or stops Omni from using the table. Pin a table that holds part of the history to its dates, keep every row in the base view, and write date boundaries in model SQL as `>=` and `<`. Rules, filter pins, joined views, [what not to declare](references/aggregate-awareness.md#what-not-to-declare) and [known issues](references/aggregate-awareness.md#known-issues): [aggregate-awareness.md](references/aggregate-awareness.md).

### Level of detail

**Reach for `level_of_detail`** when a measure has to be computed at a grain other than the query's: a per-customer total on every order row (`fixed:`), a finer aggregate summarized up (`always_include:`), or an amount held at a coarser grain while finer dims are on the report (`always_exclude:`). Grain matching, the outer-aggregate rule, template reuse and verification: [level-of-detail.md](references/level-of-detail.md).

### Cross-View Fields in Views

A field whose `sql` references another view breaks in any topic that doesn't join that view; where to define it instead: [topic-scoped-definitions.md](references/topic-scoped-definitions.md#cross-view-fields-in-views).

## Fallback: View Missing from yaml-get

Before concluding a view doesn't exist, check the schemas `yaml-get` didn't load: [troubleshooting.md](references/troubleshooting.md#fallback-view-missing-from-yaml-get).

## Writing Topics

> **Before writing a topic, confirm every view it references exists** with `omni models yaml-get <modelId>`, using the fallback above for a view in a schema that isn't loaded.

### New topic vs extend an existing one

Extending an existing topic is usually right when the request's base view matches its base view. Create a new topic when the subject (base view), always-applied constraints, or audience differ; ask the requestor when it is a judgment call, and build new topics on a branch. Criteria and key topic elements: [writing-topics.md](references/writing-topics.md).

### Filter Expressions for Topics

Topic `default_filters`, `always_where_filters`, and `always_having_filters` use the measure-filter condition syntax in [yaml-filter-syntax.md](references/yaml-filter-syntax.md); a docs-search tip is in [writing-topics.md](references/writing-topics.md#filter-expressions-for-topics).

### Composite topics

One query over two facts that share dimensions but no join, or one fact under two conditions: when to reach for a composite topic and when not to, authoring, and the query shape: [composite-topics.md](references/composite-topics.md).

## Writing Relationships

### Global Relationships

Global relationships are defined in the shared relationships file and are available across all topics. Use these for standard, reusable joins, and set `relationship_type` (`many_to_one`, `one_to_many`, `one_to_one`, `many_to_many`) to match the data, which prevents fanout. Example and when to use each type: [global-relationships.md](references/global-relationships.md).

### Topic-Scoped Relationships

One-off joins and joining the same table more than once (one `extends:` alias per role), and the `joins:` entry the view also needs: [topic-scoped-definitions.md](references/topic-scoped-definitions.md#topic-scoped-relationships) · examples: [topic-scoped-relationships.md](references/topic-scoped-relationships.md).

### Topic-Scoped View Definitions

A topic's `views:` block can set `display_order`, override labels, and add topic-only fields, aliases, and query views. Rules: [topic-scoped-definitions.md](references/topic-scoped-definitions.md#topic-scoped-view-definitions) · examples: [topic-scoped-views.md](references/topic-scoped-views.md).

## Query Views

A query view needs a primary key (`primary_key: true` on one dimension, or `custom_compound_primary_key_sql`) or joins to it fan out; confirm which field is unique before writing unless the query makes it clear, and ask the user when they are unsure. Rules, including the `FROM` alias a `sql:` block with `${view.field}` references needs: [query-views.md](references/query-views.md) · examples: [query-view-examples.md](references/query-view-examples.md).

## Common Validation Errors

Fixes for frequent validation errors (unknown view, no join path, duplicate field name, invalid YAML, fanout, column not found, a duplicate view at the repo root) and for a model out of sync with the database: [troubleshooting.md](references/troubleshooting.md#common-validation-errors).

## Docs Reference

Omni docs pages for each modeling topic: [docs-links.md](references/docs-links.md).

## Related Skills

- **omni-model-explorer** — understand the model before modifying
- **omni-ai-optimizer** — add AI context after building topics
- **omni-query** — test new fields

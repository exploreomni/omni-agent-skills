---
name: omni-model-builder
description: Create and edit Omni Analytics semantic model definitions — views, topics, dimensions, measures, relationships, query views, composite topics, and aggregate tables (materialized_query) — using YAML through the Omni CLI. Use this skill whenever someone wants to add a field, create a new dimension or measure, define a topic, set up joins between tables, modify the data model, build a new view, add a calculated field, create a relationship, edit YAML, work on a branch, promote model changes, or any variant of "model this data", "add this metric", "create a view for", or "set up a join between". Also use for migrating modeling patterns since Omni's YAML is conceptually similar to other semantic layer definitions.
---

# Omni Model Builder

Create and modify Omni's semantic model through the YAML API — views, topics, dimensions, measures, relationships, and query views.

> **Tip**: Always use `omni-model-explorer` first to understand the existing model.

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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule for profile setup (`omni config init --auth oauth`) and discovering command and request-body shapes with `--schema`.

You need **Modeler** or **Connection Admin** permissions. Add `-o json` to any command to force structured output for parsing (default `auto` is human in a TTY, JSON when piped).

## Omni's Layered Modeling Architecture

Omni composes a model from the schema layer (generated from the database), the shared model (governed fields, relationships, and topics), workbook models (ad hoc fields in one workbook), and branches, where shared-model changes are made before a merge: [model-layers.md](references/model-layers.md).

## Determine SQL Dialect

Before writing any SQL expression, look up the connection's dialect: find the model's `connectionId` with `omni models list`, then read its `dialect` from `omni connections list` (the connection name is not a reliable guide). `omni models delete` also trashes the workbooks, dashboards, and child extension models built on the model; confirm that with the user before running it. Commands, and creating a new SHARED model: [sql-dialect.md](references/sql-dialect.md).

## Schema Refresh: Syncing with Database Changes

The **schema layer** is auto-generated from your database. When your database schema changes (new/deleted/renamed columns, type changes), refresh it to stay in sync: `omni models refresh <modelId>` (add `--branch-id <branchId>` to scope to a branch; requires **Connection Admin**).

See [schema-refresh.md](references/schema-refresh.md) for when to trigger, what it does and its side effects, the deleted/renamed-column impact-check workflow, and connection/credential error handling.

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

- **Keep eval-created files on branches until confirmed** — when you create fields/views for validation, report the branch name/id, validation status, and test-query result; merging is governed by the HARD STOP above.

## Discovering Commands

```bash
omni models --help                # List all model operations
omni models yaml-create --help    # Show flags for writing YAML
omni models yaml-create --schema  # Print the body's JSON schema + a filled example (no token)
```

## Safe Development Workflow

> **Always work in a branch — never write directly to production — and first check you *can* branch.** Branching requires full-model access. Run `omni whoami whoami --model-id <modelId>`: `QUERY_FULL_MODEL` present → you can create a branch (and `UPDATE` present → you can merge/promote it, else open a PR / request a merge); absent → you can't branch — a one-off field belongs in the document's workbook model instead (`omni-content-builder` → *Updating a Dashboard's Model*). Full permission→capability map: **`omni-admin` → Model Roles & Caller Access**.

### Step 0: Create a Branch

```bash
omni models create-branch <modelId> --name "my-feature-branch"
```

The response `model.id` is your `branchId` — a UUID you'll pass to all subsequent API calls. To list existing branches at any time:

```bash
omni models list --include activeBranches
```

> **⚠️ Git-connected models — never hand-edit model YAML in git.** The repo is a *projection* of Omni's model for governance (PRs, review, audit) — not the source of truth and not a surface to author against. Omni regenerates the default branch from its own authoritative state and **deletes git-only model files** that state doesn't contain — an observed customer incident where files committed only to git silently vanished on the next sync. So author **through the Omni APIs on a branch** → `omni models commit` (Step 3) → **review/merge in your git provider**; never push hand-edited model YAML directly.
>
> **Model content vs. repo governance** — the split that makes this safe:
> - **Omni model content** (view / topic / relationship YAML): author on an Omni branch → `omni models commit` → PR. Never commit it directly in git — Omni will regenerate over it.
> - **Repo-governance / non-model files** (a root `omni/OWNERS.yaml`, CODEOWNERS, CI config, docs, scripts): not Omni model content, so direct git commits are fine — Omni's regeneration leaves them untouched.

### Step 1: Write YAML to a Branch

```bash
omni models yaml-create <modelId> --body '{
  "fileName": "my_new_view.view",
  "yaml": "dimensions:\n  order_id:\n    primary_key: true\n  status:\n    label: Order Status\nmeasures:\n  count:\n    aggregate_type: count",
  "mode": "extension",
  "branchId": "{branchId}",
  "commitMessage": "Add my_new_view with status dimension and count measure"
}'
```

> **Note**: The `branchId` parameter must be a UUID from the server (Step 0). Passing a string name instead will return `400 Bad Request: Unrecognized key: "branchName"`.

> **⚠️ Editing an existing file = whole-file read-modify-write at its exact path.** `yaml-create` **replaces** a file's authored content (no field-by-field merge), so `yaml-get` it first, edit, and write the **complete** file back, or the other authored fields are dropped. `fileName` is the file's **exact path** (not a regex, unlike on read) — reuse the full-path key verbatim, folder prefix included (e.g. `MARTS/fct_ai_events.view`); a non-matching name doesn't error, it **silently creates a duplicate** at that path (`success: true`). (Schema base columns live in the schema layer, so they're unaffected.) To **inspect** a branch, `yaml-get` **without** `--file-name` enumerates the whole model — `--mode extension` for just the branch's changed files (your deltas), `--mode combined` for the full composed model (schema + shared + branch); then drill into any file by its exact path.

> **dbt-connected models**: `omni models branch-dbt-get <modelId> <branchName>` (CLI ≥ 1.1.2) reads the dbt environment a branch resolves to, including the dbt git branch it compiles against. A branch with no environment of its own resolves to the connection's default (production) environment, reported with `is_default_environment: true`.

### Step 2: Validate and Test

Every YAML write must be validated and tested before merging — a field can be valid YAML yet produce wrong results or broken queries.

```bash
# 1. Validate — a NEW issue with is_warning:false that references your changed file is blocking; fix before proceeding
omni models validate <modelId> --branch-id <branchId>

# 2. Query the fields you changed — confirm no error, and cache_metadata.num_rows > 0
#    (the row count is at cache_metadata.num_rows; there is NO summary.row_count — see omni-query)
omni query run --body '{"query":{"modelId":"<modelId>","table":"your_view","fields":["your_view.new_dimension","your_view.new_measure"],"limit":10,"join_paths_from_topic_name":"your_topic"},"branchId":"<branchId>"}'

# 3. Read it back — confirm the field is present (and not duplicated at a second path)
omni models yaml-get <modelId> --file-name your_view.view --branch-id <branchId>
```

> **Triage validation errors — most aren't yours.** On a fresh/inherited model, blocking `not found` errors (missing table/view/column) usually mean a **stale schema**: run a **schema refresh** (`omni models refresh <modelId>`) first — it clears them; a `not found` that **persists after refresh** is real (connection lacks DB access, or a genuinely broken reference). For what remains, **baseline before your change** (or filter issues by `yaml_path`) and treat as blocking only the **new** errors referencing **your** changed files — report the pre-existing ones, don't chase them.

Spot-check that values look right (a `sum` isn't returning a `count`; booleans read true/false), and if a field references another view include fields from both to confirm the join resolves. See [validation-and-testing.md](references/validation-and-testing.md) for join-path testing, natural-language validation via `omni ai job-submit`, the full results checklist, and duplicate-file recovery.

> **Window-shaped result columns are table calculations, not model fields.** A running total, moving average, period-over-period / MoM %, percent-of-total, or rank is computed **per query on the result set** — author it as a table calculation (`query.calculations[]`) per **`omni-query` → `references/table-calculations.md`**, not as a measure/dimension here. Only model an in-warehouse field when the window must span rows *outside* the result set.

### Step 3: Ship the Branch

> **Important**: Always ask the user for confirmation before shipping. Changes applied to the production model cannot be easily undone. Only ship after validation and testing pass (Step 2).

Check whether the model is git-connected — `omni models git-get <modelId>`. A config with `sshUrl` / `baseBranch` → git-connected → **Path A** (open/update a PR); a `404`/no config → not git-connected → **Path B** (merge directly in Omni).

#### Path A — Git-connected: open or update a PR

Push the branch contents to git. Creates a new git branch + PR if one doesn't exist; otherwise updates the existing PR:

```bash
omni models commit <modelId> --body '{
  "branch_id": "<branchId>",
  "commit_message": "Add my_new_view with status dimension and count measure"
}'
```

Surface the returned `pr_url` to the user. The reviewer merges the PR in your git host; changes flow back to `baseBranch` on the next sync. Run `omni models commit --help` for optional body flags (`allow_branch_exists`, `require_branch_exists`) when you need to enforce open-only or update-only behavior.

#### Path B — Not git-connected: merge in Omni

```bash
omni models merge-branch <modelId> <branchName>
```

#### After the merge — verify net-new topics and views (both paths)

After either path, confirm new topics and views resolve against the production model (no `--branch-id`): list the views, `get-topic` the topic, validate, and run a query whose `summary.missing_fields` is `[]`. If anything is missing, re-author it through Omni and never patch it by hand in git: [post-merge-verification.md](references/post-merge-verification.md).

## YAML File Types

| Type | Extension | Purpose |
|------|-----------|---------|
| View | `.view` | Dimensions, measures, filters for a table |
| Topic | `.topic` | Joins views into a queryable unit |
| Relationships | (special) | Global join definitions |
| Composite topic | `.composite_topic` | Joins two or more topics on shared dimensions (see [composite-topics.md](references/composite-topics.md)) |

Write with `mode: "extension"` (shared model layer). To delete a file, send empty `yaml`.

## Writing Views

> **Every view that participates in joins MUST have a real `primary_key: true` dimension.** Without a genuine row-unique primary key, queries that join to this view can produce fanout errors or incorrect aggregations. Use the table's natural unique identifier (e.g., `id`, `order_id`, `user_id`). If no single column is unique, build a composite key from row-level columns that are jointly unique, for example `sql: ${order_id} || '-' || ${line_number}`. If you cannot define a row-unique expression, do not mark a dimension as `primary_key: true` yet; fix the grain first or avoid joining the view until a real key exists.

> **Why the PK matters mechanically — symmetric aggregates.** Omni keeps `sum`/`count`/`avg` correct under a one-to-many join by **deduplicating on the primary key** ([symmetric aggregates](https://docs.omni.co/analyze-explore/sql/symmetric-aggregates)). A view **missing** a PK can't be made symmetric, so a `count`-of-rows measure on it **inflates** whenever a join duplicates its rows; a `count_distinct` measure survives only because it dedupes by construction. **Diagnostic heuristic:** when a measure exceeds a measure it should be a subset of (e.g. *"sessions that viewed a product" > "total sessions"*), suspect fanout from a non-distinct count on a view with **no/weak PK** — fix the PK, don't patch the number. Audit *every* base view for a PK (one missing PK is enough to break one viz). Note that a dashboard **filter/control can pull in a join the topic never declared**, via the global `relationships` graph, to satisfy its field — so even a "single-topic" tile can fan out; the PK is what keeps the aggregates safe regardless.

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

Most common: `sql`, `label`, `description` (also used by Blobby), `primary_key` (unique key — critical for aggregations), `hidden` (hides from picker, still usable in SQL), `format` (`number_2`/`currency_2`/`percent_2`/`id`), `group_label`, `synonyms` (AI-matching aliases).
Two gotchas: a raw column **auto-maps by name** (no `sql:` needed); there is **no `${TABLE}` construct** — `${TABLE}.column` errors `Column "__omni_scoped" not found` at validate/query time (reference fields via `${field}`/`${view.field}`).

### Measure Parameters

See `references/modelParameters.md` (24+ params, all 13 aggregate types) and `references/yaml-filter-syntax.md` (filter operators + measure-filter examples). **Prefer a measure `filters:` block** for filtered aggregates over `CASE WHEN`/`WHERE` in `sql` — keep `sql` focused on the value being aggregated:

```yaml
measures:
  completed_revenue:
    sql: ${sale_price}
    aggregate_type: sum
    filters:
      status:
        is: Complete
```

### Filter-only fields and dynamic fields

**Reach for a filter-only field** when one user choice should change *how a field is computed* rather than *which rows are kept*: report by created date or shipped date, show revenue or order count in the same KPI, apply a threshold the viewer sets. It is a view-level `filters:` entry with no column that other fields read through Mustache. **Don't** reach for it to hide or show fields (use topic `fields:`), to filter rows (an ordinary filter), or when the two variants deserve their own topics (see "new topic vs extend"). Shapes, binding, validation: [templated-filters.md](references/templated-filters.md).

### Aggregate tables (aggregate awareness)

**Reach for an aggregate table** when the same fact rollup is queried repeatedly at a coarser grain than the table (daily or monthly tiles over an event-level fact) and a pre-aggregated table exists or can be built. Declare it with a `materialized_query` block on a view, one per table, described against the base view; Omni reads it when a query fits and falls back to the fact table when not. **It will not help** a query that needs a column the table lacks, a non-additive measure (`average`, `count_distinct`, `median`) at another grain, or a finer grain than the table. Confirm with a `planOnly` query headed `-- Query rewritten to use materialized view`. Rules, filter pins, joined views: [aggregate-awareness.md](references/aggregate-awareness.md).

### Level of detail

**Reach for `level_of_detail`** when a measure has to be computed at a grain other than the query's: a per-customer total on every order row (`fixed:`), a finer aggregate summarized up (`always_include:`), or an amount held at a coarser grain while finer dims are on the report (`always_exclude:`). Name the grain the report actually uses — `fixed:` is flat across everything *not* listed only while the listed field is on the report, and listing a field the report does not use re-splits the measure. `always_exclude` adapts to whichever coarser field is present and tolerates over-listing, but needs an idempotent outer aggregate (`max`, not `sum`). **It will not** cap a level via `always_include`, and the lists take field references only — no wildcards. For a header amount repeating across line detail, weigh it against a composite topic with `unrelated_dimension_handling: repeat`, which needs no list. Grain matching, the outer-aggregate rule, template reuse and verification: [level-of-detail.md](references/level-of-detail.md).

### Cross-View Fields in Views

A field in a global view file whose `sql` references `${other_view.field}` is evaluated in every topic that exposes the host view, and is a blocking `field_broken_in_topic` issue in any topic whose explicit `joins:` leave that view out. Define it in the topic's `views.<host_view>` block when it applies to one topic or depends on a topic-specific join; before using the global file, check each exposing topic's `get-topic` `join_via_map`, then validate and query one topic per distinct join context: [topic-scoped-definitions.md](references/topic-scoped-definitions.md#cross-view-fields-in-views).

## Fallback: View Missing from yaml-get

`yaml-get` only returns views from loaded schemas, so before concluding a view does not exist, run `omni models get-schemas <modelId>` and, if its schema is listed, `omni models yaml-get <modelId> --include-schemas <SCHEMA>` (one schema per call): [troubleshooting.md](references/troubleshooting.md#fallback-view-missing-from-yaml-get).

## Writing Topics

> **Before writing a topic, verify all views you plan to reference actually exist.** Run `omni models yaml-get <modelId>` and confirm each view appears. If a view is missing, run the lazy-load fallback above before concluding it doesn't exist — it may simply be in an offloaded schema.

### New topic vs extend an existing one

Extending an existing topic is usually right when the request's base view matches its base view. Create a new topic when the subject (base view), always-applied constraints, or audience differ; ask the requestor when it is a judgment call, and build new topics on a branch. Criteria and key topic elements: [writing-topics.md](references/writing-topics.md).

### Filter Expressions for Topics

Topic `default_filters`, `always_where_filters`, and `always_having_filters` use the measure-filter condition syntax in [yaml-filter-syntax.md](references/yaml-filter-syntax.md); a docs-search tip is in [writing-topics.md](references/writing-topics.md#filter-expressions-for-topics).

### Composite topics

**Reach for a composite topic** when one query must place measures from two facts that share dimensions but no join (sales and returns by month), or one fact under two conditions (this period and last, created basis and shipped basis). Cardinality decides: a filter table that is many-to-one from the summed fact is a dimension, join it; one-to-many is a query view rolled up to the summed grain; only unjoined facts need a composite. **Don't** reach for it when one topic with a join answers the question, or when the second measure is a filtered variant of the first. Authoring, the two-lens `extends` pattern, and the `@`-addressed query shape: [composite-topics.md](references/composite-topics.md).

## Writing Relationships

### Global Relationships

Global relationships are defined in the shared relationships file and are available across all topics. Use these for standard, reusable joins.

```yaml
- join_from_view: order_items
  join_to_view: users
  on_sql: ${order_items.user_id} = ${users.id}
  relationship_type: many_to_one
  join_type: always_left
```

| Type | When to Use |
|------|-------------|
| `many_to_one` | Orders → Users |
| `one_to_many` | Users → Orders |
| `one_to_one` | Users → User Settings |
| `many_to_many` | Tags ↔ Products (rare) |

Getting `relationship_type` right prevents fanout and symmetric aggregate errors.

### Topic-Scoped Relationships

Topic-scoped relationships cover one-off joins and joining the same table more than once (the extended-views pattern, one `extends:` alias per role). Before defining one, check the global relationships file for a join between the same two views in either direction: the same `on_sql` needs only a `joins:` entry, and a different `on_sql` calls for the extended-views pattern once the modeler confirms intent. The view also needs its `joins:` entry, or its fields are not exposed although validation passes (check with `get-topic`): [topic-scoped-definitions.md](references/topic-scoped-definitions.md#topic-scoped-relationships) · examples: [topic-scoped-relationships.md](references/topic-scoped-relationships.md).

### Topic-Scoped View Definitions

A topic's `views:` block can set `display_order`, override labels, and add topic-only fields, aliases, and query views. Before adding a field there, read the view YAML: skip a field that already exists with the same definition, confirm with the modeler before overriding one with different SQL, and make sure every view a `${view.field}` reference names is in the topic's `joins:`. Rules: [topic-scoped-definitions.md](references/topic-scoped-definitions.md#topic-scoped-view-definitions) · examples: [topic-scoped-views.md](references/topic-scoped-views.md).

## Query Views

A query view needs a primary key (`primary_key: true` on one dimension, or `custom_compound_primary_key_sql`) or joins to it fan out; confirm which field is unique before writing unless the query makes it clear, and ask the user when they are unsure. Rules, including the `FROM` alias a `sql:` block with `${view.field}` references needs: [query-views.md](references/query-views.md) · examples: [query-view-examples.md](references/query-view-examples.md).

## Common Validation Errors

Fixes for frequent validation errors (unknown view, no join path, duplicate field name, invalid YAML, fanout, column not found, a duplicate view at the repo root) and for a model out of sync with the database: [troubleshooting.md](references/troubleshooting.md#common-validation-errors).

## Docs Reference

- [Model YAML API](https://docs.omni.co/api/models.md) · [Views](https://docs.omni.co/modeling/views.md) · [Topics](https://docs.omni.co/modeling/topics/parameters.md) · [Dimensions](https://docs.omni.co/modeling/dimensions.md) · [Measures](https://docs.omni.co/modeling/measures.md) · [Relationships](https://docs.omni.co/modeling/relationships.md) · [Query Views](https://docs.omni.co/modeling/query-views.md) · [Composite Topics](https://docs.omni.co/modeling/topics/composite-topics) · [Templated Filters](https://docs.omni.co/modeling/templated-filters) · [Aggregate Awareness](https://docs.omni.co/analyze-explore/performance/aggregate-awareness) · [Branch Mode](https://docs.omni.co/finding-content/drafting-publishing/branch-mode.md)

## Related Skills

- **omni-model-explorer** — understand the model before modifying
- **omni-ai-optimizer** — add AI context after building topics
- **omni-query** — test new fields

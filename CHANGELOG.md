# Changelog

All notable changes to this repository will be documented in this file.

Changelog tracking begins with the next release. Historical releases are not backfilled.

The versions documented here should match the published plugin versions in the affected manifest files.

## [1.3.14] - 2026-05-24

### omni-analytics

**Changed**
- `omni-model-builder` now explicitly keeps prepared branch changes unmerged until the user confirms merge/publish, and reports no dashboard breakage when schema refresh plus content validation find no affected content.
- `omni-content-builder` now clarifies that `documents get-queries` and query execution verify only data queries, not persisted visualization renderer/config fields, so dropped KPI/chart presentation fields still require rollback/reporting.
- `omni-admin` now distinguishes user attribute definitions from per-user assigned values, verifies assigned values through SCIM user readback, and treats explicit set/update requests as idempotent updates.
- `omni-model-explorer` now gives the correct branch-scoped `yaml-create --body` pattern for impact checks and clarifies that dependent field references should remain so validation can reveal breakage.
- BenchFlow-generated judges now compact ACP trajectory evidence before truncation so long rollouts preserve every tool call title and final response context for scoring.

**Fixed**
- Eval reset/preflight now checks and deletes both `public/customer_segments.view` and root-level `customer_segments.view` fixtures left by model-builder runs.

## [1.3.13] - 2026-05-23

### omni-analytics

**Changed**
- `omni-ai-optimizer` now emphasizes branch-first model writes, reading existing YAML before writing, and keeping topic-level optimization requests on topic-level parameters when appropriate.
- `omni-content-builder` now bounds failed existing-dashboard update attempts: after a server-side document write-path error, agents should stop after one corrected retry, preserve the original dashboard, and report the blocker instead of cycling through import/export, draft, replacement-dashboard, or repeated filter-probing attempts.
- `omni-content-builder` now documents raw API URL normalization with `${OMNI_BASE_URL%/}` and treats dropped readback visualization fields as partial dashboard update blockers.
- `omni-embed` now explicitly forbids substituting `OMNI_API_TOKEN` for the embed secret and tells agents to return SDK-shaped `embedSsoDashboard()` code when `OMNI_EMBED_SECRET` is unavailable.
- The content-builder evals now account for current Omni response shapes: row counts can appear as `cache_metadata.num_rows`, query-level filter validation can hit server-side filter errors, and add-tile updates can partially persist while dropping presentation config.
- The eval runner now performs read-only remote preflight checks before starting BenchFlow for cases with known mutable Omni fixtures, failing before any LLM tokens are spent when those fixtures are dirty.
- BenchFlow-generated judges now score long trajectories using both the beginning and end of the transcript instead of only the first 50,000 characters, reducing false failures when early tool output is large.
- `omni-ai-optimizer` evals now reflect idempotent setup-aware behavior: agents should verify existing `ai_context` and `sample_queries` instead of duplicating them, and should only curate `ai_fields` when the topic is actually near the AI-visible field limit.
- `omni-embed` evals now distinguish solid-color requirements from valid rgba shadow values and account for missing embed secrets.
- `omni-model-builder` now directs deleted-column impact checks through branch schema refresh, branch validation, and content-validator before asking for clarification or recommending a merge, and gives a concrete filtered-measure `filters:` pattern.
- `omni-admin` now documents env credential fallback, idempotent create verification, real document permit commands (`documents add-permits`/`access-list`), and the current schedule creation body shape.
- `omni-content-explorer` now documents label filtering via `documents list --include labels` because `content list --labels` is not supported, and treats dashboard export failures before job creation as blockers to report rather than completed downloads.
- `omni-model-explorer` now requires verified branch setup before interpreting field-removal blast-radius results and reports full topic AI context, including `sample_queries` and `ai_fields` when configured.
- `omni-ai-eval` now makes query-generation-only quick evals explicit and tightens branch comparison guidance to score main and branch outputs against the same criteria.
- `omni-query` now gives direct table-calculation recipes for percent-of-total, SUM_IF, VLOOKUP-style, and month-over-month calculations, and tells agents to show enough query JSON to verify calc fields are rendered.
- Eval history exports now include a runner-level `run_id`; older summaries without one are backfilled with `legacy-*` ids by grouping near-simultaneous skill workspaces.

**Docs**
- Documented that `EVAL_DASHBOARD_TILES` is a mutable eval fixture and should be recreated before rerunning the content-builder add-tile case after a successful or partial run.

## [1.3.12] - 2026-05-23

### omni-analytics

**Changed**
- `omni-ai-eval` now defines how to handle quick eval requests that provide prompts without golden expected query JSON: infer expected topic, fields, filters, sorts, and limits from prompt intent, score those dimensions explicitly, and avoid treating the run as a valid-query-only smoke test.
- Tightened the first `omni-ai-eval` eval rubric to match that quick-eval behavior and require dimension-level scoring.

**Fixed**
- BenchFlow-generated LLM judges now print their parsed JSON result to verifier stdout so failed or partial scores expose the rubric item decisions and reasoning in run artifacts.

## [1.3.11] - 2026-05-22

### omni-analytics

**Added**
- `omni-query` SKILL.md — prefer `job-submit` over `generate-query` for calc-bearing prompts (more reliable SQL fallback; validated by 22-prompt bake-off). Updated "When to Use Which Approach" table. `generate-query --run-query=false` retained as the AST-inspection tool.
- `omni-query` SKILL.md + new `references/job-result-to-presentation.md` — transformation algorithm for converting job results into dashboard `queryPresentations`: always strip `userEditedSQL` (bypasses `always_where_sql` and access controls); when `calculations[]` is empty, reconstruct invented fields from `csvResultFields` using `extension_model_id + expr.type == "call"` as the discriminator; skip aggregate top-level operators (filtered measures, not table calcs); inject missing field refs. Sanity-check approach via extension model YAML documented.

## [1.3.10] - 2026-05-21

### omni-analytics

**Added**
- `skills/omni-query/references/table-calculations.md` — new reference for authoring the `calculations[]` array: wire shape, AST node types, operator catalog (`Omni.*` and `SqlStdOperatorTable.*` namespaces), `OMNI_OFFSET_MULTI` operand decoding, and 12 worked examples (ratio, % of total, running total, chained calcs, CASE, moving average, IFS/concat/TEXT labels, inside-pivot running total, outside-pivot row total, DATEDIF, SUMIF/SUM_IF, VLOOKUP).
- `omni-query` SKILL.md — "Table Calculations" subsection covering the minimum calc shape, the `calc_name`-must-be-in-`fields` gotcha, template operators, and pivot semantics (`outside_pivot`, `limit: null` error).
- 9 new evals (entries 5–13) covering running total, moving average, pivot row total, IFS/AMPERSAND, % of total, DATEDIF operand order, SUM_IF underscore, VLOOKUP 4-operand decomposition, and MoM % change without period-pivot sidestep.

## [1.3.9] - 2026-05-20

### omni-analytics

**Fixed**
- Documented that `omni models yaml-create` treats `fileName` as an exact path identity (not a regex, unlike `yaml-get`): a non-matching name silently creates a new file at the repo root and still returns `success: true`, producing a duplicate view instead of editing the intended one. The `omni-model-builder` write step now instructs reusing the full-path key from the read response verbatim (incl. folder prefixes), adds a post-write anti-duplicate read-back check, and a Common Validation Errors row. `omni-model-explorer` now documents that the `files` map is keyed by full stored path.

**Changed**
- Trimmed redundancy in `omni-model-builder` (overlapping schema-refresh/troubleshooting content, duplicated layering prose, bullet lists) to keep the skill near the ~500-line length guidance. No behavior change.

## [1.3.8] - 2026-05-05

### omni-analytics

**Added**
- `omni models commit` integration (CLI PR [exploreomni/cli#54](https://github.com/exploreomni/cli/pull/54)) for shipping branch changes through a pull request on git-connected models. Step 3 of the omni-model-builder workflow now branches on `omni models git-get <modelId>`: git-connected models use `omni models commit` to open or update a PR (returning `pr_url`); non-git models use `omni models merge-branch` as before. Same guidance added to the `omni-modeler` agent and `omni-yaml-conventions` rule.

## [1.3.7] - 2026-05-04

### omni-analytics

**Added**
- Topic-scoped relationship guidance: `relationships:` parameter inline in a `.topic` file, when to use it over global relationships, `joins` vs `relationships` distinction; YAML gallery in `references/topic-scoped-relationships.md`
- Extended views pattern for same-table aliasing: replaces `join_to_view_as` with `extends: [base_view]`; Variant 1 global `.view` file, Variant 2 topic-scoped inline. Fixes `relationship alias duplicates view name` error
- Topic-scoped view definitions: display ordering, label overrides, filtered measures, derived dimensions, cross-view fields, multi-join lifecycle, ratio measures; YAML gallery in `references/topic-scoped-views.md`
- Pre-check directives for topic-scoped fields and relationships (cross-view reference validation, redundancy/conflict checks, override confirmation)
- Query view primary key guidance: prompt for unique key before writing; `primary_key: true` and `custom_compound_primary_key_sql` documented with fanout error link; YAML gallery in `references/query-view-examples.md`
- `${view_name}` syntax preferred over hard-coded `CATALOG.SCHEMA.TABLE` in `sql:` query view blocks
- Measure filter examples in `references/yaml-filter-syntax.md`, including `not: null` (IS NOT NULL) and `is: null` (IS NULL)

**Fixed**
- Restructured "Writing Relationships" to clearly separate global (shared model) from topic-scoped relationship definitions
- Cross-view fields warning: clarifies that defining `${view_name.field_name}` references in a shared view file causes validator errors in every topic that includes the view without joining the referenced view — these fields belong in the topic's `views:` block
- SKILL.md refactored to keep all agent directives inline while moving YAML pattern galleries to `references/`; conceptual illustrations (schema layer vs extension layer) kept in SKILL.md
- Null check examples in `references/yaml-filter-syntax.md` use generic `some_field` for consistency
- Branch validation pattern corrected: `omni ai job-submit --branch-id --topic-name` correctly resolves branch-scoped topics; `omni query run` supports `branchId` via `--body`

## [1.3.6] - 2026-05-01

### omni-analytics

**Fixed**
- Embedded the lazy-load fallback pattern directly in omni-model-builder rather than cross-referencing omni-model-explorer. Adds a dedicated "Fallback: View Missing from yaml-get" section with the full two-step recovery commands (`get-schemas` + `yaml-get --includeschemas`), and a pre-flight directive in Writing Topics to run the fallback before concluding a view doesn't exist.

## [1.3.5] - 2026-04-29

### omni-analytics

**Fixed**
- Expanded topic key elements in omni-model-builder to include all four always-filter variants (`always_where_sql`, `always_where_filters`, `always_having_sql`, `always_having_filters`) with clear distinction between SQL expression and filter specification forms
- Replaced incomplete 7-item measure filter condition list with a pointer to the new `yaml-filter-syntax.md` reference (which includes `greater_than_or_equal_to`, `less_than_or_equal_to`, negation, array values, boolean handling, and date/time operators)
- Added guidance to use `omni ai search-omni-docs` when filter configuration for topics is unclear

**Added**
- `skills/omni-model-builder/references/yaml-filter-syntax.md` — comprehensive YAML filter operator reference covering all operator categories (conditional, numeric, string, date/time), negation, array values, boolean three-state logic, and field qualification rules for topic vs. measure context

## [1.3.4] - 2026-04-24

### omni-analytics

**Added**
- Schema-aware lazy-load fallback pattern in omni-model-explorer § Fallback: Expected View Missing from `yaml-get`. When normal exploration can't find a view the user named, it's likely in an offloaded or inactive schema. Fallback uses `omni models get-schemas <modelId>` to surface all schemas (including offloaded/inactive) and `omni models yaml-get <modelId> --includeschemas <schema>` to load views from one of them.

## [1.3.3] - 2026-04-23

### omni-analytics

**Changed**
- Replaced env-var auth setup (`export OMNI_BASE_URL` / `export OMNI_API_TOKEN`) with CLI profile workflow (`omni config show` → `omni config use`) across all skills, README, AGENTS.md, and rules
- Added `-o` / `--format` flag guidance to all skills for controlling JSON vs human-readable output

## [1.3.2] - 2026-04-22

### omni-analytics

**Fixed**
- Corrected CLI flag names across all skills to match actual `omni` CLI flags — the CLI is inconsistent with hyphenation per subcommand, so each flag was verified individually
- `--branchid` (no hyphen): `models validate`, `models yaml-get`
- `--branch-id` (with hyphen): `models refresh`, `models get-topic`, `models content-validator-get`, `ai generate-query`
- `--filename`, `--sortfield`, `--creatorid`, `--userid`, `--jobids` (all no hyphen)
- `--clear-existing-draft` requires a string value (e.g. `true`), not a bare flag

## [1.3.1] - 2026-04-21

### omni-analytics

**Fixed**
- Removed invalid `views: <view_name>:` wrapper from content builder `yaml-create` example — the API rejects it with `saveError: "Invalid property name at \"views\""`. The YAML body must start directly at `dimensions:` / `measures:`.

## [1.3.0] - 2026-04-21

### omni-analytics

**Added**
- Eval framework for all 9 Omni skills (`evals/` directory with runner, scorer, and per-skill `evals.json`)
- Comprehensive `visConfig` reference doc for content builder
- Validation loops to model-builder, admin, query, and content builder skills
- Migration note for users coming from deprecated repos

**Changed**
- AI optimizer skill updated for AI topic optimization
- Replaced CLI auto-install with check-and-prompt behavior across all skills
- Updated skills to use CLI shorthand syntax
- Rebranded AI assistant / query helper terminology
- Updated Omni Agent context and values
- Removed `svgMap`, `code`, and `omni-spreadsheet` chart types from visConfig reference

**Fixed**
- Clarified workbook model update flow in content builder
- Fixed primary key guidance in model builder

## [1.1.0] - 2026-04-21

### omni-integrations

**Added**
- New `omni-to-databricks-metric-views` skill with field mapping and YAML reference docs
- Cursor plugin support (`.cursor-plugin/`)

**Changed**
- Improved `omni-to-snowflake-semantic-view` skill with troubleshooting section and synonym support

**Fixed**
- Fixed Cursor integrations install (subdirectory URLs not supported)
- Fixed critical rule for `comment` vs `description` field key in Databricks metric view definitions
- Fixed synonym mapping from Omni fields into Databricks metric view definitions

## Unreleased

No unreleased changes yet.

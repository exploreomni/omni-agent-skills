# Changelog

All notable changes to this repository will be documented in this file.

Changelog tracking begins with the next release. Historical releases are not backfilled.

The versions documented here should match the published plugin versions in the affected manifest files.

## [1.4.2] - 2026-06-17

### omni-analytics

**Added**
- `omni-query` documents the **raw-SQL query pathway**: a new *Running Raw SQL (`userEditedSQL`)* section (minimal body with `fields: []`; `rewriteSql: false` for verbatim execution and `dbtMode: true` for Jinja; the SQL-querying permission gate, which fails as `FORBIDDEN` returned as HTTP 200 in the job body, not a 4xx; the 50,000-row cap with a +1 truncation sentinel; warehouse-dialect/fully-qualified-name requirement), plus a *Request-level options* table (`resultType`, `cache`, `userId`, `branchId`, `planOnly`, `formatResults`, `timezone`).
- `omni-admin` adds an **Access Boost** subsection: the role values (`NO_ACCESS`/`VIEWER`/`EDITOR`/`MANAGER`), the org-capability prerequisite (`allowsDocumentAccessBoost` / `allowsMemberToProvisionAccessBoost` — an instance setting, not a CLI op), both per-document levers (`documents add-permits`/`update-permits` with `accessBoost`, and `documents update-permission-settings` with `organizationAccessBoost`), and the **dashboard-only** scope (it does not extend to the underlying workbook's non-topic/SQL tabs).
- `omni-content-builder` adds a **Raw-SQL tiles** recipe in `references/queryPresentations.md` with the end-to-end path (author the `userEditedSQL` tile → publish → Access Boost) and a proactive directive: when a tile is non-topic/raw-SQL, ask whether the audience includes Restricted Queriers/Viewers and counsel Access Boost. Supports SQL-first dashboard migrations (e.g. from Mode) where a governed topic may not yet exist.

**Changed**
- `omni-query` corrects the `table` parameter from required to **Conditional** (a semantic query needs it only when neither `join_paths_from_topic_name` nor `userEditedSQL` is set; the API requires just `modelId` + `fields`), reframes the Fallback note so bare-view and raw-SQL read as one **non-topic** family (topic-scoped access filters / `always_where` apply to neither; raw SQL additionally bypasses object-level access grants), lists `resultType` `csv`/`xlsx`/`json`, and fixes the job-result "strip `userEditedSQL`" rationale (it removes a non-topic query that bypasses topic-scoped controls — not "row-level access controls").

## [1.4.1] - 2026-06-16

### omni-analytics

**Changed**
- `omni-content-builder` `references/documents-v2.md`: document the `--body` object-vs-string footgun — `queryPresentations`/`controls`/`settings` must be **nested objects, not stringified JSON** (the `400 … expected object, received string` error), with a worked body example and an error-map row; add an inline callout distinguishing `v2-patch-draft` (opens a draft) from `v2-patch-draft-by-identifier` (pure apply on an existing draft).
- `omni-content-builder` `references/branch-bound-drafts.md`: name the running-total table-calculation AST shape (`Omni.OMNI_FX_SUM(Omni.OMNI_OFFSET_MULTI(...))`, `sql_expression` not a workbook-style `{name, formula}`) and note the full operator catalog lives in the `omni-query` skill.

## [1.4.0] - 2026-06-12

### omni-analytics

**Changed**
- `omni-content-builder` migrated document create/edit to the GA **v2 documents API** (requires a CLI release with the `documents v2-*` commands — exploreomni/cli#62). Creation is `documents v2-create`; every edit rides the **draft flow** (`v2-get` → `v2-patch-draft` → validate the draft → `v2-publish-draft`), replacing the v1 `documents create`/`put` full-replacement path. Patches **merge by key** (null deletes; `order` arrays and `containers` replace wholesale), so updates no longer resend the whole document, and failed edits roll back by discarding the draft — the published dashboard is never touched. v1 commands remain for lifecycle ops (list/delete/move/duplicate/get-queries/list-drafts/discard-draft), downloads, workbook-model YAML, and workbook-model-ID discovery; a command boundary table routes between the generations.
- All behaviors live-verified against a GA instance with a CLI built from exploreomni/cli#62, including: the flat-read/nested-write inner vis-config asymmetry (a flat-sent spec silently keeps only `visType` — the round-trip footgun), tile queries carrying **no `modelId`** (a sent value is silently rewritten; the server anchors tiles to the workbook model), **workbook-model rotation** on every draft publish (extensions carry over; never cache the ID), the required query collection-field set (400 with per-field errors), seed-tile `"1"` merge on create, multi-tile create laying out only tile `"1"`, filter `map` per-tile scoping now working (switcher `map` still UI-only), `branchId` binding only from the JSON body (`--body` silently drops all shorthand flags), `v2-publish-draft` being main-draft-only (branch drafts publish via branch merge), and the 422 classic-layout rejection with no API fallback.
- References restructured: `documents-v2.md`/`containers.md`/`controls.md` (initially authored by Scott Barber against the experimental surface) refreshed for GA and promoted to the primary path; `updating-dashboards.md` rewritten around the draft loop with merge-by-key recipes and a live-verified error map; `branch-bound-drafts.md` rewritten — the v1 `query.modelId`-stamping gotcha is gone, replaced by body-`branchId` + `list-drafts` binding verification; `queryPresentations.md`/`visConfig.md` re-enveloped (`visConfig: {chartType, fields, version, visConfig: {visType, config}}`) with a v1→v2 field-location table; `filterConfig.md` folded into `controls.md` (filters and controls are one keyed `controls` slice); `validation-and-testing.md` re-pointed at validating the draft **before** publishing.
- Eval cases re-targeted to the draft flow: merge-by-key tile additions (no full-document resend), nested-under-`config` vis specs with flat-readback verification, the no-`modelId` workbook-field flow, body-`branchId` branch binding with `list-drafts` verification, and controls-slice filters.

## [1.3.18] - 2026-06-02

### omni-analytics

**Changed**
- `omni-model-builder` adds branch-editing guidance to the Safe Development Workflow (`yaml-create` is a whole-file write; inspecting a branch via `yaml-get` — `extension` = changed files, `combined` = full composed model) and "new topic vs extend" criteria (different subject/base view, always-applied constraints, or audience/labels), noting that querying on a topic is what exposes results to restricted queriers/viewers.
- `omni-query` adds topic-first guidance and now owns the canonical topic-query shape: prefer querying a topic (`table` = base view + `join_paths_from_topic_name`); the **join-map mechanics** (how `join_paths_from_topic_name` reaches joined-view fields from the base view, verified via `get-topic`'s `base_view_name`/`join_via_map`) — `omni-content-builder` and `omni-model-builder` now reference this instead of restating it; a use-existing / extend / new-topic decision flow; the access-control consequence (non-topic queries are invisible to restricted queriers/viewers); the bare-base-view fallback; and a handoff to `omni-model-builder` for topic changes.
- `omni-content-builder` adds field-placement guidance: a "where a new field belongs" decision order in *Updating a Dashboard's Model* (table calculation → shared-model branch → workbook model; never the schema model) and `references/branch-bound-drafts.md` for tiles whose query references a field not in the *published* shared model — the restricted-querier "Invalid model" gotcha (`documents create` stamps the base model on tiles) and its `documents put` workbook-model fix, covering both branch-only fields (warning) and workbook-model fields (the field *fails to resolve* unless `query.modelId` is the workbook model), the fixed `create` → `get` → `yaml-create … mode:extension` → `put` order, and draft tiles using the draft's own workbook model which extends its branch. Also tells the agent to flag the pending-merge draft status to the creator (a branch-bound draft only publishes when its branch merges), notes drafts link via `/dashboards/<draftIdentifier>`, and adds eval cases (workbook-field tiles, branch-bound-draft tiles, running-total-as-calculation routing).

## [1.3.17] - 2026-06-02

### omni-analytics

**Fixed**
- `omni-content-builder` visualization config guidance: the rendering spec belongs in a queryPresentation-level `visConfig.config` with `chartType` as a sibling — a bare top-level `config` was silently dropped and `query.visConfig.chartType` alone does not drive a tile. A correctly-shaped `documents create`/`put` now reliably one-shots a styled chart.
- Corrected the `chartType` enum (removed invalid `barColor`/`areaColor`/`stackedBarColor`/`scatter`; documented the real enum and the column-vertical vs bar-horizontal distinction) and `configType` values (`cartesian`/`polar`/`heatmap`/`boxplot`; pie is `polar`; funnel/sankey/map carry no `configType`).
- Corrected per-family shapes verified against a live instance: `regionMap` uses `visType: map` + `regionType: us-states`/`countries` + a `sourceProperty` matching the field's values (plus `center`/`zoom`); `svgMap` requires both `svgContent` and `mapName`; funnel uses `orient`/`funnelAlign`/`sort`; `auto` is not a persistable render; markdown is mustache-templated; AI-summary uses `ai_context`/`showWarning`; `summaryValue` is deprecated in favor of `kpi`.
- `omni-content-builder` dashboard-update guidance now uses the `omni documents put <identifier>` CLI command (full replacement) instead of a raw `curl PUT` with a manual auth header — the prior text incorrectly stated full-document replacement was not available in the CLI.
- `omni-model-builder` corrected invalid `${TABLE}.column` examples (a LookML-ism that does not resolve in Omni) to proper `${field}` references. _(Merged previously without a version bump; documented here.)_

**Changed**
- Added `omni-content-builder` eval cases (stacked column, heatmap, pie) asserting valid `chartType`, spec-in-`visConfig.config`, correct `configType`, and read-back-confirms-persistence.
- `omni-model-builder` SKILL.md trimmed under the ~500-line guideline by extracting schema-refresh and validation/testing detail into `references/schema-refresh.md` and `references/validation-and-testing.md`. _(Merged previously without a version bump; documented here.)_

## [1.3.16] - 2026-05-25

### omni-analytics

**Changed**
- `omni-query` now treats explicit table-calculation requests as a strict `calculations[]` workflow, avoiding existing model fields, raw SQL/window fallbacks, or client-side calculations when the user asks for calculated columns.
- `omni-query` now adds stricter reporting and reference-routing guidance for running totals, moving averages, pivot row totals, tier labels, date differences, SUM_IF broadcasts, VLOOKUP fallbacks, and month-over-month percent change.

## [1.3.15] - 2026-05-25

### omni-analytics

**Changed**
- `omni-model-builder` now handles schema-impact checks on connections that reject branch-based schema refresh by falling back to shared schema refresh while continuing branch-scoped validation/content validation where supported.
- `omni-model-builder` now separates validation warnings from dashboard blast-radius results and avoids inferring that join-path warnings were caused by an unspecified deleted column.
- `omni-content-builder` now treats `config: {}` as a table/fallback pattern and directs requested line/bar/area/scatter/KPI charts to use complete chart-specific config from the visualization references.
- `omni-content-builder` now distinguishes normal new-dashboard readback omissions from failed existing-dashboard partial updates, and requires explicit per-tile status/row-count verification after creation.
- `omni-ai-optimizer` now stops after verifying complete topic-level term mappings instead of adding redundant field synonyms as extra signal.

**Fixed**
- Eval reset now removes accidentally merged `eval_completed_revenue` model-builder fixtures, repairs known quote-stripped literals in `public/order_items.view`, and deletes stale branch models using a direct branch listing.

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

## [1.1.1] - 2026-05-23

### omni-integrations

**Changed**
- `omni-to-databricks-metric-view` — replaced `cat ~/.databrickscfg` with `databricks auth profiles` so the skill no longer instructs the agent to read a credentials file. Replaced the shell-substituted `python3 -c '...'` JSON-encoding step in the SQL Statements API call with a `--json @payload.json` pattern, dropping the extra interpreter and shell substitution of generated SQL. Brings the Gen Agent Trust Hub audit profile closer to the Snowflake peer skill (see https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-databricks-metric-view/security/agent-trust-hub).

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

# Changelog

All notable changes to this repository will be documented in this file.

Changelog tracking begins with the next release. Historical releases are not backfilled.

The versions documented here should match the published plugin versions in the affected manifest files.

## [1.3.6] - 2026-05-01

### omni-analytics

**Fixed**
- Embedded the lazy-load fallback pattern directly in omni-model-builder rather than cross-referencing omni-model-explorer. Adds a dedicated "Fallback: View Missing from yaml-get" section with the full two-step recovery commands (`get-schemas` + `yaml-get --includeschemas`), and a pre-flight directive in Writing Topics to run the fallback before concluding a view doesn't exist.

## [1.3.7] - 2026-05-01

### omni-analytics

**Added**
- Topic-scoped relationship guidance in omni-model-builder: documents the `relationships:` parameter inline in a `.topic` file, when to use it over global relationships, user attribute filtering in `on_sql`, and the `joins` vs `relationships` distinction with a complete worked example
- Extended views pattern for same-table aliasing: replaces `join_to_view_as` with the correct `extends: [base_view]` approach in a topic `views:` block, including the `relationship alias duplicates view name` error fix
- Topic-scoped view definitions section covering: display ordering, label overrides, topic-specific filtered measures, derived dimensions, cross-view fields, and joining the same view multiple ways with different conditions
- Pre-check directives: verify all cross-view field references are in `joins:` before writing; check for redundancy or conflicts with shared view definitions before adding topic-scoped fields, and confirm overrides explicitly with the modeler

**Fixed**
- Restructured "Writing Relationships" to clearly separate global (shared model) from topic-scoped relationship definitions

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

---
name: omni-model-explorer
description: Discover and inspect Omni Analytics models, topics, views, fields, dimensions, measures, and relationships using the Omni CLI. Use this skill whenever someone wants to understand what data is available in Omni, explore their semantic model, find specific fields or views, check how tables join together, see what topics exist, or asks any variant of "what can I query", "what fields are available", "show me the model", "what data do we have", or "how is this data modeled". Also use when you need to understand the Omni model structure before building or modifying anything.
---

# Omni Model Explorer

Explore and understand an Omni semantic model through the Omni CLI. This is the starting point — understand what exists before building, querying, or modifying anything.

> **Tip**: Start with the **Shared** model — it contains the curated analytics layer.

## Prerequisites

Configure the Omni CLI:

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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

API keys: Settings > API Keys (Organization Admin) or User Profile > Manage Account > Generate Token (Personal Access Token).

## Discovering Commands

When unsure what operations or flags are available:

```bash
omni models --help              # List all model operations
omni models <operation> --help  # Show flags and positional args
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Core Workflow

Explore top-down: **List models → Pick a model → List topics → Inspect a topic → Explore views and fields**.

### Step 1: List Available Models

```bash
omni models list
```

Returns models with `id`, `name`, `connectionId`, and `modelKind` (SCHEMA or SHARED). Use the SHARED model — it contains the curated semantic layer.

To also see active branches on each model:

```bash
omni models list --include activeBranches
```

Each model in the response will include a `branches` array. Each branch has an `id` (UUID) and `name` — use the `id` as the `branchId` parameter in other API calls.

### Step 2: List Topics in a Model

Topics are entry points for querying. Each topic defines a base view and the set of joined views available.

```bash
omni models list-topics <modelId>
```

Returns topic names, base views, labels, and descriptions.

### Step 3: Inspect a Topic

Get full detail including all views, dimensions, measures, relationships, and AI context:

```bash
omni models get-topic <modelId> <topicName>
```

The response includes:
- `base_view_name` — the primary table
- `views[]` — all accessible views, each with `dimensions[]` and `measures[]`
- `relationships[]` — how views join together
- `default_filters` — filters applied by default
- `ai_context` — instructions for Blobby (Omni's AI)
- `sample_queries` and AI field-selection metadata when configured

### Step 4: Read the Model YAML

For the full semantic model definition:

```bash
# All YAML files
omni models yaml-get <modelId>

# Specific file
omni models yaml-get <modelId> --filename order_items.view

# Regex filter
omni models yaml-get <modelId> --filename '.*sales.*'

# From a branch (branchId is a UUID from the list models response)
omni models yaml-get <modelId> --branchid <branchId>
```

The `mode` parameter: `combined` (default) merges schema + shared model; `extension` shows only shared model customizations.

The `files` map is keyed by each file's **full stored path** (e.g. `MARTS/order_items.view`), and `--filename` is a regex on read. Reuse that exact key — including any folder prefix — when editing with `omni-model-builder`; a shortened name creates a duplicate instead of editing the original.

## Model Architecture

Omni has three layers:

1. **Schema Model** — auto-generated from your database (read-only)
2. **Shared Model** — analytics engineer customizations (dimensions, measures, labels, topics, AI context)
3. **Workbook Model** — per-dashboard customizations (ad-hoc, not shared)

When exploring, use the `combined` view to see everything available.

## Key Concepts

**Views** correspond to database tables. Each has dimensions (groupable fields) and measures (aggregations).

**Topics** join views together into queryable units — curated starting points for analysis. A topic has a base view, joined views, default filters, and AI context.

**Relationships** define joins: `join_from_view`, `join_to_view`, `on_sql`, `relationship_type` (one_to_one, many_to_one, one_to_many, many_to_many), and `join_type` (always_left, inner, full_outer).

**Field naming**: `view_name.field_name` with bracket notation for date granularity: `orders.created_at[week]`.

## Exploration Patterns

**"What data do we have about X?"** — List topics → inspect the most relevant one → review views and fields.

**"How do these tables relate?"** — Inspect the topic's `relationships[]` — check `join_from_view`, `join_to_view`, `on_sql`, and `relationship_type`.

**"What measures are available for Y?"** — Inspect the topic containing view Y → review the `measures[]` array with `aggregate_type` and `sql` definitions.

## Fallback: Expected View Missing from `yaml-get`

Use this pattern only when normal exploration comes up short — the user names a specific view and it's absent from the `yaml-get` or `get-topic` response, or a relationship references a view that doesn't appear. If `yaml-get` returned what you expected, skip this section.

**Why it happens:** `yaml-get` only returns views from currently-loaded schemas. If a schema is **offloaded or inactive**, its views won't show up. The `get-schemas` call surfaces *all* schemas the connection knows about — including offloaded and inactive ones — so it's the right next step before telling the user "not found."

**Two-step recovery:**

```bash
# 1. List every schema (loaded, offloaded, and inactive)
omni models get-schemas <modelId>
# → {"schemas": ["ANALYTICS", "PUBLIC", "STAGING", ...]}

# 2. If the target schema is in the list, load just that schema
omni models yaml-get <modelId> --includeschemas PUBLIC
```

**If the schema isn't in the list at all**, this isn't a lazy-load issue — the connection likely doesn't have access or the schema isn't synced. Check with a Connection Admin.

**Rules for `--includeschemas`:**
- Accepts exactly **one schema name** per call — commas are rejected by the API. Load schemas one at a time if you need multiple.
- When set, the response contains only views belonging to that schema. Relationships are preserved even when they reference views in other schemas.
- To scope to a branch, add `--branchid <id>` to `yaml-get` or `--branch-id <id>` to `get-schemas` (the flag names differ per command — this matches the API's underlying casing).

## Calculation Fields

Calculation fields in the model use a different format than regular dimensions/measures. The field key is `calc_name` and the expression property is `sql_expression` — not `name`/`sql`.

## AI Context Inspection

When the user asks what Blobby knows about a topic, inspect the topic and report the actual AI configuration — do not infer it from field names:

```bash
omni models get-topic <modelId> <topicName>
omni models yaml-get <modelId> --filename '<topicName>\.topic'
```

Read `ai_context`, `sample_queries`, and AI field-selection values. Depending on CLI/API shape, `get-topic` may wrap these under a top-level `topic` object; if a top-level `ai_context` is null, check `topic.ai_context` before concluding none exists. If `get-topic` does not expose the full `ai_fields` list, read the topic YAML and report the configured `ai_fields` there. Include configured sample query names/prompts and the fields they exercise when present.

## Field Impact Analysis

Assess the blast radius of a field migration or removal before pushing changes to dbt:

1. **Create a model branch** where the field is actually absent before running validator checks:

```bash
omni models create-branch <modelId> --name "field-impact-<field-name>"
```

Then use the right setup for the change being tested:
- **Database column deletion/rename**: refresh the schema on the branch after the warehouse change is present, then validate the branch.
- **Model-only field removal/rename**: write the modified YAML to the branch with `omni models yaml-create`, using the exact `fileName` key returned by `yaml-get`.

`yaml-create` accepts the update as a JSON body, not separate `--filename` or `--branchid` flags:

```bash
omni models yaml-create <modelId> \
  --body '{"branchId":"<branchId>","fileName":"public/order_items.view","yaml":"<full modified YAML string>"}'
```

Use the response and `yaml-get --branchid` readback to verify the file was written to the branch. For model-only field removal impact, remove the field's own definition from the branch YAML, but leave existing dependent field references in place unless the user's planned change also removes them. Those unresolved references are what `omni models validate` uses to reveal dependent measures, dimensions, topics, and joins that would break.

Do not reuse an existing branch unless `yaml-get --branchid <branchId>` proves the target field is absent or renamed there. A branch with a matching name but unchanged YAML is not a valid blast-radius branch.

2. **Validate the branch setup** before interpreting content results:

```bash
omni models yaml-get <modelId> --filename '<viewName>\.view' --branchid <branchId>
omni models validate <modelId> --branchid <branchId>
```

Verify the field definition precisely, not with a whole-file substring search. For example, `sale_price` may still appear in `sql: ${sale_price}` after the `dimensions: sale_price: {}` definition has been removed; that is a valid impact-test branch and should be reported as a dependent reference. If the original field definition still appears in branch YAML, say the branch setup is invalid and do not claim validator results represent removal impact.

3. **Run the content validator** against the verified branch:

```bash
omni models content-validator-get <modelId> --branch-id <branchId>
```

This returns all dashboards and tiles with broken references to the removed field.

4. **Search model YAML** for additional references (run in parallel with step 3):

```bash
omni models yaml-get <modelId> --filename '.*'
```

Search the response for the field name to find references in other views, topics, and calculated fields.

5. **Report**: Combine branch validation, content-validator results (broken dashboards/tiles), and YAML search results (model references) into a structured blast-radius report. Separate direct field references, cascading references through dependent fields, raw SQL column references, and saved-content breakage.

> Do NOT paginate documents and check queries individually — the content validator does this for you in one call.

## Docs Reference

- [Models API](https://docs.omni.co/api/models.md) · [Topics API](https://docs.omni.co/api/topics.md) · [Modeling Overview](https://docs.omni.co/modeling.md) · [Views](https://docs.omni.co/modeling/views.md) · [Topics](https://docs.omni.co/modeling/topics/parameters.md) · [Dimensions](https://docs.omni.co/modeling/dimensions.md) · [Measures](https://docs.omni.co/modeling/measures.md)
- [List model schemas](https://docs.omni.co/api/models/list-model-schemas) · [Get model YAML](https://docs.omni.co/api/models/get-model-yaml)

## Related Skills

- **omni-model-builder** — create or modify views, topics, and fields
- **omni-query** — run queries against discovered fields
- **omni-ai-optimizer** — inspect and improve AI context on topics

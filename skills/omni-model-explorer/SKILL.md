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
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

API keys: Settings > API Keys (Organization Admin) or User Profile > Manage Account > Generate Token (Personal Access Token).

## Discovering Commands

When unsure what operations or flags are available:

```bash
omni models --help              # List all model operations
omni models <operation> --help  # Show flags and positional args
```

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

### Step 4: Read the Model YAML

For the full semantic model definition:

```bash
# All YAML files
omni models yaml-get <modelId>

# Specific file
omni models yaml-get <modelId> --file-name order_items.view

# Regex filter
omni models yaml-get <modelId> --file-name '.*sales.*'

# From a branch (branchId is a UUID from the list models response)
omni models yaml-get <modelId> --branch-id <branchId>
```

The `mode` parameter: `combined` (default) merges schema + shared model; `extension` shows only shared model customizations.

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

## Calculation Fields

Calculation fields in the model use a different format than regular dimensions/measures. The field key is `calc_name` and the expression property is `sql_expression` — not `name`/`sql`.

## Field Impact Analysis

Assess the blast radius of a field migration or removal before pushing changes to dbt:

1. **Create a model branch** with `omni-model-builder` where the field is removed or renamed
2. **Run the content validator** against that branch:

```bash
omni models content-validator-get <modelId> --branch-id <branchId>
```

This returns all dashboards and tiles with broken references to the removed field.

3. **Search model YAML** for additional references (run in parallel with step 2):

```bash
omni models yaml-get <modelId> --file-name '.*'
```

Search the response for the field name to find references in other views, topics, and calculated fields.

4. **Report**: Combine content-validator results (broken dashboards/tiles) with YAML search results (model references) into a structured blast-radius report.

> Do NOT paginate documents and check queries individually — the content validator does this for you in one call.

## Docs Reference

- [Models API](https://docs.omni.co/api/models.md) · [Topics API](https://docs.omni.co/api/topics.md) · [Modeling Overview](https://docs.omni.co/modeling.md) · [Views](https://docs.omni.co/modeling/views.md) · [Topics](https://docs.omni.co/modeling/topics/parameters.md) · [Dimensions](https://docs.omni.co/modeling/dimensions.md) · [Measures](https://docs.omni.co/modeling/measures.md)

## Related Skills

- **omni-model-builder** — create or modify views, topics, and fields
- **omni-query** — run queries against discovered fields
- **omni-ai-optimizer** — inspect and improve AI context on topics

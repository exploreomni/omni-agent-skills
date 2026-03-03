---
name: omni-model-explorer
description: Discover and inspect Omni Analytics models, topics, views, fields, dimensions, measures, and relationships using the Omni REST API. Use this skill whenever someone wants to understand what data is available in Omni, explore their semantic model, find specific fields or views, check how tables join together, see what topics exist, or asks any variant of "what can I query", "what fields are available", "show me the model", "what data do we have", or "how is this data modeled". Also use when you need to understand the Omni model structure before building or modifying anything.
---

# Omni Model Explorer

Explore and understand an Omni semantic model through the REST API. This is the starting point — understand what exists before building, querying, or modifying anything.

> **Tip**: Start with the **Shared** model — it contains the curated analytics layer.

## Prerequisites

Set environment variables:

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

API keys: Settings > API Keys (Organization Admin) or User Profile > Manage Account > Generate Token (Personal Access Token).

## Core Workflow

Explore top-down: **List models → Pick a model → List topics → Inspect a topic → Explore views and fields**.

### Step 1: List Available Models

```bash
curl -L "$OMNI_BASE_URL/api/v1/models" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Returns models with `id`, `name`, `connectionId`, and `modelKind` (SCHEMA or SHARED). Use the SHARED model — it contains the curated semantic layer.

To also see active branches on each model:

```bash
curl -L "$OMNI_BASE_URL/api/v1/models?include=activeBranches" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Each model in the response will include a `branches` array. Each branch has an `id` (UUID) and `name` — use the `id` as the `branchId` parameter in other API calls.

### Step 2: List Topics in a Model

Topics are entry points for querying. Each topic defines a base view and the set of joined views available.

```bash
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/topics" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Returns topic names, base views, labels, and descriptions.

### Step 3: Inspect a Topic

Get full detail including all views, dimensions, measures, relationships, and AI context:

```bash
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/topic/{topicName}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
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
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/yaml" \
  -H "Authorization: Bearer $OMNI_API_KEY"

# Specific file
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/yaml?fileName=order_items.view" \
  -H "Authorization: Bearer $OMNI_API_KEY"

# Regex filter
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/yaml?fileName=.*sales.*" \
  -H "Authorization: Bearer $OMNI_API_KEY"

# From a branch (branchId is a UUID from the list models response)
curl -L "$OMNI_BASE_URL/api/v1/models/{modelId}/yaml?branchId={branchId}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
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

## Docs Reference

- [Models API](https://docs.omni.co/api/models) · [Topics API](https://docs.omni.co/api/topics) · [Modeling Overview](https://docs.omni.co/modeling) · [Views](https://docs.omni.co/modeling/views) · [Topics](https://docs.omni.co/modeling/topics/parameters) · [Dimensions](https://docs.omni.co/modeling/dimensions) · [Measures](https://docs.omni.co/modeling/measures)

## Related Skills

- **omni-model-builder** — create or modify views, topics, and fields
- **omni-query** — run queries against discovered fields
- **omni-ai-optimizer** — inspect and improve AI context on topics

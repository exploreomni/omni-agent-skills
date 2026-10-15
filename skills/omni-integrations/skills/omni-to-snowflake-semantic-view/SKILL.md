---
name: omni-to-snowflake-semantic-view
description: "Convert an Omni Analytics topic into a Snowflake Semantic View YAML definition. Use this skill whenever someone wants to export Omni metrics to Snowflake, create a Semantic View from an Omni topic, harden BI metrics into the warehouse, or bridge Omni's semantic layer with Snowflake Cortex Analyst."
---

# Omni → Snowflake Semantic View

Converts an Omni topic into a Snowflake Semantic View YAML definition by first exploring the Omni model via API, then translating its definitions into the Snowflake Semantic View format.

---

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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the [**`omni-api-conventions`**](../../../../rules/omni-api-conventions.mdc) rule for profile setup (`omni config init --auth oauth`) and discovering command and request-body shapes with `--schema`.

---

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Runtime Environment Detection

Before starting, determine which environment you are running in — this controls how SQL is executed against Snowflake in Step 7.

### How to detect

Check for the presence of the built-in Snowflake SQL execution capability:

- **Cortex Code** (Snowflake Notebooks / Cortex Analyst): Native SQL execution is available. No extra tooling required.
- **Claude Code, Cursor, or any external IDE/agent**: No native Snowflake connection. You must use one of the CLI options below.

### Detection heuristic

```
If the agent can execute a SQL statement like `SELECT CURRENT_USER()` directly without any shell command → you are in Cortex Code.
Otherwise → you are in an external environment.
```

If unsure, ask the user: _"Are you running this inside Snowflake (Cortex Code / Notebooks), or in an external tool like Claude Code or Cursor?"_

### External environment: Snowflake connectivity options

In Claude Code, Cursor or another terminal-based agent, connect through the Snowflake CLI (`snow`, recommended), SnowSQL, or the Python connector, checking availability in that order: [CONNECTIVITY.md](references/CONNECTIVITY.md).

## Workflow

### Step 1 — Gather Requirements

Ask the user:
1. Which **Topic** do they want to convert?
2. What should the **Semantic View be named**?
3. Where should it be created in Snowflake (**database** and **schema**)?
4. Which **role** should be granted access to the Semantic View?

> ⚠️ **STOP** — Confirm all four answers before proceeding.

---

### Step 2 — Explore the Omni Model

#### 2a. Find the model ID

```bash
omni models list --model-kind SHARED
```

Identify the **Shared Model** and note its `id`. Always prefer the Shared Model over Schema or Workbook models.

#### 2b. Fetch the topic file

```bash
omni models yaml-get <modelId> --file-name <topic_name>.topic
```

#### 2c. Fetch the relationships file

```bash
omni models yaml-get <modelId> --file-name relationships
```

#### 2d. Fetch each view file referenced in the topic

For every view in `base_view` and `joins`, fetch its YAML:

```bash
omni models yaml-get <modelId> --file-name <view_name>.view
```

> If a view is prefixed with `omni_dbt_`, fetch the file that also starts with `omni_dbt_` (e.g. `omni_dbt_ecomm__order_items.view`).

---

### Step 3 — Identify Tables and Joins

#### Mapping view names to Snowflake tables

The `base_view` in the topic file is the primary table. Convert view names to Snowflake table references:

| `base_view` / join value | Snowflake table |
|---|---|
| `ecomm__order_items` | `ECOMM.ORDER_ITEMS` |
| `omni_dbt_ecomm__order_items` | `ECOMM.ORDER_ITEMS` (strip `omni_dbt_`) |

The `__` separator maps to schema (left) and table name (right). If the schema does not exist in Snowflake, skip that table entirely.

#### Reading the join hierarchy

The `joins` parameter in the topic uses indentation to define the join chain — a table indented beneath another joins into its parent:

```yaml
joins:
  user_order_facts: {}        # skip — this is a derived CTE, not a physical table
  ecomm__users: {}            # joins to base_view (ORDER_ITEMS)
  ecomm__inventory_items:     # joins to base_view (ORDER_ITEMS)
    ecomm__products:          # joins to INVENTORY_ITEMS
      demo__product_images: {}           # joins to PRODUCTS
      ecomm__distribution_centers: {}   # joins to PRODUCTS
```

> Skip any view that is a derived table (CTE defined in SQL in Omni). These have no physical Snowflake table to reference.

#### Primary keys

In each view file, find the dimension with `primary_key: true` — this becomes the `unique: true` dimension in the Semantic View.

> ✋ **STOP** — Confirm the table list with the user before continuing.

---

### Step 4 — Resolve the Field List

The topic's `fields` parameter controls which fields from the views are included in the Semantic View.

#### Field targeting rules

| Syntax | Meaning |
|---|---|
| *(no `fields` parameter)* | Include **all** fields from all views |
| `all_views.*` | Include all fields from all views |
| `view.*` | Include all fields in the named view |
| `tag:<value>` | Include all fields tagged with this value |
| `view.field` | Include this specific field |
| `-view.field` | **Exclude** this specific field |

#### How to apply exclusions correctly

Exclusions (prefixed with `-`) must be applied **after** all inclusions are resolved. The process is:

1. Start with an empty inclusion set
2. Process each entry in `fields` in order:
   - If it is an inclusion rule (`view.*`, `view.field`, `tag:x`) → add matching fields to the set
   - If it is an exclusion rule (`-view.field`) → **remove** that field from the set, even if it was added by a wildcard
3. The final set is the complete list of fields to include in the Semantic View

**Example:**

```yaml
fields:
  - ecomm__order_items.*          # include all order_items fields
  - ecomm__users.country          # include this one users field
  - -ecomm__order_items.cost      # remove cost — excluded even though * was used above
  - -ecomm__order_items.raw_json  # remove raw_json — same reason
```

Result: all `order_items` fields **except** `cost` and `raw_json`, plus `users.country`.

> ⚠️ **Critical:** A `-` exclusion always wins. Never include a field that has been explicitly excluded, regardless of what wildcard included it.

---

### Step 5 — Build Relationships

Using the join hierarchy from Step 3 and the `relationships.yaml` fetched in Step 2c, map each join to a Snowflake Semantic View relationship.

Each entry in `relationships.yaml` looks like:

```yaml
- join_from_view: ecomm__order_items
  join_to_view: ecomm__inventory_items
  join_type: always_left
  on_sql: ${ecomm__order_items.inventory_item_id} = ${ecomm__inventory_items.id}
  relationship_type: assumed_many_to_one
```

The `on_sql` field tells you the join columns. Extract the column names to populate `relationship_columns` in the output.

**Available relationship parameters:**

| Parameter | Description |
|---|---|
| `join_from_view` | Source view the join originates from |
| `join_to_view` | Target view being joined to |
| `join_type` | SQL join type (e.g. `always_left`) |
| `on_sql` | SQL condition — extract column names from this |
| `relationship_type` | Cardinality (e.g. `assumed_many_to_one`) |
| `reversible` | Whether the join is bi-directional |
| `where_sql` | Additional WHERE clause when join is active |

---

### Step 6 — Map Dimensions and Measures

For each view in the resolved field list, translate its Omni field definitions into Semantic View entries.

> ⚠️ Only translate fields that survived the Step 4 inclusion/exclusion resolution. Do not add fields that were excluded.

Dimensions map to `dimensions` or `time_dimensions`, and measures to `metrics`. Filter-only fields are never emitted themselves; they only parameterize other fields' SQL. Rules and examples, including filtered measures: [FIELD-MAPPING.md](references/FIELD-MAPPING.md).

---

#### AI Context → `module_custom_instructions`

If the topic has an `ai_context` parameter, include it as:

```yaml
module_custom_instructions:
  question_categorization: <ai_context value>
```

---

#### Sample Queries → `verified_queries`

Convert each entry under `sample_queries` into a SQL statement for `verified_queries`. Use the `prompt` as the `question` and the `description` as context for writing the SQL.

> ✋ **STOP** — Review all dimensions, measures, and relationships with the user before generating the final output.

---

### Step 7 — Generate and Execute the Semantic View

#### Output YAML structure

The file's top-level keys and the shape of each section: [YAML-REFERENCE.md](references/YAML-REFERENCE.md).

#### Create the Semantic View

The SQL is the same regardless of environment. The difference is *how* it is executed.

**SQL to run:**

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('<database>.<schema>', $$
<yaml content here>
$$);
```

**Execution by environment:**

| Environment | Command |
|---|---|
| Cortex Code | Execute the SQL directly in the active Snowflake session |
| `snow` CLI | `snow sql -q "CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(...)"` or write YAML to a temp file and pipe it |
| SnowSQL | `snowsql -a <account> -u <user> -f <sql_file.sql>` |
| Python | `conn.cursor().execute("<sql>")` |

> **Tip for CLI environments:** If the YAML is long, write it to a temporary `.sql` file first and execute the file rather than passing it inline — this avoids shell escaping issues with the `$$` dollar-quoting.

```bash
# snow CLI example with a file
snow sql -f /tmp/create_semantic_view.sql
```

#### Grant access

```sql
GRANT SELECT ON SEMANTIC VIEW <database>.<schema>.<name> TO ROLE <role>;
```

Execute this the same way as the `CREATE` call above, using whichever connection method was established during the Runtime Environment Detection step.

---

## Reference

- [Snowflake Semantic View YAML Spec](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec)
- [SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML](https://docs.snowflake.com/en/sql-reference/stored-procedures/system_create_semantic_view_from_yaml)

# Semantic View YAML Structure

```yaml
name: <name>
description: <string>

tables:
  - name: <name>
    description: <string>
    base_table:
      database: <database>
      schema: <schema>
      table: <table name>

    dimensions:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>
        unique: <boolean>

    time_dimensions:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>

    facts:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>

    metrics:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>

    filters:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>

relationships:
  - name: <string>
    left_table: <table>
    right_table: <table>
    relationship_columns:
      - left_column: <column>
        right_column: <column>

metrics:
  - name: <name>
    synonyms: [ <string>, ... ]
    description: <string>
    expr: <SQL expression>

verified_queries:
  - name: <string>
    question: <string>
    sql: <string>
    use_as_onboarding_question: <boolean>
```

> **Valid top-level keys only:** `name`, `description`, `tables`, `relationships`, `metrics`, `verified_queries`, `module_custom_instructions`

---

# Snowflake Connectivity Options

For **Claude Code, Cursor, or any terminal-based agent**, choose one of the following. Check availability in order:

### Option A — Snowflake CLI (`snow`) ✅ Recommended

```bash
# Check if available
command -v snow

# Configure a connection (first time)
snow connection add

# Execute SQL
snow sql -q "SELECT CURRENT_USER();" --connection <connection_name>
```

Set a default connection to avoid repeating `--connection` on every call:
```bash
snow connection set-default <connection_name>
```

### Option B — SnowSQL (classic CLI)

```bash
# Check if available
command -v snowsql

# Execute SQL
snowsql -a <account> -u <user> -q "SELECT CURRENT_USER();"
```

### Option C — Python (`snowflake-connector-python`)

```bash
pip install snowflake-connector-python
```

```python
import snowflake.connector
conn = snowflake.connector.connect(
    account="<account>",
    user="<user>",
    password="<password>",   # or use key-pair / SSO
    warehouse="<warehouse>",
    database="<database>",
    schema="<schema>",
)
conn.cursor().execute("<SQL here>")
```

> ✋ **STOP** — Confirm the Snowflake connection method with the user before proceeding to Step 7. Record which method is being used so Step 7 generates the correct execution command.

---

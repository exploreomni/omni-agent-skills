# Uploads

Manage CSV/spreadsheet uploads (the files users upload to query alongside warehouse data). `create` and `replace-data` are multipart file uploads: pass the CSV path with `--file` and the other fields as flags. Run either with `--schema` for the full field list. (On CLI < 1.2.0 these flags don't exist — the same fields go through `--body` as *multipart* fields, with file paths as the binary values.)

```bash
# List uploads — filter by connection or model, search by file name
omni uploads list --connection-id <connectionId>
omni uploads list --model-id <modelId> --search-term "forecast" --type csv

# Upload a CSV into a model (--file and --model-id are required)
omni uploads create --file ./forecast.csv --model-id <modelId>

# Upload onto a branch, overriding the generated view name
omni uploads create --file ./forecast.csv --model-id <modelId> \
  --branch-name <branchName> --view-name forecast_v2

# Replace the data behind an existing upload, keeping its id (CLI ≥ 1.1.2)
omni uploads replace-data <uploadId> --file ./forecast_november.csv

# Delete an upload
omni uploads delete <uploadId>
```

`replace-data` fully replaces the upload's data while its id stays stable — views and document tabs reference the upload by id, so they serve the new data with no model or document changes. Column renames/removals may break content referencing the old columns, so compare headers before replacing. For `uploads list --model-id`: shared models return connection uploads; workbook models return their own uploads.

> **Flags vs. `--body`**: `--file` takes a **path**, not file contents, and `--branch-id` / `--branch-name` are mutually exclusive. `--file` and `--model-id` are required on `create` (`--file` on `replace-data`) unless you supply the same fields through `--body`, which on these two commands carries **multipart fields** — binary values are still file paths, not inline data.

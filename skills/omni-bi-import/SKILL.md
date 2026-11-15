---
name: omni-bi-import
description: Migrate dashboards from another BI tool into Omni Analytics with the BI import API — upload a Tableau, Power BI, Looker or Sigma export, parse it, bind its views to warehouse tables, start the AI translation, poll the run, review fidelity, then accept, merge or reject. Use this skill whenever someone wants to import or migrate a workbook, report or dashboard export into Omni, convert a .twb/.twbx, a Power BI report or a LookML project into Omni dashboards, script a bulk migration of many dashboards, check on or list import runs, or fix an import that failed or is blocked on table bindings — including phrasings like "migrate our Tableau workbooks to Omni", "import this Looker dashboard", "move us off Power BI" or "what happened to my import". For building a new Omni dashboard by hand use omni-content-builder; for work inside the other BI tool itself, use no Omni skill.
---

# Omni BI Import

Turn an export from another BI tool into an Omni model change plus Omni dashboards. Omni parses the export, its AI writes the model onto a branch or a workbook model, then builds each dashboard. A run started here is the same run the imports wizard shows in Omni (`runUrl`).

The API is `/api/unstable/bi-imports`. It is unstable: its shape may change, and the Omni CLI has no command for it yet, so this skill uses `curl`.

## Known Issues & Safe Defaults

- Parse before you start. Send `start=false` on create, read the parse, then call `/start`. A run that starts spends AI credits; the parse spends none and shows the dashboards, the views with no table, and the table check.
- Fix every table problem before `/start`. START checks only the tables you name in `tableBindings`. A view the export binds to a table the connection lacks (`cause` not null in `tables`) starts anyway and fails after the AI work.
- When `tableCheck` is `skipped`, the model could not be read: empty `tables` and `candidates` mean unchecked, not clean. Check the tables with `omni-model-explorer` before starting.
- A retried create makes a second run. Before retrying, list runs and match on `sourceDashboardName` (the `title` you sent).
- Keep at most 3 runs in flight. Nothing throttles a script, and each run runs AI jobs.
- Confirm with the user before `/start` (it spends AI credits and writes to the model), before `accept` and before `reject` (it archives the built dashboards and drops the branch or workbook model).
- `accept` applies only to a `workbook` run. A `branch` run completes when its branch is merged in Omni (see `omni-model-builder`); accepting one is a 400.
- Read `modelTarget` from the run. The API defaults to `branch`; the wizard defaults to `workbook`.
- A `start=false` create carrying `dashboards`, `modelTarget` or `tableBindings` is a 400. Pass them to `/start`.
- An unknown field is a 400 in either encoding.
- An `.html` file is imported as an Omni app, and starting it can upload its hard-coded rows as a CSV view. An HTML dashboard sent from Claude is refused with a 422; it has its own import path through Omni's MCP server.
- Export files hold the customer's data model and can hold data rows. Upload them only to the Omni instance the user named, and do not paste their contents elsewhere.

## Prerequisites

```bash
# The instance URL and an API key (org key or personal access token)
: "${OMNI_BASE_URL:?set to https://<org>.omniapp.co}" "${OMNI_API_TOKEN:?set an Omni API key}"

# The Omni CLI, for the companion skills (finding the model, checking tables)
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed. See https://github.com/exploreomni/cli#readme"
```

The caller needs Querier access to a model (a Restricted Querier gets a 403), AI enabled on the target model, and update rights on branches (or on workbook models for a `workbook` target). No feature flag is needed; an `.html` source also needs apps enabled for the organization. A user sees their own runs; a connection admin sees and can decide every run. Another member's run is a 404.

## Discovering Commands

No `omni` command or `--schema` covers these routes. The error bodies are specific: a 400 `detail` names the field or the refused input. Routes:

| Route | Does |
|---|---|
| `POST /api/unstable/bi-imports` | Parse an export into a run and, unless `start=false`, start it |
| `GET /api/unstable/bi-imports` | List runs, newest first |
| `GET /api/unstable/bi-imports/{runId}` | A run's status; a poll moves it forward |
| `POST /api/unstable/bi-imports/{runId}/start` | Start a `PARSED` run |
| `POST /api/unstable/bi-imports/{runId}/{accept\|reject\|cancel}` | Decide a run |

## Workflow

### 1. Gather the export and pick the model

Collect every file the export needs into one request; the source is detected from the files. What each tool needs: [references/source-exports.md](references/source-exports.md). Uploads are capped at 50 MiB across all files.

Find the shared model to import into with `omni-model-explorer` (`omni models list`). Its connection is where the imported views read their tables.

### 2. Parse only

```bash
curl -sS "$OMNI_BASE_URL/api/unstable/bi-imports" \
  -H "Authorization: Bearer $OMNI_API_TOKEN" \
  -F file=@sales.twbx \
  -F modelId=<model-id> \
  -F title="Sales overview" \
  -F start=false
```

Repeat `-F file=@…` once per file. Use multipart, not the JSON body: base64 adds a third to the upload.

The 201 body carries `runId`, `state: PARSED` and the parse. Read:

- `dashboards[]`: each `name` (what `/start` selects by), its `tiles` and the `views` it reaches. `tiles` counts text tiles as well as query tiles, so a built dashboard has fewer query tiles than this number when the source has text. A Looker dashboard with `missingModels` reads explores the export did not include; add those files and parse again.
- `unboundViews[]`: views the export names no table for, with `candidateTable` when the name reads as one.
- `tables[]` and `candidates[]`: each view's table checked against the connection. `cause` is null when the table exists.
- `fidelity.counts`: objects that translate `clean`, `approximated`, by `ai`, or `dropped`, and those `excluded` because no dashboard reaches them. `fidelity.rows` gives the reason per object; a `blocker` severity means that object will not carry over as is.

Tell the user what the parse found before going on: dashboards, counts, blockers and dropped objects.

### 3. Resolve bindings

Every view with a non-null `cause`, and every unbound view a chosen dashboard reaches, needs a `tableBindings` entry keyed by the view's `name`. The value is a warehouse table (`table`, `schema.table` or `database.schema.table`) or `{"view": "<name>"}` for a view the model already has. Prefer an existing view, so the import reuses its fields.

Find the right table or view with `omni-model-explorer`. Ask the user when no table matches; do not guess a binding. For a `cause` of `schema_not_in_model` or `unloaded_schema`, the schema has to be added to the model or refreshed first (`omni-admin`).

### 4. Start

```bash
curl -sS "$OMNI_BASE_URL/api/unstable/bi-imports/$RUN_ID/start" \
  -H "Authorization: Bearer $OMNI_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "<model-id>",
    "modelTarget": "branch",
    "dashboards": ["Sales overview"],
    "tableBindings": { "orders_extract": "analytics.orders" }
  }'
```

- `dashboards` defaults to the first dashboard the export opens on. Name each one to build. A `workbook` target builds one document.
- Choose `branch` when the model change should be reviewed and merged into the shared model, `workbook` when the dashboard should own its model and leave the shared model untouched. Ask the user if they have not said.
- A 400 whose body carries `runId` left the run `PARSED`: fix what `detail` names and call `/start` again. Any other failure cancels the run; parse again to retry.

### 5. Poll

```bash
curl -sS "$OMNI_BASE_URL/api/unstable/bi-imports/$RUN_ID" \
  -H "Authorization: Bearer $OMNI_API_TOKEN"
```

Poll every 30 seconds; a run takes minutes. Stop at `READY_FOR_REVIEW`, `COMPLETE` or `FAILED`. `phase` says the state in plain words. On `FAILED`, report `error.message` and each `documents[].error`, then see [references/errors.md](references/errors.md).

### 6. Review

A run that reached `READY_FOR_REVIEW` built something; it has not been checked. Before recommending a decision:

1. Read `fidelity`: report the `dropped` and `approximated` counts and the `blocker` and `warning` rows.
2. For each entry in `documents[]`, report its `url`, or its `error` if it was skipped.
3. Read each dashboard's tiles. A `branch` run builds its dashboards as drafts bound to the branch: until the branch is merged, the published document is an empty placeholder, so `GET /api/v1/documents/{identifier}` and its `/queries` show one blank query. List the draft with `GET /api/v1/documents/{identifier}/drafts`, then read it by its draft `identifier` (`omni-content-builder` → *branch-bound drafts*).
4. Run each headline tile's query with its saved filters (`omni-query`), setting `modelId` to the draft's `workbookModelId`. A tile that returns zero or no rows is a finding: rerun it with one filter at a time, and compare the filter's values with the values in the column. Filter values are carried over as the export wrote them, so a filter that matched nothing in the source tool (`United States` where the column holds `USA`) matches nothing in Omni; check the export before reporting it as an import fault.
5. Compare a headline number against the source tool's value when the user can supply it.
6. For a `branch` run, review the model change on `branchName` with `omni-model-explorer`.

### 7. Decide

```bash
curl -sS -X POST "$OMNI_BASE_URL/api/unstable/bi-imports/$RUN_ID/accept" \
  -H "Authorization: Bearer $OMNI_API_TOKEN"
```

- `accept`: completes a `workbook` run in `READY_FOR_REVIEW`.
- A `branch` run: merge `branchName` with `omni-model-builder`, following its merge rules.
- `reject`: for a `READY_FOR_REVIEW` or `FAILED` run. Archives the dashboards and drops the branch or workbook model.
- `cancel`: stops a `PARSED` or in-progress run and cleans up what it wrote.

Repeating `reject` or `cancel` on a run already `REJECTED` or `CANCELLED` returns 200 and retries its cleanup.

## Listing runs

```bash
curl -sS "$OMNI_BASE_URL/api/unstable/bi-imports?state=READY_FOR_REVIEW&state=FAILED&sourceType=tableau&pageSize=50" \
  -H "Authorization: Bearer $OMNI_API_TOKEN"
```

Pass `pageInfo.nextCursor` as `cursor` for the next page. A list record names its run `id` and its source `sourceType`; the create and status bodies call them `runId` and `source`.

## Many imports

For more than a handful of exports, follow [references/bulk-migration.md](references/bulk-migration.md): parse everything first, resolve bindings once, then start a few runs at a time from a ledger.

## Related Skills

- `omni-model-explorer`: find the target model, and the tables and views to bind
- `omni-model-builder`: review and merge a `branch` run's model change
- `omni-content-explorer` and `omni-query`: inspect the built dashboards and check their numbers
- `omni-content-builder`: fix or finish a tile the import approximated or dropped
- `omni-ai-optimizer`: add AI context to the imported topics once merged

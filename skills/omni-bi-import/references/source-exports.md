# What to upload for each source

The source is detected from the files, so nothing names it in the request. Send every file one import needs in a single create; a file sent in a later request is a different run. Zip archives are read by their members.

| Source | Send | Notes |
|---|---|---|
| Tableau | The workbook (`.twb` or `.twbx`), plus the file of each published datasource it reads (`.tds` or `.tdsx`) | Without the datasource file, a view that reads a published datasource names no table. It appears in `unboundViews` and needs a `tableBindings` entry before the run can start. |
| Power BI | The report, with its model folder zipped beside it | A thin report carries no model. If the model is a different version of the dataset the report binds, the parse warns and names the tables the model lacks. |
| Looker | The LookML project (zipped) with the dashboard JSON exports | `.dashboard.lookml` files in the project are read as dashboards too. A dashboard whose `missingModels` is not null reads explores the upload did not include. |
| Sigma | The workbook export | |
| HTML page | The `.html` file | Imported as an Omni app, not a dashboard. Needs apps enabled for the organization. |

Fetching straight from the source tool with credentials (the wizard's connect mode) is not available through the API. Export the files first.

## Tableau specifics

- An extract's view does not block the start: the AI looks for its table. Binding it saves that search and removes a guess.
- Every custom SQL relation is named `Custom SQL Query` in Tableau, so the view takes its datasource's or its caption's name. Match bindings on the `name` the parse returns, not on the name in Tableau.
- A connection's Initial SQL does not run on an Omni connection. Temp tables and variables it defines are inlined where possible; what cannot be inlined is a `blocker` row in `fidelity.rows` on the view that reads it.

## Reading a parse that found nothing

A file no supported tool exported is a 400. A file the extractor could not read is a 422. A zip with no usable member parses, with a `blocker` row naming it. In each case check the export against the table above before retrying.

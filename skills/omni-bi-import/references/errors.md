# Errors and what to do

Read the response body first: `detail` names the field or the refused input.

| Status | When | Do |
|---|---|---|
| 400 | Invalid body, query or cursor; an unknown field; no files; files no supported tool exported; over 50 MiB | Fix the request. Check the files against [source-exports.md](source-exports.md). |
| 400 with `runId` | START refused the inputs: a dashboard the export lacks, a blank binding, a binding to a table the connection lacks, an export table in a schema the connection excludes, or several documents onto one `workbook` model | The run is still `PARSED`. Fix what `detail` names and call `/start` on that `runId`. Do not create again. |
| 400 on a decision | The run's state does not allow it, such as `accept` on a `branch` run | Read the run's `state` and `modelTarget`, then pick the decision that applies. |
| 400 on `/start` | The run was already started | Poll it. |
| 403 | An `.html` source in an organization without apps, an embed user, no Querier access to a model, or no AI access or update rights on the target model | Not fixable from here. Tell the user which check failed; an admin changes it (`omni-admin`). |
| 404 | Run or model not found, or another member's run | Check the id and the profile. Only a connection admin sees other members' runs. |
| 500 | A server fault, not a bad request | Do not retry in a loop. Poll the run: a 500 on `/start` can leave it `PARSED`, in which case `/start` can be sent again once the fault is fixed. Report the `detail` to the user. |
| 422 | A file the extractor could not read, or an HTML file sent from Claude | Re-export the file. A Claude dashboard goes through Omni's MCP server, not this API. |

## A create that parsed but did not start

With `start` left true, two responses leave the run `PARSED`:

- 201 with `blockedOn: ["tableBindings"]`: the views in `blockingViews` need bindings. Call `/start` with them.
- 400 with `runId`: see the table above.

A script must handle both. Creating with `start=false` avoids the first.

## A run that failed after starting

`state` is `FAILED` and `error.message` says why. `documents[].error` says why a single dashboard was skipped while others built.

- A table or column the warehouse lacks: a binding was wrong or missing. Reject the run, parse again, and bind the view first.
- A failure with no table cause: retry once. If it fails the same way, stop and report the `runId` and message to the user; do not loop.

A failed run keeps what it wrote until it is rejected. Send `reject` (after confirming) so its branch or workbook model and any built dashboards are cleaned up.

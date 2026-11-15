# Migrating many dashboards

A migration of tens or hundreds of exports fails in two ways: duplicate runs from retries, and AI credits spent on runs that were going to fail on a missing table. Work in three passes and keep a ledger.

## The ledger

Keep one local file (CSV or JSON) with a row per export: file paths, the `title` sent, `runId`, `state`, the chosen `dashboards`, the `tableBindings`, and the decision. Give every export a unique `title`; it comes back as `sourceDashboardName` and is the only way to match a run to an export, since an import cannot be keyed by an id of your own.

After a restart, rebuild the ledger's states from the list route before doing anything else:

```bash
curl -sS "$OMNI_BASE_URL/api/unstable/bi-imports?pageSize=50" \
  -H "Authorization: Bearer $OMNI_API_TOKEN"
```

Follow `pageInfo.nextCursor` until it is absent. Never re-send a create for an export whose `title` already has a run that is not `FAILED`, `REJECTED` or `CANCELLED`.

## Pass 1: parse everything

Create each run with `start=false`. Parsing spends no AI credits, so it can run for the whole set. Record `runId`, `dashboards`, `unboundViews`, the `tables` and `candidates` with a non-null `cause`, and `fidelity.counts`.

Report to the user before pass 2:

- how many exports parsed, and which were refused (400 or 422) and why
- the distinct views that need a binding, across all exports
- exports with `blocker` rows or a high `dropped` count, which are candidates to rebuild by hand instead

## Pass 2: resolve bindings once

The same published datasource or table usually recurs across workbooks. Build one map from view name to binding, confirm it with the user, and reuse it for every run. Prefer `{"view": "<name>"}` once an earlier run's branch has been merged and the view exists in the model, so later imports reuse it and the model does not grow a copy per workbook.

Order the runs so shared views land first: start the exports that cover the most common datasources, merge their branches, then start the rest bound to the merged views.

## Pass 3: start a few at a time

Keep at most 3 runs in flight. Start the next when one reaches `READY_FOR_REVIEW`, `COMPLETE` or `FAILED`. Poll each in-flight run every 30 seconds.

Stop starting new runs and report when:

- two runs in a row fail with the same `error.message` (a shared cause, such as a wrong binding or AI access)
- a start returns a 403 (credits shut off or access changed)

Start one export alone first and review it fully before starting the rest. Its result tells the user what to expect from the set.

## Review and decide

Review every run as in the skill's Review step; a batch does not waive it. Collect the decisions in the ledger and confirm them with the user in one list before sending any `accept` or `reject`.

`branch` runs each write their own branch. Merging many branches that touch the same views can conflict; merge and re-check one at a time with `omni-model-builder`.

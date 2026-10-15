# Alerts

An alert is a schedule with a condition on one tile of an existing dashboard: it runs on its cron and delivers only when the condition holds. Any user who can schedule the dashboard can create one; it needs no admin rights. For plain scheduled deliveries, recipients and email-only users, see **`omni-admin`** → *Schedules*. To build or change the tile an alert watches, see **`omni-content-builder`**.

Add `conditionType` and `conditionQueryMapKey` to the `schedules create` body (each requires the other):

| `conditionType` | Delivers when the watched tile… |
|---|---|
| `RESULTS_PRESENT` | returns rows |
| `RESULTS_MISSING` | returns no rows |
| `RESULTS_CHANGED` | returns different results from the last run |
| `RESULTS_UNCHANGED` | returns the same results as the last run |

`conditionQueryMapKey` is the watched tile's key in the dashboard's `queryPresentations.data` (`omni documents v2-get`), and `filterConfig` sets the dashboard filter values for this alert, so each alert can watch its own subset. Confirm field names with `omni schedules create --schema` before writing the body.

```bash
omni schedules create --body '{
  "identifier": "dashboard-identifier",
  "name": "Alert - projects reaching 80% of budget",
  "schedule": "0 8 ? * MON-FRI *",
  "timezone": "Europe/London",
  "destinationType": "email",
  "format": "link_only",
  "conditionType": "RESULTS_CHANGED",
  "conditionQueryMapKey": "7",
  "recipients": [{ "email": "owner@company.com" }]
}'
```

- **An alert sends messages to people.** Confirm the recipients with the user before creating one.
- **Match the cron to when the data is complete.** A weekly "missing timesheets" list run on Monday morning flags everyone who has not submitted yet. Run it after the submission deadline.
- **The tile decides whether the alert is useful.** A watchlist of categorical columns, filtered to the threshold and about 10 rows long, with the condition named in its subtitle: `omni-content-builder` → *Tiles an alert can watch* in `references/dashboard-style.md`.

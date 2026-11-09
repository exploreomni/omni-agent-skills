# Dashboard Downloads

Async render → poll → fetch. **Poll the `status` field** (`in_progress` → terminal `error`, or a success state carrying the result/URL). **Early-exit on any terminal state** — a fixed-count `for … sleep` loop that only breaks on success runs to the end if the filter is wrong or the render errors:

```bash
# Start async download
JID=$(omni dashboards download <dashboardId> --body '{ "format": "png" }' -o json \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["job_id"])')

# Poll with early exit: anything that is NOT still-in-progress is terminal → break and inspect
while :; do
  R=$(omni dashboards download-status <dashboardId> "$JID" -o json)
  S=$(echo "$R" | python3 -c 'import json,sys;print((json.load(sys.stdin).get("status") or "").lower())')
  case "$S" in
    in_progress|queued|pending|running) sleep 4 ;;
    *) echo "$R"; break ;;   # terminal: success carries the result/URL; "error" carries .error
  esac
done
```

> **`"Job failed to render."` has two causes — disambiguate, don't assume.** It's either (a) **one tile in *your* dashboard throws at render** (a markdown component handed an undefined value, a bad token) — a single bad tile fails the **whole** export — or (b) the render service is down. **Tell them apart by exporting a known-good dashboard:** if that renders, the fault is your content (find the bad tile — isolate by exporting a *one-tile* test doc, or binary-search tiles); if the known-good one *also* errors, the service is down — bound your attempts and report. Either way, while the render path is unavailable you can't PNG-verify markdown/CSS tiles, so fall back to draft read-back and per-tile `query run`, plus a browser check when one is reachable (see [validation-and-testing.md](validation-and-testing.md#optional-check-the-render-in-a-browser)). On success, fetch the image with **`omni dashboards download-file <dashboardId> <jobId>`**. Full catch-22 writeup: [references/markdown-tiles.md](markdown-tiles.md).

## Download a single tile (not the whole dashboard)

Add **`queryIdentifierMapKey`** = the tile's `queryPresentations.data` key (e.g. `"5"`) to the download body; it renders only that tile. Same async flow (`download` → `download-status` → `download-file`).

```bash
omni dashboards download <dashboardId> --body '{ "format": "png", "queryIdentifierMapKey": "5" }'
```

Format matrix: **pdf / png / xlsx / csv / json** — `json` is **single-tile only** (requires `queryIdentifierMapKey`), and for a full dashboard `csv` returns a **ZIP of one CSV per tile**. `pdf`/`png` give the image; `csv`/`xlsx`/`json` give the tile's data. For the authoritative `paperFormat` values and the full PDF/PNG + data option set (`paperOrientation`, `hideTitle`, `showFilters`, formatting/row-limit flags, `filename`, `filterConfig`, …), run **`omni dashboards download --schema`** — don't rely on this list staying exhaustive.

## Multi-page dashboards

Without a selection, pdf and png render the first page. On an advanced-layout dashboard, `containerPages` takes page `instanceKey`s (from `v2-get` → `containers`) to choose pages, and `elements` (png only) captures listed tiles as their own pngs. Neither combines with `queryIdentifierMapKey`. Options: `omni dashboards download --schema`.

# Peloton Product Comparison Studio (Omni App prototype)

An interactive, Peloton-branded app built as an **Omni App** (custom HTML in place of a dashboard) on the Omni demo instance. It compares the product line-up (Bike, Bike+, Tread, Tread+, Row, Guide, App) across specs, sales momentum, regional mix, and member engagement, and finishes with a "Fit finder" that ranks the line-up from four quick answers.

| Item | Value |
|---|---|
| Document | `Peloton Product Comparison` (identifier `f8a35453`) on omni.omniapp.co |
| App URL | https://omni.omniapp.co/w/f8a35453?redirectToApp=true |
| App source | `app.html` (self-contained, embedded subset font, no external requests, ~90 KB) |
| Wired queries | `peloton_products`, `peloton_monthly_sales`, `peloton_engagement` (SQL in `sql/`) |

## What the app does

1. **Choose products** – tap up to four product chips (or press 1 to 7), or use the presets. A sticky tray keeps the current comparison, a reset, and a jump to the fit finder within reach once you scroll.
2. **Side by side** – price, membership, signature feature, footprint, engagement, with winner tags (lowest price, biggest screen, best retention, most used) only when one product wins outright.
3. **Spec sheet** – grouped into Price, Equipment, and Experience, with "best" on the single strongest value per row and a differences-only toggle.
4. **Fit finder** – goal, budget slider, space, and priority produce a match score out of 100 with the reasons, and one button loads the top three into the comparison.
5. **Deeper analysis (collapsed)** – a 24-month momentum chart (units, hardware revenue, or new memberships) with a region filter, keyboard arrow navigation, and a table view; regional share with the chosen region highlighted and a table view; and engagement small multiples.

Light and dark mode follow the viewer's Omni theme (`prefers-light` / `prefers-dark` on `<body>`). The chart palette was validated for colour-vision deficiency and contrast in both modes, every muted text style measures at least 4.5:1, controls are 44px tall on touch screens and narrow viewports, focus rings are visible, and the typeface (Archivo, SIL Open Font License) is subset and embedded so the app loads nothing from outside Omni.

### Impeccable review

The app went through [Impeccable](https://impeccable.style/) `critique` and `audit` (two isolated assessments plus the deterministic detector), then a `polish` pass. Before: 26/40 design health, 13/20 audit, 14 CLI detector findings and 50 in-browser findings (muted text at 2.9 to 3.4:1, kicker labels, ghost cards, sub-44px targets). After: 0 detector findings, all measured text at or above 4.5:1, and the analyst panels moved behind a disclosure so the shopper story runs picker, side by side, spec sheet, fit finder. The critique snapshot is in `.impeccable/critique/`; the assessment notes are in `archive/`.

## How data gets in

Omni Apps cannot query the warehouse directly. They read the results of **wired queries** in the paired workbook through the in-app runtime:

```js
omni.ready.then(() => {
  omni.runQueries(['peloton_products', 'peloton_monthly_sales', 'peloton_engagement']);
  omni.query('peloton_products').onData(result => {
    if (result.status === 'running') return;
    // result.rows is an array of objects keyed by field name, e.g. "peloton_products.product"
  });
});
```

The app normalises row keys to the bare column name, so it works whether the tab is a SQL tab or a model query.

**Current state:** the workbook holds a `placeholder` query only (the Omni chat agent cannot create SQL tabs). Until the three tabs exist, the app shows the badge **"Sample data"** and uses an embedded dataset generated with the same formulas as the SQL. Once the tabs are added the badge switches to **"Live data from Omni"** with no code change.

### Add the three SQL tabs (2 minutes in the UI)

1. Open the workbook https://omni.omniapp.co/w/f8a35453 and enter draft mode.
2. Add a new query tab → **Start from SQL**, paste `sql/peloton_products.sql`, run it, and rename the tab to `peloton_products`.
3. Repeat for `sql/peloton_monthly_sales.sql` → `peloton_monthly_sales` and `sql/peloton_engagement.sql` → `peloton_engagement`.
4. Open the App tab; the badge should read "Live data from Omni". Publish.

The tab **names** are what the app binds to. The SQL uses literal `VALUES` and a `GENERATOR` (with a per-product regional mix), so it needs no tables; for a real engagement swap each tab for a query on Peloton's product catalog, orders, and workouts tables with the same column names (or edit the `QUERIES` map and column names at the top of `app.html`).

## Omni CLI equivalents

The app was written through the Omni MCP app tools (`putApp` / `publishDraft`) because this session had no CLI credentials. The same steps with the Omni CLI (verified against `omni` 1.4.0 with `--help` and `--schema`):

```bash
omni config use <profile>
omni whoami whoami                                          # auth + permission check

# Build the request body from app.html ({"html": "<page>"}); settings are kept as they are when omitted
python3 -c 'import json,sys; json.dump({"html": open("app.html").read()}, open("archive/body.json","w"))'

omni documents put-app-auto-draft f8a35453 --body @archive/body.json   # create-or-reuse main draft, replace HTML
omni documents get-main-draft-app f8a35453                               # read back; check "warnings"
omni documents v2-publish-draft f8a35453                                 # publish the main draft
omni documents get-app f8a35453                                          # published HTML + settings
```

`put-app-auto-draft --schema` shows the body: `html` (required, 2 MiB cap) and an optional `settings` object (clipboard, downloads, navigation, `safeDomains`, `frameDomains`). The `warnings` array is where host-policy issues show up: this app loads nothing external, so none are expected and none came back.

## Files

| Path | Purpose |
|---|---|
| `app.html` | The app. Edit and re-publish with `putApp` or the CLI. |
| `sql/*.sql` | The three wired query definitions (Snowflake). |
| `archive/preview.js` | Local Chromium harness: renders light, dark, tablet, mobile, and a stubbed `omni` runtime, exercises the controls, and screenshots each. `node archive/preview.js` |
| `archive/app.v1.html` | The version before the Impeccable polish pass. |
| `archive/impeccable-*.json`, `archive/impeccable-assessment-a.md` | Detector output before and after, and the design-review assessment. |
| `archive/shot-*.png` | Screenshots from the last preview run. |

## Caveats to say out loud with Peloton

- Product specs and US list prices are indicative (public figures, rounded); sales and engagement numbers are synthetic.
- Apps are an alpha/beta surface; embedding an App in a customer-facing product sits behind the `embed-apps` flag. See the internal "SE Guide - Embedding Apps" app for current status.
- The runtime API (`omni.ready`, `omni.runQueries`, `omni.query(name).onData`) was taken from working apps on the instance, not from public docs, so re-check it against the Apps docs before promising method names.

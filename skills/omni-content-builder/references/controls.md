# Controls (v2) Reference

In the [v2 documents API](documents-v2.md), `controls.data` holds dashboard filters and interactive controls. Each entry is `{ "config": {…}, "map": {…} }`. To make a control **visible**, also add a content-item for it to a container (see [containers.md](containers.md)) — otherwise it lands in the HIDDEN CONTROLS tray.

```jsonc
"controls": {
  "data": { "<controlId>": { "config": { … }, "map": { … } } },
  "order": ["order_created_filter", "granularity", "kpi_metric_1", …]
}
```

## `map` — per-tile scoping

`map` overrides which tiles a control affects, keyed by tile key:
- `"<tileKey>": false` — exclude that tile.
- `"<tileKey>": "<fieldName>"` — remap to a different field on that tile.
- **Omit or empty `map` ⇒ the control applies to every tile by its `config.fieldName`.**

> **Known limitation.** A **filter's** `map` works (e.g. excluding a tile from a date filter so it stays all-time). An **interactive control's** `map` (a `FIELD_SELECTION` field/timeframe switcher) is currently a **no-op through the API** — the switcher applies to all tiles using its field and cannot be scoped programmatically. Scope these in the **UI Mapping panel**. Plan layouts so a global switcher is acceptable, or expect to finish scoping in the UI.

## Config shapes

### Date filter

```jsonc
"config": {
  "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
  "left_side": "1 year ago", "right_side": "1 year",
  "fieldName": "ecomm__order_items.created_at",
  "topic": "orders", "base_view": "ecomm__order_items", "label": "Order Creation Time"
}
```

### Timeframe switcher (day/week/month)

```jsonc
"config": {
  "type": "FIELD_SELECTION", "kind": "TIMEFRAME", "id": "granularity",
  "label": "Timeframe", "display": "BUTTON_TOGGLE",
  "field": "ecomm__order_items.created_at[month]",
  "options": [
    { "label": "Day",   "value": "ecomm__order_items.created_at[date]" },
    { "label": "Week",  "value": "ecomm__order_items.created_at[week]" },
    { "label": "Month", "value": "ecomm__order_items.created_at[month]" }
  ]
}
```

Binds to tiles whose query uses that timeframed field.

### Field / metric switcher

```jsonc
"config": {
  "id": "kpi_metric_1", "kind": "FIELD", "type": "FIELD_SELECTION",
  "field": "ecomm__order_items.total_revenue",   // BOTH the default selection AND the swap target
  "label": "Metric", "display": "SELECT",
  "options": [
    { "label": "Total Revenue",  "value": "ecomm__order_items.total_revenue" },
    { "label": "Total Margin",   "value": "ecomm__order_items.total_margin" },
    { "label": "Order Count",    "value": "ecomm__order_items.order_count" },
    { "label": "Avg Sale Price", "value": "ecomm__order_items.average_sale_price" }
  ]
}
```

> `config.field` is **both** the default selected option **and** the field the control swaps. They cannot be decoupled — you cannot point the swap at a throwaway field while keeping a real default. This matters when a switcher would otherwise corrupt other tiles that share the field (see the metric-switch pattern in [visConfig.md](visConfig.md)).

## Control vs. content-item — and syncing a filter across pages

A **control** lives once in `controls.data[id]` — it owns the config **and the live value/state**. A **content-item** (`{ type: "filter" | "control", id, instanceKey }`) is just a *placement* that renders that control somewhere: the `id` is the reference into `controls.data`; the `instanceKey` is the placement's own unique key.

**To show the same filter on multiple pages and keep their values in sync:** put a content-item on each page that reuses the **same `controls.data` id**, varying only the `instanceKey`. There's still exactly one control, so its value is shared — change it on any page and every placement reflects it. (Mint a *new* id and you get a separate, **unsynced** filter.)

```jsonc
// page-1 sidebar
{ "type": "filter", "id": "order_created_filter", "instanceKey": "fbar-order-created" }
// page-2 sidebar — SAME id, different instanceKey → one control, two placements, synced
{ "type": "filter", "id": "order_created_filter", "instanceKey": "fbar-order-created-p2" }
```

- **UI path:** **Duplicate page** does exactly this — it deep-clones the page's containers + content-items, regenerating `instanceKey`s but **preserving each content-item's `id`**, so the copy's filters reference the same controls (synced). Build the sidebar on one page, duplicate, then swap the copy's content tiles.
- **Not** via independent drag/add: dragging a filter **moves** its single placement (no copy), and there's no UI affordance to place an already-placed control a second time. The filter-bar's duplicate-rejection is **bar-scoped only**, so you *can* drag a filter out of the bar into a page sidebar — but just that one placement.
- **Filter-bar contrast:** in the (global, every-page) filter bar, **one** placement covers all pages. Per-page sidebars need **one placement per page**, all reusing the same control id.

## Mustache control tokens (in markdown/text tiles)

A markdown tile can react to a control's current selection:

| Token | Resolves to |
|---|---|
| `{{controls.<id>.summary}}` | the selected option's **friendly label** (e.g. `"Total Revenue"`) |
| `{{controls.<id>.value}}` | the raw selected **field name** |
| `{{controls.<id>.label}}` | the control's **title** |

> **Namespace gotcha.** `{{controls.<id>}}` resolves only against **dashboard controls** (`controls.data`). A control embedded in a tile's `query.controls[]` is invisible to the template (every token returns empty) **and** renders in the HIDDEN CONTROLS tray. Drive markdown from a dashboard control, not a tile-embedded one.

This is the basis of the dynamic-caption and metric-switch patterns documented in [visConfig.md](visConfig.md).

## See also

- [documents-v2.md](documents-v2.md) — the v2 envelope
- [containers.md](containers.md) — making controls visible (filter bar / in-tile)
- [visConfig.md](visConfig.md) — markdown tiles that follow a control

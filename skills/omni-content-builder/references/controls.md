# Controls (v2) Reference

In the [v2 documents API](documents-v2.md), `controls.data` holds dashboard filters and interactive controls. Each entry is `{ "config": {…}, "map": {…} }`. To make a control **visible**, also add a content-item for it to a container (see [containers.md](containers.md)) — otherwise it lands in the HIDDEN CONTROLS tray.

```jsonc
"controls": {
  "data": { "<controlId>": { "config": { … }, "map": { … } } },
  "order": ["order_created_filter", "granularity", "kpi_metric_1", …]
}
```

## Contents

- [`map` — per-tile scoping](#map--per-tile-scoping) — exclude/include tiles, field overrides
- [Config shapes](#config-shapes) — filter and interactive-control config by type
- [More filter config shapes](#more-filter-config-shapes)
- [Hiding a control](#hiding-a-control) — `config.hidden`
- [Parent controls (one control drives many)](#parent-controls-one-control-drives-many)
- [Control vs. content-item — and syncing a filter across pages](#control-vs-content-item--and-syncing-a-filter-across-pages)
- [Mustache control tokens (in markdown/text tiles)](#mustache-control-tokens-in-markdowntext-tiles)
- [See also](#see-also)

## `map` — per-tile scoping

`map` overrides which tiles a control affects, keyed by tile key:
- `"<tileKey>": false` — exclude that tile.
- `"<tileKey>": "<fieldName>"` — remap to a different field on that tile.
- **Omit or empty `map` ⇒ the control applies to every tile by its `config.fieldName`.**

> **Both filters and interactive controls scope per-tile.** `{"<tileKey>": false}` excludes a tile from either a **filter** (it stays all-time) or an interactive **`FIELD_SELECTION`** switcher (it stops rewriting that tile); `"<tileKey>": "<fieldName>"` remaps it.

### Wiring a filter across tiles that use different date fields

A date filter's `config.fieldName` (e.g. `order_items.created_at`) is the **default** applied to every tile. When tiles come from topics with **different date fields** — `order_items.created_at`, `sessions.session_start`, `users.created_at` — the default only matches some of them. Use `map` to remap each tile to *its own* date field:

```jsonc
"map": {
  "12": "ecomm__sessions.session_start",   // a sessions-based tile
  "15": "ecomm__users.created_at",          // a users/acquisition tile
  "20": false                               // a current-state snapshot — leave unfiltered
}
```

Two rules:

- **A new tile inherits the control's *default* field.** If that field isn't in the new tile's topic, the filter can still be satisfied by **forcing a join through the global `relationships`** (a field reachable via a join the *topic* never declared) — which can **fan out and inflate counts** (e.g. a sessions tile dragging in `order_items`, so "viewed > sessions"). Always wire a new tile to its real date field (or `false`) — don't rely on the default.
- **Relative-date filters shouldn't apply to current-state *snapshot* tiles** (inventory on hand, units in stock). Filtering "units in stock" by `created_at` turns a current snapshot into a creation-cohort and distorts it — exclude those tiles with `false`.

A `map` value can only be a field name or `false` — there's no per-tile *override* of the relative window itself.

> **Two filter controls on the same field of the same tile = OR, not AND.** If two (or more) filters map to the same field on a tile, they're merged into a single composite **OR** before the query runs — a *union* of the windows (e.g. `created_at` in "past 12 months" **OR** "past 6 months" → effectively past 12 months), never an intersection. You **cannot AND two filters on one field** this way, so you can't bound a range by stacking, say, a `>=` and a `<=` date control on one field — author a **single range/`between` filter** instead. (This OR-merge is the *query* behavior. In mustache it's context-dependent: a **viz tile** sees only the merged composite at the `view.field` key with `.value` empty, but a **dashboard text tile** sees the two filters **separately, keyed by control id**, each with its own `.value` — see [mustache.md](mustache.md).)

## Config shapes

The full control catalog (`type` values from the `CONTROL_TYPE` enum):

| `type` | Kind | Filter / control | Purpose |
|---|---|---|---|
| `date` / `string` / `number` / `boolean` | — | filter | standard dashboard filters |
| `FIELD_SELECTION` | `FIELD` | control | swap which field/metric a tile shows |
| `FIELD_SELECTION` | `TIMEFRAME` | control | swap the timeframe grain (day/week/month) |
| `MULTI_FIELD_SELECTION` | — | control (parent) | one picker sets several child `FIELD_SELECTION` controls |
| `FIELD_PICKER` | — | control | viewer picks one or more fields to **add** to a tile |
| `MULTI_FIELD_FILTER` | — | filter | OR a filter across several different fields |
| `DYNAMIC_FILTER` | — | filter | let viewers add their own ad-hoc filters |
| `TOP_N` | — | control | override a dimension's dynamic top-N limit |
| `PERIOD_OVER_PERIOD` | — | control | add prior-period comparison columns (dashboard-only) |

All carry `id` + optional `label`/`description`/`hidden` — **except `PERIOD_OVER_PERIOD`**, which carries only `id` + its own fields (no `label`/`hidden`).

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

> `config.field` is **both** the default selected option **and** the field the control swaps. They cannot be decoupled — you cannot point the swap at a throwaway field while keeping a real default. To keep a switcher from rewriting other tiles that share its field, **scope it with `map`** (set those tiles to `false`); the markdown metric-switch pattern in [markdown-tiles.md](markdown-tiles.md) is the alternative when you want a card to follow `.summary` with no field-swap at all.

### Field picker (FIELD_PICKER — adds fields)

```jsonc
"config": {
  "id": "extra_fields", "type": "FIELD_PICKER", "label": "Add fields",
  "options": [
    { "label": "Department",   "value": "ecomm__products.department", "isDimension": true },
    { "label": "Total Margin", "value": "ecomm__order_items.total_margin" }
  ],
  "values": ["ecomm__products.department"]   // currently-selected fields to ADD
}
```

> Unlike `FIELD_SELECTION` (which *swaps* one field), a field picker **adds** its selected `values` to a tile's query — so it has no existing-field-overlap requirement and applies to the tiles it's mapped to. `isDimension` hints whether each option is a dimension; `values` is the live selection.
>
> **Known cosmetic bug:** a field picker's chip renders with the string-filter verb — e.g. `is Category,Order Count` — because it falls through to the string-EQUALS summary instead of having its own. Functionality is unaffected (the fields are added correctly).

### Top-N (TOP_N — override the limit)

```jsonc
"config": {
  "id": "top_n", "type": "TOP_N", "label": "Top N",
  "field": "ecomm__products.brand_top",   // BASE dimension name; the tile field carries [N]
  "value": 10, "defaultValue": 10, "min": 1, "max": 50
}
```

> Overrides a dimension's dynamic top-N by swapping its numeric parameterization (top 10 → top 25). `value`/`defaultValue` are integers ≥ 1 within `min`/`max` (and `min ≤ max`).
>
> **Requires a `dynamic_top_n` dimension** — `field[N]` is a **no-op** on a plain dimension (returns all rows regardless of N), so the control appears to do nothing. Define it in the model:
> ```yaml
> dimensions:
>   brand_top: { sql: ${brand}, dynamic_top_n: { n: 10, by: ecomm__order_items.total_revenue, desc: true, else: Other } }
> ```
> Then the tile queries `ecomm__products.brand_top[10]` and the control's `field` is `ecomm__products.brand_top`. Verify: `brand_top[5]` → 6 rows (5 + "Other"), `brand_top[25]` → 26.

### Period over period (PERIOD_OVER_PERIOD)

```jsonc
"config": {
  "id": "pop", "type": "PERIOD_OVER_PERIOD",
  "filterFieldName": "ecomm__order_items.created_at", "filterId": "order_created_filter",
  "computations": [ { "timeUnitName": "year", "periodsAgo": 1, "isDynamicPreviousPeriod": false } ]
}
```

> Dashboard-only; adds prior-period comparison columns. **Add it to `controls.data` (+ `order`) only — do _not_ author a PoP child in the `containers` filter bar.** Omni **auto-renders** the "Compare to" widget next to the date filter named in **`filterId`**; a manually-placed PoP filter-bar child duplicates it and the extra copy renders as **"Item missing"** (and it still can't go **in-tile** — same "Item missing"). Point `filterId` at an existing **date-filter control**. The comparison comes from the **tile query's** `period_over_period_computations` + a date filter (the control only changes the offset) — to make the table follow the dashboard date control, **map that date filter onto the tile** (`map["<tileKey>"]: "<view.field>"`) instead of hardcoding a competing window in `query.filters`. **No `label`/`hidden`.** **Casing differs by layer:** the control config is **camelCase** (`timeUnitName`/`periodsAgo`/`filterFieldName`/`filterId`); the tile query is **snake_case** (`time_unit_name`/`periods_ago`/`date_filter_field_name`). Tile-query scaffolding:
> ```jsonc
> "query": {
>   "filters": { "ecomm__order_items.created_at": { "type":"date","kind":"TIME_FOR_INTERVAL_DURATION","ui_type":"PAST","left_side":"6 months ago","right_side":"6 months" } },
>   "period_over_period_computations": [ { "date_filter_field_name":"ecomm__order_items.created_at", "periods_ago":1, "time_unit_name":"year" } ]
> }
> ```

### Multi-field filter (MULTI_FIELD_FILTER — OR across fields)

```jsonc
"config": {
  "id": "recent", "type": "MULTI_FIELD_FILTER", "label": "Recent activity", "conjunction": "OR",
  "filters": [
    { "id": "f1", "fieldName": "ecomm__users.created_at",       "filter": { /* a filter object */ } },
    { "id": "f2", "fieldName": "ecomm__order_items.created_at", "filter": { /* a filter object */ } }
  ]
}
```

> ORs each entry's filter across *different* fields. `conjunction` is `"OR"` only (AND is the implicit behavior of separate filters). Each entry's `filter` is a standard filter object (same shapes as "More filter config shapes" below), stored as JSON.

### Dynamic filter (DYNAMIC_FILTER — viewer-added)

```jsonc
"config": {
  "id": "adhoc", "type": "DYNAMIC_FILTER", "label": "Add a filter", "includeViewNameInLabels": true,
  "fieldSelection": { "mode": "specific", "fields": [ { "fieldName": "ecomm__users.state" }, { "fieldName": "ecomm__products.brand" } ] }
}
```

> Lets viewers add their own ad-hoc filters at view time. `fieldSelection.mode`: `"full-model"` (any field), `"auto"` (fields from `topics: ["…"]`), or `"specific"` (only the listed `fields: [{ fieldName, topicName? }]`). `includeViewNameInLabels` prefixes labels with the view name.

## More filter config shapes

Each shape below is a `controls.data.<id>.config` body. Common optional properties across filter types: `description` (info-icon tooltip), `required: true` (a value must be selected), `hidden: true` (see below). Rules:

- **Every filter MUST include `fieldName`** — fully qualified (e.g. `"users.state"`) — or it won't bind to any column. Date filters take **no timeframe bracket** (`order_items.created_at`, not `created_at[month]`).
- Configs read back from UI-built dashboards also carry `topic` and `base_view` (see the date-filter example above) — include them.
- `config.type` values include `"string"`, `"number"`, `"date"`, `"boolean"`, `"null"`, `"by_query"`, `"user_attribute"`, `"composite"`. Shapes for the common ones are below; for the rest, build the filter in the Omni UI and read it back — `omni documents v2-get <identifier>` returns a `controls` slice you can copy directly into a patch.

### String dropdown

```jsonc
"config": {
  "type": "string", "kind": "EQUALS",
  "fieldName": "order_items.status", "label": "Order Status",
  "values": []        // default selection: [] = none (show all); ["complete"] pre-selects
}
```

### Boolean toggle

```jsonc
"config": {
  "type": "boolean",
  "fieldName": "users.is_active", "label": "Active Only",
  "is_negative": false   // false = keep true rows; true = keep false rows
}
```

### Relative date range ("last 6 months")

```jsonc
"config": {
  "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
  "left_side": "6 months ago", "right_side": "6 months",
  "fieldName": "order_items.created_at", "label": "Date Range"
}
```

`ui_type` is `"PAST"` for lookback, `"FUTURE"` for forward-looking. `left_side` is the human-readable start (`"30 days ago"`, `"1 year ago"`); `right_side` is the duration (`"30 days"`, `"1 year"`). Note `"1 year ago"`/`"1 year"` means the calendar year, not a rolling window — use `"12 months"` for rolling.

### Absolute date range

```jsonc
"config": {
  "type": "date", "kind": "WITHIN_RANGE",
  "left_side": "2024-01-01", "right_side": "2024-12-31",
  "fieldName": "order_items.created_at", "label": "Date Range"
}
```

### Hidden filter

Any filter type with `"hidden": true` — applied to queries but not shown in the dashboard UI. Useful for hardcoded filters viewers shouldn't change. (Omni recommends model **access filters** over hidden dashboard filters for data restriction.)

```jsonc
"config": {
  "type": "string", "kind": "EQUALS",
  "fieldName": "order_items.status", "label": "Status",
  "values": ["complete"], "hidden": true
}
```

Filters do **not** auto-apply to SQL-mode tiles — use templated (dynamic) filters in the SQL instead.

## Hiding a control

Set **`config.hidden: true`** to keep a control out of the layout: it won't render and won't be auto-placed into the filter bar, yet it still holds live state and reacts to other controls. Remove its content-item from every container at the same time — a control left unplaced **but not hidden** gets auto-placed back into the filter bar.

> The flag lives at **`config.hidden`** (inside the config object). An entry-level `"hidden": true` (sibling of `config`/`map`) is **stripped on save** — set it on the config and read the doc back to confirm.

**In the editor (UI).** Hidden controls collect in a collapsible **HIDDEN CONTROLS** tray pinned to the top of the canvas — collapsed it shows just a count (`▸ HIDDEN CONTROLS (5)`), expanded it lists each so an author can still edit and set values. The UI equivalent of `config.hidden` is **Edit Control → Settings → "Hide this control when viewing the dashboard."** A hidden control is invisible to viewers but its **value still applies**, and can be set via scheduled deliveries, embeds, and the URL param **`?c--<controlId>=<value>`** (`&editControl=<controlId>` opens its edit panel).

## Parent controls (one control drives many)

A **`MULTI_FIELD_SELECTION`** control sets several child `FIELD_SELECTION` controls at once — one button group swaps an entire row of KPIs to a named preset:

```jsonc
"metric_set": { "config": {
  "id": "metric_set", "type": "MULTI_FIELD_SELECTION", "display": "BUTTON_TOGGLE",
  "label": "Metric Set", "value": "fin",
  "options": [ { "label": "Financials", "value": "fin" }, { "label": "Volume", "value": "vol" } ],
  "selectionMap": {
    "kpi_metric_1": { "fin": "ecomm__order_items.total_revenue", "vol": "ecomm__order_items.order_count" },
    "kpi_metric_2": { "fin": "ecomm__order_items.total_margin",  "vol": "ecomm__order_items.returned_item_count" }
  }
}, "map": {} }
```

- `selectionMap` is `{ "<childControlId>": { "<parentValue>": "<childFieldValue>" } }` — picking a parent option pushes the mapped value into each child.
- Place **only the parent** in a container; set each child's **`config.hidden: true`** so the children stay invisible.
- The hidden children feed markdown tiles via `{{controls.<childId>.summary}}` (see [markdown-tiles.md](markdown-tiles.md)), so one parent click re-labels a whole row of KPI cards. The cards follow `.summary` (no field-swap needed); if a child's `config.field` is a real measure other tiles share, scope it with all-`false` child `map`s so it can't bleed into them.

### A parent's Mapping tab is moot

A parent control has **no field of its own** — it acts only through its children's `selectionMap`, so it never injects anything into a tile. Whether a parent affects a tile is structural: it applies only to a tile whose query embeds **all** of its child controls. So its per-tile Mapping checkboxes can at most *exclude*, never *add* — and when the children are read via `.summary` (not embedded in tile queries), the parent touches **zero** tiles regardless of the Mapping tab. The tab still renders and **defaults to all-checked**, which misleadingly reads as "drives every tile"; treat it as exclusion-only.

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

A markdown tile can react to a **control's** current selection. These tokens are for the **interactive controls** in this file (`FIELD_SELECTION` field/timeframe switchers, `FIELD_PICKER`, `TOP_N`, `PARENT`, `MULTI_FIELD_FILTER`, `DYNAMIC_FILTER`) — **not** for plain filters:

| Token | Resolves to |
|---|---|
| `{{controls.<id>.summary}}` | the selected option's **friendly label** (e.g. `"Total Revenue"`) |
| `{{controls.<id>.value}}` | `FIELD_SELECTION` → field name · `TOP_N` → number · `FIELD_PICKER` → array · `PARENT` → value |
| `{{controls.<id>.label}}` | the control's **title** |

> **⚠️ Filters and controls share one slice but split across two mustache namespaces.** A `date`/`string`/`number`/`boolean` **filter** lives in `controls.data` like every control, but it is **not** exposed in the `controls` template namespace — `{{controls.<filterId>.…}}` renders **empty**. Reference a filter under **`filters`**, keyed by **`view.field`** (not by control id): `{{filters.ecomm__order_items.created_at.summary}}` for the friendly window text, `.value` for the raw value. In a markdown-viz tile, `filters` resolves against that tile's **own** `query.filters`, so the same token reflects each tile's own (per-tile) filter/control. The full filter-vs-control decision, the keying rule, every namespace (`filters`/`controls`/`result`/`metadata`/`queries`/`inspect`), and worked scenarios are in **[mustache.md](mustache.md)**.

> **Namespace gotcha.** `{{controls.<id>}}` resolves only against **dashboard controls** (`controls.data`). A control embedded in a tile's `query.controls[]` is invisible to the template (every token returns empty) **and** renders in the HIDDEN CONTROLS tray. Drive markdown from a dashboard control, not a tile-embedded one.

This is the basis of the dynamic-caption and metric-switch patterns documented in [markdown-tiles.md](markdown-tiles.md) and [mustache.md](mustache.md).

## See also

- [documents-v2.md](documents-v2.md) — the v2 envelope
- [containers.md](containers.md) — making controls visible (filter bar / in-tile)
- [markdown-tiles.md](markdown-tiles.md) — markdown tiles that follow a control

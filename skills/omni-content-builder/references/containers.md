# Containers (v2 Layout) Reference

In the [v2 documents API](documents-v2.md), `containers` is the layout tree — it decides where each tile renders and which controls are visible. If a tile (or control) is not referenced by a container, it does not appear, even though it exists and runs. This is the single most common reason a v2 dashboard looks empty.

## Top-level shape

```jsonc
"containers": [
  { "instanceKey": "filter-bar", "containerType": "stack", "direction": "row", "children": [ /* visible filters/controls */ ] },
  { "containerType": "page", "container": { "containerType": "grid", "children": [ /* tile stacks */ ] } }
]
```

- The **filter bar** holds the visible filters/controls (see "Control placement" below).
- The **page → grid** holds the tile stacks.
- Supply your own unique `instanceKey` strings (ULIDs not required, but they must be unique).

## The grid is 24 columns

Tile widths are in 24ths: `w: 12` = half width, `w: 24` = full width, `w: 6` = quarter. A tile sized `w: 12` fills half the row; size accordingly or tiles render at unexpected widths.

`gridPosition` = `{ x, y, w, h }`:
- `x` (0–23) and `w` are columns.
- `y` and `h` are fine-grained row units. Rough heights: **KPI ~20–28**, **chart ~48**, **table ~46**.
- To move a row down, increase its `y` and shift everything below it by the same delta (tiles can overlap if you don't).

## A tile stack

Each placed tile is a `stack` carrying a `gridPosition` and a `metadata.attachedQueryKey` pointing at its `queryPresentation`:

```jsonc
{
  "containerType": "stack",
  "style": "tile",
  "name": "Metric 3",
  "fillSpace": true,
  "metadata": { "attachedQueryKey": "3" },
  "gridPosition": { "x": 0, "y": 0, "w": 6, "h": 24 },
  "instanceKey": "tile-stack-3",
  "children": [
    { "as": "metadata", "id": "3", "type": "query", "format": "name", "padding": [0,0,2,0], "instanceKey": "tile-title-3" },
    { "as": "chart", "id": "3", "type": "query", "instanceKey": "tile-viz-3" }
  ]
}
```

- `style: "tile"` gives the tile its card chrome (it adds padding/margin — account for it if you also set flex `gap`).
- **Stack-level `padding` = the tile's outer white frame.** The `stack` itself accepts a top-level `padding` (same discrete scale as content items — see §"Content-item `padding`"). It defaults to the `style: "tile"` chrome; setting **`"padding": 0` on the stack** collapses that frame so the tile renders **edge-to-edge / borderless** — the right way to make a full-bleed gradient banner or KPI strip. This is distinct from the content-item `padding` on the *children*. It is also **the** way to drop a tile's white border: the bi-app `hideBorder` tile-setting is **not** part of the v2 documents schema (a `settings.hideBorder` patch is silently stripped on write), so zeroing the stack `padding` is the only programmatic path. Apply it per-stack — don't blanket every tile unless you actually want the whole dashboard frameless.
- The `{ "as": "metadata", "format": "name" }` child is the tile **title**. It renders the raw `queryPresentation.name` — **it is not mustache-templated** (a token there prints literally). Drop this child if you want a dynamic caption (e.g. from a markdown body) to stand alone.
- The `{ "as": "chart" }` child renders the visualization.

### Text tile (`inline-text`) — markdown/mustache with **no query**

A **dashboard text tile** is **not** a `queryPresentation` — it's a content-item authored **only in `containers`**: a tile `stack` whose single child is an `inline-text` item carrying the markdown inline. There is no `attachedQueryKey` and no `as:"chart"`/`as:"metadata"` child.

```jsonc
{ "containerType": "stack", "style": "tile", "name": "Header",
  "gridPosition": { "x": 0, "y": 0, "w": 24, "h": 6 },
  "instanceKey": "ts-header",
  "children": [
    { "type": "inline-text", "content": "### Sales — {{filters.users.state.summary}}", "preset": "tile-align", "instanceKey": "ti-header" }
  ] }
```

- The mustache body lives in **`content`** (markdown, HTML-escaping off — `<div>`/`<style>` work like a markdown viz tile).
- Because it has **no query**, it gets the **dashboard mustache context**: `filters` keyed by control **`id`** (not `view.field`), a `queries` namespace, **no `result`**. See the context table in [mustache.md](mustache.md).
- **Don't** try to make a text tile as a no-query *markdown queryPresentation* (`type:"blank"`, or `type:"query"` with the query omitted) — it renders **"This chart is empty."** Markdown `queryPresentation` tiles require a query; the no-query text tile is this `inline-text` content-item instead.

## Grouping tiles into a movable band

To make several tiles move together as one unit, wrap them in a named `stack` that has a single `gridPosition`, and give the **child** tile stacks **no** `gridPosition` (let them flex with `fillSpace`):

```jsonc
{
  "containerType": "stack", "direction": "row", "name": "KPIs",
  "instanceKey": "kpi-group", "gap": 0,
  "gridPosition": { "x": 0, "y": 0, "w": 24, "h": 28 },
  "children": [
    { "containerType": "stack", "style": "tile", "fillSpace": true, "metadata": { "attachedQueryKey": "1" }, "children": [ … ] },
    { "containerType": "stack", "style": "tile", "fillSpace": true, "metadata": { "attachedQueryKey": "2" }, "children": [ … ] }
    /* …more, no per-child gridPosition… */
  ]
}
```

The group occupies one grid slot; its children flex evenly across it and cannot drift apart. In the UI the band selects and drags as one unit. Move the band by changing the group's `gridPosition.y` (and shifting rows below).

## Multi-page dashboards

The top-level `containers` array holds **one `page` container per page** — add another `{ "containerType": "page", … }` entry to add a page. Each page owns its own grid (or stack) of tile stacks.

```jsonc
"containers": [
  { "instanceKey": "filter-bar", "containerType": "stack", "direction": "row", "children": [
      /* filters / controls — shown on every page */
  ]},
  { "containerType": "page", "instanceKey": "page-1", "name": "Page 1",
    "container": { "containerType": "grid", "instanceKey": "page-1-grid", "children": [
      /* page switcher as the first, full-width child (see "The page switcher") */
      /* …tile stacks… */
    ] } },
  { "containerType": "page", "instanceKey": "page-2", "name": "Page 2",
    "container": { "containerType": "grid", "instanceKey": "page-2-grid", "children": [ /* switcher + tile stacks */ ] } }
]
```

- A page is `{ containerType: "page", instanceKey, name, container: <grid|stack> }`. Optional: `description`, `breakpoint`, `media: "screen" | "print"`.
- **`queryPresentations` are page-agnostic** — a flat pool keyed by tile key. The *containers* decide which page shows each tile. A tile renders on whichever page's grid holds its tile stack, and a given tile stack lives on exactly **one** page. Move a tile between pages by moving its stack between page grids' `children`.
- **Breakpoint / print variants**: a page's `container` may be a `reference` to another page's grid, so desktop / mobile / print variants can share one layout (`media: "print"` + `breakpoint` drive PDF/print rendering).

### The page switcher

Navigate between pages with an `inline-page-switcher`. **Let the `appearance` you want drive where you place it:**

| Appearance | Feels like | Place it |
|---|---|---|
| `tabs` | page tabs / a section divider | **Page grid root** (default) |
| `buttons`, `dropdown`, `list` | a filter/control | **Filter Bar** |

Default to **tabs at the page grid root** unless the user explicitly asks for it in the Filter Bar. Buttons and dropdowns read as filter-like, so the Filter Bar is the natural home for those.

- **Tabs as a divider below the global filters (default):** put it at the **page grid root** — a direct child of a page's `grid`, full-width, at `y:0`. It renders as a full-width tab row at the top of the page body, directly under the Filter Bar. The renderer treats it as full-width (`w:24`) with a short height and snaps it to the tile grid via `preset: "tile-align"`:

  ```jsonc
  // first child of page-N-grid.children, with the page's tiles shifted down below it
  { "type": "inline-page-switcher", "instanceKey": "page-N-switcher",
    "preset": "tile-align", "appearance": { "as": "tabs", "variant": "underline" },
    "gridPosition": { "x": 0, "y": 0, "w": 24, "h": 7 } }
  ```

  **This is per-page** — add it to *each* page's grid, or that page has no way to navigate away. Give each a unique `instanceKey`.

- **Buttons / dropdown in the Filter Bar:** a `buttons`- or `dropdown`-style switcher reads as another control, so add it as a content-item in the `"filter-bar"` stack alongside the filters. (A `tabs` switcher placed here renders *inline* among the filters — no "below the filters" divider — which is why tabs belong at the page grid root.)

Options & appearance:
- **Options auto-derive from the document's pages** when `options` is omitted — each page becomes a tab labelled by its `name`.
- `appearance.as`: `"tabs"` (`variant: underline | bordered`), `"buttons"` (`segment | toggle | pills`), `"list"`, or `"dropdown"`.
- To customise, supply `options: [{ "label": "…", "value": "<page instanceKey>", "id": "…" }]`. An option may instead link an external `uri` (with `target`), and `includeControls: true` carries the current filters/controls into the link. A custom `label` can embed `{{page.<instanceKey>.name}}` so it tracks page renames.

> A second `page` is accepted in the top-level array; the switcher's tabs auto-populate from page names; a tile on page 2's grid renders only there. Placing the switcher at a page grid root yields the full-width divider below the Filter Bar; the renderer rewrites it to `w:24` + `preset: "tile-align"`. Because `containers` is a **full replacement**, send the whole array with edits applied; `queryPresentations` stays a diff (add the tile under `data`, include its key in `order`).

## The Filter Bar

The conventional "shown on every page" header is the **Filter Bar** — a top-level `stack` with the **reserved** `instanceKey: "filter-bar"`. This key is what makes *it* the global top bar, **not** its position:

- Only the stack keyed `"filter-bar"` renders as the global *top* header. A *second top-level* stack with any other key is **dropped**.
- Within the filter-bar stack, keep `filter` / `control` content-items as **direct** children (nesting them in a sub-stack inside the filter-bar makes them disappear).

**But the filter-bar is not the only place filters/controls can live.** `filter` and `control` content-items render in **whatever container holds them** — a page grid cell, a nested grid, etc. (anything *not* placed in any container falls into the HIDDEN CONTROLS tray). So you can build a **full-height left sidebar** by putting a **nested grid** in a page grid cell (e.g. `gridPosition {x:0, w:3, h:<full page height>}`) and stacking the date filter, a timeframe control, and the `inline-page-switcher` (list) inside it — then reflow the page content into the remaining columns. This is fully live (the filters drive the data), and the reserved `"filter-bar"` stack can be left empty. Note such filters are placed **per page**, so duplicate the sidebar onto each page; their *effect* is still global (placement is only visual), but the UI to change them only appears where the content-item is.

## Control placement (filters vs interactive controls)

Controls live in `controls.data` (see [controls.md](controls.md)) but only **render** when added as content-items to a container — most often the Filter Bar stack. **The content-item type differs by kind:**

| Kind | Content-item |
|---|---|
| Date / string / number / boolean **filter** | `{ "type": "filter", "id": "<controlId>", "instanceKey": "…" }` |
| Interactive **control** (FIELD_SELECTION field/timeframe switcher) | `{ "type": "control", "id": "<controlId>", "instanceKey": "…" }` |
| **Page switcher** (navigates pages) | `{ "type": "inline-page-switcher", "instanceKey": "…", "appearance": {…} }` |
| **Inline text** (static label/heading) | `{ "type": "inline-text", "instanceKey": "…", … }` |

Using the wrong type renders an "Item missing" placeholder. A control that is in `controls.data` but in no container falls into the **HIDDEN CONTROLS** tray. (`filter`, `control`, `chart`, `result`, and `metadata` are *placed* content items that reference a query/control by `id`; `inline-text` and `inline-page-switcher` are *inline* items that carry their own content.)

### In-tile controls

To place a switcher inside a specific tile (e.g. a per-KPI metric picker), add the control content-item to **that tile stack's `children`**, after the chart:

```jsonc
"children": [
  { "as": "chart", "id": "2", "type": "query", "instanceKey": "tile-viz-2" },
  { "type": "control", "id": "kpi_metric_2", "instanceKey": "kpi_metric_2-switcher" }
]
```

To **hide** an in-tile switcher (e.g. once a [parent control](controls.md#parent-controls-one-control-drives-many) drives it and you only want the parent visible), remove its content-item from the tile stack **and** set `config.hidden: true` on the control — a control left unplaced but un-hidden gets auto-placed back into the filter bar. The hidden control still feeds the card via `{{controls.<id>.summary}}`. See [controls.md](controls.md#hiding-a-control).

> **`PERIOD_OVER_PERIOD` is auto-placed — don't author a content-item for it.** A PoP content-item in a tile stack renders as "Item missing," and so does a **manual filter-bar child**: Omni already auto-renders the "Compare to" widget next to the date filter in the control's `filterId`, so a hand-placed copy duplicates it → "Item missing." Just add the control to `controls.data`/`order` (no `containers` entry); the tile's comparison columns come from the query's `period_over_period_computations`. See [controls.md](controls.md).

## Content-item `padding` (and the switcher-alignment trick)

Any content-item (`chart`, `control`, `filter`, `inline-page-switcher`, `metadata`, …) accepts an optional **`padding`** tuple. It is **CSS-shorthand order** and uses a **discrete size scale**, not pixels — neither is surfaced in the docs or UI (you only see valid values in a validation tooltip after entering a bad one), so it's worth stating:

- **Order** (4 values): `[top, right, bottom, left]`. Shorthand forms mirror CSS:
  - `2` or `[2]` → all four sides
  - `[v, h]` → vertical, horizontal
  - `[t, h, b]` → top, horizontal, bottom
  - `[t, r, b, l]` → top, right, bottom, left
- **Valid sizes:** `0, 0.5, 1, 2, 3, 4, 5, 6, 7, 8` (the `paddingSizes` scale) — anything else is rejected.

**Filter-bar alignment note:** the filter row lays items out **bottom-aligned** (`align: flex-end`), and the content-item `style` exposes only sizing (`height`/`minHeight`/`width`), no `alignSelf`. A label-less item like the `inline-page-switcher` can read as floating high next to the labeled filters. Two things matter:
- **Variant:** the page-switcher `buttons` appearance defaults to `variant: "segment"`, whose track box has inner `padding` and shrinks the buttons to `--size7` inside a `--size8` box — so the buttons sit inset and look slightly off. Prefer **`variant: "toggle"`**: full `--size8` buttons, no inset, and it visually matches the Day/Week/Month timeframe control. This is the real fix.
- **Padding fine-tune:** the page-switcher renders as a `ButtonToggle`, which can still sit a hair off from the date-filter dropdown (different control components, even at the same nominal height). Concrete values that line it up (empirical): the **`toggle`** variant → a uniform **`"padding": 2`** (a single scalar = all four sides); the **`segment`** variant → bottom-only **`"padding": [0, 0, 2, 0]`**. Either way, prefer adding **bottom** (or uniform) padding, *not* top-only — top padding grows a bottom-aligned item upward and makes it worse.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Only one tile shows after `v2-create` | Auto-layout placed only the seed tile | Author the full `containers` tree |
| A tile is missing | No container references its `attachedQueryKey` | Add a tile stack for it |
| Tiles render at half width | Sized for a 12-col grid | Grid is 24 cols — double the `w` (full = 24) |
| Control sits in "HIDDEN CONTROLS" | Not added as a content-item | Add `{type:filter|control}` to the filter bar (or a tile) |
| "Item missing" placeholder | Wrong content-item type | Filter → `type:filter`; switcher → `type:control` |
| Rows overlap after a height change | Increased a row's `h`/`y` without shifting rows below | Shift every lower row's `y` by the same delta |
| Can't navigate away from a page | Page switcher only on some pages' grids | Add an `inline-page-switcher` to **every** page's grid (unique `instanceKey` each) |
| Page tabs render inline with filters, not below | Switcher placed in the `"filter-bar"` stack | Place it at the page grid root (`w:24`, `y:0`) instead |
| Second top-level stack doesn't render | Only the reserved `"filter-bar"` stack is the global bar | Put global filters/controls in the `"filter-bar"` stack; don't add sibling stacks |

## See also

- [documents-v2.md](documents-v2.md) — the v2 envelope and tile shape
- [controls.md](controls.md) — control configs and mustache tokens

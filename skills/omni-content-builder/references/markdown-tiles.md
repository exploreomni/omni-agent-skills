# Markdown Tile Recipes

Patterns for **markdown viz tiles** (`chartType: "markdown"`, `visType: "omni-markdown"`) — the two documented data components (`<Sparkline>`/`<ChangeArrow>` — see *Native data components* below), sizing, responsive fonts, control-driven KPIs, and data-driven shapes no native chart type gives you. (For a progress gauge / comparison delta, configure a **KPI vis** instead — [visConfig.md](visConfig.md) → *Config Object: KPI* — not a markdown tile.) For the markdown tile's **config shape** (and the `automaticVis:false`/`prefersChart:false` blank-tile trap) see [visConfig.md](visConfig.md) → *Text & AI tiles*; for the mustache token namespaces and contexts see [mustache.md](mustache.md); for a *dashboard text tile* (no query) see [containers.md](containers.md).

> **Recipe source for advanced markdown vizzes — [docs.omni.co/showcase](https://docs.omni.co/showcase).** Working CSS/mustache for things no native chart type gives you: **symmetric funnel** (clip-path trapezoids + step-conversion labels — more informative than the built-in echarts funnel), **conditional-color KPI** (CASE calc → class name → `<style>`), **table with tiny inline bars**, **gauges/thermometer**, **dumbbell plot**, **waffle/square-fill** charts. For a "stages as rows" viz (funnel, tiny-bar table) shape the query with `transposed_measures` (see `omni-query`) so stages become `measure_value` rows, or compute step ratios as their own measures and read them via `result._first`.

## Native data components — `<Sparkline>` and `<ChangeArrow>`

Omni's markdown renderer ships two **publicly documented** data components that draw inline visualizations from the tile's query results — **prefer them over hand-rolled equivalents.** A KPI "big number + sparkline + up/down delta" card needs **no table calculations and no CSS `<div>` bar tricks**: `<Sparkline>` draws the trend and `<ChangeArrow>` computes and colors the delta. (A `spark_h = metric/MAX(metric)` calc in a `{{#result}}` loop, or a `mom_pct`/`mom_dir` CASE-class arrow, just re-implements these — more fragily.)

Public reference: [docs.omni.co → Markdown § Adding visual components](https://docs.omni.co/visualize-present/visualizations/types/markdown#adding-visual-components).

> **Three more tags — `comparison`, `single-value`, `progress` — are the building blocks the native KPI viz (`visType: "omni-kpi"`) compiles its config sections into. They render in plain markdown tiles too, with varying robustness:**
> - **`<comparison>` is hand-authorable and genuinely useful — prefer it when you want the arrow PLUS the change *value*.** Unlike `<changearrow>` (icon/pill only), `<comparison>` **computes the percent change itself** from `current`/`comparison` and shows it — so you do **not** need an `OMNI_PERCENT_CHANGE_FROM_PREVIOUS` table calc. Verified-rendering attributes (all kebab): `current`, `comparison`, `comparison-type` (`percent`/`number`/`number_percent`), `decimals`, `swap-colors`, `color-positive`, `color-negative`, `label`. Example — green-on-decrease, auto-computed: `<comparison current="{{result._last.v.metric.raw}}" comparison="{{result._second_to_last.v.metric.raw}}" comparison-type="percent" decimals="1" swap-colors="true"></comparison>` → renders `↓ -1.0%` (green). Pair it with a `color_class` `<style>` on the *value* and you have the full status card with **no change-calc at all**. **Layout:** it renders as a block `<div class="kpi-comparison">`, so adjacent text wraps to the next line — to keep it inline (e.g. `↗ 0.1% vs 14.55% prior mo` on one line), add `.kpi-comparison{display:inline-flex;width:auto}` to a scoped `<style>` (the class otherwise grabs full width).
> - **`<progress>` IS fragile — it throws on an undefined value, which fails the whole export** (see the catch-22 below). For a gauge, prefer the native KPI `progress` section or a plain CSS `<div>` bar driven by a 0–100 calc.
> - `<single-value>` is the number+label block; rarely worth hand-authoring (a styled `<div>` is simpler).
>
> Separately, the renderer also exposes **`<iframe>`** — which **is** documented and supported in markdown tiles (sandboxed; parameterizable with query tokens) — and the embed-oriented **`<omni-drill>`** (make wrapped content drillable) and **`<omni-message>`** (emit embed `postMessage` events). Those are legitimate for their own purposes; they're just not part of the KPI-card pattern here.

### `<Sparkline>` — trend micro-chart

Draws one mark per **result row**, reading that row's `<field>.raw`. Needs **>1 row**.

```html
<Sparkline field="orders.total_revenue" color="#10B981" type="line" width="100" height="32"></Sparkline>
```

| Attr | Value | Notes |
|---|---|---|
| `field` | `view.field` (or a **selected** calc name) | **The field MUST be a column in the tile's `query.fields`.** Point it at a missing/unselected/misspelled field and it silently renders a **flat zero line** (no error). |
| `color` | CSS color | Default is a magenta `#ff4794` — always set it. |
| `type` | `line` (default) or `bar` | (An `area` type and a `show-axis` toggle also render but aren't in the public docs — they're KPI-config options.) |
| `width` / `height` | **fixed integer pixels — NOT responsive** | A fixed-size recharts chart (defaults `width: 200`, `height: 100`) with **no `ResponsiveContainer`**: it does **not** stretch to the card, and a `%` is `parseInt`-stripped to px (`width="100%"` → **100px**, not full width). There is **no auto-fill option** — to make it span a tile you must hard-code a large px width (e.g. `width="1400"` fills a full-width tile), but that's **brittle**: it only suits one tile size/viewport and clips (or under-fills) on resize/reflow (the wrapper is `overflow:hidden`). Two sparklines of the same data at different widths look different (wider = flatter), so **match `width`/`height` across tiles you compare**. (A responsive sparkline that honors `%`/fills its container is not available today — it's a genuine gap, not a config you're missing.) |
| `reverse` | `true` | Reverses row order — set it when the query is sorted **descending** but you want the sparkline chronological. **This is the default situation inside a native `omni-kpi` sparkline section:** that tile's query *must* sort descending (so `_first` = latest for the number/comparison sections), so the sparkline draws latest→oldest (mirror-imaged / "backwards trend") unless you set `reverse: true`. |

### `<ChangeArrow>` — delta indicator (no calc needed)

Computes the percent change itself (`current / comparison − 1`) and picks the arrow + color. **You do not need a `mom_pct` or direction calc** — pass the latest and prior values straight from `result`.

```html
<ChangeArrow current="{{result._last.orders.total_revenue.value_static}}"
             comparison="{{result._second_to_last.orders.total_revenue.value_static}}"></ChangeArrow>
```

- **`current` / `comparison`** — value tokens (`.value_static` or `.raw`); pass the latest as `current`, the prior as `comparison`. The public docs example uses `result.0` / `result.1`; for "latest vs prior period" use `result._last` / `result._second_to_last`.
- Behavior: `current > comparison` → up; equal → no arrow; a cross-zero comparison → `N/A`.
- **"Lower is better" (green on a *decrease*) IS available in markdown — via `swap-colors="true"`.** Full attribute set: `current`, `comparison`, `swap-colors`, `color-positive`, `color-negative`, `comparison-type`, `decimals`.
- **`<changearrow>` draws only the arrow + colored pill — NOT the numeric delta** (it has no `show-comparison-value`). **To show the % change too, use `<comparison>` instead** (see the KPI-blocks note above) — it computes the percent from `current`/`comparison` itself and renders the arrow + value, with `swap-colors`/`color-*`/`decimals`. **No table calc.** (A manual `OMNI_PERCENT_CHANGE_FROM_PREVIOUS` calc + `{{…value_static}}` token is only worth it if you need a *fully custom* layout `<comparison>` can't express — don't reach for it by default.)

> ## ⚠️ Data-component attributes are **kebab-case** — a camelCase attribute is silently dropped
>
> The markdown sanitizer passes each data component a **fixed, kebab-case attribute allowlist**; any attribute *not* on it (including the camelCase spelling of one that is) is **stripped before the component sees it** — no error, it just no-ops. This is the single biggest gotcha with these tags, and it's silent.
>
> - `swap-colors` ✅ — `swapColors` ❌ (stripped → arrow never swaps; you'll swear `swapColors` "doesn't work")
> - `color-negative` / `color-positive` / `comparison-type` ✅ — `colorNegative` / `colorPositive` / `comparisonType` ❌
> - `<Sparkline>`: `show-axis` ✅ — `showAxis` ❌
> - `<comparison>` (and `<single-value>`/`<progress>`): `description-before` / `description-after` ✅ — `descriptionBefore` / `descriptionAfter` ❌
>
> Tag names are case-insensitive (`<ChangeArrow>` = `<changearrow>`); **attribute names are not** — always kebab-case. (You can't tell from `query run` — a stripped attribute is a *render* behaviour; verify in the UI or a dashboard PNG.) This is why a swapped delta "didn't work" with `swapColors` but works with `swap-colors`.

### Worked KPI card (label + value + delta + sparkline)

```html
<div style="container-type:inline-size;height:100%;display:flex;flex-direction:column;justify-content:center;gap:3px">
  <div style="font-size:13px;letter-spacing:.05em;color:#4B5563;font-weight:700">REVENUE</div>
  <div style="font-size:clamp(16px,15cqw,40px);font-weight:800;color:#111827;line-height:1;white-space:nowrap">{{result._last.orders.total_revenue.value_static}}</div>
  <div style="font-size:12px;color:#6B7280"><ChangeArrow current="{{result._last.orders.total_revenue.value_static}}" comparison="{{result._second_to_last.orders.total_revenue.value_static}}"></ChangeArrow> vs prior mo · {{filters.orders.created_at.summary}}</div>
  <Sparkline field="orders.total_revenue" color="#10B981" type="line" width="160" height="32"></Sparkline>
</div>
```

The query is just `[orders.created_at[month], orders.total_revenue]` sorted ascending — **no `calculations` at all**. The `<Sparkline>` reads every month's `total_revenue.raw`; `<ChangeArrow>` diffs the last two months.

### Lower-is-better arrow (green on a *decrease*) — without `<ChangeArrow>`

**The simple path is `<ChangeArrow … swap-colors="true">`** (kebab — see the attribute gotcha above): that alone gives green-on-decrease, optionally paired with a `color_class` `<style>` on the *value* (arrow = *direction*, value = *level*). So you usually **don't** need a calc. Reach for the direction calc below only for a **fully custom glyph** `<ChangeArrow>` can't render — it keeps the threshold-coloured value too:

```jsonc
// query.calculations[] (calc_name also in query.fields AND visConfig.fields):
{ "calc_name": "arrow_class",
  "sql_expression": { "type":"call","operator":"SqlStdOperatorTable.CASE","operands":[
    { "type":"call","operator":"SqlStdOperatorTable.LESS_THAN","operands":[
      { "type":"call","operator":"Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS",
        "operands":[ { "type":"field","field_name":"sessions.cart_abandonment_rate","for_calc":true } ] },
      { "type":"literal","value":0,"string_value":"0" } ] },
    { "type":"literal","value":"dn","string_value":"dn" },     // decreased → good
    { "type":"literal","value":"up","string_value":"up" } ] }  // increased → bad
}
```

```html
<style>.dn{color:#059669;font-weight:700}.dn::before{content:"\2193 "}.up{color:#DC2626;font-weight:700}.up::before{content:"\2191 "}
.bad{color:#DC2626}.warn{color:#D97706}.good{color:#111827}</style>
<div class="{{result._last.color_class.raw}}" style="font-size:clamp(16px,15cqw,38px);font-weight:800;line-height:1">{{result._last.sessions.cart_abandonment_rate.value_static}}</div>
<div style="font-size:12px;color:#6B7280"><span class="{{result._last.arrow_class.raw}}"></span>vs prior mo</div>
```

A separate `color_class` calc recolours the *value* by threshold (*level*) while `arrow_class` colours the glyph by *direction*; the CSS `::before` supplies the ↓/↑ glyph so the span body stays empty. Query sorted **ascending** so `_last` = latest and `OMNI_PERCENT_CHANGE_FROM_PREVIOUS` compares it to the prior month.

> **These are still markdown-viz tiles**, so the blank-tile and round-trip rules elsewhere in this file apply: keep `automaticVis:false` + `prefersChart:false`, and re-author the inner spec nested under `config` on write. The components render in normal dashboard markdown tiles (not only AI-summary tiles). As always, **you cannot confirm the render from `query run`** — download a dashboard PNG (`omni dashboards download` → `download-status` → `download-file`) or check in the UI.

> **The export catch-22 — one throwing tile fails the WHOLE dashboard render.** A markdown tile that throws at render (an undefined value handed to a component, a bad token) shows "Chart unavailable" *and* fails the PNG/PDF export with the generic `"Job failed to render."`. Two consequences: (1) a render-job failure is **not** automatically a service outage — it's often a single bad tile; confirm by exporting a known-good dashboard. (2) Verify an **unfamiliar component** as a **one-tile** dashboard export first, so a crash is isolated. Fetch the image with `omni dashboards download-file <id> <jobId>`.

## Sizing markdown tiles (heights) — they clip easily

Markdown/text tiles clip far more readily than chart tiles. What actually governs it:

- **Grid `h` is ~4–5px per unit.** Empirical reference points for a markdown tile with the default `style: "tile"` chrome: a **single line of text ≈ h:7–8**, **two lines ≈ h:11**, a **28–32px KPI value ≈ h:16–18**.
- **`style: "tile"` eats ~16px** of vertical space (`--tile-margin` padding on every side). The usable content height ≈ tile height − that chrome, so small tiles clip even when the text "should" fit — **budget +3–4 h-units over the bare text height**.
- **Keep the markdown tight.** A `<style>` block followed by **blank lines** renders as empty paragraphs at the *top* of the tile, pushing the visible content down so it looks bottom-anchored or clipped. Put `<style>` and the content on adjacent lines with no blank lines between blocks.
- **Vertical-center only when there's room.** `<div style="height:100%; display:flex; align-items:center; justify-content:center">` centers cleanly — but only once the tile clears chrome + content. At minimal heights it still clips; there, use natural top-flow with small padding instead.
- **When a tile clips, add height, not padding.** The content area is simply smaller than what's rendering; +2–3 h-units fixes it where padding tweaks won't.

## Responsive KPI headline numbers — scale font to the *card*, not the viewport

A markdown KPI with a fixed `font-size:40px` headline number **clips horizontally** when the tile narrows (long currency like `$187,727.51` overflows and is cut off; the value just *disappears* off the right edge — no ellipsis, no error). Fix it with a **CSS container query** so the number scales to its own card width:

- Wrap the card body in a container: `<div style="container-type:inline-size;height:100%">…</div>`.
- Size the number in `cqw` (1cqw = 1% of the container's width) with a `clamp()` floor/cap: `font-size:clamp(16px,15cqw,40px);…;white-space:nowrap`. `15cqw` ≈ 25px in a ~165px six-across card (fits a 10-char value), grows to the 40px cap on wide/full-width cards, and shrinks gracefully when cards reflow.
- **Omni's markdown renderer supports container queries** — inline `container-type` and the `cqw` unit both pass the sanitizer and render. (`<style>` blocks work too.) Prefer `cqw` over `vw`: `vw` tracks the *viewport*, so when cards reflow to full-width at narrow widths the number turns tiny in a wide card; `cqw` tracks the card and stays correctly sized at every breakpoint.
- Anchor the edit on `font-weight:800` — in these KPI cards only the headline number is weight 800 (labels are 700), so it uniquely identifies the value line across all the size variants (36/38/40px, colored or class-driven).
- **This is a markdown-tile edit, so it is subject to the round-trip trap** (see [visConfig.md](visConfig.md)) — re-author the inner spec as `visConfig.visConfig = { visType:"omni-markdown", config:{ version:1, markdown:"…" } }`. Sending the GET's *flat* `{version,markdown,visType}` back silently drops `markdown` and the tile renders blank — a blank tile here is the flat shape, not the `cqw`.

## A markdown KPI card that follows a metric picker

A markdown tile can present a styled KPI whose value **and** label track a `FIELD_SELECTION` switcher — without a table calc. The trick is a **multi-measure query + a CSS attribute-selector switch**:

1. Query returns **all** candidate measures as columns (one `limit 1` row).
2. Render one hidden `<span data-m="<Label>">` per measure, each reading `{{result._first.<view>.<field>.value_static}}`.
3. Put the control's selection on a wrapper via `data-sel="{{controls.<id>.summary}}"`, and add one CSS rule per metric that reveals the matching span.

```html
<style>
.kpival .m{display:none;font-size:32px;font-weight:700;}
.kpicard[data-sel="Total Revenue"] .m[data-m="Total Revenue"],
.kpicard[data-sel="Total Margin"]  .m[data-m="Total Margin"]{display:block;}
</style>
<div class="kpicard" data-sel="{{controls.kpi_metric_1.summary}}">
  <div class="kpilabel">{{controls.kpi_metric_1.summary}}</div>
  <div class="kpival">
    <span class="m" data-m="Total Revenue">{{result._first.ecomm__order_items.total_revenue.value_static}}</span>
    <span class="m" data-m="Total Margin">{{result._first.ecomm__order_items.total_margin.value_static}}</span>
  </div>
</div>
```

The control's option **labels must match** the `data-m`/`data-sel` strings (`.summary` returns the label). This switches in the presentation layer — the control never mutates the query — so it sidesteps the interactive-control scoping limitation. Place the switcher in-tile (see [containers.md](containers.md)).

> **Why a table calc can't do this.** A table calc — including a cell reference like `=A1` — binds to a **field name at author time** (stored as `{type:'field', field_name:…}`). A field picker swaps *which field* is in the query, so the calc keeps pointing at the original field and does not follow the switch. Use the CSS pattern above (or a templated-filter + CASE measure) instead.

## Data-driven funnel (proportional widths, no table calc)

Segment widths track the data, so the taper *is* the conversion:

1. **Wide query, one row** — the stage measures as columns (`units_sold`, `shipped_items`, …); NO `transposed_measures`, NO `calculations`. (Transposing or using calcs breaks the token reads — see [mustache.md](mustache.md).)
2. **One full-width div per stage**, stacked in a `height:100%` flex column with `flex:1` segments (fills the tile).
3. **Shape each segment with `clip-path` whose coordinates are CSS `calc()` over raw measure tokens** — top width = this stage ÷ max, bottom width = next stage ÷ max, so consecutive segments meet on one continuous diagonal:
   `clip-path: polygon(calc(50% - {{result._first.v.stageN.raw}} / {{result._first.v.max.raw}} * 50%) 0, calc(50% + …) 0, calc(50% + {{…stageN1.raw}} / {{…max.raw}} * 50%) 100%, calc(50% - …) 100%)`
   `max` = the first/largest measure. Subtraction works too (terminal "Not Returned" = `( {{…delivered.raw}} - {{…returned.raw}} )`). Last stage: bottom = top (flat) for a clean base.
4. **Labels/values** = `{{result._first.v.stageN.value_static}}` (these resolve; calcs don't).
   The **conversion-% *text* between stages is NOT feasible** (it needs a calc → empty) — but the proportional widths already encode it. Make the terminal the **success** case, not a drop-out.
5. **Terminal stage = a real measure, never CSS subtraction.** For "kept/net" terminals (e.g. "Not Returned"), add a model measure (`count` filtered `is_delivered:true` + `is_returned:false`) and read it like any field — a CSS `calc(delivered - returned)` can go **negative** when events lag the period (returns from earlier deliveries) and "negative not-returned" is nonsense. A filtered count is always ≥ 0.
6. **White-gap + delta-colored arrow between stages.** Between segments put a small white `.gap` div holding a down-arrow (`&#8595;`, ~26px bold). Color it by the step's retention with **`hsl(clamp(…))` over raw tokens** — no calc field: `color: hsl(clamp(0, ( {{…next.raw}} / {{…this.raw}} - 0.5 ) / 0.5 * 120, 120), 75%, 42%)` maps retention 50%→100% across red→green (stretch the floor to taste; funnels retain a lot, so a 0-floor leaves everything green). `hsl(clamp(calc…))` evaluates in the markdown renderer.

**Discover the context with `{{inspect}}`** as the **bare** markdown body (not wrapped — see [mustache.md](mustache.md)).

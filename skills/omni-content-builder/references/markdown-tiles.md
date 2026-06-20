# Markdown Tile Recipes

Patterns for **markdown viz tiles** (`chartType: "markdown"`, `visType: "omni-markdown"`) — sizing, responsive fonts, control-driven KPIs, and data-driven shapes no native chart type gives you. For the markdown tile's **config shape** (and the `automaticVis:false`/`prefersChart:false` blank-tile trap) see [visConfig.md](visConfig.md) → *Text & AI tiles*; for the mustache token namespaces and contexts see [mustache.md](mustache.md); for a *dashboard text tile* (no query) see [containers.md](containers.md).

> **Recipe source for advanced markdown vizzes — [docs.omni.co/showcase](https://docs.omni.co/showcase).** Working CSS/mustache for things no native chart type gives you: **symmetric funnel** (clip-path trapezoids + step-conversion labels — more informative than the built-in echarts funnel), **conditional-color KPI** (CASE calc → class name → `<style>`), **table with tiny inline bars**, **gauges/thermometer**, **dumbbell plot**, **waffle/square-fill** charts. For a "stages as rows" viz (funnel, tiny-bar table) shape the query with `transposed_measures` (see `omni-query`) so stages become `measure_value` rows, or compute step ratios as their own measures and read them via `result._first`.

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

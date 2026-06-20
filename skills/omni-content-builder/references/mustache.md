# Mustache in Dashboards Reference

How dashboard text/markdown tiles interpolate `{{...}}` tokens — the namespaces, the **filter‑vs‑control** distinction, the per‑namespace token tables, and worked scenarios. Behaviors here are verified against live dashboards; the authoritative token list is Omni's public [Mustache reference](https://docs.omni.co/visualize-present/mustache-reference).

> **Why this matters:** the most common mistake is reaching for `{{controls.<id>.…}}` to show a **filter's** value. A date/string/number/boolean *filter* lives under the **`filters`** namespace, not `controls` — it's configured as a control but isn't addressable in that namespace. And its `filters` key depends on the **tile kind**: `view.field` in a markdown **viz** tile, the control **`id`** in a dashboard **text** tile (see the keying gotcha). Using the wrong namespace *or* the wrong key form for the tile fails **silently** (the token renders empty), so it looks like a rendering bug.

## Table of Contents

- [The engine](#the-engine)
- [Two contexts — *where* decides what you get](#two-contexts--where-decides-what-you-get)
- [control vs filter — the decision](#control-vs-filter--the-decision)
- [The keying gotcha (`view.field` vs `id`)](#the-keying-gotcha-viewfield-vs-id)
- [Token reference by namespace](#token-reference-by-namespace)
- [Scenarios](#scenarios)
- [Pitfalls](#pitfalls)

## The engine

Interpolation uses the standard Mustache templating library with HTML‑escaping **turned off**, which is why inline `<div style="…">` and scoped `<style>` render inside a markdown body. Tokens are plain dotted‑path lookups into a per‑tile **context object** — there is no custom token DSL, and a path that doesn't resolve yields an empty string rather than an error (so mistakes are silent).

## Two contexts — *where* decides what you get

The available namespaces **and how `filters` is keyed** differ by **tile kind**:

| Tile kind | `filters` source → **keyed by** | Namespaces |
|---|---|---|
| **Markdown *visualization* tile** (`chartType:"markdown"`, has a `query`) | this tile's **`query.filters`** → **`view.field`** (same-field collapsed to OR) | `result`, `fields`, `filters`, `controls`, `metadata`, `inspect` |
| **Dashboard *text* tile** (an `inline-text` content-item, **no query**) | the **raw dashboard filter controls** → control **`id`** (same-field kept separate) | `filters`, `controls`, `queries` (all tiles' presentations), `metadata`, `inspect` — **no `result`** |
| **Viz axis labels / field display** (chart/axis title strings) | `query.filters` → **`view.field`** | `fields`, `filters`, `controls` — **no `result`, no `queries`** |
| KPI / chart / table / pivot **tile bodies** | — | **not** mustache‑templated (only their axis labels are, per the row above). For a dynamic number *and* caption, use a **markdown viz tile**, not a KPI tile. |

Two consequences worth internalizing:
- In a **markdown viz tile**, `filters` resolves against **that tile's own `query.filters`** keyed by `view.field` — so `{{filters.ecomm__order_items.created_at.summary}}` renders **per‑tile**, which is what makes one token work across many cards that each have their own date control.
- In a **dashboard text tile**, `filters` is the **raw dashboard controls keyed by `id`** — so you reference `{{filters.my_date_filter.summary}}`, you can address **two filters on the same field separately**, and there's a `queries` namespace but **no `result`**. (See the keying gotcha below.)

**Authoring a text tile:** it's **not** a `queryPresentation` — it's a content-item in the `containers` tree: a tile `stack` whose child is `{ "type": "inline-text", "content": "<markdown/mustache>", "preset": "tile-align", "instanceKey": "…" }` (no `query`, no `attachedQueryKey`). A no-query markdown *queryPresentation* renders "This chart is empty" — see [containers.md](containers.md).

KPI tile text components (`markdownConfig` of type `"number"`/`"text"`) are markdown‑enabled but **do not** run mustache — see [Pitfalls](#pitfalls).

## control vs filter — the decision

> **Step 0 — read the entry's `type` before you write the token.** The thing you're referencing is in `controls.data` either way, so the key name doesn't tell you the namespace; its **`config.type`** does. Look it up (or run `{{inspect}}`) first:
> - `type` is `date`/`string`/`number`/`boolean`/`null`/`by_query`/`user_attribute`/`composite` → it's a **filter** → `{{filters.<view>.<field>.…}}`
> - `type` is `FIELD_SELECTION`/`FIELD_PICKER`/`TOP_N`/`PARENT`/`MULTI_FIELD_FILTER`/`DYNAMIC_FILTER` → it's an **interactive control** → `{{controls.<id>.…}}`
>
> Skipping this and copying a `controls.<id>` example onto a `type:"date"` filter is the #1 cause of a silently‑empty token.

Both kinds live in `controls.data`; the `config.type` only decides which **namespace** exposes them to mustache:
- **Filter-type** — `date`, `string`, `number`, `boolean`, `null`, `by_query`, `user_attribute`, `composite`. → **`{{filters.<view>.<field>.…}}`**
- **Interactive-control-type** — `FIELD_SELECTION` (field **and** timeframe switchers), `FIELD_PICKER`, `TOP_N`, `PARENT`, `MULTI_FIELD_FILTER`, `DYNAMIC_FILTER`. → **`{{controls.<id>.…}}`**
- `PERIOD_OVER_PERIOD` (the "Compare to" control) is **visible in the filter bar but unreachable from mustache.** Even though it renders as a control, it never appears in the `controls` template context **in either tile context** (viz *or* text) — *every* `{{controls.<pop_id>.…}}` form (`.summary`, `.value`, `.label`, even `.json`) comes back empty, and it isn't under `filters` either. There is no token for the comparison period; the prior-period columns come from the tile query's `period_over_period_computations` instead (see [queryPresentations.md](queryPresentations.md)). Confirm with `{{inspect}}` — there is no `pop` key under `controls`.

> "Filter" vs "control" here is about the **mustache namespace, not ontology** — both kinds are entries in the same `controls.data` slice and both render as filter-bar widgets. A `type:"date"` filter is still routed to **`filters`** (keyed by `view.field` in a viz tile, by control `id` in a text tile — see the keying gotcha below), while an interactive control is routed to **`controls`** (keyed by id). So reference a date filter under `filters`, not `controls` — even though it *is* a control entry in the document.

## The keying gotcha — filter keying **flips by tile kind**

**How a filter is keyed in the `filters` namespace depends on the tile kind**, because each kind feeds a *different* filter object to the template:

- **Markdown viz tile** (has a `query`): `filters` = the tile's **`query.filters`** — the filters as *applied to the query* (after same-field consolidation). Keyed by **`view.field`**, and multiple filters on one field are **merged into one composite-OR** at that key (`.summary` = the combined window, `.value` empty). `{{filters.<controlId>.…}}` is empty here.
- **Dashboard text tile** (`inline-text`, no query): `filters` = the **raw dashboard filter controls**. Keyed by control **`id`**, and same-field filters stay **separate** — each with its own `.summary` *and* `.value`. `{{filters.<view>.<field>.…}}` is empty here.

So the *same* dashboard date filter is addressed two different ways depending on where the token lives:

| | Markdown **viz** tile | Dashboard **text** tile |
|---|---|---|
| reference a filter | `{{filters.ecomm__order_items.created_at.summary}}` (by `view.field`) | `{{filters.my_date_filter.summary}}` (by control **id**) |
| two filters on one field | one OR composite at the field key, `.value` empty | two separate id keys, each its own `.summary` + `.value` |

Controls are keyed by **`id`** in **both** contexts; `PERIOD_OVER_PERIOD` is in **neither** (above). This is current behavior, not a bug — the viz tile reads the consolidated `query.filters`, the text tile reads the unconsolidated dashboard controls.

**Rule of thumb:** viz tile → filters by **`view.field`**; text tile → filters by control **`id`**; controls by `id` everywhere. When unsure, drop `{{inspect}}` into the body and read the exact keys for *that* tile.

## Token reference by namespace

### `{{filters.…}}`
The key is `<view>.<field>` in a **viz** tile and the control **`id`** in a **text** tile (see the keying gotcha); the leaf tokens below are identical either way.

| Token | Resolves to |
|---|---|
| `.summary` | **friendly text** — `"in the past 4 months"`, `"is California"`, `"= 5"`, `"is any value"` |
| `.value` | raw values joined — date interval → `"3 months ago,3 months"`; string → `"California,Oregon"`; boolean → `"true"`; negated → empty |
| `.filter_value_label` | applied label if present, else the raw value |
| `.label` | the field's label |
| `.value_url_encoded` | URL‑encoded `.value` (for links) |
| `.json` | URL‑encoded JSON of the whole filter |

> For a **caption that reads like the filter chip**, use `.summary`. Use `.value` only when you need the raw value (logic, links). Negated filters return empty `.value` by design.

### `{{controls.<id>.X}}`
| Token | Resolves to |
|---|---|
| `.summary` | the selected option's **friendly label** (e.g. `"Total Revenue"`) |
| `.value` | `FIELD_SELECTION` → field name · `TOP_N` → number (string) · `FIELD_PICKER` → array · `PARENT` → value |
| `.label` | the control's title |
| `.value_url_encoded`, `.json` | URL‑encoded value / full control JSON |

### `{{result.…}}` (markdown viz tiles only)
Rows are nested by `[pivot…].view.field`, each leaf carrying:
| Token | Resolves to |
|---|---|
| `.value_static` | **formatted, no interactivity** — the display string (use this for text — `"4.77"`, `"$793,533.63"`) |
| `.value` | **formatted *and* interactive** — a drillable element (renders a component, not a string) |
| `.value_url_encoded` | URL‑encoded formatted value |
| `.raw` | unformatted raw value |

Row accessors: `result._first`, `._second`, `._second_to_last`, `._last`, `._rows` (count), `._totals._first` (column‑totals row), and numeric indices `result.0`, `result.1`. Single‑value aggregate queries → use `result._first`.

> **A measure is keyed by `view.field`; a table calculation is keyed by its bare `calc_name` at the row level — NOT nested under a view.** A model field is `{{result._last.ecomm__order_items.total_revenue.value_static}}`, but a calc named `color_class` is `{{result._last.color_class.raw}}` (not `…ecomm__order_items.color_class…`). Mis-nesting a calc under a view silently yields an empty string. This makes calcs handy for driving CSS: a `CASE`-based calc that outputs a class name (`'good'`/`'warn'`/`'bad'`), read via `{{result._last.<calc_name>.raw}}` into a `class="…"`, gives you a **conditional-color KPI** (threshold-driven number color) with one calc + a `<style>` block.

> **For data-driven markdown geometry, prefer raw MEASURE tokens + CSS `calc()` over table calcs.** A table calc resolves in `result` **only if its `calc_name` is also in `query.fields`** — a calc that's only in `query.calculations` is not selected, so `{{result._first.<calc_name>.raw}}` comes back blank. (That's *why* the color-class calc above works: it's selected.) You can select a calc and read it, but for sizing/geometry it's simpler and more robust to skip calcs: query the raw **measures** (wide, one row — they always resolve, `.value_static` formatted / `.raw` unformatted, including the transposed synthetic `measure_value`) and do the arithmetic in CSS `calc()` on `.raw` tokens — division, subtraction, scaling all evaluate: `width: calc({{result._first.v.stage.raw}} / {{result._first.v.max.raw}} * 100%)`, `calc(( {{…delivered.raw}} - {{…returned.raw}} ) / {{…units.raw}} * 50%)`. (A blank tile from a ratio is usually a malformed *measure* — unquoted `${}`, see `omni-model-builder` topic-scoped-views — not the calc; calcs selected into `fields` render fine.)
> **Empty token ⇒ stripped CSS.** Mustache substitutes *before* the HTML/CSS sanitizer. A token that resolves to empty produces invalid CSS (`width:calc( * 100%)`, `clip-path:polygon(…calc(50% +  * 50%)…)`) and the sanitizer **silently drops that declaration** (a static `clip-path:polygon(0 0,100% 0,72% 100%,28% 100%)` with no token survives — that's the tell). So only inject tokens guaranteed to resolve — i.e. **measures, not calcs**. (`mv.value_static` → `"110,924"`, `mv.raw` → `110924`.)

### `{{metadata.X}}`
`createdAt`, `createdBy`, `lastRanAt`, `lastUpdatedAt`, `lastUpdatedBy`, `refreshInterval`, `theme`, `userAttributes.<attr>.element` (e.g. `{{metadata.userAttributes.omni_user_email.element}}`).

### `{{queries.<tileKey>.…}}` (text tiles only)
The dashboard's other tile presentations, keyed by tile key.

### `{{inspect}}`
Dumps the entire resolved context as a `<pre>` block. The fastest way to discover exact keys for the current tile. The dump confirms the shape: `result._first.<view>.<field>` (measures nested under view), plus `controls`, `filters`, `fields`, `metadata`, `userAttributes`.
> **Use it as the BARE markdown body** — set the whole tile markdown to exactly `{{inspect}}`, nothing else. Wrapping it (`<pre style=…>{{inspect}}</pre>` or any HTML) makes it render **literally** as the text `{{inspect}}` instead of resolving. Omni formats the dump as its own block, so no wrapper is needed.

## Scenarios

Each scenario notes its **tile kind**, because the `filters` keying differs (see the keying gotcha): a markdown **viz** tile (has a `query`; `filters` keyed by `view.field`; has `result`) vs. a dashboard **text** tile (an `inline-text` content-item, no query; `filters` keyed by control `id`; has `queries`, no `result`). Controls are keyed by `id` in both.

### A. Dynamic KPI caption that tracks a per‑tile date control — *markdown viz tile*
A "big number + live window" card. Use a **markdown viz tile** (not a KPI tile): its query supplies the number, its own `query.filters` supplies the window. One in‑tile date filter scoped to this tile drives both.

```jsonc
// queryPresentations.data["2"]
{
  "name": "Total Margin", "type": "query",
  "prefersChart": false, "automaticVis": false,           // both required, or the tile renders blank
  "query": { "table": "ecomm__order_items", "fields": ["ecomm__order_items.total_margin"],
             "filters": {}, "limit": 1000, "join_paths_from_topic_name": "",
             "sorts": [], "calculations": [], "column_totals": {}, "row_totals": {},
             "fill_fields": [], "pivots": [], "userEditedSQL": "" },
  "visConfig": { "chartType": "markdown", "fields": ["ecomm__order_items.total_margin"], "version": 0,
    "visConfig": { "visType": "omni-markdown", "config": { "version": 1, "markdown":
      "<div><div style=\"font-size:12px;color:#6b7280;font-weight:700\">TOTAL MARGIN</div><div style=\"font-size:38px;font-weight:700\">{{result._first.ecomm__order_items.total_margin.value_static}}</div><div style=\"font-size:12px;color:#9ca3af\">{{filters.ecomm__order_items.created_at.summary}}</div></div>"
  } } }
}
```
- Value: `{{result._first.ecomm__order_items.total_margin.value_static}}`
- Window caption: **`{{filters.ecomm__order_items.created_at.summary}}`** (by field — the per‑tile date control's filter lands here). `{{controls.<id>…}}` would be empty.
- **Don't** bake the window into the tile `name`/title — the title child is **not** mustache‑templated (see [containers.md](containers.md)), so a static "Last 3 Months" can't track an adjustable control and will drift.

### B. Dashboard header that reflects the global filters — *dashboard text tile*
A standalone **text tile** (an `inline-text` content-item, no query — see [containers.md](containers.md)). Here `filters` is keyed by **control `id`**, so reference each filter by its control id — **not** `view.field`:
```
### Sales — {{filters.state_filter.summary}}, {{filters.status_filter.summary}}
Viewed by {{metadata.userAttributes.omni_user_email.element}} · refreshed {{metadata.lastRanAt}}
```
> Build the **same** header as a *markdown viz tile* (with a query) instead, and `filters` keys by `view.field` (`{{filters.ecomm__users.state.summary}}`) and you also get `result`. The text tile is simpler for a pure caption — `queries` namespace, no `result`.

### C. Caption that follows a metric/field *switcher* — *either tile kind*
The one case where `controls.*` is correct — a `FIELD_SELECTION` control, keyed by `id` in both contexts:
```
**{{controls.kpi_metric.summary}}**
```
Pair with the CSS metric‑switch pattern in [markdown-tiles.md](markdown-tiles.md) to reveal the matching value span.

### D. Exact filter boundary *dates* (not the friendly summary) — *markdown viz tile*
Viz mustache has no absolute start/end‑date token (`.summary` is friendly text, `.value` is the relative expression). To show real boundary dates, expose them as **model dimensions** via templated‑filter tokens, then read with `result`:
```yaml
# on the filtered view
period_start: { sql: 'DATE({{ filters.ecomm__order_items.created_at.range_start }})', hidden: true }
period_end:   { sql: 'DATE({{ filters.ecomm__order_items.created_at.range_end }})',   hidden: true }
```
Tile query selects `period_start`/`period_end`; body reads `{{result._first.ecomm__order_items.period_start.value_static}}`. (`range_start`/`range_end` are model‑SQL templated‑filter tokens — **not** available in viz mustache.)

### E. Show a value from the result set (single number, last row, total) — *markdown viz tile* (needs `result`)
```
Latest month: {{result._last.order_items.created_at.value_static}} →
{{result._last.order_items.total_revenue.value_static}}
(of {{result._rows}} months; YTD {{result._totals._first.order_items.total_revenue.value_static}})
```

### F. Build a filter‑aware deep link — *use a dashboard text tile*
The URL param targets the filter by its **control id** (`f--<filterId>`; an interactive control is `c--<controlId>`); the value comes from a `.value_url_encoded` token. Build it in a **text tile**, where filters are id-keyed and each is addressable separately:
```
[Open](…/dashboards/<id>?f--state_filter={{filters.state_filter.value_url_encoded}})
```
> **Don't build this in a viz tile.** There the value token keys by `view.field`, and if **two filters target the same field** they collapse to one composite-OR whose `.value`/`.value_url_encoded` is **empty** — the link's value silently drops. The text tile keeps each filter separate (its own `.value`), so the link stays correct, and the URL param id matches the token id.

## Pitfalls

- **Wrong namespace (the classic):** a date/string filter is addressed via the **`filters`** namespace, not `controls` — `{{controls.<filterId>.summary}}`/`.value` render **empty** in both tile kinds (it's configured as a control, but mustache routes filters to `filters`; only non-filter interactive controls appear under `controls`). Use the `filters` namespace (keyed by `view.field` in a viz tile, by control `id` in a text tile).
- **Wrong key form for the tile kind:** in a **viz** tile a filter is keyed by `view.field`, so `{{filters.<controlId>.…}}` is empty; in a **dashboard text** tile it's keyed by control `id`, so `{{filters.<view>.<field>.…}}` is empty. Match the key to the context (or run `{{inspect}}` to read the live keys).
- **KPI tile text isn't mustache:** a `chartType:"kpi"` tile's `markdownConfig` text/number sections do **not** run mustache. For a dynamic caption use a **markdown viz tile** instead.
- **Blank markdown *viz* tile (one of three blank causes):** on a markdown **`queryPresentation`** (a tile *with* a query), set **both** `automaticVis:false` and `prefersChart:false`, or the renderer ignores your markdown and auto‑derives a chart → white tile (tell‑tale: `{{result…}}` resolves but the tile is blank). The other two blanks are distinct: the **round-trip flat-config trap** (the inner spec sent flat → `markdown` dropped — see [visConfig.md](visConfig.md)), and a **no-query `queryPresentation`** which renders **"This chart is empty"** (a real text tile is an `inline-text` content-item, *not* a `queryPresentation` — see [containers.md](containers.md)).
- **`.value` / `.value_static` / `.raw` in `result`:** `.value` is **formatted *and* interactive** (a drillable element — renders a component, not a string); **`.value_static`** is **formatted, no interactivity** (the display string — use this for caption text); **`.raw`** is the **unformatted underlying value** (use it for arithmetic / CSS `calc()`).
- **Discovery:** when a token is empty and you're not sure why, put `{{inspect}}` in the body and read the dumped keys.

## See also
- [Omni Mustache reference](https://docs.omni.co/visualize-present/mustache-reference) — the authoritative public token list
- [visConfig.md](visConfig.md) — the markdown config shape + the blank‑tile trap
- [markdown-tiles.md](markdown-tiles.md) — markdown-tile recipes (metric‑switch, responsive fonts, funnel, sizing)
- [controls.md](controls.md) — control/filter config shapes and per‑tile `map` scoping
- [containers.md](containers.md) — placing controls (filter bar / in‑tile); the non‑templated title child
- [queryPresentations.md](queryPresentations.md) — tile query/visConfig structure

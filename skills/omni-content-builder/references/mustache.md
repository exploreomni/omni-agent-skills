# Mustache in Dashboards Reference

How dashboard text/markdown tiles interpolate `{{...}}` tokens — the namespaces, the **filter‑vs‑control** distinction, the per‑namespace token tables, and worked scenarios. Behaviors here are verified against live dashboards; the authoritative token list is Omni's public [Mustache reference](https://docs.omni.co/visualize-present/mustache-reference).

> **Why this matters:** the most common mistake is reaching for `{{controls.<id>.…}}` to show a **filter's** value. A date/string/number/boolean *filter* is **not** a control and never appears in the `controls` namespace — it lives under `filters`, keyed by **`view.field`**. Using the wrong namespace fails **silently** (the token renders empty), so it looks like a rendering bug.

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

The available namespaces differ by **tile kind**:

| Tile kind | Namespaces |
|---|---|
| **Markdown *visualization* tile** (`chartType:"markdown"`, has its own `query`) | `result`, `filters` (**this tile's** `query.filters`), `controls`, `metadata`, `fields`, `inspect` |
| **Dashboard *text* tile** (standalone inline text, no query) | `filters` (**dashboard** filters), `controls`, `queries` (all tiles' presentations), `metadata`, `inspect` — **no `result`** |
| KPI / chart / table / pivot tiles | **not** mustache‑templated. Only viz **axis labels** have limited support. To show a dynamic number *and* a dynamic caption, use a **markdown viz tile**, not a KPI tile. |

The crucial consequence: in a **markdown viz tile**, `filters` resolves against **that tile's own `query.filters`** — so the same token (e.g. `{{filters.ecomm__order_items.created_at.summary}}`) renders **per‑tile**, reflecting whatever filter/control applies to *that* card. This is what makes one token work identically across many KPI cards that each have their own date control.

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
- `PERIOD_OVER_PERIOD` (the "Compare to" control) is **visible in the filter bar but unreachable from mustache.** Even though it renders as a control, it never appears in the `controls` template context — *every* `{{controls.<pop_id>.…}}` form (`.summary`, `.value`, `.label`, even `.json`) comes back empty, and it isn't under `filters` either. There is no token for the comparison period; the prior-period columns come from the tile query's `period_over_period_computations` instead (see [queryPresentations.md](queryPresentations.md)). Confirm with `{{inspect}}` — there is no `pop` key under `controls`.

> "Filter" vs "control" here is about the **mustache namespace, not ontology** — both kinds are entries in the same `controls.data` slice and both render as filter-bar widgets. A `type:"date"` filter is still routed to **`filters`** (keyed by `view.field`), while an interactive control is routed to **`controls`** (keyed by id). So reference a date filter under `filters`, not `controls` — even though it *is* a control entry in the document.

## The keying gotcha (`view.field` vs `id`)

Within the `filters` namespace, each entry of the tile's `query.filters` is keyed one of two ways:

- A filter applied **by a control**, or any field‑scoped filter whose id equals its field name, is keyed by **`view.field`** → `{{filters.ecomm__order_items.created_at.summary}}`.
- Only a document filter whose **`id` differs from its `fieldName`** is keyed by id → `{{filters.<id>.…}}`.

**Rule of thumb: reference filters by `view.field`, reference controls by `id`.** When unsure, drop `{{inspect}}` into the body to dump the live context and read the exact keys.

## Token reference by namespace

### `{{filters.<view>.<field>.X}}`
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
| `.value_static` | **formatted display string** (use this for text — `"4.77"`, `"$793,533.63"`) |
| `.value` | a clickable drill element (renders interactive, not plain text) |
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

### A. Dynamic KPI caption that tracks a per‑tile date control
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

### B. Dashboard header that reflects the global filters
A standalone **text tile** summarizing the active dashboard filters:
```
### Sales — {{filters.users.state.summary}}, {{filters.order_items.status.summary}}
Viewed by {{metadata.userAttributes.omni_user_email.element}} · refreshed {{metadata.lastRanAt}}
```

### C. Caption that follows a metric/field *switcher*
This is the one case where `controls.*` is correct — a `FIELD_SELECTION` control:
```
**{{controls.kpi_metric.summary}}**
```
Pair with the CSS metric‑switch pattern in [visConfig.md](visConfig.md) to reveal the matching value span.

### D. Exact filter boundary *dates* (not the friendly summary)
Viz mustache has no absolute start/end‑date token (`.summary` is friendly text, `.value` is the relative expression). To show real boundary dates, expose them as **model dimensions** via templated‑filter tokens, then read with `result`:
```yaml
# on the filtered view
period_start: { sql: 'DATE({{ filters.ecomm__order_items.created_at.range_start }})', hidden: true }
period_end:   { sql: 'DATE({{ filters.ecomm__order_items.created_at.range_end }})',   hidden: true }
```
Tile query selects `period_start`/`period_end`; body reads `{{result._first.ecomm__order_items.period_start.value_static}}`. (`range_start`/`range_end` are model‑SQL templated‑filter tokens — **not** available in viz mustache.)

### E. Show a value from the result set (single number, last row, total)
```
Latest month: {{result._last.order_items.created_at.value_static}} →
{{result._last.order_items.total_revenue.value_static}}
(of {{result._rows}} months; YTD {{result._totals._first.order_items.total_revenue.value_static}})
```

### F. Build a filter‑aware deep link
```
[Open filtered](https://app/dash?c--state={{filters.users.state.value_url_encoded}})
```

## Pitfalls

- **Wrong namespace (the classic):** a date filter is **not** a control. `{{controls.<dateFilterId>.summary}}` and `.value` both render **empty**. Use `{{filters.<view>.<field>.summary}}`.
- **Wrong key form:** referencing a control‑applied filter by id (`{{filters.date_2.summary}}`) is empty; it's keyed by field (`{{filters.ecomm__order_items.created_at.summary}}`).
- **KPI tile text isn't mustache:** a `chartType:"kpi"` tile's `markdownConfig` text/number sections do **not** run mustache. For a dynamic caption use a **markdown viz tile** instead.
- **Blank markdown tile:** set **both** `automaticVis:false` and `prefersChart:false`, or the renderer auto‑derives a chart and the tile is white (tell‑tale: `{{result…}}` resolves when tested but the tile is blank).
- **Tile-embedded controls don't resolve:** `{{controls.<id>}}` reads **dashboard** controls (`controls.data`). A control embedded in `query.controls[]` is invisible to the template and lands in the HIDDEN CONTROLS tray.
- **`.value` vs `.value_static` in `result`:** `.value` is an interactive drill element (renders a component); use **`.value_static`** for plain text.
- **Discovery:** when a token is empty and you're not sure why, put `{{inspect}}` in the body and read the dumped keys.

## See also
- [Omni Mustache reference](https://docs.omni.co/visualize-present/mustache-reference) — the authoritative public token list
- [visConfig.md](visConfig.md) — markdown tiles, the metric‑switch CSS pattern, the blank‑tile trap
- [controls.md](controls.md) — control/filter config shapes and per‑tile `map` scoping
- [containers.md](containers.md) — placing controls (filter bar / in‑tile); the non‑templated title child
- [queryPresentations.md](queryPresentations.md) — tile query/visConfig structure

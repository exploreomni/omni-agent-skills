# Embed Event Reference

## Contents

- `dashboard:loaded`
- `dashboard:filters`
- `error`
- `dashboard:tile-drill`
- `page:changed`

**`dashboard:loaded`** — Fired when the embedded dashboard finishes loading.

```json
{ "source": "omni", "name": "dashboard:loaded" }
```

**`dashboard:filters`** — Fired when filter state changes inside the embedded dashboard.

```json
{
  "source": "omni",
  "name": "dashboard:filters",
  "payload": { /* filter state */ }
}
```

**`error`** — Fired when a detectable error occurs on the embedded page.

```json
{
  "source": "omni",
  "name": "error",
  "payload": {
    "href": "https://...",
    "message": "Error description"
  }
}
```

**`dashboard:tile-drill`** — Fired when a user drills on any dashboard tile (charts, tables, maps). No Omni-side configuration required.

```json
{
  "source": "omni",
  "name": "dashboard:tile-drill",
  "payload": {
    "userId": "string",
    "dashboard": {
      "filters": {
        "filterName": {
          "filter": {},
          "asJsonUrlSearchParam": "string"
        }
      },
      "href": "string",
      "urlId": "string",
      "path": "string",
      "title": "string"
    },
    "tile": {
      "id": "string",
      "title": "string",
      "appliedFilters": {
        "filterName": {
          "filter": {},
          "asJsonUrlSearchParam": "string"
        }
      }
    },
    "drill": {
      "field": "string",
      "fieldLabel": "string",
      "drillQueryLabel": "string",
      "rowToDrill": { "field_name": "value" }
    }
  }
}
```

Use `drill.rowToDrill` for the data from the drilled row. Use `asJsonUrlSearchParam` from `tile.appliedFilters` or `dashboard.filters` to sign and embed a different dashboard with those filters applied.

**`page:changed`** — Fired when the URL changes inside the iframe (including after saving a new dashboard).

```json
{
  "source": "omni",
  "name": "page:changed",
  "payload": {
    "pathname": "string",
    "type": "string"
  }
}
```

**Custom visualization events** — Fired when a user clicks a configured table row or markdown link. Requires setup in Omni: set the table column's Display to **Link** → **Embed event** and enter an event name. For markdown, use `<omni-message>` tags.

```json
{
  "source": "omni",
  "name": "<your-event-name>",
  "payload": {
    "data": "comma-separated values"
  }
}
```

Table setup: field dropdown → Display tab → Display as: Link → URL: Embed event → enter event name.

Markdown setup:
```html
<omni-message event-name="product-click" event-data="{{products.name.raw}},{{products.retail_price.raw}}">
  Click here
</omni-message>
```

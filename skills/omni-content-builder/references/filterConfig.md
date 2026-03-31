# filterConfig Reference

Complete filter and control configuration examples for creating dashboards with pre-configured filters. Include `filterConfig`, `filterOrder`, and optionally `controls` in the `POST /api/v1/documents` body alongside `queryPresentations`.

> **Important**: The `filterConfig` schema is not fully documented in Omni's public API docs. The examples below are based on reading back filters from dashboards created in the Omni UI via `GET /api/v1/dashboards/{dashboardId}/filters`. **Always verify filter structure** by creating a reference filter in the UI and reading it back before relying on these examples.

## Structure Overview

```json
{
  "modelId": "your-model-id",
  "name": "Dashboard Name",
  "filterConfig": {
    "<filter_id>": { /* filter definition */ },
    "<filter_id>": { /* filter definition */ }
  },
  "filterOrder": ["<filter_id>", "<control_id>", "<filter_id>"],
  "controls": [
    { /* control definition */ }
  ],
  "queryPresentations": [...]
}
```

- `filterConfig` keys are arbitrary string IDs (e.g., `"date_filter"`, `"status_filter"`)
- `filterOrder` is an array of filter IDs and control IDs — controls display order on the dashboard
- Every ID in `filterOrder` must exist in either `filterConfig` or `controls`
- **Filters** restrict data (date ranges, string matches, booleans)
- **Controls** change what fields or granularity tiles display (field switchers, time frame pickers) — these go in a separate `controls` array, not in `filterConfig`

## Filter Properties

All filter types support these common properties:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Data type: `"string"`, `"number"`, `"date"`, `"boolean"`, `"null"`, `"by_query"`, `"user_attribute"`, `"composite"` |
| `kind` | Yes | Operation type (varies by filter type — see below) |
| `label` | Yes | Display label shown above the filter |
| `fieldName` | Yes | Fully qualified field name the filter binds to (e.g., `"order_items.created_at"`, `"users.state"`). Without this, the filter won't bind to any column. For date filters, do NOT include a timeframe bracket. |
| `description` | No | Help text — shows as an info icon tooltip next to the filter label |
| `required` | No | Whether the filter must have a value selected |
| `hidden` | No | `true` to apply the filter but hide it from the dashboard UI |

## Date Range Filter

Lets the user pick a date range.

### Relative date range (e.g., "last 6 months")

```json
{
  "date_filter": {
    "type": "date",
    "label": "Date Range",
    "fieldName": "order_items.created_at",
    "kind": "TIME_FOR_INTERVAL_DURATION",
    "ui_type": "PAST",
    "left_side": "6 months ago",
    "right_side": "6 months"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | Yes | `"TIME_FOR_INTERVAL_DURATION"` for relative date ranges |
| `ui_type` | Yes | `"PAST"` for lookback, `"FUTURE"` for forward-looking |
| `left_side` | Yes | Human-readable start (e.g., `"6 months ago"`, `"30 days ago"`, `"1 year ago"`) |
| `right_side` | Yes | Duration string (e.g., `"6 months"`, `"30 days"`, `"1 year"`) |

### Absolute date range (e.g., "2024-01-01 to 2024-12-31")

```json
{
  "date_filter": {
    "type": "date",
    "label": "Date Range",
    "fieldName": "order_items.created_at",
    "kind": "WITHIN_RANGE",
    "left_side": "2024-01-01",
    "right_side": "2024-12-31"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | Yes | `"WITHIN_RANGE"` for absolute date ranges |
| `left_side` | Yes | Start date in `YYYY-MM-DD` format |
| `right_side` | Yes | End date in `YYYY-MM-DD` format |

### Date range variants

**Last 30 days:**
```json
{
  "type": "date",
  "label": "Date Range",
  "fieldName": "order_items.created_at",
  "kind": "TIME_FOR_INTERVAL_DURATION",
  "ui_type": "PAST",
  "left_side": "30 days ago",
  "right_side": "30 days"
}
```

**Last 1 year:**

Note: This will be for the given calendar year, not a rolling 1 year window. For a rolling window, use the last 12 months.

```json
{
  "type": "date",
  "label": "Date Range",
  "fieldName": "order_items.created_at",
  "kind": "TIME_FOR_INTERVAL_DURATION",
  "ui_type": "PAST",
  "left_side": "1 year ago",
  "right_side": "1 year"
}
```

## String Dropdown Filter

Lets the user select one or more values from a dropdown populated by field values.

```json
{
  "status_filter": {
    "type": "string",
    "label": "Order Status",
    "kind": "EQUALS",
    "fieldName": "order_items.status",
    "values": []
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | Yes | `"EQUALS"` for dropdown selection |
| `fieldName` | Yes | Fully qualified field name (e.g., `"users.state"`) |
| `values` | Yes | Default selected values. `[]` for no default (shows all). `["complete", "pending"]` to pre-select. |

### String filter with default values

```json
{
  "type": "string",
  "label": "Status",
  "kind": "EQUALS",
  "fieldName": "order_items.status",
  "values": ["complete"]
}
```

## Boolean Toggle Filter

A simple on/off toggle.

```json
{
  "is_active_filter": {
    "type": "boolean",
    "label": "Active Only",
    "fieldName": "users.is_active",
    "is_negative": false
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `fieldName` | Yes | Fully qualified boolean field name |
| `is_negative` | No | `false` = filter for `true` values, `true` = filter for `false` values |

## Hidden Filter

Any filter type with `"hidden": true`. Applied to queries but not visible in the dashboard UI. Useful for hardcoded filters the user shouldn't change.

> **Security note**: Omni recommends access filters (in the model) over hidden dashboard filters for data restriction.

```json
{
  "hidden_status": {
    "type": "string",
    "label": "Status",
    "kind": "EQUALS",
    "fieldName": "order_items.status",
    "values": ["complete"],
    "hidden": true
  }
}
```

## Controls (not filters)

Controls change what fields or granularity tiles display — they go in a separate `controls` array, NOT in `filterConfig`. Control IDs are referenced in `filterOrder` alongside filter IDs.

### Date Granularity Picker (Time Frame Switcher)

Lets the user switch between time granularities (day, week, month, etc.).

```json
{
  "controls": [
    {
      "id": "granularity_picker",
      "type": "FIELD_SELECTION",
      "kind": "TIMEFRAME",
      "label": "Date Granularity",
      "field": "order_items.created_at[month]",
      "options": [
        { "label": "Day", "value": "order_items.created_at[date]" },
        { "label": "Week", "value": "order_items.created_at[week]" },
        { "label": "Month", "value": "order_items.created_at[month]" },
        { "label": "Quarter", "value": "order_items.created_at[quarter]" },
        { "label": "Year", "value": "order_items.created_at[year]" }
      ]
    }
  ],
  "filterOrder": ["date_filter", "granularity_picker", "status_filter"]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique control ID — must be referenced in `filterOrder` |
| `type` | Yes | `"FIELD_SELECTION"` for single field switcher, `"FIELD_PICKER"` for multi-select, `"PERIOD_OVER_PERIOD"` for time comparison |
| `kind` | Yes | `"TIMEFRAME"` for date granularity, `"FIELD"` for field switching |
| `label` | Yes | Display label |
| `field` | No | Currently selected/default field value |
| `options` | Yes | Array of `{ label, value }` where `value` is the field reference |

### Field Switcher

Lets viewers swap one field for another (e.g., switch between revenue and order count).

```json
{
  "controls": [
    {
      "id": "metric_switcher",
      "type": "FIELD_SELECTION",
      "kind": "FIELD",
      "label": "Metric",
      "field": "order_items.total_revenue",
      "options": [
        { "label": "Revenue", "value": "order_items.total_revenue" },
        { "label": "Order Count", "value": "order_items.count" },
        { "label": "Average Order Value", "value": "order_items.average_order_value" }
      ]
    }
  ]
}
```

## Complete Example: Dashboard with Filters and Controls

```json
{
  "modelId": "your-model-id",
  "name": "Sales Overview",
  "filterConfig": {
    "date_range": {
      "type": "date",
      "label": "Date Range",
      "fieldName": "order_items.created_at",
      "kind": "TIME_FOR_INTERVAL_DURATION",
      "ui_type": "PAST",
      "left_side": "6 months ago",
      "right_side": "6 months"
    },
    "status": {
      "type": "string",
      "label": "Order Status",
      "kind": "EQUALS",
      "fieldName": "order_items.status",
      "values": []
    },
    "state": {
      "type": "string",
      "label": "State",
      "kind": "EQUALS",
      "fieldName": "users.state",
      "values": []
    }
  },
  "controls": [
    {
      "id": "date_granularity",
      "type": "FIELD_SELECTION",
      "kind": "TIMEFRAME",
      "label": "Date Granularity",
      "field": "order_items.created_at[month]",
      "options": [
        { "label": "Week", "value": "order_items.created_at[week]" },
        { "label": "Month", "value": "order_items.created_at[month]" },
        { "label": "Quarter", "value": "order_items.created_at[quarter]" }
      ]
    }
  ],
  "filterOrder": ["date_range", "date_granularity", "status", "state"],
  "queryPresentations": []
}
```

## Tips

- **Always verify filter structure**: Create the filter in the Omni UI and read it back with `GET /api/v1/dashboards/{dashboardId}/filters` — the response includes both `filters` and `controls` objects you can use as templates.
- `PUT` and `PATCH` on `/dashboards/{id}/filters` may return 405 or 500. Include filters during document creation instead.
- Filter IDs are arbitrary strings — use descriptive names for readability.
- Filters can be **mapped to different fields across tiles** — e.g., a date filter based on `order_items.created_at` can map to `users.created_at` on a different tile. This mapping is managed in the Omni UI after creation.
- **Filters will not automatically apply to custom-written SQL queries** — use dynamic filtering (templated filters) for SQL-mode tiles.

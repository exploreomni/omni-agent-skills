---
name: omni-embed
description: Embed Omni Analytics dashboards in external applications — URL signing, custom themes, iframe events, entity workspaces, and permission-aware content — using the @omni-co/embed SDK and Omni CLI. Use this skill whenever someone wants to embed a dashboard, sign an embed URL, customize the embedded theme, handle embed events, listen for clicks or drills in the iframe, send filters to an embedded dashboard, set up entity workspaces, look up embed users, build a permission-aware content list, white-label an embedded dashboard, or any variant of "embed this dashboard", "customize the iframe theme", "handle click events from the embed", "filter the embedded dashboard", "set up embedding", or "what dashboards can this user see".
---

# Omni Embed

Embed Omni dashboards in external applications using signed iframe URLs. The `@omni-co/embed` SDK handles URL signing and theme customization. Omni's postMessage events enable two-way communication between the parent app and embedded iframe.

> **Tip**: Use `omni-content-explorer` to find dashboards to embed, and `omni-admin` to manage embed user permissions and user attributes for row-level security.

## Prerequisites

```bash
npm install @omni-co/embed
```

```bash
command -v omni >/dev/null || curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh
```

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
export OMNI_EMBED_SECRET="your-embed-secret"   # Admin → Embed (for URL signing)
```

The embed secret is found in **Admin → Embed** in your Omni instance. The `OMNI_BASE_URL` for embedding uses the `.embed-omniapp.co` domain, not the standard `.omniapp.co` domain.

## Discovering Commands

```bash
omni scim --help        # Embed user lookup
omni documents --help   # Document listing
omni folders --help     # Folder listing
```

## Signing Embed URLs

Use `embedSsoDashboard()` from the `@omni-co/embed` SDK to generate a signed URL server-side, then load it in an iframe client-side.

```typescript
import { embedSsoDashboard, EmbedSessionMode } from "@omni-co/embed";

const embedUrl = await embedSsoDashboard({
  contentId: "dashboard-uuid",
  secret: process.env.OMNI_EMBED_SECRET,
  host: "yourorg.embed-omniapp.co",       // Hostname only, no https://
  externalId: "user@example.com",
  name: "Jane Doe",
  userAttributes: { brand: ["Acme"] },     // For row-level security
  mode: EmbedSessionMode.SingleContent,
  prefersDark: "false",
});
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `contentId` | Yes | Dashboard UUID (from URL or Admin → Dashboards) |
| `secret` | Yes | Embed secret from Admin → Embed |
| `host` | Yes | Embed hostname only — no protocol, no port |
| `externalId` | Yes | Unique user identifier (typically email) |
| `name` | Yes | Display name for the user |
| `userAttributes` | No | `Record<string, string[]>` for row-level security |
| `mode` | No | `SingleContent` (default) or `Application` (enables create) |
| `prefersDark` | No | `"true"` or `"false"` — controls light/dark mode |
| `customTheme` | No | Theme object (see Custom Themes below) |
| `entity` | No | Entity name for workspaces (see Entity Workspaces below) |

**Gotcha**: The `host` parameter must be a bare hostname (e.g., `yourorg.embed-omniapp.co`). Including a protocol (`https://`) or port (`:3000`) causes Omni to return 400.

## Custom Themes

Pass a `customTheme` object to `embedSsoDashboard()` to style the embedded dashboard content (tile backgrounds, text colors, controls, buttons). This controls what's **inside** the iframe — parent app styling is separate.

```typescript
const embedUrl = await embedSsoDashboard({
  // ...signing params
  prefersDark: "false",
  customTheme: {
    "dashboard-background": "#FEF2F2",
    "dashboard-tile-background": "#FFF5F5",
    "dashboard-key-color": "#E60000",
    "dashboard-key-text-color": "#ffffff",
    // ...
  },
});
```

### Property Reference

**Page:**

| Property | Description |
|----------|-------------|
| `dashboard-background` | Dashboard page background |
| `dashboard-page-padding` | Dashboard page padding |

**Tiles:**

| Property | Description |
|----------|-------------|
| `dashboard-tile-margin` | Spacing around tiles |
| `dashboard-tile-background` | Tile background color |
| `dashboard-tile-shadow` | Tile box shadow |
| `dashboard-tile-text-body-color` | Primary text color in tiles |
| `dashboard-tile-text-secondary-color` | Secondary text color in tiles |
| `dashboard-tile-border-color` | Tile border color |
| `dashboard-tile-border-radius` | Tile border radius |
| `dashboard-tile-border-style` | Tile border style |
| `dashboard-tile-border-width` | Tile border width |
| `dashboard-tile-title-font-size` | Title font size |
| `dashboard-tile-title-font-weight` | Title font weight |
| `dashboard-tile-title-text-color` | Title text color |
| `dashboard-tile-title-font-family` | Custom title font (woff2 URL) |
| `dashboard-tile-text-body-font-family` | Custom body font |
| `dashboard-tile-text-code-font-family` | Custom code font |

**Controls (filter dropdowns):**

| Property | Description |
|----------|-------------|
| `dashboard-control-background` | Filter control background |
| `dashboard-control-radius` | Filter control border radius |
| `dashboard-control-border-color` | Filter control border color |
| `dashboard-control-text-color` | Filter control text color |
| `dashboard-control-placeholder-color` | Placeholder text color |
| `dashboard-control-label-color` | Label text above controls |
| `dashboard-control-outline-color` | Focus outline color |

**Control Popovers (dropdown menus):**

| Property | Description |
|----------|-------------|
| `dashboard-control-popover-background` | Popover background |
| `dashboard-control-popover-text-color` | Popover text color |
| `dashboard-control-popover-secondary-text-color` | Secondary text in popovers |
| `dashboard-control-popover-link-color` | Link color in popovers |
| `dashboard-control-popover-divider-color` | Divider color |
| `dashboard-control-popover-radius` | Popover border radius |
| `dashboard-control-popover-border-color` | Popover border color |
| `dashboard-filter-input-background` | Filter input background |
| `dashboard-filter-input-radius` | Filter input border radius |
| `dashboard-filter-input-border-color` | Filter input border color |
| `dashboard-filter-input-text-color` | Filter input text color |
| `dashboard-filter-input-placeholder-color` | Placeholder text |
| `dashboard-filter-input-icon-color` | Icon color in filter inputs |
| `dashboard-filter-input-outline-color` | Focus outline for filter inputs |
| `dashboard-filter-input-accent-color` | Checkbox, radio, and toggle color |
| `dashboard-filter-input-accent-invert-color` | Checkmark/dot color inside inputs |
| `dashboard-filter-input-token-color` | Multi-select token background |
| `dashboard-filter-input-token-text-color` | Multi-select token text color |

**Buttons:**

| Property | Description |
|----------|-------------|
| `dashboard-key-color` | Primary action color (Update buttons) |
| `dashboard-key-text-color` | Text color on primary buttons |
| `dashboard-button-radius` | Button border radius |
| `dashboard-button-transparent-text-color` | Transparent button text color |
| `dashboard-button-transparent-interactive-color` | Transparent button hover color |
| `dashboard-menu-item-interactive-color` | Menu item hover background |

### Supported CSS Values

- Hex colors: `"#FEF2F2"`, `"#E60000"`
- Box shadows with rgba: `"0 2px 8px rgba(230, 0, 0, 0.1)"`
- Custom fonts via URL: `"url(https://fonts.gstatic.com/...) format('woff2')"`
- Empty strings to clear defaults: `""`
- `linear-gradient()` and `rgba()` for backgrounds work in Omni's UI theme editor but may fail when passed via the SDK — use solid hex colors for reliability

### Theming Tips

For effective branding, tint backgrounds throughout rather than only coloring buttons:

- `dashboard-background` → light brand tint (like Tailwind's color-50)
- `dashboard-tile-background` → slightly lighter than page background
- `dashboard-tile-title-text-color` → brand primary (titles in brand color)
- `dashboard-control-label-color` → brand primary (labels in brand color)
- `dashboard-tile-border-color` → medium-light brand tint (like color-200)
- `dashboard-key-color` → brand primary
- `dashboard-filter-input-accent-color` → brand primary (checkboxes, toggles)

## Embed Events

Omni communicates with the parent app via `postMessage`. All Omni events have `source: "omni"`.

### Listening for Events

```javascript
window.addEventListener("message", (event) => {
  if (event.data?.source !== "omni") return;

  switch (event.data.name) {
    case "dashboard:loaded":
      // Dashboard ready
      break;
    case "error":
      // Handle error
      break;
    case "dashboard:tile-drill":
      // Handle drill action
      break;
  }
});
```

### Event Reference

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

### Sending Events to the Iframe

**`dashboard:filter-change-by-url-parameter`** — Push a filter from the parent app into the embedded dashboard.

```javascript
iframe.contentWindow.postMessage({
  source: "omni",
  name: "dashboard:filter-change-by-url-parameter",
  payload: {
    filterUrlParameter: 'f--<filter_id>={"values":["value1","value2"]}'
  }
}, iframeOrigin);
```

Get the `filterUrlParameter` string by opening the dashboard in Omni, changing filter values, and copying the `f--` parameter from the URL.

## Entity Workspaces

Entity workspaces let embed users create and save their own dashboards within a scoped folder.

```typescript
import {
  embedSsoDashboard,
  EmbedSessionMode,
  EmbedEntityFolderContentRoles,
  EmbedUiSettings,
  EmbedConnectionRoles,
} from "@omni-co/embed";

const embedUrl = await embedSsoDashboard({
  // ...standard signing params
  entity: "acme",
  entityFolderContentRole: EmbedEntityFolderContentRoles.EDITOR,
  mode: EmbedSessionMode.Application,
  uiSettings: {
    [EmbedUiSettings.SHOW_NAVIGATION]: false,
  },
  connectionRoles: {
    "connection-uuid": EmbedConnectionRoles.RESTRICTED_QUERIER,
  },
});
```

| Parameter | Description |
|-----------|-------------|
| `entity` | Entity name — scopes the user's folder (e.g., derived from email domain) |
| `entityFolderContentRole` | `EDITOR` lets users create/edit dashboards in their entity folder |
| `mode` | Must be `Application` to enable create features |
| `uiSettings` | Control Omni's built-in UI (e.g., hide Omni's sidebar if you provide your own) |
| `connectionRoles` | Grant query access: `RESTRICTED_QUERIER` for data exploration |

## Embed Users and Permissions

When building permission-aware experiences (e.g., a sidebar that only shows dashboards a user can access), use these REST API calls. Note: API calls use the `.omniapp.co` domain, not the `.embed-omniapp.co` embed domain.

### Look Up an Embed User

```bash
omni scim embed-users-list --filter 'embedExternalId eq "user@example.com"'
```

Returns the Omni user ID for the given `externalId`. If no user is found, the user hasn't accessed any embedded dashboards yet.

### List Documents by User Permission

```bash
omni documents list --user-id <omniUserId>
```

Response uses `records` array (not `documents`):

```json
{
  "pageInfo": {
    "hasNextPage": false,
    "nextCursor": null,
    "pageSize": 20,
    "totalRecords": 5
  },
  "records": [
    {
      "identifier": "fb007aa3",
      "name": "Sales Dashboard",
      "hasDashboard": true,
      "folder": {
        "id": "...",
        "name": "Sales",
        "path": "sales/regional"
      }
    }
  ]
}
```

Use `identifier` as the `contentId` for embed signing. Filter for `hasDashboard: true` to get embeddable dashboards only.

### List Folders for Friendly Names

Entity folders have technical paths like `omni-system-sso-embed-entity-folder-poc`. Map paths to display names:

```bash
omni folders list
```

Build a `path → name` mapping from the response to display user-friendly folder names.

### Domain Mapping

The embed domain (`.embed-omniapp.co`) and API domain (`.omniapp.co`) are different:

```
Embed: yourorg.embed-omniapp.co  →  used for iframe URLs
API:   yourorg.omniapp.co        →  used for REST API calls
```

When your app stores the embed domain, convert it for API calls by replacing `.embed-omniapp.co` with `.omniapp.co`.

## Docs Reference

- [Embed Overview](https://docs.omni.co/embed.md) · [Custom Themes](https://docs.omni.co/embed/customization/themes.md) · [Embed Events](https://docs.omni.co/embed/events.md) · [AI Chat in Embeds](https://docs.omni.co/embed/customization/ai-chat.md) · [Embed Users API](https://docs.omni.co/api/users/list-embed-users.md) · [Documents API](https://docs.omni.co/api/documents.md)

## Related Skills

- **omni-content-explorer** — find dashboards to embed
- **omni-content-builder** — create dashboards before embedding them
- **omni-admin** — manage embed user permissions, user attributes for RLS, and connections
- **omni-model-explorer** — understand available fields for embed event data

# Theme Property Reference

## Property Reference

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

## Supported CSS Values

- Hex colors: `"#FEF2F2"`, `"#E60000"`
- Box shadows with rgba: `"0 2px 8px rgba(230, 0, 0, 0.1)"` (for shadow properties only)
- Custom fonts via URL: `"url(https://fonts.gstatic.com/...) format('woff2')"`
- Empty strings to clear defaults: `""`
- `linear-gradient()` and `rgba()` for background/color properties work in Omni's UI theme editor but may fail when passed via the SDK — use solid hex colors for reliability

# Color Palettes

Custom chart color palettes for the organization (CLI ≥ 1.3.1). Writes need the **Manage Config** permission. Run `create` / `update` with `--schema` for the body; `type` is `discrete` (colors categories in order) or `continuous` (a gradient for numeric scales).

```bash
omni color-palettes list                 # custom palettes only; built-ins are not listed
omni color-palettes get <paletteId>
omni color-palettes create --body '{ "name": "Brand colors", "type": "discrete", "colors": ["#1f77b4", "#ff7f0e"] }'
omni color-palettes update <paletteId> --body '{ "colors": ["#1f77b4", "#2ca02c"] }'
omni color-palettes delete <paletteId>
```

- **Updates and deletes reach every chart that uses the palette.** An update recolors those charts in place; a delete makes them fall back to the org default palette. Neither reports which charts were affected.
- The org's current default palette cannot be deleted, and names must be unique per `type`.

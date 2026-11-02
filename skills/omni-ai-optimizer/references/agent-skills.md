# Agent Skills Commands

```bash
omni skills list                                   # bodies omitted
omni skills list --identifier quarterly-report     # filter by handle; exact match, still returns a list
omni skills list --q revenue                       # free-text search (CLI ≥ 1.4.0)
omni skills get <skillId>                          # includes the body
omni skills create --body @skill.json              # name, identifier, description, body
omni skills update <skillId> --body '{ "body": "…" }'
omni skills delete <skillId>
omni skills invocation-mode-set <skillId> --body '{ "invocationMode": "manual" }'   # CLI ≥ 1.5.0
```

- **Limits**: `identifier` is the handle without the slash: lowercase letters, numbers and hyphens, starting with a letter or number, up to 48 characters. `name` up to 256, `description` up to 1,024, `body` up to 20,000.
- **Roles on a skill**: reading needs Viewer, `update` needs Editor and `delete` needs Manager; anything less is a 403.
- **`update`** changes only the fields you send. A handle already taken is a 409, as on `create`.
- **Invocation mode** is per member, and changes only that member's agent: `auto` lets the agent use the skill on its own when a request fits, `manual` only when the member names it or its `/identifier`, and `off` hides it from the agent and the chat menus.
- **Org-scoped API keys** act for one member with `--user-id <membershipId>` on `list`, `get`, `update`, `delete` and `invocation-mode-set`.
- **Skills in model YAML**: a model or topic file can also hold a `skills:` block. The docs mark it for deprecation in favor of the skills above; existing ones still work, but create new skills with `omni skills`.

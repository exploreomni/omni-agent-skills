# Agent Skills Commands

```bash
omni skills list                                   # bodies omitted
omni skills list --identifier quarterly-report     # filter by handle; exact match, still returns a list
omni skills list --q revenue                       # free-text search (CLI ≥ 1.4.0)
omni skills get <skillId>                          # includes the body
omni skills create --body @skill.json              # name, identifier, description, body
omni skills update <skillId> --body '{ "body": "…" }'
omni skills delete <skillId>
```

# Agent Skills

A skill is a saved set of instructions the Omni Agent loads when a user invokes its slash-command handle (e.g. `/quarterly-report`). Where `ai_context` shapes every answer on a topic, a skill packages one repeatable task. Manage them with `omni skills` (CLI ≥ 1.3.1; experimental, so fields may still change). Run `create` / `update` with `--schema` for the body.

```bash
omni skills list                                   # bodies omitted
omni skills list --identifier quarterly-report     # filter by handle; exact match, still returns a list
omni skills list --q revenue                       # free-text search (CLI ≥ 1.4.0)
omni skills get <skillId>                          # includes the body
omni skills create --body @skill.json              # name, identifier, description, body
omni skills update <skillId> --body '{ "body": "…" }'
omni skills delete <skillId>
```

- **`list` is scoped to the caller.** An org admin sees every skill in the organization; anyone else sees only their own, and `--creator-id` / `--q` narrow within that — neither widens it. An empty list from a non-admin key is not evidence that no skill holds a handle — `create` still 409s on a handle held by someone else's skill.
- **`list` never returns `body`.** Read a skill's instructions with `get`, not from the list.
- **`description` is what the agent chooses between skills on**, so write it the way you would a good `ai_context` line: what the skill is for and when it applies.
- `delete` is a soft delete: the skill vanishes from every read and its handle is free to reuse.

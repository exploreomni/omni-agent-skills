# Agent Skills

## Commands

```bash
omni skills list                                   # bodies omitted
omni skills list --identifier quarterly-report     # filter by handle; exact match, still returns a list
omni skills list --q revenue                       # free-text search (CLI ≥ 1.4.0)
omni skills get <skillId>                          # includes the body
omni skills create --body @skill.json              # name, identifier, description, body
omni skills update <skillId> --body '{ "body": "…" }'
omni skills delete <skillId>
```

- **Limits**: `identifier` is the handle without the slash: lowercase letters, numbers and hyphens, starting with a letter or number, up to 48 characters. `name` up to 256, `description` up to 1,024, `body` up to 20,000.
- **Roles on a skill**: reading needs Viewer, `update` needs Editor and `delete` needs Manager; anything less is a 403.
- **`update`** changes only the fields you send. A handle already taken is a 409, as on `create`.
- **Org-scoped API keys** act for one member with `--user-id <membershipId>` on `list`, `get`, `update` and `delete`.
- **Skills in model YAML**: a model or topic file can also hold a `skills:` block. The docs mark it for deprecation in favor of the skills above; existing ones still work, but create new skills with `omni skills`.

## How a skill runs

- **From the `/` menu or the Skills page**: Omni puts the skill's `body` into the user's message, and the agent follows it as instructions the user chose.
- **Typed as `/identifier` anywhere in a message**: in chat, the Slack agent, a routine's prompt, the create-AI-job API's `prompt`, or MCP's `askOmni`. What the user typed stays the prompt and the instructions are attached, so the agent applies one to the other (`run /churn-cut broken out by region`). In Slack, don't start the message with the `/identifier`.
- **With little or no other text**, a skill runs on the conversation so far.
- **On its own**: the agent's prompt lists the skills the user can run, their own and those shared with them, one line each: `/identifier — name (id): description`, with the description cut at 300 characters. It lists up to 150 by name and searches for the rest. When a request plainly fits one, the agent loads it and says which skill it applied.
- **As whom**: a skill grants no data access. It runs as the user who runs it; in a routine as the routine's owner; through the API or MCP as the effective user.
- **Sharing**: Viewers can run a skill, Editors edit it, Managers share, move and delete it. A shared skill appears in the recipient's `/` menu, and edits apply the next time it runs, in routines too.
- **Turned off**: when skills are off for the organization, every `omni skills` call returns 403.
- **Comments**: `<!-- -->` comments in a body are stripped when the skill runs and kept when it's read for editing, so they can hold notes for the next author.

## Writing a skill

- **Skill, sample query or `ai_context`**: a skill is a task the agent works through step by step; a sample query is a verified answer to a common question; `ai_context` shapes every answer.
- **Name**: two to four words for the task.
- **Body**: be specific about fields, time ranges, groupings, metrics and output format. If the skill needs something only the user knows, such as an account or a date range, open by telling the agent to ask for it. Number the steps of a multi-step task, say how to present the results, and name the topic when it matters.
- **Description**: what the skill is for and when it applies, in the first 300 characters.

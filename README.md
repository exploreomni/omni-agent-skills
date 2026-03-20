# Omni Analytics Agent Skills

Reusable Omni Analytics skills for coding agents and LLM-powered developer
tools. These skills work across assistants that support the `SKILL.md` format
and help teams explore models, run queries, manage content, administer Omni,
and update semantic models through Omni's REST APIs and YAML modeling layer.

## Installation

### Using skills.sh

Install the full collection:

```bash
npx skills add exploreomni/omni-agent-skills
```

Install a specific skill from this repository:

```bash
npx skills add https://github.com/exploreomni/omni-agent-skills --skill omni-query
```

### Using Codex

Use Codex's built-in `skill-installer` skill (`$skill-installer`) and point it
at this repository. For example, ask Codex:

```text
Use the skill-installer skill to install these skills from GitHub:
- repo: exploreomni/omni-agent-skills
- path: plugins/omni-analytics/skills/omni-model-explorer
- path: plugins/omni-analytics/skills/omni-query
```

Install any of the skill directories under
`plugins/omni-analytics/skills/<skill-name>`, then restart Codex to pick up new
skills.

## Setup

Set these environment variables before using the Omni REST API based skills:

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

API keys are created in **Settings > API Keys** for Organization Admins or in
**User Profile > Manage Account > Generate Token** for Personal Access Tokens.
Some skills, especially admin workflows, require an Organization API Key.

> **Token security**: These tokens can appear in terminal scrollback when used
> in shell commands. For team deployments, prefer a secrets manager or an MCP
> server wrapper where possible.

## Skills

This repository currently includes 8 Omni Analytics skills:

| Skill | Description |
|-------|-------------|
| **omni-model-explorer** | Discover and inspect models, topics, views, fields, dimensions, measures, and relationships. |
| **omni-model-builder** | Create and edit Omni semantic model definitions in YAML, including views, topics, fields, and relationships. |
| **omni-query** | Run queries against Omni's semantic layer and interpret the results. |
| **omni-content-explorer** | Find, browse, and organize dashboards, workbooks, folders, and other content. |
| **omni-content-builder** | Create, update, and manage dashboards and documents programmatically. |
| **omni-ai-optimizer** | Optimize Omni models for Blobby by improving AI context, sample queries, and field curation. |
| **omni-admin** | Manage connections, users, groups, permissions, schedules, and schema refreshes. |
| **omni-embed** | Build embedded Omni experiences with signed URLs, theming, iframe events, and permission-aware workflows. |

## Usage

How skills are invoked depends on your assistant, but the request patterns are
the same:

```text
"What topics are available in our Omni model?"                -> omni-model-explorer
"Run a query showing revenue by month"                        -> omni-query
"Add a customer tier dimension to the users view"             -> omni-model-builder
"Find the dashboard about sales performance"                  -> omni-content-explorer
"Build a dashboard showing revenue by month"                  -> omni-content-builder
"Improve the AI context on our orders topic"                  -> omni-ai-optimizer
"Give the marketing team access to the sales dashboard"       -> omni-admin
"Generate a signed embed URL for this dashboard"              -> omni-embed
```

## Documentation

- [Omni REST API Reference](https://docs.omni.co/api.md)
- [Omni Modeling Documentation](https://docs.omni.co/modeling.md)
- [Omni AI Optimization Guide](https://docs.omni.co/ai/optimize-models.md)
- [Omni MCP Server](https://docs.omni.co/ai/mcp.md)
- [skills.sh](https://skills.sh)

## Repository Structure

```text
omni-agent-skills/
├── .github/
│   └── scripts/
│       └── sync-upstream.sh
├── docs/
│   └── upstream-sync.md
└── plugins/
    └── omni-analytics/
        └── skills/
            ├── omni-model-explorer/
            │   └── SKILL.md
            ├── omni-query/
            │   └── SKILL.md
            ├── omni-model-builder/
            │   └── SKILL.md
            ├── omni-content-explorer/
            │   └── SKILL.md
            ├── omni-content-builder/
            │   └── SKILL.md
            ├── omni-ai-optimizer/
            │   └── SKILL.md
            ├── omni-admin/
            │   └── SKILL.md
            └── omni-embed/
                └── SKILL.md
```

## Contributing

If you are syncing from `exploreomni/omni-claude-skills`, see
`docs/upstream-sync.md` for the filtered history workflow used in this
repository.

## License

Apache 2.0

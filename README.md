# Omni Analytics Agent Skills

Reusable skills, agents, and rules for working with [Omni Analytics](https://omni.co) programmatically through Omni's REST APIs. Works across coding agents and LLM-powered developer tools that support the `SKILL.md` format.

## Installation

### Claude Code

From the marketplace (recommended):

```bash
/plugin marketplace add exploreomni/omni-agent-skills
```
```bash
/plugin install omni-analytics@omni-analytics
```

Or from Git URL:

```bash
/plugin marketplace add https://github.com/exploreomni/omni-agent-skills.git
```
```bash
/plugin install omni-analytics@omni-analytics
```

### Cursor

```
/add-plugin https://github.com/exploreomni/omni-agent-skills.git
```

### skills.sh / Codex

Install the full collection:

```bash
npx skills add exploreomni/omni-agent-skills
```

Install a specific skill:

```bash
npx skills add https://github.com/exploreomni/omni-agent-skills --skill omni-query
```

## Setup

Set these environment variables before using the skills:

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

API keys are created in **Settings > API Keys** (Organization Admin) or **User Profile > Manage Account > Generate Token** (Personal Access Token). Some skills, especially admin workflows, require an Organization API Key.

> **Token security**: These tokens can appear in terminal scrollback when used in shell commands. For team deployments, prefer a secrets manager or an MCP server wrapper where possible.

## What's Included

### Skills (8)

Skills activate automatically based on your request:

| Skill | Description |
|-------|-------------|
| **omni-model-explorer** | Discover and inspect models, topics, views, fields, dimensions, measures, and relationships |
| **omni-model-builder** | Create and edit views, topics, dimensions, measures, and relationships in YAML |
| **omni-query** | Run queries against Omni's semantic layer and interpret results |
| **omni-content-explorer** | Find, browse, and organize dashboards, workbooks, and folders |
| **omni-content-builder** | Create, update, and manage documents and dashboards programmatically — lifecycle, tiles, filters, layouts |
| **omni-ai-optimizer** | Optimize your Omni model for Blobby (Omni's AI assistant) |
| **omni-admin** | Manage connections, users, groups, permissions, schedules, and schema refreshes |
| **omni-embed** | Embed Omni dashboards in external applications — URL signing, themes, and postMessage events |

### Agents (3)

Specialized agents for complex multi-step workflows:

| Agent | Description |
|-------|-------------|
| **omni-analyst** | Explores models, runs queries, and delivers insights |
| **omni-modeler** | Builds semantic models, writes YAML, and optimizes for AI |
| **omni-admin-agent** | Manages users, permissions, schedules, and connections |

### Rules (3)

Always-available context applied when relevant:

| Rule | Description |
|------|-------------|
| **omni-api-conventions** | Auth headers, base URL patterns, error handling, pagination |
| **omni-yaml-conventions** | YAML file types, field syntax, dimension/measure patterns |
| **omni-terminology** | Maps business intelligence terms to Omni-specific vocabulary |

## Usage

Just ask naturally — skills, agents, and rules activate automatically:

```
"What topics are available in our Omni model?"          → omni-model-explorer
"Run a query showing revenue by month"                  → omni-query
"Add a new dimension for customer tier to the users view" → omni-model-builder
"Find the dashboard about sales performance"            → omni-content-explorer
"Build a dashboard showing revenue by month"            → omni-content-builder
"Improve the AI context on our orders topic"            → omni-ai-optimizer
"Give the marketing team access to the sales dashboard" → omni-admin
"Generate a signed embed URL for this dashboard"        → omni-embed
```

For complex workflows, invoke agents directly:

```
@omni-analyst What are our top 10 products by revenue this quarter?
@omni-modeler Add customer lifetime value metrics to the users view
@omni-admin-agent Set up weekly PDF delivery of the executive dashboard
```

## Team Deployment (Claude Code)

To make this plugin available to your entire team automatically, add it to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "omni-analytics": {
      "source": {
        "source": "github",
        "repo": "exploreomni/omni-agent-skills"
      }
    }
  },
  "enabledPlugins": ["omni-analytics@omni-analytics"]
}
```

When team members trust the repository folder, Claude Code automatically installs the marketplace and plugin.

## Updating

### Claude Code

Enable auto-updates:
1. Run `/plugin`
2. Go to **Marketplaces**
3. Select the marketplace → **Enable auto-update**

Or update manually from the `/plugin` menu.

### Cursor / skills.sh

Re-run the installation command to pull the latest version.

## Repository Structure

```
omni-agent-skills/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .cursor-plugin/
│   └── plugin.json
├── skills/
│   ├── omni-model-explorer/
│   ├── omni-query/
│   ├── omni-model-builder/
│   ├── omni-content-explorer/
│   ├── omni-content-builder/
│   ├── omni-ai-optimizer/
│   ├── omni-admin/
│   └── omni-embed/
├── agents/
│   ├── omni-analyst.md
│   ├── omni-modeler.md
│   └── omni-admin-agent.md
├── rules/
│   ├── omni-api-conventions.mdc
│   ├── omni-yaml-conventions.mdc
│   └── omni-terminology.mdc
├── assets/
│   └── logo.svg
├── README.md
└── LICENSE
```

## Documentation

- [Omni REST API Reference](https://docs.omni.co/api.md)
- [Omni Modeling Documentation](https://docs.omni.co/modeling.md)
- [Omni AI Optimization Guide](https://docs.omni.co/ai/optimize-models.md)
- [Omni MCP Server](https://docs.omni.co/ai/mcp.md)
- [skills.sh](https://skills.sh)

## Contributing

Contributions welcome! This is the single source of truth for all Omni Analytics agent skills. Please open an issue or PR.

## License

Apache 2.0

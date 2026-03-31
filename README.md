<p align="left">
  <img src="assets/omni-agent-skills-banner.svg" alt="Omni Agent Skills" width="480">
</p>

# Omni Analytics Agent Skills

Official [Omni Analytics](omni.co) skills for Claude Code, Cursor, Codex and other [skills.sh](skills.sh) compatible agents.

Bring governed Omni workflows directly into your agent environment with one install target for model exploration, querying, dashboard creation, semantic modeling, AI optimization, administration, and embed work.

## How It Works

These skills are not slash commands or one-off prompts you have to memorize. Once installed, the agent loads the relevant skill or agent when your request matches the use case.

- Ask in natural language for modeling, querying, dashboard, admin, or embed work
- Claude Code and Cursor can auto-load the right skills and agents
- Cursor can also apply the `.mdc` rules in this repo when relevant
- skills.sh-compatible agents such as OpenAI Codex, Gemini CLI, and GitHub Copilot can load the same skills

## Why This Repo

- One shared source of truth for Omni workflows across major agent surfaces
- 8 production-focused skills covering exploration, querying, modeling, content, admin, AI optimization, and embed
- 3 specialized agents for deeper multi-step work
- 3 Cursor rules for API, YAML, and terminology consistency

## Platform Support

| Platform | Install path | What loads automatically | Notes |
|----------|--------------|--------------------------|-------|
| Claude Code | Claude plugin marketplace or Git URL | 8 skills + 3 agents | Best fit for Claude-native plugin installs and team rollout |
| Cursor | Git URL plugin install | 8 skills + 3 agents + 3 `.mdc` rules | Includes Cursor rules support |
| skills.sh-compatible agents | `npx skills add` | 8 skills | Works with OpenAI Codex, Gemini CLI, GitHub Copilot, and other compatible runtimes |

## Installation

### Claude Code

Marketplace install (recommended, run separately):

```bash
/plugin marketplace add exploreomni/omni-agent-skills
```
```bash
/plugin install omni-analytics@omni-analytics
```

Git URL install (run separately):

```bash
/plugin marketplace add https://github.com/exploreomni/omni-agent-skills.git
```
```bash
/plugin install omni-analytics@omni-analytics
```

### Cursor

Install from Git URL:

```text
/add-plugin https://github.com/exploreomni/omni-agent-skills.git
```

### skills.sh-Compatible Agents

Use this path for agents that load skills through [skills.sh](https://skills.sh), including OpenAI Codex, Gemini CLI, GitHub Copilot, and other compatible agent runtimes.

Preview available skills:

```bash
npx skills add exploreomni/omni-agent-skills --list
```

Install the full collection:

```bash
npx skills add exploreomni/omni-agent-skills
```

Install one skill directly:

```bash
npx skills add https://github.com/exploreomni/omni-agent-skills --skill omni-query
```

Install globally:

```bash
npx skills add exploreomni/omni-agent-skills --global
```

Check for updates:

```bash
npx skills check
```

Update installed skills:

```bash
npx skills update
```

## Setup

Set these environment variables before using the skills:

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

API keys are created in **Settings > API Keys** (Organization Admin) or **User Profile > Manage Account > Generate Token** (Personal Access Token).

**Admin note**: Some workflows, especially schema refresh, permissions, schedules, and other admin operations, require an Organization API Key.

> **Token security**: These tokens can appear in terminal scrollback when used in shell commands. For team deployments, prefer a secrets manager or an MCP server wrapper where possible.

## What You Get

### Skills (8)

These activate from natural-language requests:

| Skill | Description |
|-------|-------------|
| **omni-model-explorer** | Discover and inspect models, topics, views, fields, dimensions, measures, and relationships |
| **omni-model-builder** | Create and edit views, topics, dimensions, measures, and relationships in YAML |
| **omni-query** | Run queries against Omni's semantic layer and interpret results |
| **omni-content-explorer** | Find, browse, and organize dashboards, workbooks, and folders |
| **omni-content-builder** | Create, update, and manage documents and dashboards programmatically - lifecycle, tiles, filters, layouts |
| **omni-ai-optimizer** | Optimize your Omni model for Blobby, Omni's AI assistant |
| **omni-admin** | Manage connections, users, groups, permissions, schedules, and schema refreshes |
| **omni-embed** | Embed Omni dashboards in external applications - URL signing, themes, and postMessage events |

### Agents (3)

These are built for heavier workflows where explicit delegation is useful:

| Agent | Description |
|-------|-------------|
| **omni-analyst** | Explores models, runs queries, and delivers insights |
| **omni-modeler** | Builds semantic models, writes YAML, and optimizes for AI |
| **omni-admin-agent** | Manages users, permissions, schedules, and connections |

### Cursor Rules (3)

These `.mdc` files are included for Cursor's rules system:

| Rule | Description |
|------|-------------|
| **omni-api-conventions** | Auth headers, base URL patterns, error handling, and pagination |
| **omni-yaml-conventions** | YAML file types, field syntax, and dimension and measure patterns |
| **omni-terminology** | Maps business intelligence terms to Omni-specific vocabulary |

> **Platform note**: Cursor loads the `rules/` directory automatically. Claude Code and skills.sh-compatible agents do not load these files as plugin rules, so outside Cursor they should be treated as shared reference material unless you copy them into that tool's own rule mechanism.

## Example Prompts

Ask naturally:

```text
"What topics are available in our Omni model?"
"Run a query showing revenue by month"
"Add a new dimension for customer tier to the users view"
"Find the dashboard about sales performance"
"Build a dashboard showing revenue by month"
"Improve the AI context on our orders topic"
"Give the marketing team access to the sales dashboard"
"Generate a signed embed URL for this dashboard"
```

For direct agent routing:

```text
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

### Cursor / skills.sh-Compatible Agents

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
│   ├── logo.svg
│   └── omni-agent-skills-banner.svg
├── README.md
└── LICENSE
```

## Documentation

- [Omni REST API Reference](https://docs.omni.co/api)
- [Omni Modeling Documentation](https://docs.omni.co/modeling)
- [Optimize Models for Omni AI](https://docs.omni.co/modeling/develop/ai-optimization)
- [Omni MCP Server](https://docs.omni.co/ai/mcp)
- [Claude Code Plugin Docs](https://code.claude.com/docs/en/plugins)
- [Cursor Plugin Docs](https://cursor.com/docs/plugins)
- [skills.sh](https://skills.sh)

## Contributing

Contributions welcome! This is the single source of truth for all Omni Analytics agent skills. Please open an issue or PR.

## License

Apache 2.0

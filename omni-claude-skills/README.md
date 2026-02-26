# Omni Analytics Plugin for Claude Code

A Claude Code plugin that helps analytics engineers and data teams work with [Omni Analytics](https://omni.co) programmatically through Omni's REST APIs.

## Installation

### From Marketplace (recommended)

```bash
/plugin marketplace add omni-co/omni-claude-skills
/plugin install omni-analytics@omni-analytics
```

### From Git URL

```bash
/plugin marketplace add https://github.com/omni-co/omni-claude-skills.git
/plugin install omni-analytics@omni-analytics
```

## Setup

After installation, set these environment variables:

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

API keys are created in **Settings > API Keys** (Organization Admin) or **User Profile > Manage Account > Generate Token** (Personal Access Token for Modeler/Connection Admin roles).

## Skills

This plugin includes 7 skills that Claude activates automatically based on your request:

| Skill | Description |
|-------|-------------|
| **omni-model-explorer** | Discover and inspect models, topics, views, fields, and relationships |
| **omni-model-builder** | Create and edit views, topics, dimensions, measures, and relationships in YAML |
| **omni-query** | Run queries against Omni's semantic layer and interpret results |
| **omni-content-explorer** | Find, browse, and organize dashboards, workbooks, and folders |
| **omni-content-builder** | Create, update, and manage documents and dashboards programmatically — lifecycle, tiles, filters, layouts |
| **omni-ai-optimizer** | Optimize your Omni model for Blobby (Omni's AI assistant) |
| **omni-admin** | Manage connections, users, groups, permissions, and schedules |

## Usage

Just ask Claude naturally — skills activate automatically:

```
"What topics are available in our Omni model?"          → omni-model-explorer
"Run a query showing revenue by month"                  → omni-query
"Add a new dimension for customer tier to the users view" → omni-model-builder
"Find the dashboard about sales performance"            → omni-content-explorer
"Build a dashboard showing revenue by month"             → omni-content-builder
"Improve the AI context on our orders topic"            → omni-ai-optimizer
"Give the marketing team access to the sales dashboard" → omni-admin
```

## Team Deployment

To make this plugin available to your entire team automatically, add it to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "omni-analytics": {
      "source": {
        "source": "github",
        "repo": "omni-co/omni-claude-skills"
      }
    }
  },
  "enabledPlugins": ["omni-analytics@omni-analytics"]
}
```

When team members trust the repository folder, Claude Code automatically installs the marketplace and plugin.

## Documentation

- [Omni REST API Reference](https://docs.omni.co/api)
- [Omni Modeling Documentation](https://docs.omni.co/modeling)
- [Omni AI Optimization Guide](https://docs.omni.co/ai/optimize-models)
- [Omni MCP Server](https://docs.omni.co/ai/mcp) (complementary — this plugin uses the REST API directly)
- [Claude Code Plugin Docs](https://code.claude.com/docs/en/plugins)

## Repository Structure

```
omni-claude-skills/
├── .claude-plugin/
│   └── marketplace.json              ← Marketplace catalog
├── plugins/
│   └── omni-analytics/
│       ├── .claude-plugin/
│       │   └── plugin.json           ← Plugin manifest
│       └── skills/
│           ├── omni-model-explorer/
│           │   └── SKILL.md
│           ├── omni-query/
│           │   └── SKILL.md
│           ├── omni-model-builder/
│           │   └── SKILL.md
│           ├── omni-content-explorer/
│           │   └── SKILL.md
│           ├── omni-content-builder/
│           │   └── SKILL.md
│           ├── omni-ai-optimizer/
│           │   └── SKILL.md
│           └── omni-admin/
│               └── SKILL.md
└── README.md
```

## Contributing

Contributions welcome! Please open an issue or PR.

## License

Apache 2.0

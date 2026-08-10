<p align="left">
  <img src="assets/omni-agent-skills-banner.svg" alt="Omni Agent Skills" width="480">
</p>

# Omni Analytics Agent Skills

Official [Omni Analytics](https://omni.co) skills for Claude Code, Cursor, OpenAI Codex, Snowflake Cortex Code, and other [skills.sh](https://skills.sh) compatible agents.

Bring governed Omni workflows directly into your agent environment with one install target for model exploration, querying, dashboard creation, semantic modeling, AI optimization, administration, and embed work.

## How It Works

These skills are not slash commands or one-off prompts you have to memorize. Once installed, the agent loads the relevant skill or agent when your request matches the use case.

- Ask in natural language for modeling, querying, dashboard, admin, or embed work
- Claude Code and Cursor can auto-load the right skills and agents
- Cursor can also apply the `.mdc` rules in this repo when relevant
- OpenAI Codex, Gemini CLI, and GitHub Copilot can load the same skills through [skills.sh](https://skills.sh)
- Snowflake Cortex Code can load the repo's `SKILL.md` directories as custom skills

## Why This Repo

- One shared source of truth for Omni workflows across major agent surfaces
- 9 production-focused skills covering exploration, querying, modeling, content, admin, AI optimization, AI eval, and embed
- 3 specialized agents for deeper multi-step work
- 3 Cursor rules for API, YAML, and terminology consistency

## Platform Support

| Platform | Install method | Notes |
|----------|----------------|-------|
| [Claude Code](https://claude.com/product/claude-code) | [Plugin marketplace or Git URL](#install-claude-code) | Full plugin install with 9 skills and 3 agents |
| [Cursor](https://cursor.com) | [Git URL plugin install](#install-cursor) | Full plugin install plus 3 `.mdc` rules |
| [OpenAI Codex](https://openai.com/codex/) | [`npx skills add`](#install-skills-sh-compatible-agents) | Uses the shared [skills.sh](https://skills.sh) install flow |
| [GitHub Copilot](https://github.com/features/copilot) | [`npx skills add`](#install-skills-sh-compatible-agents) | Uses the shared [skills.sh](https://skills.sh) install flow |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | [`npx skills add`](#install-skills-sh-compatible-agents) | Uses the shared [skills.sh](https://skills.sh) install flow |
| [Snowflake Cortex Code](https://www.snowflake.com/en/product/features/cortex-code/) | [Upload skill folders or copy into `.cortex/skills/`](#install-cortex-code) | Loads the repo's `SKILL.md` directories as custom skills |
| Other [skills.sh](https://skills.sh)-compatible agents | [`npx skills add`](#install-skills-sh-compatible-agents) | Same install flow as Codex, Copilot, and Gemini CLI |

## Installation

<a id="install-claude-code"></a>
### Claude Code

Marketplace install (recommended, run separately):

```bash
/plugin marketplace add exploreomni/omni-agent-skills
```
```bash
/plugin install omni-analytics@omni-analytics
```

To also install the integrations plugin (Snowflake Semantic Views, etc.):

```bash
/plugin install omni-integrations@omni-analytics
```

Git URL install (run separately):

```bash
/plugin marketplace add https://github.com/exploreomni/omni-agent-skills.git
```
```bash
/plugin install omni-analytics@omni-analytics
```

To also install the integrations plugin:

```bash
/plugin install omni-integrations@omni-analytics
```

<a id="install-cursor"></a>
### Cursor

Install from Git URL:

```text
/add-plugin https://github.com/exploreomni/omni-agent-skills.git
```

To also install the integrations plugin (Snowflake Semantic Views, etc.), use [Cursor's team marketplace import](https://cursor.com/docs/plugins) (Dashboard > Settings > Plugins > Import) with the repo URL `https://github.com/exploreomni/omni-agent-skills` — both `omni-analytics` and `omni-integrations` will appear as separate installable plugins.

<a id="install-cortex-code"></a>
### Cortex Code

Cortex Code can load these skills directly as custom skill folders. For the CLI, copy one or more folders from this repo's `skills/` directory into project-local `.cortex/skills/` or user-level `~/.snowflake/cortex/skills/`. In Snowsight workspaces, you can upload the same skill folders directly.

Install all repo skills in the current project:

```bash
mkdir -p .cortex/skills
cp -R skills/* .cortex/skills/
```

Install one skill directly:

```bash
mkdir -p .cortex/skills
cp -R skills/omni-query .cortex/skills/
```

Install the integrations skills (Snowflake Semantic Views, etc.):

```bash
mkdir -p .cortex/skills
cp -R skills/omni-integrations .cortex/skills/
```

<a id="install-skills-sh-compatible-agents"></a>
### skills.sh-Compatible Agents

Use this path for agents that load skills through [skills.sh](https://skills.sh), including [OpenAI Codex](https://openai.com/codex/), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [GitHub Copilot](https://github.com/features/copilot), and other compatible agent runtimes.

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

Install the integrations skills (Snowflake Semantic Views, etc.):

```bash
npx skills add https://github.com/exploreomni/omni-agent-skills --skill omni-integrations
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

## Migrating from Older Repos

This repo replaces two earlier, platform-specific repos that are now deprecated:

| Deprecated repo | Replacement |
|-----------------|-------------|
| [`exploreomni/omni-claude-skills`](https://github.com/exploreomni/omni-claude-skills) | Use the [Claude Code install](#install-claude-code) above |
| [`exploreomni/omni-cursor-plugin`](https://github.com/exploreomni/omni-cursor-plugin) | Use the [Cursor install](#install-cursor) above |

If you previously installed from either repo, uninstall the old plugin first, then follow the installation instructions above.

**Claude Code**

```bash
/plugin uninstall omni-analytics@omni-analytics
/plugin marketplace remove omni-claude-skills
```

**Cursor**

```text
/remove-plugin omni-cursor-plugin
```

Then follow the [installation instructions](#installation) above to install from this repo.

## Setup

### Install the Omni CLI

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh
```

This downloads the latest release, verifies the SHA-256 checksum, and installs the `omni` binary to `/usr/local/bin` (or `~/.local/bin` if not writable). Pre-built binaries for all platforms are also available on the [GitHub Releases page](https://github.com/exploreomni/cli/releases).

### Configure authentication

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, pick one and switch:
omni config use <profile-name>
```

If no profiles exist, run `omni config init` to create one interactively. You can also use `--profile`, `--base-url`, or `--token` flags to override the active profile for a single command.

API keys are created in **Settings > API Keys** (Organization Admin) or **User Profile > Manage Account > Generate Token** (Personal Access Token).

**Admin note**: Some workflows, especially schema refresh, permissions, schedules, and other admin operations, require an Organization API Key.

## What You Get

### omni-analytics — Skills (9)

These activate from natural-language requests:

| Skill | Description |
|-------|-------------|
| **omni-model-explorer** | Discover and inspect models, topics, views, fields, dimensions, measures, and relationships |
| **omni-model-builder** | Create and edit views, topics, dimensions, measures, and relationships in YAML |
| **omni-query** | Run queries against Omni's semantic layer and interpret results |
| **omni-content-explorer** | Find, browse, and organize dashboards, workbooks, and folders |
| **omni-content-builder** | Create, update, and manage documents and dashboards programmatically - lifecycle, tiles, filters, layouts |
| **omni-ai-optimizer** | Optimize your Omni model for Blobby, the Omni Agent |
| **omni-admin** | Manage connections, users, groups, permissions, schedules, and schema refreshes |
| **omni-embed** | Embed Omni dashboards in external applications - URL signing, themes, and postMessage events |
| **omni-ai-eval** | Evaluate AI query generation accuracy — run test prompts, compare results, and score across dimensions |

### omni-integrations — Skills (1)

| Skill | Description |
|-------|-------------|
| **omni-to-snowflake-semantic-view** | Convert an Omni Analytics topic into a Snowflake Semantic View YAML definition |

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

> **Platform note**: Cursor loads the `rules/` directory automatically. Claude Code, Cortex Code, and skills.sh-compatible agents do not load these files as plugin rules, so outside Cursor they should be treated as shared reference material unless you copy them into that tool's own rule mechanism.

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
"Convert this Omni topic to a Snowflake Semantic View"
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
  "enabledPlugins": ["omni-analytics@omni-analytics", "omni-integrations@omni-analytics"]
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

### Cursor / Cortex Code / skills.sh-Compatible Agents

Re-run the installation command or re-copy the updated `skills/` folders to pull the latest version.

### Getting the Latest Version

If your skills appear outdated, or the install command reports the plugin is "already installed" while skills aren't loading, your IDE may be serving a cached version. This can happen when the uninstall process doesn't fully clean up all registry and cache entries.

To ensure you're running the latest version, manually clear the stale plugin data and reinstall.

#### Claude Code

1. Edit `~/.claude/settings.json` and remove:
   - The `"omni-analytics@omni-analytics"` entry from `enabledPlugins`
   - The `"omni-analytics"` block from `extraKnownMarketplaces`

2. Edit `~/.claude/plugins/installed_plugins.json` and remove the `omni-analytics` entry

3. Edit `~/.claude/plugins/known_marketplaces.json` and remove the `omni-analytics` entry

4. Delete cached files:
   ```bash
   rm -rf ~/.claude/plugins/cache/omni-analytics/
   rm -rf ~/.claude/plugins/marketplaces/omni-analytics/
   ```

5. Reinstall the latest version:
   ```bash
   /plugin marketplace add exploreomni/omni-agent-skills
   /plugin install omni-analytics@omni-analytics
   /reload-plugins
   ```

#### Cursor

1. Remove the plugin:
   ```text
   /remove-plugin omni-analytics
   ```

2. Delete the cached plugin clone:
   ```bash
   rm -rf ~/.cursor/plugins/omni-analytics/
   ```

3. Reinstall the latest version:
   ```text
   /add-plugin https://github.com/exploreomni/omni-agent-skills.git
   ```

## Repository Structure

```
omni-agent-skills/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .cursor-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── skills/
│   ├── omni-model-explorer/
│   ├── omni-query/
│   ├── omni-model-builder/
│   ├── omni-content-explorer/
│   ├── omni-content-builder/
│   ├── omni-ai-optimizer/
│   ├── omni-ai-eval/
│   ├── omni-admin/
│   ├── omni-embed/
│   └── omni-integrations/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── .cursor-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── omni-to-snowflake-semantic-view/
├── agents/
│   ├── omni-analyst.md
│   ├── omni-modeler.md
│   └── omni-admin-agent.md
├── evals/
│   ├── README.md
│   ├── SETUP.md
│   ├── .env.example
│   ├── eval-env.json
│   ├── lib/
│   ├── runner.sh
│   ├── history.sh
│   ├── gepa_export.sh
│   ├── reset.sh
│   └── workspaces/
├── rules/
│   ├── omni-api-conventions.mdc
│   ├── omni-yaml-conventions.mdc
│   └── omni-terminology.mdc
├── assets/
│   ├── logo.svg
│   └── omni-agent-skills-banner.svg
├── CHANGELOG.md
├── README.md
└── LICENSE
```

### Layout Conventions

Skill packages stay compatible with the Agent Skills specification by keeping each skill's `SKILL.md` at the skill root. Supporting material lives beside it in focused subdirectories such as `references/`, `evals/`, `scripts/`, or `assets/`; keep references from `SKILL.md` shallow and relative to the skill root.

The root `evals/` directory is contributor tooling, not a distributed skill package. It is a thin BenchFlow wrapper and keeps public entrypoints at the top level:

```text
evals/runner.sh
evals/history.sh
evals/gepa_export.sh
evals/reset.sh
```

Implementation details are grouped by purpose:

| Path | Purpose |
|------|---------|
| `evals/lib/` | Python helpers used by the BenchFlow runner |
| `evals/.env.example` | Template for local model and Omni credentials |
| `evals/eval-env.json` | Template for instance-specific eval identifiers |
| `evals/workspaces/` | Generated BenchFlow tasks, jobs, trajectories, and summaries |
| `evals/history.sh` | CSV/JSONL export of timestamped BenchFlow summaries |
| `evals/gepa_export.sh` | GEPA trace export from completed BenchFlow runner workspaces |

Per-skill eval definitions live with the skill they evaluate and use BenchFlow's `cases` schema:

```text
skills/<skill>/evals/evals.json
```

## skills.sh Security Audits

This table is refreshed weekly by `.github/workflows/update-skills-security-audits.yml` from the public skills.sh audit pages.
Status labels use `🟢 Pass`, `🟡 Warn`, `🔴 Fail`, and `⚫ Error`.

<!-- skills-security-audits:start -->
| Skill | Gen Agent Trust Hub | Socket | Snyk |
|---|---|---|---|
| [omni-admin](https://www.skills.sh/exploreomni/omni-agent-skills/omni-admin) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-admin/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-admin/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-admin/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-ai-eval](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-eval) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-eval/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-eval/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-eval/security/snyk)<br>Apr 24, 2026, 11:15 PM |
| [omni-ai-optimizer](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-optimizer) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-optimizer/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-optimizer/security/socket)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-ai-optimizer/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-content-builder](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-builder) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-builder/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-builder/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-builder/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-content-explorer](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-explorer) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-explorer/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-explorer/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-content-explorer/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-embed](https://www.skills.sh/exploreomni/omni-agent-skills/omni-embed) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-embed/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-embed/security/socket)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-embed/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-model-builder](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-builder) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-builder/security/agent-trust-hub)<br>May 6, 2026, 04:43 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-builder/security/socket)<br>May 6, 2026, 04:44 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-builder/security/snyk)<br>May 6, 2026, 04:42 PM |
| [omni-model-explorer](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-explorer) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-explorer/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-explorer/security/socket)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-model-explorer/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-query](https://www.skills.sh/exploreomni/omni-agent-skills/omni-query) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-query/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-query/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-query/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-to-databricks-metric-view](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-databricks-metric-view) | [🔴 Fail](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-databricks-metric-view/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-databricks-metric-view/security/socket)<br>Apr 24, 2026, 11:16 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-databricks-metric-view/security/snyk)<br>Apr 24, 2026, 11:14 PM |
| [omni-to-snowflake-semantic-view](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-snowflake-semantic-view) | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-snowflake-semantic-view/security/agent-trust-hub)<br>Apr 24, 2026, 11:14 PM | [🟢 Pass](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-snowflake-semantic-view/security/socket)<br>Apr 24, 2026, 11:15 PM | [🟡 Warn](https://www.skills.sh/exploreomni/omni-agent-skills/omni-to-snowflake-semantic-view/security/snyk)<br>Apr 24, 2026, 11:14 PM |
<!-- skills-security-audits:end -->

## Documentation

- [Skill eval runbook](evals/README.md)
- [Skill eval instance setup](evals/SETUP.md)
- [Omni REST API Reference](https://docs.omni.co/api)
- [Omni Modeling Documentation](https://docs.omni.co/modeling)
- [Optimize Models for Omni AI](https://docs.omni.co/modeling/develop/ai-optimization)
- [Omni MCP Server](https://docs.omni.co/ai/mcp)
- [Claude Code Plugin Docs](https://code.claude.com/docs/en/plugins)
- [Cursor Plugin Docs](https://cursor.com/docs/plugins)
- [skills.sh](https://skills.sh)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidance, including skill and agent authoring, validation, evals, versioning, changelog entries, and PR expectations.

## License

Apache 2.0

# Contributing with Agents

This file provides guidance for AI agents (Claude Code, Cursor, Codex, etc.) working in this repository. It covers skill authoring conventions, validation requirements, plugin registration, and PR workflow. Read this before making changes.

## Repository Overview

```
omni-agent-skills/
├── skills/            # One directory per skill, each with a SKILL.md
├── agents/            # Agent definitions (*.md with frontmatter)
├── rules/             # Cursor .mdc rules (shared reference for other platforms)
├── evals/             # Eval harness for omni-ai-eval skill testing
├── .claude-plugin/    # Claude Code plugin metadata (plugin.json, marketplace.json)
└── .cursor-plugin/    # Cursor plugin metadata
```

Skills are loaded by agents when a user's request matches the `description` field in `SKILL.md`. Agents in `agents/` are invoked directly by name (e.g., `@omni-analyst`). Both are auto-discovered from their directories once the plugin is installed — no manual registration is required.

## Skill Authoring

Each skill lives in its own directory under `skills/` and must contain a `SKILL.md`.

### SKILL.md Frontmatter

```yaml
---
name: skill-name
description: One paragraph description of what this skill does and when to use it. Include natural-language trigger phrases — this is what the agent reads to decide whether to load the skill.
---
```

The `description` field is the primary routing signal. Write it to match how users naturally ask for this work. Include verb phrases like "use this skill whenever someone wants to..." and list representative trigger phrases.

### SKILL.md Body Conventions

Start with **Prerequisites** (Omni CLI check, env vars) and **Discovering Commands** (`omni <command> --help` examples). Organize the rest around the skill's domain — look at existing skills for patterns. Where there is non-obvious behavior, a bug, or a constraint an agent would otherwise learn the hard way, document it under a **Known Issues & Safe Defaults** section near the top.

Use CLI examples over raw API calls where the Omni CLI supports the operation. When using the REST API directly, include the auth header pattern (`-H "Authorization: Bearer $OMNI_API_TOKEN"`).

### Skill Directory Structure

```
skills/my-skill/
├── SKILL.md          # Required
├── references/       # Optional: reference docs, schemas, example responses
└── evals/            # Optional: eval test cases for this skill
```

## Agent Authoring

Agent definitions live in `agents/` as Markdown files with YAML frontmatter.

```yaml
---
name: agent-name
description: When to delegate to this agent. Be specific — this routes requests at the agent level.
---
```

Agent bodies should define:
- **Workflow** — numbered steps the agent follows, in order
- **Conventions** — behavioral defaults (e.g., default granularity, output format)
- **Skills You Should Use** — explicit list of skill names this agent relies on

Agents orchestrate skills — they do not duplicate skill content. If an agent needs to run a query, it invokes `omni-query`. Do not copy CLI examples or API patterns from skills into agent definitions.

## Plugins

Skills and agents are auto-discovered from `skills/` and `agents/` — no manifest registration needed. The plugin manifests (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and their `marketplace.json` counterparts) carry only plugin-level metadata: name, version, description, author.

This repo ships two plugins: `omni-analytics` at the root, and `omni-integrations` rooted at `skills/omni-integrations/`. Both are listed as separate entries in the root `.claude-plugin/marketplace.json` and `.cursor-plugin/marketplace.json`. New integrations skills go under `skills/omni-integrations/skills/`; new general skills go under `skills/`.

## Validation

Before opening a PR, validate that your skill or agent works against a real Omni instance:

1. **Install the Omni CLI** if not already present — see [README Setup](README.md#setup)
2. **Configure credentials**:
   ```bash
   export OMNI_BASE_URL="https://yourorg.omniapp.co"
   export OMNI_API_TOKEN="your-api-key"
   ```
3. **Run the key CLI commands** referenced in your skill — verify they succeed and return expected output
4. **For query or model skills**: run at least one realistic end-to-end operation (e.g., `omni query run`, `omni models yaml-create`)
5. **For content skills**: read back the created artifact to confirm it was written correctly — dashboard updates are full replacements, so verify nothing was lost

Do not mark a PR ready for review if the skill has only been tested with mocked or fabricated API responses.

### Evals

The `evals/` directory contains a harness for scoring AI query generation accuracy (`omni-ai-eval` skill). If you add or modify query-related skills, add eval cases under `skills/<skill-name>/evals/`. See `evals/SETUP.md` for the runner and grader workflow.

## Versioning

Bump the plugin version when **a user who already has the plugin installed would get different behavior after updating**. Ask: would an existing install change? If yes, bump. If no, skip it.

Examples that warrant a bump:
- A skill's `description` changed (affects when the skill loads)
- A skill's workflow, CLI commands, or defaults changed (affects what the agent does)
- A new skill or agent was added

Examples that do not warrant a bump:
- `AGENTS.md`, `README.md`, `CHANGELOG.md` — not loaded by the agent runtime
- Files in `evals/` or `references/` subdirectories — contributor tooling, not agent content
- Reformatting or rewording that doesn't change agent behavior

For the mechanics — which files to update, PATCH/MINOR/MAJOR breakdown, and changelog format — follow the [Versioning and Changelog](README.md#versioning-and-changelog) section of the README.

## PR Checklist

- [ ] SKILL.md frontmatter has a `name` and a `description` that routes correctly
- [ ] New skills go under the correct plugin (`skills/` for general, `skills/omni-integrations/skills/` for integrations)
- [ ] Skill validated end-to-end against a real Omni instance
- [ ] Eval cases added or updated if the change affects query behavior
- [ ] If skill or agent content changed: version bumped in all affected plugin manifests and `CHANGELOG.md` updated

## What to Avoid

- **Don't hallucinate CLI flags** — use `omni <command> --help` to discover real flags before writing skill content
- **Don't copy rules content into skills** — `omni-api-conventions` and `omni-yaml-conventions` are reference rules; link to them instead of duplicating

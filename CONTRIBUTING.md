# Contributing to Omni Analytics Agent Skills

This guide is the source of truth for contributor-facing policy: repository layout, skill and agent authoring, validation, evals, versioning, changelog entries, and PR expectations. The README is for users installing and using the repo; `AGENTS.md` is for agent-specific operating instructions; `evals/README.md` owns eval runner mechanics.

## Repository Layout

```text
omni-agent-skills/
├── skills/            # omni-analytics skills; one directory per skill
├── skills/omni-integrations/
│   └── skills/        # omni-integrations skills
├── agents/            # Agent definitions (*.md with frontmatter)
├── rules/             # Cursor .mdc rules
├── evals/             # BenchFlow eval harness and shared setup docs
├── .claude-plugin/    # Claude Code plugin metadata
├── .cursor-plugin/    # Cursor plugin metadata
├── CHANGELOG.md
├── README.md
└── AGENTS.md
```

New general Omni skills go under `skills/`. New integration-specific skills go under `skills/omni-integrations/skills/`. Skills, agents, and Cursor rules are auto-discovered from their directories; plugin manifests carry plugin-level metadata and version information only.

## Setup

Install and configure the Omni CLI before validating skill behavior:

```bash
omni config show
omni config use <profile-name>
```

If no profiles exist, run `omni config init`. Some workflows can also use explicit `--base-url "$OMNI_BASE_URL" --token "$OMNI_API_TOKEN"` flags, but examples should prefer the CLI profile flow unless the workflow specifically needs environment fallback.

Use a safe development environment. Prefer non-production data when testing modeling, content, admin, or eval workflows.

## Skill Authoring

Each skill lives in its own directory and must contain `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name
description: One paragraph description of what this skill does and when to use it. Include natural-language trigger phrases.
---
```

The `description` is the primary routing signal. Write it to match how users naturally ask for the work, using phrases such as "Use this skill whenever someone wants to..." and representative trigger phrases.

Start the body with **Prerequisites** and **Discovering Commands** sections. Use Omni CLI examples where the CLI supports the operation. When REST is necessary, include the auth header pattern:

```bash
-H "Authorization: Bearer $OMNI_API_TOKEN"
```

Put non-obvious constraints, current bugs, and safe defaults near the top under **Known Issues & Safe Defaults** so agents see them before workflow details.

Supporting material belongs beside the skill in focused subdirectories such as `references/`, `evals/`, `scripts/`, or `assets/`. Keep `SKILL.md` references shallow and relative to the skill root.

## Agent Authoring

Agent definitions live in `agents/` as Markdown files with YAML frontmatter:

```yaml
---
name: agent-name
description: When to delegate to this agent. Be specific.
---
```

Agent bodies should define:

- **Workflow**: numbered steps the agent follows
- **Conventions**: behavioral defaults, output format, and confirmation points
- **Skills You Should Use**: explicit companion skills

Agents orchestrate skills. Do not duplicate skill examples, CLI patterns, or API payloads inside agent definitions. If an agent needs to run a query, it should invoke `omni-query`; if it needs to modify model YAML, it should invoke `omni-model-builder`.

## Rule Authoring

Rules in `rules/` are Cursor-specific `.mdc` files. Keep them narrowly scoped to stable conventions that should be available in Cursor without loading a skill.

Do not copy rule content into skills. Link to rules as shared reference material when needed.

## Validation

Before opening a PR that changes skill or agent behavior, validate against a real Omni instance:

1. Install and configure the Omni CLI.
2. Run the key CLI commands referenced in the changed skill or agent.
3. For query or model skills, run at least one realistic end-to-end operation, such as `omni query run` or `omni models yaml-create`.
4. For content skills, read back the created or updated artifact. Dashboard updates are full replacements, so verify nothing was lost.
5. For admin changes, verify permissions and read back the changed user, group, schedule, permit, or connection state where the CLI supports it.

Do not mark a PR ready for review if the behavior has only been tested with mocked or fabricated API responses.

Run `git diff --check` before requesting review.

## Evals

The root `evals/` directory is contributor tooling, not a distributed skill package. `evals/README.md` owns BenchFlow setup, runner commands, reset flows, fixture notes, and export mechanics.

If you add or modify query-related skill behavior, add or update BenchFlow `cases` under the affected skill:

```text
skills/<skill-name>/evals/evals.json
```

Use the shared eval instance setup in `evals/SETUP.md` when a case depends on mutable Omni fixtures.

## Staying in Sync with the Omni CLI

The skills document CLI commands, so a CLI release can silently invalidate
them — a removed command leaves prose pointing at something that now 404s, and
a new command leaves agents working around a gap that has since been filled.

`.github/workflows/sync-cli-changes.yml` handles this. It runs the procedure in
`.claude/agents/sync-cli-changes.md` against a release, installs that release's
binary on the runner, and opens a sync PR if anything in the repo is affected.

It is triggered three ways:

| Trigger | When |
|---|---|
| `repository_dispatch` (`cli-update`) | Preferred — `exploreomni/cli` dispatches on release |
| `schedule` (daily) | Fallback — picks up a release whose dispatch never arrived |
| `workflow_dispatch` | Manual, for a specific tag or to re-run a sync |

The daily poll exists because the dispatch is a cross-repo dependency that can
break silently on either side; without it, a missed dispatch means the drift is
only found when someone hits a stale command. After each run the workflow pushes
a `cli-synced/<tag>` marker tag, and skips any tag that already has one — a
release needing no skill changes produces no PR, so a PR check alone would let
the poll reconsider it every day.

It needs one repository secret, `SYNC_REVIEW_TOKEN`, used only to comment
`/review` on the sync PR. Reading `exploreomni/cli` needs no secret — the repo
is public, so the built-in `GITHUB_TOKEN` covers it.

`SYNC_REVIEW_TOKEN` is required because `skill-review.yml` triggers on
`issue_comment`, and GitHub does not start workflow runs from events created
with `GITHUB_TOKEN`. Commenting with the default token posts the comment and
silently triggers nothing.

The review comment is best-effort and never fails the job: if the secret is
unset, or set but rejected — a fine-grained token awaiting org approval looks
exactly like this — the workflow logs a warning naming the PR to review by
hand. The `cli-synced/<tag>` marker is pushed *before* the comment is
attempted, so a review that could not be requested never costs the record of
the sync having run.

> **Fine-grained PATs expire.** `DOCS_REPO_TOKEN` (used by `notify-docs.yml`)
> lapsed in early August 2026 and the workflow failed silently on every push
> for a month. Prefer the built-in token wherever a repo is public, and when a
> PAT is unavoidable, note its expiry.

To run a sync by hand, install the release you are syncing to and follow
`.claude/agents/sync-cli-changes.md`. The installed binary is the source of
truth: verify every command with `--help` and every body shape with `--schema`
before documenting it. Release notes tell you where to look, not what is true.

`.claude/agents/` holds maintenance agents. The marketplace entry installs from
the repo root, so these files travel with the plugin, but Claude Code loads a
plugin's user-facing agents from `agents/` — so they are not loaded as agents for
plugin users, and are not counted in the plugin description.

## Versioning and Changelog

Bump the affected plugin version when a user who already has the plugin installed would get different behavior after updating.

Examples that warrant a bump:

- a skill `description` changes, affecting when it loads
- a skill or agent workflow, CLI command, API payload, or default changes
- a new skill or agent is added
- plugin metadata that users see changes

Examples that usually do not warrant a bump:

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, or `CHANGELOG.md` only
- files in `evals/` or `references/` only
- reformatting or rewording that does not change agent behavior

Use semantic versioning:

| Change type | Version component |
|---|---|
| Bug fixes, clarifications, doc corrections | `PATCH` |
| New skills, new features, behavior changes | `MINOR` |
| Breaking changes to existing skill behavior | `MAJOR` |

Only bump the plugin whose behavior changed. A fix to `omni-integrations` does not require bumping `omni-analytics`.

Keep duplicated version metadata in sync:

- `omni-analytics`: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`
- `omni-integrations`: `skills/omni-integrations/.claude-plugin/plugin.json`, `skills/omni-integrations/.cursor-plugin/plugin.json`, `.claude-plugin/marketplace.json` (`omni-integrations` entry), `.cursor-plugin/marketplace.json` (`omni-integrations` entry)

Document user-visible changes in `CHANGELOG.md` under the affected version. Use `Added`, `Changed`, and `Fixed` sections. The date should be the release date, not necessarily the commit date.

```markdown
## [1.3.0] - YYYY-MM-DD

### omni-analytics

**Added**
- Description of new capability

**Changed**
- Description of behavior change

**Fixed**
- Description of bug fix
```

Version bumps and changelog entries should be included in the same PR as the behavior change, not batched separately after the fact.

## PR Checklist

- [ ] Skill or agent frontmatter routes correctly
- [ ] New skills are under the correct plugin directory
- [ ] CLI commands and flags were checked with `omni <command> --help` where relevant
- [ ] Behavior was validated end-to-end against a real Omni instance where relevant
- [ ] Eval cases were added or updated if query behavior changed
- [ ] Affected plugin manifests were version bumped if distributed behavior changed
- [ ] `CHANGELOG.md` was updated if distributed behavior changed
- [ ] `git diff --check` passes

## What to Avoid

- Do not hallucinate CLI flags. Use `omni <command> --help` before documenting commands.
- Do not prefer raw API examples when the Omni CLI supports the operation.
- Do not duplicate rule content in skills or agent definitions.
- Do not add a manifest registration step for skills or agents; directories are auto-discovered.
- Do not mark real-instance validation complete when only mocked responses were used.

## License

By contributing to this repository, you agree that your contributions will be licensed under the same license as the project.

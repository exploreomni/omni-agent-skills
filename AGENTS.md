# Contributing with Agents

This file contains agent-specific operating instructions for this repository. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for contributor policy: skill and agent authoring, validation, evals, versioning, changelog entries, and PR expectations.

## Before Editing

- Read the relevant existing skill, agent, rule, README, or eval file before changing it.
- Keep edits scoped to the requested workflow and the repository's current patterns.
- Use `rg`/`rg --files` for repository searches.
- Respect dirty worktrees. Do not revert changes you did not make.
- Keep an addition proportional to a mistake that has actually happened. A line in a doc for a mistake nobody has made yet beats a CI check for it.

## Repository Routing

Every file in this repo is one of the nouns below. Each noun has one place in the tree and one job at runtime, so the folder tells you where a change goes and who will see it.

| Noun | Lives at | Job at runtime | Never holds |
|---|---|---|---|
| Skill | `skills/<name>/SKILL.md` (general) or `skills/omni-integrations/skills/<name>/SKILL.md` (integration) | Loaded when a request matches its `description`, which is the routing signal | Agent orchestration or Cursor rule content |
| Reference | `skills/<name>/references/*.md` | Read only when `SKILL.md` points at it, so it costs nothing until needed | Constraints the skill needs on every run; those go near the top of `SKILL.md` |
| Agent | `agents/<name>.md` | Delegated to for multi-step work; orchestrates skills | CLI examples, API payloads, or duplicated skill steps |
| Maintenance agent | `.claude/agents/<name>.md` | Run by a GitHub workflow or by hand during a release; plugin users never load it | User-facing workflows |
| Rule | `rules/<name>.mdc` | Cursor only, applied by glob or always-on without loading a skill | Workflow steps; Claude Code users never see rules |
| Eval case | `skills/<name>/evals/evals.json`, plus out-of-scope prompts in `evals/ci/negative-cases.json` | Run by CI and the BenchFlow suite; never distributed | Content an agent should read while working |
| Eval tooling | `evals/` | Contributor tooling; part of neither plugin | Skill or agent content |
| Version | `versions.json` | Stamped into the plugin manifests by `.github/scripts/stamp_versions.py` | Hand edits to the manifests |

Skills, agents, and rules are auto-discovered from their directories. Do not add manifest registration for individual skills or agents.

## Command and Content Rules

- Do not hallucinate CLI flags. Run `omni <command> --help` before documenting or relying on a command shape.
- Use Omni CLI examples where the CLI supports the operation.
- When REST is necessary, use the bearer-token pattern documented in `CONTRIBUTING.md`.
- Do not copy Cursor rule content into skills or agent definitions. Link to rules as reference material when needed.

## Validation and Release

- Validate behavior-changing skill or agent updates against a real Omni instance before marking the work ready.
- Add or update BenchFlow eval cases when query-related behavior changes.
- If distributed skill or agent behavior changes, update the affected plugin versions and `CHANGELOG.md` in the same PR.
- After changing `versions.json`, run `python3 .github/scripts/stamp_versions.py` and commit the generated manifests in that same PR. CI checks them; it does not create a follow-up PR.
- Documentation-only changes to `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CHANGELOG.md`, `evals/`, or a skill's `references/` usually do not need a version bump unless they change agent runtime behavior.

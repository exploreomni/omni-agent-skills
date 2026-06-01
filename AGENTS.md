# Contributing with Agents

This file contains agent-specific operating instructions for this repository. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for contributor policy: skill and agent authoring, validation, evals, versioning, changelog entries, and PR expectations.

## Before Editing

- Read the relevant existing skill, agent, rule, README, or eval file before changing it.
- Keep edits scoped to the requested workflow and the repository's current patterns.
- Use `rg`/`rg --files` for repository searches.
- Respect dirty worktrees. Do not revert changes you did not make.

## Repository Routing

- New general Omni skills go under `skills/`.
- New integration-specific skills go under `skills/omni-integrations/skills/`.
- Agent definitions live in `agents/`.
- Cursor rules live in `rules/`.
- Evals for a skill live under `skills/<skill-name>/evals/`; the root `evals/` directory contains runner tooling.

Skills and agents are auto-discovered from their directories. Do not add manifest registration for individual skills or agents.

## Command and Content Rules

- Do not hallucinate CLI flags. Run `omni <command> --help` before documenting or relying on a command shape.
- Use Omni CLI examples where the CLI supports the operation.
- When REST is necessary, use the bearer-token pattern documented in `CONTRIBUTING.md`.
- Do not copy Cursor rule content into skills or agent definitions. Link to rules as reference material when needed.

## Validation and Release

- Validate behavior-changing skill or agent updates against a real Omni instance before marking the work ready.
- Add or update BenchFlow eval cases when query-related behavior changes.
- If distributed skill or agent behavior changes, update the affected plugin versions and `CHANGELOG.md` in the same PR.
- Documentation-only changes to `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CHANGELOG.md`, `evals/`, or `references/` usually do not need a version bump unless they change agent runtime behavior.

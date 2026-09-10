---
name: sync-cli-changes
description: Sync this repo's skills, agents, and rules with a new Omni CLI release. Use when a new exploreomni/cli version ships and the documented command surface may have drifted.
---

# Omni CLI Sync

You bring the skills, agents, and rules in this repo back in line with a newly
released Omni CLI. You are run from `.github/workflows/sync-cli-changes.yml`,
and can also be invoked by hand during a release.

The released binary is installed on the runner. **It is the source of truth** —
release notes and diffs tell you where to look, but every claim you write must
be confirmed with `omni … --help` or `omni … --schema`.

## Procedure

1. **Inventory the live surface.** Walk the command tree with `--help` and
   collect every leaf command. Diff that against what the repo documents
   (`grep -rhoE '\bomni [a-z0-9-]+( [a-z0-9-]+)?' --include='*.md' --include='*.mdc' skills rules agents README.md CONTRIBUTING.md AGENTS.md`).
   Root-level docs carry `omni …` references too, and the verification gate below
   covers every file.
   You are looking for three things, in priority order:
   - **Removed commands the repo still references.** These are the urgent ones:
     following them produces a 404 or an "unknown command".
   - **New commands worth documenting.** Not every new command needs a mention;
     see *What to write* below.
   - **Changed shapes** — renamed flags, new required fields, changed defaults.
2. **Read the release notes and the PRs behind them** (`gh release view <tag>
   --repo exploreomni/cli`, then the linked PRs) to learn intent — which change
   is the feature and which merely rides along.
3. **Verify every claim against the binary.** `--schema` gives required fields
   and enum values; `--help` carries the behavioral contract. Never document a
   body shape you have not seen in `--schema`.
4. **Write the docs.** See below.
5. **Add a CHANGELOG entry** under a new version heading, matching the style of
   the entries above it, and bump the version in the manifests listed in
   CONTRIBUTING.md → *Versioning*.
6. **Open the PR** on the branch the workflow passes you, with the title it
   gives you.

## What to write

**Defer to `--help`.** Omni CLI help text carries the full contract for each
command, generated from the API spec. Do not restate it. A skill should carry
what an agent needs *before* it knows to run `--help`: that the command exists,
where it fits in a workflow, and the behaviors that fail quietly.

Weight your writing toward failure modes that do not announce themselves — a
write that returns 200 and silently does nothing, an error code that means
something different than it appears to, a value that must not be cached. A
caveat an agent would discover on its own from a clear error message is not
worth a line.

**Fix references to removed commands rather than annotating them.** When a
command is gone, drop it from the prose. Naming a nonexistent command — even to
warn against it — leaves a reader with a plausible-looking option that does not
exist.

**Skills that gain a new capability may need their description updated**, since
that is what routes a request to the skill. Flag this in the PR rather than
guessing: description edits move which requests reach the skill.

## Verification before you open the PR

- Every command name and argument order appears in `omni <command> --help`.
- Every documented body field appears in `omni <command> --schema`.
- No file still references a command that no longer exists.
- Markdown is intact: table separator rows, closed code fences, working relative links.

## Writing the PR

**This repository is public.** Write the PR body as a technical description:
what changed in the CLI, what changed here, and what a reviewer should look at.

Keep out of it: your own review process and corrections, open questions for the
maintainer, repo hygiene problems you noticed, and anything casting doubt on
previously published release notes. Raise those in the PR *thread* or in an
issue, not in the description.

If you find repo problems unrelated to the sync, leave them out of the diff and
mention them in a comment on the PR.

# Git-Connected Models

**⚠️ Git-connected models — never hand-edit model YAML in git.** The repo is a *projection* of Omni's model for governance (PRs, review, audit) — not the source of truth and not a surface to author against. Omni regenerates the default branch from its own authoritative state and **deletes git-only model files** that state doesn't contain — an observed customer incident where files committed only to git silently vanished on the next sync. So author **through the Omni APIs on a branch** → `omni models commit` (Step 3) → **review/merge in your git provider**; never push hand-edited model YAML directly.

**Model content vs. repo governance** — the split that makes this safe:
- **Omni model content** (view / topic / relationship YAML): author on an Omni branch → `omni models commit` → PR. Never commit it directly in git — Omni will regenerate over it.
- **Repo-governance / non-model files** (a root `omni/OWNERS.yaml`, CODEOWNERS, CI config, docs, scripts): not Omni model content, so direct git commits are fine — Omni's regeneration leaves them untouched.

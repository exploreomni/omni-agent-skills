#!/usr/bin/env bash
# automation/stamp-versions is generated; do not put manual edits on it.
set -euo pipefail

branch=automation/stamp-versions
git fetch origin main
previous=$(git ls-remote origin "refs/heads/$branch" | cut -f1)
git checkout -B "$branch" origin/main
python3 .github/scripts/stamp_versions.py
if git diff --quiet; then
  echo "Manifests already match versions.json."
  exit 0
fi
python3 .github/scripts/stamp_versions.py --check
version=$(python3 -c 'import json; print(json.load(open("versions.json"))["version"])')
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -- .claude-plugin/*.json .cursor-plugin/*.json \
  skills/omni-integrations/.claude-plugin/*.json \
  skills/omni-integrations/.cursor-plugin/*.json
git commit -m "chore: stamp plugin manifests at $version"
# Refresh only the dedicated generated branch, and reject concurrent updates.
git push --force-with-lease="refs/heads/$branch:$previous" origin "HEAD:refs/heads/$branch"

body_file=$(mktemp)
trap 'rm -f "$body_file"' EXIT
cat > "$body_file" <<EOF
Stamp all plugin manifest versions at $version from versions.json.

Generated from main by the Versions workflow. Review and merge this PR to
publish the manifest update; main's branch protections remain in effect.

Validation: stamp_versions.py --check passes. The workflow explicitly starts
Versions and Skills CI on this branch to supply the required checks without
depending on automatic workflow runs from GITHUB_TOKEN events.

This branch is generated and may be replaced by later stamping runs.
EOF
pr=$(gh pr list --base main --head "$branch" --state open --json number --jq '.[0].number // empty')
if [ -n "$pr" ]; then
  gh pr edit "$pr" --title "chore: stamp plugin manifests at $version" --body-file "$body_file"
else
  gh pr create --base main --head "$branch" \
    --title "chore: stamp plugin manifests at $version" --body-file "$body_file"
fi
# Dispatch events run with GITHUB_TOKEN. Ordinary bot pushes do not start CI
# automatically; bot PR events may require a maintainer to approve the run.
gh workflow run versions.yml --ref "$branch"
gh workflow run skills-ci.yml --ref "$branch"

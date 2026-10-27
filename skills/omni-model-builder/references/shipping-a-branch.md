# Shipping a Branch

Ask the user before shipping, and ship only after validation and testing pass. After either path, verify the result: [post-merge-verification.md](post-merge-verification.md).

Check whether the model is git-connected — `omni models git-get <modelId>`. A config with `sshUrl` / `baseBranch` → git-connected → **Path A** (open/update a PR); a `404`/no config → not git-connected → **Path B** (merge directly in Omni).

## Path A — Git-connected: open or update a PR

Push the branch contents to git. Creates a new git branch + PR if one doesn't exist; otherwise updates the existing PR:

```bash
omni models commit <modelId> --body '{
  "branch_id": "<branchId>",
  "commit_message": "Add my_new_view with status dimension and count measure"
}'
```

Surface the returned `pr_url` to the user, with a link to the branch in the Omni IDE: `https://<instance>/models/<modelId>/ide?branchId=<branchId>&mode=staged` (the shared model's ID in the path; `mode=staged` shows only the branch's changes). `omni models commit` doesn't write the PR description, so once the PR exists and you can edit it (for example `gh pr edit <pr_url> --body-file <file>`), add that link to its description so reviewers can open the branch in Omni. The reviewer merges the PR in your git host; changes flow back to `baseBranch` on the next sync. Run `omni models commit --help` for optional body flags (`allow_branch_exists`, `require_branch_exists`) when you need to enforce open-only or update-only behavior.

## Path B — Not git-connected: merge in Omni

When you ask the user to confirm the merge, include the branch's IDE link (the URL in Path A) so they can review the changes in Omni first.

```bash
omni models merge-branch <modelId> <branchName>
```

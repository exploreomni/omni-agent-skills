# Upstream Sync

This repository vendors filtered history from `exploreomni/omni-claude-skills`.

Imported history excludes these paths:

- `.claude-plugin/`
- `plugins/omni-analytics/.claude-plugin/`
- `README.md`

That means the imported branch keeps the commit history for the files we retain,
but the commit SHAs differ from the source repository because the history is
rewritten during filtering.

## Syncing

Run the sync script from the repository root on a clean working tree:

```bash
bin/sync-upstream
```

To sync from a local checkout instead of GitHub:

```bash
bin/sync-upstream --source /Users/ernesto/dev/omni-claude-skills
```

To sync a different source ref:

```bash
bin/sync-upstream --ref main
```

The script:

1. Clones the source repository into a temporary directory.
2. Rewrites that temporary clone to drop the excluded paths from every commit.
3. Updates the local `vendor/omni-claude-skills` branch with the filtered history.
4. Merges the filtered vendor branch into the currently checked out branch.

`README.md` is intentionally local to this repository. If you want upstream
documentation here, add it in a separate file rather than trying to partially
merge the upstream README.

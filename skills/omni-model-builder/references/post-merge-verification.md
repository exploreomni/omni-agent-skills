# After the merge — verify net-new topics and views (both paths)

After the merge, Omni regenerates the default branch from its own (authoritative) model state — re-serializing to canonical form, and adding a normalization commit only when the merged git content *differs* from that state. Content authored through the Omni APIs is already canonical, so a clean merge often adds **no extra commit** — don't go hunting for one; verify by resolution instead. (A non-git merge promotes the branch into the shared model.) Either way — and **especially for net-new topics or views** — confirm the files resolve against the **production** model (no `--branch-id`):

```bash
# 1. Files resolve in production — the new view appears / the new topic resolves
omni models get-views <modelId>                 # new view is listed
omni models get-topic <modelId> <topicName>     # new topic resolves (base_view_name + join_via_map present)

# 2. Production model validates — no blocking errors (any is_warning:false is blocking)
omni models validate <modelId>

# 3. Run at least one semantic query against the new topic/view
omni query run --body '{"query":{"modelId":"<modelId>","table":"<base_view>","fields":["<base_view>.<field>"],"limit":10,"join_paths_from_topic_name":"<topicName>"}}'
```

In the query response, confirm `summary.missing_fields` is `[]` (and `summary.invalid_calculations` is empty — note it comes back as `{}`, not `[]`). A non-empty `missing_fields` means a field didn't resolve — the signature of a model file dropped or renamed during the merge. If anything is missing, re-author it through Omni; never patch it back by hand in git.

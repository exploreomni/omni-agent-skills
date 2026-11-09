# AI Model Suggestions Commands

```bash
# Start a run, then read it
omni ai-model-suggestions model-suggestions-generate <modelId>
omni ai-model-suggestions model-suggestions-run-latest <modelId>
omni ai-model-suggestions model-suggestions-run-get <modelId> <runId>

# List and manage suggestions
omni ai-model-suggestions model-suggestions-list <modelId>                   # --status active (default) | ignored | all
omni ai-model-suggestions model-suggestions-ignore <modelId> <suggestionId>
omni ai-model-suggestions model-suggestions-restore <modelId> <suggestionId>
omni ai-model-suggestions model-suggestions-delete <modelId> <suggestionId>

# Daily schedule
omni ai-model-suggestions model-suggestions-schedule-enable <modelId>
omni ai-model-suggestions model-suggestions-schedule-disable <modelId>
```

- `<modelId>` is a shared model.
- Generating and the schedule need organization admin permissions. A model has at most one active run, with a cooldown after a run completes.
- Runs work from chat sessions in the last 30 days that carry feedback or other quality signals.
- A suggestion only proposes `ai_context` (on the model, a topic, a view or a field), or a field's `description`, `synonyms` or `sample_values`. To apply one, make the change on a branch with `omni models yaml-create`. The suggestion stays listed until a later run sees the change.

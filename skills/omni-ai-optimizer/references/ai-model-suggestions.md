# AI Model Suggestions Commands

```bash
# Kick off a generation run, then read it back
omni ai-model-suggestions model-suggestions-generate <modelId>
omni ai-model-suggestions model-suggestions-run-latest <modelId>
omni ai-model-suggestions model-suggestions-run-get <modelId> <runId>

# Work the suggestion list
omni ai-model-suggestions model-suggestions-list <modelId>
omni ai-model-suggestions model-suggestions-ignore <modelId> <suggestionId>
omni ai-model-suggestions model-suggestions-restore <modelId> <suggestionId>
omni ai-model-suggestions model-suggestions-delete <modelId> <suggestionId>

# Recurring generation
omni ai-model-suggestions model-suggestions-schedule-enable <modelId>
omni ai-model-suggestions model-suggestions-schedule-disable <modelId>
```

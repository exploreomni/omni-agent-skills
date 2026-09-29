# Cache and Validation

```bash
# Reset cache policy
omni models cache-reset <modelId> <policyName> --body '{ "resetAt": "2025-01-30T22:30:52.872Z" }'

# Content validator (find broken field references across all dashboards and tiles)
# Useful for blast-radius analysis: remove a field on a branch, then run the
# validator against that branch to see what content would break.
# See the Field Impact Analysis section in omni-model-explorer for the full workflow.
omni models content-validator-get <modelId>

# Run against a specific branch (e.g., after removing a field)
omni models content-validator-get <modelId> --branch-id <branchId>

# On large content the validator may only check references; plan every query (slower)
omni models content-validator-get <modelId> --force-full-validation true

# Git configuration
omni models git-get <modelId>
```

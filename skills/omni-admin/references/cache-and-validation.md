# Cache and Validation

```bash
# Reset cache policy
omni models cache-reset <modelId> <policyName> --body '{ "resetAt": "2025-01-30T22:30:52.872Z" }'

# Content validator (find broken field references across all dashboards and tiles)
# Useful for blast-radius analysis: remove a field on a branch, then run the
# validator against that branch to see what content would break.
# See the Field Impact Analysis section in omni-model-explorer for the full workflow.
# The default filter mode (ALL) returns every document with a query, broken or not;
# WITH_ISSUES returns only broken content, so an empty `content` array means nothing breaks.
omni models content-validator-get <modelId> --content-filter-mode WITH_ISSUES

# Run against a specific branch (e.g., after removing a field)
omni models content-validator-get <modelId> --branch-id <branchId> --content-filter-mode WITH_ISSUES

# On large content the validator may only check references; plan every query (slower)
omni models content-validator-get <modelId> --force-full-validation true

# Git configuration
omni models git-get <modelId>
```

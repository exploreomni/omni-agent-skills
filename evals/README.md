# Skill Eval Framework

Measure whether an Omni agent skill actually improves agent performance. Each eval runs the same prompts **with** and **without** a skill's `SKILL.md` injected as a system prompt, then scores the outputs using assertion-based grading. This produces an A/B comparison with pass rates, token usage, and time metrics.

## Quick Start

```bash
# Run all scenarios for a single skill
./evals/runner.sh --skill omni-model-explorer

# Run a specific scenario
./evals/runner.sh --skill omni-model-explorer --scenario list-models

# Run with more repetitions for statistical significance
./evals/runner.sh --skill omni-model-explorer --runs 5

# Only run the "with-skill" config
./evals/runner.sh --skill omni-model-explorer --config-only with-skill

# Run all evals for all skills
./evals/runner.sh --all

# Score an existing results directory manually
./evals/scorer.sh evals/results/2026-04-15-omni-model-explorer/
```

## Dependencies

| Tool | Install | Purpose |
|------|---------|---------|
| `claude` | [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | Run headless agent sessions |
| `yq` | `brew install yq` | Parse YAML scenario files |
| `jq` | `brew install jq` | Parse JSON run outputs |
| `bc` | Pre-installed on macOS | Arithmetic in scorer |

## Scenario YAML Format

Each skill has a scenario file at `evals/scenarios/<skill-name>.eval.yaml`:

```yaml
skill: omni-model-explorer
description: What this eval measures.

scenarios:
  - id: list-models
    prompt: "The prompt sent to the agent"
    assertions:
      - type: tool_called
        pattern: "omni models list"
        description: "The agent ran omni models list"
      - type: output_contains
        value: "SHARED"
        description: "Output mentions SHARED model kind"
```

### Assertion Types

| Type | Parameters | Behavior |
|------|-----------|----------|
| `tool_called` | `pattern` | Check if any Bash tool call contains the pattern substring |
| `output_contains` | `value` | Case-insensitive substring check on output text |
| `output_contains_all` | `values` (list) | All values must be present (case-insensitive) |
| `output_contains_any` | `values` (list) | At least one value must be present |
| `output_not_contains` | `value` | Value must NOT be present |
| `output_regex` | `pattern` | `grep -iE` match against output |
| `output_count_gte` | `pattern`, `min_count` | Count pattern occurrences >= min_count |
| `llm_judge` | `criteria` | Calls Claude Haiku to score PASS/FAIL based on criteria |
| `step_count_lte` | `max_steps` | Check that num_turns <= max_steps |

Every assertion should include a `description` field for human-readable reporting.

## Adding Evals for a New Skill

1. Create a scenario file at `evals/scenarios/<skill-name>.eval.yaml`
2. Define the `skill` field to match the directory name under `skills/`
3. Write scenarios with prompts that test the skill's core capabilities
4. Add assertions that verify the agent used the right tools and produced correct output
5. Run: `./evals/runner.sh --skill <skill-name>`

Design tips:
- Write prompts that a real user would ask, not prompts that game the eval
- Use `tool_called` assertions to verify the agent used the right CLI commands
- Use `llm_judge` for nuanced checks that substring matching can't handle (e.g., "did the agent fabricate data?")
- Use `output_not_contains` to catch common failure modes like hallucination
- Start with 3 runs per config; increase to 5+ for publishing results

## How Scoring Works

The scorer reads each run's JSON output and evaluates all assertions against it. It computes:

- **Per-run**: Which assertions passed/failed, pass rate, tokens, time
- **Per-scenario per-config**: Aggregate pass rate across runs, per-assertion pass rates
- **Per-config summary**: Mean pass rate (with std deviation), mean tokens, mean time
- **Delta**: Difference between with-skill and without-skill on all metrics

Results are written to `scores.json` in the results directory and a summary table is printed to stdout.

## Results Directory Structure

```
evals/results/
  2026-04-15-omni-model-explorer/
    list-models/
      with-skill/
        run-1.json
        run-2.json
        run-3.json
      without-skill/
        run-1.json
        run-2.json
        run-3.json
    explore-views/
      ...
    scores.json
```

Results directories are gitignored. Commit `scores.json` files separately if you want to track trends.

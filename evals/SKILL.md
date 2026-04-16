---
name: omni-skill-eval
description: Run skill evaluations to benchmark agent performance with and without skills. Use when someone wants to run evals, benchmark skills, measure skill impact, compare with-skill vs without-skill performance, check for regressions, or any variant of "run evals", "benchmark the skills", "how well do the skills perform", or "test skill quality".
allowed-tools: Bash(*),Read,Write,Edit,Glob,Grep,Agent,WebFetch
argument-hint: run <skill-name> | run all | report <results-dir> | baseline <skill-name> | add-scenario <skill-name>
---

# Skill Eval Orchestrator

You are the orchestrator for the omni-agent-skills evaluation framework. Parse the user's intent from $ARGUMENTS and execute the appropriate mode below.

## Parsing $ARGUMENTS

Extract the mode and target from the arguments:
- `run <skill-name>` -- run evals for a specific skill (e.g., `run omni-query`)
- `run all` -- run evals for all skills with scenarios
- `report <results-dir>` -- generate/view a report from existing results
- `baseline <skill-name>` -- save current results as the baseline for regression detection
- `add-scenario <skill-name>` -- interactively create a new eval scenario

If $ARGUMENTS is empty or unclear, ask the user which mode they want.

---

## Mode: `run <skill-name>` or `run all`

### Step 1: Verify prerequisites

Check that the following tools are installed and available on PATH:
- `claude` -- the Claude Code CLI (required to spawn eval agents)
- `jq` -- JSON processing (required for scoring)
- `yq` -- YAML processing (required for reading scenario files)

If any are missing, tell the user exactly what to install:
- `claude`: Install from https://docs.anthropic.com/en/docs/claude-code
- `jq`: `brew install jq` (macOS) or `apt-get install jq` (Linux)
- `yq`: `brew install yq` (macOS) or `snap install yq` (Linux)

Do NOT proceed until all prerequisites are satisfied.

### Step 2: Run the eval runner

For a single skill:
```bash
./evals/runner.sh --skill <skill-name>
```

For all skills:
```bash
./evals/runner.sh --all
```

**Important for `run all`**: To avoid overloading the system, do NOT launch all skills simultaneously. Instead, use the Agent tool to run up to 3 skills in parallel at a time. Wait for a batch to complete before launching the next batch. Group skills by expected duration if possible.

Monitor the runner output for progress. The runner will print status lines as each scenario starts and completes.

### Step 3: Score the results

Once the runner finishes, it prints the results directory path (e.g., `evals/results/2024-01-15T10-30-00`). Run the scorer on that directory:

```bash
./evals/scorer.sh <results-dir>
```

The scorer evaluates each assertion in the scenario files against the actual agent output and produces `scores.json` in the results directory.

### Step 4: Generate the report

```bash
./evals/report.sh <results-dir>
```

This generates an HTML report with visualizations and summary statistics.

### Step 5: Display summary

Read `<results-dir>/scores.json` and display a summary table:

```
| Skill               | Config      | Scenarios | Pass Rate | Avg Tokens | Avg Time |
|---------------------|-------------|-----------|-----------|------------|----------|
| omni-query          | with-skill  | 5         | 92%       | 12,450     | 45s      |
| omni-query          | no-skill    | 5         | 68%       | 18,200     | 62s      |
```

Key metrics to highlight:
- **Pass rate delta**: The difference between with-skill and without-skill pass rates. This is the primary measure of skill value.
- **Token efficiency**: Lower tokens with-skill means the skill helps the agent work more efficiently.
- **Time savings**: Faster completion with-skill indicates better guidance.

### Step 6: Baseline comparison

Check if a baseline exists at `evals/baselines/<skill-name>-baseline.json`. If it does:
1. Compare current pass rates against baseline pass rates
2. Flag any regressions (current pass rate < baseline - 5%)
3. Highlight improvements (current pass rate > baseline + 5%)
4. Show a comparison table:

```
| Skill          | Baseline | Current | Delta  | Status      |
|----------------|----------|---------|--------|-------------|
| omni-query     | 90%      | 95%     | +5%    | IMPROVED    |
| omni-embed     | 85%      | 78%     | -7%    | REGRESSION  |
```

If no baseline exists, suggest running `baseline <skill-name>` to establish one.

---

## Mode: `report <results-dir>`

1. Verify the results directory exists and contains `scores.json`
2. Run the report generator:
   ```bash
   ./evals/report.sh <results-dir> --open
   ```
3. Read `scores.json` and summarize the benchmark results in a table (same format as the run summary above)
4. Highlight any notable findings: regressions, high-variance scenarios, skills with low pass rates

---

## Mode: `baseline <skill-name>`

1. Find the most recent results directory for the skill under `evals/results/`
2. Verify `scores.json` exists in that directory
3. Extract the scores for the specified skill
4. Copy the scores to `evals/baselines/<skill-name>-baseline.json`
5. Stage and commit the baseline:
   ```bash
   git add evals/baselines/<skill-name>-baseline.json
   git commit -m "Update eval baseline for <skill-name>"
   ```
6. Report what was baselined: pass rate, number of scenarios, timestamp of the results

---

## Mode: `add-scenario <skill-name>`

1. Read the skill definition at `skills/<skill-name>/SKILL.md` to understand what the skill does and its capabilities
2. Read existing scenarios at `evals/scenarios/<skill-name>.eval.yaml` to see what's already covered
3. Ask the user what task or workflow they want to test. Guide them with suggestions based on gaps in coverage.
4. Generate a new scenario with:
   - A clear, descriptive name
   - A realistic user prompt that exercises the capability
   - 3-5 assertions that verify correct behavior (mix of `contains`, `regex`, `file_exists`, `tool_used` types)
   - Appropriate tags for categorization
5. Append the new scenario to `evals/scenarios/<skill-name>.eval.yaml`
6. Show the user the generated scenario for review
7. Suggest running the new scenario to verify it works:
   ```
   Try: run <skill-name> to verify the new scenario passes
   ```

---

## Interpreting Results

### What's a good pass rate?
- **90%+ with-skill**: The skill is working well. Minor failures may be due to non-determinism.
- **70-89% with-skill**: The skill has gaps. Review failing scenarios to identify missing guidance.
- **Below 70% with-skill**: The skill needs significant work. Check if the skill instructions are clear and complete.
- **With-skill vs without-skill delta > 10%**: The skill is providing meaningful value.
- **Delta < 5%**: The skill may not be adding much value. Consider if it's covering the right scenarios.

### What token/time overhead is acceptable?
- Skills should ideally reduce token usage (agent needs less exploration).
- If a skill increases tokens by >20% while also increasing pass rate, the tradeoff may still be worthwhile.
- Time overhead from skills should be minimal (<10% increase). Large time increases suggest the skill is adding unnecessary steps.

### High variance
- If the same scenario has very different pass rates across runs, the assertions may be too brittle or the task may be inherently non-deterministic.
- Consider making assertions more flexible (use `contains` instead of exact match, use broader regex patterns).

---

## Writing Good Assertions

### Assertion types
- `contains` -- Check if output contains a substring. Good for verifying key information appears.
- `regex` -- Check if output matches a regex pattern. Good for structured output.
- `file_exists` -- Check if a file was created/modified. Good for code generation tasks.
- `tool_used` -- Check if a specific tool was called. Good for verifying the agent used the right approach.
- `file_contains` -- Check if a file contains specific content. Good for verifying generated code.

### Tips
- Test the "what" not the "how": Assert on outcomes, not specific steps the agent takes.
- Avoid over-specifying: Don't assert on exact wording -- the agent's language varies between runs.
- Cover failure modes: Include assertions that verify the agent doesn't do something wrong (e.g., doesn't hallucinate a field name).
- Use multiple assertion types: A mix of `contains`, `tool_used`, and `file_exists` gives better coverage than any single type.
- Keep assertions independent: Each assertion should test one thing. Don't chain assertions where one depends on another.

---

## Troubleshooting

### Agent timeouts
- Default timeout is set in `evals/config.yaml`. Increase it for complex scenarios.
- If agents consistently timeout, the scenario prompt may be too vague or the task too complex for a single eval run.

### Permission errors
- Ensure the Claude CLI has the necessary permissions configured.
- Check that `evals/runner.sh`, `evals/scorer.sh`, and `evals/report.sh` are executable: `chmod +x evals/*.sh`

### yq not installed
- macOS: `brew install yq`
- Linux: `snap install yq` or download from https://github.com/mikefarah/yq/releases
- Verify with: `yq --version`

### No scenarios found
- Check that scenario files exist at `evals/scenarios/<skill-name>.eval.yaml`
- Verify the skill name matches exactly (use `ls evals/scenarios/` to see available files)

### Flaky results
- Run with more iterations: `./evals/runner.sh --skill <name> --runs 5`
- Check if the scenario depends on external state (API availability, specific data)
- Review assertions for brittleness

---

## How Regression Detection Works

1. **Baselines** are saved snapshots of eval scores stored in `evals/baselines/<skill-name>-baseline.json`
2. When evals run, the scorer compares current results against the baseline (if one exists)
3. A **regression** is flagged when the current pass rate drops more than 5 percentage points below the baseline
4. Regressions in CI will cause the workflow to post a warning comment on the PR
5. To update a baseline after intentional changes: use `baseline <skill-name>` to save the new expected performance
6. Baselines should be committed to the repo so CI can use them for comparison

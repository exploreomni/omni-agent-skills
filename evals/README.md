# Skill Evals

This directory contains the local harness for running skill evals against a real Omni instance.

For first-time instance setup, required dashboards, model fields, branch IDs, user attributes, and `eval-env.local.json`, start with [SETUP.md](SETUP.md). This README is the day-to-day command flow once that setup exists.

## What the Harness Does

`runner.sh` reads eval cases from `skills/<skill>/evals/evals.json` and runs each prompt twice:

- `with_skill`: the agent receives the skill's `SKILL.md` as its system prompt.
- `without_skill`: the agent runs without that skill prompt.

`scorer.sh` grades each run against the assertions in the eval file, writes per-run `grading.json`, computes `benchmark.json`, and publishes an aggregate JSON file under `evals/results/<skill>/`.

`report.sh` turns a scored iteration into a local HTML report.

## Directory Layout

The root of `evals/` keeps the files people edit or run directly:

```text
evals/
  README.md              Day-to-day eval runbook
  SETUP.md               One-time Omni instance setup
  eval-env.json          Committed placeholder config
  eval-env.local.json    Local instance IDs; gitignored
  requirements.txt       Python dependencies
  runner.sh              Public entrypoint: run evals
  scorer.sh              Public entrypoint: grade evals
  report.sh              Public entrypoint: build HTML reports
  reset.sh               Public entrypoint: reset mutable eval state
  lib/                   Python implementation helpers
  prompts/               Reusable agent prompt material
  templates/             Report templates and static HTML sources
  results/               Published scored summaries
  workspaces/            Raw per-run outputs, transcripts, and reports
```

Per-skill eval definitions live with the skill they exercise, not in the root harness:

```text
skills/<skill>/evals/evals.json
```

For example, `omni-query` cases live at `skills/omni-query/evals/evals.json`.

Keep new public commands at the `evals/` root. Put reusable implementation code in `evals/lib/`, long prompt material in `evals/prompts/`, and generated or published output under `evals/workspaces/` or `evals/results/`.

## Prerequisites

From the repository root:

```bash
omni config show
python3 -m pip install -r evals/requirements.txt
```

The runner uses LiteLLM, so set the API key for the provider you are running:

```bash
export ANTHROPIC_API_KEY="..."
```

The scorer currently uses the Claude CLI as the grading harness, so it also requires:

```bash
command -v claude
export ANTHROPIC_API_KEY="..."
```

Most evals also need local instance identifiers:

```bash
cp evals/eval-env.json evals/eval-env.local.json
$EDITOR evals/eval-env.local.json
```

`eval-env.local.json` is gitignored. See [SETUP.md](SETUP.md) for the values to put in it.

## Full Command Flow

Run, score, and report a single skill:

```bash
./evals/runner.sh omni-query

ITER_DIR="$(ls -td evals/workspaces/omni-query/iteration-* | head -1)"

./evals/scorer.sh omni-query "$ITER_DIR"

./evals/report.sh "$ITER_DIR"
```

Open the generated HTML report:

```bash
./evals/report.sh "$ITER_DIR" --open
```

The report is written to:

```text
evals/workspaces/omni-query/iteration-<n>-<model>/report.html
```

## Choosing a Model

Use flags:

```bash
./evals/runner.sh omni-query --provider anthropic --model claude-sonnet-4-6
./evals/runner.sh omni-query --provider openai --model gpt-4o
```

Or environment variables:

```bash
EVAL_PROVIDER=anthropic EVAL_MODEL=claude-sonnet-4-6 ./evals/runner.sh omni-query
```

For OpenAI reasoning models, pass reasoning effort when needed:

```bash
./evals/runner.sh omni-query \
  --provider openai \
  --model gpt-5 \
  --reasoning-effort medium
```

## Tool Output Truncation

The runner truncates each tool result before feeding it back into the model. This keeps large CLI responses from being replayed on every later turn and reduces eval overhead.

Default cap:

```text
4000 characters per tool result
```

Tune it with a flag or environment variable:

```bash
./evals/runner.sh omni-query --max-tool-result-chars 8000
EVAL_MAX_TOOL_RESULT_CHARS=8000 ./evals/runner.sh omni-query
```

Use `0` to disable truncation. `transcript.json` keeps the full tool output in `content` for scoring and debugging. When truncation happens, the same tool entry also includes `visible_content` with the shortened model-visible output and a `truncation` object with original and omitted character counts.

## Repeated Runs

Use repeats when you want per-eval variance:

```bash
./evals/runner.sh omni-query --repeat 3

ITER_DIR="$(ls -td evals/workspaces/omni-query/iteration-* | head -1)"
./evals/scorer.sh omni-query "$ITER_DIR"
./evals/report.sh "$ITER_DIR"
```

Repeated runs create nested `run-<n>/` directories under each eval/config pair.

## Running All Skills

Run every skill that has `evals/evals.json`:

```bash
./evals/runner.sh all
./evals/scorer.sh all
```

`scorer.sh all` scores the latest iteration directory for each skill.

Generate reports per skill iteration:

```bash
./evals/report.sh evals/workspaces/omni-query/iteration-<n>-<model>
```

## Outputs

Runner output:

```text
evals/workspaces/<skill>/iteration-<n>-<model>/
  meta.json
  eval-<id>/
    with_skill/
      raw_output.json
      timing.json
      transcript.json
    without_skill/
      raw_output.json
      timing.json
      transcript.json
```

`raw_output.json` includes exact provider-reported usage totals plus an estimated attribution block:

```json
{
  "usage": {"input_tokens": 12345, "output_tokens": 678},
  "usage_by_turn": [
    {"turn": 1, "input_tokens": 5000, "output_tokens": 300}
  ],
  "token_attribution": {
    "method": "estimated_chars_div_4_for_categories_provider_usage_exact",
    "task_tokens_estimated": 1200,
    "eval_overhead_tokens_estimated": 11823,
    "eval_overhead_ratio": 0.958
  }
}
```

The total input/output token counts come from the provider. The task-vs-overhead split is estimated from prompt and transcript text so it can identify the biggest cost drivers, but it should not be treated as an exact billing category. `task_tokens_estimated` is the skill or baseline prompt, user task prompt, and all model output tokens. `eval_overhead_tokens_estimated` is the remaining provider-reported input token usage, including harness instructions, tool schemas, tool results, and conversation replay.

Scorer output:

```text
evals/workspaces/<skill>/iteration-<n>-<model>/benchmark.json
evals/workspaces/<skill>/iteration-<n>-<model>/eval-<id>/<config>/grading.json
evals/results/<skill>/iteration-<n>-<model>.json
```

Report output:

```text
evals/workspaces/<skill>/iteration-<n>-<model>/report.html
```

## Publishing a CSV Summary

After one or more scored runs, flatten `evals/results/<skill>/*.json` into a CSV for BI tools:

```bash
python3 evals/lib/publish.py
```

Default output:

```text
evals/results/eval_results_summary.csv
```

Use a custom path:

```bash
python3 evals/lib/publish.py /tmp/eval_results_summary.csv
```

## Cleanup Between Runs

Some evals mutate the Omni instance by creating users, schedules, labels, or model branches. Before rerunning mutating evals:

```bash
./evals/reset.sh --dry-run
./evals/reset.sh
```

See [SETUP.md](SETUP.md#after-each-eval-run-cleanup) for the cleanup table and manual alternatives.

## Common Issues

If `runner.sh` fails with `litellm not installed`, run:

```bash
python3 -m pip install -r evals/requirements.txt
```

If prompts still contain `{{EVAL_*}}` placeholders, fill in:

```text
evals/eval-env.local.json
```

If `scorer.sh` fails before grading, check:

```bash
command -v claude
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY is set" || echo "ANTHROPIC_API_KEY is missing"
```

If `report.sh` says `benchmark.json` is missing, score the iteration first:

```bash
./evals/scorer.sh omni-query "$ITER_DIR"
```

If you are unsure which iteration was most recent:

```bash
ls -td evals/workspaces/omni-query/iteration-*
```

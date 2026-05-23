# Skill Evals

This repo uses [BenchFlow](https://github.com/benchflow-ai/benchflow) for skill
evals. Each skill owns its eval cases at:

```text
skills/<skill>/evals/evals.json
```

The local `evals/` directory is intentionally thin: it loads local Omni/model
credentials, substitutes instance-specific placeholders, materializes temporary
BenchFlow tasks, and runs with-skill/baseline jobs.

## Directory Layout

```text
evals/
  README.md              Day-to-day eval runbook
  SETUP.md               One-time Omni instance setup
  .env.example           Runtime env template
  .env.local             Local secrets and runner defaults; gitignored
  eval-env.json          Placeholder instance identifiers
  eval-env.local.json    Local instance identifiers; gitignored
  requirements.txt       Python dependency: benchflow
  runner.sh              Public entrypoint
  history.sh             Flatten run summaries for trend reporting
  reset.sh               Best-effort Omni instance cleanup
  lib/
    benchflow_runner.py  Thin BenchFlow wrapper
  workspaces/            Generated tasks, jobs, trajectories; gitignored
```

## Eval Schema

Eval files use BenchFlow's skill-eval schema:

```json
{
  "version": "1",
  "skill_name": "omni-query",
  "defaults": {
    "timeout_sec": 600,
    "judge_model": "claude-haiku-4-5-20251001"
  },
  "cases": [
    {
      "id": "1",
      "question": "What query powers the Revenue Overview dashboard tile?",
      "ground_truth": "The agent extracts the tile query definition.",
      "expected_behavior": [
        "The agent calls omni documents get-queries",
        "The agent reports fields, filters, and sorts"
      ],
      "expected_skill": "omni-query",
      "files": ["evals/files/cases.jsonl"]
    }
  ]
}
```

`{{EVAL_*}}` placeholders are resolved from `evals/eval-env.local.json` at run
time so committed eval cases stay instance-neutral.

`files` is optional. Declared files are copied into the generated BenchFlow task
at `/app/evals/<filename>` for agents to read.

## Local Configuration

Install BenchFlow:

```bash
uv tool install benchflow
```

Or let the runner use `uv run --with benchflow` automatically if `uv` is
available.

Create local runtime env:

```bash
cp evals/.env.example evals/.env.local
```

Set the model credentials your selected agent and judge need:

```dotenv
ANTHROPIC_API_KEY=...
EVAL_AGENT=claude-agent-acp
EVAL_MODEL=claude-sonnet-4-6
EVAL_SANDBOX=docker
```

Set Omni credentials in `evals/.env.local`; the runner passes them into the
BenchFlow sandbox:

```dotenv
OMNI_BASE_URL=https://your-instance.example/
OMNI_API_TOKEN=...
```

Local instance identifiers still live in:

```bash
cp evals/eval-env.json evals/eval-env.local.json
```

See [SETUP.md](SETUP.md) for the required dashboards, model fields, branch IDs,
users, labels, and schedules.

## Running Evals

Run one skill:

```bash
./evals/runner.sh omni-query
```

Run one case:

```bash
./evals/runner.sh omni-query --case 1
```

Run without baseline:

```bash
./evals/runner.sh omni-query --case 1 --no-baseline
```

Run all skills:

```bash
./evals/runner.sh all
```

Common options:

```bash
./evals/runner.sh omni-query \
  --agent claude-agent-acp \
  --model claude-sonnet-4-6 \
  --sandbox docker \
  --concurrency 1
```

The runner defaults to one retry per case (`--max-retries 1`) to absorb
transient sandbox or provider failures. Higher concurrency can make local Docker
runs faster, but if Docker reports compose/network setup errors, rerun with
lower concurrency.

The runner adds a short Omni auth hint to each materialized task: credentials
are available as `OMNI_BASE_URL` and `OMNI_API_TOKEN`, so agents can use CLI
flags when the sandbox has no Omni config file.

## Outputs

Runs are written under:

```text
evals/workspaces/benchflow/<skill>/<timestamp>/
```

Important files:

```text
summary.json                              Combined with-skill/baseline summary
jobs/with-skill/summary.json             BenchFlow aggregate for with-skill
jobs/baseline/summary.json               BenchFlow aggregate for baseline
jobs/<mode>/<run>/<case>/result.json      Per-case score, errors, token totals
jobs/<mode>/<run>/<case>/timing.json      Phase timings
jobs/<mode>/<run>/<case>/prompts.json     Prompt sent to the agent
jobs/<mode>/<run>/<case>/trajectory/      ACP/provider trajectories
jobs/<mode>/<run>/<case>/verifier/        Reward and verifier stdout
```

BenchFlow reports provider token telemetry (`input`, `output`, cache read, cache
creation, total) and timing. It does not compute the old local harness'
task-vs-overhead attribution.

## History

Export a flat CSV across all timestamped runs:

```bash
./evals/history.sh > eval-history.csv
```

Or JSONL:

```bash
./evals/history.sh --format jsonl > eval-history.jsonl
```

Rows include skill, mode (`with_skill`, `baseline`, or `lift`), agent, model,
case ids, pass/fail counts, score, timing, token totals when BenchFlow captured
them, and the source job directory. This is the lightweight equivalent of an
over-time report: commit no run artifacts, but archive or load this export into
BI when you want longitudinal views.

## GEPA

BenchFlow's native `bench skills eval --export-gepa` path can export scored
skill traces for GEPA-style skill optimization. This wrapper does not automate
GEPA yet; use the generated BenchFlow task/job artifacts as the starting point
once the BenchFlow path is stable across the full eval suite.

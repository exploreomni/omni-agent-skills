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
    "timeout_sec": 1200,
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

Install BenchFlow with token telemetry support:

```bash
uv tool install 'benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main'
```

Or let the runner use `uv run --with "$BENCHFLOW_PACKAGE"` automatically if
`uv` is available. By default `BENCHFLOW_PACKAGE` points at BenchFlow `main` so
token telemetry from BenchFlow PR #289 is captured. Override it in
`evals/.env.local` after a released package includes the same support:

```dotenv
BENCHFLOW_PACKAGE=benchflow
```

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
  --concurrency 1 \
  --timeout-sec 1200
```

The runner defaults to one retry per case (`--max-retries 1`) to absorb
transient sandbox or provider failures. For a single skill, `--concurrency`
limits concurrent cases for that skill. For `all`, it is a global case budget
spread across skills, so `all --concurrency 15` can run multiple skills at once
instead of processing skills strictly one by one. Higher concurrency can make
local Docker runs faster, but if Docker reports compose/network setup errors,
rerun with lower concurrency.

The runner materializes tasks with a 1200 second wall-clock budget by default
(`--timeout-sec`, or `EVAL_TIMEOUT_SEC` in `evals/.env.local`). This is higher
than the committed per-skill schema defaults because full Omni workflows can
spend several minutes discovering model/content context before producing the
scored answer.

Before starting BenchFlow, the runner performs cheap, read-only Omni preflight
checks for selected cases with known mutable remote fixtures. If a fixture is
dirty, the run exits before any LLM tokens are spent. Current checks verify that
`omni-content-builder` case 2 is pointed at a clean Sales Performance dashboard
and that `omni-model-builder` cases 1 and 2 have not already shipped their
eval-created model objects. Run `./evals/reset.sh` for best-effort cleanup, then
rerun preflight. Some failures require manual fixture recreation or removal;
fix Omni connectivity or credentials first when relevant, then follow the
specific preflight message and `evals/SETUP.md` when reset cannot clean them
safely.

To check readiness without starting BenchFlow:

```bash
./evals/runner.sh all --preflight-only
```

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
creation, total) and timing when the resolved BenchFlow package includes token
telemetry support. The default runner package points at BenchFlow `main` for
that support until it is available in a normal release. BenchFlow does not
compute the old local harness' task-vs-overhead attribution.

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

CSV fields:

| Field | Description |
|---|---|
| `run_id` | Stable id for the runner invocation. All skills in one `./evals/runner.sh all ...` run share this value. Older summaries without a stored id are backfilled as `legacy-YYYYMMDDTHHMMSS` by grouping near-simultaneous skill workspaces. |
| `run_started_at` | Run start timestamp in `%Y-%m-%d %H:%M:%S` format, normalized from the workspace directory name for CSV import tools. |
| `skill_name` | Skill evaluated, matching the directory under `skills/`. |
| `mode` | `with_skill`, `baseline`, or `lift`. |
| `agent` | BenchFlow agent used for the rollout, for example `claude-agent-acp`. |
| `model` | Model used by the agent rollout. |
| `sandbox` | BenchFlow environment type, usually `docker`. |
| `cases` | Comma-separated case ids included in the run. |
| `total` | Number of cases in the mode summary. Empty for `lift` rows. |
| `passed` | Number of cases BenchFlow marked passed. Empty for `lift` rows. |
| `failed` | Number of cases BenchFlow marked failed. Empty for `lift` rows. |
| `errored` | Number of agent/runtime errors. Empty for `lift` rows. |
| `verifier_errored` | Number of verifier errors. Empty for `lift` rows. |
| `score` | BenchFlow score string, usually a percentage. |
| `score_pct` | Numeric score percentage. For `lift` rows, this is the with-skill score minus baseline score in percentage points. |
| `efficiency_adjusted_score_pct` | Experimental score for rollout rows only: `score_pct` minus transparent efficiency penalties for high tokens per case and timeouts. Use this for optimization triage, not as the canonical pass rate. |
| `efficiency_penalty_pct` | Percentage-point penalty applied to `score_pct` for `efficiency_adjusted_score_pct`. Current policy: no token penalty up to 1M tokens/case, capped token penalty above that, plus timeout penalties capped separately. |
| `elapsed_sec` | Mode elapsed seconds from BenchFlow. Empty for `lift` rows. |
| `total_tool_calls` | Sum of agent tool calls across result files for the rollout. Empty for `lift` rows and older/incomplete artifacts. |
| `avg_tool_calls` | Average tool calls per case for the rollout. Use to spot tool churn and looping behavior. |
| `total_prompts` | Sum of agent prompt turns across result files for the rollout. |
| `avg_prompts` | Average prompt turns per case for the rollout. |
| `avg_case_duration_sec` | Average per-case wall-clock duration derived from result timestamps. This complements `elapsed_sec`, which is the whole mode runtime. |
| `timeout_count` | Number of cases whose agent error included a wall-clock budget timeout. |
| `total_input_tokens` | Provider-reported non-cache input tokens. |
| `total_output_tokens` | Provider-reported output tokens. |
| `total_cache_read_tokens` | Provider-reported cache read tokens. |
| `total_cache_creation_tokens` | Provider-reported cache creation/write tokens. |
| `total_tokens` | Sum of reported input, output, cache read, and cache creation tokens. |
| `tokens_per_case` | `total_tokens / total`. Use for efficiency comparisons within a skill/case mix. |
| `tokens_per_pass` | `total_tokens / passed`. Useful for cost-to-success views; empty when `passed` is zero. |
| `total_cost_usd` | Cost reported by BenchFlow, when available. This may be `0.0` if BenchFlow lacks pricing for the model. |
| `job_dir` | Local path to the source BenchFlow run workspace. |

JSONL uses the same logical fields as the CSV export, with one JSON object per
row. `with_skill` and `baseline` rows include rollout metrics, token telemetry,
and timing. `lift` rows are comparison rows and intentionally omit fields that
do not apply to a single rollout, such as pass/fail counts, elapsed time, and
tokens.

JSONL field descriptions:

| Field | Description |
|---|---|
| `run_id` | Stable id for one eval runner invocation. Use this to group every skill and mode row from a single `./evals/runner.sh all ...` run, even when individual skill workspaces have different timestamps. |
| `run_started_at` | Human-readable local start timestamp derived from the BenchFlow workspace directory, formatted as `YYYY-MM-DD HH:MM:SS`. Use it for sorting and display; use `run_id` for grouping. |
| `skill_name` | Skill under test, matching a directory under `skills/`. Use this as the main dimension for per-skill trend charts. |
| `mode` | Row type: `with_skill` is the agent with the skill loaded, `baseline` is the comparison run without the skill, and `lift` is the score delta between them. |
| `agent` | BenchFlow agent adapter used for the rollout, for example `claude-agent-acp`. Use this to separate results if the harness starts testing different agent adapters. |
| `model` | Model used by the rollout. Use this to avoid comparing scores or token usage across model changes without labeling the change. |
| `sandbox` | BenchFlow execution environment, usually `docker`. Useful for spotting changes caused by local versus container execution. |
| `cases` | Comma-separated list of eval case ids included in the row. Use this to confirm two rows are comparable before comparing scores. |
| `total` | Number of cases evaluated for a rollout row. Omitted on `lift` rows because lift compares two rollouts rather than running cases itself. |
| `passed` | Number of cases that received a passing reward in that rollout. Omitted on `lift` rows. |
| `failed` | Number of cases that did not pass in that rollout. Omitted on `lift` rows. |
| `errored` | Number of cases with agent/runtime errors, such as wall-clock timeout. Track separately from failed rubric scores because these point to harness or execution issues. |
| `verifier_errored` | Number of cases where the verifier failed. Treat these as eval infrastructure issues before treating them as skill quality signals. |
| `score` | BenchFlow score string, usually a percentage such as `75.0%`. Good for display, but prefer `score_pct` for calculations. |
| `score_pct` | Numeric score percentage. For `with_skill` and `baseline`, this is the rollout score; for `lift`, this is `with_skill score - baseline score` in percentage points. |
| `efficiency_adjusted_score_pct` | Experimental rollout score after subtracting efficiency penalties from `score_pct`. Keep it separate from correctness reporting; use it to prioritize optimization work and GEPA objectives. |
| `efficiency_penalty_pct` | Total percentage-point efficiency penalty. Token penalties start only above 1M tokens per case and are capped; timeout penalties are additive and separately capped. |
| `elapsed_sec` | Wall-clock seconds for a rollout mode. Use this for runtime trends and timeout investigation. Omitted on `lift` rows. |
| `total_tool_calls` | Total agent tool calls across the rollout's case result files. High values often indicate exploration, retries, or tool-output loops. |
| `avg_tool_calls` | Tool calls divided by case count. Use this as a normalized tool-churn metric within comparable case sets. |
| `total_prompts` | Total agent prompt turns across case result files. Most current evals should be near one prompt per case. |
| `avg_prompts` | Prompt turns divided by case count. Spikes suggest multi-turn recovery, retries, or harness behavior changes. |
| `avg_case_duration_sec` | Average case runtime computed from each `result.json` start/finish timestamp. Use alongside `elapsed_sec` to understand serial versus parallel runtime. |
| `timeout_count` | Count of agent executions that hit the configured wall-clock budget. Treat these as efficiency and reliability failures even when other cases pass. |
| `total_input_tokens` | Provider-reported non-cache input tokens for the rollout. Can be `null` for older runs without telemetry. |
| `total_output_tokens` | Provider-reported output tokens for the rollout. Use with input/cache fields to understand token shape. |
| `total_cache_read_tokens` | Provider-reported prompt-cache read tokens. High values here usually indicate repeated shared prompt/context reuse rather than new paid input. |
| `total_cache_creation_tokens` | Provider-reported prompt-cache creation/write tokens. Spikes can indicate larger prompts, tool results, or skill context being cached. |
| `total_tokens` | Sum of input, output, cache read, and cache creation tokens reported by BenchFlow. Use this for broad consumption trends, not precise billing unless pricing is separately applied. |
| `tokens_per_case` | Total reported tokens divided by number of cases. Compare within the same skill or case mix, not across unrelated skills. |
| `tokens_per_pass` | Total reported tokens divided by passed cases. Useful for cost-to-success dashboards; omitted when nothing passed. |
| `total_cost_usd` | Cost reported by BenchFlow when available. This may be `0.0` or `null` if BenchFlow does not have pricing for the model. |
| `job_dir` | Local source workspace for the run artifacts. Use this to drill from a trend row back into detailed case results, trajectories, and verifier output. |

## GEPA

BenchFlow's native `bench skills eval --export-gepa` path can export scored
skill traces for GEPA-style skill optimization. This wrapper does not automate
GEPA yet; use the generated BenchFlow task/job artifacts as the starting point
once the BenchFlow path is stable across the full eval suite.

There is an experimental local smoke test for GEPA's `optimize_anything` API at
`evals/lib/gepa_smoke.py`. It does not spend model tokens or touch Omni, but it
is intentionally not wired into the default eval dependency set or exposed as an
executable wrapper.

Install GEPA explicitly, then run the script directly:

```bash
python3 -m pip install gepa
python3 evals/lib/gepa_smoke.py
```

The smoke test uses GEPA's `optimize_anything` API with a deterministic local
reflection callable. It verifies the shape GEPA needs for a future real
integration: a text candidate, an evaluator score, and diagnostic feedback
captured as Actionable Side Information. By default it writes to a timestamped
directory under `evals/workspaces/gepa-smoke/`; it will not delete or reuse an
existing run directory unless you pass `--keep-run-dir`.

When we wire GEPA to real skill evals, keep correctness as the primary reward
and use efficiency as a secondary objective. A practical objective is the case
reward plus feedback from `efficiency_adjusted_score_pct`, `tokens_per_case`,
`total_tool_calls`, and timeout counts, so GEPA can prefer faster/lower-token
skill wording only when it preserves task quality.

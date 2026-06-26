---
name: omni-ai-eval
description: Evaluate Omni AI accuracy using Omni's built-in eval system — define a prompt set, run a judged eval against a model (or branch), and read the accuracy-judge verdicts. Use this skill whenever someone wants to evaluate Omni AI, benchmark Blobby, run regression tests, compare AI output across branches or model-context changes, measure AI quality, run A/B tests on model changes, assess the impact of an ai_context or modeling change, or any variant of "run evals", "test Blobby", "benchmark query generation", "compare AI results", "regression test", "how accurate is the AI", or "measure the impact of my changes".
---

# Omni AI Eval

Omni ships a first-class eval system (the **AI Hub** → **Prompt sets** and **Eval runs**). This skill drives it through the Omni CLI: define a reusable **prompt set**, start a judged **eval run** against a model or branch, and read per-prompt verdicts from Omni's built-in **accuracy judge**.

Prefer this native system over building your own harness. The judge scores each answer *semantically* against the full agent conversation — it does not require golden query JSON, and it evaluates the whole agentic workflow (topic selection, queries, results, and the final written answer), not just generated query structure.

> **Tip**: Use `omni-ai-optimizer` to improve scores after finding failures, `omni-model-builder` to apply context changes on a branch before A/B testing, and `omni-model-explorer` to discover topics and fields when writing prompts.

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it.
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."

# Verify the CLI has the eval commands. If this errors with "unknown command",
# the binary is stale — ask the user to update it (the ai-eval group is generated
# from the bundled API spec).
omni ai-eval --help >/dev/null 2>&1 || echo "ERROR: 'omni ai-eval' missing — update the Omni CLI."
```

```bash
# Show available profiles and select the right one — running against the wrong
# instance silently evaluates the wrong model.
omni config show
# If multiple profiles exist, ask the user which to use:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

You also need the **model ID** of a shared model to evaluate. Evals require at least **Querier** access on that model, and at least one topic optimized for AI. See the [Evals guide](https://docs.omni.co/ai/evals) for concepts and prompt-set best practices.

## How it works

| Concept | What it is |
|---------|-----------|
| **Prompt set** | A reusable, named list of up to **25** natural-language prompts, scoped to one model. Each prompt may carry an optional `expectation` — a reference answer the judge scores against. Lives server-side; create one per topic, per release, or for regression coverage. |
| **Eval run** | Executes a prompt set against a model branch (or `main`). Each prompt runs as a full async agentic AI job (the same engine as production Blobby), then the accuracy judge scores the result. |
| **Accuracy judge** | A fixed judge model that reads the evaluated AI's full conversation and returns a **pass/fail** verdict per prompt, plus confidence and a rationale. It targets high-impact analysis errors (hallucinations, date/time filtering, row-limit handling, mental math, period-over-period mistakes, wrong topic). It does **not** grade wording or formatting. |

All commands accept `-o json` (or `--compact`) to force structured output for parsing, and `--profile <name>` / `--branch-id` style global flags. Run `omni ai-eval <command> --help` for the full flag list. For commands that take a `--body` (e.g. `prompt-sets-create`), run them with `--schema` to print the body's JSON schema and a filled example instead of guessing the JSON.

## Step 1 — Build a prompt set

```bash
omni ai-eval prompt-sets-create --compact --body '{
  "model_id": "your-model-id",
  "name": "Orders regression",
  "slug": "orders-regression",
  "description": "Core revenue + orders coverage",
  "prompts": [
    { "prompt_text": "Show me revenue by month" },
    { "prompt_text": "What are the top 5 products by revenue?",
      "expectation": "The top product by revenue should be Aniseed Syrup." },
    { "prompt_text": "How many orders were placed last week?" }
  ]
}'
```

The response includes the created `prompt_set.id` (a UUID) — capture it for the run.

| Field | Required | Notes |
|-------|----------|-------|
| `model_id` | Yes | Shared model UUID the set is bound to |
| `name` | Yes | ≤ 255 chars |
| `slug` | Yes | Unique per `model_id`; must match `^[a-z][a-z0-9-]*$` |
| `description` | No | ≤ 1024 chars |
| `prompts[]` | No | ≤ 25; each needs `prompt_text` (≤ 8000 chars), optional `expectation` (≤ 16000 chars) |

**Find or update an existing set** instead of recreating:

```bash
omni ai-eval prompt-sets-list --model-ids your-model-id --compact   # discover sets + ids
omni ai-eval prompt-sets-get <promptSetId> --compact                # full set with prompts
```

`prompt-sets-update` replaces the **entire** `prompts` list: omitted prompts are deleted, entries with no `id` are created, entries with a matching `id` are updated in place. To add one prompt, send the full desired list (existing prompts carry their `id`).

```bash
omni ai-eval prompt-sets-update <promptSetId> --compact --body '{
  "prompts": [
    { "id": "<existing-prompt-id>", "prompt_text": "Show me revenue by month" },
    { "prompt_text": "Revenue by month, last 12 months only" }
  ]
}'
```

### Writing good prompts and expectations

- **Mirror real user questions** — pull from the AI usage analytics dashboard rather than inventing phrasing that echoes field names.
- **Favor breadth over depth** — one prompt across many topics yields more signal than ten on one topic.
- **Add a regression prompt** whenever an answer turns out wrong, so the same failure is caught next time.
- **Set an `expectation`** only when a prompt has a known answer worth pinning: a value or ranking ("top product should be Aniseed Syrup"), a direction ("revenue should be up YoY"), or a required breakdown. The judge treats a *material* divergence (wrong numbers, wrong direction, missing required result) as a failure but ignores wording/formatting differences. With no expectation, the judge decides whether the answer is correct on its own terms. The expectation is shown only to the judge — the evaluated AI never sees it.

## Step 2 — Run an eval

```bash
# Against main:
omni ai-eval runs-create --compact --body '{
  "prompt_set_id": "<promptSetId>",
  "description": "Baseline on main"
}'

# Against a branch (measures a model-context change before promotion):
omni ai-eval runs-create --compact --body '{
  "prompt_set_id": "<promptSetId>",
  "description": "After adding ai_context to order_items",
  "run_config": { "branch_id": "<branchId>" }
}'
```

The response returns `run.id` and `job_count` (one agentic job per prompt). Omit `run_config.branch_id` to run against the live shared model.

> **Concurrency cap**: at most **2 eval runs in flight at once**. A `429` means the per-user active-run cap is reached — wait for an in-flight run to finish or cancel one. A `503` means eval is paused for the org. Check `runs-list` before launching.

### Poll for completion

```bash
omni ai-eval runs-get <runId> --compact
```

Poll with backoff (e.g. 5s, 10s, 20s) until the run's `status` is terminal — `COMPLETE` or `CANCELLED`. Track progress with each result's `agentic_job.state` (`QUEUED` → `EXECUTING` → `COMPLETE`/`FAILED`). Don't hammer the endpoint.

## Step 3 — Read results

`runs-get` returns `results[]`, one row per prompt:

```json
{
  "run": {
    "status": "COMPLETE",
    "branch_id": null,
    "results": [
      {
        "prompt": "What are the top 5 products by revenue?",
        "score": 1,
        "error_reason": null,
        "cost": 0.0021,
        "scoring_cost": 0.0004,
        "timing_ms": 4321,
        "agentic_job": { "state": "COMPLETE", "conversation_id": "conv-uuid", "id": "job-uuid" }
      }
    ]
  }
}
```

| Field | Meaning |
|-------|---------|
| `score` | Judge verdict for the prompt — pass = `1`, fail = `0` |
| `error_reason` | Set when the underlying agentic job failed |
| `cost` / `scoring_cost` | LLM cost (USD) for the answer vs. for judging it |
| `timing_ms` | Total **AI time** in ms — all LLM processing and tool calls (matches the "AI time" column in the UI), not wall-clock duration |
| `agentic_job.conversation_id` | Open this chat to read the judge's full verdict, confidence, and rationale |

**Overall accuracy = the pass rate** (mean of `score` across results). Report it with the per-prompt breakdown, and for any failure, point to the `conversation_id` so the user can read *why* the judge failed it — that rationale is where the actionable signal lives.

```
Eval run "Baseline on main" — 9/12 passed (75.0%)
  ✗ "Revenue by quarter"        — judge: summed a row-limited result as a total
  ✗ "Top products this year"    — judge: date filter used calendar instead of fiscal year
  ✗ "Churn rate by segment"     — agentic job FAILED (error_reason)
  (open each conversation_id for the full rationale)
```

## A/B comparison: branch vs main

The core workflow for measuring whether a model change helps. Run the **same prompt set** twice — once on `main`, once on the branch — then compare.

1. Create or identify the branch with the change (use `omni-model-builder` to apply `ai_context`, fields, joins, `ai_settings`, etc. on a branch).
2. `runs-create` with no `run_config` → baseline run on main.
3. `runs-create` with `run_config.branch_id` → branch run.
4. Poll both to `COMPLETE`, then diff per-prompt verdicts.

```
A/B: main vs branch/new-context  (prompt set: orders-regression)
                    main      branch     Δ
Accuracy:           75.0%     91.7%     +16.7%
Prompt credits:     0.024     0.026     +0.002

Regressions (passed on main, failed on branch):
  - rev-by-quarter
Improvements (failed on main, passed on branch):
  - top-products-this-year
  - churn-rate-by-segment
```

> **Always check for regressions, not just net improvement.** A higher overall pass rate can still hide a prompt that newly broke — an `ai_context` change that helps most prompts may conflict with one. Call out any prompt that passed on main but fails on the branch.

Notes for an auditable comparison:
- Both runs must use the **same prompt set** so they evaluate identical prompts (the AI Hub comparison view enforces this too).
- Record the full `branch_id` used and confirm the branch run's `run.branch_id` matches it — don't claim the branch was exercised without that.
- Expectations are snapshotted per run, so editing a prompt's `expectation` later won't change how earlier runs were scored.

## Managing prompt sets and runs

```bash
omni ai-eval runs-list --prompt-set-id <promptSetId> --compact   # runs for a set, newest first
omni ai-eval runs-cancel <runId>                                 # cancel an in-flight run (also archives it)
omni ai-eval runs-archive <runId>                                # archive a finished run
omni ai-eval runs-unarchive <runId>                              # restore an archived run

omni ai-eval prompt-sets-archive <promptSetId>                   # archive a set (cancels its in-flight jobs)
omni ai-eval prompt-sets-unarchive <promptSetId>                 # restore an archived set
```

Archiving is a soft delete — sets and runs are preserved and can be restored. Cancelling a run marks it `CANCELLED` and archives it; use `runs-unarchive` to surface it in the default list again. Use `--archived true` on the `*-list` commands to see archived items.

## Gotchas

- **Right profile, right instance** — the eval runs against whatever model lives on the active profile's instance. Confirm the profile before creating sets or runs.
- **Judge is binary and fixed** — a pass means the answer avoided the high-impact analysis errors, not that it's the single best possible answer. The judge model isn't configurable per run.
- **Failed job ≠ failed judgment** — a result with `error_reason` set means the agentic job itself failed (it never produced an answer to score); treat that separately from a judge `score` of `0`.
- **Snapshotting** — to keep runs reproducible, capture the model state alongside results: `omni models yaml-get <modelId> --compact` and `omni models validate <modelId>`. Branch runs already pin the change to a branch.

## Docs reference

- [Evals (concepts + judge)](https://docs.omni.co/ai/evals) · [AI Eval API](https://docs.omni.co/api/ai-eval/list-eval-prompt-sets) · [Create AI job API](https://docs.omni.co/api/ai/create-ai-job) · [Optimizing models for AI](https://docs.omni.co/modeling/develop/ai-optimization)

## Related skills

- **omni-ai-optimizer** — improve AI accuracy based on eval findings (`ai_context`, `sample_queries`, field metadata)
- **omni-model-builder** — apply context changes on a branch before A/B testing
- **omni-model-explorer** — discover topics and fields when writing prompts

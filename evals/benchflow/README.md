# BenchFlow Skill Eval POC

This is an experimental adapter for trying this repo's skill eval cases with
BenchFlow's `bench skills eval` contract.

The local harness schema is:

```json
{
  "skill_name": "omni-query",
  "evals": [
    {
      "id": 1,
      "prompt": "task text",
      "expected_output": "expected result",
      "assertions": ["rubric item"]
    }
  ]
}
```

BenchFlow expects:

```json
{
  "version": "1",
  "skill_name": "omni-query",
  "cases": [
    {
      "id": "1",
      "question": "task text",
      "ground_truth": "expected result",
      "expected_behavior": ["rubric item"]
    }
  ]
}
```

Generate a two-case Omni Query POC:

```bash
python3 evals/lib/benchflow_adapter.py \
  omni-query \
  /private/tmp/omni-query-benchflow-poc \
  --case 1 \
  --case 2
```

Validate the generated directory from a BenchFlow checkout:

```bash
uv run python - <<'PY'
from benchflow.skill_eval import load_eval_dataset
d = load_eval_dataset("/private/tmp/omni-query-benchflow-poc")
print(d.skill_name, len(d.cases), [c.id for c in d.cases])
PY
```

Materialize generated task directories:

```bash
uv run python - <<'PY'
from pathlib import Path
from benchflow.skill_eval import generate_tasks, load_eval_dataset
d = load_eval_dataset("/private/tmp/omni-query-benchflow-poc")
generate_tasks(d, Path("/private/tmp/omni-query-benchflow-tasks/with-skill"), with_skill=True)
generate_tasks(d, Path("/private/tmp/omni-query-benchflow-tasks/baseline"), with_skill=False)
PY
```

## Current Gaps

- Stock `bench skills eval` does not expose `--agent-env`; it only forwards
  provider/judge keys. Omni evals need `OMNI_BASE_URL` and `OMNI_API_TOKEN`
  available to the agent.
- The BenchFlow LLM judge needs one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GOOGLE_API_KEY`, or `GEMINI_API_KEY` available while tasks are generated so
  the verifier can reference it.
- The generated POC writes `evals/Dockerfile` to install Omni CLI and judge SDKs,
  so a live run needs Docker build network access.
- BenchFlow reports provider token telemetry, but it does not preserve our
  task-vs-overhead attribution or model-visible tool-output truncation.

For a real live run, the practical next step is either:

1. Add `agent_env` support to BenchFlow's `bench skills eval` path, or
2. Use the generated task dirs with `bench eval create`, where `--agent-env` is
   already available, then compute with/baseline lift ourselves.

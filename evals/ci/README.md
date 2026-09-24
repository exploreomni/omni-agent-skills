# CI evals

Two tiers that are cheap enough to run on every pull request. Neither one talks
to an Omni instance, so neither can replace `evals/runner.sh` — they sit in
front of it and catch the failures you would otherwise wait twenty minutes to
discover.

| | What it does | Needs | Runtime |
|---|---|---|---|
| Tier 0 — `validate.py` | Structural checks over `SKILL.md`, `agents/`, `rules/`, and every `evals.json` | Nothing | seconds |
| Tier 1 — `routing_eval.py` | Asks a model which skill each eval question should load | `ANTHROPIC_API_KEY` | ~1 min |
| Tier 2 — `../runner.sh` | Full BenchFlow run: real CLI calls, judged trajectories | Omni instance + model creds | ~20 min |

## Tier 0 — `validate.py`

```bash
python3 evals/ci/validate.py
```

Stdlib only. Fails the build on:

- frontmatter that is missing, unclosed, or not flat `key: value`
- a `name` that does not match its directory, or a description over 1024 chars
  (Claude Code truncates past that, usually cutting the "use this when…" half)
- `evals.json` that does not parse, or has a key BenchFlow's strict schema rejects
- `expected_skill` / `depends_on` pointing at a skill that does not exist,
  duplicate case ids, a `depends_on` entry naming its own skill
- a declared `files:` input that is not on disk
- `{{PLACEHOLDER}}` with no matching key in `evals/eval-env.json`
- a relative markdown link that does not resolve
- two skill descriptions whose wording overlaps enough to compete for the same
  prompts (warns at 30%, fails at 50%; today's closest pair is 17%)

Add `--json` for machine-readable output.

## Tier 1 — `routing_eval.py`

```bash
python3 -m pip install -r evals/ci/requirements.txt
python3 evals/ci/routing_eval.py                     # every skill
python3 evals/ci/routing_eval.py --skill omni-query  # one skill
```

Shows the model nothing but the skill catalog — the `name` and `description`
from each `SKILL.md`, exactly what an agent sees before it loads anything — and
asks which skill handles the prompt. The prompts are the `question` fields
already in `skills/*/evals/evals.json`; `expected_skill` is the label. No CLI,
no tools, no judge: one classification call per sample.

That narrow scope is the point. It is the one regression a docs-sync PR
actually causes — a description edit that quietly steals another skill's
prompts or loses its own — and it is invisible to tier 0 and expensive to see
in tier 2.

Defaults: `claude-sonnet-5`, 3 samples per case, majority vote, 8 concurrent
requests. The catalog is sent as a cached system prefix, so after the first
call it is nearly all cache reads. A full 65-case run costs well under a
dollar; the script prints its own token and cost line.

Useful flags:

| Flag | Effect |
|---|---|
| `--samples N` | Samples per case (default 3). Cases that pass on a split vote are reported separately — routing that unstable is worth a look. |
| `--model` | Also `ROUTING_EVAL_MODEL`. |
| `--json-out PATH` | Full per-case results, including every individual vote. |
| `--update-baselines` | Record this run's scores as the gate. |
| `--skip-if-no-key` | Exit 0 rather than fail when no credential is present (CI uses this for forks). |

### Baselines

`baselines.json` holds an overall floor and a per-skill floor, recorded from a
full run on `main` (65 cases x 3 samples, `claude-sonnet-5`): **89.2% overall**.
Re-record with

```bash
python3 evals/ci/routing_eval.py --update-baselines
```

A partial run (`--skill x --update-baselines`) merges only the skills it ran and
leaves `min_overall` alone.

Four skills sit at a 100% floor, so one flipped case fails them. That is
deliberate — majority-of-3 makes a spurious flip unlikely — but relax a floor if
it proves noisy in practice.

The seven cases that misroute today are not all bugs in the descriptions. Two
(`omni-content-builder` 9 and 10) are multi-skill tasks whose `depends_on` names
exactly the skill the router picked. Three more are the same underlying
question — "show me the query behind this dashboard tile" — labelled
`omni-query` in two cases and `omni-content-explorer` in another, which no
description can satisfy both ways. Worth settling the labels before reading
those three as routing failures.

Gate on the floors rather than on per-case perfection: repeated identical
requests are not deterministic, and sampling parameters are not available on
current models, so a single case can flip between runs. Lowering a floor should
be a deliberate, reviewed commit.

## CI

`.github/workflows/skills-ci.yml` runs tier 0 on every PR touching `skills/`,
`agents/`, `rules/`, or `evals/`, then tier 1 on the skills that PR changed
(everything, if the change is to shared harness or rules). Tier 1 is skipped on
fork PRs, which cannot read `ANTHROPIC_API_KEY` — tier 0 still gates those.

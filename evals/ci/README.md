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
python3 evals/ci/routing_eval.py                            # absolute
python3 evals/ci/routing_eval.py --compare-to origin/main   # paired
python3 evals/ci/routing_eval.py --skill omni-query         # one skill
```

Shows the model nothing but the skill catalog — the `name` and `description`
from each `SKILL.md`, exactly what an agent sees before it loads anything — and
asks which skill handles the prompt. No CLI, no tools, no judge: one
classification call per sample.

That narrow scope is the point. It is the one regression a docs-sync PR
actually causes — a description edit that quietly steals another skill's
prompts or loses its own — and it is invisible to tier 0 and expensive to see
in tier 2.

### Cases

Two sources, both run every time:

- **`skills/*/evals/evals.json`** — every `question`, labelled by its
  `expected_skill`.
- **`evals/ci/negative-cases.json`** — out-of-scope prompts that must route to
  `none`, grouped in the report under `(negative)`. Without these the eval can
  only see a skill that stops attracting its own work; it is blind to a
  description that gets *greedier*. The `hard` ones deliberately borrow the
  skills' vocabulary — dashboard, revenue, model, semantic layer — while
  targeting Tableau, dbt, Looker, Cube or Snowflake. That is where
  over-triggering shows up first.

Add one whenever a description grows a new claim. `--no-negatives` skips them.

### Paired vs absolute

**Paired (`--compare-to REF`)** builds the catalog twice — once from the working
tree, once from a git ref — runs every case against both, and reports what *this
change* moved: regressions (passed on base, fails on head), fixes, and cases
where the pick changed without changing the outcome. It exits non-zero on any
regression.

This is what CI runs on a pull request, and it is the more trustworthy signal.
Scores drift run to run — four identical runs on `main` scored 89.2 / 89.2 /
92.3 / 89.2 — so an absolute number moving by a case or two says very little. A
paired comparison runs both catalogs in the same job, minutes apart, on the same
model, which cancels most of that.

Note that every case runs against both catalogs, not just the changed skills'
cases. A description edit in one skill can pull another skill's prompts across,
and scoping to changed skills would hide exactly that.

**Absolute (default)** scores one catalog against the floors in
`baselines.json`. This is what CI runs on `main`, where there is no base to
compare against.

Defaults: `claude-sonnet-5`, 3 samples per case, majority vote, 8 concurrent
requests. The catalog is a cached system prefix, so after the first call it is
nearly all cache reads. An absolute run is ~$0.06; paired is roughly double.

| Flag | Effect |
|---|---|
| `--compare-to REF` | Paired mode against a git ref. |
| `--samples N` | Samples per case (default 3). Cases that pass on a split vote are reported separately — routing that unstable is worth a look. |
| `--no-negatives` | Skip the out-of-scope cases. |
| `--model` | Also `ROUTING_EVAL_MODEL`. |
| `--json-out PATH` | Full per-case results, including every individual vote and which catalog produced it. |
| `--update-baselines` | Record this run's scores as the gate (absolute mode only). |
| `--skip-if-no-key` | Exit 0 rather than fail when no credential is present (CI uses this for forks). |

### Baselines

`baselines.json` holds an overall floor and a per-group floor for absolute mode.
Record them with

```bash
python3 evals/ci/routing_eval.py --update-baselines
```

against `main`, and commit the result. Floors are truncated rather than rounded,
so the run that produced a floor can always clear it — `round(9/11, 2)` is 0.82
while 9/11 is 0.8182, and that gap once failed a run against its own baseline. A
partial run (`--skill x --update-baselines`) merges only the groups it ran and
leaves `min_overall` alone.

Gate on floors rather than per-case perfection: repeated identical requests are
not deterministic, and sampling parameters are not available on current models,
so a single case can flip between runs. Lowering a floor should be a deliberate,
reviewed commit.

Two `omni-content-builder` cases (9 and 10) misroute to the skill their own
`depends_on` names. They are multi-skill tasks, so picking the dependency is not
obviously wrong — worth keeping in mind before reading them as failures.

## CI

`.github/workflows/skills-ci.yml` runs tier 0 on every PR touching `skills/`,
`agents/`, `rules/`, or `evals/`, then tier 1 — paired against the base branch
on a PR, absolute on `main`. Tier 1 is skipped on fork PRs, which cannot read
`ANTHROPIC_API_KEY` — tier 0 still gates those.

Tier 0 is a required status check. Tier 1 reports but does not block, pending
enough runs to know how often a transient API failure turns into a red check.

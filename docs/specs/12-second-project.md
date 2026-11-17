# Spec 12: a second research project to test the belief result, with Kimi as overseer

Branch `spec/12-second-project`, from `main`.

On Madelon the Markov blanket did not help ([spec 11](11-beliefs-review.md)). Code forecasters
built from it did no better than the base rate, and the six real forecasts did worse than a coin
flip. The explanation offered was that every outcome sat within about one standard error of the
floor, so outcomes were coin flips. It also said that the dependence that mattered, one held-out
file and one threshold, is not in route order.

That explanation makes predictions. Madelon cannot test them, because:
- it has four real forecasts;
- it has no truth to check a ✓ against;
- every margin is small.

This spec builds a second project that can test them, and runs it.

## Goals

1. **A known truth.** Synthetic data from a fixed generator, with a replication sample of 50,000
   rows that no agent or forecaster reads. Re-running a credited analysis on it measures how the
   analysis truly does.
2. **Margins that vary.** Model families far below the floor, near it and far above it.
3. **Forecasts made before their outcomes.** A second model forecasts every unresolved milestone
   before each round of agents. The forecasts are committed and pushed before the agents start.
4. **A model overseeing the Bayesian side.** Kimi K3.1 Pro (`moonshotai/Kimi-K3.1-Pro` on
   Berget) forecasts, and chooses which routes the next agents run. Code builds what it reads,
   checks its choice, and does every update and score.

## Non-goals

- **Kimi as an agent.** The agents stay `zai-org/GLM-5.3-Flash`, so the only new model is the
  overseer.
- **Kimi judging credits.** `check` decides them, as before.
- **More than two rounds or three agents at once.**
- **Changing Madelon's map** or `step.schema.json`, `trail.py`, `project.py` or capture.

## The task (`demo2/`, project `synthetic-interactions`)

`demo2/make_data.py` draws twelve standard normal features from NumPy's PCG64 generator with a
fixed seed per file. Five of the features carry the label, through:
- a weak linear part, `0.8·(x1 + 0.5·x2)`;
- an interaction, `4.5·x3·x4`;
- a step, `1.2·[x5 > 0.3]`.

The label is drawn from the logistic of their sum. The files are:

| File | Rows | Where |
| --- | --- | --- |
| `pilot.csv` | 1,000 | the workspace |
| `heldout.csv` | 3,000 | the workspace, sealed |
| `replication.csv` | 50,000 | `research/synthetic-interactions/replication/`, gitignored and rebuilt from the generator |

The digests are recorded and checked. The sandbox hides the repository, so no agent can open the
replication file. Kimi is shown only text that code builds from the map.

This deviates from the plan of 30 features and 800 pilot rows. With 30 features, no method
separated from the others on 800 rows.

**The true values, measured before the map was declared.** Each method was fitted at default
settings on three pilot-sized samples and scored on 200,000 rows from the generator. Its Bayes
AUC is 0.920.

| Method | True AUC | From the floor of 0.80 |
| --- | --- | --- |
| logistic regression | 0.632 | −0.17 |
| L1 logistic regression | 0.635 | −0.17 |
| k-nearest neighbours (k 25) | 0.769 | −0.03 |
| random forest | 0.800 | 0.00 |
| gradient boosting | 0.862 | +0.06 |
| logistic regression on pairwise products | 0.885 | +0.09 |

An agent's tuned analysis can differ from these. The truth that scores the predictions is each
credited analysis re-run on the replication sample, not this table. The author of the map, an AI
agent, also ran the inherited analysis once (`holdout_auc` 0.6107). Both are disclosed because
the same agent seals the revisions; `check` decides every credit from the trails.

## The map (`research/synthetic-interactions/map`)

- **The goal.** `floor`: an analysis chosen on pilot data alone reaches a held-out AUC of 0.80,
  and its own estimate agrees to within 0.05.
- **Six routes**, one per method above. Each runs `baseline → <method>-cv → <method>-holdout`:
  - `baseline`: `cv_auc ≥ 0.60`;
  - `<method>-cv`: `cv_auc ≥ 0.80`;
  - `<method>-holdout`: `holdout_auc ≥ 0.80` and `|gap| ≤ 0.05`.
- The prompt asks agents to write a pilot-only estimate first, so a `-cv` milestone can settle
  before its `-holdout` milestone.
- `beliefs/assumptions.json` declares the `holdout_auc` standard error as 0.0081: 1,498 and 1,502
  rows of each class, at 0.80.

## Kimi's two jobs (`beliefs.py`)

- **`questions --all-open`** asks every unresolved milestone on an open route, at the last
  revision. The default `questions` is unchanged.
- **`nominate`** writes one prompt holding:
  - the open routes;
  - the map as `project.py view` prints it;
  - the belief report.

  Kimi answers `routes: a, b, c` and `why:`.
- **`choose`** checks that the prompt's digest still matches the map, and refuses a route that is
  not open, a repeated route, or more than three. It writes `oversight/round-N.json` with:
  - the choice and its reason;
  - the order `project.py next` gives;
  - the information ranking.

## The rounds

Each round runs in this order:
1. Kimi forecasts every open milestone: `forecasts/kimi-round-N.json`, from `forecast.sh` and
   `collect`.
2. Kimi chooses up to three routes: `oversight/round-N.json`.
3. Both are committed and pushed.
4. `fleet.sh` runs Kimi's routes for 40 minutes, in the sandbox and under the trace.
5. The revision is proposed and sealed.

Two rounds, then the replication.

## Predictions, registered before round 1

Each is reported as **held**, **failed**, or **too few to tell**, with `n` and the standard error
of each difference. None is re-specified after round 1.

- **P1, margin.** Group the settled milestones by their true margin, from the replication sample:
  `|true value − threshold| / se`, using the declared standard error.
  - Where it is at least 1.645, Kimi and `code:blanket` each score below the coin flip.
  - Where it is under 1.645, no forecaster's difference from the coin flip is outside noise.

  A `-cv` milestone has no replicated value; it is grouped by its parent route's `-holdout`
  replication when there is one, and otherwise left out of P1.
- **P2, calibration.** `beliefs.py`'s P(true value meets it), computed from each held-out score,
  has a lower Brier score than 0.5 against the replicated outcomes.
- **P3, structure.** On `-holdout` milestones asked after their `-cv` parent was resolved, Kimi
  scores better than `code:blanket`.

## The replication (`replicate.py`)

For each resolution of a `-holdout` milestone, `replicate.py`:
1. clones the cited run's code snapshot from the trail's `code.bundle`;
2. puts `replication.csv` in place of `data/heldout.csv`;
3. runs the same command, without the trace;
4. reads `holdout_auc`.

It writes `replication.json`: the run, its commit, the digest of the data used, the replicated
value, and whether the floor criterion holds.

**A hint in the name.** The project is called `synthetic-interactions`, and every text Kimi
reads names it. Kimi's reasons in round 1 cite it ("the synthetic-interactions setup"). The name
tells a forecaster where the signal is, so Kimi starts with that hint and the code forecasters do
not. It was found after round 1's answers were in. Kimi was not asked again, because a second
asking would be chosen after seeing the first.

## What happened

**Round 1 (rev-1).** Kimi chose `pairs`, `boost` and `forest`. All three agents cleared the floor
within 25 minutes. Each first ran the inherited analysis pilot-only, then made a pilot-only
estimate, then scored the held-out file once:

| Route | cv_auc | holdout_auc | Replicated |
| --- | --- | --- | --- |
| pairs | 0.8923 | 0.8923 | 0.8969 |
| boost | 0.8343 | 0.8538 | 0.8627 |
| forest | 0.8931 | 0.8983 | 0.9003 |

**Round 2 (rev-2).** Kimi chose the three routes left, `logistic`, `l1` and `knn`, which the
table above put far below the floor at default settings. Every agent read the pairs result
through `project_map` and built on it, so each reached the interaction:

| Route | What the agent ran | holdout_auc | Replicated | Credited |
| --- | --- | --- | --- | --- |
| knn | k-nearest neighbours on raw features and pairwise products, F screen and k chosen in CV | 0.8405 | 0.8507 | yes |
| l1 | L1 logistic regression on raw features and pairwise products, C tuned in CV | 0.9079 | 0.9115 | yes |
| logistic | an RBF-kernel logistic regression | 0.8667 | not run | no |

The logistic route is "a logistic regression on the features as given". The agent's own
diagnostics showed that this caps at 0.63, so it switched to a kernel method. Rev-2 declines the
two logistic credits by judgment, and says so.

**The design did not hold.** The routes were chosen to sit far below, near and far above the
floor at default settings. Tuned agents that read each other's results put every route far above
it: the five replicated results stand 6 to 14 standard errors over 0.80. No settled outcome is
near the threshold, and **every one of the 15 settled forecasts held**. A forecaster that always
said yes would have scored best.

## The predictions

| Prediction | Verdict | Numbers (Brier; difference ± its standard error) |
| --- | --- | --- |
| P1, far from the threshold: Kimi beats the coin flip | **failed** | round 1: 0.286, +0.036 ± 0.081 (n 10); round 2: 0.387, +0.137 ± 0.123 (n 4) |
| P1, far from the threshold: `code:blanket` beats the coin flip | **held in round 2**, nothing to go on in round 1 | round 1: 0.250, every value 0.50 (n 10); round 2: 0.056, −0.194 ± 0.032 (n 4) |
| P1, near the threshold: nothing beats the coin flip | **too few to tell** | n 0 |
| P2, P(true value meets it) beats the coin flip | **held, trivially** | 0.000 (n 5): every margin was over 6 standard errors |
| P3, Kimi beats `code:blanket` after the parent is resolved | **too few to tell** | n 0: no `-cv` milestone was resolved before its round |

**What it says about Madelon.** It is consistent with the explanation, and does not test its
other half:
- **Far from the threshold, the blanket helped.** In round 2 the blanket forecaster read three
  sibling scores far above the floor and gave the open held-out milestones 1.00. It was right.
  On Madelon every sibling score sat at the floor, and it was not.
- **The structure that carried the information was the agents', not the map's.** Siblings
  predicted each other because agents read each other's results and copied what worked.
- **Kimi forecast from method names and did worse than a coin flip.** It expected a linear model
  and kNN to fail, as they would have at default settings, and did not foresee the agents adapting.
- **Kimi as chooser** picked the three routes that would reach the goal first, with a stated
  reason. It changed nothing here, because every route was run.

The near-threshold half, that nothing beats a coin flip there, is still tested only by Madelon.
[Spec 13](13-third-round.md) ran a third round to test it, and reports the verdicts again with
its results.

**Limits.**
- **The settled forecasts are too few to rank forecasters.** There are 15, all held, 4 of them
  where the code forecasters had anything to go on.
- **The project's name gave Kimi a hint** (above).
- **The author of the map knew the default-setting truths** before declaring it, and sealed every
  revision. `check` decided every credit; the declined logistic credits and the accepted method
  claims are judgments, named in rev-1 and rev-2.

## Testing

- `make_data` builds the recorded digests, and the committed pilot and held-out files. It needs
  NumPy, which the repository's environment does not have, so it is skipped there; it runs with
  `uv run --project demo/workspace`.
- `--all-open` asks the 13 milestones of rev-0, and leaves Madelon's default questions unchanged.
- `choose` refuses a route that is not open, too many routes, and an answer not in the asked form,
  and the committed round 1 choice's digest equals a rebuild.
- The grouping by margin matches a hand value.
- The new project's committed `beliefs.txt`, `forecasts/scores.txt`, `view.txt` and `shared.txt`
  equal a rebuild.
- `replicate.py` is not tested in CI: it needs each trail's environment and scikit-learn. Its
  output is committed as `replication.json`, which the score rebuild reads.

**The nomination text is built from the trails as they stood at its revision** (`as_of`). The
first version used every trail on disk. The rebuild test caught that the committed round 1 digest
no longer matched once round 1's agents had written steps.

## Target files

- `demo2/`
- `beliefs.py`, `replicate.py`, `tests/`
- `research/synthetic-interactions/`
- `live/synth-r1-*`, `live/synth-r2-*`
- this spec, and the docs that name the project

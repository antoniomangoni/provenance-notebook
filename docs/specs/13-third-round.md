# Spec 13: a third round of the second project, built to land near the floor

Branch `spec/13-third-round`, from `main`.

[Spec 12](12-second-project.md) ran two rounds of the second project. Its 15 settled forecasts
all held, and every outcome stood 6 to 14 standard errors above the floor. Two consequences:
- **No skill test.** A forecaster that always said yes would have scored best, so the project
  could not tell skill from optimism.
- **The near-threshold half of P1 is untested** (n 0): no outcome sat within noise of the floor.

The design failed because agents read each other's results and built the interaction into every
route. This round adds routes whose method forbids that, so their outcomes land on or below the
floor.

## Goals

1. **The first refutations.** The `logistic` route is still open, and its forecasts are on record:
   `code:blanket` said 0.67 and 1.00 at rev-1, and Kimi said 0.10 to 0.25.
2. **The first outcomes near the floor**, from two routes on the raw features.

## Non-goals

- **Re-specifying P1 to P3.** They stand as spec 12 registered them. Round 3 is reported on its
  own and pooled with rounds 1 and 2.
- **A fourth round, or more than three agents.**
- **Changing** `step.schema.json`, `trail.py`, `project.py`, `beliefs.py`, capture, `demo2/` or
  Madelon's map.

## The routes (rev-3)

Rev-3 adds two routes to goal `floor`. Each runs `baseline → X-cv → X-holdout`, with the criteria
of the other routes:

| Route | Method |
| --- | --- |
| `forest-raw` | a random forest on the twelve features as given, at scikit-learn's default settings (only the number of trees and the seed may change) |
| `knn-raw` | k-nearest neighbours on the twelve standardised features as given, with only k (and its weighting) tuned inside cross-validation |

Both forbid products, kernels, feature selection and other constructed features. A credit that
breaks its route's method rule is declined by judgment and named in the revision, as round 2's
logistic credits were.

`logistic` stays open as rev-0 declared it: "a logistic regression on the features as given".

## The truths, measured before rev-3 was declared

Each method was fitted on three pilot-sized samples (the pilot file and two more from the
generator) and scored on 200,000 rows:

| Method on the raw features | True AUC | From the floor, in standard errors (0.0081) |
| --- | --- | --- |
| random forest, default settings | 0.812 (0.800, 0.828, 0.806; 0.800 on the pilot file) | +1.5 |
| random forest, `max_features` and leaf size tuned in CV | 0.846 | +5.7 |
| k-nearest neighbours, k and weighting tuned in CV | 0.791 | −1.1 |
| k-nearest neighbours, k 25 | 0.779 | −2.6 |
| logistic regression, C tuned in CV | 0.627 | −21 |

A tuned forest would land far above the floor, so the forest route fixes the defaults. The
project's owner chose that after seeing this table. The truth that scores the predictions is still each analysis
re-run on the replication sample.

## What the round should show

Expected outcomes, from the table:
- `forest-raw`: on the floor, either way;
- `knn-raw`: just under it, either way;
- `logistic`: refuted, far below.

**For P1.** `forest-raw` and `knn-raw` should fall in the near-threshold group (under 1.645 SE) and
`logistic` in the far group. Three or four settled outcomes cannot decide either half. The verdict
can at most move from "n 0" to "too few to tell", with the first cases shown.

**For always-yes.** The `logistic` refutation is the first. `code:blanket` reads siblings far above
the floor, so it should forecast it high and lose there. A forecaster that knew the method's limit
should forecast it low.

## The round

As in spec 12:
1. Kimi forecasts the 6 open milestones at rev-3 (`forecasts/kimi-round-3.json`).
2. Kimi chooses the routes (`oversight/round-3.json`). Only three routes are open, so the choice is
   forced, as in round 2.
3. Both are committed and pushed before the agents start.
4. One fleet of three GLM-5.3-Flash agents, 40 minutes, in the sandbox and under the trace.
5. Rev-4 is proposed and sealed.
6. `replicate.py` re-runs every `-holdout` resolution, refuted ones included. The five earlier
   rows must come out as committed.

## What happened

**The first launch ran nothing.** At 14:10 Berget's gateway answered every request with a server
error (`JWT_SIGNING_ERROR`), for Kimi as well as GLM. Each agent's three retries failed before
its first turn, so the trails `synth-r3-*` hold only the runner's opening steps and no run. They are committed
as they are. A smoke prompt each minute found the gateway back at 14:19, and the same three routes
were launched again as `synth-r3b-*`, from the same revision, briefs and forecasts.

**The second launch (rev-4).** All three agents stopped on their own within 12 minutes. Every
trail checks, and no trail opened the replication file.

| Route | What the agent ran | cv_auc | holdout_auc | Replicated | Rev-4 |
| --- | --- | --- | --- | --- | --- |
| forest-raw | a random forest at default settings but 1,000 trees | 0.7878 | 0.788 | 0.7945 (−0.68 SE) | both milestones refuted |
| knn-raw | kNN on the standardised features, k and weighting in nested CV | 0.7919 | not scored | — | `-cv` refuted; `-holdout` open |
| logistic | a logistic regression on a degree-2 polynomial Nystroem kernel | 0.8854 | 0.8906 | not run | declined by judgment |

- **The two raw routes kept to their rule.** Their code snapshots were read: the forest sets only
  `n_estimators` and the seed, and the kNN grid holds only `n_neighbors` and `weights`.
- **The kNN agent stopped at a plateau** of about 0.79 and did not score the held-out file.
- **The logistic agent left its method again,** as in round 2. Its candidates and round 2's are
  declined, and the route stays open.
- **The first refutations.** These are the project's first refutations, and its first outcome near
  the threshold.
- **The replication matches.** The five earlier rows came out as committed.

## The predictions

The forecasts that settled in round 3 were all refutations (n 3):

| Forecaster | Brier, round 3 (n 3) | Brier, rounds 1–3 (n 18) | Rounds 1–3, against the coin flip |
| --- | --- | --- | --- |
| Kimi K3.1 Pro | 0.365 | 0.306 | +0.056 ± 0.060 |
| coin flip | 0.250 | 0.250 | — |
| base rate | 0.871 | 0.300 | +0.050 ± 0.066 |
| blanket | 0.625 | 0.269 | +0.019 ± 0.050 |
| whole map | 0.909 | 0.305 | +0.055 ± 0.070 |

| Prediction | Verdict | Numbers |
| --- | --- | --- |
| P1, far from the threshold: Kimi and `code:blanket` beat the coin flip | **unchanged** (failed for Kimi; held for the blanket in round 2 only) | round 3: n 0 |
| P1, near the threshold: no forecaster's difference from the coin flip is outside noise | **failed, on n 2 from one analysis** | Kimi +0.281 ± 0.109, base rate +0.621, blanket +0.465 ± 0.270, whole map +0.678 ± 0.057: worse than the coin flip, not level with it |
| P2, P(true value meets it) beats the coin flip | **held** | 0.001 against 0.250 (n 6), now with a refutation 0.68 SE from the floor |
| P3, Kimi beats `code:blanket` after the parent is resolved | **too few to tell** | n 0 |

**What it shows.**
- **Every code forecaster said yes, and lost.** They read siblings that had succeeded. The base
  rate, the blanket and the whole map gave the refuted milestones 0.67 to 0.99. Kimi, which
  read the methods, gave the raw kNN 0.18 and did better than all three in this round
  (−0.260 ± 0.120 against the blanket).
- **No forecaster beat a coin flip over the three rounds.** The rounds rewarded opposite habits.
  Reading the siblings won in round 2, when the agents copied what worked. Reading the method won
  in round 3, when the routes forbade copying.
- **Near the threshold, forecasters did worse than a coin flip.** The prediction expected them to
  be level with it. The two cases are one analysis, a pilot estimate and a held-out score, so this
  is one observation of how confident forecasters fail at the floor, not a rate.
- **Code's P(true value meets it) was right about the refutation,** from the held-out score
  alone.

**Limits.**
- **Three refutations, two near the threshold, all from two agents.** The near-threshold verdict
  rests on one analysis.
- **The logistic route never ran as declared.** In two rounds of asking, its agents left the
  method each time.
- **The author of the map measured the truths before declaring the routes,** and the project's
  owner chose the forest's default settings after seeing them.

## Target files

- `research/synthetic-interactions/` (rev-3, rev-4, forecasts, oversight, replication, outputs)
- `live/synth-r3-*`
- `tests/test_beliefs.py`
- this spec, and the docs that name the project

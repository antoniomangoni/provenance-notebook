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

A tuned forest would land far above the floor, so the forest route fixes the defaults. You chose
that after seeing this table. The truth that scores the predictions is still each analysis
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

## Target files

- `research/synthetic-interactions/` (rev-3, rev-4, forecasts, oversight, replication, outputs)
- `live/synth-r3-*`
- `tests/test_beliefs.py`
- this spec, and the docs that name the project

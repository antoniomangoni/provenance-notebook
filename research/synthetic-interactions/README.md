# Research map: synthetic interactions

The second research project ([spec 12](../../docs/specs/12-second-project.md)). It exists to test
what Madelon's belief layer found: that the Markov blanket did not help forecast, and that a coin
flip did as well. The explanation offered was that every Madelon outcome sat within noise of its
threshold. Here the data are synthetic (`demo2/`), so the truth is known, and the routes were
chosen to sit far from the floor, near it, or far above it.

A second model, Kimi K3.1 Pro on Berget, oversees the beliefs:
- before each round of agents, it forecasts every open milestone and chooses the routes to run;
- its forecasts and choice are committed and pushed before the agents start.

Code builds every text it reads, checks its choice, and scores it. The agents are
`zai-org/GLM-5.3-Flash` through Pi under capture, in the sandbox and under the file trace.

```sh
uv run python project.py check  research/synthetic-interactions/map --live live
uv run python beliefs.py show   research/synthetic-interactions/map --live live    # beliefs.txt
uv run python beliefs.py score  research/synthetic-interactions/map --live live \
  --truth research/synthetic-interactions/replication.json                       # forecasts/scores.txt
uv run --project demo/workspace python demo2/make_data.py                           # the data, and replication/
uv run python replicate.py research/synthetic-interactions/map --live live \
  --data research/synthetic-interactions/replication/replication.csv --out research/synthetic-interactions/replication.json
```

## The rounds

| Rev | What it records |
| --- | --- |
| 0 | **The declared map.** One goal and six routes, one per model family, each through a pilot-only estimate before one held-out score. Written before any run. |
| 1 | **Round 1: pairs, boost, forest, chosen by Kimi.** All three reached the floor in 25 minutes (held-out 0.8923, 0.8538, 0.8983). `forest` reached it with a forest on the features and their pairwise products, built after reading the pairs result. Two row counts are excused. |
| 2 | **Round 2: logistic, l1, knn, the routes left.** Every agent built on the pairs result. `knn` (0.8405) and `l1` (0.9079) are credited. `logistic` reached 0.8667 with an RBF-kernel logistic regression, which is not "a logistic regression on the features as given"; the two credits are declined by judgment. |

## Against the truth

`replicate.py` re-ran each credited held-out analysis on the 50,000-row replication sample
([replication.json](replication.json)). All five clear the floor by 6 to 14 standard errors:
boost 0.8627, knn 0.8507, pairs 0.8969, forest 0.9003, l1 0.9115.

## The forecasts

[forecasts/scores.txt](forecasts/scores.txt) scores Kimi and the code forecasters on the 15
forecasts that settled. All 15 held.

| Round | n | Kimi K3.1 Pro | coin flip | base rate | blanket | whole map |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (rev-0) | 11 | 0.261 | 0.250 | 0.250 | 0.250 | 0.250 |
| 2 (rev-1) | 4 | 0.387 | 0.250 | 0.008 | 0.056 | 0.004 |

At rev-0 nothing was resolved, so every code forecaster said 0.50.
- **Round 1.** Kimi forecast from the routes' names. It gave the linear and kNN routes 0.08 to
  0.40, and the agents then made them work.
- **Round 2.** The blanket read three sibling scores far above the floor and said 1.00 for the
  held-out milestones. Kimi said 0.55.

Kimi's difference from the coin flip is within noise in both rounds. The blanket's in round 2 is
−0.194 ± 0.032.

**What this shows.** Away from the threshold, the blanket's sibling scores carried the
information, and a model's priors about methods did not. The agents shared results, so a sibling's
success predicted the next route's.

**What it does not show.** That nothing beats a coin flip near the threshold: no outcome here was
near it. That a forecaster has skill: every outcome held, so always saying yes would have won.
[Spec 12](../../docs/specs/12-second-project.md) gives each prediction's verdict.

## Limits

- **The design did not hold.** Routes meant to fail were made to work by agents that read each
  other's results.
- **Few forecasts.** 15 settled, all held.
- **A hint in the name.** Kimi read "interactions" in the project's name.
- **Judgments.** The map's author knew the default-setting truths, sealed every revision, and
  judged the method claims in rev-1 and rev-2.

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
| 3 | **Two routes on the raw features** ([spec 13](../../docs/specs/13-third-round.md)): `forest-raw` (a random forest at default settings) and `knn-raw` (k-nearest neighbours, only k tuned). Both forbid products, kernels and feature selection, so their outcomes land near the floor: measured beforehand at 0.812 and 0.791. |
| 4 | **Round 3: logistic, forest-raw, knn-raw, chosen by Kimi.** The first launch ran nothing: Berget's gateway refused every request (`live/synth-r3-*`). The relaunch (`live/synth-r3b-*`) gives the map's first refutations. `forest-raw` misses at both milestones (cv 0.7878, held-out 0.788). `knn-raw-cv` misses (0.7919), and the agent did not score the held-out file. `logistic` again left its method, for a polynomial kernel, and is declined again. |

## Against the truth

`replicate.py` re-ran each held-out analysis the map credits or refutes on the 50,000-row
replication sample ([replication.json](replication.json)):
- **The five credits** clear the floor by 6 to 14 standard errors: boost 0.8627, knn 0.8507,
  pairs 0.8969, forest 0.9003, l1 0.9115.
- **The refuted raw forest** replicates at 0.7945, 0.68 standard errors under the floor: the
  project's one outcome near the threshold.

## The forecasts

[forecasts/scores.txt](forecasts/scores.txt) scores Kimi and the code forecasters on the 18
forecasts that settled: 15 held and 3 were refuted.

| Round | n | Kimi K3.1 Pro | coin flip | base rate | blanket | whole map |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (rev-0) | 11, all held | 0.261 | 0.250 | 0.250 | 0.250 | 0.250 |
| 2 (rev-1) | 4, all held | 0.387 | 0.250 | 0.008 | 0.056 | 0.004 |
| 3 (rev-3) | 3, all refuted | 0.365 | 0.250 | 0.871 | 0.625 | 0.909 |
| all | 18 | 0.306 | 0.250 | 0.300 | 0.269 | 0.305 |

At rev-0 nothing was resolved, so every code forecaster said 0.50.
- **Round 1.** Kimi forecast from the routes' names. It gave the linear and kNN routes 0.08 to
  0.40, and the agents then made them work.
- **Round 2.** The blanket read three sibling scores far above the floor and said 1.00 for the
  held-out milestones. Kimi said 0.55.
- **Round 3.** The routes forbade what the siblings had done. Every code forecaster still read
  their successes and said 0.67 to 0.99. Kimi read the methods and said 0.18 for the raw kNN.

Over all 18, every forecaster's difference from the coin flip is within noise: Kimi
+0.056 ± 0.060, the blanket +0.019 ± 0.050.

**What this shows.** Each round rewarded a different habit. In round 2, agents copied what worked,
so a sibling's success predicted the next route's, and the blanket won. In round 3, the routes
forbade copying, so reading the method won: Kimi beat the blanket by 0.260 ± 0.120. No forecaster
had both habits, and none beat a coin flip overall.

**Near the threshold** there are two settled forecasts, both of the raw forest. Every forecaster
did worse than a coin flip there; spec 12 predicted level with it. That is one analysis, not a
rate. [Spec 13](../../docs/specs/13-third-round.md) gives each prediction's verdict.

## Limits

- **The first design did not hold.** In rounds 1 and 2, routes meant to fail were made to work
  by agents that read each other's results. Round 3's routes forbade that, and two held to it.
- **Few forecasts.** 18 settled and 3 refuted; the 2 near the threshold come from one analysis.
- **The logistic route never ran as declared.** Its agent left the method in both rounds.
- **A hint in the name.** Kimi read "interactions" in the project's name.
- **Judgments.** The map's author knew the measured truths, sealed every revision, and judged
  the method claims in rev-1, rev-2 and rev-4.

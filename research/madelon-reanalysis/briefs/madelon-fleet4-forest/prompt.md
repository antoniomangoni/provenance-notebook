You have inherited an analysis. `analysis.py` predicts the class label from 500 numeric features in `data/pilot.csv` and reports a cross-validated AUC of 0.76. Since then `data/heldout.csv` has arrived: 2200 samples the analysis never saw. Establish whether the reported result holds on them, taking a held-out AUC of at least 0.71 as holding. If it does not hold, find out why, correct the analysis, and report an estimate you would stand behind. Run the analysis with `uv run python analysis.py`; it writes its numbers to `out/metrics.json`. Finish with a short summary of what you found.

## Your route: forest

This task is one route of a research map that has several routes to several goals. Your route's goal: An analysis chosen on pilot data alone reaches a held-out AUC of 0.71, and its own estimate agrees. Your route's method: a random forest on all 500 features.

The task above is shared by every route, and its first part is already answered. These results are established by earlier work, which this task cites; do not recompute them:
- The inherited cross-validated AUC is reproduced; The inherited analysis misses the held-out floor: cv_auc 0.761, holdout_auc 0.5639, gap 0.1971 (step-7 of probe:madelon-2026-11-15-2)

The workspace is the code that produced the last of these: the code snapshot of step-6 in madelon-reanalysis/probe:madelon-2026-11-15-2, 1907960.

## Working alongside other agents

Other agents are working on this map at the same time, on routes l1, boost. The `project_map` tool shows the map and what every trail has found so far. Read it before each new plan. When a result of theirs serves your route, put its step reference, copied whole from `project_map`, in `propose_plan`'s `builds_on`, and say in the reasoning how you use it. Numbers from a run that opened a sealed input are withheld from you; do not look for them. A milestone counts only when a run writes its measures to `out/metrics.json`, so write them in the run that reaches it, the first shared milestone above all: then the map shows it and the others can build on it.

Rules for every route of this map:
Choose every part of the analysis, the screen, the model and its settings, on data/pilot.csv alone. data/heldout.csv is read only by the final analysis, which scores it once: do not use it to diagnose, compare or tune.

What your route must reach, in order:
1. A random forest on all features clears the floor, and its estimate agrees: holdout_auc >= 0.71, gap <= 0.05, gap >= -0.05

Write every one of these measures to `out/metrics.json`: cv_auc, holdout_auc, gap.

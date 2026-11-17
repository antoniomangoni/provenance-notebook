You have inherited an analysis. `analysis.py` predicts a binary label from twelve numeric features in `data/pilot.csv` with a logistic regression, and reports its cross-validated AUC. `data/heldout.csv` holds 3000 samples the analysis never saw. Find an analysis, chosen on the pilot data alone, that reaches a held-out AUC of at least 0.80, with its own cross-validated estimate within 0.05 of the held-out AUC. First establish a pilot-only estimate: write only `cv_auc` to `out/metrics.json`. Then score the held-out file once, at the end, writing `cv_auc`, `holdout_auc` and `gap` (`cv_auc` less `holdout_auc`). `out/metrics.json` must be one flat JSON object of measure names to numbers, with nothing nested. Fit models on one thread (`n_jobs=1`, and `OMP_NUM_THREADS=1` for gradient boosting): every command runs under a file trace that makes many threads slow. Run the analysis with `uv run python analysis.py`. Finish with a short summary of what you found.

## Your route: pairs

This task is one route of a research map that has several routes to several goals. Your route's goal: An analysis chosen on pilot data alone reaches a held-out AUC of 0.80, and its own estimate agrees to within 0.05. Your route's method: a logistic regression on the features and their pairwise products, with its penalty tuned inside cross-validation.

## Working alongside other agents

Other agents are working on this map at the same time, on routes boost, forest. The `project_map` tool shows the map and what every trail has found so far. Read it before each new plan. When a result of theirs serves your route, put its step reference, copied whole from `project_map`, in `propose_plan`'s `builds_on`, and say in the reasoning how you use it. Numbers from a run that opened a sealed input are withheld from you; do not look for them. A milestone counts only when a run writes its measures to `out/metrics.json`, so write them in the run that reaches it, the first shared milestone above all: then the map shows it and the others can build on it.

Rules for every route of this map:
Choose every part of the analysis, the features, the model and its settings, on data/pilot.csv alone. data/heldout.csv is read only by the final analysis, which scores it once: do not use it to diagnose, compare or tune.

What your route must reach, in order:
1. The inherited analysis runs, and its cross-validated AUC is above chance: cv_auc >= 0.6
2. A logistic regression on the pairwise products, chosen on pilot data alone, has a cross-validated AUC of at least 0.80 on the pilot sample: cv_auc >= 0.8
3. A logistic regression on the pairwise products clears the held-out floor of 0.80, and its estimate agrees: holdout_auc >= 0.8, gap <= 0.05, gap >= -0.05

Write every one of these measures to `out/metrics.json`: cv_auc, holdout_auc, gap.

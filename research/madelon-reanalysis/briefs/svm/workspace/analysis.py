"""Predict the Madelon class label with a pilot-fitted feature screen and a random forest.

Why the first analysis was corrected: with 400 pilot samples the F-statistic ranks are noisy.
The original script selected the 30 best features on the whole pilot sample *before* the
cross-validation loop and then fit a linear model, so its 0.76 was the optimism of both
selection leakage and a model that cannot combine features. On the 2200 held-out samples the
selected features score near chance individually and the AUC collapsed to 0.56.

The corrected procedure, fitted on the pilot sample alone:

1. Score the 500 features by their F statistic against the label.
2. Choose K, the number kept, from {10, 25, 50} (at most 50) by inner cross-validation.
3. Fit a random forest on the kept features; a forest can use the informative features
   jointly, which the label structure of Madelon requires.
4. Estimate the AUC by *nested* cross-validation: in every outer fold the screen, the choice
   of K and the forest are refitted inside that fold, so cv_auc is an honest estimate of the
   whole procedure. The final K is chosen the same way on the whole pilot sample.

Usage: uv run python analysis.py [--seed N] [--folds F]
"""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline

K_GRID = (10, 25, 50)


def load(path):
    # One row per sample: the features x1..x500, then the label (-1 or 1).
    table = np.loadtxt(path, delimiter=",", skiprows=1)
    return table[:, :-1], table[:, -1]


def make_model(k, seed):
    return make_pipeline(
        SelectKBest(f_classif, k=k),
        RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=-1),
    )


def choose_k(X, y, seed, folds=4):
    # Inner cross-validation over the K grid; used inside every outer fold and once on the
    # whole pilot sample for the final model. Pilot data only, never the held-out samples.
    inner = StratifiedKFold(folds, shuffle=True, random_state=seed)
    best_k, best_auc = None, -np.inf
    for k in K_GRID:
        auc = cross_val_score(make_model(k, seed), X, y, cv=inner, scoring="roc_auc").mean()
        if auc > best_auc:
            best_auc, best_k = auc, k
    return best_k


parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--seed", type=int, default=0, help="sets the folds and the model")
parser.add_argument("--folds", type=int, default=5)
args = parser.parse_args()

X, y = load("data/pilot.csv")
X_new, y_new = load("data/heldout.csv")

# Nested cross-validation: inside each outer fold, choose K and fit screen + forest on that
# fold's training samples only, then score the fold's test samples.
outer = StratifiedKFold(args.folds, shuffle=True, random_state=args.seed)
fold_aucs = []
for train_idx, test_idx in outer.split(X, y):
    k_fold = choose_k(X[train_idx], y[train_idx], seed=args.seed)
    model = make_model(k_fold, args.seed).fit(X[train_idx], y[train_idx])
    auc = roc_auc_score(y[test_idx], model.predict_proba(X[test_idx])[:, 1])
    fold_aucs.append(auc)
    print(f"outer fold: chose K={k_fold}, AUC {auc:.4f}", flush=True)
cv_auc = float(np.mean(fold_aucs))

# Final model: choose K on the whole pilot sample, fit screen + forest on it, score held-out.
k_hat = choose_k(X, y, seed=args.seed)
model = make_model(k_hat, args.seed).fit(X, y)
holdout_auc = roc_auc_score(y_new, model.predict_proba(X_new)[:, 1])

metrics = {
    "cv_auc": round(cv_auc, 4),
    "holdout_auc": round(holdout_auc, 4),
    "gap": round(cv_auc - holdout_auc, 4),
    "n_features": int(k_hat),
}
Path("out").mkdir(exist_ok=True)
Path("out/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(f"final K={k_hat}")
print(json.dumps(metrics))

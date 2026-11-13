"""The corrected analysis: the same pipeline, with the feature selection inside each fold.

`workspace/analysis.py` picks its K features using every pilot sample and only then
cross-validates, so each fold is scored on samples whose labels already chose the features.
Here the selection is a step of the model, refitted on each fold's training part. Nothing else
differs: the same statistic, model, folds, flags and measures.

Usage, from the workspace so that its data and environment are used:
    uv run --directory demo/workspace python ../corrected.py [--seed N] [--k K] [--folds F]
"""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load(path):
    # One row per sample: the features x1..x500, then the label (-1 or 1).
    table = np.loadtxt(path, delimiter=",", skiprows=1)
    return table[:, :-1], table[:, -1]


parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--seed", type=int, default=0, help="sets the folds and the model")
parser.add_argument("--k", type=int, default=30, help="how many features to keep")
parser.add_argument("--folds", type=int, default=5)
args = parser.parse_args()

X, y = load("data/pilot.csv")
X_new, y_new = load("data/heldout.csv")

# The selection is refitted wherever the model is, so a fold never scores samples that chose its features.
model = make_pipeline(SelectKBest(f_classif, k=args.k), StandardScaler(), LogisticRegression(max_iter=1000, random_state=args.seed))
folds = StratifiedKFold(args.folds, shuffle=True, random_state=args.seed)
cv_auc = cross_val_score(model, X, y, cv=folds, scoring="roc_auc").mean()

# The final model is fitted on every pilot sample, then scored on the new ones.
model.fit(X, y)
holdout_auc = roc_auc_score(y_new, model.decision_function(X_new))

metrics = {"cv_auc": round(cv_auc, 4), "holdout_auc": round(holdout_auc, 4), "gap": round(cv_auc - holdout_auc, 4)}
Path("out").mkdir(exist_ok=True)
Path("out/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics))

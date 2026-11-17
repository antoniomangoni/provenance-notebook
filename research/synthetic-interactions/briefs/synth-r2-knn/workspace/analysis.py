"""Predict the label from the twelve features with a logistic regression.

Fits a standardised logistic regression on every feature and reports the AUC: cross-validated
on the pilot sample, and on the held-out samples.

Usage: uv run python analysis.py [--seed N] [--folds F]
"""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load(path):
    # One row per sample: the features x1..x12, then the label (0 or 1).
    table = np.loadtxt(path, delimiter=",", skiprows=1)
    return table[:, :-1], table[:, -1]


parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--seed", type=int, default=0, help="sets the folds and the model")
parser.add_argument("--folds", type=int, default=5)
parser.add_argument("--final", action="store_true", help="also load and score data/heldout.csv once (final run only)")
args = parser.parse_args()

X, y = load("data/pilot.csv")

model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=args.seed))
folds = StratifiedKFold(args.folds, shuffle=True, random_state=args.seed)
cv_auc = cross_val_score(model, X, y, cv=folds, scoring="roc_auc").mean()

Path("out").mkdir(exist_ok=True)

if not args.final:
    # Pilot-only estimate: the held-out file is never opened.
    metrics = {"cv_auc": round(cv_auc, 4)}
else:
    # The final run, and it alone, reads data/heldout.csv, once, at the end:
    # the model is fitted on every pilot sample, then scored on the new ones.
    X_new, y_new = load("data/heldout.csv")
    model.fit(X, y)
    holdout_auc = roc_auc_score(y_new, model.decision_function(X_new))
    metrics = {"cv_auc": round(cv_auc, 4), "holdout_auc": round(holdout_auc, 4), "gap": round(cv_auc - holdout_auc, 4)}

Path("out/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics))

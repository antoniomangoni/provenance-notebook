# Madelon: predicting the class label

The Madelon data have 500 numeric features and a class label of -1 or 1. This analysis keeps
the features most associated with the label and fits a logistic regression on them.

## Result

On the 400 pilot samples the model reaches a cross-validated AUC of **0.76** (30 features,
5 folds, seed 0).

## Running it

```sh
uv run python analysis.py                  # the reported setting
uv run python analysis.py --seed 1 --k 30 --folds 5
```

The script writes `out/metrics.json`:

| Measure | Meaning |
| --- | --- |
| `cv_auc` | cross-validated AUC on the pilot sample |
| `holdout_auc` | AUC on the held-out samples of the model fitted on the whole pilot sample |
| `gap` | `cv_auc` less `holdout_auc` |

`--seed` sets the folds and the model. `--k` is the number of features kept, and `--folds` the
number of folds.

## Data

| File | Samples | Contents |
| --- | --- | --- |
| `data/pilot.csv` | 400 | the pilot sample, 200 of each label |
| `data/heldout.csv` | 2200 | samples that arrived after the pilot study |

Each row is one sample: the features `x1` to `x500`, then `label`. The features have no names
in the source. Madelon is from the UCI Machine Learning Repository (Guyon, 2004), under CC BY 4.0.

## Method

1. Score each feature by its F statistic against the label, and keep the 30 highest.
2. Standardise the kept features and fit a logistic regression.
3. Estimate the AUC by stratified 5-fold cross-validation.
4. Fit the model on every pilot sample and score the held-out samples.

The held-out score was added when those samples arrived. It has not been reported.

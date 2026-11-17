# Predicting a binary label from twelve features

The data have twelve numeric features and a label of 0 or 1. This analysis fits a standardised
logistic regression on every feature.

## Running it

```sh
uv run python analysis.py                  # seed 0, 5 folds
uv run python analysis.py --seed 1 --folds 5
```

The script writes `out/metrics.json`:

| Measure | Meaning |
| --- | --- |
| `cv_auc` | cross-validated AUC on the pilot sample |
| `holdout_auc` | AUC on the held-out samples of the model fitted on the whole pilot sample |
| `gap` | `cv_auc` less `holdout_auc` |

## Data

| File | Samples | Contents |
| --- | --- | --- |
| `data/pilot.csv` | 1000 | the pilot sample |
| `data/heldout.csv` | 3000 | samples the analysis never saw |

Each row is one sample: the features `x1` to `x12`, then `label`. The features have no names.

# The demo task

A re-analysis for the live run. The agent inherits `workspace/analysis.py`, which reports a
cross-validated AUC of 0.76, and is asked whether that holds on 2200 samples the analysis never
saw. It does not: the held-out AUC is 0.56, against a floor of 0.71 fixed in `task.json`.

**This example is constructed.** The inherited script was written for this repository to show a
known pitfall on public data. No published analysis is being corrected.

| File | Contents |
| --- | --- |
| `task.json` | the task file: question, declared measures, public parameters, inputs |
| `prompt.md` | what the agent is told |
| `workspace/` | what the agent starts from: the inherited script, its data and its environment |
| `corrected.py` | the corrected analysis, kept where the agent cannot read it |
| `make_data.py` | rebuilds the two data files from the source |

## The pitfall

The inherited script picks the 30 features most associated with the label using every pilot
sample, and only then cross-validates a model on those features. Each fold is scored on samples
whose labels already helped to choose the features, so the estimate is too high. The effect is
largest when most features are noise, as 480 of Madelon's 500 are.

Reference: Ambroise, C. and McLachlan, G. J. (2002). Selection bias in gene extraction on the
basis of microarray gene-expression data. *PNAS* 99(10), 6562–6566.

`corrected.py` makes the selection a step of the model, so it is refitted on each fold's
training part. Nothing else differs, and the model fitted on the whole pilot sample is the same
in both, so both report the same `holdout_auc`.

Nothing in `workspace/` or `prompt.md` names the pitfall. A test checks that the words "leak",
"pitfall", "bias" and "optimistic" are absent from both.

## Measured

`H`, the inherited `cv_auc` at seed 0 to two decimals, is **0.76**. The floor is `H - 0.05`,
**0.71**. Defaults: `--k 30 --folds 5`. Each run takes about one second.

| Seed | Inherited `cv_auc` | `holdout_auc` | `gap` | Corrected `cv_auc` | `holdout_auc` | `gap` |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.7610 | 0.5639 | 0.1971 | 0.5640 | 0.5639 | 0.0001 |
| 1 | 0.7608 | 0.5639 | 0.1969 | 0.5420 | 0.5639 | -0.0219 |
| 2 | 0.7649 | 0.5639 | 0.2010 | 0.5855 | 0.5639 | 0.0216 |
| 3 | 0.7645 | 0.5639 | 0.2006 | 0.5541 | 0.5639 | -0.0098 |
| 4 | 0.7734 | 0.5639 | 0.2095 | 0.5963 | 0.5639 | 0.0324 |

The seed sets the folds, so `holdout_auc` does not move with it. The acceptance numbers, which
`tests/test_demo.py` asserts: inherited `cv_auc >= 0.73`, `gap >= 0.15` and
`holdout_auc <= 0.66`; corrected `gap` between -0.07 and 0.07.

```sh
uv run --directory demo/workspace python analysis.py --seed 0
uv run --directory demo/workspace python ../corrected.py --seed 0
DEMO_FULL=1 uv run pytest tests/test_demo.py      # seeds 0 to 4
```

The honest estimate is modest. A linear model finds little in Madelon, whose classes are
separated by a non-linear rule.

## The data

Madelon, an artificial two-class dataset made for the NIPS 2003 feature selection challenge:
5 informative features, 15 linear combinations of them and 480 noise features, in an order that
is not disclosed.

- Source: <https://archive.ics.uci.edu/dataset/171/madelon>, archive
  `https://archive.ics.uci.edu/static/public/171/madelon.zip`
  (`sha256:eb99a0153ebe7d9f4e74551b4b10c54a958b2990b156ce7d76b4e8d71a6f6e82` on 13 November 2026).
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0), as stated on the source page.
- Citation: Guyon, I. (2004). Madelon [Dataset]. UCI Machine Learning Repository.
  <https://doi.org/10.24432/C5602H>. Described in Guyon, I., Gunn, S., Ben-Hur, A. and Dror, G.
  (2004). Result analysis of the NIPS 2003 feature selection challenge. *NIPS* 17.

The files hold the 2600 labelled samples: the archive's training set (2000) and validation set
(600), in that order. The test set has no public labels and is not used. Values and labels are
as in the source; the only changes are commas for spaces, a header row (`x1` to `x500`,
`label`) and the division into two files.

| File | Samples | Digest |
| --- | --- | --- |
| `data/pilot.csv` | 400, 200 of each label | `sha256:11bd022d3a3bd3b394688fb17f5c0c59312f3afdb273d48ad33bbf92ce8d0238` |
| `data/heldout.csv` | 2200 | `sha256:e0b31cbc8eedf1ed84726d9e50066520eccf9ce4f56c182098432fc231784cc1` |

**How the pilot sample was drawn.** Each sample's position in that order, from 0, is hashed as
`sha256("madelon-pilot:POSITION")`. Of each label, the 200 samples whose hashes sort first are
the pilot sample; the rest are held out. The rule has no seed to choose. It was fixed before
anything was measured on its draw.

```sh
uv run python demo/make_data.py                 # downloads the archive
uv run python demo/make_data.py madelon.zip     # or reads a copy
```

`make_data.py` uses the standard library only. It writes the files only when their digests are
the ones above, and fails otherwise.

## Candidates measured

Measured on 13 November 2026, in the spec's order, each over a grid of pilot size, `k` and
model, seeds 0 to 4. The first candidate that met the acceptance numbers was taken.

| Candidate | Licence | Measured | Result |
| --- | --- | --- | --- |
| Arcene (UCI 167) | CC BY 4.0 | 200 labelled samples, 9961 varying features. 64 settings: pilot 40 to 100, `k` 10 to 100, four models | **Not taken.** No setting met the numbers. The held-out AUC stays between 0.60 and 0.77, the largest inherited gap is 0.20, and where the inherited numbers are met (3 settings) the corrected gap is 0.08 to 0.22 |
| Madelon (UCI 171) | CC BY 4.0 | 2600 labelled samples, 500 features. 80 settings, then 144 with 5 and 10 folds | **Taken.** See below |
| Bioresponse (OpenML) | not looked up | not measured | Not needed: Madelon met the numbers first |
| Parkinsons (UCI 174), the second pitfall | CC BY 4.0 | not measured | Not needed |

The four models were logistic regression, a linear support vector machine, 5 nearest neighbours
and Gaussian naive Bayes, the first three after standardising, with the features chosen by F statistic.

### How the setting was chosen

The grids used an exploratory draw: one stratified draw of the pilot sample with seed 0.

1. 80 settings (pilot 60 to 300, `k` 5 to 50, four models, 5 folds): 9 met every number on
   seeds 0 to 4. Small pilot samples met the inherited numbers easily, and missed the corrected
   one, because a cross-validated AUC on 60 to 150 samples moves by more than 0.07 with the folds.
2. 144 settings (pilot 100 to 400, `k` 10 to 50, three models, 5 and 10 folds), each run for
   20 seeds. A pilot sample of 400, 30 features, logistic regression and 5 folds had the widest
   margin on seeds 0 to 4 (0.033 to the nearest threshold) and met every number on 20 of 20 seeds.

That setting was then measured once on the committed draw, with the table above as the result.

### What depends on the draw

The same setting on 20 other stratified draws of 400 (seeds 0 to 19), each for seeds 0 to 4:

- on all 20, the inherited held-out AUC (0.54 to 0.59) is below that draw's own floor, by 0.08
  at the least;
- 14 of the 20 meet every acceptance number. Of the other 6, 3 have an inherited gap between
  0.135 and 0.149, under the 0.15 asked for, and all 6 have a corrected gap outside ±0.07 on some seed.

So the contradiction does not depend on the draw. The margins asked of it do, for about one
draw in three.

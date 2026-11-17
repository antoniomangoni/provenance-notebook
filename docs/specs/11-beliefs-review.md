# Spec 11: the belief layer held to its own standard, and the open forecasts settled

Branch `spec/11-beliefs-review`, from `main`.

[Spec 10](10-beliefs.md) added `beliefs.py` and one run of a second model as forecaster. A review
of it found the arithmetic right and four things wrong or weak. This spec fixes what code can fix,
and runs one fleet to settle the only real forecasts the project holds.

## What the review found

1. **The forecaster's lead on milestones came from questions whose answer was known.** Three of
   the eight (`reproduce`, `miss`, `nested`) are asked at rev-0, which was written the day after
   the runs that settle them. A fourth, `screen` at rev-8, followed from the map: the milestones
   after it were already resolved, and their runs had measured its criteria. On the other four the
   model scored 0.433, worse than a coin flip's 0.250.
2. **The scores had no error.** The model stood 0.065 ± 0.151 below the base rate on milestones.
   The docs said it "beat" the code-only forecasters.
3. **A goal reached by one of several routes was given a flat prior.** The four `compact` scores
   differ by a standard deviation of 0.0084, under one score's standard error of 0.0109, so they do
   not tell the routes apart. The report also did not count how often the held-out file was opened:
   31 runs in 11 trails then, 32 in 12 after the run below.
4. **The blanket was said to hold everything that bears on a milestone, and it does not.** It
   follows the order of the routes. The `compact` scores bear on the open `floor` milestones, which
   are measured on the same criterion over the same file, and they sit outside those blankets. The
   ranking of open milestones also said nothing: every value was under 0.02 bits, in `next`'s order.

## Goals

1. **Mark a milestone question that was never a forecast**, and score those apart.
2. **Give every score a reference and an error**: a coin flip as a forecaster, and each difference
   in Brier score with its standard error.
3. **Test the blanket's scope with code**: a forecaster that reads the same criterion across the
   whole map, beside the one that reads the blanket.
4. **Say what a goal is worth when its routes are related**, how often the sealed file was opened,
   and how many rows would settle a mark that is within noise.
5. **Settle the pending forecasts with a run made after them.**

## Non-goals

- **Changing the text a forecaster is shown.** `score` refuses a forecast whose text has changed,
  so the committed forecasts pin both prompts.
- **Changing `code:blanket`**, whose forecasts of the open milestones were committed in spec 10.
- **A second forecaster run**: other views of a milestone, or repeats. Too few questions are real
  forecasts for either to show accuracy.
- **Beliefs shown to the agents.** The fleet exists to settle forecasts, so it is not told them.

## Technical decisions

### Marks (`known_before`, `marked`)

A settled milestone question is marked ‡ when the run that settles it is older than the revision it
is asked at, or when a milestone after it on a route is already resolved in that revision. A plan
question keeps its † from spec 10. `score` gives the marked rows their reason and scores the
unmarked ones apart.

### Forecasters and their error

- `code:even`: 0.5 on every question.
- `code:pooled` (milestones): the blanket's normal predictive, over every milestone of the pinned
  revision measured on the same criterion (measure, comparison, threshold), wherever it stands;
  with fewer than two, the revision's base rate. Its definition is the blanket's with a wider
  scope, so the two differ in scope alone. A normal predictive from two scores is too sure of
  itself: at rev-2 it gave 1.00 from two scores 0.003 apart, and missed. That is left as it is,
  because the definition was fixed before the run below.
- Each code forecaster's line carries the forecaster's mean Brier difference from it and the
  standard error of that mean; "within noise" under 1.645 of them.
- A forecast file made before a question's outcome is scored as a forecast, and where a file holds
  both, the forecasts are also scored apart.

### The report (`show`)

- **Related routes** (`pooled`). A normal-normal model: each route's true value drawn about a
  shared mean with a spread τ, each score its true value with the declared error, errors
  independent. Two numbers beside the flat-prior range: P with τ = 0, every route sharing one true
  value, and P with a flat prior on the mean and on τ from 0 to 3 standard errors, summed on a fixed
  grid. A flat prior on each true value is τ without limit, so the three bracket what the data can
  support. Given when every scored route of a goal ends at the same single noisy criterion.
- **Looks at a sealed input.** The runs of each trail that opened one, from the traces.
- **Rows to settle a mark.** For a resolution within noise, `(1.645 / margin)²` times the rows,
  were the value to stay where it is.
- **The ranking** says when every value is under 0.05 bits and whether the order is `next`'s. The
  line of goal probabilities says it counts routes that were refuted.
- **From the whole map.** Each open milestone shows `code:pooled`'s forecast under the blanket's.

### Assumptions

`noise` refuses a standard error that is not a positive number, or a `by` that is not an actor.

## The run

**Pre-registered.** The model's forecasts of the four open milestones were committed in spec 10
(16 Nov, 23:32Z). The code forecasters' values were committed and pushed in 9cf5854 (17 Nov,
06:42Z), before the fleet's first step:

| Milestone | Gemma 4 31B | code:blanket | code:pooled | code:even |
| --- | --- | --- | --- | --- |
| `floor-l1` | 0.10 | 0.75 | 0.59 | 0.50 |
| `floor-forest` | 0.10 | 0.75 | 0.59 | 0.50 |
| `compact-boost` | 0.60 | 0.49 | 0.59 | 0.50 |
| `floor-search` (not run) | 0.90 | 0.75 | 0.59 | 0.50 |

**Fleet 4.** `scripts/fleet.sh research/madelon-reanalysis/map madelon-fleet4 l1 forest boost`,
GLM-5.3-Flash on Berget, every command sandboxed and traced, 60 minutes. `search` was left out: a
nested search over six model families is the slowest under the trace.

**It settled none** (rev-12). The wall clock stopped each agent inside a run. `l1` and `boost`
never scored the held-out file. `forest` scored it once, at step-18, with a design chosen on pilot
data: the run printed `holdout_auc` 0.694, under the floor. Its `out/metrics.json` also held a
nested object, so capture read no measures and the observation is inconclusive. `check` credits and
refutes from measures alone, so `floor-forest` stays open and its forecasts stay unscored. The run
was not repeated to have the measures written: that would be a second run on the held-out file,
made knowing the first.

So the project still holds no forecast settled after it was made. The one printed score agrees
with the model's 0.10 and not with the code forecasters' 0.75 and 0.59. It is one score, held as
text.

**What the run did show.** A wall clock of 60 minutes is too short for these agents under the
trace: `boost` lost 40 minutes to two searches that ran out their own limits. And a metrics file
that capture cannot read costs a route its one look. Capture's note says why at once, but the
look is spent.

## Testing (`tests/test_beliefs.py`)

The marks on the four known questions and none on the other four; the marked rows scored apart, and
the coin flip's line; a difference's standard error by hand; the pooled forecast of a `floor`
milestone against its blanket's; a forecast made before its outcome is not called a backtest;
`pooled` against a hand value (the four scores sharing one value: 0.49) and for scores far apart;
the count of looks and the rows figure; the information of an open milestone; an assumption that
cannot be used.

## Boundaries

No change to `step.schema.json`, `trail.py`, `project.py`, capture, `examples/` or an existing
revision. `live/` gains the three trails the fleet wrote.

## Target files

`beliefs.py`, `tests/test_beliefs.py`, `research/madelon-reanalysis/` (the new revision, the
fleet's briefs, and the regenerated `view.txt`, `shared.txt`, `map.html`, `beliefs.txt` and
`forecasts/scores.txt`), `live/madelon-fleet4-*`, this spec, and the docs that name them.

# Spec 10: beliefs over the research map, and a second model as forecaster

Branch `spec/10-beliefs`, from `main`.

A research map marks a milestone ✓ or ✗ when one observation's measures meet its criteria or miss
one. `check` recomputes that, so the mark is honest about what was measured. It says nothing about
how far the measure stood from the threshold, or how many routes were scored on the same held-out
file before one cleared it.

On the Madelon map both matter. The held-out file has 1,100 rows of each class, so an AUC of 0.71
has a standard error of 0.0109 (Hanley and McNeil, 1982). Every ✓ and ✗ at the 0.71 floor is
within 1.1 standard errors of it. `compact-knn` was refuted at 0.709 and `compact-stable-forest`
reached at 0.7125.

The map is a small belief network: a milestone is a variable, a route is the AND of its path and a
goal the OR of its routes. A milestone's Markov blanket is its parents (the milestone before it on
each route), its children (the next milestone, or the goal) and the children's other parents. That
is the part of the map that bears on it, so it is what a forecaster is shown.

## Goals

1. **Say how sure each mark is.** For each resolution at a criterion whose measure has a declared
   standard error: its distance from the threshold in standard errors, and the probability that the
   true value meets it.
2. **Say what a goal reached by one of several routes rests on.** The routes scored on the sealed
   file, and the probability that at least one credited route truly meets the goal.
3. **Give an open milestone's blanket and a probability from it alone**, and rank the open
   milestones by what settling each would tell about its goal, beside `project.py next`.
4. **Let a second model forecast, and score it.** The model writes a probability and a sentence. Code
   builds the text it is shown, records its digest, checks the text is blind to the outcome, and
   scores the forecast against what the map and trails show and against code-only forecasters.

## Non-goals

- **Changing a mark.** Nothing here touches a revision, `check`, `step.schema.json` or a trail.
- **A model doing arithmetic.** A model's probability is an input; every update and score is code.
- **Calibration.** 22 settled questions, all asked after their outcomes existed, cannot rank
  forecasters. The run shows the mechanism and one comparison.
- **A forecaster asked at each `propose_plan`**, with its probability in the trail. That needs a
  decision on the step format.
- **Tighter criteria on the map**, such as a bound that must clear the floor. That is a new revision,
  for a person or a later revision to seal.
- **Learning the network from data.** Twelve trails cannot support it.

## Technical decisions

### Assumptions (`research/NAME/beliefs/assumptions.json`)

`{"version": 1, "noise": [{"measure", "se", "why", "by"}]}`. A measure with no entry is taken as
measured without error, and the report lists those. The Madelon file declares `holdout_auc: 0.0109`,
by `agent:claude-code/claude-fable-5-2`, recomputable with `beliefs.py se --auc 0.71 --pos 1100 --neg 1100`.
It is the error of scoring one fixed model once, not of refitting it.

### The arithmetic (`beliefs.py`)

- **A noisy criterion**: margin `m = (value − threshold) / se`, signed toward meeting it;
  `P = Φ(m)` under a flat prior; "within noise" when `|m| < 1.645`; the one-sided 95% bound
  `value ∓ 1.645·se`. Several noisy criteria multiply.
- **A goal**: over its credited routes, `P(at least one truly meets it)` lies between `max p` (errors
  fully shared, as when every route is scored on one file) and `1 − Π(1 − p)` (independent).
- **An open milestone**: for each noisy criterion, a normal predictive over the co-parents scored on
  the same criterion (`mean`, `sd·√(1 + 1/n)`), when there are two or more; otherwise the Laplace
  rate of the blanket's resolved milestones.
- **The ranking**: `I(G; X)` in bits for each open milestone X and goal G, with routes independent,
  a route's chance the product of its milestones', and one run taken to settle X. An upper bound.

### Questions

- **A milestone** is asked at the last revision before each time it goes from unresolved to
  resolved; the outcome is that first resolution. It is also asked at the last revision when it is
  the next milestone of an open route; the outcome is pending. Not asked, and counted: a first
  resolution that a later revision withdrew; a milestone that first appeared with its resolution;
  a blanket that already cites the run that settles it.
- **A plan** with an expectation on a measure is asked when its first observation is as expected
  or contradicted. A plan never run, or whose first run failed or was inconclusive, is counted.
- **The text shown.** For a milestone, one revision cut to the blanket: statements, criteria, routes
  and each blanket milestone's deciding measures. A revision's `reason` is free text and is left
  out. For a plan, the trail up to and including the plan: each step's kind and summary, the
  measures and outcome of observations, and the plan's reasoning. Nothing after the plan.
- **Sealed reads.** A plan question records the earlier runs of its trail known to have opened a
  map's sealed input. Their printed output may be in the text shown, so the score marks those rows
  (†) and scores the others apart.

### Forecast files (`research/NAME/forecasts/*.json`)

`{"version": 1, "project", "by", "at", "forecasts": [{kind, node, rev | trail, step, saw, p, why}]}`.
`saw` is the digest of the exact text shown; `p` is null when no probability could be read.
`score` rebuilds each text and refuses a forecast whose `saw` differs, or one that is not a question
of the map. A milestone forecast pinned at an earlier revision stays valid while the milestone was
unresolved there, and is settled by its first later resolution. Brier score and log loss in bits
(probabilities clipped to 0.01–0.99) are reported with `n` for each forecaster, and on the same
questions for `code:base-rate` (the Laplace rate of what was settled before the question) and
`code:blanket` (the blanket predictive, for milestones). An unanswered question is not scored.

### The run (`scripts/forecast.sh`)

Pi is called once per question with `-p --no-tools --no-extensions --no-skills --no-context-files
--no-session` and a one-line system prompt. Answers go to `DIR/answers/`; `beliefs.py collect` reads
them. The key is read by Pi's models file only.

## Testing (`tests/test_beliefs.py`)

The standard error against a hand value and against the committed held-out file's class counts; the
blanket of `compact-boost` and of a shared milestone; the goal range for `compact`; no settled
question's text names the run that settles it; a plan's text ends at the plan; a plan after a sealed
read is marked; a tampered `saw` and a forecast of an already-resolved milestone are refused; an
unanswered question is not scored; a forecast pinned at an earlier revision is settled by the first
resolution after it; only `p: X` is read; `beliefs.txt` and `forecasts/scores.txt` equal a rebuild.

## Boundaries

No change to `step.schema.json`, `trail.py`, `project.py`, a map revision, `live/`, `examples/` or
`evidence/`. A new revision changes `beliefs.txt` and `scores.txt`, which must then be regenerated.

## Target files

`beliefs.py`, `scripts/forecast.sh`, `tests/test_beliefs.py`, `research/madelon-reanalysis/beliefs/`,
`research/madelon-reanalysis/beliefs.txt`, `research/madelon-reanalysis/forecasts/`, this spec, and
the docs that name them.

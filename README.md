# Provenance notebook

A record of an AI-assisted research task that a reviewer who was not there can read and check:
what was planned and why, what was run, what contradicted the plan, and how the plan changed.

It is an entry for Task 2 of the [AI for Meta-Science
Hackathon](https://ai4metascience-hackathon.stockholm.ai/), 10–17 November 2026. The brief's test
is that a reviewer can answer "why did they change approach at step 4?" from the log alone.

The notebook has four parts:

- **A trail.** One directory per task, `steps/step-N.json`, each file written once and chained to
  the one before by its hash. A step is a task, a plan, a run, an observation, a review or a note.
- **Capture.** An extension for the [Pi coding agent](https://github.com/earendil-works/pi) that
  writes the trail from hooks around the agent's tools. The agent does not write it.
- **The reviewer's page.** One self-contained HTML file generated from a trail, and `trail.py why`,
  which answers the brief's question in text.
- **A research map.** Many trails toward shared goals, with a checker that recomputes every credit
  from the step files and records every credit that was withdrawn.

## Start here

- **[The pages](https://antoniomangoni.github.io/provenance-notebook/)**: the reviewer's page of a
  live trail, the two research maps and their belief reports, all generated from the step files.
- **[The brief's question, answered](#the-briefs-question-answered-from-a-live-trail)** from a
  live trail, in the terminal.
- **[What was run, and what it showed](#what-was-run-and-what-it-showed)**: 27 live trails over
  two research projects.

What we found:
- **The record answers the brief.** `trail.py why` gives the reason for a change of approach from
  the step files alone, and says which runs had opened the held-out file before the new plan.
- **A model reader did as well from the raw transcript.** The page's measured advantage is its
  length, a tenth of the transcript's.
- **Forecasting the map was not easier than a coin flip.** On a second project with a known truth,
  over 18 settled forecasts, neither a second model nor any code forecaster beat a coin flip.

## The brief's question, answered from a live trail

An agent (GLM-5.3-Flash under Pi) was given an inherited analysis that reports a cross-validated
AUC of 0.76, and asked whether it holds on 2200 held-out samples. This is the answer `why` prints
for the step where its plan changed. Nothing in it is inferred: each line is a link or a field of
a step.

```text
$ uv run python trail.py why live/madelon-2026-11-15-1 step-14 --store live/store \
    --reads research/madelon-reanalysis/retrace/madelon-2026-11-15-1.json --sealed data/heldout.csv
Change of approach at step-14
Replaced plan: step-4, Basic data sanity checks, then run the inherited analysis to see if holdout AUC >= 0.71
Trigger: step-8, contradicted
  holdout_auc 0.5639, expected >= 0.71 (holds-criterion)
New plan: step-14, Rewrite analysis.py: selection + all tuning nested in CV, tuned on pilot only, one held-out scoring
Reasoning:
Diagnosis confirmed: cv_auc 0.76 was inflated by selecting features on all pilot data before CV; […]
Before it was proposed: 5 runs had opened data/heldout.csv: step-2 (wrote no metrics), step-5 (wrote
no metrics), step-7 (measured), step-10 (wrote no metrics), step-12 (measured); known on re-execution
```

The last line is the part a transcript does not give a reviewer. The new plan promises "one
held-out scoring", and the trail shows that five earlier commands had already opened the
held-out file. One of them, `diagnose.py` at step 12, printed per-feature AUCs on it, and the
plan's reasoning quotes one. The page reports the reads and leaves the judgment to the reader.

![The reviewer's page: the decision path, then the runs that opened the held-out file](docs/img/reviewer-page.png)

## Why it is more than a log

- **Expectations come before results.** A plan commits to a measure and a threshold before its
  run, so a reader sees whether a result was predicted or explained afterwards.
- **Outcomes are recomputed.** The checker derives each outcome from the measures, and reads the
  measures again from the metrics file the run wrote. An agent does not grade its own run.
- **What failed stays.** A run is recorded before its command starts, so a crash or an abandoned
  attempt cannot drop out. `trail.py facts` lists what a reviewer would ask about: a plan re-run
  until it held, an eased threshold, a run that never settled.
- **What a run opened is recorded.** Each command is traced, so reading a held-out file is a fact
  of the trail, not something a reader must find in the code.
- **A citation is stable.** A trail is cited at the hash of its last step. One that was rewritten
  and re-chained still checks, but no longer has the head it was cited at.

## What was run, and what it showed

Every live attempt is committed under `live/`: twenty-seven trails over two research projects, all by the same model.

| What | Result | Where |
| --- | --- | --- |
| Two live runs of the task | Both saw the inherited result miss (0.56 against a floor of 0.71). One recorded a replacement plan; the other recorded none | [evidence/](evidence/README.md) |
| A forgery, in five stages | An edited number breaks the chain. A re-chained trail passes `check`, but `check --store` reads the true number in the stored metrics file. Forging that file too is caught only by a head cited beforehand | [tamper.txt](evidence/madelon-2026-11-15-1/tamper.txt) |
| A reader check: three models answer fixed questions from the page, and from the agent's raw transcript | **The page was not needed.** A model answers as well from the transcript. The page's measured advantage is its length, a tenth of the transcript's, which let a small-context model answer at all | [evidence/](evidence/README.md#the-reader-check) |
| Re-executing five trails under a file trace | Two credits were withdrawn: designs judged "pilot-only" from their command lines had opened the held-out file. 17 of 17 metrics files were reproduced byte for byte | [the map](research/madelon-reanalysis/README.md#checked-not-judged) |
| Two fleets of three agents sharing one map | The first reached nothing. In the second, agents built on each other's steps and two routes reached the goal; one held-out result leaked between agents, and the leak is disclosed and closed | [the map](research/madelon-reanalysis/README.md#agents-sharing-the-map) |
| One agent in a sandbox | The sandbox held: no command reached outside its workspace, and the held-out file was never opened. The run reached nothing. The file trace slowed its first search thirteen times, and the wall clock ended it there | [the map](research/madelon-reanalysis/README.md#the-sandboxed-run) |
| Three agents in the sandbox, run to settle forecasts of three open milestones | It settled none. The wall clock stopped each agent inside a run. One scored the held-out file once, at 0.694, but wrote a metrics file capture could not read, so the map holds no measure and refutes nothing | [the map](research/madelon-reanalysis/README.md#fleet-4) |
| A second research project, with Kimi K3.1 Pro overseeing the beliefs | Synthetic data with a known truth. Kimi forecast every open milestone and chose the routes, before each of three rounds of three agents. In two rounds, agents that read each other's results put every route above the floor. A third round, on routes that forbade that, gave the first refutations. Over 18 settled forecasts no forecaster beat a coin flip: reading the siblings won one round, reading the method another | [the project](research/synthetic-interactions/README.md) |
| How sure the map's marks are, and a second model as forecaster | Every ✓ and ✗ at the floor is within noise of it (below). A second model forecast 22 settled questions from text that code built and scored. On the six that were real forecasts it did worse than a coin flip: four of the 8 milestone outcomes were known when the question's revision was written, and 12 of the 14 plans came after their trail had opened the held-out file | [the map](research/madelon-reanalysis/README.md#how-sure-the-marks-are) |

### How sure the marks are

A milestone is ✓ when one observation's measures meet its criteria. `beliefs.py` says how far
each measure stood from its threshold. The held-out file has 1,100 rows of each class, so an AUC
of 0.71 has a standard error of 0.0109:

| Milestone | Held-out AUC | From the 0.71 floor | P(true AUC ≥ 0.71) |
| --- | --- | --- | --- |
| floor-selected-forest ✓ | 0.7214 | +1.05 SE | 0.85 |
| compact-vote ✓ | 0.7190 | +0.83 SE | 0.80 |
| compact-stable-forest ✓ | 0.7125 | +0.23 SE | 0.59 |
| compact-knn ✗ | 0.7090 | −0.09 SE | 0.46 |
| compact-forest ✗ | 0.6989 | −1.02 SE | 0.15 |

`compact` was reached by two of four routes scored on the same file. If each route's true AUC is
unrelated to the others', the chance that at least one of the two truly clears the floor is 0.80
to 0.92. But the four scores differ by less than one score's standard error (0.0084 against
0.0109), so they do not tell the routes apart. If the true values are drawn about a shared mean
the chance is 0.75, and if the routes share one value it is 0.49. Neither route's 95% lower bound
clears the floor: `compact-vote` would need 4.0 times the rows. And 32 runs in 12 trails opened
the held-out file. The marks stand: `check` decides them, and this report only advises.

The map is a small belief network: a route is the AND of its milestones, a goal the OR of its
routes. A milestone's Markov blanket (the milestone before it, what follows, the other milestones
leading there) is what a second model, Gemma 4 31B, was shown to forecast each milestone,
alongside each plan's trail up to the plan. Code built every text, recorded its digest and did all
the scoring, against four code-only forecasters: a coin flip, the base rate, the blanket alone,
and every score on the same criterion across the map.

Where it counted, the model did worse than the coin flip
([spec 11](docs/specs/11-beliefs-review.md)). On 8 milestones its Brier score was 0.246 against a
coin flip's 0.250, but four of those outcomes were known when the question's revision was
written. On the other four it scored 0.433. On 14 plans it scored 0.180, but 12 came after their
trail had opened the held-out file. On the other two it scored 0.425. Over all 8 milestones and
all 14 plans, its difference from the coin flip is within noise.

Four open milestones carried forecasts made before any run toward them. Three agents then ran on
three of those milestones to settle the forecasts, and settled none: the wall clock stopped each
agent inside a run. The `forest` agent scored the held-out file once, at 0.694, under the floor.
The model had given that milestone 0.10 and the blanket 0.75. But the agent's metrics file held a
nested object, so capture read no measures, and the map refutes nothing. The forecasts stay open
([scores](research/madelon-reanalysis/forecasts/scores.txt),
[report](research/madelon-reanalysis/beliefs.txt), [spec 10](docs/specs/10-beliefs.md)).

### A second project, to test that

If outcomes at the threshold are coin flips, forecasts should beat a coin flip away from it. A
second project tests that ([spec 12](docs/specs/12-second-project.md),
[the project](research/synthetic-interactions/README.md)):
- **Synthetic data.** A 50,000-row replication sample, which no agent or forecaster reads, gives
  each credited analysis its true AUC.
- **Six routes.** One per model family, chosen so that at default settings some sit far below a
  floor of 0.80 and some far above.
- **Kimi K3.1 Pro oversees the beliefs.** Before each of three rounds of three agents it forecast
  every open milestone and chose the routes. Both were pushed before the agents started.

**Rounds 1 and 2 did not go to plan.** In round 2 every agent read the first round's results
and built on the interaction they had found, so the linear and kNN routes cleared the floor too.
All 15 settled forecasts held, so always saying yes would have scored best.

**Round 3** ([spec 13](docs/specs/13-third-round.md)) added routes on the raw features whose
method forbade products, kernels and feature selection, so their outcomes would land near the
floor. They gave the first refutations: a default random forest at 0.788 held-out (0.7945
replicated, 0.68 standard errors under the floor), and kNN at 0.79 on the pilot sample.

| Forecaster | Round 1 (n 11, held) | Round 2 (n 4, held) | Round 3 (n 3, refuted) | All (n 18) |
| --- | --- | --- | --- | --- |
| Kimi K3.1 Pro | 0.261 | 0.387 | 0.365 | 0.306 |
| coin flip | 0.250 | 0.250 | 0.250 | 0.250 |
| blanket (code) | 0.250, nothing resolved yet | **0.056** | 0.625 | 0.269 |

- **Each round rewarded a different habit.** When agents copied what worked (round 2), sibling
  scores carried the information, and the blanket beat the coin flip by 0.194 ± 0.032. When the
  routes forbade copying (round 3), reading the method did: Kimi beat the blanket by
  0.260 ± 0.120.
- **No forecaster beat a coin flip over the 18.** Every difference is within noise.
- **Near the threshold, every forecaster did worse than a coin flip.** Spec 12 predicted level
  with it. There are two forecasts, both of one analysis, so this is one case, not a rate.

The demo task is constructed: the inherited script was written for this repository to show a
known pitfall (feature selection outside cross-validation) on public data. No published analysis
is being corrected.

![The research map: routes as lines, milestones as stations, one lane per trail](docs/img/map.png)

## Try it

Requires [uv](https://docs.astral.sh/uv/). Capture's tests also need Node.js 24, `strace` and
`bwrap`, and are skipped without them. No model or key is needed for anything below.

```sh
uv sync
uv run pytest
uv run python trail.py check live/madelon-2026-11-15-1 --store live/store
uv run python trail.py why   live/madelon-2026-11-15-1 step-14 --store live/store \
  --reads research/madelon-reanalysis/retrace/madelon-2026-11-15-1.json --sealed data/heldout.csv
uv run python trail.py facts live/madelon-2026-11-15-1 --store live/store
scripts/site.sh site                             # the pages, then open site/index.html
uv run python project.py serve research/madelon-reanalysis/map --live live    # http://127.0.0.1:8077/
```

To see the tamper evidence on a trail of your own choosing:

```sh
uv run python trail.py head   examples/churn-model-2026-11-11      # the digest to cite
uv run python trail.py verify examples/churn-model-2026-11-11 sha256:…
```

`verify` passes for any head the trail has had, so a trail that grew still resolves. It fails for
a trail whose past was rewritten, however well that trail checks.

Running an agent under capture needs Pi (`npm ci --prefix capture`) and a model:
`scripts/live.sh demo NAME --provider … --model …`. [capture/README.md](capture/README.md) has
the details, and a scripted provider that replays tool calls with no model.

## Commands

| Command | Does |
| --- | --- |
| `trail.py check DIR [--store STORE]` | Checks the chain, who wrote what, and that outcomes follow from the measures. With a store, that the measures are the ones the run wrote |
| `trail.py why DIR [STEP]` | Answers "why did the plan change at STEP?" from the links alone |
| `trail.py view DIR [--code REPO]` | Writes the reviewer's page |
| `trail.py facts DIR` | Lists what a checked trail shows without judging it |
| `… --reads FILE --sealed PATH` | For `why`, `view` and `facts`: which runs had opened PATH before each plan |
| `trail.py head DIR`, `verify DIR HEAD` | Prints the digest a trail is cited at; says whether the trail ever had a head |
| `trail.py review DIR STEP …`, `note DIR STEP …` | Appends a person's review or note |
| `trail.py graph DIR`, `merge OUT DIR…` | Exports trails as node and edge tables |
| `project.py check MAP --live DIR` | Recomputes every credit of a research map from the trails |
| `project.py view`, `shared`, `next`, `status` | The map as text, what routes share, what to run next, and the live state |
| `project.py propose`, `seal` | Drafts the next revision from the trails; seals it |
| `project.py page`, `serve` | The map as one static page, or live on 127.0.0.1; `/review` there sets out every judgment for a person to countersign |
| `beliefs.py show MAP --live DIR` | How sure each mark is, each open milestone's Markov blanket, and which to run next |
| `beliefs.py questions`, `collect`, `score`; `scripts/forecast.sh` | Asks a model to forecast from text checked blind to the outcome, and scores it against code-only forecasters |
| `beliefs.py nominate`, `choose`; `replicate.py` | Asks a model to choose the routes the next agents run, checked against the open routes; re-runs each credited analysis on a replication sample |
| `retrace.py DIR` | Re-executes a trail's runs from their code snapshots under a file trace |
| `tamper.py DIR …` | Runs the forgery sequence on a copy of a trail |
| `readers.py texts`, `ask`, `grade` | The reader check |
| `scripts/live.sh`, `scripts/fleet.sh` | One agent under capture; up to three at once on one map |

## What it does not prove

- **Who wrote a step.** The chain proves order, and that nothing changed after a head was cited.
  Authorship rests on the capture host. `seal --by` and `review --by` take a name as text.
- **A complete rewrite of an uncited trail.** A forged trail with forged metrics files is caught
  only by a head that was cited somewhere the forger cannot reach.
- **What a read was used for.** A trace says a file was opened. Whether it fed a design is a
  judgment, made by a reader or in a map revision's stated reason.
- **That a run used the method it claims.** `check` recomputes numbers, not methods. The map's
  second revision exists because two method claims were wrong and passed.
- **Containment.** The sandbox hides named places: the repository, the trails, the map, the other
  agents' workspaces. The rest of the machine stays readable and the network open. Single runs
  with `live.sh` are not sandboxed unless asked.
- **Privacy.** Commands are recorded as typed. The design's redactor and keyed digests are not
  built, so the committed trails hold absolute paths of the machine they ran on.
- **A person's judgment.** Every revision of the research map was sealed by an AI agent, named in
  its `by`, and no live trail holds a person's review. No person has yet confirmed or disputed one.
- **Cheap tracing.** The file trace slowed one multithreaded search from 52 to 701 seconds. No
  sandboxed agent, of four, recorded a held-out score before its wall clock.
- **That a ✓ would hold again.** The belief report rests on a declared standard error and gives a
  range, because the data cannot say how related the routes are. Of the 22 settled forecasts, 6
  were real forecasts, all backtests. The second project settled 18 forecasts made before their
  outcomes, 3 of them refutations; no forecaster beat a coin flip over them.
- **Generality.** One task, one model, one agent host. The reader check used models as readers.

## Layout

| Path | Contents |
| --- | --- |
| `trail.py`, `step.schema.json`, `view.py` | The checker, the schema of one step, and the reviewer's page |
| `capture/` | The Pi extension that writes steps as the agent works, and its scripted provider |
| `project.py`, `mapview.py`, `beliefs.py` | Research maps: the checker, the page that draws them, and beliefs and forecasts over them |
| `retrace.py`, `replicate.py`, `tamper.py`, `readers.py` | Re-execution under a trace, re-running a credited analysis on a replication sample, the forgery sequence, the reader check |
| `demo/`, `demo2/` | The tasks: an inherited analysis with a known pitfall; synthetic data with a replication sample |
| `live/` | Every trail an agent wrote, with its transcript and code snapshots |
| `evidence/`, `research/` | What was measured on the live trail; the two research projects and their maps |
| `examples/` | Three constructed trails, used as test fixtures |
| `docs/` | [The pitch](docs/HACKATHON.md), [the step format](docs/DESIGN.md), [the graph export](docs/GRAPH.md), and one [spec](docs/specs/) per piece of work |

## How it was built

From specs, by AI coding agents, one branch and pull request per spec; [PLAN.md](PLAN.md) is the
roadmap and its decisions. The step schema, the checker and the three example trails predate the
hackathon's start on 10 November and came in with the first commit. Everything else was built
during the week.

Licensed under the [MIT License](LICENSE).

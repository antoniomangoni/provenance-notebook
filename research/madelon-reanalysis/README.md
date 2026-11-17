# Research map: the Madelon re-analysis

This map covers the demo task (`demo/`). An inherited analysis reports a cross-validated AUC of
0.76, and on 2200 held-out samples it scores 0.56.

It has fifteen revisions over fifteen trails. The last two are a person's countersign; the rest were
sealed by AI agents. The trails are:
- two from 15 November, written before the map existed;
- three runs that the map steered one at a time on 16 November;
- two fleets of three agents that ran at the same time and shared the map as they worked;
- one agent that ran in a sandbox ([below](#the-sandboxed-run));
- three agents that ran at once in the sandbox, to settle forecasts ([below](#fleet-4)).

Rev-10 checked every credit again across agents ([below](#checked-across-agents)).

Every run used `zai-org/GLM-5.3-Flash` through Pi under capture.

```sh
uv run python project.py check  research/madelon-reanalysis/map --live live   # ok: 15 revisions, 15 resolutions, 15 trails
uv run python project.py view   research/madelon-reanalysis/map --live live   # view.txt
uv run python project.py shared research/madelon-reanalysis/map --live live   # shared.txt
uv run python project.py page   research/madelon-reanalysis/map --live live --out research/madelon-reanalysis/map.html
uv run python project.py serve  research/madelon-reanalysis/map --live live   # the same page, live, on 127.0.0.1:8077
#   and http://127.0.0.1:8077/review: each judgment, the steps under it, and a button for a person to seal
uv run python project.py graph  research/madelon-reanalysis/map --live live --out research/madelon-reanalysis/graph --csv
```

`--live live` takes every trail under `live/` whose task names this project. The re-executions in
`retrace/` are used without asking. [map.html](map.html) is the map and its trails drawn as one
page.

## Goals and where they stand

| Goal | State | How |
| --- | --- | --- |
| **explain**: the inherited result does not hold, and selecting features before cross-validation accounts for it | reached | Both trails of 15 November moved the selection inside cross-validation. The estimate then agreed with the held-out AUC of 0.5639. |
| **floor**: an analysis chosen on pilot data alone reaches 0.71 held-out, and its own estimate agrees | reached | One route: a random forest on 30 features selected inside cross-validation, 0.7214 (live-2). Live-1's 0.7185 was withdrawn in rev-6: its design followed per-feature held-out AUCs. |
| **compact**: the same, with at most 50 features counted | reached | Two routes in the second fleet, each scored on the held-out file once: a soft vote of a forest and k-nearest neighbours on 20 features, 0.719 (vote), and a forest on 10 features kept across bootstrap screens, 0.7125 (stable-forest). |

## The revisions

| Rev | What changed, and why |
| --- | --- |
| 0 | **The declared map:** 3 goals, 6 routes and 9 milestones. It was written after the two trails of 15 November, and says so. Only the routes to compact were declared before any run toward them. |
| 1 | **What the two trails reached,** drafted by `propose`. Both reproduced the inherited result and saw it miss, with the same command on the same code tree and data. Both reached `nested`. |
| 2 | **A correction.** rev-1 credited the trails with the L1 route and with a forest on all 500 features. The code they ran shows otherwise: a search over model families (live-1) and a forest on 30 selected features (live-2). Both errors passed `check`, which checks numbers, not methods. The two credits are withdrawn, and the routes the trails did walk are added. |
| 3 | **The first steered run, `screened-forest`.** It built on the cited inherited result instead of rerunning it, and reached the shared milestone `screen`. Its pilot-only design missed `compact-forest` twice, at held-out 0.6989. A later pass met the criteria at 0.7308, but only after steps 38 and 41 had scored candidate designs on the held-out file, so it is not credited. From here every brief carries a rule: the held-out file is scored once, by the final analysis. |
| 4 | **The second steered run, `knn`.** It started from the first run's screen code, and every exploratory script it ran read the pilot data only. Its one held-out score was 0.709, under the floor of 0.71, so `compact-knn` is refuted. A second score after re-tuning, 0.7196, is not credited. |
| 5 | **The third steered run, `svm`.** It started from the same screen. Five pilot-only designs gave nested cross-validated AUCs of 0.66 to 0.68. The run stopped at capture's token ceiling before its held-out score. The route is abandoned, with why. |
| 6 | **Checked, not judged.** The five trails were re-executed under a file trace ([spec 6](../../docs/specs/06-traced-reads.md)). Two credits are withdrawn: `screen`, because screened-forest steps 5 and 8 ranked features by their held-out strength before it, and `floor-search`, because live-1's `diagnose.py` printed held-out AUCs that its next plan used. The refutations and the rest of rev-3 and rev-4 are confirmed. |
| 7 | **Three routes for agents running at once:** boost, stable-forest and vote, all through `screen`. They were declared before any run toward them. |
| 8 | **The first fleet reached nothing.** No run wrote its measures, and each agent read the map once, at its start, so none built on another. |
| 9 | **The second fleet reached compact twice.** The agents built on each other as they ran. Each credit excuses one row count of the held-out file, named and explained in the revision. The revision also discloses one leak of a held-out result between agents, now closed. |
| 10 | **Checked across agents.** The first version 2 revision ([spec 8](../../docs/specs/08-rests-on.md)). Every rev-9 credit rested, through `builds_on`, on sibling runs that had opened the held-out file. Each such read is excused, with why. Nothing is withdrawn. |
| 11 | **The sandboxed run reached nothing.** One agent on `boost`, every command in the sandbox. The wall clock stopped it inside its first search, which the file trace had slowed about thirteen times. `boost` stays open. |
| 12 | **Fleet 4 settled no forecast.** Three agents on `l1`, `forest` and `boost`, in the sandbox, each stopped by the wall clock inside a run. `forest` scored the held-out file once, at 0.694, but its metrics file held a nested object, so the trail has no measure and `floor-forest` is neither credited nor refuted. It was not rerun. |
| 13 | **A person's seal, by mistake without rulings.** Sealed as `human:Antonio` from the review page (`serve`, `/review`) with its default reason, which rules on nothing. It changes nothing in the map. |
| 14 | **The countersign.** `human:Antonio`, from the review page, followed each credit's steps to the trails and re-ran nothing. It confirms the abandonment of `svm`, the four withdrawals, and every revision's reason, which hold the excused reads (rev-9) and the forest's unrecorded held-out look (rev-12). It does not rule one by one on the fifteen credits and refutations. It changes nothing in the map. |

## What the shared milestones did

- **Converged.** `reproduce`, `miss` and `nested` were each reached by both trails of 15 November,
  independently. `shared.txt` shows the same inherited computation run in both: the same command,
  the same code tree and the same input digests.
- **Reused.** None of the three steered runs repeated a cited computation; the "repeated
  computation" list holds only the pair from 15 November. The `knn` and `svm` trails ran code with
  the same tree as the first steered run's screen (`f68ad08`), because their briefs started them
  from it.
- **Steered.** `next` put `screen` first, the milestone three routes were waiting on. Once it was
  credited, the knn and svm briefs built on it. Rev-6 withdrew that credit, so both built on a
  screen chosen after held-out diagnostics. Their outcomes stand as they are: a refutation and an
  abandonment.

## Agents sharing the map

The two fleets ran three agents at once with `scripts/fleet.sh` ([spec 7](../../docs/specs/07-live-map.md)).
Each agent could read the live map through capture's `project_map` tool, and cite what it showed.

**Fleet 1** (30 minutes). Each agent read the map once, at its first step, before any sibling had
found anything, and never again. None of them wrote `out/metrics.json`, so nothing was reached.
Two changes followed:
- capture now tells an agent when its siblings have new observations since it last read the map;
- briefs now ask for the shared milestone's measures to be written.

**Fleet 2** (60 minutes). The agents read the map 3 to 5 times each and built on each other:

| Plan | Builds on | What it used |
| --- | --- | --- |
| boost step-15 | vote step-22 | vote's pilot-only screen (`screen`, cv 0.73) |
| boost step-23 | stable-forest step-56 | stable-forest's stability screen (`screen`, cv 0.755) |
| boost step-29 | stable-forest steps 56 and 59 | the screen, and the fact that it cleared `compact`, numbers withheld |
| stable-forest step-57 | vote step-22 | vote's screen, beside its own |

vote reached `compact-vote` at 0.719, and stable-forest reached `compact-stable-forest` at 0.7125.
boost reached `screen`, then the wall clock stopped it before its held-out score.

**What went wrong, and what the map records about it:**
- **Row counts.** Every agent counted the rows of `data/heldout.csv` while looking around, which
  the trace caught. `check` refuses a credit after such a read unless the revision excuses it and
  says why. rev-9 excuses each one, and `view` shows the excuse next to the read.
- **A held-out result shown to a sibling.** `project_map` withheld vote's number, but it showed
  stable-forest that vote had met `compact-vote`. That fact is itself held-out information.
  Agents are no longer shown such results.
- **Reads outside the workspace.** Fleets 1 and 2 ran without a sandbox. In fleet 2, vote copied
  code from fleet 1's vote workspace, and stable-forest read that workspace's outputs. Fleet 1 had scored
  nothing on the held-out file, and no command read the model key, the Pi configuration, or
  another fleet 2 agent's workspace. A trace keeps only reads inside the agent's own workspace,
  so these reads are known from the command lines alone.

## Checked across agents

rev-9 passed `check`, which then looked for sealed reads only in the cited trail. But a plan that
builds on a sibling's step rests on everything that step rested on. All five of rev-9's holding
credits rested, through `builds_on` links, on runs in other trails that had opened
`data/heldout.csv`:

| Credit | Rests on (other trails) | Their captured held-out reads |
| --- | --- | --- |
| `screen`, boost step-25 | vote to step-22, stable-forest to step-56, both fleet-1 trails, live-2 | fleet2-vote step-5, fleet2-stable-forest step-3, fleet-vote step-5, fleet-stable-forest step-5 |
| `screen`, stable-forest step-56 | fleet-1 stable-forest to step-14, live-2 | fleet-stable-forest step-5 |
| `compact-stable-forest`, stable-forest step-59 | vote to step-22, both fleet-1 trails, live-2 | fleet2-vote step-5, fleet-vote step-5, fleet-stable-forest step-5 |
| `screen`, vote step-22 | fleet-1 vote to step-21, live-2 | fleet-vote step-5 |
| `compact-vote`, vote step-26 | fleet-1 vote to step-21, live-2 | fleet-vote step-5 |

Four distinct runs. Each was the agent looking around before any design, and each counted the
file's rows with `wc -l`. Two also looked at its header line (`head -1`):
- fleet-2 vote step-5 counted its columns;
- fleet-1 stable-forest step-5 printed its last two column names.

None printed a value of the file. rev-10 excuses each read in every credit that rests on it, so
the credits stand, and the judgment is in the revision rather than in the checker. On the page,
each such credit has an amber mark, and its hover text names the reads and the excuses.

The fleets also show why reads outside the workspace mattered. Agents are not sandboxed by
capture alone, and fleet 2's agents read fleet 1's workspaces. From spec 8 on, `fleet.sh` runs
every command in a bwrap sandbox that hides the repository, the trails, the map and the other
workspaces.

## The sandboxed run

One agent ran on `boost` in that sandbox for 30 minutes (`live/madelon-fleet3-boost`, 13 steps,
rev-11). It was the first run of a model in the sandbox; [fleet 4](#fleet-4) ran three more.

**What the sandbox did.**
- `uv`, Python and git worked inside it, and the agent read the map through `project_map`.
- The note at step-1 lists what was hidden: the repository, the directory of workspaces, and Pi's
  two configuration directories.
- No command names a path outside the workspace or reaches the network. That is a reading of all
  four commands, because a trace keeps only reads inside the workspace.
- No run opened `data/heldout.csv`, by the trace of the three runs that settled. It is the first
  trail of this map that never opened the held-out file.
- No process outlived the session.

**What stopped it.** The agent's fourth command was a pilot-only search over four screens. The
wall clock ended the session while it ran, so the run has no observation and nothing was reached.
The file trace is why:

| The first screen of that search | Time | Result |
| --- | --- | --- |
| under the trace, in the sandbox (the agent's run) | 701 s | nested AUC 0.6598 |
| the same command without the trace, on a copy of the workspace | 52 s | nested AUC 0.6598 |

`strace` stops a process at every system call, and a boosted model fitted on many threads makes a
great many. A second measurement, a three-fold fit on random data on an idle machine, took 1.2 s
without the trace and 4.6 s with it; `strace`'s seccomp filter brought that only to 3.9 s. The
cost of knowing what a run opened is therefore large for this kind of work, and a wall clock set
for untraced runs is too short.

**What it does not show.** An agent trying to leave the sandbox, or a held-out score from a
sandboxed run. The sandbox hides named places. The rest of the machine stays readable and the
network open.

## Fleet 4

Three agents ran on `l1`, `forest` and `boost` at once, in the sandbox and under the trace, for 60
minutes (`live/madelon-fleet4-*`, rev-12). The run was made to settle forecasts. A second model and
three code forecasters had each given `floor-l1`, `floor-forest` and `compact-boost` a probability
before any run toward them ([below](#how-sure-the-marks-are)).

It settled none. The wall clock stopped each agent inside a run.

| Agent | Steps | Where it stopped |
| --- | --- | --- |
| l1 | 21 | In a pilot-only comparison of L1 designs (step-20), which had been running for 48 minutes. |
| forest | 27 | In a second run of its final analysis (step-26), with a changed forest. |
| boost | 35 | In a pilot-only nested estimate (step-34). Two earlier searches each ran out their own limit of 20 minutes. It then timed one fit on one, two and four threads (3.1, 4.2 and 4.7 seconds under the trace) and ran on one thread from there. |

**The score the map does not hold.** `forest` chose its design on pilot data and scored the
held-out file once, at step-18. The run took 17 minutes and printed `cv_auc` 0.718, `holdout_auc`
0.694 and `gap` 0.024: under the floor. Its `out/metrics.json` also held a nested object,
`final_config`, and capture reads measures only from one object of names to numbers (the note at
step-20). So step-19 has no measures. `check` credits and refutes from measures alone, and
`floor-forest` stays open. The number is in the session transcript and in the agent's reasoning at
step-25, as text. It was not rerun to have the measures written: that would be a second run on the
held-out file, made knowing the first. The agent's own step-26 was such a second look, and the
wall clock stopped it.

No run of `l1` or `boost` opened the held-out file, by the traces of the runs that finished.

## Checked, not judged

Rev-3 to rev-5 judged held-out peeking by reading code and command lines. Rev-6 reads it from
traces. `retrace.py` re-executed every run from its code snapshot under strace, with no model, and
recorded each file the run opened (`retrace/`).

| Judgment | What the trace showed |
| --- | --- |
| screened-forest steps 38 and 41 scored designs on the held-out file (rev-3) | confirmed: both opened it |
| knn's exploratory scripts read the pilot data only (rev-4) | confirmed: its only held-out reads are its scoring runs, steps 29 and 39 |
| `screen` was a pilot-only design (rev-3) | **wrong**: steps 5 and 8 computed per-feature statistics on the held-out file before it. Rev-3 saw only the command lines. Withdrawn in rev-6 |
| `floor-search` was a pilot-only design (rev-1) | **wrong**: `diagnose.py`, run as `uv run python diagnose.py`, opened the held-out file and printed per-feature AUCs. No command line showed it. Withdrawn in rev-6 |

A trace says a file was opened, not what was done with it. svm's step-5 opened the held-out file to
count its rows. Which reads fed a design is still a judgment, made in a revision's reason.

The map's own structure has a limit too. `miss` and `nested` are scored on the held-out file, and
every floor route passes them, so every trail that reaches a floor node opened the held-out file
first.

**Reproducibility.** On re-execution, every metrics file the runs recorded was written again
byte for byte: 17 of 17. One exit code differed: knn step-42 was a `git commit`, and in the
replayed clone there was nothing left to commit.

From spec 6 on, capture traces every command as it runs. A held-out read before a holding
resolution is then a `check` failure, not a judgment.

## What the map found about the method

On both routes it could judge, the first held-out score of a design chosen on pilot data alone
landed just under the floor: 0.6989 and 0.709. Both runs went on to look again, and the second
look cleared the floor: 0.7308 and 0.7196. Those are forking paths. Within each trail the order
is visible, and the map only records it because a revision cited the first score.

`propose` now marks a candidate that follows misses of the same milestone (`after_misses`). That
puts the second look in front of whoever seals the revision.

## How sure the marks are

`beliefs.py show` ([beliefs.txt](beliefs.txt)) reads the map as a belief network, with the noise
declared in [beliefs/assumptions.json](beliefs/assumptions.json): a held-out AUC near 0.71 on
1,100 rows of each class has a standard error of 0.0109. Every resolution at the floor is within
noise: `floor-selected-forest` stands 1.05 standard errors above it, `compact-vote` 0.83,
`compact-stable-forest` 0.23, and `compact-knn` was refuted 0.09 below it. For `compact-vote` to
clear the floor at 95%, it would take 4.0 times the rows; for `compact-stable-forest`, 51 times.

`compact` was reached by two of the four routes scored on the held-out file. How sure that is
depends on how related the routes are, which four scores cannot say:

| If the routes' true AUCs are | P(at least one credited route truly clears the floor) |
| --- | --- |
| unrelated (a flat prior on each) | 0.80 with shared errors, 0.92 with independent ones |
| drawn about a shared mean | 0.75 |
| one value | 0.49 |

The four scores differ by a standard deviation of 0.0084, under the 0.0109 error of one score, so
they do not tell the routes apart. The report also counts the looks: 32 runs in 12 trails opened
the held-out file.

A milestone's Markov blanket follows the order of the routes: what comes before it, what comes
after, and what else leads to the same place. It leaves out what that order does not carry. The
`compact` scores bear on the open `floor` milestones, which are measured on the same criterion
over the same file, and they sit outside those blankets. So the report gives each open milestone
two numbers: from its blanket, and from every score on the same criterion across the map. For
`compact-boost` they are 0.49 and 0.59. For the three open `floor` milestones they are 0.75, a
crude rate from one scored sibling, and 0.59. The ranking by what settling each would tell about
its goal says nothing here: every value is under 0.02 bits, in the order `next` gives.

### The forecaster

[forecasts/scores.txt](forecasts/scores.txt) scores a second model, Gemma 4 31B on Berget, asked
26 questions once each, with no tools: the 8 milestones whose first resolution stands, each at
the revision before it, the 4 open ones, and the 14 plans whose first run settled them. Code
built each text and scored every answer. Five milestone questions could not be asked, because
the credit was later withdrawn or the milestone appeared with its resolution.

A [review](../../docs/specs/11-beliefs-review.md) of the first scores found that most of the 22
settled questions were not forecasts. Four milestone outcomes were known when the question's
revision was written (‡): rev-0 was written the day after the runs that settle `reproduce`, `miss`
and `nested`, and `screen` at rev-8 followed from the milestones after it. Twelve plans came after
their trail had opened the held-out file (†). `score` now marks both and scores the rest apart,
beside a coin flip:

| Questions | Gemma 4 31B | code:even | code:base-rate | code:blanket | code:pooled |
| --- | --- | --- | --- | --- | --- |
| 8 milestones | Brier 0.246 | 0.250 | 0.311 | 0.313 | 0.339 |
| the 4 not marked ‡ | 0.433 | 0.250 | 0.406 | 0.410 | 0.463 |
| 14 plans | 0.180 | 0.250 | 0.287 | | |
| the 2 not marked † | 0.425 | 0.250 | 0.217 | | |

On the six real forecasts the model did worse than the coin flip. On all 8 milestones it stands
0.004 ± 0.104 below it, within noise. `code:pooled` did no better than `code:blanket`, and at
rev-2 it gave 1.00 from two scores 0.003 apart and missed: a predictive from two scores is too
sure of itself. On `madelon-route-screened-forest` step-43 the model answered 0.9 after reading,
in the agent's own reasoning, held-out scores that step-41 printed.

The four open milestones carried the only forecasts made before their outcomes, and the code
forecasters' values were committed before [fleet 4](#fleet-4) started:

| Milestone | Gemma 4 31B | code:blanket | code:pooled | After fleet 4 |
| --- | --- | --- | --- | --- |
| `floor-l1` | 0.10 | 0.75 | 0.59 | open: no held-out score |
| `floor-forest` | 0.10 | 0.75 | 0.59 | open: scored 0.694, under the floor, but not as a measure |
| `compact-boost` | 0.60 | 0.49 | 0.59 | open: no held-out score |
| `floor-search` | 0.90 | 0.75 | 0.59 | not run |

No forecast is settled. The one score that was printed agrees with the model's 0.10 against the
code forecasters. It is one score, and the map does not hold it.

## Limits

- **Methods.** `check` recomputes criteria, not methods. Rev-2 exists because two method claims
  were wrong and passed.
- **Who judged.** Not crediting the two second looks, and abandoning `svm`, were judgments,
  written in the revisions' reasons by the agent that sealed them
  (`agent:claude-code/claude-opus-5-5`). A later revision can reverse either. Rev-0 to rev-12
  were sealed by AI agents, named in their `by`. A person countersigned at rev-14, confirming
  those judgments and every reason, but not each credit one by one (rev-13 was their first seal,
  made with no rulings).
- **Re-executed reads are leads, not proof.** They come from a replay, not the run itself. Only
  a read captured as the run happened fails `check`. For runs from before spec 6, the command
  line is the weakest lead, used only where there is no trace.
- **The steering rule ranks by structure only.** The milestone that the most open routes wait on
  comes first. Live-1's printed per-family scores (forest 0.72, kNN 0.66, SVM 0.65) predicted the
  order the routes fared in, but they are not measures, so `next` does not use them.
- **The trace is slow.** It cost about thirteen times on the one command measured both ways
  ([above](#the-sandboxed-run)). No sandboxed agent, of four, recorded a held-out score before
  its wall clock.
- **Beliefs are advisory and rest on assumptions.** A declared standard error, and a range over
  how related the routes are. Of 22 settled forecasts, 6 were real forecasts, all backtests. No
  forecast made before its outcome has been settled.
- **Scale.** One model, one task, three steered runs, three fleets of three agents and one sandboxed run: this demonstrates
  the mechanism, not a study of it.

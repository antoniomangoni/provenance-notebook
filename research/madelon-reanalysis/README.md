# Research map: the Madelon re-analysis

This map covers the demo task (`demo/`). An inherited analysis reports a cross-validated AUC of
0.76, and on 2200 held-out samples it scores 0.56.

It has ten revisions over eleven trails:
- two from 15 November, written before the map existed;
- three runs that the map steered one at a time on 16 November;
- two fleets of three agents that ran at the same time and shared the map as they worked.

Every run used `zai-org/GLM-5.3-Flash` through Pi under capture.

```sh
uv run python project.py check  research/madelon-reanalysis/map --live live   # ok: 10 revisions, 15 resolutions, 11 trails
uv run python project.py view   research/madelon-reanalysis/map --live live   # view.txt
uv run python project.py shared research/madelon-reanalysis/map --live live   # shared.txt
uv run python project.py page   research/madelon-reanalysis/map --live live --out research/madelon-reanalysis/map.html
uv run python project.py serve  research/madelon-reanalysis/map --live live   # the same page, live, on 127.0.0.1:8077
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
- **Reads outside the workspace.** Agents are not sandboxed. In fleet 2, vote copied code from
  fleet 1's vote workspace, and stable-forest read that workspace's outputs. Fleet 1 had scored
  nothing on the held-out file, and no command read the model key, the Pi configuration, or
  another fleet 2 agent's workspace. A trace keeps only reads inside the agent's own workspace,
  so these reads are known from the command lines alone.

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

## Limits

- **Methods.** `check` recomputes criteria, not methods. Rev-2 exists because two method claims
  were wrong and passed.
- **Who judged.** Not crediting the two second looks, and abandoning `svm`, were judgments,
  written in the revisions' reasons by the agent that sealed them
  (`agent:claude-code/claude-opus-5-5`). A later revision can reverse either.
- **Re-executed reads are leads, not proof.** They come from a replay, not the run itself. Only
  a read captured as the run happened fails `check`. For runs from before spec 6, the command
  line is the weakest lead, used only where there is no trace.
- **The steering rule ranks by structure only.** The milestone that the most open routes wait on
  comes first. Live-1's printed per-family scores (forest 0.72, kNN 0.66, SVM 0.65) predicted the
  order the routes fared in, but they are not measures, so `next` does not use them.
- **Scale.** One model, one task, three steered runs and two fleets of three agents: this demonstrates the mechanism, not a
  study of it.

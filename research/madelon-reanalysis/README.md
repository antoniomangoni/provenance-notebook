# Research map: the Madelon re-analysis

This map covers the demo task (`demo/`). An inherited analysis reports a cross-validated AUC of
0.76, and on 2200 held-out samples it scores 0.56.

It has six revisions over five trails: two from 15 November, written before the map existed,
and three runs that the map steered on 16 November. All five runs used `zai-org/GLM-5.3-Flash`
through Pi under capture.

```sh
T="live/madelon-2026-11-15-1 live/madelon-2026-11-15-2 live/madelon-route-screened-forest live/madelon-route-knn live/madelon-route-svm"
uv run python project.py check  research/madelon-reanalysis/map --trails $=T    # ok: 6 revisions, 12 resolutions, 5 trails
uv run python project.py view   research/madelon-reanalysis/map --trails $=T    # view.txt
uv run python project.py shared research/madelon-reanalysis/map --trails $=T    # shared.txt
uv run python project.py graph  research/madelon-reanalysis/map --trails $=T --out research/madelon-reanalysis/graph --csv
```

(`$=T` splits the list in zsh; in bash write `$T`.)

## Goals and where they stand

| Goal | State | How |
| --- | --- | --- |
| **explain**: the inherited result does not hold, and selecting features before cross-validation accounts for it | reached | Both trails of 15 November moved the selection inside cross-validation. The estimate then agreed with the held-out AUC of 0.5639. |
| **floor**: an analysis chosen on pilot data alone reaches 0.71 held-out, and its own estimate agrees | reached | Two routes, both a random forest on 20 to 30 features selected inside cross-validation: 0.7185 (live-1) and 0.7214 (live-2) |
| **compact**: the same, with at most 50 features counted | not reached | Every route to it is blocked or abandoned. See below. |

## The revisions

| Rev | What changed, and why |
| --- | --- |
| 0 | **The declared map:** 3 goals, 6 routes and 9 milestones. It was written after the two trails of 15 November, and says so. Only the routes to compact were declared before any run toward them. |
| 1 | **What the two trails reached,** drafted by `propose`. Both reproduced the inherited result and saw it miss, with the same command on the same code tree and data. Both reached `nested`. |
| 2 | **A correction.** rev-1 credited the trails with the L1 route and with a forest on all 500 features. The code they ran shows otherwise: a search over model families (live-1) and a forest on 30 selected features (live-2). Both errors passed `check`, which checks numbers, not methods. The two credits are withdrawn, and the routes the trails did walk are added. |
| 3 | **The first steered run, `screened-forest`.** It built on the cited inherited result instead of rerunning it, and reached the shared milestone `screen`. Its pilot-only design missed `compact-forest` twice, at held-out 0.6989. A later pass met the criteria at 0.7308, but only after steps 38 and 41 had scored candidate designs on the held-out file, so it is not credited. From here every brief carries a rule: the held-out file is scored once, by the final analysis. |
| 4 | **The second steered run, `knn`.** It started from the first run's screen code, and every exploratory script it ran read the pilot data only. Its one held-out score was 0.709, under the floor of 0.71, so `compact-knn` is refuted. A second score after re-tuning, 0.7196, is not credited. |
| 5 | **The third steered run, `svm`.** It started from the same screen. Five pilot-only designs gave nested cross-validated AUCs of 0.66 to 0.68. The run stopped at capture's token ceiling before its held-out score. The route is abandoned, with why. |

## What the shared milestones did

- **Converged.** `reproduce`, `miss` and `nested` were each reached by both trails of 15 November,
  independently. `shared.txt` shows the same inherited computation run in both: the same command,
  the same code tree and the same input digests.
- **Reused.** None of the three steered runs repeated a cited computation; the "repeated
  computation" list holds only the pair from 15 November. The `knn` and `svm` trails ran code with
  the same tree as the first steered run's screen (`f68ad08`), because their briefs started them
  from it.
- **Steered.** `next` put `screen` first, the milestone three routes were waiting on. Once it was
  reached, the knn and svm briefs built on it.

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
- **`sealed_inputs` gives leads, not proof.** It finds a run whose command line names the
  held-out file, but not a script that reads it without naming it.
- **The steering rule ranks by structure only.** The milestone that the most open routes wait on
  comes first. Live-1's printed per-family scores (forest 0.72, kNN 0.66, SVM 0.65) predicted the
  order the routes fared in, but they are not measures, so `next` does not use them.
- **Scale.** One model, one task and three steered runs: this demonstrates the mechanism, not a
  study of it.

# Spec 5: a research map over many trails

Branch `spec/05-research-map`, stacked on `spec/04-evidence-plain` (PR #10).

A trail records one path through one task. A research project has several possible end
results, several routes to each, and milestones that more than one route passes through. This
spec adds the **research map**, a graph of those goals, routes and milestones that cites trails.
It is the "larger graph" of [GRAPH.md](../GRAPH.md#the-boundary): it points in at probes pinned
at their heads and never edits them, so nesting stays at two levels. Every route run is one
probe inside it.

The map does three things with the nodes routes share:

- **Shows convergence.** It shows where routes meet: the same milestone, data, code or
  computation.
- **Reuses results.** A route that starts after a shared milestone is resolved begins from it:
  the task cites the resolving step, and the workspace is that step's code.
- **Steers.** The open milestone that the most open routes pass through is run first.

The map is declared before the runs it steers, and it changes as trails come in. Each change is
a new revision chained to the last, and it cites the steps that prompted it.

**The first revision is written after the two Madelon trails of 15 November**
(`live/madelon-2026-11-15-1` and `-2`) and says so. Only the routes run after it are steered by
the map.

## Goals

1. `project.py` checks a chain of map revisions against the trails it cites. It recomputes
   every claim that a milestone was reached from the cited observation's measures.
2. `propose` drafts the next revision from new trails; `seal` appends it.
3. `next` ranks the open milestones; `brief` writes the demo directory for one route, with
   reuse.
4. `shared` reports convergence and repeated computation. `graph` adds the map to the merged
   tables. `view` prints the whole map as text.
5. Capture writes a task file's optional `builds_on` as step 0's links.
6. A Madelon map, `research/madelon-reanalysis/`:
   - rev-0, declared;
   - rev-1, from the two existing trails;
   - up to three new route runs that the map steers, each followed by a revision.

## Non-goals

- Any change to `step.schema.json`, to the rules in `trail.check`, or to `examples/`.
- Any edit to an existing trail under `live/`.
- Checking that a route's *method* was used. The checker recomputes a milestone's criteria from
  measures. The method a resolution claims is shown beside the cited plan's own reasoning, for a
  reader to judge.
- An HTML view of the map. It is the first thing cut.

## Technical decisions

### A map revision

`research/PROJECT/map/rev-N.json` is written once, as canonical JSON (`trail.canonical`). It is
a whole snapshot, so the difference between two revisions is the change.

| Field | Contents |
| --- | --- |
| `version` | `1` |
| `project` | the trails' project, `madelon-reanalysis` |
| `rev` | `N`, from 0 |
| `prev` | from rev 1 on: `sha256:` of the previous revision's canonical JSON |
| `at`, `by` | UTC time; `human:NAME` or `agent:NAME` |
| `reason` | why this revision, at most 4,000 characters |
| `triggered_by` | probe references `[PROJECT/]probe:T@HEAD#step-N` that prompted it, possibly none |
| `goals` | `{id, statement}` |
| `nodes` | `{id, statement, criteria}`: a milestone; `criteria` are expectations as a plan states them (`name`, `measure`, `comparison`, `threshold`), measured ones only |
| `routes` | `{id, goal, method, path, status}`: `path` is node ids in order, `status` is `open` or `abandoned`, and an abandoned route has `why` |
| `resolutions` | `{node, cites, holds}`: `cites` is an observation, `probe:T@HEAD#step-N` |
| `instructions` | optional, added in rev-3: text every later brief carries under "Rules for every route of this map" |
| `sealed_inputs` | optional, added in rev-3: paths only a resolution's own run may read. `view` lists, under each resolution, the earlier runs in its trail whose command names one. This gives a reader a lead, not a check: a script that reads the file without naming it on the command line is not found |

**Rules that `check` enforces:**

- **The chain.** Revision N is `rev-N.json` with `rev` N, and every `prev` matches.
- **Ids.** Ids are unique within their kind and use the trail slug's alphabet.
  - A route's `goal` is a goal, and its `path` is one or more existing nodes with none repeated.
  - Every goal has a route.
  - Every node is on a route.
- **Resolutions.** Each `cites` names a trail that is given, at a head that trail had, and an
  observation it had written by that head.
  - `holds` is what `trail.holds` gives for every criterion, applied to that observation's
    measures. A criterion whose measure the observation does not have makes the resolution
    fail.
- **`triggered_by`.** It resolves in the same way, to a step of any kind.
- **`by`.** It matches the step schema's actor pattern for `human` or `agent`.

**Derived state, never stored:**

- **Reached.** A node is reached when some resolution of it `holds: true`.
- **Refuted.** A node is refuted when it has a resolution with `holds: false` and none with
  `holds: true`.
- **A route is:**
  - *done* when every node on it is reached;
  - *blocked* when a node on it is refuted;
  - otherwise *open*, with its next node being the first one not reached.
- **A goal is reached** when one of its routes is done.

### Commands

`project.py COMMAND MAP --trails T… [options]`. MAP is the `map/` directory, and the last
revision is the map. Each T is a trail directory.

| Command | Prints or writes | Exit |
| --- | --- | --- |
| `check` | the problems, or `ok: N revisions, R resolutions` | 0 or 1 |
| `propose [--out FILE]` | a draft of the next revision, as JSON | 0 |
| `seal DRAFT --by ACTOR` | writes `rev-N.json` | 0, or 1 when the result fails `check` |
| `next` | the open routes' next nodes, ranked | 0 |
| `brief ROUTE --out DIR [--demo DIR]` | a demo directory for `scripts/live.sh` | 0 or 2 |
| `shared` | the convergence report | 0 |
| `graph --out DIR [--csv]` | `nodes` and `edges` tables | 0 or 1 |
| `view` | the map as text | 0 |

Every command except `check` and `seal` checks first, and stops with exit 1 on a problem.

**`propose`.** The draft is the last revision with `rev`, `prev`, `at` and `by` removed. It adds:

- **`candidates`.** For each trail whose step 0 summary begins `Route ROUTE:`, its
  observations are walked in order against that route's path, starting at the route's next
  node. An observation that meets the next node's criteria is a candidate resolution, and the
  walk moves on, since one observation may meet several nodes in a row. A candidate that holds lists, as `after_misses`, the trail's earlier observations
  that measured the same node and missed it: a hit after a miss may be a second look. Once the walk stops, the
  trail's last observation that has every measure the next node needs becomes a candidate with
  `holds: false`.
- **The same walk for a trail without a route,** against every open route, with the routes it
  could resolve listed on each candidate.
- **`reason` lines,** one for each plan that `supersedes` another plan and is not cited by
  any resolution: the trail, the step and its summary. These are candidate new nodes or routes.

`seal` refuses a draft that still holds `candidates`. A person or agent moves the candidates
they accept into `resolutions`, deletes the rest, and rewrites `reason`.

**`next`.** It ranks the next nodes of open routes. The key, highest first:

1. the number of open routes whose next node it is;
2. the number of routes whose path holds it;
3. its id.

For each node it prints the routes it leads, and whether one of them belongs to a goal not yet
reached.

**`brief`.** It writes `DIR/task.json`, `DIR/prompt.md` and `DIR/workspace/`. The route must be
open.

- **`task.json`:**
  - starts from `--demo` (default `demo/`) `task.json`;
  - the summary is `Route ROUTE: …`, cut to 200 characters;
  - `declared_measures` adds every measure the route's criteria name;
  - `builds_on` cites the newest resolution of the last reached node before the route's next
    node, pinned at its head, when there is one.
- **`workspace/`:**
  - **with a cited step:** the files of that trail's code snapshot at the cited run, taken from
    the trail's `code.bundle` with `git archive`;
  - **otherwise:** the demo's workspace;
  - `out/` and `.venv/` are left out either way.
- **`prompt.md`:**
  - the demo's prompt;
  - then the route's method;
  - then the criteria the next node and each later node must meet;
  - then the cited results, with their measures, which the agent is told not to recompute.

**`shared`.** Four sections:

1. **Milestones on two or more routes,** with the trails that resolved each one.
2. **Files** used by two or more trails at the same digest.
3. **Code by tree:** for each run, the tree of its snapshot commit, read from the trail's
   `code.bundle`. A commit hash differs between trails even when their files match, so trees
   are compared instead.
4. **Repeated computation:** runs in two or more trails with the same command digest, code
   tree and input digests. These are computations that reuse would have saved.

**`graph`.** It returns `trail.merge` of the trails, plus the map, in graph
`PROJECT/map:rev-N`.

- **Nodes:**
  - `PROJECT/goal:ID`, `PROJECT/milestone:ID` and `PROJECT/route:ID`, at tier 3;
  - `label` is the statement or the method;
  - `outcome` is `reached`, `refuted` or empty for a milestone, and `done`, `blocked`, `open` or
    `abandoned` for a route.
- **Edges:**
  - `route aims_at goal`;
  - `route passes milestone`;
  - `milestone resolved_by` or `refuted_by` the cited step, with the head on the edge;
  - `PROJECT/map:rev-N triggered_by` each cited step.

**`view`.** It prints:

- the project and its revision;
- each goal with its state;
- each route as `reproduce ✓ → miss ✓ → screen ○ → floor-knn ○`, where ✓ is reached, ✗ refuted
  and ○ open, with a `*` on shared nodes;
- for each reached node, its resolution's trail, step and summary;
- `next`.

### Capture

`task.json` may hold `builds_on`, a list of probe references pinned at a head. `readTask`
checks the form against the pattern the schema uses for a link target. `taskStep` writes each
one as a `builds_on` link with status `confirmed`. This is a change to an interface listed in
[PLAN.md](../../PLAN.md#interfaces-the-slices-share), approved with this spec's plan. A task
file without the field gives the same step 0 as before.

### The Madelon map, rev-0

- **project:** `madelon-reanalysis`;
- **by:** the actor who seals each revision. This session seals as `agent:claude-code/claude-opus-5-5`.

`gap` is `cv_auc − holdout_auc`.

| Node | Criteria |
| --- | --- |
| `reproduce` | `cv_auc` ≥ 0.75 |
| `miss` | `holdout_auc` < 0.71 |
| `nested` | `gap` ≤ 0.05, `gap` ≥ −0.05, `holdout_auc` < 0.71 |
| `floor-l1`, `floor-forest` | `holdout_auc` ≥ 0.71, `gap` ≤ 0.05, `gap` ≥ −0.05 |
| `screen` | `n_features` ≤ 50, `cv_auc` ≥ 0.70 |
| `compact-knn`, `compact-forest`, `compact-svm` | `holdout_auc` ≥ 0.71, `gap` ≤ 0.05, `gap` ≥ −0.05, `n_features` ≤ 50 |

| Goal | Statement |
| --- | --- |
| `explain` | The inherited result does not hold, and selecting features before cross-validation accounts for it |
| `floor` | An analysis chosen on pilot data alone reaches a held-out AUC of 0.71, and its own estimate agrees |
| `compact` | The same, with at most 50 features |

| Route | Goal | Path | Method |
| --- | --- | --- | --- |
| `explain` | explain | reproduce, miss, nested | selection moved inside cross-validation |
| `l1` | floor | reproduce, miss, nested, floor-l1 | L1-penalised logistic regression, tuned inside cross-validation |
| `forest` | floor | reproduce, miss, floor-forest | a random forest on all features |
| `knn` | compact | reproduce, miss, screen, compact-knn | a pilot-only screen, then k-nearest neighbours |
| `screened-forest` | compact | reproduce, miss, screen, compact-forest | a pilot-only screen, then a random forest |
| `svm` | compact | reproduce, miss, screen, compact-svm | a pilot-only screen, then an RBF support vector machine |

`reproduce` and `miss` lie on all six routes. `nested` lies on three and `screen` on three.

### Runs

The model is `zai-org/GLM-5.3-Flash`, through the scratch Pi settings used for the live trails.
The steps are:

1. **One run first:** `next`, then `brief` for the top route, then `scripts/live.sh`.
2. **After each run:**
   - commit the trail, failed ones too;
   - `propose`, edit and `seal` the next revision;
   - commit it before the next brief.
3. **At most three new runs.** Each stays under capture's existing ceilings and the launcher's
   wall clock.

## Project structure

| Path | Contents |
| --- | --- |
| `project.py` | the commands |
| `tests/test_project.py` | the rules below |
| `research/madelon-reanalysis/map/rev-N.json` | the revisions |
| `research/madelon-reanalysis/briefs/ROUTE/` | each brief as given to the launcher, with its workspace's data left out (`brief.json` records the data's digests) |
| `research/madelon-reanalysis/shared.txt`, `view.txt`, `graph/` | the outputs, regenerated by the commands |
| `live/madelon-route-*` | the new trails, written by the launcher |

## Testing

1. **The chain.** A broken `prev`, a missing revision or a wrong `rev` fails `check`.
2. **Ids.** A route through an unknown node, a goal without a route, and a node on no route
   each fail `check`.
3. **Resolutions.**
   - A resolution whose `holds` disagrees with the recomputed criteria fails `check`.
   - So does one that cites a head the trail never had, a step that is not an observation, or a
     trail that was not given.
4. **Live trails.** The live-1 resolutions of `reproduce`, `miss`, `nested` and `floor-l1`, and
   live-2's of `floor-forest`, pass `check`.
5. **Blocking.** A refuted node blocks every route through it. `next` leaves blocked routes
   out.
6. **`next`.** It ranks a node shared by three open routes above one on a single route.
7. **`propose`.**
   - A route-tagged trail gives candidates for that route only.
   - The walk resolves successive nodes from one observation.
   - `seal` refuses a draft with `candidates`.
8. **`shared`.** It finds the inherited `uv run python analysis.py` repeated in live-1 step 7
   and live-2 step 6: the same command digest, inputs and code tree.
9. **`brief`.**
   - It writes `builds_on` for the last reached node.
   - It writes a workspace equal to the cited snapshot, and a prompt that states the next
     node's criteria.
10. **`graph`.** It holds every map node, and one `resolved_by` edge per holding resolution
    with the head as digest. Its rows include `trail.merge`'s rows unchanged.
11. **Capture.**
    - A task file with `builds_on` gives step 0 that link, and the trail checks.
    - A malformed reference stops capture at load.

## Sequence

1. This spec and a PLAN.md decision row. Commit.
2. `project.py`: `check`, the derived state and `view`; tests 1 to 5. Commit.
3. `next`, `propose`, `seal`; tests 6 and 7. Commit.
4. `shared`, `graph`, `brief`; tests 8 to 10. Commit.
5. Capture's `builds_on`; test 11. Commit.
6. rev-0, then `propose` and `seal` rev-1 from live-1 and live-2. Commit both before any run.
7. The runs, each followed by its revision, as under [Runs](#runs).
8. `shared.txt`, `view.txt`, `graph/` and the pull request. It is not merged without the user.

## Target files

- `docs/specs/05-research-map.md`
- `project.py`
- `tests/test_project.py`
- `capture/capture.ts`
- `tests/test_capture.py`
- `tests/fixtures/capture-demo/`, for a task file with `builds_on` if needed
- `research/`
- one row in `PLAN.md`'s decisions
- `live/madelon-route-*`, written only by the launcher

## Commands

```sh
uv run pytest && uv run ruff check
uv run python project.py check research/madelon-reanalysis/map --trails live/madelon-2026-11-15-1 live/madelon-2026-11-15-2
uv run python project.py view  research/madelon-reanalysis/map --trails live/madelon-*
```

Style follows `trail.py` and `tamper.py`: plain functions over dicts, errors as strings naming
where, no new dependency.

## Boundaries

- **Always:**
  - Recompute every outcome a map revision claims.
  - Commit each trail and each revision as soon as it exists.
  - Report runs that failed.
- **Ask first:**
  - A fourth run.
  - A model other than GLM-5.3-Flash.
  - Any change to a sealed revision's content. A change is a new revision.
- **Never:**
  - Edit `live/` or `examples/` by hand.
  - Rerun a route to replace a trail.
  - Write a key anywhere.

## Rejection criteria

- `check` passes on a resolution whose criteria do not hold, or on a broken chain.
- Any revision is edited after it is sealed.
- A briefed trail repeats the computation of the step it builds on, and `shared` does not
  show it.
- rev-0 does not say it was written after the two existing trails.

## Self-audit

After each step of the sequence:

- read the diff against the goals, non-goals and rejection criteria;
- `git diff main --stat -- examples live/madelon-2026-11-15-*` is empty.

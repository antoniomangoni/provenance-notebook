# Spec 9: what a run opened, on the reviewer's page

Branch `spec/09-reads-on-the-page`, from `main`.

Since spec 6 an observation records the workspace files its run opened, and a research map's
`check` refuses a credit that follows a read of a sealed input. The reviewer's page of one trail
shows none of it. `facts` reports only reads beyond a run's declared inputs, so a held-out file
that the task declares is never mentioned. The evidence says so of its own fifth question:
"Neither the view nor the trail flags it."

The agent-systems research this repository was measured against names the pattern: provenance
that is recorded and then dropped before it reaches the reader, and a record of how a link was
established that the reader is never shown.

## Goals

1. **The page shows what each run opened**, and how that is known: traced as the run happened, or
   found when the run was executed again.
2. **A reader can name a sealed input**, a file that a design should not have seen. The page,
   `facts` and `why` then say which runs had opened it before each plan was proposed.
3. **Two acceptance checks from the research** hold: committed map outputs equal a rebuild, and a
   provider that reports no token usage is said, not counted as zero.

## Non-goals

- **Declaring sealed inputs in the task.** That would change the step format. The reader names
  them, as a map's `sealed_inputs` does.
- **Judging a read.** A fact says a file was opened before a plan, not that the plan used it.
- **Changing `step.schema.json` or `trail.check`.**

## Technical decisions

### What was opened (`trail.py`)

- **`opened(steps, retraced=None)`** returns, for each run whose reads are known, how they are
  known and the files:
  - `traced as it ran`, when the run's observation carries `reads`;
  - `on re-execution`, when only a `retrace.py` file has them.

  A run in neither is absent: it was not traced, and nothing is claimed about it.
- **`retraced(path, steps)`** loads a `retrace.py` file. It refuses a file written for another
  trail, or at a head this trail never had.
- **`before(steps, reads, sealed)`** gives, for each plan and each sealed path, the earlier runs
  that opened the path, whether each wrote metrics, and how many earlier runs were not traced.
- **`facts(steps, reads=None, sealed=())`** gains, for each plan that has a measured run:
  `step-14: proposed after 4 runs had opened data/heldout.csv: step-7 (measured), step-12 (wrote
  no metrics); known on re-execution`. Earlier runs that were not traced are counted in the same
  line. When no run of the trail was traced, one line says that instead.

### The command line

`trail.py view|facts|why DIR … [--reads FILE] [--sealed PATH]…`
- `--reads` is a `retrace.py` file for this trail.
- `--sealed` may be given more than once. A path is relative to the workspace, as an input is.

### The page (`view.py`)

- **Each run** whose reads are known gains an "Opened" row: the declared inputs it opened by
  name, the number of other workspace files, and how that is known. A sealed one is tagged.
- **With a sealed input:**
  - a "Sealed inputs" section after the decision path lists each run that opened one, in order,
    with its plan and whether it wrote metrics;
  - each plan, and each change-of-approach card, says which runs had opened it before the plan
    was proposed;
  - `why STEP` says the same for a change of approach.
- **A trail with no recorded reads, viewed with no options, renders to the same bytes as
  before.** The evidence's `view.txt` is such a page.
- Every opened path is escaped.

### From the map (`mapview.py`)

`serve`'s `/trail/NAME` passes the map's `sealed_inputs` and its `retrace/` reads to the page.

### Two checks

- **Equal to a rebuild.** A test regenerates `research/madelon-reanalysis/view.txt` and
  `shared.txt` and compares them with the committed files.
- **Unknown usage is said** (`capture/capture.ts`). The first turn that reports no finite token
  count writes one runner note: the token ceiling cannot stop this session. The run and
  wall-clock ceilings still apply.

## Testing

- `facts` on `live/madelon-2026-11-15-1`, with its retrace file and `data/heldout.csv` sealed,
  says step-14 was proposed after step-12 opened it.
- A retrace file for another trail is refused.
- The page of a trail traced as it ran says so on a run.
- The page of the churn example, and of `live/madelon-2026-11-15-1` with no options, is the same
  bytes as on `main`.
- An opened path holding `<script>` is escaped.
- `/trail/NAME` shows the sealed section.
- The committed `view.txt` and `shared.txt` equal a rebuild.
- A scripted turn with no usage writes the note once.

## Boundaries

- **Never:** change a file under `evidence/`, `examples/` or `live/`.
- `step.schema.json` and `trail.check` do not change.

## Target files

- `docs/specs/09-reads-on-the-page.md`, one `PLAN.md` row
- `trail.py`, `view.py`, `mapview.py`
- `capture/capture.ts`, `capture/scripted.ts`
- `tests/test_trail.py`, `tests/test_view.py`, `tests/test_mapview.py`, `tests/test_project.py`,
  `tests/test_capture.py`
- `docs/DESIGN.md`: the facts list and the page's description

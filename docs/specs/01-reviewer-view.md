# Spec 1: the reviewer view

Branch `spec/01-reviewer-view`. Depends on no other spec. The live run and spec 4 depend on it.
Written to [the meta-spec](../meta-spec.md); [AGENTS.md](../../AGENTS.md) applies throughout.

A reviewer who was not present must be able to answer "why did they change approach at step 4?"
from the trail alone. Today the answer is in the step files' links, and nothing shows it. This
spec adds the two things a reviewer reads, a text answer and a page, and the facts and human
steps they need.

## Goals and non-goals

Goals:

1. `trail.py why DIR [STEP]` prints the answer to the brief's question from the links.
2. `trail.py view DIR` writes one self-contained HTML page that leads with the decision path.
3. `trail.py facts` tells exploratory commands from attempts, and reports an eased threshold.
4. `trail.py review` and `trail.py note` append a person's step to a trail.

Non-goals:

- No change to `step.schema.json`, to any rule in `trail.check`, or to what `trail.py examples`
  writes.
- No server, no JavaScript, no template engine, no new dependency.
- No inference. `why` and the page state only what steps and links say, through fixed
  templates. They never summarise or reword an agent's text.
- No rendering of merged trails or of the graph export.
- Nothing under `capture/`, `demo/`, `scripts/` or `live/`.

## Terms

- **Change of approach**: a plan step with a `supersedes` link to an earlier plan.
- **Trigger**: the observation its `triggered_by` link points at. When the link cites another
  probe, the trigger is shown as that citation, with no numbers.
- **Missed expectation**: an expectation of the plan the trigger tests whose check has
  `held: false`. An observation with outcome `failed` is shown as "exit code N".
- **Measured run**: a run whose observation has `measures_source`. **Exploratory command**: a
  run whose observation has none. **Unsettled run**: a run with no observation.
- **Exploration plan**: a plan whose every expectation compares with `exit_ok` or `exit_fail`.

Comparisons print as `<`, `<=`, `==`, `>=`, `>`. Numbers print with `format(x, "g")`.

## Behaviour

### `why DIR [STEP]`

For a change of approach, the output names, in this order: the replaced plan (id, summary); the
trigger (id) with each missed expectation as `measure measured, expected comparison threshold
(name)`; the new plan (id, summary); its reasoning, in full and unchanged; each review or note
on the new plan, the replaced plan or the trigger (id, verdict, text).

On `examples/churn-model-2026-11-11 step-4` the output therefore contains `step-1`, `step-3`,
`auc 0.58, expected >= 0.75 (auc-floor)`, step 4's reasoning, `step-7` and `confirms`.

- With no `STEP`: one line per change of approach, in order, or `No plan was replaced.`
- `STEP` is not a change of approach: one line saying what kind of step it is, and the change
  of approach it took part in (as its trigger, as the replaced plan, or as a run or observation
  under either), if any. Exit 0.
- `STEP` is not in the trail: a message and exit 1.
- The trail fails `check`: the problems and exit 1, as the other commands do.

### `view DIR [--store STORE] [--code REPO] [--out FILE]`

Writes `DIR/view.html`, or `FILE`. Writes nothing and exits 1 when the trail fails `check`.
The page has, in order:

1. **Header.** The task's summary and question, the agent and model, the trail's name, its
   number of steps and the head digest.
2. **Decision path.** One sentence per change of approach, each linking to its card:
   "At step-4 the plan changed: step-3 measured auc 0.58, expected >= 0.75." With none: "The
   plan was never replaced."
3. **A card per change of approach**, in an element with id `change-step-N`: the replaced plan
   and its expectations; the trigger, its run's command and public parameters, and each missed
   expectation; the new plan, its reasoning and expectations; how the new plan's measured runs
   came out; reviews and notes on any of these steps.
4. **Timeline.** Each plan in order with its runs beneath it. A measured run shows its command,
   public parameters, code reference, measures and outcome. A plan's exploratory commands are
   one closed `<details>` element whose summary is their count and how many failed. An unsettled
   run says so. An exploration plan is labelled as one. Reviews and notes sit under the step
   they are about.
5. **Facts.** The lines `facts` prints.

With `--code REPO`, consecutive measured runs whose code references differ show the output of
`git -C REPO diff A B`, in a closed `<details>`, cut at 400 lines with the number left out.
Without it, or when `REPO` lacks a commit, the page shows the two references.

Rules for the page:

- One file. Inline CSS only. No `<script>`, `<link>`, `<img>`, `@import` or `url(`.
- Every string that comes from a step passes through `html.escape`. Agents write steps.
- The same trail gives the same bytes: no generation time, no absolute paths.
- Readable at 1280 and 390 pixels wide with no horizontal page scroll; `<pre>` scrolls inside
  itself. Light and dark through `prefers-color-scheme`. An outcome is always a word, with
  colour as an addition.

### `facts`

Existing lines keep their exact wording. The changes:

- A plan's attempts are its measured and unsettled runs. Exploratory commands are not attempts.
- A plan with exploratory commands gets `step-N: 12 commands wrote no metrics`, followed by
  `, 2 failed` when some did.
- An exploration plan gets one line, `step-N: exploration, 6 commands`, with `, 1 failed` when
  some did, and no attempt lines.
- A plan with runs but no attempts gets `step-N: no measured run` in place of the attempts line.
- The repeat facts consider attempts only.
- **Eased threshold.** A plan that supersedes another and is triggered by a local observation
  gets `step-4: eases auc from >= 0.75 to >= 0.7 after step-3 missed it` when both plans hold an
  expectation on the same measure with the same comparison, the trigger's check of the old one
  did not hold, and the new threshold is easier: lower for `ge` and `gt`, higher for `le` and
  `lt`.

### `review DIR STEP --verdict confirms|disputes --text TEXT --by NAME` and `note DIR STEP --text TEXT --by NAME`

Each appends one step, by `human:NAME`, linked to `STEP` with `reviews` or `about`, both
`confirmed`. The summary is `Confirms step-N`, `Disputes step-N` or `Note on step-N`. `at` is
the current UTC time to the second, or the last step's `at` when that is later. The new step is
built in memory, the whole trail is checked with it, and the file is written only when the check
is clean. Otherwise nothing is written and the exit code is 1.

## Technical decisions and stack

- Python 3.12 or later, standard library only (`html`, `subprocess` for `git diff`).
- New code for `why` and the page lives in `view.py` at the repository root, which imports
  `trail`. `trail.py` imports `view` inside its command dispatch, so there is no import cycle.
- `facts`, `review` and `note` live in `trail.py`.
- The command line may move to `argparse`, provided every existing command keeps its arguments
  and output.

## Project structure and git workflow

Modules sit at the repository root and tests in `tests/`. Work on `spec/01-reviewer-view`, in
small commits with imperative subjects, and open one pull request to `main`.

## Target files

| File | Change |
| --- | --- |
| `view.py` | new: `changes(steps)`, `why(steps, step)`, `page(steps, code)` |
| `trail.py` | `facts`; dispatch for `why`, `view`, `review`, `note`; the usage lines in the docstring |
| `tests/test_view.py` | new |
| `tests/test_trail.py` | additions only |
| `docs/DESIGN.md` | the Facts section; a new section on `why` and the view |
| `.github/workflows/ci.yml` | build the churn view and upload it as an artifact named `view` |

## Testing and conformance

`pytest`, one test per rule, built from the committed examples. Tests that need a changed trail
copy the steps, change them and re-chain, as `tests/test_trail.py` does.

1. `why` on churn step 4 contains the strings listed above, in that order.
2. `why` with no step gives one line for churn and `No plan was replaced.` for the features
   example.
3. `why` on churn step 3 names step 4. An unknown step exits 1.
4. The churn page holds the same strings inside `change-step-4`, and none of the forbidden
   constructs.
5. A plan whose reasoning is `<script>alert(1)</script>` appears escaped.
6. Two renderings of one trail are byte-identical.
7. A run with an observation that has no `measures_source` is inside a `<details>` and not in
   the decision path.
8. All three examples render.
9. The existing `facts` assertions pass unchanged, and each new line has a test, including no
   eased-threshold line on the unchanged churn trail.
10. `review` and `note` on a copy of each example leave a trail that checks and still verifies
    at its earlier head. The tuning example's last step is dated after today, so `at` must not
    go backwards. An unknown step and a broken trail write nothing.
11. `--code`: a temporary repository with two commits, a trail citing them, and the changed line
    in the page.

## Sequence

1. `changes` and `why`, with tests 1 to 3.
2. `facts`, with test 9.
3. `review` and `note`, with test 10.
4. The page, with tests 4 to 8.
5. `--code`, with test 11. This is first on the roadmap's cut list: if it is not done, leave it
   out whole and say so.
6. The CI artifact and `docs/DESIGN.md`. Then the self-audit.

## Commands and code style

```sh
uv sync
uv run pytest tests/test_view.py tests/test_trail.py
uv run ruff check
uv run python trail.py why examples/churn-model-2026-11-11 step-4
uv run python trail.py view examples/churn-model-2026-11-11 --out /tmp/view.html
```

Match `trail.py`: line length 140, small functions, a comment where a rule needs its reason.

## Boundaries

- **Always**: run the tests and `ruff check` before each commit; escape step text; keep output
  deterministic; attach a screenshot of the churn page to the pull request when the environment
  can take one.
- **Ask first**: any change that alters an existing test's expected value, the schema, a check
  rule or the examples; any file outside the target files.
- **Never**: load anything from the network in the page; reword an agent's reasoning; edit
  `examples/` by hand.

## Rejection criteria

The work is rejected if any of these holds:

- an existing test was changed or removed, or `examples/` differs;
- the page contains unescaped step text, or a forbidden construct;
- `why` or the page states a cause that no link carries;
- the output depends on the time or the machine;
- a file outside the target files changed.

## Self-audit

After each step of the sequence, read the diff against the goals, non-goals and rejection
criteria, and run that step's tests. Before the pull request, run the five commands above and
list in its description each numbered test with its name.

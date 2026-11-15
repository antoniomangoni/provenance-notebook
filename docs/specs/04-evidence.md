# Spec 4: evidence

Branch `spec/04-evidence`. Depends on the live run: `live/madelon-2026-11-15-1` and `live/store`
must be on `main`. The submission depends on it.
Written to [the meta-spec](../meta-spec.md); [AGENTS.md](../../AGENTS.md) applies throughout.

The brief asks that a reviewer who was not present can answer "why did they change approach?"
from the log. The live trail exists and `trail.py why` answers that question for it. This spec
adds the two demonstrations [PLAN.md](../../PLAN.md#evidence) promises on that trail, and
fixes what the live trail showed in the view.

## The live trail

`live/madelon-2026-11-15-1`: Pi 0.84.1 with `berget/zai-org/GLM-5.3-Flash`, 26 steps, head
`sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933`.

| Step | What it is |
| --- | --- |
| step-4 | the first measured plan: `cv_auc >= 0.75` and `holdout_auc >= 0.71` |
| step-7, step-8 | the inherited analysis, and its observation: contradicted, `holdout_auc 0.5639` |
| step-9 to step-13 | an exploration plan; `diagnose.py` fails once, then runs |
| step-14 | the replacement plan: supersedes step-4, triggered by step-8 |
| step-17, step-18 | the rewritten analysis: as expected, `holdout_auc 0.7185` |
| step-19 | the last plan: the same expectations after a clean-up |
| step-22, step-23 | its one measured run: as expected, the same metrics file as step-17 |

Four of the ten runs are settled as inconclusive: they wrote no metrics under a plan that
expected some.

## Goals and non-goals

Goals:

1. **The tamper sequence**, on a copy of the live trail: one command prints each stage with
   the checker's own output, and a test asserts each stage.
2. **The reader check**: a model that has not seen the task answers the roadmap's four
   questions from two presentations of the live trail, and a grader scores the answers against
   a committed key. The script, the questions, the key, every answer and the table are committed.
3. **Three fixes** the live trail and the earlier evaluation showed (see [Fixes](#fixes)).

Non-goals:

- Any change to `capture/`, `scripts/`, `demo/`, `step.schema.json` or a rule in `trail.check`.
- Human readers, the video, the published view, `README.md`, `PLAN.md`, `docs/HACKATHON.md`.
  They belong to the submission slice.
- A model as the grader. Grading is mechanical.
- A run that cites the code from before its own command. No run in the live trail edits code
  and runs it in one command, and [capture's limits](../../capture/README.md#limits) state it.
- A run that never settles. The live trail has none.

## The tamper sequence

`tamper.py TRAIL --store STORE --cited HEAD --step STEP --measure NAME --value NUMBER` copies
the trail and the store to a temporary directory, never writes to `TRAIL` or `STORE`, and prints
five stages. Each stage runs `trail.check` or `trail.verify` and prints what it returns.

| Stage | What is done to the copy | Expected |
| --- | --- | --- |
| 1 | nothing | `check --store` passes; `verify HEAD` passes |
| 2 | the measure's value in `STEP` is rewritten: in `measures`, in the check that used it and in the summary | `check` fails at the next step's `prev` |
| 3 | every later `prev` is recomputed | `check` passes; `check --store` fails: the measures are not the ones in the stored file |
| 4 | a metrics file with the new value is put in the store, and `STEP` cites its digest | `check --store` passes |
| 5 | nothing more | `verify HEAD` fails: the trail never had that head |

The sequence shows what each defence catches. The chain catches a careless edit, the stored
metrics catch a rewritten number, and only a head cited outside the trail catches a complete
rewrite.

For the live trail: `--step step-8 --measure holdout_auc --value 0.7039`, a near miss in place
of a clear one. The outcome stays contradicted, so no other step has to change. When the new
value would change the step's outcome, `tamper.py` stops and says so.

The command exits 0 when every stage came out as expected and 1 otherwise. Its output for the
live trail is committed as `evidence/madelon-2026-11-15-1/tamper.txt`, with the temporary path
shown as `COPY`.

## The reader check

`readers.py` has three commands.

### `readers.py texts TRAIL --store STORE --log FILE --out DIR`

Writes the two presentations a reader is given:

- `view.txt`: the text of the page `trail.py view TRAIL --code CLONE` writes, where `CLONE` is
  a temporary clone of `TRAIL/code.bundle`. Tags are removed with `html.parser`; the text of
  closed `<details>` is kept; styles and scripts are dropped.
- `baseline.txt`: what a reviewer has today. Pi's session file under `TRAIL/session/`, every
  message in order with its role, text, thinking, tool calls with their arguments and tool
  results in full, followed by `FILE`, the agent's own `git log --stat`.

Nothing is removed from the transcript. It therefore holds capture's receipts and the
`propose_plan` calls, which a reviewer would not have without the notebook. The comparison is
conservative for that reason, and `evidence/README.md` says so.

`evidence/madelon-2026-11-15-1/git-log.txt` is already committed. It was taken from the live
run's workspace with `git log --stat --date=iso-strict --format='commit %h%nDate: %ad%n%n    %s%n'`,
which leaves the author out.

### `readers.py ask DIR --questions FILE --repeats N [pi options]`

For each presentation and each repeat, one call to Pi in print mode with no tools, no
extensions, no skills and no context files. The prompt is fixed in `readers.py`: the
presentation, then the four questions, then the form of the answer. The reader answers with one
JSON object:

| Question (as in `PLAN.md`) | Fields of the answer |
| --- | --- |
| 1. Why did the approach change, and at which step? | `new_plan`, `replaced_plan`, `trigger`, `measure`, `measured`, `threshold` |
| 2. Which code and parameters produced the final result? | `run`, `command`, `code`, `parameters` |
| 3. How many attempts did the final plan take before it held? | `plan`, `measured_runs` |
| 4. What was tried and abandoned? | `abandoned`, a list of plans or analyses, each with the result that ended it |

Every call appends one line to `DIR/answers.jsonl`: the presentation, the repeat, the model as
Pi names it, the raw reply and the parsed object, or `null` when the reply holds no JSON
object. A call that fails is recorded and counted, not repeated silently. The default is
5 repeats and `--provider berget --model zai-org/GLM-5.3-Flash --thinking off`.

A presentation longer than one argument allows (128 kB on Linux) cannot be passed on the
command line. Step 4 of the sequence finds how Pi 0.84.1 takes it, on standard input or as a
file, and records the choice here.

### `readers.py grade DIR --questions FILE --trail TRAIL`

Scores every line of `answers.jsonl` against the key and writes `DIR/table.md`.

- An item is right when the answer's field holds one of the key's accepted values. Step ids
  match exactly, numbers within 0.0005, a commit by its first 7 characters, a command after
  collapsing white space. An unparsed reply scores 0 on every item.
- A question's score is the share of its items that are right. The table gives, for each
  question and presentation, the mean over repeats and the range, then the number of
  characters of each presentation and the number of calls, failed calls and unparsed replies.
- For each key item the table also says whether its value occurs in each presentation's text.
  An item the baseline cannot contain, such as a snapshot commit, is marked so.

### The questions and the key

`evidence/questions.json` holds the four questions, word for word as in `PLAN.md`, the answer
fields, and the key for `madelon-2026-11-15-1`:

| Item | Accepted |
| --- | --- |
| 1 `new_plan` | step-14 |
| 1 `replaced_plan` | step-4 |
| 1 `trigger` | step-8 |
| 1 `measure`, `measured`, `threshold` | `holdout_auc`, 0.5639, 0.71 |
| 2 `run` and `code`, as a pair | step-22 with `190a214`, or step-17 with `13a6623`: both wrote the same metrics file |
| 2 `command` | `uv run python analysis.py`, with or without `2>/dev/null` |
| 2 `parameters` | none given: an empty list or object |
| 3 `plan`, `measured_runs` | step-19, 1; or step-14, 1 |
| 4 `abandoned` | includes step-4, or the inherited analysis with `holdout_auc` 0.5639 |

A test derives every step id, number and commit in the key from the step files, so the key
cannot drift from the trail. The key is committed before the first call to a model, in a commit
of its own. It does not change after that commit; a key that proves wrong is corrected in a
later commit that says what changed and why, and both tables are kept.

## Fixes

1. **The outcome is printed once.** Capture's observation summaries begin with the outcome
   ("contradicted: holdout_auc 0.5639, expected >= 0.71", "as expected"), and the view prints
   the outcome's label before the summary. Where a summary begins with its own outcome's
   label, the view prints the label once and the rest of the summary. The examples' summaries
   are unchanged.
2. **A missing option value is a usage error.** `trail.py review DIR STEP --text` and any
   other option given without its value print one line naming the option and exit 2, with no
   traceback.
3. **A generated page is not committed by accident.** `view` without `--out` writes
   `DIR/view.html`, inside `examples/` or `live/`. `.gitignore` lists `view.html`. The command
   does not change.

## Technical decisions and stack

- Python, standard library only. No new dependency.
- The reader is called through Pi, so the model changes with Pi's options and no key is read
  by this repository's code. `readers.py` holds one function that takes a prompt and returns
  the reply; the tests replace it.
- `tamper.py` and `readers.py` import `trail` and `view`. They are not imported by them.

## Project structure and git workflow

Two modules at the repository root, one test file, and `evidence/` for what they write.
Work on `spec/04-evidence`, in small commits with imperative subjects, one pull request to `main`.

## Target files

| File | Change |
| --- | --- |
| `tamper.py`, `readers.py` | new |
| `tests/test_evidence.py` | new |
| `evidence/questions.json`, `evidence/README.md` | new |
| `evidence/madelon-2026-11-15-1/` | `git-log.txt` exists; new: `tamper.txt`, `view.txt`, `baseline.txt`, `answers.jsonl`, `table.md` |
| `view.py` | fix 1 |
| `trail.py` | fix 2, in `option` and the command line only |
| `tests/test_view.py`, `tests/test_trail.py` | a test for fix 1 and a test for fix 2 |
| `.gitignore` | fix 3 |

`evidence/README.md` says what each file is, how to rebuild it, the limits of the comparison
and how many live attempts there were (one).

## Testing and conformance

`tests/test_evidence.py` needs no model and no network.

1. Each tamper stage on a copy of the live trail gives the result in the table above, and
   `live/` is byte for byte what it was.
2. `tamper.py` refuses a value that would change the step's outcome.
3. `view.txt` holds the text of a closed `<details>` and no tag; `baseline.txt` holds every
   tool call of the session file and the git log.
4. Every step id, number and commit in the key is in the step files of the live trail.
5. The grader gives 1.0 to an answer built from the key, 0 to an unparsed reply, and the
   stated share to an answer with one item wrong.
6. `ask`, with the model function replaced, writes one line per call and records a failed call.
7. A captured observation's outcome label appears once in its line of the page.
8. An option without its value exits 2 with one line and no traceback.

## Sequence

1. Fixes 1 to 3, each with its test.
2. `tamper.py`, its tests, and `evidence/madelon-2026-11-15-1/tamper.txt`.
3. `readers.py texts` and `grade`, their tests, `evidence/questions.json` with the key, and
   the two text files. The key is committed here, before any call to a model.
4. `readers.py ask`, its test, then the calls: `answers.jsonl` and `table.md`.
5. `evidence/README.md`. Then the self-audit.

## Commands and code style

```sh
uv run pytest tests/test_evidence.py
uv run python tamper.py live/madelon-2026-11-15-1 --store live/store \
  --cited sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933 \
  --step step-8 --measure holdout_auc --value 0.7039
uv run python readers.py texts live/madelon-2026-11-15-1 --store live/store \
  --log evidence/madelon-2026-11-15-1/git-log.txt --out evidence/madelon-2026-11-15-1
uv run python readers.py ask evidence/madelon-2026-11-15-1 --questions evidence/questions.json --repeats 5
uv run python readers.py grade evidence/madelon-2026-11-15-1 --questions evidence/questions.json --trail live/madelon-2026-11-15-1
uv run pytest && uv run ruff check
```

Python as in the rest of the repository, line length 140, small functions, comments that say
why a rule exists.

## Boundaries

- **Always**: run the tests and `ruff check` before each commit; keep every reply a model
  gave; report the table as measured, whichever presentation it favours.
- **Ask first**: a change to a question's wording or to the key after its commit; a model other
  than the default; more than 40 calls to a model; any file outside the target files.
- **Never**: write under `live/` or `examples/`; put a key or a token in a file or a message;
  grade by hand; drop or rerun a call because of its answer.

## Rejection criteria

The work is rejected if any of these holds:

- a file under `live/` or `examples/` changed;
- the key changed after the first call to a model without a commit that says so;
- `answers.jsonl` holds fewer lines than calls made, or the table leaves a call out;
- a tamper stage is asserted from a constant and not from what `trail.check` or
  `trail.verify` returned;
- the page of an example trail changed, other than by fix 1 where a summary repeats its outcome;
- a test needs a model, a key or the network;
- a file outside the target files changed.

## Self-audit

After each step of the sequence, read the diff against the goals, non-goals and rejection
criteria. Before the pull request, run the commands above from a clean clone, confirm that
`git status` shows nothing under `live/`, and read `table.md` beside `answers.jsonl` for three
calls chosen before looking at their scores.

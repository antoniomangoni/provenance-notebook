# Spec 3: the demo task

Branch `spec/03-demo-task`. Depends on no other spec. The live run depends on it.
Written to [the meta-spec](../meta-spec.md); [AGENTS.md](../../AGENTS.md) applies throughout.

The live run needs a research task in which a plan is honestly contradicted, so that the trail
holds a real change of approach. If that depended on the model making a mistake, a careful
model would leave nothing to show. So the task is a re-analysis: the agent inherits a script
with a known pitfall, reproduces its headline number, and tests it on data the script never
saw. The contradiction belongs to the inherited analysis, and a test can show it with no model.

## Goals and non-goals

Goals:

1. `demo/`, a demo directory the launcher can run: `task.json`, `prompt.md` and `workspace/`.
2. An inherited analysis whose cross-validated AUC does not hold on held-out data, by a clear
   distance, on every seed tried.
3. A corrected analysis, kept outside the workspace, whose two numbers agree.
4. A record of where the data came from and of every candidate that was measured.

Non-goals:

- Running Pi or a model. Anything under `capture/`, `scripts/` or `live/`, and `trail.py`.
- A new method. The pitfall is a documented one and the analysis is ordinary.
- Tuning the corrected analysis for a high score. Its honest number may be modest.

## The task

The pitfall, in order of preference:

1. **Features selected before cross-validation.** The inherited script picks the `k` features
   most associated with the outcome using every pilot sample, then cross-validates a model on
   those features. The folds have already seen the labels, so the estimate is too high
   (Ambroise and McLachlan, PNAS 2002). It bites when features far outnumber samples.
2. **Records split where subjects should be.** The inherited script cross-validates over
   recordings when each subject has several, so a subject sits on both sides of a fold. The
   held-out data are whole subjects.

The data are public, and are divided once into a small pilot sample, which the inherited study
used, and the rest, held out. Candidates, each to be measured and its licence confirmed at the
source: Arcene and Madelon from the UCI repository and Bioresponse from OpenML for the first
pitfall; the UCI Parkinsons voice recordings for the second. Take the first candidate that meets
the acceptance numbers and whose licence allows the files to be committed.

`workspace/analysis.py [--seed N] [--k K] [--folds F]` reads `data/pilot.csv` and
`data/heldout.csv` and writes `out/metrics.json` with three numbers:

| Measure | Meaning |
| --- | --- |
| `cv_auc` | the inherited estimate: cross-validated AUC on the pilot sample |
| `holdout_auc` | AUC on the held-out data of the same pipeline fitted on the whole pilot sample |
| `gap` | `cv_auc` less `holdout_auc` |

`--seed` sets the folds and the model's randomness. It does not move the division into pilot
and held-out data, which is fixed in the files.

### Acceptance numbers

`H` is the inherited `cv_auc` at seed 0, to two decimals. The floor is `H - 0.05`, written into
the task's question before any agent runs it. For each seed from 0 to 4:

- inherited: `cv_auc >= H - 0.03`, `gap >= 0.15`, and `holdout_auc <= H - 0.10`;
- corrected: `gap` between `-0.07` and `0.07`;
- each run takes under 60 seconds once the environment exists. Aim for under 20.

The pilot size, `k` and the model may be chosen to meet these. When the best candidate misses
them narrowly, stop, record the measured table and ask.

### The files

- `demo/task.json` holds `summary`, `question`, `project`, `declared_measures` (`cv_auc`,
  `holdout_auc`, `gap`), `public_parameters` (`seed`, `k`, `folds`), `inputs` (the two data
  files) and `by` (`human:antonio`). The question states `H`, the floor and the number of
  held-out samples.
- `demo/prompt.md` is what the agent is told, in this form:

  > You have inherited an analysis. `analysis.py` predicts OUTCOME from FEATURES in
  > `data/pilot.csv` and reports a cross-validated AUC of H. Since then `data/heldout.csv` has
  > arrived: N samples the analysis never saw. Establish whether the reported result holds on
  > them, taking a held-out AUC of at least FLOOR as holding. If it does not hold, find out
  > why, correct the analysis, and report an estimate you would stand behind. Run the analysis
  > with `uv run python analysis.py`; it writes its numbers to `out/metrics.json`. Finish with
  > a short summary of what you found.

- `demo/workspace/` is a `uv` project with its own `pyproject.toml` and `uv.lock`, a
  `.gitignore` listing `out/` and `.venv/`, `analysis.py`, the two data files, and a `README.md`
  that describes the analysis as its author would.
- Nothing in `workspace/` or `prompt.md` names the pitfall. The words "leak", "pitfall",
  "bias" and "optimistic" do not appear there.
- `demo/corrected.py` is the corrected analysis, with the same flags and measures.
- `demo/make_data.py` rebuilds the two data files from the source and fails when their digests
  differ from the recorded ones.
- `demo/README.md` records the source, licence and citation; how the pilot sample was drawn;
  the digests; the measured table for seeds 0 to 4, inherited and corrected; every candidate
  that was measured and why it was or was not taken; and the pitfall with its reference. The
  example is constructed to show a known pitfall, and this file says so.

## Technical decisions and stack

- The workspace is Python 3.12 or later with `numpy` and `scikit-learn`, and `pandas` only if
  needed, pinned by its own `uv.lock`. The root `pyproject.toml` does not change.
- The data files are CSV, at most 10 MB together, committed.
- `analysis.py` is one file an agent can read in a minute: load, select, cross-validate, score,
  write.

## Project structure and git workflow

Everything sits under `demo/`, with one test file in `tests/`. Work on `spec/03-demo-task`, in
small commits with imperative subjects, and open one pull request to `main`.

## Target files

| File | Change |
| --- | --- |
| `demo/task.json`, `demo/prompt.md`, `demo/README.md` | new |
| `demo/make_data.py`, `demo/corrected.py` | new |
| `demo/workspace/` | new: `pyproject.toml`, `uv.lock`, `.gitignore`, `README.md`, `analysis.py`, `data/pilot.csv`, `data/heldout.csv` |
| `tests/test_demo.py` | new |

## Testing and conformance

`tests/test_demo.py` runs the analyses with `uv run --directory demo/workspace`, after one
`uv sync` there, and skips without `uv`.

1. `task.json` has exactly the fields of the task file, its measures and parameters fit the
   schema's patterns, and each input exists.
2. The data files have the digests `demo/README.md` records.
3. The inherited analysis at seed 0 meets its acceptance numbers, with the floor read from the
   test's own constant and matched against the question's text.
4. The corrected analysis at seed 0 meets its acceptance number.
5. Each run takes under 60 seconds.
6. The forbidden words are absent from `workspace/` and `prompt.md`.
7. With `DEMO_FULL=1`, tests 3 and 4 run for seeds 0 to 4.

## Sequence

1. Measure the candidates in a scratch directory. For each, record the licence and the table.
2. Choose one. Write `make_data.py` and the two data files.
3. Write `workspace/` with the inherited `analysis.py`, and `corrected.py`.
4. Write `task.json`, `prompt.md` and the tests.
5. Write `demo/README.md`. Then the self-audit.

## Commands and code style

```sh
uv sync
uv run --directory demo/workspace python analysis.py --seed 0
uv run pytest tests/test_demo.py
DEMO_FULL=1 uv run pytest tests/test_demo.py
uv run ruff check
```

Python as in the rest of the repository, line length 140. `analysis.py` is written as a
researcher's script: plain, short, with the comments its author would have left.

## Boundaries

- **Always**: run the tests and `ruff check` before each commit; record every candidate that
  was measured, including the rejected ones; put the full table from `DEMO_FULL=1` in the pull
  request.
- **Ask first**: data whose licence does not clearly allow redistribution; acceptance numbers
  that cannot be met; a dependency beyond `numpy`, `scikit-learn` and `pandas`; any file outside
  the target files.
- **Never**: plant a defect that is not the documented pitfall; change labels or values in the
  data; name the pitfall where the agent under test can read it; choose a seed because it gives
  the result wanted.

## Rejection criteria

The work is rejected if any of these holds:

- the inherited analysis meets the floor on any seed from 0 to 4;
- the contradiction comes from anything other than the documented pitfall;
- the data's source, licence or digests are missing, or `make_data.py` does not reproduce the
  files;
- the workspace or the prompt tells the agent what is wrong;
- a run needs the network or more than a minute;
- a file outside the target files changed.

## Self-audit

After each step of the sequence, read the diff against the goals, non-goals and rejection
criteria. Before the pull request, run the commands above, read `workspace/` as the agent under
test will, with nothing else in view, and confirm that the task can be done from it.

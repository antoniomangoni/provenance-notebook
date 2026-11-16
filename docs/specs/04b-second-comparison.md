# Spec 4b: the reader check's second comparison

Branch `spec/04-evidence-plain`. Depends on [spec 4](04-evidence.md), merged.

**Added after the first result was seen.** The first comparison (`evidence/madelon-2026-11-15-1/table.md`)
found the view no better than the transcript. This comparison was designed after reading that
table. Everything it grades is committed before its first call to a model, and the first table,
its key and its 20 answers stay as they are.

## Why a second comparison

The first comparison cannot show what [PLAN.md](../../PLAN.md#evidence) asks:

1. **Its baseline holds the notebook's own words.** It has 4 `propose_plan` calls, 10 receipts
   (`[notebook] run step-N, observation step-M: …`), and 44 step ids in the agent's thinking
   that the agent learned from those receipts. It is the notebook's record read from a
   transcript, not what a reviewer has without the notebook.
2. **Half its key can only be answered with the notebook.** Step ids and snapshot commits exist
   only because capture made them, so a baseline without the notebook loses those items
   whatever a reader understands.
3. **No question asks about the forking-paths fact of this trail.** Before step 14 designed the
   analysis that cleared the floor, `diagnose.py` (run step 12) measured feature AUCs on
   `data/heldout.csv`.

## Goals

1. **A third presentation, `plain.txt`:** what Pi alone records.
2. **A fifth question,** about the held-out data, asked of all three presentations.
3. **Scores on the items all three presentations can answer,** next to the full scores.
4. **A third reader from another family:** `mistralai/Mistral-Small-3.2-24B-Instruct-2506`.

Non-goals: any change to `questions.json`, `answers.jsonl`'s first 20 lines, `table.md`,
`live/`, `examples/`, `trail.py`, `view.py` or `capture/`.

## The plain presentation

`readers.py texts` also writes `plain.txt`, from the same session file and git log as
`baseline.txt`:

- each `propose_plan` tool call is removed, with its tool result (matched by `toolCallId`);
- every line beginning `[notebook]` is removed from tool results and their details;
- every remaining step id (`step-N`) in text, thinking, arguments or details becomes
  `(step id removed)`.

Nothing else changes; thinking is kept.

The two transcripts bracket what a reviewer would have. `baseline.txt` says too much: it holds
the notebook's record. `plain.txt` may say too little: an agent working without the notebook
might have written its plans' reasoning into its text, where the reader could see it.

## The fifth question

`evidence/heldout.json`, the same structure as `questions.json`, one question:

> 5. Before the analysis that gave the final result was designed, did the agent measure anything
>    on the held-out samples other than the inherited analysis's own score? If so, with which
>    command, and at which step?

| Field | Kind | Accepted | Neutral |
| --- | --- | --- | --- |
| `measured_heldout` | `bool`, new | `true` | yes |
| `command` | `command` | `uv run python diagnose.py` | yes |
| `step` | `step` | step-12, the run; or step-13, its observation | no |

A test derives these from the step files:

- step 12 runs `uv run python diagnose.py` under exploration plan step 9;
- it comes after step 8, the inherited analysis's score, and before step 14, the plan that
  designed the final analysis;
- the code it ran reads `data/heldout.csv`.

The question leads: it names the held-out data. A reader who answers `true` without having read
the record is not caught by `measured_heldout`; it is caught by `command`.

## The neutral items

`evidence/comparison-2.json` names the items a reader can answer without step ids or snapshot
commits. An `accepted` given in this file replaces the key's for this comparison only.

| Question | Items | Accepted |
| --- | --- | --- |
| 1 | `measure`, `measured`, `threshold` | as in the key |
| 2 | `command`, `parameters` | as in the key |
| 3 | `measured_runs` | as in the key |
| 4 | `abandoned` | an entry with result 0.5639 only; the step-4 alternative is a step id |
| 5 | `measured_heldout`, `command` | as above |

## Calls

The order is fixed here and the calls are made in it. Every call is appended to its file, and
none is dropped or rerun because of its answer.

| # | Questions | Presentations | Models | Calls | To |
| --- | --- | --- | --- | --- | --- |
| 1 | `questions.json` | plain | GLM-5.3-Flash, Gemma 4 31B, Mistral Small, in that order | 15 | `answers.jsonl`, after its 20 lines |
| 2 | `questions.json` | view, baseline | Mistral Small | 10 | `answers.jsonl` |
| 3 | `heldout.json` | view, baseline, plain | GLM-5.3-Flash, Gemma 4 31B, Mistral Small | 45 | `answers-heldout.jsonl` |

That is 70 calls: 20 to GLM-5.3-Flash, 20 to Gemma 4 31B and 30 to Mistral Small. Each model
stays under spec 4's limit of 40.

Mistral Small is given a Pi model entry in a settings directory outside the repository. One
call with a one-line prompt, carrying no presentation, checks that the entry works; it is not
recorded in an answer file, and the README says it was made.

## Code

`readers.py`:

- `plain_text`. `PRESENTATIONS` becomes `view`, `baseline`, `plain`.
- `ask --presentations NAMES` (comma-separated, default all) and `--answers FILE` (default
  `answers.jsonl`).
- Kind `bool`: `true` or `false` as JSON booleans only.
- `grade --compare FILE --out FILE`. It reads `answers.jsonl` and, when the comparison names
  it, `answers-heldout.jsonl`, and writes the second table. Without `--compare`, `grade` writes
  `table.md` byte for byte as before, with two columns, the view and the baseline.

`table-2.md` gives:

- neutral scores by model, question and presentation, in three columns;
- full scores for every question and presentation;
- the calls table;
- for each neutral item, whether it can be read off each text, and how many calls got it right.

## Target files

`docs/specs/04b-second-comparison.md` (this file), `readers.py`, `tests/test_evidence.py`,
`evidence/heldout.json`, `evidence/comparison-2.json`, `evidence/README.md`, and in
`evidence/madelon-2026-11-15-1/`: `plain.txt`, `answers.jsonl` (appended), `answers-heldout.jsonl`,
`table-2.md`.

## Testing

1. `plain.txt` holds no `[notebook]`, no `propose_plan` and no `step-N`. It keeps every bash,
   read, write and edit call's arguments, with step ids removed, and ends with the git log.
2. The key of question 5 and the neutral list are derived from the step files.
3. Kind `bool` accepts `true` and rejects `"yes"`, `1` and `null`.
4. `table.md` is what `grade` writes without `--compare`, as committed.
5. `table-2.md` is what `grade --compare` writes from the committed answer files.
6. `ask --presentations plain` asks the plain presentation only.

## Boundaries

- **Always:** report the table as measured, whichever presentation it favours. Label this
  comparison "added after the first result" wherever it is reported.
- **Ask first:** a change to `heldout.json` or `comparison-2.json` after the first call; more
  than 40 calls to a model; a model other than the three named.
- **Never:** rerun or drop a call; write under `live/` or `examples/`; change the first
  comparison's files.

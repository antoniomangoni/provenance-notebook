# Evidence

What was measured on the live trail `live/madelon-2026-11-15-1`, and how to measure it again.
The spec is [docs/specs/04-evidence.md](../docs/specs/04-evidence.md).

**Live attempts.** There were two, both committed under `live/`, as every attempt is.

| Attempt | Model | Result |
| --- | --- | --- |
| `madelon-2026-11-15-1` | `zai-org/GLM-5.3-Flash` | 26 steps. Contradicted at step 8, plan replaced at step 14. **The evidence here uses this one** |
| `madelon-2026-11-15-2` | `google/gemma-4-31B-it` | 20 steps. Contradicted at step 7, but no plan is recorded as replacing another, so there is no change of approach to ask about |

## Files

| File | What it is | Written by |
| --- | --- | --- |
| `questions.json` | the roadmap's four questions, the fields of an answer and the key | hand, from the step files; a test derives every value again |
| `madelon-2026-11-15-1/tamper.txt` | the tamper sequence, five stages | `tamper.py` |
| `madelon-2026-11-15-1/view.txt` | the first presentation: the text of the reviewer's page | `readers.py texts` |
| `madelon-2026-11-15-1/baseline.txt` | the second presentation: Pi's transcript and the agent's git log | `readers.py texts` |
| `madelon-2026-11-15-1/git-log.txt` | the agent's own `git log --stat`, saved from the run's temporary workspace | hand, on 15 November |
| `madelon-2026-11-15-1/answers.jsonl` | every reply to questions 1 to 4: the first comparison's 20 lines, then the second's 25 | `readers.py ask` |
| `madelon-2026-11-15-1/table.md` | the first comparison's scores | `readers.py grade` |
| `heldout.json`, `comparison-2.json` | the second comparison's fifth question and its list of neutral items | hand, from the step files; tests derive them again |
| `madelon-2026-11-15-1/plain.txt` | the third presentation: the transcript without the notebook's words | `readers.py texts` |
| `madelon-2026-11-15-1/answers-heldout.jsonl` | every reply to the fifth question, 45 lines | `readers.py ask` |
| `madelon-2026-11-15-1/table-2.md` | the second comparison's scores | `readers.py grade --compare` |

## The tamper sequence

The held-out AUC of step 8 is changed from 0.5639 to 0.7039, a near miss in place of a clear
one, on a copy of the trail. Each line of [tamper.txt](madelon-2026-11-15-1/tamper.txt) is what
`trail.check` or `trail.verify` returned.

| Stage | What the forger does | What catches it |
| --- | --- | --- |
| 2 | rewrites the number in the step | the chain: step 9's `prev` no longer matches |
| 3 | recomputes every later `prev` | the stored metrics file: `check --store` reads 0.5639 there |
| 4 | puts a forged metrics file in the store and cites it | nothing in the trail or the store |
| 5 | | the head cited before the change: `verify` fails |

Limits:

- A complete rewrite is caught only by a head that was cited somewhere the forger cannot
  reach. A trail whose head was never cited has no defence against stage 4.
- The forged file keeps the other two measures, so its `gap` is no longer `cv_auc` less
  `holdout_auc`. The checker does not know that relation and does not notice.
- `tamper.py` refuses a value that changes the step's outcome. That forgery would also need
  the plan that answered the outcome rewritten, and is not shown.

## The reader check

A model that has not seen the task is given one presentation and the four questions, and
answers with one JSON object. Two models, five calls for each presentation, 20 calls, none
failed. Scores are in [table.md](madelon-2026-11-15-1/table.md). In short:

| | From the view (20,411 characters) | From the baseline (221,290 characters) |
| --- | --- | --- |
| GLM-5.3-Flash | every item right in 5 of 5 calls | every item right except the commit of the final code |
| Gemma 4 31B | every item right except the number of measured runs of the final plan, where it answered 2 for 1 in 5 of 5 calls | every item right except the commit of the final code |

**The check does not show that the view is needed to answer these questions.** On this trail a
model answers them from the transcript as well as from the view. The view's text is a tenth of
the length.

Limits of the comparison, which a reader of the table needs:

- **The baseline holds the notebook's own words.** Nothing is removed from the transcript, so
  it has every `propose_plan` call, with the plan it replaces and the observation that
  triggered it, and capture's receipts with the step ids. A reviewer without the notebook
  would have none of that. The baseline is therefore not "no notebook"; it is "the notebook's
  record read from the transcript".
- **The one item the baseline misses is partly the key's doing.** The key accepts capture's
  snapshot commits (`190a214` or `13a6623`), which exist only in the trail. All ten baseline
  answers gave `cb37651`, the agent's own commit, made two steps after the final run. Its
  `analysis.py` is byte for byte the one in snapshot `190a214`. A key that also accepted it
  would score the baseline 1.00 on question 2. The key was fixed before the first call and is
  left as it was.
- **Gemma's miss from the view is unexplained.** The page lists one measured run under the
  final plan and two exploratory commands folded away. Why the model answered 2 was not
  looked into.
- **The readers are models, and one is the trail's author.** GLM-5.3-Flash also ran the live
  task. Each call is a fresh session with no tools, but the two are not independent in the
  way two people are.
- **One trail, one task, five calls a cell.** Every cell has the same score in all five calls,
  so the ranges say nothing about a wider spread.
- **The fields of the answer and the key were written after the live run**, from the step
  files, and committed before any reader was asked. The four questions were fixed in `PLAN.md`
  before the live run.
- **Grading is by exact value.** A step id must be the id, a number must be within 0.0005, and
  an answer that is right in words but names no accepted value scores 0 on that item.

## Second comparison, added after the first result

The first comparison could not show what the roadmap asks. Its baseline holds the notebook's
own words, half its key needs step ids that only the notebook makes, and none of its questions
asks about the held-out data. This comparison was designed **after** reading the first table,
in [spec 4b](../docs/specs/04b-second-comparison.md). Its presentation, its fifth question and
its list of items were committed before its first call (`169991c`). The first table is unchanged.

What it adds:

- **`plain.txt`, what Pi alone records.** The transcript without the 6 `propose_plan` calls and
  their results, without capture's receipts, and with every step id replaced.
- **A fifth question.** "Before the analysis that gave the final result was designed, did the
  agent measure anything on the held-out samples other than the inherited analysis's own
  score?" The answer is yes: `uv run python diagnose.py`, step 12.
- **Scores on the 9 items any presentation can answer:** no step id and no snapshot commit.
- **A third reader from another family:** Mistral Small 3.2 24B.

That made 70 calls; 24 failed. The scores, in [table-2.md](madelon-2026-11-15-1/table-2.md),
count a failed call as 0. GLM's and Gemma's answers to questions 1 to 4 from the view and the
full transcript are the first comparison's calls, graded again on the neutral items; every other
call is new. Over the calls that answered, on the neutral items:

| Reader | View | Full transcript | Plain transcript |
| --- | --- | --- | --- |
| GLM-5.3-Flash | every item right, 10 calls of 10 | every item right, 10 of 10 | every item right in the 6 calls that answered; 4 failed |
| Gemma 4 31B | every item right except question 3, in all 10 calls | every item right, 10 of 10 | every item right except question 3, in all 10 calls |
| Mistral Small | every item right, 10 of 10 | all 10 calls failed | all 10 calls failed |

"Question 3" is the number of measured runs the final plan took: Gemma answered 2 for 1.

What it shows:

- **Without step ids, the transcript answers as well as the view.** Every reader that could read
  the plain transcript got the measure, the numbers, the command, the abandoned result and the
  held-out question as right as from the view.
- **The fifth question is not the view's.** Every answer from every presentation said the
  held-out samples were measured, and named `diagnose.py`. Neither the view nor the trail flags
  it; a reader finds it in the command and its output.
- **The view's measured advantage is its length.** Berget serves Mistral Small with a context of
  32,768 tokens. The transcripts are about 55,000 tokens, the view about a tenth of that. Mistral could
  answer only from the view, and from it answered every item right.
- **Step ids are the notebook's.** On the whole key, the plain transcript loses every item that
  asks for a step id. That shows the ids exist only in the trail, not that a reader understood less.

Why the calls failed:

- **Mistral, all 20 on the transcripts.** Pi exited 0 with no output, and `readers.py` recorded
  "exit code 0: no output". It has since been changed to read Pi's JSON events, so a later call
  records the provider's own message; the 70 calls here were made before that change. One more call, made afterwards with Pi's JSON output to find the
  cause, was refused with `context_length_exceeded`: "This model's maximum context length is
  32768 tokens. However, your input is estimated at 54729 tokens". That call was not graded and
  is not in an answer file.
- **GLM-5.3-Flash, 4 of 10 on the plain transcript.** The same silent failure. The cause was not
  found: GLM answered all 10 calls on the full transcript, which is longer, so the length is
  not it. No failed call was made again.

Limits of the second comparison:

- **It was designed after the first result.** It tests what the first could not; it was not
  planned before the live run.
- **The plain transcript is a removal, not a run.** It may say too little: an agent without the
  notebook might have written its plans' reasoning into its text. It also says too much: the
  agent's thinking still names `propose_plan` 10 times and receipts 16 times, because it was
  written under the notebook. A run without capture would settle this, and was not made.
- **The fifth question leads.** It names the held-out data, so `measured_heldout` is easy to get
  right by guessing. The `command` item is not.
- **Five calls a cell, one trail, readers that are models.** As in the first comparison. Every
  answered cell has the same score in all its calls.

## Measuring it again

```sh
uv run pytest tests/test_evidence.py      # no model, no network
uv run python tamper.py live/madelon-2026-11-15-1 --store live/store \
  --cited sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933 \
  --step step-8 --measure holdout_auc --value 0.7039
uv run python readers.py texts live/madelon-2026-11-15-1 --store live/store \
  --log evidence/madelon-2026-11-15-1/git-log.txt --out evidence/madelon-2026-11-15-1
uv run python readers.py grade evidence/madelon-2026-11-15-1 --questions evidence/questions.json \
  --trail live/madelon-2026-11-15-1
```

`tamper.py` prints `tamper.txt`, and `texts` and `grade` write their committed files again, byte
for byte. `readers.py ask` calls a model
and appends to `answers.jsonl`, so running it adds calls to the record; it needs
`capture/node_modules` installed and a Pi model file with the provider's key, which this
repository does not hold:

```sh
uv run python readers.py ask evidence/madelon-2026-11-15-1 --questions evidence/questions.json --repeats 5
uv run python readers.py ask evidence/madelon-2026-11-15-1 --questions evidence/questions.json --repeats 5 \
  --model google/gemma-4-31B-it
```

The second comparison's calls are listed, in their order, in spec 4b. Its table:

```sh
uv run python readers.py grade evidence/madelon-2026-11-15-1 --questions evidence/questions.json \
  --trail live/madelon-2026-11-15-1 --compare evidence/comparison-2.json --out evidence/madelon-2026-11-15-1/table-2.md
```

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
| `madelon-2026-11-15-1/answers.jsonl` | every reply of every call, 20 lines | `readers.py ask` |
| `madelon-2026-11-15-1/table.md` | the scores | `readers.py grade` |

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

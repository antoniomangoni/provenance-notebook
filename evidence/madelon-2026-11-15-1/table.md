# Reader check: madelon-2026-11-15-1

Written by `readers.py grade` from `answers.jsonl` and `evidence/questions.json`. The trail's head is `sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933`.

A score is the share of a question's key items that an answer got right. Each cell is the mean over
the calls and, in brackets, the lowest and the highest. A failed call or a reply without a JSON
object scores 0 on every item.

## Scores

| Model | Question | From the view | From the baseline |
| --- | --- | --- | --- |
| `berget/zai-org/GLM-5.3-Flash` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.67 (0.67 to 0.67) |
| `berget/zai-org/GLM-5.3-Flash` | 3. How many attempts did the final plan take before it held? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.67 (0.67 to 0.67) |
| `berget/google/gemma-4-31B-it` | 3. How many attempts did the final plan take before it held? | 0.50 (0.50 to 0.50) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |

## Calls

| Model | Presentation | Characters | Calls | Failed | Without a JSON object |
| --- | --- | --- | --- | --- | --- |
| `berget/zai-org/GLM-5.3-Flash` | view | 20411 | 5 | 0 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | baseline | 221290 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | view | 20411 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | baseline | 221290 | 5 | 0 | 0 |

## Each item of the key

How many calls got the item right, and whether an accepted value can be read off each presentation's
text at all. "No" marks an item that presentation cannot answer; "counted" marks a value a reader
has to work out, which no text needs to state.

| Item | Accepted | In the view | In the baseline | `berget/zai-org/GLM-5.3-Flash`: view, baseline | `berget/google/gemma-4-31B-it`: view, baseline |
| --- | --- | --- | --- | --- | --- |
| 1 `new_plan` | `step-14` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 1 `replaced_plan` | `step-4` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 1 `trigger` | `step-8` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 1 `measure` | `holdout_auc` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 1 `measured` | `0.5639` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 1 `threshold` | `0.71` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 2 `run`, `code` | `step-22` with `190a214`; or `step-17` with `13a6623` | yes | no | 5 of 5, 0 of 5 | 5 of 5, 0 of 5 |
| 2 `command` | `uv run python analysis.py`; or `uv run python analysis.py 2>/dev/null` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 2 `parameters` | none given | counted | counted | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 3 `plan` | `step-19`; or `step-14` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |
| 3 `measured_runs` | `1` | counted | counted | 5 of 5, 5 of 5 | 0 of 5, 5 of 5 |
| 4 `abandoned` | an entry with step `step-4`; or an entry with result `0.5639` | yes | yes | 5 of 5, 5 of 5 | 5 of 5, 5 of 5 |

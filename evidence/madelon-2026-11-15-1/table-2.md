# Reader check, second comparison: madelon-2026-11-15-1

**Added after the first result was seen** ([spec 4b](../../docs/specs/04b-second-comparison.md)). The first
comparison's table, `table.md`, is unchanged. Written by `readers.py grade --compare` from `answers.jsonl`, `answers-heldout.jsonl`. The trail's head is `sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933`.

Presentations: `view.txt`, the text of the reviewer's page; `baseline.txt`, Pi's whole transcript, which
holds the notebook's plan calls and receipts; `plain.txt`, the same transcript without them and with
step ids removed, and so without the notebook. A score is the share of a question's items an answer got
right: the mean over the calls and, in brackets, the lowest and the highest.

## Scores on the items every presentation can answer

Only the items listed in `comparison-2.json`: none needs a step id or a snapshot commit.

| Model | Question | From the view | From the baseline | From the plain |
| --- | --- | --- | --- | --- |
| `berget/zai-org/GLM-5.3-Flash` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.40 (0.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.40 (0.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 3. How many attempts did the final plan take before it held? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.40 (0.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.40 (0.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.80 (0.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 3. How many attempts did the final plan take before it held? | 0.00 (0.00 to 0.00) | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) |
| `berget/google/gemma-4-31B-it` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 3. How many attempts did the final plan take before it held? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |

## Scores on the whole key

The plain transcript has no step ids, so it cannot score on the items that ask for one.

| Model | Question | From the view | From the baseline | From the plain |
| --- | --- | --- | --- | --- |
| `berget/zai-org/GLM-5.3-Flash` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.20 (0.00 to 0.50) |
| `berget/zai-org/GLM-5.3-Flash` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.67 (0.67 to 0.67) | 0.27 (0.00 to 0.67) |
| `berget/zai-org/GLM-5.3-Flash` | 3. How many attempts did the final plan take before it held? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.20 (0.00 to 0.50) |
| `berget/zai-org/GLM-5.3-Flash` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.40 (0.00 to 1.00) |
| `berget/zai-org/GLM-5.3-Flash` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.53 (0.00 to 0.67) |
| `berget/google/gemma-4-31B-it` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 0.67 (0.67 to 0.67) |
| `berget/google/gemma-4-31B-it` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.67 (0.67 to 0.67) | 0.67 (0.67 to 0.67) |
| `berget/google/gemma-4-31B-it` | 3. How many attempts did the final plan take before it held? | 0.50 (0.50 to 0.50) | 1.00 (1.00 to 1.00) | 0.50 (0.50 to 0.50) |
| `berget/google/gemma-4-31B-it` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/google/gemma-4-31B-it` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) | 1.00 (1.00 to 1.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 1. Why did the approach change, and at which step? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 2. Which code and parameters produced the final result? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 3. How many attempts did the final plan take before it held? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 4. What was tried and abandoned? | 1.00 (1.00 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 5. Before the analysis that gave the final result was designed, did the agent measure anything on the held-out samples other than the inherited analysis's own score? If so, with which command, and at which step? | 0.80 (0.67 to 1.00) | 0.00 (0.00 to 0.00) | 0.00 (0.00 to 0.00) |

## Calls

| Model | Questions | Presentation | Characters | Calls | Failed | Without a JSON object |
| --- | --- | --- | --- | --- | --- | --- |
| `berget/zai-org/GLM-5.3-Flash` | `questions.json` | view | 20411 | 5 | 0 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | `questions.json` | baseline | 221290 | 5 | 0 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | `questions.json` | plain | 214907 | 5 | 3 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | `heldout.json` | view | 20411 | 5 | 0 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | `heldout.json` | baseline | 221290 | 5 | 0 | 0 |
| `berget/zai-org/GLM-5.3-Flash` | `heldout.json` | plain | 214907 | 5 | 1 | 0 |
| `berget/google/gemma-4-31B-it` | `questions.json` | view | 20411 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | `questions.json` | baseline | 221290 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | `questions.json` | plain | 214907 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | `heldout.json` | view | 20411 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | `heldout.json` | baseline | 221290 | 5 | 0 | 0 |
| `berget/google/gemma-4-31B-it` | `heldout.json` | plain | 214907 | 5 | 0 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `questions.json` | view | 20411 | 5 | 0 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `questions.json` | baseline | 221290 | 5 | 5 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `questions.json` | plain | 214907 | 5 | 5 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `heldout.json` | view | 20411 | 5 | 0 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `heldout.json` | baseline | 221290 | 5 | 5 | 0 |
| `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `heldout.json` | plain | 214907 | 5 | 5 | 0 |

## Each item every presentation can answer

Whether an accepted value can be read off each text ("counted": a reader works it out), and how many
calls got the item right, in the order view, baseline, plain.

| Item | Accepted | In the view | In the baseline | In the plain | `berget/zai-org/GLM-5.3-Flash` | `berget/google/gemma-4-31B-it` | `berget/mistralai/Mistral-Small-3.2-24B-Instruct-2506` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 `measure` | `holdout_auc` | yes | yes | yes | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 1 `measured` | `0.5639` | yes | yes | yes | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 1 `threshold` | `0.71` | yes | yes | yes | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 2 `command` | `uv run python analysis.py`; or `uv run python analysis.py 2>/dev/null` | yes | yes | yes | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 2 `parameters` | none given | counted | counted | counted | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 3 `measured_runs` | `1` | counted | counted | counted | 5 of 5, 5 of 5, 2 of 5 | 0 of 5, 5 of 5, 0 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 4 `abandoned` | an entry with result `0.5639` | yes | yes | yes | 5 of 5, 5 of 5, 2 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 5 `measured_heldout` | `true` | counted | counted | counted | 5 of 5, 5 of 5, 4 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |
| 5 `command` | `uv run python diagnose.py` | yes | yes | yes | 5 of 5, 5 of 5, 4 of 5 | 5 of 5, 5 of 5, 5 of 5 | 5 of 5, 0 of 5, 0 of 5 |

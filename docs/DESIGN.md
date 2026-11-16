# Provenance trail: step schema v2

Context: this is a candidate entry for Challenge 02 (provenance-preserving lab
notebook) of the AI for Meta-Science Hackathon — see [HACKATHON.md](HACKATHON.md).

A trail is one defined task: `steps/step-N.json`, one file per step, each written once.
[step.schema.json](../step.schema.json) checks one file; `trail.py check` checks what spans files.
`trail.py examples DIR` writes three, with the metrics files they cite in `DIR/store`: churn's eight
steps, whose step 4 is a change of approach; retention's five, which build on churn's result; and
tuning's thirteen, which re-run one plan until it holds ([Facts](#facts)). `check --store DIR` reads
each observation's metrics file again, and `trail.py facts DIR` lists what a checked trail shows.
`trail.py why` and `trail.py view` are what a reviewer reads ([Why, and the reviewer's view](#why-and-the-reviewers-view)).
`trail.py graph DIR` exports a checked trail as
`graph/nodes.parquet` and `graph/edges.parquet` ([Graph](GRAPH.md#graph)), and `trail.py merge OUT DIR...`
exports several as one graph ([Many probes](GRAPH.md#many-probes)); `--csv` writes text tables instead.
`scripts/cross.py` queries the merged examples with DuckDB.

## Kinds

| Kind | Written by | Carries | Links |
| --- | --- | --- | --- |
| task (step 0 only) | human, runner | question, project, agent identity, the measures the runner can produce, public parameter names | builds_on other probes |
| plan | agent, human | reasoning, at least one expectation (measure, comparison, threshold) | supersedes a plan + triggered_by an observation (this probe's or another's), both or neither |
| run | runner, before it executes | command (shown + digest), code commit, dirty diff digest, environment digest, parameters, inputs | implements exactly one plan |
| observation | runner, after the run ends | exit code, outputs, duration, measures and the metrics file they were read from, checks against the plan's expectations, outcome, error class, and, when the command was traced, the workspace files it opened for reading (`reads`) | observes one run, at most once; tests the plan that run implements |
| review | human | confirms or disputes, text | reviews a step |
| note | anyone | text | about a step |

"Why did they change approach at step 4?" reads off step 4 and its links: its reasoning, the observation it
was triggered by (step 3: AUC 0.58 against a 0.75 floor, positive rate 0.07), the plan it supersedes, and the
review that confirmed it.

## Rules

1. **Append only.** Steps are numbered without gaps; each `prev` is the SHA-256 of the previous step's
   canonical JSON (sorted keys, no whitespace, UTF-8), so changing any step breaks every later one.
   Corrections are new steps that supersede, and links point only backwards. Time is the capture clock,
   and `at` never goes backwards.
2. **Who said it.** The agent writes plans and notes; the runner writes runs and observations from what it
   measured; only people review. The agent's links are `suggested`; the runner's and people's are `confirmed`.
   Outcomes are not claims: the checker recomputes each check from the measures and the outcome from
   the checks and exit code. A check whose measure is missing is refused; leaving it out makes the
   outcome inconclusive. Measures are not claims either: they are read from a metrics file the run
   wrote (by convention `out/metrics.json`, one object of measure names to numbers), named in
   `measures_source` and listed among the outputs at the same digest, and `check --store` reads that
   file again. A plan's expectations may name only the measures its task declares.
3. **No values by default.** Parameters, commands, inputs and outputs are kept as digests; a parameter
   value appears only when the task lists its name as public. A public parameter's digest is the
   `sha256` of its value, so anyone can check it; a non-public one is `hmac-sha256` under a secret drawn
   per trail and kept outside it, because a plain hash of a seed or a short key is reversed by guessing. `command.shown` and the text fields
   pass a redactor first, and `redactions` counts what it replaced; a redacted command's digest is
   keyed too, since a plain hash of it hides only the redacted part. Errors are a class plus a digest of
   stderr. Raw payloads, when kept, live in a content-addressed store outside the trail.
4. **Capture outside the build.** The trail is produced by hooks around the agent, which the agent
   cannot write to; plans enter only through a tool the agent calls, and its messages and thinking are
   never parsed. Anything reading the trail (Almanaque included) imports it with a preview.
5. **Intent, then settlement.** A run step is written before its command executes, and its observation
   after it ends, once. A run that crashed or was stopped keeps its run step and has no observation:
   it is unsettled, never dropped, because what failed is part of the trail.
6. **Versioned.** `version` and `$id` carry the schema version; a new optional field never needs a default.

## Facts

`trail.py facts DIR` reports what a checked trail shows without judging it, for a reviewer to ask about:

- each plan's attempts, how many distinct results they produced and each outcome. An attempt is a
  measured run, whose observation names a metrics file, or an unsettled run. A plan with runs but no
  attempt gets `no measured run`;
- a plan's exploratory commands, runs whose observation names no metrics file, counted apart as
  `12 commands wrote no metrics`, with how many failed;
- an exploration plan, one whose every expectation is only about the exit code, as one line with its
  number of commands and failures, and no attempts;
- a plan that first held only after earlier attempts contradicted it, which is how re-running until a
  result appears (the garden of forking paths) looks in a trail;
- an attempt that repeats an earlier one: the same command, code, environment, parameters and inputs;
- a different attempt that wrote the same outputs as an earlier one;
- an unsettled run;
- an eased threshold: a plan that replaces another after its own trigger missed one of the old plan's
  expectations, and expects less of the same measure with the same comparison, as
  `step-4: eases auc from >= 0.75 to >= 0.7 after step-3 missed it`.

None is an error, and none says why: a repeat can be a deliberate reproduction, and an eased threshold
can be the right call. Only steps carry reasons. The tuning example has each of the first kinds once:
five runs of one plan, holding first on the third, step 8 repeating step 6, step 10 stopped by the
budget before it settled, and a review that disputes reporting the one seed that held.

## Why, and the reviewer's view

`trail.py why DIR STEP` answers "why did they change approach at STEP?" from the links alone. A change of
approach is a plan that supersedes an earlier plan. Its answer names the replaced plan, the trigger with
each expectation it missed (`auc 0.58, expected >= 0.75 (auc-floor)`, or the exit code of a failed run),
the new plan and its reasoning, whole and unchanged, and each review or note on any of these. A trigger
in another probe is shown as its citation, without numbers. Without `STEP`, `why` prints one sentence
per change of approach; for a step that is not one, it says what kind of step it is and which change it
took part in.

`trail.py view DIR` writes `view.html` (or `--out FILE`): the task and head, the decision path with one
sentence per change of approach, a card for each change, a timeline of plans with their runs, and the
facts. Exploratory commands are folded into one closed section per plan. With `--code REPO`, consecutive
measured runs at different commits show `git diff` between them, cut at 400 lines; without the
repository, the two references.

Both use fixed templates and infer nothing: a cause appears only when a link carries it. The page is one
file with inline CSS and no script, every string from a step is escaped, and a trail always renders to the
same bytes. It is not written for a trail that fails `check`.

`trail.py review DIR STEP --verdict confirms|disputes --text TEXT --by NAME` and `trail.py note DIR STEP
--text TEXT --by NAME` append a person's step, linked to `STEP`. Its `at` is now, or the last step's when
that is later. The trail is checked with the new step before it is written, and nothing is written if it
fails.

## The head

A trail is cited at its head, the digest of its last step's canonical JSON, which `trail.py head`
prints. Every earlier step is fixed by the chain, so a head names one exact history. A trail
rewritten and re-chained keeps passing `trail.py check`, but `trail.py verify DIR HEAD` fails: it
never had that head. A trail that only grew still has it. [GRAPH.md](GRAPH.md#the-pinned-head)
covers citing a trail from a larger graph.

## Capture host, checked at Pi 0.84.1

What the capture extension can rely on, from a probe extension run against
`@earendil-works/pi-coding-agent@0.84.1` with a scripted provider (`pi -p --mode json -e probe.ts
--provider script`), so no model key was needed. The probe wrote v2 steps, and `trail.py check` passed on them.

| Assumption | At 0.84.1 | So the extension |
| --- | --- | --- |
| An extension loads from one file, and the demo runs unattended | `-e FILE` loads it; `-p --mode json` runs headless. `typebox` and `pi-ai` imports resolve through the loader, so no extra install is needed | runs as `pi -p -e capture.ts`; the session id and `provider/model` come from `session_start`'s `ctx` |
| Tests can run without a key | `registerProvider(name, {streamSimple})` replays fixed tool calls per turn | tests every rule below offline and deterministically; the live demo needs a key |
| `propose_plan` can refuse a plan | a thrown error reaches the model as an error result, with its message | refuses an undeclared measure when the plan is proposed; the message names the declared ones, never values |
| The run intent is written before the command | `tool_call` is awaited. In a parallel batch, every sibling's `tool_call` runs, one at a time, before any of them executes | writes runs in `tool_call` with no lock of its own; observations still go through one queue, since `tool_result` arrives in completion order |
| A plan exists before its runs | **No.** When `propose_plan` and `bash` share a turn, bash's `tool_call` runs before `propose_plan` executes, so the run cites a plan not yet written | declares `propose_plan` `executionMode: "sequential"`, which makes that batch run call by call; it blocks a `bash` run when there is no open plan |
| Blocking fails closed | `{block: true}` and a throwing handler both stop the call; the reason, or the thrown message, is what the model sees. Blocked calls get no `tool_result` | writes the budget stop's runner note in `tool_call` itself, and keeps values out of every reason |
| The budget can stop the agent | `{block: true, terminate: true}` ended the run after that turn | stops on a run or token ceiling with a runner note |
| Token usage per turn | `turn_end`'s `event.message.usage` (`input`, `output`, `totalTokens`) | counts the budget from `turn_end` |
| The observation has the exit code | **No.** `BashToolDetails` has no exit code; a non-zero exit is a thrown error whose text ends "Command exited with code N" | overrides `bash` with the stock definition, running it with an `exec` wrapper that keeps `exitCode` per call id. It never parses the text |
| The trail says when the agent saw only part of the output | Only on success: `details.truncation` gives `totalLines`/`outputLines` (3,000 lines showed the last 2,000). On a failing command the details are dropped | counts lines and bytes in the same `exec` wrapper's `onData`, so a failed run's cap is recorded as well |
| The ledger is not saved | a message appended in `context` reaches the provider for that request only. Each request held exactly one, and the session file has none | rebuilds the ledger every turn from steps |
| A crash leaves an unsettled run | `kill -9` while a command ran left step-2 with no observation; `facts` reports "never settled". The command itself kept running, orphaned | needs nothing more: the unsettled run is the honest record. An orphaned command can still write outputs no step names |
| The agent cannot write the trail | `write`/`edit` are blocked by path in `tool_call`. `bash` is free text, but `bwrap --dev-bind / / --ro-bind TRAIL TRAIL` makes the trail read-only to the command alone (unprivileged bubblewrap works here) | blocks `write`/`edit` on the resolved real path, so symlinks are covered, and runs every command under that `bwrap` in the `exec` wrapper. The extension writes the trail outside the sandbox |
| TypeScript hashes as `trail.py` does | Steps are written with `JSON.stringify` and canonicalised again by Python. Strings, non-ASCII, ` ` and ASCII key order round-trip, and so do `1.0`, `-0.0`, `1e16` and `1e21`. Non-zero numbers below 1e-4 do not: JS writes `0.00001`, Python re-canonicalises `1e-05` | formats numbers in `canonical()` as Python does: below 1e-4, exponent form with at least two digits (`x.toExponential()`, then `e-5` becomes `e-05`). This matched on 100,007 random doubles. Keys stay ASCII, as the schema's patterns already make them |

## Open questions

- Who wrote a step rests on the capture host: the chain proves order, not authorship. Whether the
  host should sign what it writes, or only be named as the trust root.
- Whether a step's `at` from a remote runner needs a signature as well as the hash chain.

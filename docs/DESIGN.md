# Provenance trail: step schema v2

Context: this is a candidate entry for Challenge 02 (provenance-preserving lab
notebook) of the AI for Meta-Science Hackathon — see [HACKATHON.md](HACKATHON.md).

A trail is one defined task: `steps/step-N.json`, one file per step, each written once.
[step.schema.json](../step.schema.json) checks one file; `trail.py check` checks what spans files.
`trail.py examples DIR` writes three, with the metrics files they cite in `DIR/store`: churn's eight
steps, whose step 4 is a change of approach; retention's five, which build on churn's result; and
tuning's thirteen, which re-run one plan until it holds ([Facts](#facts)). `check --store DIR` reads
each observation's metrics file again, and `trail.py facts DIR` lists what a checked trail shows.
`trail.py graph DIR` exports a checked trail as
`graph/nodes.parquet` and `graph/edges.parquet` ([Graph](#graph)), and `trail.py merge OUT DIR...`
exports several as one graph ([Many probes](#many-probes)); `--csv` writes text tables instead.
`scripts/cross.py` queries the merged examples with DuckDB.

## Kinds

| Kind | Written by | Carries | Links |
| --- | --- | --- | --- |
| task (step 0 only) | human, runner | question, project, agent identity, the measures the runner can produce, public parameter names | builds_on other probes |
| plan | agent, human | reasoning, at least one expectation (measure, comparison, threshold) | supersedes a plan + triggered_by an observation (this probe's or another's), both or neither |
| run | runner, before it executes | command (shown + digest), code commit, dirty diff digest, environment digest, parameters, inputs | implements exactly one plan |
| observation | runner, after the run ends | exit code, outputs, duration, measures and the metrics file they were read from, checks against the plan's expectations, outcome, error class | observes one run, at most once; tests the plan that run implements |
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

- each plan's runs, how many distinct results they produced and each outcome;
- a plan that first held only after earlier runs contradicted it, which is how re-running until a
  result appears (the garden of forking paths) looks in a trail;
- a run that repeats an earlier one: the same command, code, environment, parameters and inputs;
- a different run that wrote the same outputs as an earlier one;
- an unsettled run.

None is an error, and none says why: a repeat can be a deliberate reproduction. Only steps carry
reasons. The tuning example has each fact once: five runs of one plan, holding first on the third,
step 8 repeating step 6, step 10 stopped by the budget before it settled, and a review that disputes
reporting the one seed that held.

## Graph

A trail is a probe: a named graph whose nodes are its steps, held as one node of the larger graph it
lives in (Almanaque's organisation graph, or any other). The step files stay the source of truth;
the node and edge tables are a projection of a checked trail, and an unchecked one is not exported.

### References

Names use Almanaque's syntax, `[project/]kind:identity[@version][#fragment]`, so a probe's nodes
join the larger graph's by identity rather than by copying. The task names the probe's `project`,
and the graph qualifies every project-local reference with it; actors and URLs are the same node
in every project and stay unqualified.

| Node | Reference | Example |
| --- | --- | --- |
| the probe | `PROJECT/probe:TRAIL`, cited as `PROJECT/probe:TRAIL@HEAD` | `churn/probe:churn-model-2026-11-11@sha256:c812…` |
| a step | `PROJECT/probe:TRAIL#step-N`, cited as `…@HEAD#step-N` | `churn/probe:churn-model-2026-11-11#step-4` |
| an actor | the step's `by` | `agent:pi/glm-5.2`, `runner:notebook/0.1`, `human:antonio` |
| code | the run's `code.ref`, qualified | `churn/commit:notebook@3f9c2a1` |
| an input or output | its `ref`, qualified and unversioned; the digest the run saw is on the edge | `churn/file:data/telco.csv` |
| a record | the link target, qualified | `churn/item:task-12`, `churn/decision:dec-3` |

A file is named by its project and path, so runs in one project reading the same path share a
node and their edges show whether they saw the same content. Almanaque's closed kind list gains
`probe`, `file`, `agent`, `runner` and `human` for this.

### Tables

Parquet by default, the format Almanaque's G1 plans for its graph artifact, read with DuckDB
locally; `--csv` writes the same columns as text, with an absent value empty rather than null.
Parquet needs `pyarrow`, CSV nothing beyond the checker.

`nodes`: `id`, `kind` (`probe`, a step kind, or the cited reference's kind), `graph` (the probe,
for its own nodes), `tier` (int8), `version` (the probe's head digest), `at` (UTC timestamp),
`label` (the step summary), `outcome` (an observation's, as the checker recomputed it).
`edges`: `source`, `relation`, `target`, `status`, `digest`, `graph` (the probe that asserts it).
Every other column is a string; `id`, `kind` and all of `edges` but `digest` are never null.

| Relation | From → to | Status | Digest |
| --- | --- | --- | --- |
| `contains` | probe → each step | confirmed | |
| `follows` | step N → step N−1 | confirmed | `prev` |
| `written_by` | step → actor | confirmed | |
| the step's links | step → step, record or another probe | as written | the head another probe was cited at |
| `runs_code` | run → commit | confirmed | the dirty diff, if any |
| `used`, `generated` | run → input, output | confirmed | what the run read or wrote |

Parameters, measures, commands and environment stay on the steps and out of the graph: they are
properties, and non-public parameter digests are keyed, so a graph never carries anything joinable
to a hidden value.

### The boundary

Every edge the probe asserts starts at one of its own nodes: steps point backwards at earlier steps
and outwards at actors, code, data and records, never the other way. The larger graph points in at
the probe or at one step, with its own edges in its own graph (`decision:dec-3 motivated_by
probe:T@HEAD#step-4`), and never edits the probe, so the chain stays valid. A review done in the
larger graph is one of those edges, not a new step. Nesting stops at two levels: a probe may cite
another probe as a node, but never contains one.

### The pinned head

The larger graph cites a probe at its head, the digest of its last step's canonical JSON (the
probe node's `version`). Every earlier step is fixed by the chain, so `probe:T@HEAD#step-4` names
one exact step. A trail rewritten and re-chained keeps passing `trail.py check`, but its head no
longer matches the one cited, which is what makes the chain tamper-evident. A probe that grows
gets a new head; citations of the old one still resolve, because steps are only appended.

### Many probes

Probes share one graph by union: `trail.py merge` concatenates their tables, keeps each edge in
the graph of the probe that asserted it, and lets a probe's own node win over another probe's
citation of it. Nothing is reconciled; two probes that disagree both stay, each in its own graph.

- **Ids.** A probe is `PROJECT/probe:TRAIL`; a trail slug is unique only within its project, and
  merge refuses the same probe twice.
- **Citing another probe.** A link may target `[PROJECT/]probe:TRAIL@HEAD[#step-N]`, always pinned
  at a head: a task `builds_on` a probe, a plan is `triggered_by` another probe's observation, a
  note is `about` one. `trail.py check` checks the form; `merge` resolves it against the cited
  probe's chain. The head must be one the probe had after some step, the cited step must have
  existed by then, and it must be the kind the relation needs. A probe rewritten and re-chained
  after it was cited no longer has the cited head, and the merge says so.
- **Same data by content.** Files are qualified by project, so the same bytes at two paths, or in
  two repositories, are two nodes. Their `used` edges carry the same digest, and joining on it is
  how the graph finds them: retention's `inputs/telco.csv` and churn's `data/telco.csv` are one
  dataset. Keyed parameter digests never join across probes, because each trail has its own key.

### Tiers

Every node the probe owns is tier 3, an observed signal, whoever wrote it: an agent's plan, a
runner's measure, even a person's review inside the trail. Cited nodes keep their own tier, which the
probe does not assign. A conclusion reaches tier 1 only through the larger graph, when an accepted
decision cites the step; a `suggested` edge inside the probe stays suggested there and never
invalidates a conclusion until confirmed.

### PROV-O

For export the probe is a `prov:Bundle`, itself a `prov:Entity` of the graph that cites it.

| Probe | PROV-O |
| --- | --- |
| probe | `prov:Bundle` |
| plan | `prov:Plan` |
| run | `prov:Activity`; `prov:qualifiedAssociation` with the runner and `prov:hadPlan` the plan it implements |
| observation | `prov:Entity`, `prov:wasGeneratedBy` the run it observes |
| task, review, note | `prov:Entity`, `prov:wasAttributedTo` its author |
| `used`, `generated` | `prov:used`, `prov:wasGeneratedBy` |
| `supersedes` | `prov:wasRevisionOf` |
| `triggered_by` | `prov:wasInfluencedBy` |
| `written_by` | `prov:wasAttributedTo` (`prov:wasAssociatedWith` for a run) |
| agent, runner / human | `prov:SoftwareAgent` / `prov:Person` |
| `builds_on` | `prov:wasDerivedFrom` the cited bundle |
| `tests`, `reviews`, `about`, `follows`, `contains` | the `almanaque:` namespace |

## Record-collection subset

Each field has one type, objects have fixed keys and there is no `$ref` or `oneOf`, the subset
`almanaque/planning/schemas.py` keeps so the flattener can turn every field into a typed column. Kind-specific
fields are therefore optional in the schema and required by the checker, as `planning/check.py` does
for work records.

## Port to Almanaque (G4)

| Trail | Almanaque |
| --- | --- |
| the probe | a tier-3 source like `work commits`: its tables imported with a preview, pinned at its head |
| task | a work item cites the probe (`item:task-12` → `probe:T@HEAD`) |
| a superseding plan and its review | an accepted decision citing the step, which is what makes it tier 1 |
| `suggested` / `confirmed` links | the same `status` field planning links already carry |
| references | the existing syntax, with the kinds `probe`, `file`, `agent`, `runner` and `human` added to G0's list |

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

# Provenance notebook

A trail of an AI-assisted research task that a reviewer who was not there can read and trust:
what was planned and why, what was run, what contradicted the plan, and how the plan changed.

It is an entry for Task 2 of the [AI for Meta-Science
Hackathon](https://ai4metascience-hackathon.stockholm.ai/), 10–17 November 2026. The brief's
test is that a reviewer can answer "why did they change approach at step 4?" from the log alone.

**Status.** The step format, the checker and three worked example trails exist and are tested.
Capture around a live agent and the reviewer's timeline view are this week's work; see
[PLAN.md](PLAN.md).

## What a trail is

One directory per task, `steps/step-N.json`, each file written once. A step is a task, a plan,
a run, an observation, a review or a note.

Four properties make it more than a log:

- **Expectations come before results.** A plan commits to a measure and a threshold before its
  run, so a reader sees whether a result was predicted or explained afterwards.
- **Outcomes are recomputed.** The checker derives each outcome from the measures, and reads
  the measures again from the metrics file the run wrote. An agent does not grade its own run.
- **What failed stays.** A run is recorded before it executes, so a crash or an abandoned
  attempt cannot drop out, and `trail.py facts` shows a plan that was re-run until it held.
- **A citation is stable.** Each step holds the hash of the one before it, and a trail is cited
  at the hash of its last step. A trail that was rewritten and re-chained still checks, but no
  longer has the head it was cited at.

[docs/HACKATHON.md](docs/HACKATHON.md) is the pitch and maps the design to the brief.
[docs/DESIGN.md](docs/DESIGN.md) specifies the steps and rules, and
[docs/GRAPH.md](docs/GRAPH.md) the export of trails as a graph.

## Try it

Requires [uv](https://docs.astral.sh/uv/). The canonical-JSON tests also need Node.js 24 and
are skipped without it.

```sh
uv sync
uv run python trail.py check examples/churn-model-2026-11-11 --store examples/store
uv run python trail.py facts examples/churn-tuning-2026-11-13
uv run pytest
```

The worked example stages the brief's question. In `examples/churn-model-2026-11-11`, step 4 is
a change of approach, and its links say why: it was triggered by step 3 (AUC 0.58 against a
0.75 floor), it supersedes the plan at step 1, and the review at step 7 confirms it.

To see the tamper evidence:

```sh
uv run python trail.py head examples/churn-model-2026-11-11      # the digest to cite
uv run python trail.py verify examples/churn-model-2026-11-11 sha256:…
```

`verify` passes for any head the trail has had, so a trail that grew still resolves. It fails
for a trail whose past was rewritten, however well that trail checks.

## Commands

| Command | Does |
| --- | --- |
| `trail.py check DIR [--store STORE]` | Checks the chain, who wrote what, and that outcomes follow from the measures; with a store, that the measures are the ones the run wrote |
| `trail.py facts DIR` | Lists what a checked trail shows without judging it: attempts per plan, repeats, runs that never settled |
| `trail.py head DIR` | Prints the digest the trail is cited at |
| `trail.py verify DIR HEAD` | Says whether the trail ever had that head |
| `trail.py graph DIR [--csv]` | Exports a checked trail as node and edge tables |
| `trail.py merge OUT DIR... [--csv]` | Exports several trails as one graph and resolves their citations of each other |
| `trail.py examples DIR` | Writes the three example trails and their metrics store |

## Layout

| Path | Contents |
| --- | --- |
| `trail.py`, `step.schema.json` | The checker and the schema of one step |
| `capture/` | The Pi extension that writes steps as the agent works. `canonical.ts` hashes steps as the checker does; `probe.ts` is the spike that capture is built from |
| `examples/` | Three generated trails and the metrics files they cite |
| `scripts/cross.py` | Queries across merged trails with DuckDB |
| `tests/` | The checker's guarantees, and hash parity between TypeScript and Python |

# Capture

`capture.ts` is an extension for the [Pi coding agent](https://github.com/earendil-works/pi), pinned
at 0.84.1. It writes a provenance trail while an agent works on one task. The agent does not write
the trail: capture does, from hooks around the agent's tools. Every trail it writes passes
`trail.py check DIR --store STORE`.

## What it records

| When | Step | From |
| --- | --- | --- |
| The session starts | task (step 0) | the task file, plus Pi's version and `provider/model` |
| The agent calls `propose_plan` | plan | the agent's summary, reasoning and expectations, unshortened; `supersedes` and `triggered_by` when it replaces a plan |
| Before a `bash` command executes | run | the command, a snapshot commit of the code, the digest of `uv.lock`, the public parameters, the digests of the task's inputs |
| After the command ends | observation | the exit code, the duration, the measures in a fresh `out/metrics.json`, the checks against the plan, the outcome, and the workspace files the command opened for reading (`reads`) |
| A metrics file cannot be read, a ceiling is reached, or the provider reports no token usage | note, by the runner | what happened |
| The agent calls `project_map` (with a research map) | note, by the runner | the revision and the heads of the other trails it was shown |

Five rules make the record more than a log:

- **A run is written before its command starts.** A command with no plan is blocked, and so is one
  capture could not record. A command that never returns leaves its run unsettled.
- **Fresh metrics only.** `out/metrics.json` counts for a command when that command made or changed
  it. It must be one object of measure names to finite numbers. Anything else gives no measures and a
  runner note. The file is copied to the store under its digest, where `check --store` reads it again.
- **The outcome is computed.** Checks and outcome follow `trail.check_observation`, and the checker
  recomputes them. The agent never says how a run came out.
- **What a command opened is traced.** Each command runs under `strace`, which follows every process
  it starts. The observation lists the workspace files opened for reading, with their digests, so
  reading a held-out file is a fact of the trail. `NOTEBOOK_TRACE=0`, or a machine without `strace`,
  gives observations with no `reads`, and nothing is then claimed about what they opened.
- **The agent learns step ids from receipts.** The text the model reads for each command ends with a
  line such as `[notebook] run step-5, observation step-6: contradicted (auc 0.58, expected >= 0.75)`.
  A plan that replaces another cites those ids, and a wrong id is refused with the usable ones.

A code snapshot is a commit of the whole working tree on `refs/heads/notebook/TRAIL`, made with an
index of its own. `HEAD`, the real index and the working tree are not touched. Unchanged code is
cited at the same commit again.

## Running it

```sh
scripts/live.sh DEMO_DIR NAME [pi options]
```

`DEMO_DIR` holds `task.json`, `prompt.md` and `workspace/`. The launcher copies the workspace to a new
git repository outside this one, runs Pi there with capture and [protocol.md](protocol.md) loaded, then
bundles the snapshots and checks the trail. Its exit status is the check's. Under `live/NAME`, or
`$NOTEBOOK_LIVE/NAME`, it leaves `steps/`, `code.bundle`, `session/` and `events.jsonl`; metrics files
go to `live/store`. `git clone -b notebook/NAME live/NAME/code.bundle` gives the repository that
`trail.py view --code` reads.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOTEBOOK_TASK`, `NOTEBOOK_TRAIL`, `NOTEBOOK_STORE` | set by the launcher | the task file, the trail's directory and the metrics store |
| `NOTEBOOK_MAX_RUNS` | 40 | the most run steps one trail may hold |
| `NOTEBOOK_MAX_TOKENS` | 2000000 | the most tokens the session may use |
| `NOTEBOOK_WALL` | 1800 | the most seconds Pi may run, enforced by the launcher |
| `NOTEBOOK_LIVE` | `live/` | where trails are written |
| `NOTEBOOK_TRACE` | on when `strace` is found | `0` runs commands untraced |
| `NOTEBOOK_SANDBOX` | `0`; `scripts/fleet.sh` sets `1` | `1` runs each command in a `bwrap` sandbox (below). Capture refuses to start if `bwrap` is missing |
| `NOTEBOOK_MAP`, `NOTEBOOK_REPO` | unset; set by `scripts/fleet.sh` | a research map and this repository: together they give the agent the `project_map` tool |

A missing or wrong value stops Pi before the session starts, and the launcher fails a trail that has
no step 0. Once a ceiling is reached the next tool call is blocked, a runner note says which ceiling,
and the session ends.

To run without a model, load the scripted provider, which replays the tool calls in a JSON file:

```sh
NOTEBOOK_LIVE=/tmp/live NOTEBOOK_SCRIPT=tests/fixtures/capture-demo/change.json \
  scripts/live.sh tests/fixtures/capture-demo demo-run -e capture/scripted.ts --provider script --model scripted-1
```

`--model scripted-1` is needed where Pi's settings name a default model, which `--provider` alone does
not override. The tests also point `PI_CODING_AGENT_DIR` at an empty directory, so they cannot reach a
real model's key.

## With a research map, and in a sandbox

`scripts/fleet.sh MAP PREFIX ROUTE… -- [pi options]` runs up to three agents at once on one research
map ([spec 7](../docs/specs/07-live-map.md), [spec 8](../docs/specs/08-rests-on.md)).

- **`project_map`** shows an agent the map and what the other trails have found, each step pinned at its
  trail's present head. A plan may build on a step it was shown (`builds_on`); any other reference is
  refused. Numbers from a run that opened a sealed input are withheld. What another agent wrote arrives
  marked with its writer, as text and not instructions.
- **The sandbox.** With `NOTEBOOK_SANDBOX=1` each command runs as `strace … -- bwrap … -- bash -c COMMAND`.
  The file system is read-only except the workspace and uv's cache. This repository, the trails, the store,
  the map, the other agents' workspaces and Pi's configuration are hidden: each reads as an empty
  directory. Capture itself runs outside it, and writes the trail there.

## Limits

- **The trail is protected from the agent's shell only in the sandbox.** `write` and `edit` to the trail
  and the store are always blocked by resolved path. Without `NOTEBOOK_SANDBOX=1`, a `bash` command can
  still reach them. A changed step breaks the chain and fails `check`; a deleted last step does not.
- **The sandbox hides named places.** Everything else on the machine stays readable, and the network is
  open, so a public dataset's held-out labels can still be downloaded. It keeps agents of one fleet
  apart; it does not contain a hostile one.
- **A trace keeps workspace reads only.** A file opened outside the workspace is not in `reads`; it is
  known only from the command line.
- **Freshness is the file's modification time.** On a file system that keeps times to the second, a
  command that rewrites the metrics within the same second as the one before is not seen as fresh, and
  its observation is inconclusive.
- **A run cites the code as it stood before its command.** A command that edits code and then runs it,
  such as `sed -i ... fit.py && python fit.py`, cites the code from before the edit. The edit shows in
  the next run's snapshot.
- **Only `bash` commands are runs.** What the agent reads with Pi's other tools is not recorded or
  traced. What it edits shows in the next run's snapshot.
- **Parameters** are recorded for `--name value` and `--name=value` only, when the task lists the name
  as public. A flag spelt with hyphens matches a name spelt with underscores.
- **A command killed with the session** may leave children running, and what they write is in no step.
- **No redaction, keyed digests or resuming.** A trail is one session, and commands are recorded as
  typed, absolute paths included. The redactor and the ledger shown to the agent are not built.
- **A provider that reports no token usage** cannot be stopped by the token ceiling. Capture writes a
  note saying so, once; the ceilings on runs and on the wall clock still apply.
- A model that only sends malformed tool calls never reaches the ceilings, because Pi rejects those
  calls first. The launcher's wall clock covers that case.

## What a host must offer

The step builders in `capture.ts` take plain data and know nothing of Pi. An adapter for another agent
is new wiring around them, and needs five things from its host:

1. a hook that is awaited before a command runs and can stop it, failing closed;
2. a tool the adapter defines and can refuse from;
3. the command's exit code;
4. a way to add a line to the result the model reads;
5. an unattended mode, with a scripted provider so that tests need no key.

`probe.ts` is the spike that checked these on Pi, and a person uses it for the real-model smoke test.
`canonical.ts` hashes steps as `trail.py` does.

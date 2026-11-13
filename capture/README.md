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
| After the command ends | observation | the exit code, the duration, the measures in a fresh `out/metrics.json`, the checks against the plan, the outcome |
| A metrics file cannot be read, or a ceiling is reached | note, by the runner | what happened |

Four rules make the record more than a log:

- **A run is written before its command starts.** A command with no plan is blocked, and so is one
  capture could not record. A command that never returns leaves its run unsettled.
- **Fresh metrics only.** `out/metrics.json` counts for a command when that command made or changed
  it. It must be one object of measure names to finite numbers. Anything else gives no measures and a
  runner note. The file is copied to the store under its digest, where `check --store` reads it again.
- **The outcome is computed.** Checks and outcome follow `trail.check_observation`, and the checker
  recomputes them. The agent never says how a run came out.
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
go to `live/store`. `git clone live/NAME/code.bundle` gives the repository that `trail.py view --code`
reads.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOTEBOOK_TASK`, `NOTEBOOK_TRAIL`, `NOTEBOOK_STORE` | set by the launcher | the task file, the trail's directory and the metrics store |
| `NOTEBOOK_MAX_RUNS` | 40 | the most run steps one trail may hold |
| `NOTEBOOK_MAX_TOKENS` | 2000000 | the most tokens the session may use |
| `NOTEBOOK_WALL` | 1800 | the most seconds Pi may run, enforced by the launcher |
| `NOTEBOOK_LIVE` | `live/` | where trails are written |

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

## Limits

- **The trail is not protected from the agent's shell.** `write` and `edit` to the trail and the store
  are blocked by resolved path. A `bash` command can still reach them. A changed step breaks the chain
  and fails `check`; a deleted last step does not.
- **Freshness is the file's modification time.** On a file system that keeps times to the second, a
  command that rewrites the metrics within the same second as the one before is not seen as fresh, and
  its observation is inconclusive.
- **Only `bash` commands are runs.** What the agent reads with Pi's other tools is not recorded. What
  it edits shows in the next run's snapshot.
- **Parameters** are recorded for `--name value` and `--name=value` only, when the task lists the name
  as public. A flag spelt with hyphens matches a name spelt with underscores.
- **A command killed with the session** may leave children running, and what they write is in no step.
- **No redaction, keyed digests or resuming.** A trail is one session. The redactor, the read-only
  mount and the ledger shown to the agent are not built.
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

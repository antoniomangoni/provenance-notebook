# Spec 2: capture

Branch `spec/02-capture`. Depends on no other spec. The live run depends on it.
Written to [the meta-spec](../meta-spec.md); [AGENTS.md](../../AGENTS.md) applies throughout.

The step format and its checker exist, and `capture/probe.ts` proved against Pi 0.84.1 that an
extension can write steps as an agent works. This spec turns the probe into the extension that
writes a real trail, and adds the launcher that runs a task under it.

## Goals and non-goals

Goals:

1. `capture/capture.ts`, a Pi extension. Every trail it writes passes
   `trail.py check DIR --store STORE`.
2. `scripts/live.sh DEMO_DIR NAME [pi options]`, which runs one task under capture.
3. Scripted tests of every rule below, offline, with no model key.

Non-goals:

- The redactor, keyed digests, the read-only mount and the ledger shown to the agent.
- Any agent other than Pi 0.84.1. Resuming a trail. Citing another probe.
- Any change to `step.schema.json`, `trail.py`, `capture/canonical.ts` or `capture/probe.ts`.
  The probe stays as it is: a person uses it for the real-model smoke test.
- The view, the demo task, reviews and notes by people.
- A sandbox. `bash` can still reach the trail's path, and `capture/README.md` says so.

## Interface

Capture reads three environment variables and fails at load when one is missing or wrong:

| Variable | Meaning |
| --- | --- |
| `NOTEBOOK_TASK` | path of the task file |
| `NOTEBOOK_TRAIL` | the trail's directory. Its name is the trail's name and fits the schema's pattern. It must not hold a `steps/` directory yet |
| `NOTEBOOK_STORE` | the directory metrics files are copied to, named by digest |

Two more are optional, and a value that is not a positive integer fails at load:

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOTEBOOK_MAX_RUNS` | 40 | the most run steps one trail may hold |
| `NOTEBOOK_MAX_TOKENS` | 2000000 | the most tokens the session may use |

The task file holds `summary`, `question`, `project`, `declared_measures`, `public_parameters`,
`inputs` (paths relative to the workspace) and `by` (`human:NAME`). The workspace is Pi's
working directory and must be a git repository. A run reports numbers by writing
`out/metrics.json` there: one object of measure names to numbers.

## Behaviour

Steps are written through one queue, so `seq` and `prev` follow write order. Runner steps are
`by: runner:notebook/0.1`. Agent steps are `by: agent:pi/MODEL`, with every character the
schema's pattern refuses replaced by `-`. `hook` names the Pi hook or tool that wrote the step.

### Task

At `session_start`, step 0 is written from the task file, with `agent` holding `pi`, Pi's
version and `provider/model`.

### Plans: the `propose_plan` tool

Parameters: `summary`, `reasoning`, `expectations` (each `name`, `measure`, `comparison`,
optional `threshold`), optional `supersedes` and `triggered_by`. The tool is sequential. It
refuses, by throwing, and writes nothing when:

- there is no expectation, or a numeric comparison lacks a threshold or names a measure the task
  does not declare (the message lists the declared measures);
- two expectations get the same name. Names are first lowercased and hyphenated to fit the
  schema; a name that is then empty is refused;
- `summary` is over 200 characters or `reasoning` over 8,000. Capture never shortens what the
  agent wrote;
- only one of `supersedes` and `triggered_by` is given, `supersedes` is not a plan in this
  trail, or `triggered_by` is not an observation in it. The message lists the plans and the
  observations by id, each observation with its outcome.

An accepted plan is written with `suggested` links, and the result says `recorded as step-N`.

### Runs

The current plan is the most recent one. A `bash` call with no plan is blocked, and the reason
says to call `propose_plan` first and that looking around is done under a plan whose only
expectation is `exit_ok` on measure `exit`.

Otherwise, in `tool_call` and so before the command executes, capture writes a run step:

- `command.shown` is the first 2,000 characters, `command.digest` the SHA-256 of all of it, and
  `summary` its first 200 characters on one line.
- `code.ref` is `commit:SHA` of a snapshot. Capture stages the whole working tree in a temporary
  index, writes the tree, and commits it on `refs/heads/notebook/TRAIL` with the previous
  snapshot as parent and a fixed identity. When the tree equals the previous snapshot's, that
  commit is cited again, so runs of the same code share a reference. `HEAD`, the real index and
  the working tree are never touched.
- `environment` is the SHA-256 of the workspace's `uv.lock`, or absent without one.
- `parameters` holds each `--name value` or `--name=value` whose name the task lists as public,
  with its value and the SHA-256 of the value. Other flags are not recorded as parameters.
- `inputs` holds `file:PATH` and the SHA-256 of each declared input that exists.
- It `implements` the current plan.

### Observations

`bash` is overridden with the stock definition, sequential, with `exec` wrapped as in the probe.
After the command ends, and before its result reaches the model, capture writes the
observation:

- `exit_code` (`-1` when there is none) and `duration_ms`.
- **Fresh metrics only.** `out/metrics.json` counts when it did not exist before the command or
  its modification time changed during it. Capture never deletes it.
- A fresh file that is one non-empty object of valid measure names to finite numbers is copied
  to the store and becomes `outputs`, `measures_source` and `measures`. A fresh file that is
  anything else gives no measures, and a runner `note` about the observation says so.
- `checks` and `outcome` follow `trail.check_observation` exactly: a check per expectation whose
  measure is present, `failed` for a non-zero exit with no `exit_fail` expectation,
  `inconclusive` when a check is missing, otherwise `as_expected` or `contradicted`. A failed
  observation has `error.class` `exit`.
- `summary` states the outcome and each missed expectation.

A command that never returns leaves its run unsettled, which is the record of it.

### Receipts

The text the model sees for each command ends with one line, on success and on failure:

    [notebook] run step-5, observation step-6: contradicted (auc 0.58, expected >= 0.75)

These ids are how the agent names an observation in `triggered_by`. A receipt holds measures
and thresholds, never a parameter's value.

### Budget

A model can loop, and a provider that bills cached input at the full rate makes a loop's cost
grow with the square of its calls. Capture therefore stops a run at two ceilings:

- **Runs.** The number of run steps written.
- **Tokens.** The sum, over every `turn_end`, of the usage's `input`, `output`, `cacheRead` and
  `cacheWrite`. A turn that reports no usage adds nothing.

Once either is reached, the next tool call of any kind is blocked with `terminate`, and nothing
runs. Capture writes one runner `note` about the task step, naming the ceiling, its limit and
the count, and the reason the model sees says the same. No run step is written for the blocked
call.

Pi validates a tool call's arguments before `tool_call`, so a model that only sends malformed
calls never reaches this stop. The launcher's wall clock covers that case.

### Guards and protocol

`write` and `edit` are blocked when the resolved real path is inside the trail or the store.
`capture/protocol.md` states the rules to the agent in under 200 words: plan before any command,
exploration plans, numbers through `out/metrics.json`, receipts, and replacing a contradicted
plan with `supersedes` and `triggered_by`. The launcher appends it to the system prompt.

### The launcher

`scripts/live.sh DEMO_DIR NAME [pi options]`:

1. Refuses a `NAME` that does not fit the trail pattern or already exists under the output
   root, which is `live/` here or `$NOTEBOOK_LIVE`.
2. Copies `DEMO_DIR/workspace/`, without any `out/` or `.venv/` in it, to a new directory
   outside this repository, makes it a git repository with one commit, excludes `out/` and
   `.venv/` through `.git/info/exclude`, and runs `uv sync` there when it has a
   `pyproject.toml`.
3. Runs Pi there with `-p --mode json --no-context-files`, `capture.ts`, the protocol appended,
   the session directory at `ROOT/NAME/session`, the options passed through, and the text of
   `DEMO_DIR/prompt.md` as the message. Standard output goes to `ROOT/NAME/events.jsonl`.
   Pi runs under `timeout`, for `NOTEBOOK_WALL` seconds or 1,800. When the time runs out the
   launcher says so and goes on.
4. Whatever Pi's exit status, bundles the snapshot branch to `ROOT/NAME/code.bundle`, runs
   `trail.py check` with the store at `ROOT/store`, and prints the result and the workspace's
   path. The workspace is kept. The launcher's own exit status is the check's.

## Technical decisions and stack

- TypeScript, run by Pi's loader and by Node.js 24 with no build step. Pi stays pinned at
  0.84.1. No new dependency.
- Digests and canonical JSON come from `capture/canonical.ts`.
- Steps are built by functions that take plain data and know nothing of Pi. The Pi hooks only
  gather that data and call them. An adapter for another agent is then new wiring, and
  `capture/README.md` lists what such a host must offer: a hook awaited before a command runs
  that can stop it, a tool the adapter defines and can refuse from, the command's exit code, a
  way to add a line to the result the model reads, and an unattended mode.
- Capture never reads which provider or model is in use, beyond naming it in step 0. Changing
  model is a launcher option.
- The scripted provider moves to `capture/scripted.ts`, loaded with a second `-e` and
  `--provider script`. It replays the turns in the JSON file `NOTEBOOK_SCRIPT` names.
- The table "Capture host, checked at Pi 0.84.1" in `docs/DESIGN.md` lists what the probe
  verified. Where Pi behaves otherwise than this spec assumes, change the spec first.

## Project structure and git workflow

The extension sits in `capture/`, the launcher in `scripts/`, tests in `tests/`. Work on
`spec/02-capture`, in small commits with imperative subjects, and open one pull request to
`main`.

## Target files

| File | Change |
| --- | --- |
| `capture/capture.ts` | new |
| `capture/scripted.ts` | new: the scripted provider |
| `capture/protocol.md` | new |
| `capture/README.md` | new: what capture records, how to run it, its limits, and what a host must offer |
| `scripts/live.sh` | new |
| `tests/test_capture.py` | new |
| `tests/fixtures/capture-demo/` | new: `task.json`, `prompt.md`, and a `workspace/` whose `fit.py` writes the metrics its flags name, with the standard library only |

## Testing and conformance

`tests/test_capture.py` runs the launcher with the scripted provider and `NOTEBOOK_LIVE` set to
a temporary directory, and skips without Node.js or `capture/node_modules/.bin/pi`. Every
scenario asserts that `trail.check(steps, store)` is empty.

1. **A change of approach.** An exploration plan and an `ls`; a plan with a floor; a run that
   misses it; a plan that supersedes it, citing the observation's id; a run that meets it. The
   test asserts the kinds in order, the public parameters and their values, the input digests,
   and the receipt lines in `events.jsonl`.
2. **A run is written before it executes.** A command that tests for its own run step's file
   exits 0.
3. **Stale metrics.** An `ls` after a metrics run has no measures and is `inconclusive`.
4. **Two commands in one turn.** Each observation observes its own run, and only the command
   that wrote metrics has measures.
5. **No plan.** `bash` is blocked, no step is written, and the reason names `propose_plan`.
6. **Refusals.** An undeclared measure; `supersedes` alone; an unknown id. Nothing is written,
   and the messages list what can be used.
7. **A failing command.** Exit 3 gives `failed`, an error class, and a receipt.
8. **Snapshots.** Run, change `fit.py`, run, run: the second reference differs from the first
   and equals the third; the bundle holds them; the workspace's `HEAD` and status are unchanged.
9. **Guards.** `write` and `edit` to the trail are blocked.
10. **Malformed metrics.** A nested object gives no measures and a runner note.
11. **The run ceiling.** With `NOTEBOOK_MAX_RUNS=1`, the second command is blocked and never
    executes, one runner note names the ceiling, and the session ends.
12. **The token ceiling.** With `NOTEBOOK_MAX_TOKENS` below the scripted usage of two turns, the
    same holds.
13. **The wall clock.** With `NOTEBOOK_WALL=3` and a command that sleeps for 20 seconds, the
    launcher still writes the bundle and checks the trail, and the run is unsettled.

## Sequence

1. `scripted.ts`, the fixture, the launcher, and a capture that writes step 0. A trail of one
   step checks.
2. `propose_plan` and the block on `bash`, with tests 5 and 6.
3. Runs: snapshot, parameters, inputs, with tests 2 and 8.
4. Observations, fresh metrics, checks and receipts, with tests 1, 3, 4, 7 and 10.
5. Guards, `protocol.md`, `capture/README.md`, the bundle and the final check, with test 9.
6. The budget and the wall clock, with tests 11 to 13.
7. The self-audit.

## Commands and code style

```sh
uv sync && npm ci --prefix capture
uv run pytest tests/test_capture.py
uv run ruff check
NOTEBOOK_LIVE=/tmp/live NOTEBOOK_SCRIPT=tests/fixtures/capture-demo/change.json \
  scripts/live.sh tests/fixtures/capture-demo demo-run -e capture/scripted.ts --provider script
```

TypeScript uses tabs and ES modules, as `canonical.ts` does. `live.sh` is `bash` with
`set -euo pipefail`.

## Boundaries

- **Always**: run the tests and `ruff check` before each commit; fail closed, so that a
  capture error blocks the command it could not record.
- **Ask first**: a new dependency or another Pi version; any change to the interface above or
  to a file outside the target files; a rule the checker would have to change for.
- **Never**: put a parameter's value in a message unless the task lists it as public; delete or
  rewrite a file in the workspace; write a step file twice; move the workspace's `HEAD`.

## Rejection criteria

The work is rejected if any of these holds:

- a trail written by any test scenario fails `trail.check` with its store;
- a run step can be written after its command started, or a command can run unrecorded;
- an observation takes measures from a file its command did not write;
- a replacement plan cannot be made from the ids a model is shown;
- a command can run after a ceiling was reached, or the launcher can wait past its wall clock;
- `step.schema.json`, `trail.py`, `canonical.ts` or `probe.ts` changed;
- the tests need a model key or the network.

## Self-audit

After each step of the sequence, read the diff against the goals, non-goals and rejection
criteria, and run that step's tests. Before the pull request, run the commands above, open one
written trail's steps and read them as a reviewer would, and list in the description each
numbered test with its name.

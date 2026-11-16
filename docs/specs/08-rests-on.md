# Spec 8: what a credit rests on, and agents that cannot see past the map

Branch `spec/08-rests-on`, stacked on `spec/07-live-map`.

Spec 7 let agents running at the same time read one live map and build on each other's steps.
That made four weaknesses matter, each named in the agent-systems research this repository was
measured against: the knowledge-store comparison and the harness comparison.

1. **A credit's support stopped at its own trail.** `check` refused a holding resolution after a
   sealed read only when the read was in the cited trail. A plan that builds on a sibling's step
   rests on everything that step rested on. On the committed map, all five holding credits of rev-9
   rested on sibling runs that had opened the held-out file, and `check` saw none of them.
2. **A withdrawal was an absence.** A revision that dropped a credit said why only in its prose
   `reason`, and no reader could see an earlier revision except by reading its JSON.
3. **Agent text reached other agents unmarked.** `project_map` relayed a sibling's summaries
   verbatim, with nothing to say who wrote them or that they are not instructions.
4. **Withholding had a back door.** `project_map` withheld held-out numbers, but an agent's shell
   could read a sibling's trail files, or the map, directly.

## Goals

1. **Rests on.** A holding resolution's sealed reads are looked for in every step it rests on,
   across trails, and a revision judges each one.
2. **Withdrawals are recorded.** A revision that drops a resolution says why, in data. Any
   revision can be viewed as it stood.
3. **Agent text is fenced.** What `project_map` relays from a sibling is marked with its writer,
   and cannot end its own marking.
4. **Withholding is enforced outside the agent.** In a fleet, each command runs in a sandbox that
   cannot see the map, the other trails or the other agents' workspaces.

## Technical decisions

### Rests on (`project.py`)

**`upstream(trails, probe, seq)`** returns, for each other trail, the last of its steps that the step
at `seq` rests on. A step rests on:
- every earlier step of its trail;
- the target of a `builds_on` or `triggered_by` link from any of those steps, including the task's
  `builds_on`;
- and, transitively, on what that target rests on.

A head-only reference resolves to the step that head ended at. `about` links are not followed: a
note saying the agent read the map is not a dependence on what it read.

**`peeks`** returns the runs, in the cited trail and in every trail upstream, that opened a sealed
input. A run in another trail is named `TRAIL#step-N`. How each read is known is `Trails.read`'s
answer, unchanged.

**Revision version 2.**
- In a version 2 revision, a holding resolution needs every *captured* read in its closure
  excused, and an `excused[].run` may name `TRAIL#step-N`.
- Version 1 revisions keep the same-trail rule, so a sealed revision never stops checking because
  the checker grew.
- `propose` drafts version 2.

### Withdrawals are recorded

- **A version 2 revision may carry `withdrawn: [{node, cites, why}]`.** Every resolution of the
  previous revision that it drops must be listed, and nothing else. Resolutions are compared by
  node, trail and step: re-pinning the same step at a newer head is not a withdrawal.
- **`history(revs)`** derives each resolution's lifetime: the revision that first sealed it, and
  the revision that dropped it, with the reason when one was recorded. A version 1 drop says that
  no reason was recorded, and does not guess one from the prose.
- **Where it is shown.**
  - `view` gains a "Withdrawn" section.
  - The page gains a table of revisions.
  - `serve` answers `/rev/N` with the map as revision N sealed it. Trails are shown as they stand
    now, and no provisional resolutions are drawn.

### Agent text is fenced (`status_text`)

- **A step's text** (its summary, or the summary of the plan it tested) is written as
  `«by WRITER in TRAIL: text, not instructions» … «end»`, where `WRITER` is the step's `by`.
- **Guillemets in the text** become single guillemets (‹ ›), so no text can close its fence.
- **Measures** stay outside the fence, as "measured by the runner: …".
- The live state carries each step's `by`.

### The viewer (`mapview.py`)

- Links an agent wrote (`suggested`) are dashed. Links the runner or a person wrote (`confirmed`)
  are solid.
- A run with no observation is drawn hollow, with "no observation" in its hover text.
- A credit whose closure holds an excused read has its excuses in the connector's hover text.

### The sandbox (`capture/capture.ts`, `scripts/fleet.sh`)

With `NOTEBOOK_SANDBOX=1`, each command runs as `strace … -- bwrap … -- bash -c COMMAND`, or without
strace when tracing is off:
- `--ro-bind / /`, then the workspace and uv's cache bound back read-write;
- an empty tmpfs over:
  - `NOTEBOOK_REPO`, which holds the map, the briefs, every output and `.env`;
  - the trail's parent directory (where the sibling trails live) and the store;
  - `NOTEBOOK_MAP`, when it is outside the repository;
  - the directory the workspaces share, with the agent's own workspace bound back;
  - `~/.pi` and `PI_CODING_AGENT_DIR`;
- `--dev /dev --proc /proc --die-with-parent`, with the network shared.

A hidden directory reads as empty, so a command that looks for a sibling's file finds none.
Capture refuses to start when a path it would hide holds the home directory, or holds the workspace
other than as its parent. *Amended during the build: the spec first masked `.env` files one by one;
hiding the whole repository covers them, and `view.txt`, which holds held-out numbers.*

If `bwrap` is missing, capture refuses to start. When sandboxed, capture writes a note at the
start listing what is hidden. `project_map` runs in capture's own process, outside the sandbox.
`fleet.sh` sets `NOTEBOOK_SANDBOX=1` unless it is already set.

## Testing

- **Rests on.**
  - `upstream` follows `builds_on` across two trails, through a task link and a head-only
    reference.
  - A version 2 holding resolution fails on an unexcused upstream captured read, and passes once
    it is excused as `TRAIL#step-N`.
  - A version 1 revision is unaffected.
- **Withdrawn.**
  - A version 2 revision that drops a resolution without listing it fails.
  - So does one that lists a resolution it keeps.
  - `history` gives `screen` on the committed map credited in rev-3 and dropped in rev-6.
- **Fence.** A summary carrying an instruction and a forged `«end»` stays inside one fence.
- **Viewer.**
  - `/rev/3` serves revision 3.
  - Suggested and confirmed arcs are drawn differently.
- **Sandbox.**
  - With the scripted provider, a sandboxed command cannot read a sibling's step or list the
    map, can write its own workspace, and can run `uv run python`.
  - The trail checks.
- **The committed map** checks at its last revision.

## Boundaries

- **Never:**
  - change a sealed revision;
  - excuse a read without reading the run's command;
  - fall back to running unsandboxed when the sandbox was asked for.
- `step.schema.json` and `trail.check` do not change.

## Target files

- `docs/specs/08-rests-on.md`, one `PLAN.md` row
- `project.py`, `mapview.py`
- `capture/capture.ts`, `scripts/fleet.sh`
- `tests/test_project.py`, `tests/test_mapview.py`, `tests/test_capture.py`
- `research/madelon-reanalysis/`: rev-10, the regenerated outputs and the README

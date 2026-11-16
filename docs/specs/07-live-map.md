# Spec 7: the live map, with several agents contributing to it

Branch `spec/07-live-map`, stacked on `spec/06-traced-reads`.

A research map (spec 5) is visible only after the work, as text and as tables. Its agents work
blind to each other: each writes its own trail from a brief, and a coordinator joins the
results afterwards.

This spec does two things:

- it draws the map and its trails as one picture, which updates while agents run;
- it lets agents running at the same time read that state and cite each other's steps, so the
  project graph gains edges between their trails as they work.

## Goals

1. **One state.** `project.py` computes the map's live state once, and three readers use it:
   - the terminal (`status`);
   - the viewer (`page`, `serve`);
   - the agents (capture's `project_map` tool).
2. **The viewer.**
   - `project.py page` writes a static picture of the map as a metro map, with a lane for each
     trail and the links between them.
   - `project.py serve` shows the same picture, updated within seconds of a step being written.
3. **Agents read and cite.** With `NOTEBOOK_MAP` set, capture gives the agent a `project_map`
   tool, and records each call as a note. A plan may then build on a sibling's step that a call
   returned.
4. **A fleet.** `scripts/fleet.sh` runs several routes at once, and one real run of two or three
   agents on Madelon shows the result.

## Non-goals

- **Agents sealing revisions.** A coordinator seals; agents only read and cite.
- **Agents writing to each other's trails.** Each trail has one writer.
- **A hosted service.** `serve` binds to 127.0.0.1.
- **A JavaScript build.** The page is server-rendered SVG. The live page has one small inline
  script.

## Technical decisions

### The live state (`project.py`)

`live_state(revs, trails, for_probe=None)` returns a JSON-ready dict.

**From the latest sealed revision:**
- goals, nodes and routes with their derived states (`state`, `node_state`);
- the shared nodes (`shared_nodes`);
- the next milestones (`ranked`).

**Provisional resolutions.** These are `propose`'s candidates, each pinned at its trail's present
head and marked `sealed: false`. Nothing provisional reaches a revision without `seal`.

**For each trail:**
- its route (`ROUTE_TAG`), agent, head, number of steps and the time of its last step;
- its check problems, and whether it is `reading`;
- each step's id, kind, time, summary, outcome and measures;
- how a sealed read is known (`Trails.read`);
- its links to other probes.

**Discovery.** `--live DIR` adds every `DIR/*/` whose `steps/step-0.json` names the map's
project. A trail being written may end in a half-written file. Since steps are written in
order, `Trails` keeps the steps up to the first unparsable file and marks the trail
`reading`. It is never dropped.

**Withholding.** With `--for TRAIL`, a sibling's observation whose run is known to have opened a
sealed input loses its measures and its summary. It is shown as "scored a sealed input; numbers
withheld". This holds whether the read was captured, re-executed or only named. It is rev-3's rule
across agents: otherwise one agent's held-out score could steer another's design.

**`project.py status MAP [--for TRAIL] [--json]`.** It prints the state: as text for a person or
an agent, as JSON for a program.

**What an agent is shown of a sibling.** For each other trail, `status` prints its latest step, and its last
three observations with their measures and the summary of the plan each tested. Each is pinned
at the trail's present head, so a plan can cite it.

**Re-executions count.** A map's own `retrace/` files are used for the trails given, without
`--reads`. A run known only by re-execution to have opened a sealed input is therefore withheld
from agents too.

**Judged steps stay judged.** `propose` does not offer a step that any revision has already
cited. A credit that a revision withdrew stays withdrawn until a later revision says otherwise.

**Excused reads.** A holding resolution may carry `excused: [{run, why}]`, for a captured read of
a sealed input that the sealer judged harmless, such as a row count. `check` accepts the
resolution only if every captured read is named. It refuses an excuse for a run that read
nothing, and an excuse without a reason. `view`, `status` and the page show each excuse beside
the read. Added after the second fleet, where every agent counted the held-out file's rows
before designing anything.

**Withheld results.** For an agent, a sibling's unsealed result from a run that opened a sealed
input is left out of what it is shown. That it met a milestone judged on the sealed input is
itself a held-out result.

**`seal`.** It creates `rev-N.json` exclusively, so of two seals of the same revision, the
second fails and says so.

### The viewer (`mapview.py`)

**The map panel, a metro map.**
- Milestones are stations, laid out left to right by their longest-path depth over consecutive
  pairs on route paths.
- Each route is a coloured line through its stations, ending at its goal.
- Station marks:
  - reached: filled;
  - refuted: a cross;
  - open: hollow;
  - supported only by a provisional resolution: a dashed ring;
  - on more than one route: drawn as an interchange.
- An abandoned route is dimmed, with its reason in the hover text.

**The trails panel.**
- One lane for each trail, labelled with:
  - the trail, its route and agent;
  - "running", with the time since its last step, or "finished".
- Step marks:
  - a mark by step kind;
  - an observation coloured by its outcome;
  - a ring on a run that opened a sealed input, drawn differently when it was captured and when
    it was re-executed;
  - the newest step marked.
- Lines from each station to the observations that resolve it.
- Arcs between lanes for cross-trail `builds_on` and `about` links.

**Text and theme.**
- Every string from a step or a revision is escaped.
- Hover text is SVG `<title>`.
- Colours are CSS tokens with a dark theme.
- A legend sits under the picture.

**`project.py page … --out FILE`** writes the page with no script, and loads nothing external.

**`project.py serve … [--port 8077]`.**
- A stdlib `ThreadingHTTPServer`, bound to 127.0.0.1.
- `/` is the page with a short inline script. Every two seconds the script asks for `/frame`
  with the last ETag. The ETag is a digest of every trail's head and the last revision. The
  server answers 304 when nothing changed, or with the new SVG.
- `/trail/NAME` is that trail's page from `view.page`.

### Agents read and cite (`capture/capture.ts`)

**Configuration.** `NOTEBOOK_MAP` (the map directory) and `NOTEBOOK_REPO` (this repository)
enable the tool. Without them, capture is as it was.

**`project_map`.**
- **What it runs:** `uv run --project REPO python REPO/project.py status MAP --live <the
  trail's parent> --for <this trail>`.
- **Its environment:** only `PATH`, `HOME` and `TMPDIR`. The model key never reaches it.
- **What it returns:** the text, and each sibling step reference it contains.
- **What it records:** a note step, "Read the project map at rev-N", with an `about` link to each
  sibling probe at the head it was shown.

**`propose_plan`** gains an optional `builds_on: string[]`.
- Each reference must be one that a `project_map` call in this session returned. Any other is
  refused, and the plan is not recorded.
- Each is written as a `builds_on` link with status `suggested`, as every link an agent writes
  is. Capture confirms the reference was shown to the agent, not that the plan uses it.

**A nudge.** When the other trails have new observations since the agent last called
`project_map`, the reply to its next `propose_plan` says so. This was added after the first
fleet, where each agent read the map once, at its start, and never again.

**The checker.** `trail.check` allows `builds_on` on a plan as well as on the task. It is
already cross-probe, so `merge` checks its head and step. The schema stays version 2.

**The store.** A metrics file is created exclusively, so two agents storing the same digest do
not interleave.

### The fleet (`scripts/fleet.sh MAP ROUTE…`)

For each route, the script:
1. writes a brief (`project.py brief --with`) into `research/PROJECT/briefs/PREFIX-ROUTE`;
2. starts `scripts/live.sh BRIEF PREFIX-ROUTE [pi options]` in the background, with
   `NOTEBOOK_MAP` and `NOTEBOOK_REPO` set.

It then waits for every agent and prints each trail's check. Pi options come after `--`.

## Testing

- **State.**
  - `live_state` agrees with `view` on the committed map.
  - A provisional resolution is marked unsealed.
  - `--for` withholds a sibling's sealed-read numbers.
  - Discovery picks trails by project.
  - A truncated last step keeps the trail, marked `reading`.
  - A second seal of the same revision fails.
- **Viewer.**
  - Every station, route line and lane is drawn.
  - A `<script>` in a summary is inert.
  - `page` has no script and nothing external.
  - `serve` answers `/` and `/frame`, gives 304 on an unchanged ETag, and binds to 127.0.0.1.
- **Capture** (scripted provider, two agents at once):
  - `project_map` writes a note pinned at the sibling's real head;
  - a plan building on a returned reference passes `trail.py merge`;
  - a made-up reference is refused;
  - without `NOTEBOOK_MAP` there is no tool;
  - both trails check.
- **Checker.** `builds_on` is accepted on a plan and refused on a run.

## Target files

- `docs/specs/07-live-map.md`
- `project.py`, `mapview.py`
- `trail.py`, `step.schema.json`, `docs/DESIGN.md`
- `capture/capture.ts`, and `capture/scripted.ts`: a scripted turn may cite `{{ref:N}}`, the Nth step
  reference in the latest tool result
- `scripts/fleet.sh`
- `tests/test_project.py`, `tests/test_mapview.py`, `tests/test_capture.py`, `tests/test_trail.py`
- one `PLAN.md` row
- `research/madelon-reanalysis/`: rev-7 and rev-8, the briefs, `map.html`, the outputs and the
  README
- `live/madelon-fleet-*`, written only by capture

## Boundaries

- **Always:**
  - escape agent text;
  - keep provisional and sealed resolutions apart;
  - record each map read as a note.
- **Ask first:** a fleet larger than three agents.
- **Never:**
  - pass the model key to `project.py`;
  - show a sibling's sealed-read numbers to an agent.

## Rejection criteria

- A provisional resolution is drawn or listed as sealed.
- An agent is shown a measure from a sibling run that opened a sealed input.
- A plan's `builds_on` names a head that its trail never had.
- The static page runs a script or fetches anything.

# Research maps

A trail records one path through one task. A research map records the project the paths belong
to:

- the **goals**, which are the end results that would count;
- the **routes** to each goal, each a method and an ordered path of **milestones**;
- the trails that reached each milestone.

Routes share milestones, and a map exists to make use of that. [Spec 5](../docs/specs/05-research-map.md)
is the specification, and `project.py` the tool.

| What it does with shared milestones | How |
| --- | --- |
| Shows where routes converge | `project.py shared` lists milestones on several routes and the trails that reached each. It also lists files read at the same digest, code with the same git tree, and computations repeated across trails. |
| Reuses results | `project.py brief ROUTE` writes a task for one route that `builds_on` the steps already reached on its path. Its workspace is the code that produced the last of them, so the agent starts there. |
| Steers what runs next | `project.py next` ranks each open route's next milestone. The milestone the most open routes are waiting on comes first. |

## Watching a map, and agents that share one

[Spec 7](../docs/specs/07-live-map.md) draws the map and its trails as they grow, and lets agents
running at the same time contribute to the same map.

```sh
uv run python project.py serve research/madelon-reanalysis/map --live live      # http://127.0.0.1:8077/
uv run python project.py page  research/madelon-reanalysis/map --live live --out map.html
scripts/fleet.sh research/madelon-reanalysis/map madelon-fleet boost stable-forest vote -- --provider … --model …
```

- **The picture.** The map is drawn as a metro map: milestones are stations, routes are lines in
  their goal's colour, and goals are the termini. Under it, each trail is a lane of its steps. Lines
  join each milestone to the observations that resolved it. Arcs join steps that cite another
  trail. A milestone a trail has met but no revision has sealed is drawn with a dashed ring, never
  as reached.
- **Agents read the map.** Capture gives an agent of a fleet a `project_map` tool. It shows the map
  and what every other trail has found so far, each step pinned at its trail's present head. Each
  call is recorded as a note naming the revision and the heads it showed.
- **Agents cite each other.** A plan may build on a step that `project_map` showed (`builds_on`),
  so the project graph gains edges between agents' trails as they work.
- **Withheld numbers.** An agent is not shown a sibling's numbers from a run that opened a sealed
  input, whether that read was traced live or found on re-execution. Otherwise one agent's
  held-out score could steer another's design.

[Spec 8](../docs/specs/08-rests-on.md) closes three gaps that sharing opened:

- **A credit rests on what its trail built on.** In a version 2 revision, `check` looks for sealed
  reads in every step a credit rests on, through `builds_on` and `triggered_by` links into other
  trails, and refuses the credit unless the revision excuses each read. `view` and the page show
  what each credit rests on.
- **Withdrawals are recorded.** A version 2 revision lists each resolution it drops in
  `withdrawn`, with why. The page has a table of revisions, and `serve` shows any one at
  `/rev/N`.
- **What agents tell each other is fenced.** `project_map` marks each sibling's text with its
  writer, as text and not instructions. Measures stay outside the fence, as the runner's.
- **Withholding is enforced outside the agent.** `fleet.sh` runs every command in a bwrap
  sandbox. The repository, the trails, the map and the other workspaces are hidden in it, so an
  agent sees its siblings only through `project_map`.

## What a map claims, and what is checked

A map is a chain of revisions, `map/rev-N.json`. Each revision is a whole snapshot, written once
and linked to the one before by `prev`, as steps are. A revision changes the map by being the
next revision, never by being edited, so the diff between two revisions is the change and its
`reason` says why.

A milestone has criteria in the form a plan's expectations take: a measure, a comparison and a
threshold. It is reached when a revision cites an observation, pinned at its trail's head, whose
measures meet them. `project.py check` recomputes every such claim from the step files.

**`check` cannot confirm a route's method.** It confirms the numbers; whether the cited run used
the route's method is read from the code the run cites. The Madelon map shows why this matters.
Its rev-1 credited two trails with routes they had not taken, and the error passed `check`. Rev-2
records the correction and the code that showed it.

## Maps

| Map | Project |
| --- | --- |
| [madelon-reanalysis](madelon-reanalysis/) | the demo task: an inherited Madelon analysis whose cross-validated AUC does not hold on held-out data |

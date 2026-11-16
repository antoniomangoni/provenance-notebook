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

# Provenance trail: the graph a trail lives in

How a checked trail is exported as node and edge tables, how several trails share one graph and
cite each other, and how the format maps to PROV-O and to Almanaque. [DESIGN.md](DESIGN.md) has
the step kinds and rules; none of this is needed to capture, check or read a single trail.

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

# The hackathon entry: Task 2, a provenance-preserving lab notebook

This is an entry for the [AI for Meta-Science
Hackathon](https://ai4metascience-hackathon.stockholm.ai/) (Stockholm AI, the AI for
Meta-Science NeurIPS Workshop and Sweden AI Factory), Stockholm, 10–17 November 2026.
Submission closes 17 November at 18:00 CET. The winner is announced on 24 November and presents
a poster and a talk at the AI for Meta-Science workshop, NeurIPS 2026, Paris, 9–13 December.

## The brief

When AI tools iterate quickly on a research task, the trail can disappear: why a method was
chosen, what was abandoned, which code produced which result. The brief asks for a lightweight
logging or wrapper tool around a single AI-assisted research task that automatically captures:

- each proposed plan or hypothesis and the reasoning behind it;
- what was actually run, including code, parameters and data versions;
- what failed or contradicted expectations, and how the plan changed in response;
- a timeline a human can walk back through to see the actual decision path.

The success criterion: a reviewer who was not present can look at the log afterwards and answer
"why did they change approach at step 4?" without asking the researcher.

## How the design answers it

The step format in [DESIGN.md](DESIGN.md) is what gets captured, and `trail.py` checks it.

| Brief | Here |
| --- | --- |
| plan and reasoning | a `plan` step: the reasoning, plus expectations (a measure, a comparison and a threshold) stated before anything runs |
| what was actually run | a `run` step, written before the command executes: the command, a snapshot commit of the code, the environment and input digests, the parameters |
| failure and contradiction | an `observation` step: measures read from the metrics file the run wrote and checked against the plan's expectations. A run that never finished stays in the trail, unsettled |
| plan changed in response | a new `plan` that `supersedes` the old one and is `triggered_by` the observation that contradicted it |
| a timeline to walk back through | the numbered step files, a single-page view generated from them, and `trail.py why`, which answers the question below for any step |

The worked example stages the brief's question. In `examples/churn-model-2026-11-11`, step 4 is
a change of approach, and its links say why: the observation that triggered it (step 3, AUC 0.58
against a 0.75 floor), the plan it supersedes, and the review that confirmed it.

## What makes it more than a log

- **Expectations come before results.** A plan commits to a threshold before its run, as a
  preregistration does for a whole study. A reader sees whether a result was predicted or
  explained afterwards.
- **Outcomes are recomputed, not claimed.** The checker derives each outcome from the measures,
  and reads the measures again from the file the run wrote. The agent does not grade its own run.
- **What failed stays.** Runs are recorded before they execute, so a crash or an abandoned
  attempt cannot drop out. `trail.py facts` lists what a reviewer would ask about: a plan that
  held only after earlier runs contradicted it, an exact repeat, a run that never settled, and a
  replacement plan that lowers the bar the first one missed.
- **What a run opened is recorded.** Each command is traced as it runs, so reading a held-out file
  is a fact of the trail. A reader names a file as sealed, and the page says which runs had
  opened it before each plan was proposed.
- **A citation of a trail is stable.** Each step holds the hash of the one before, and a trail
  is cited at the hash of its last step. A trail rewritten and re-chained still checks, but it no
  longer has the head it was cited at.

### What it costs the researcher

One file before the task: the question, the measures the run will report, and which parameter
names may be shown. The task's own script writes its numbers to `out/metrics.json`. The agent is
started with one command. After that the researcher writes nothing, apart from any review.

The step format does not depend on the agent. One adapter is built, for the Pi coding agent.
Another agent needs an adapter of its own, and can have one if it offers a hook that is awaited
before a command runs and can stop it, a tool the adapter defines, the command's exit code, and
a way to add a line to the result the model reads.

### What it does not prove

The chain proves order and that nothing was changed after a head was cited. It does not prove
who wrote a step. That rests on the capture host, which alone writes runs and observations and
must be outside the agent's reach. A researcher who controls that host can still fabricate a
trail from the start; what they cannot do is revise one that has been cited. The plan's reasoning
is the agent's own statement, which is why its links are marked `suggested`.

## How it was evaluated

The brief's criterion can be checked, so the entry checks it three ways.
[PLAN.md](../PLAN.md#evidence) has the questions and the protocol, and
[evidence/](../evidence/README.md) the results.

- `trail.py why TRAIL STEP` prints the answer to the brief's question from the links alone. A
  test pins it on the worked example, and it answers for step 14 of the live trail.
- Models that had not seen the task answered fixed questions, once from the generated view and
  once from what a reviewer has today, the agent's raw session transcript and the git log. The
  answers were graded against a key taken from the step files. **The view was not needed:** a
  model answers as well from the transcript. The view's measured advantage is its length, a
  tenth of the transcript's.
- A person who did not see the task answers the brief's question from the view, in the video.

Every live attempt is committed: twenty-one trails. On Madelon, two were the task itself, three
were steered one at a time by a research map, six ran as two fleets of three agents sharing that
map, one ran in a sandbox, and three ran in the sandbox to settle forecasts. Six more ran on a
second, synthetic project, in two rounds of three chosen by a second model.

## What was built

Before the week: the step schema, the cross-step checker, `facts`, `head` and `verify`, three
worked example trails, and the graph export in [GRAPH.md](GRAPH.md).

Built during the week, as planned:

1. **The reviewer view.** One self-contained page that leads with the decision path and answers
   the step-4 question on one screen, and `trail.py why`, which answers it in text. It is what a
   judge reads.
2. **Capture.** A Pi extension that writes steps as the work happens: plans enter only through a
   `propose_plan` tool, runs are written before they execute, and measures are read from the
   metrics file the run wrote.
3. **A live task.** A re-analysis of an inherited script with a known pitfall, run end to end:
   the agent reproduces the headline number, finds that it does not hold on held-out data, and
   changes approach. The tamper demonstration runs on its trail.
4. **The evidence** above.

Built during the week, beyond the plan:

5. **Traced reads.** Each command runs under a file trace, and `retrace.py` re-executes past
   trails the same way, so opening a held-out file is recorded, not judged from the code.
6. **A research map.** Many trails toward shared goals ([research/](../research/README.md)).
   `project.py check` recomputes every credit from the step files, follows what each credit rests
   on across trails, and records every withdrawal with its reason.
7. **Agents sharing a map.** Up to three agents run at once, read each other's progress through
   one tool, and build on each other's steps. Numbers from a held-out file are withheld, what one
   agent wrote reaches another marked as text and not instructions, and each command runs in a
   sandbox that hides the map and the other trails.
8. **Beliefs over the map, and a second model as forecaster** ([spec 10](specs/10-beliefs.md),
   [spec 11](specs/11-beliefs-review.md)). `beliefs.py` says how far each ✓ and ✗ stood from its
   threshold, in declared standard errors: every one at the held-out floor is within noise. A
   second model forecasts milestones from their Markov blanket and plans from their trail. Code
   builds the text, marks a question whose outcome was already known, and scores the rest against
   code-only forecasters, each difference with its error. On the real forecasts the model did
   worse than a coin flip, and the run made to settle its open forecasts settled none. The marks
   never change.
9. **A second research project, overseen by a second model** ([spec 12](specs/12-second-project.md)).
   Synthetic data with a replication sample give each credited analysis its true value. Kimi K3.1
   Pro forecast every open milestone and chose the routes before each round, pushed before the
   agents started. The agents read each other's results and every route cleared the floor. Kimi
   was within noise of a coin flip; the blanket's code forecaster, given sibling scores far from
   the floor, beat it.

One task type, one agent host, one model. Left out, and said so: redaction and keyed digests for
hidden values in capture, signing by the capture host, resuming a trail in a second session,
PROV-O export and the Almanaque port. The sandbox hides named places and does not close the
network, and a single run is not sandboxed unless asked.

## Relation to the other tasks, and to Almanaque

Task 2 is the entry. A trail is the evidence chain a claim-to-evidence linker (Task 3) would
trace a result back through, and the `task` step's question is where an ideation stress-test
(Task 1) verdict would attach. Neither is built here.

Almanaque is downstream. A trail is produced by capture outside any consumer, and anything
reading it imports it with a preview (rule 4 in DESIGN.md). The
[port to Almanaque](GRAPH.md#port-to-almanaque) would make a trail a tier-3 probe in Almanaque's
organisation graph, cited at its head. The entry stands alone: a reviewer with `trail.py` and
the view needs nothing else.

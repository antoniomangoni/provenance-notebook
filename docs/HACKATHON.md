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
  held only after earlier runs contradicted it, an exact repeat, a run that never settled, and
  (planned this week) a replacement plan that lowers the bar the first one missed.
- **A citation of a trail is stable.** Each step holds the hash of the one before, and a trail
  is cited at the hash of its last step. A trail rewritten and re-chained still checks, but it no
  longer has the head it was cited at.

### What it costs the researcher

One file before the task: the question, the measures the run will report, and which parameter
names may be shown. The task's own script writes its numbers to `out/metrics.json`. The agent is
started with one command. After that the researcher writes nothing, apart from any review.

The step format does not depend on the agent. One adapter is built, for the Pi coding agent.

### What it does not prove

The chain proves order and that nothing was changed after a head was cited. It does not prove
who wrote a step. That rests on the capture host, which alone writes runs and observations and
must be outside the agent's reach. A researcher who controls that host can still fabricate a
trail from the start; what they cannot do is revise one that has been cited. The plan's reasoning
is the agent's own statement, which is why its links are marked `suggested`.

## How it will be evaluated

The brief's criterion can be checked, so the entry checks it three ways.
[PLAN.md](../PLAN.md#evidence) has the questions and the protocol.

- `trail.py why TRAIL STEP` prints the answer to the brief's question from the links alone, and
  a test pins it on the worked example.
- A model that has not seen the task answers four fixed questions, once from the generated view
  and once from what a reviewer has today, the agent's raw session transcript and the git log.
  The answers are graded against a key taken from the step files.
- A person who did not see the task answers the brief's question from the view, in the video.

Every live attempt at the task is committed, and the write-up says how many there were.

## What exists, and what the week is for

Exists and tested: the step schema, the cross-step checker, `facts`, `head` and `verify`, three
worked example trails, and the graph export in [GRAPH.md](GRAPH.md).

Built during the week:

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

One task type, one agent, one runner. Left out of the week, and said so: redaction and keyed
digests for hidden values, the read-only sandbox around the trail, multi-trail merge in the demo,
PROV-O export and the Almanaque port.

## Relation to the other tasks, and to Almanaque

Task 2 is the entry. A trail is the evidence chain a claim-to-evidence linker (Task 3) would
trace a result back through, and the `task` step's question is where an ideation stress-test
(Task 1) verdict would attach. Neither is built here.

Almanaque is downstream. A trail is produced by capture outside any consumer, and anything
reading it imports it with a preview (rule 4 in DESIGN.md). The
[port to Almanaque](GRAPH.md#port-to-almanaque-g4) makes a trail a tier-3 probe in Almanaque's
organisation graph, cited at its head. The entry stands alone: a reviewer with `trail.py` and
the view needs nothing else.

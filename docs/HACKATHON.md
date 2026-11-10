# Hackathon context: Challenge 02, provenance-preserving lab notebook

This brainstorming is a candidate entry for the [AI for Meta-Science
Hackathon](https://ai4metascience-hackathon.stockholm.ai/) (Stockholm AI, the AI for
Meta-Science NeurIPS Workshop and Sweden AI Factory): Stockholm, 10–17 November 2026,
kick-off 10 Nov 17:30 at RISE KTH, submission deadline 17 Nov 18:00 CET. The winner is
announced 24 Nov and presents a poster and oral at the AI for Meta-Science workshop,
NeurIPS 2026, Paris, 9–13 December.

## The challenge it answers

02, "Keep the research trail intact": when AI tools rapidly iterate on a research task,
the trail — why a method was chosen, what was abandoned, which code produced which
result — can disappear, eroding accountability and reproducibility. The brief asks for
a lightweight logging or wrapper tool around a single AI-assisted research task that
automatically captures:

- each proposed plan or hypothesis and the reasoning behind it;
- what was actually run, including code, parameters and data versions;
- what failed or contradicted expectations, and how the plan changed in response;
- a timeline a human can follow to reconstruct the actual decision path.

Success looks like: a reviewer who wasn't present can inspect the log and answer
"Why did they change approach at step 4?" without asking the researcher.

## How this design maps to it

The step schema in [DESIGN.md](DESIGN.md) is the capture format; `trail.py` is its
checker and graph export. The mapping is direct:

| Brief | Here |
| --- | --- |
| plan and reasoning | `plan` steps: reasoning plus expectations (measure, comparison, threshold) stated before the run |
| what was actually run | `run` steps, written before execution: command and code commit, environment and input digests, parameters; the observation settles it with exit code and output digests |
| failure and contradiction | `observation` steps: measures read from the metrics file the run wrote, checked against the plan's expectations, with the outcome recomputed by the checker, not claimed; a run that never finished stays as unsettled |
| plan changed in response | a new `plan` that `supersedes` the old one and is `triggered_by` the observation that contradicted it |
| human-followable timeline | the append-only, hash-chained `steps/step-N.json` sequence, plus the exported node/edge graph |

The worked example already stages the brief's test: in `examples/churn-model-2026-11-11`
the step-4 plan change reads off its links — the observation it was triggered by (step 3:
AUC 0.58 against a 0.75 floor), the plan it supersedes, and the human review that
confirmed it.

Three properties go beyond a plain log, and are the pitch:

- **Tamper-evident, not just append-only.** Each step hashes the previous one, and
  outside citations pin the trail at a head digest; a trail rewritten and re-chained
  still checks internally but no longer matches the head it was cited at.
- **Outcomes are recomputed, not asserted.** The checker re-derives each check from
  the measures and the outcome from the checks, and the measures are re-read from the
  digested metrics file the run wrote. The agent cannot grade its own run, provided
  the capture host, which alone writes runs and observations, is outside its reach:
  that host is the trust root.
- **No values by default.** Parameters, inputs and outputs are digests (keyed where a
  plain hash would be guessable), so a trail can be shared with a reviewer without
  leaking the data or secrets behind it.

## Where it sits among the three challenges

02 is the entry. The neighbouring challenges are consumers, not scope: a trail is
exactly the evidence chain a claim-to-evidence linker (03) would trace a result back
through, and the `task` step's question is where an ideation stress-test (01) verdict
would attach. Building either is out of scope for the week; citing a trail from
outside, at a pinned head, is already in the design.

## What exists, and what the seven days are for

Exists: the schema (`step.schema.json`), the cross-step checker, graph and multi-probe
merge export (`trail.py check|facts|graph|merge`), three worked example trails (the
third re-runs one plan until it holds, for `facts` to show), and a PROV-O mapping. That is the format and its guarantees, proven on hand-written examples.

Not yet built — this is the hackathon work:

1. **Capture.** The wrapper or hooks around one real AI-assisted task that write steps
   as the work happens: a Pi extension, with plans entering only through a
   `propose_plan` tool, runs written before they execute, and measures read from
   `out/metrics.json`.
2. **A reviewer view.** A human-readable timeline that answers the step-4 question in
   one screen: plan, run, observation, superseding plan, review. The graph export is
   the data; the view is what a judge actually reads.
3. **A live demo task.** One small, real task (the churn examples are the rehearsal)
   run end to end through the wrapper, including a genuine failure and change of
   approach — plus the negative demo: edit a past step and show the cited head no
   longer matching.

Scope discipline for the week: one task type, one agent, one runner. Multi-probe
merge, PROV-O export and the Almanaque port below are already-designed stretch, not
submission requirements.

## Relation to Almanaque

Deliberately downstream. The trail is produced by capture outside any consumer, and
anything reading it imports it with a preview (rule 4 in DESIGN.md); the
[port to Almanaque](DESIGN.md#port-to-almanaque-g4) makes a trail a tier-3 probe in
Almanaque's organisation graph, cited at its head. The hackathon build must stand
alone — a reviewer with `trail.py` and the timeline needs nothing else — with
Almanaque as evidence the format has a home after the week, not as a dependency
during it.

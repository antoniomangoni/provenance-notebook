# Plan for the hackathon week, 10–17 November 2026

The entry answers Task 2 of the AI for Meta-Science Hackathon: a provenance-preserving lab
notebook for AI-assisted work. [docs/HACKATHON.md](docs/HACKATHON.md) maps the brief to the
design, and [docs/DESIGN.md](docs/DESIGN.md) is the specification. This file is the schedule.

Submission closes **Tuesday 17 November, 18:00 CET**.

## What the brief is judged on

A reviewer who was not present opens the log and answers "why did they change approach at
step 4?" without asking the researcher. Everything below serves that one test.

## Milestones

A milestone is done when its check passes, not when its code is written.

| When | Milestone | Done when | State |
| --- | --- | --- | --- |
| Tue 10 | **M0 Repository.** The design under version control, with tests | `uv run pytest` passes: the examples regenerate byte for byte and check against their stored metrics, an edited step breaks the chain, and a re-chained trail fails `verify` against the head it was cited at | done |
| Tue 10, kick-off | Learn the submission format, judging criteria, team and prior-work rules | Recorded under [Decisions](#decisions); this plan adjusted if the deliverable differs | open |
| Wed 11 – Thu 12 | **M1 Capture.** `capture/capture.ts` writes real steps as Pi works | An offline run on the scripted provider produces a trail that passes `trail.py check --store`, and a test covers every row of the capture table in the design | |
| Fri 13 | **M2 Reviewer view.** `trail.py view DIR` writes one self-contained HTML timeline | On the churn example, the step-4 card shows its reasoning, the observation that triggered it with numbers against thresholds, the plan it supersedes and the review, on one screen, beside the facts and the head digest | |
| Sat 14 | **M3 Live task.** One real task through Pi with a real model | A trail from an unscripted run holds at least one contradicted observation and a superseding plan; a human review step is appended; `check --store` passes | |
| Sun 15 | **M4 Proof.** The tamper demonstration and a blind read | Editing a past step fails `check`; re-chaining it passes `check` and fails `verify`. One person who was not present answers the step-4 question from the view alone | |
| Mon 16 | **M5 Write-up.** README, the pitch, a recorded run-through | A stranger clones the repository, runs one command and sees the demo trail and its view | |
| Tue 17 | Buffer, then submit by 18:00 | Submitted | |

### M1: what capture does

`capture/probe.ts` is the spike that proved each assumption against Pi 0.84.1. `capture.ts`
replaces its stubs with the behaviour the design's capture table specifies.

- **Task.** Step 0 comes from `demo/task.json` (question, project, declared measures, public
  parameters) at `session_start`, with the agent's identity from the session.
- **Plans.** `propose_plan` takes a summary, reasoning, expectations and optional `supersedes`
  and `triggered_by`. It runs sequentially, refuses an undeclared measure, and refuses a
  replacement plan that names no observation. A `bash` call with no open plan is blocked.
- **Runs.** Written before the command executes: the redacted command and its digest, the git
  commit and dirty-diff digest, the environment digest, the parameters parsed from
  `--name value` flags, and digests of the declared input files.
- **Observations.** `bash` runs through a wrapper that keeps the exit code, duration and output
  size, with the trail mounted read-only. Afterwards `out/metrics.json` is copied to the
  content-addressed store, the measures are read from it, and checks and outcome are computed by
  the same rules as the checker.
- **Guards.** `write` and `edit` are blocked on the trail's real path. A run or token budget
  stops the agent and leaves a runner note. The ledger shown to the agent is rebuilt from the
  steps every turn.

### Additions to `trail.py`

- `head` and `verify` (done in M0).
- `review TRAIL STEP --verdict … --text …` and `note`, the only way a human step enters. Both
  chain from the current head.
- `view TRAIL`, the HTML timeline, built from the existing `load`, `check`, `facts` and `graph`.
  No server and no external assets.

## Cut line

In scope: one task type, one agent, one runner.

If time runs short, cut in this order:

1. the recorded run-through;
2. the read-only mount (keep path blocking, and say so in the write-up);
3. parameter parsing beyond `--name value`.

Never cut: runs written before they execute, measures read from the metrics file, the view, and
the live trail.

Out of scope this week: multi-probe merge in the demo, PROV-O export, the Almanaque port, and
signing by the capture host, which stays an open question with the host named as the trust root.

## Risks

- **The submission format is unknown.** The site gives only the deadline. M5 assumes a
  repository and a short write-up.
- **The live model may not call tools reliably.** Try the real model with the real extension on
  Wednesday, not Saturday. Keep a second provider key as a fallback.
- **The demo task may not fail by itself.** Pick a task whose naive first approach falls short
  of a floor that `task.json` fixes before the run, as the churn rehearsal does. The failure has
  to be real.

## Working rules

- Commit to `main`. Run `uv run pytest` and `uv run ruff check` before each commit.
- A step-format change updates `step.schema.json`, `trail.py`, `capture/` and the design
  together, and regenerates `examples/`.
- The committed examples are fixtures: change them only through `trail.py examples examples`.

## Decisions

| Date | Decision |
| --- | --- |
| 10 Nov | A repository of its own, apart from Almanaque. The entry has to stand alone, and Almanaque stays a downstream consumer |
| 10 Nov | Local git only until the submission rules are known. Remote, visibility and licence are decided after kick-off |
| 10 Nov | Pi 0.84.1 is the one agent, pinned in `capture/package.json` |

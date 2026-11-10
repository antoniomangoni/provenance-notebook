# Plan for the hackathon week, 10–17 November 2026

The entry answers Task 2 of the AI for Meta-Science Hackathon: a provenance-preserving lab
notebook for AI-assisted work. [docs/HACKATHON.md](docs/HACKATHON.md) is the pitch and maps the
brief to the design, and [docs/DESIGN.md](docs/DESIGN.md) is the specification. This file is the
schedule.

Submission closes **Tuesday 17 November, 18:00 CET**.

## What the brief is judged on

A reviewer who was not present opens the log and answers "why did they change approach at
step 4?" without asking the researcher. Two things follow, and they order the week:

- the reviewer's view is the product, so it is built first and improved all week;
- the criterion is a measurement, so the entry measures it with a [reader study](#reader-study).

## Milestones

A milestone is done when its check passes, not when its code is written.

| When | Milestone | Done when | State |
| --- | --- | --- | --- |
| Tue 10 | **M0 Repository.** The design under version control, with tests | `uv run pytest` passes | done |
| Tue 10, kick-off | The [kick-off questions](#kick-off-questions) | Answers recorded under [Decisions](#decisions); this plan adjusted if the deliverable differs | open |
| Wed 11 | **M1 View.** `trail.py view DIR` writes one self-contained HTML page | On the churn example, one screen answers the step-4 question: the reasoning, the observation that triggered the change with its numbers against thresholds, the plan it supersedes and the review | |
| Wed 11 | Demo task chosen; real model smoke-tested | [The task](#the-demo-task) meets its conditions; the model calls `propose_plan` through the spike extension | |
| Thu 12 – Fri 13 | **M2 Capture.** `capture/capture.ts` writes real steps as Pi works | An offline run on the scripted provider passes `trail.py check --store`, with a test for each item under [what capture does](#m2-what-capture-does) | |
| Sat 14 | **M3 Live task.** One real task through Pi with a real model | The trail holds a contradicted observation and a superseding plan; a human review is appended; `check --store` passes; the view and `facts` read cleanly despite exploratory commands | |
| Sun 15 | **M4 Evidence.** The reader study and the tamper demonstration | Three or more readers, answers and minutes recorded for view and baseline. Editing a past step fails `check`; re-chaining it passes `check` and fails `verify` | |
| Mon 16 | **M5 Write-up.** The study's table, a figure of the timeline, the pitch | The live trail and its view are committed, and a stranger sees the demo from one link | |
| Tue 17 | Buffer, then submit by 18:00 | Submitted | |

### M1: the view

Built from the existing `load`, `check`, `facts` and `heads`. No server and no external assets,
so the page can be committed and opened from a link.

- It leads with the decision path: each change of approach as one sentence, with its step.
- A change-of-approach card shows the old plan, the observation that contradicted it with
  measured values against thresholds, the new plan's reasoning and any review.
- Runs that wrote no metrics are collapsed into a count ("12 exploratory commands"), and open on
  request.
- Consecutive runs show the code that changed between them, from their snapshot commits.
- The facts and the head digest sit beside the timeline.

### M2: what capture does

`capture/probe.ts` is the spike that proved each assumption against Pi 0.84.1. `capture.ts`
replaces its stubs. Each item has a test on the scripted provider.

- **Task.** Step 0 comes from `demo/task.json` (question, project, declared measures, public
  parameters) at `session_start`, with the agent's identity from the session.
- **Plans.** `propose_plan` takes a summary, reasoning, expectations and optional `supersedes`
  and `triggered_by`. It runs sequentially, refuses an undeclared measure, and refuses a
  replacement plan that names no observation. A `bash` call with no open plan is blocked.
- **Runs.** Written before the command executes: the command and its digest, the code, the
  environment digest, the parameters parsed from `--name value` flags, and digests of the
  declared input files.
- **Code snapshots.** Before each run the working tree is committed to a side ref, and the run
  cites that commit. An agent edits files between runs without committing, and a digest of a
  dirty diff would leave "which code produced which result" unreadable.
- **Observations.** `bash` runs through a wrapper that keeps the exit code, duration and output
  size. The measures are read from `out/metrics.json`, which is copied to the content-addressed
  store, and checks and outcome are computed by the same rules as the checker.
- **Fresh metrics only.** A metrics file counts only if this run wrote it. Without that rule an
  `ls` after an experiment would be settled with the experiment's numbers.
- **Guards.** `write` and `edit` are blocked on the trail's real path.

Two changes to `trail.py` go with it:

- `facts` counts a plan's attempts only among runs that wrote metrics, so exploratory commands
  do not read as "14 runs".
- `facts` reports a moved goalpost: a superseding plan whose threshold on the same measure is
  easier than the one the triggering observation missed.

Also added: `review TRAIL STEP --verdict … --text …` and `note`, the only way a human step
enters. Both chain from the current head.

### The demo task

A small re-analysis of a public dataset with a known pitfall (leakage, class imbalance or a
confound), not generic model tuning: the audience should recognise it as research. Conditions:

- the floor is fixed in `task.json` before the run;
- the naive first approach honestly falls short of it, so the failure is real;
- one run takes under a minute, and the whole task fits the compute credit;
- every parameter is public, so the reviewer reads values, not digests.

The churn examples remain the rehearsal and the test fixtures.

### Reader study

- **Readers.** Three to five people who did not see the task run.
- **Material.** The live trail, presented two ways: the generated view, and the baseline a
  reviewer has today, Pi's raw session transcript plus the git log.
- **Questions**, fixed before the live run, each with an answer key taken from the step files:
  1. Why did the approach change, and at which step?
  2. Which code and parameters produced the final result?
  3. How many attempts did the final plan take before it held?
  4. What was tried and abandoned?
- **Design.** Each reader answers from one presentation first, then the other; alternate which
  comes first. Stop a reader at ten minutes per presentation.
- **Recorded.** Per reader and presentation: correct answers out of four, and minutes.
- **Reported.** The table as measured, with the number of readers, and what readers said was
  missing. No claim beyond what three to five readers can support.

### Kick-off questions

1. What is submitted, and where: a repository, a write-up, a video? Is there a template or a
   length limit?
2. What are the judging criteria?
3. Is work done before 10 November allowed? The schema, checker and examples predate it, and
   the first commit says so.
4. Team size, and whether a solo entry is accepted.
5. Must the repository be public, and under which licence?
6. What the Berget AI credit covers, and which models support tool calling.

## Cut line

In scope: one task type, one agent, one runner.

Already cut for the week, and named in the pitch: the redactor, keyed digests for hidden values,
the read-only mount around the trail, the token budget and the ledger shown to the agent.

If time still runs short, cut in this order:

1. code diffs in the view (keep the snapshot commits);
2. parameter parsing beyond `--name value`;
3. the second presentation order in the reader study.

Never cut: the view, runs written before they execute, measures read from a fresh metrics file,
the live trail, and at least three readers.

Out of scope: multi-trail merge in the demo, PROV-O export, the Almanaque port, and signing by
the capture host, which stays an open question with the host named as the trust root.

## Risks

- **The submission format is unknown.** The site gives only the deadline. M5 assumes a
  repository and a short write-up.
- **The live model may not call tools reliably.** That is why the smoke test is on Wednesday.
  Keep a second provider key as a fallback.
- **The demo task may not fail by itself.** The conditions above exist for this; test the naive
  approach by hand on Wednesday before committing to the task.
- **Readers are hard to find on a Sunday.** Ask at kick-off and line them up by Thursday.

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
| 10 Nov | The view comes before capture, and the entry reports a reader study. Privacy features and the sandbox are cut for the week |

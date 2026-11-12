# Roadmap to submission, 13–17 November 2026

The entry answers Task 2 of the AI for Meta-Science Hackathon: a provenance-preserving lab
notebook for AI-assisted work. [docs/HACKATHON.md](docs/HACKATHON.md) is the pitch and maps the
brief to the design, and [docs/DESIGN.md](docs/DESIGN.md) is the specification. This file is the
roadmap: what is built, in which order, by whom, and how each piece is known to be done.

Submission closes **Tuesday 17 November, 18:00 CET**. The entry is submitted by 15:00. The
submission includes a video or a demo.

## What the brief is judged on

A reviewer who was not present opens the log and answers "why did they change approach at
step 4?" without asking the researcher. Two things follow:

- the reviewer's view is the product, and it is what the video shows;
- the criterion can be checked, so the entry checks it ([Evidence](#evidence)).

## State on 12 November

The step schema, the checker, `facts`, `head`, `verify`, three example trails and the graph
export exist, with 15 passing tests. `capture/probe.ts` proved the capture assumptions against
Pi 0.84.1. Not started: the view, capture, the demo task, the real-model test.

## Slices

A slice is done when its check passes, not when its code is written. Slices 1 to 3 share no
files and are built at the same time.

| When | Slice | Built by | Done when | State |
| --- | --- | --- | --- | --- |
| Thu 12 | **R0 Roadmap.** This file, [AGENTS.md](AGENTS.md), CI, specs 1 to 3 | a session | `uv run pytest` passes; each spec has every section of the [meta-spec](docs/meta-spec.md) | done |
| Fri 13 | **Smoke test.** A real model drives `capture/probe.ts` | a person | The model calls `propose_plan`, then `bash`, and `trail.py check` passes on what the probe wrote | |
| Fri 13 | **1 Reviewer view.** [Spec](docs/specs/01-reviewer-view.md): `why`, `view`, two new facts, `review` and `note` | an agent | Tests assert that `why` and the page give step 4's trigger, 0.58 against 0.75, the plan it replaced and its review; the page loads nothing external | |
| Fri 13 | **2 Capture.** [Spec](docs/specs/02-capture.md): `capture/capture.ts` and `scripts/live.sh` | an agent | A scripted run passes `check --store`; a later `ls` is not settled with earlier numbers; a replacement plan is accepted with an id taken from a receipt | |
| Fri 13 | **3 Demo task.** [Spec](docs/specs/03-demo-task.md): `demo/` | an agent | A test shows the inherited analysis missing the floor and a corrected one meeting it, each in under a minute | |
| Sat 14 | **Live run.** The demo task through Pi with a real model, on merged slices 1 to 3 | a person; defects go to agents | A trail under `live/` holds a contradicted observation and a replacement plan, passes `check --store`, and `why` answers for the replacement | |
| Sun 15 | **4 Evidence.** Spec written from the live trail: the reader check, the tamper sequence, fixes to the view | an agent and a person | The reader check prints its table; editing a past step fails `check`; re-chaining it passes `check` and fails `verify` | |
| Mon 16 | **Submission.** `README.md` as the landing page, the write-up, the video, the published view, licence and visibility | a person and an agent | A stranger sees the live trail's view from one link; the video is under three minutes | |
| Tue 17 | Buffer; submit by 15:00 | a person | Submitted | |

### How a slice is built

1. A spec in `docs/specs/`, written to [docs/meta-spec.md](docs/meta-spec.md), is merged to
   `main` before any code.
2. One agent works one spec on one branch, `spec/NN-name`, and edits only the spec's target
   files. [AGENTS.md](AGENTS.md) has the rules every agent follows.
3. A deviation is written into the spec first, in the same pull request.
4. The branch merges by pull request once CI is green and the spec's rejection criteria have
   been read against the diff.

### Interfaces the slices share

These are fixed. A slice that needs one changed stops and asks.

- **The step format.** `step.schema.json` and the rules in `trail.check`. No slice changes them.
- **The task file.** `task.json` holds `summary`, `question`, `project`, `declared_measures`,
  `public_parameters`, `inputs` (file paths relative to the workspace) and `by` (`human:NAME`).
  Capture writes step 0 from it.
- **The metrics file.** A run reports its numbers by writing `out/metrics.json` in the
  workspace: one object of measure names to numbers.
- **A demo directory.** `task.json`, `prompt.md` and `workspace/`, the files the agent starts
  from. `workspace/` is a `uv` project with its own lock file.
- **The launcher.** `scripts/live.sh DEMO_DIR NAME [pi options]` copies the workspace to a new
  git repository outside this one, runs Pi there with capture loaded, and leaves:

  | Path | Contents |
  | --- | --- |
  | `live/NAME/steps/step-N.json` | the trail, named `NAME` |
  | `live/store/` | metrics files by digest, shared by all live trails |
  | `live/NAME/code.bundle` | a git bundle of the code snapshots, one branch |
  | `live/NAME/session/` and `live/NAME/events.jsonl` | Pi's own transcript: what a reviewer has today |

- **Code for the view.** `trail.py view DIR --code REPO` reads snapshot commits from a git
  repository, which `git clone live/NAME/code.bundle` produces.

### Only a person can do these

- Run the smoke test. It needs nothing that is not already in the repository, so it comes
  first. Pi's model file on the development machine holds Berget and Anthropic entries from
  September: confirm the keys with `capture/node_modules/.bin/pi --list-models`, then try
  GLM-5.2 on Berget, then Haiku 4.5 on Anthropic. Run with `--thinking off` and note whether
  reasoning text still appears.
- Run the live task on Saturday and decide which defects are worth fixing.
- Ask the organisers the [open questions](#open-questions-for-the-organisers) on Friday.
- Find one person who has not seen the task and record them answering the step question.
- Record the video, choose the licence and make the view reachable from one link.
- Merge pull requests.

## Gates

| When | If | Then |
| --- | --- | --- |
| Fri 13, evening | the Berget model does not call the tools in order | use a Claude model through Pi's Anthropic entry from Saturday. Capture does not change |
| Sat 14, 14:00 | no live trail has a replacement plan | switch model the same way |
| Sat 14, 20:00 | still none | revise `demo/prompt.md` and run again, keeping every attempt |
| Sun 15, 18:00 | code diffs in the view or parameter parsing are unfinished | cut them |
| Mon 16, 20:00 | the repository cannot be public | attach the view and the video to the submission |

## Evidence

The brief's criterion is checked in three ways, in this order of priority.

1. **`trail.py why TRAIL STEP`** prints the answer to the brief's question from the links alone:
   the plan that was replaced, the observation that contradicted it with the measured value
   against the threshold, the new plan's reasoning and any review. A test pins it on the churn
   example. It works for any step, so it works on a live trail whose change is not at step 4.
2. **A reader check.** A model that has not seen the task answers four questions, once from the
   view's text and once from what a reviewer has today, Pi's transcript and the git log. The
   answers are graded against a key of step ids and numbers taken from the step files. The
   script, the questions, the key and the table are committed.
   1. Why did the approach change, and at which step?
   2. Which code and parameters produced the final result?
   3. How many attempts did the final plan take before it held?
   4. What was tried and abandoned?
3. **One cold reader.** A person who did not see the task answers question 1 from the view, and
   the video shows it.

Stretch: three human readers, asked by link. Each reads one presentation only, so no answer is
learned from the other. Report the table as measured, with the number of readers.

The questions are fixed before the live run. Every live attempt is committed under `live/`, and
the write-up says how many there were: an entry about forking paths shows its own.

## The demo task

A re-analysis of an inherited script that has a known pitfall, on a public dataset. The agent
reproduces the script's headline number, then tests it on data held out before anything was
fitted. The failure belongs to the inherited analysis, so it does not depend on the model making
a mistake, and a test can show it without a model. Conditions:

- the floor is fixed in `task.json` before any run, as the headline number less a stated margin;
- the inherited analysis misses it by a clear distance, and a corrected analysis is consistent;
- one run takes under a minute, and the whole task fits the compute credit;
- every parameter is public, so the reviewer reads values, not digests.

The churn examples remain the test fixtures.

## The agent host

Capture runs inside the Pi coding agent, pinned at 0.84.1. An adapter needs five things from a
host, and the probe checked each on Pi
([the table](docs/DESIGN.md#capture-host-checked-at-pi-0841)):

- a hook that is awaited before a command runs and can stop it, failing closed;
- a tool the adapter defines and can refuse from;
- the command's exit code;
- a way to add a line to the result the model reads;
- an unattended mode, with a scripted provider so that tests need no key.

Pi also reaches Berget's models and Anthropic's with one configuration file, so the model can
change while capture stays the same. Considered and not taken this week:

| Alternative | Why not |
| --- | --- |
| Claude Code hooks, with an MCP server for `propose_plan` | It is the agent more researchers use, but none of the five is probed there, its tests would need a mock API, and it cannot use the Berget credit |
| An MCP server alone, for any agent | The agent's own shell goes around it, so a run would be recorded only when the agent chose to |
| A loop of our own | We would own retries, malformed calls and outages, and it is a weaker answer to "a wrapper around an AI-assisted task" |
| Pi 0.87.1 | It adds nothing capture needs, and the extension interface changed |

Spec 2 keeps step construction apart from the Pi hooks, so a second adapter is new wiring.

## Cut line

In scope: one task type, one agent, one runner.

Cut for the week, and named in the pitch: the redactor, keyed digests for hidden values, the
read-only mount around the trail and the ledger shown to the agent. The agent learns step ids
from a receipt line on each command's result instead. A ceiling on runs and tokens and a wall
clock on the launcher stay in, because one looping run can spend a fifth of the credit.

If time runs short, cut in this order:

1. code diffs in the view (keep the snapshot commits);
2. parameter parsing beyond `--name value`;
3. the human readers beyond the one in the video;
4. the moved-goalposts fact.

Never cut: the view, `why`, runs written before they execute, measures read from a fresh
metrics file, a live trail, the video.

Out of scope: multi-trail merge in the demo, PROV-O export, the Almanaque port, and signing by
the capture host, which stays an open question with the host named as the trust root.

## Risks

- **The live model may not call tools reliably.** The smoke test is first for that reason. In
  September, on another task under the same Pi version, GLM-5.2 on Berget failed 37 of 99 runs
  and Qwen3.8-27B 13 of 23, mostly in tool loops, and Haiku 4.5 on Anthropic ran 6 of 6. The
  rates do not carry over to this task; the failure modes do. Anthropic is the fallback.
- **A loop is expensive.** Berget bills cached input at the full rate, so cost grows with the
  square of the calls: one looping run cost EUR 10.76, against EUR 50 of credit. Capture stops
  at a ceiling on runs and tokens, and the launcher at a wall clock.
- **Berget may fail or slow down.** September saw 500 and 503 outages that Pi's retry did not
  survive, and throughput that varied about three times by hour. A failed attempt is kept and
  run again later, or on the fallback.
- **Thinking may not switch off on Berget.** Only `chat_template_kwargs` reached the model
  there. If the smoke test shows reasoning with `--thinking off`, a person ports the September
  hook as `capture/thinking.ts`, loaded with a second `-e`.
- **The agent may never replace a plan.** The demo task makes the contradiction certain; whether
  the agent then records a replacement depends on the protocol text and the receipts. The
  scripted test covers the mechanics, Saturday's gates the behaviour.
- **The pitfall may not bite on the chosen data.** Spec 3 chooses the dataset by measurement and
  has a second pitfall to fall back on.
- **Three agents may collide.** Target files are disjoint by spec, and the shared documents
  (`README.md`, this file, `docs/HACKATHON.md`) are edited only in the submission slice.
- **The trail is not protected from the agent's shell.** `write` and `edit` are blocked on the
  trail's path, `bash` is not. The pitch says so.

## Open questions for the organisers

1. Is work done before 10 November allowed? The schema, checker and examples predate it, and
   the first commit says so. The write-up discloses it either way.
2. Must the repository be public, and under which licence?
3. What are the judging criteria, and is there a length limit for the video and the write-up?
4. Which Berget model do they recommend for tool calling? GLM-5.2 and Qwen3.8-27B called tools
   in September.

## Decisions

| Date | Decision |
| --- | --- |
| 10 Nov | A repository of its own, apart from Almanaque. The entry has to stand alone, and Almanaque stays a downstream consumer |
| 10 Nov | Pi 0.84.1 is the one agent, pinned in `capture/package.json` |
| 10 Nov | The view comes before capture. Privacy features and the sandbox are cut for the week |
| 10 Nov | From kick-off: the submission includes a video or a demo |
| 12 Nov | Built from specs by agents, one branch and pull request per spec, on a private GitHub remote. Visibility and licence are decided by Monday |
| 12 Nov | Slices 1 to 3 are built in parallel; the view's code lives in `view.py` so that `trail.py` has one owner |
| 12 Nov | The reader study is replaced by `why`, a reader check by a model, and one cold reader in the video. Human readers are a stretch |
| 12 Nov | The demo task is a re-analysis of an inherited script, so its failure does not depend on the model |
| 12 Nov | Every live attempt is committed |
| 12 Nov | Pi stays the host, after weighing Claude Code hooks, an MCP server alone, a loop of our own and Pi 0.87.1. The model is the larger risk, so the budget stop returns to capture and Anthropic is the named fallback |

# Submission text and video plan

Text to paste into the submission form, and a shot list for the video. Every number here is in
the repository; the file that holds it is named beside it.

## Title

Provenance notebook: a checked trail of an AI-assisted research task

## One sentence

A record written around an AI agent, not by it, from which a reviewer who was not there can read
why the plan changed, check that the numbers are the ones the runs wrote, and see which runs had
opened the held-out data first.

## Short description (about 100 words)

When an AI agent iterates on a research task, the reasons disappear. The provenance notebook
wraps the agent and writes a trail of small, hash-chained step files: each plan with the result it
expects, each run before it executes, and each observation with numbers read from the file the
run wrote. Outcomes are recomputed by a checker, never claimed by the agent. One command answers
"why did they change approach at step N?" from the links alone, and one page shows the decision
path, the code behind each result, and every run that opened a held-out file. A trail is cited by
the hash of its last step, so a rewritten one no longer matches.

## Long description (about 300 words)

**What it is.** A step format and a checker (`trail.py`), an extension for the Pi coding agent
that writes steps from hooks around the agent's tools (`capture/`), a reviewer's page generated
from a trail (`view.py`), and a research map over many trails (`project.py`).

**How it answers the brief.**
- *Plans and reasoning:* a plan enters only through a tool, and must state a measure and a
  threshold before anything runs.
- *What was run:* a run step is written before its command starts, with the command, a snapshot
  commit of the code, the environment digest and the input digests.
- *What failed, and how the plan changed:* outcomes are computed from a metrics file the run
  wrote. A replacement plan links to the plan it supersedes and the observation that triggered it.
- *A timeline to walk back through:* the reviewer's page, and `trail.py why TRAIL STEP`.

**What was run.** Twelve live trails by one model on one constructed task, all committed,
including the ones that reached nothing. On the first, the plan changes at step 14 after a
held-out AUC of 0.5639 against a floor of 0.71, and `why` says so.

**What was measured.**
- A forged number is caught by the chain, then by the stored metrics file, and a complete
  rewrite only by a head cited beforehand (`evidence/…/tamper.txt`).
- A reader check with three models: they answered the fixed questions as well from the agent's
  raw transcript as from the page. The page's measured advantage is its length, a tenth of the
  transcript's (`evidence/README.md`).
- Re-executing five trails under a file trace reproduced 17 of 17 metrics files byte for byte,
  and showed that two results judged "pilot-only" had opened the held-out file. Both credits
  were withdrawn, and the withdrawal is recorded (`research/madelon-reanalysis/README.md`).

**What it does not prove.** Who wrote a step, what a read was used for, or that a run used the
method it claims. The README lists each limit.

**Disclosure.** The step schema, checker and three example trails predate 10 November. The code
was written by AI coding agents from specs in `docs/specs/`.

## Links

- Repository: `https://github.com/OWNER/provenance-notebook`
- Pages, once published: the reviewer's page of the live trail, and the research map
- Start at `README.md`

## Video, under three minutes

One take of a browser and a terminal. Build the pages first with `scripts/site.sh site`, and
start `uv run python project.py serve research/madelon-reanalysis/map --live live`.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00 | `site/index.html` | When an agent iterates on a research task, the reasons disappear. This notebook records them as the work happens, and the agent does not write the record. |
| 0:15 | `site/trail.html`, the top: task, decision path | This page was generated from 26 step files. A reader who was not there is asked the brief's question. |
| 0:25 | The card "At step-14 the plan changed" | **The cold reader answers aloud:** why did they change approach at step 14? (The inherited analysis scored 0.5639 on held-out data against a floor of 0.71, so the plan at step 4 was replaced.) |
| 1:00 | The "Sealed inputs" section, then "Before this plan was proposed" on the card | The new plan promises one held-out scoring. The trail shows five earlier commands had opened the held-out file. The page reports that. It does not judge it. |
| 1:25 | The timeline: a measured run with its code diff and "Opened" row | Each result names the commit that produced it and the files its run opened. |
| 1:40 | Terminal: `cat evidence/madelon-2026-11-15-1/tamper.txt` | Changing a number breaks the chain. Re-chaining passes the check but not the stored metrics file. A full rewrite fails against the head that was cited. |
| 2:00 | `http://127.0.0.1:8077/` | Twelve trails on one map. Stations are milestones, lines are routes, and each lane is one agent's trail. |
| 2:15 | Hover a station with an amber mark; then the "Withdrawn" table; then `/rev/3` | Every credit is recomputed from the step files. A credit that was withdrawn stays on record with its reason, and any past revision can be opened. |
| 2:35 | `evidence/README.md`, "The check does not show…" | What we did not find: models answered our questions as well from the raw transcript. The page was a tenth of the length. |
| 2:50 | `README.md`, "What it does not prove" | The limits are in the README. |

**For the cold reader.** Someone who has not seen the task. Give them only `site/trail.html` and
the question "why did they change approach at step 14?". Record their answer unprompted, and
keep it whether or not it is right.

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

**What was run.** Twenty-seven live trails by one model on two constructed tasks, all committed,
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
- One agent ran with every command in a sandbox. The sandbox held, and the run reached nothing:
  the file trace slowed its first search thirteen times, and the wall clock ended it there.
- Every ✓ and ✗ at the held-out floor is within 1.1 standard errors of it (0.0109 on
  2,200 rows), and the four scores behind one goal do not tell its routes apart. A second model
  forecast the map's milestones from their Markov blanket, from text that code built and scored.
  On the six questions that were real forecasts it did worse than a coin flip. Three agents run
  to settle three open forecasts settled none (`research/…/forecasts/scores.txt`).
- A second project on synthetic data with a known truth tested that. Kimi K3.1 Pro forecast and
  chose the routes for three rounds of three agents, pushed before each round. In two rounds the
  agents read each other's results and every route cleared the floor. A third, on routes that
  forbade that, gave the first refutations, one 0.68 standard errors under the floor. The
  blanket's code forecaster beat a coin flip by 0.19 ± 0.03 in round 2, and Kimi beat the blanket
  by 0.26 ± 0.12 in round 3. Over all 18 settled forecasts, none beat a coin flip
  (`research/synthetic-interactions/README.md`).

**What it does not prove.** Who wrote a step, what a read was used for, or that a run used the
method it claims. The map's revisions were sealed by AI agents until a person countersigned it at rev-14, confirming
the agents' judgments but not each credit one by one. The README lists each
limit.

**Disclosure.** The step schema, checker and three example trails predate 10 November. The code
was written by AI coding agents from specs in `docs/specs/`.

## Links

- Repository: `https://github.com/antoniomangoni/provenance-notebook`
- Pages: `https://antoniomangoni.github.io/provenance-notebook/`, the reviewer's page of the live
  trail, both research maps and their belief reports
- Start at `README.md`

## Video, under three minutes

One take of a browser and a terminal, with no voice. The words are subtitles, a scripted dialogue
shown in a caption strip recorded with the screen: Person 1 asks as a reviewer who was not there,
and Person 2 answers from the pages. No cold reader was recorded. Build the pages first with
`scripts/site.sh site`, and start `uv run python project.py serve research/madelon-reanalysis/map --live live`.

| Time | On screen | Person 1 | Person 2 |
| --- | --- | --- | --- |
| 0:00 | `site/index.html` | An agent worked on a research task. Why did it change approach at step 14? | Don't ask the agent. Read the record it couldn't write. |
| 0:12 | `site/trail.html`, the top | | This page is built from 26 hash-chained step files, written around the agent by hooks, not by the agent. |
| 0:24 | The card "At step-14 the plan changed" | So why did it change? | The inherited analysis scored 0.5639 on held-out data against a floor of 0.71. So the plan from step 4 was replaced at step 14. |
| 0:46 | "Sealed inputs", then "Before this plan was proposed" | Had it touched the held-out data before that? | Five earlier commands opened it. The page reports that. It doesn't judge it. |
| 1:04 | The timeline: a run with its code diff and "Opened" row | | Every result names the commit that produced it and every file its run opened. |
| 1:18 | Terminal: `cat evidence/madelon-2026-11-15-1/tamper.txt` | Could someone just edit a number? | Then the chain breaks. Re-chain it, and the stored metrics file disagrees. Rewrite it all, and the head cited earlier no longer matches. |
| 1:40 | `http://127.0.0.1:8077/` | | Fifteen agent trails on one research map. Every ✓ and ✗ is recomputed from the step files, never claimed. |
| 1:54 | `http://127.0.0.1:8077/review`, one credit's graph | Who decided which reads of the held-out file were harmless? | Agents, in 13 revisions. Then a person countersigned here: one ruling per judgment, with the steps under each. |
| 2:14 | `site/synthetic.html`, then `site/synthetic-scores.txt` | Can the map predict what will work? | We tested that on a second project with a known truth. A second model forecast every milestone before each round. Over 18 settled forecasts, nothing beat a coin flip. |
| 2:36 | `README.md`, "What it does not prove" | So is the page better than the transcript? | Not on our questions: models answered as well from the raw transcript. The page is a tenth the length. The limits are in the README. |
| 2:52 | `site/index.html` | | github.com/antoniomangoni/provenance-notebook |

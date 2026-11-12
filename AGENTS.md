# Working in this repository

Rules for every agent and session. [PLAN.md](PLAN.md) is the roadmap, and each piece of work has
a spec in [docs/specs/](docs/specs/) written to [docs/meta-spec.md](docs/meta-spec.md).

## What this is

A provenance trail for an AI-assisted research task: step files that record plans, runs,
observations and reviews, a checker for them (`trail.py`), and a Pi extension that writes them
as an agent works (`capture/`). [docs/DESIGN.md](docs/DESIGN.md) specifies the step format.

## Setup

```sh
uv sync                    # Python 3.12 or later; the dev group has pytest and ruff
npm ci --prefix capture    # Pi 0.84.1, pinned; needs Node.js 24
```

## Commands

```sh
uv run pytest              # all tests; the ones that need Node.js or Pi skip without them
uv run ruff check
uv run python trail.py check examples/churn-model-2026-11-11 --store examples/store
```

## Working on a spec

1. Read the whole spec, then only its target files and what they import.
2. Work on the branch the spec names, `spec/NN-name`. Edit only the spec's target files.
3. Take the spec's sequence one step at a time. After each step, run its check and read the
   diff against the spec's goals, non-goals and rejection criteria.
4. When the spec is wrong or incomplete, change the spec first, in the same branch, and say so
   in the pull request.
5. Open one pull request to `main`. Its description lists each "done when" with the command
   that shows it, and anything left undone.

## Always

- Run `uv run pytest` and `uv run ruff check` before each commit.
- Write a test for each rule a spec states, named for the behaviour it guards.
- Escape every string taken from a step before it reaches HTML: an agent wrote it.
- Keep parameter values out of messages shown to the agent and out of errors, unless the task
  lists the parameter as public.

## Ask first

- A change to `step.schema.json`, to a rule in `trail.check`, or to an interface listed under
  "Interfaces the slices share" in [PLAN.md](PLAN.md).
- A new dependency in `pyproject.toml` or `capture/package.json`.
- Regenerating `examples/`, or any change that makes an existing test's expected value change.
- Editing `README.md`, `PLAN.md` or `docs/HACKATHON.md` from a spec branch.

## Never

- Edit a file under `examples/` or `live/` by hand. Examples come from `trail.py examples`, and
  a live trail is evidence.
- Commit a key, a token or a `*.key` file.
- Change another spec's target files.
- Push to `main` directly, or merge with failing checks.

## Style

- Python: one module per concern at the repository root, standard library first, line length
  140. Match the density of `trail.py`: small functions, comments that say why a rule exists.
- TypeScript: tabs, ES modules, run directly by Node.js 24 and by Pi's loader, no build step.
- Error messages name the step and the rule, as `trail.check` does.
- Documents describe behaviour and limits, not history. One sentence per idea.

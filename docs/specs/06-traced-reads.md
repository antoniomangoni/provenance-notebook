# Spec 6: traced reads

Branch `spec/06-traced-reads`, stacked on `spec/05-research-map` (PR #11).

The research map's most important judgments were made by reading code. Two examples:

- that the first steered run scored candidate designs on `data/heldout.csv` (steps 38 and 41);
- that the second run's exploratory scripts never read it.

A run's `inputs` cannot settle this, because capture fills them from the task file: every run in
every trail lists both data files. `sealed_inputs` only searches command lines.

This spec records what each command actually opened, so that "read a sealed input before its
result" is a fact the checker can use. It also re-executes the existing trails to find out what
they read, without a model.

## Goals

1. Capture traces every command with strace, and writes the files it opened as the observation's
   `reads`.
2. `retrace.py` re-executes a trail's runs from its code snapshots, under the same trace. It
   reports each run's reads, and whether the run reproduced its exit code and metrics file.
3. `project.py` labels each sealed read by how it is known: captured, re-executed, or named on the
   command line. `check` refuses a holding resolution after a captured read of a sealed input.
4. The five Madelon trails are re-executed, and the map is revised (rev-6) from what that shows.

## Non-goals

- Editing any trail. A re-execution is an attestation beside the trail, not a step in it.
- Tracing writes, network or `stat` calls.
- Any platform without strace. There a run has no `reads`, which means unknown.
- New model runs.

## Technical decisions

### `reads`

- **Schema.** `reads` is an optional observation field, `[{ref, digest}]`, the shape of `outputs`.
  The schema stays at version 2: the field is optional, and no existing trail changes.
- **What is kept.** A read is a file the command or any process it started opened for reading,
  successfully. Only files inside the workspace count, leaving out `.git/`, `.venv/` and
  `__pycache__/`. Each path is workspace-relative, sorted, unique, and capped at 500.
- **When the digest is taken.** When the command ends. A file the command changed after reading
  it is cited at its new content.
- **Absent versus empty.** A run without tracing has no `reads`. `[]` means it was traced and
  read nothing.

The trace is:

```
strace -f -qq -y -e trace=open,openat,openat2 -e status=successful -o TRACE -- bash -c COMMAND
```

`NOTEBOOK_TRACE=0` turns it off.

**`trail.py`:**
- the checker allows `reads` on observations;
- `graph` adds `read` edges from the run to each file, with the digest on the edge;
- `facts` names each run that read a file outside its declared `inputs`.

### `retrace.py TRAIL --out FILE [--timeout-factor 3]`

- **Commands.** Each comes from the run step, or from Pi's session file when `shown` was cut
  (matched by digest). A run whose command cannot be found is reported and skipped.
- **The workspace.**
  - It sits at the session's original `cwd`, so commands that `cd` there work. The script refuses
    if that path exists.
  - It is a clone of `code.bundle`, then `uv sync`.
- **Each run, in order:**
  - `git checkout -f` its commit, keeping the ignored `out/` and `.venv/`;
  - run the command under the trace, with only `PATH`, `HOME` and `TMPDIR` in its environment;
  - stop it after `max(60 s, factor × the recorded duration)`.
- **Recorded per run:**
  - the exit code, recorded and replayed;
  - the fresh metrics digest, recorded and replayed;
  - the reads.
- **After.** The workspace is removed.

### `project.py`

- **Where reads come from.** An observation's `reads` (captured). Or retrace files passed as
  `--reads FILE…` (re-executed): these must name a trail given, at a head it had.
- **`peeks` labels.** Each run before a resolution is labelled `read`, `read on re-execution`,
  or `names`. `names` comes from the command-line search, used only when neither source covers
  the run.
- **`check`.** It fails a resolution with `holds: true` when an earlier run in its trail has a
  captured read of a sealed input. The cited run itself is allowed to read it.
- **`shared`.** For each re-executed trail: the runs whose metrics file reproduced, out of
  those that wrote one.

## Testing

- **Capture** (scripted, skipped without strace):
  - `cat data/pilot.csv` reads it at its digest;
  - `true` reads `[]`;
  - with `NOTEBOOK_TRACE=0` there is no field;
  - `.venv` never appears;
  - trails check.
- **Checker and graph.**
  - `reads` is accepted on an observation and refused on a run.
  - Graph `read` edges carry the digest.
  - The examples' tables are unchanged.
- **Retrace** (a scripted trail made in the test):
  - exit codes and metrics digests match;
  - reads are found;
  - the trail is unchanged.
- **Map.**
  - A captured sealed read before a holding resolution fails `check`.
  - Retrace labels reach `view`.
  - Without either source, the command-line search is still used.

## Target files

- `docs/specs/06-traced-reads.md`
- `step.schema.json`
- `trail.py`
- `docs/DESIGN.md`
- `docs/GRAPH.md`
- `capture/capture.ts`
- `tests/test_capture.py`
- `retrace.py`
- `tests/test_retrace.py`
- `project.py`
- `tests/test_project.py`, `tests/test_trail.py`
- `.github/workflows/ci.yml` (install strace)
- one `PLAN.md` row
- `research/madelon-reanalysis/` (`retrace/`, rev-6, outputs, README)

## Boundaries

- **Always:** report a run that did not reproduce, and keep the re-executed and captured labels
  apart.
- **Ask first:** a command that would touch anything outside its workspace or `/tmp`.
- **Never:** write into a trail, or run a replay with the model key in its environment.

## Rejection criteria

- `check` passes a holding resolution after a captured sealed read.
- A re-executed read is presented as captured.
- An untraced run shows `reads: []`.

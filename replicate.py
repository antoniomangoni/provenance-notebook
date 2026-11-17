"""Re-runs each held-out analysis a map credits or refutes on a replication sample: how it truly does.

Usage: replicate.py MAP --live DIR --data FILE --out FILE [--node-suffix S]

For each resolution of a milestone whose id ends with S (default -holdout), the cited observation's
run is found in its trail, the trail's code.bundle is cloned at that run's commit, the sealed input
(the map's first sealed_inputs entry) is replaced by FILE, and the same command is run again with
only PATH, HOME and TMPDIR in its environment, on one thread. Its out/metrics.json gives the
replicated value of each measure. Nothing in a trail or the map is written.

The replicated value is what the analysis the agent locked does on another sample from the same
source: with a large FILE, close to its true value. It is a re-execution, not the run itself.

docs/specs/12-second-project.md is the specification.
"""

import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import project
import retrace
import trail

TIMEOUT = 1800


class Usage(Exception):
    """The command line was wrong."""


def rerun(trail_dir: Path, run: dict, sealed: str, data: Path, command: str, cwd: str | None) -> dict:
    """One run again, at its own snapshot, with the sealed input replaced by data."""
    env = {name: os.environ[name] for name in ("PATH", "HOME", "TMPDIR") if name in os.environ}
    env |= {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    work = Path(tempfile.mkdtemp(prefix="replicate-")) / "work"
    try:
        subprocess.run(["git", "clone", "-q", str((trail_dir / "code.bundle").resolve()), str(work)], check=True, capture_output=True)
        retrace.git("checkout", "-q", "-f", run["code"]["ref"].split(":")[-1].split("@")[-1], cwd=work)
        if (work / "pyproject.toml").exists():
            subprocess.run(["uv", "sync", "--quiet"], cwd=work, env=env, check=True, capture_output=True)
        target = work / sealed
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(data, target)
        (work / retrace.METRICS).unlink(missing_ok=True)
        if cwd and cwd in command:
            command = command.replace(cwd, str(work))
        started = time.monotonic()
        process = subprocess.Popen(
            ["bash", "-c", command], cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )
        try:
            code, timed_out = process.wait(timeout=TIMEOUT), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code, timed_out = process.wait(), True
        kept = {"exit": None if timed_out else code, "seconds": round(time.monotonic() - started, 1)}
        metrics = work / retrace.METRICS
        if timed_out or not metrics.exists():
            return kept | {"problem": "timed out" if timed_out else "no out/metrics.json"}
        try:
            found = json.loads(metrics.read_text())
        except json.JSONDecodeError:
            return kept | {"problem": "out/metrics.json is not JSON"}
        measures = {k: v for k, v in found.items() if isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)}
        return kept | {"measures": measures}
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)


def replicate(revision: dict, trails: project.Trails, data: Path, suffix: str = "-holdout") -> list[dict]:
    sealed = revision["sealed_inputs"][0]
    nodes = {n["id"]: n for n in revision["nodes"]}
    rows, done = [], {}
    for resolution in revision["resolutions"]:
        if not resolution["node"].endswith(suffix):
            continue
        probe, observation = trails.cite(resolution["cites"], revision["project"])
        steps = trails.steps[probe]
        run = next(s for s in steps if s["id"] == trail.observed(observation))
        key = (probe, run["id"])
        if key not in done:
            cwd, commands = retrace.session(trails.paths[probe])
            command = commands.get(run["command"]["digest"])
            if command is None and trail.digest(run["command"]["shown"].encode()) == run["command"]["digest"]:
                command = run["command"]["shown"]
            if command is None:
                done[key] = {"problem": "the full command is in neither the step nor the session file"}
            else:
                done[key] = rerun(trails.paths[probe], run, sealed, data, command, cwd)
        again = done[key]
        recorded = project.measures(observation)
        row = {
            "node": resolution["node"],
            "cites": resolution["cites"],
            "holds": resolution["holds"],
            "run": run["id"],
            "commit": run["code"]["ref"],
            "recorded": recorded,
            **again,
        }
        if "measures" in again:
            # The replicated outcome of each criterion on the measure the sealed input decides.
            row["criteria"] = [
                {**c, "value": again["measures"][c["measure"]], "holds": trail.holds(c, again["measures"][c["measure"]], 0)}
                for c in nodes[resolution["node"]]["criteria"]
                if c["measure"] in again["measures"] and c["measure"] in recorded and "holdout" in c["measure"]
            ]
        rows.append(row)
    return rows


def main(argv: list[str]) -> int:
    args, named, rest = [], {}, list(argv[1:])
    while rest:
        word = rest.pop(0)
        if word in ("--live", "--data", "--out", "--node-suffix"):
            named[word[2:]] = rest.pop(0) if rest else ""
        else:
            args.append(word)
    if len(args) != 1 or not {"live", "data", "out"} <= set(named):
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    directory, data = Path(args[0]), Path(named["data"])
    revs = project.revisions(directory)
    paths = project.discover(Path(named["live"]), revs[-1]["project"])
    trails = project.Trails(paths, (), directory.parent)
    if errors := project.check(revs, trails):
        print("the map does not check:", *errors, sep="\n  ", file=sys.stderr)
        return 1
    rows = replicate(revs[-1], trails, data, named.get("node-suffix", "-holdout"))
    kept = {
        "version": 1,
        "project": revs[-1]["project"],
        "rev": revs[-1]["rev"],
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {"file": data.name, "digest": trail.digest(data.read_bytes()), "rows": data.read_bytes().count(b"\n") - 1},
        "note": "Re-executions of the cited runs with the sealed input replaced by the replication sample, not the runs themselves.",
        "rows": rows,
    }
    Path(named["out"]).write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {named['out']}: {len(rows)} resolutions re-run")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Re-executes a trail's runs under a file trace: what each one read, and whether it reproduced.

Usage: retrace.py TRAIL --out FILE [--timeout-factor N]

The trail's code snapshots are cloned from its code.bundle into a fresh workspace; a command that
names the session's original workspace (Pi's session file records it) is given the new path. Each run's command is run again, in order, at
its own snapshot, with only PATH, HOME and TMPDIR in its environment. strace records every file
the command and its children opened for reading. The result is an attestation beside the trail:
a re-execution, not the run itself. Nothing in TRAIL is written.

docs/specs/06-traced-reads.md is the specification.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import trail

# PID name(args) = FD</absolute/path>: -y decodes the descriptor a successful open returned.
OPENED = re.compile(r"^\d+\s+(?:open|openat|openat2)\((?P<args>.*)\)\s+=\s+\d+<(?P<path>.+)>$")
SKIPPED = (".git", ".venv", "__pycache__")
METRICS = "out/metrics.json"


def traced(command: str, trace: Path) -> list[str]:
    return [
        "strace",
        "-f",
        "-qq",
        "-y",
        "-e",
        "trace=open,openat,openat2",
        "-e",
        "status=successful",
        "-o",
        str(trace),
        "--",
        "bash",
        "-c",
        command,
    ]


def reads(trace: Path, workspace: Path) -> list[dict]:
    """The workspace files a trace shows opened for reading, workspace-relative, at their present digest."""
    root, found = workspace.resolve(), set()
    for line in trace.read_text(errors="replace").splitlines():
        if not (opened := OPENED.match(line)) or "O_WRONLY" in opened["args"] or "O_DIRECTORY" in opened["args"]:
            continue
        path = Path(opened["path"])
        if not path.is_relative_to(root) or not path.is_file():
            continue
        relative = path.relative_to(root)
        if not set(relative.parts) & set(SKIPPED):
            found.add(relative.as_posix())
    return [{"ref": f"file:{name}", "digest": trail.digest((root / name).read_bytes())} for name in sorted(found)[:500]]


def session(trail_dir: Path) -> tuple[str | None, dict[str, str]]:
    """The workspace the session ran in, and every bash command the model gave, by digest."""
    cwd, commands = None, {}
    for path in sorted((trail_dir / "session").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "session":
                cwd = cwd or event.get("cwd")
            for part in (event.get("message") or {}).get("content") or []:
                if isinstance(part, dict) and part.get("type") == "toolCall" and part.get("name") == "bash":
                    command = (part.get("arguments") or {}).get("command")
                    if isinstance(command, str):
                        commands[trail.digest(command.encode())] = command
    return cwd, commands


def stamp(path: Path) -> float | None:
    return path.stat().st_mtime_ns if path.exists() else None


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def retrace(trail_dir: Path, factor: float = 3, workspace: Path | None = None) -> dict:
    steps = trail.load(trail_dir)
    if problems := trail.check(steps):
        raise SystemExit(f"retrace.py: {trail_dir} does not check: {problems[0]}")
    cwd, commands = session(trail_dir)
    # A fresh directory, never the original workspace, which may still exist: a command that names
    # the original path is given the new one instead, and its run says so.
    workspace = workspace or Path(tempfile.mkdtemp(prefix=f"retrace-{steps[0]['trail']}-")) / "work"
    if workspace.exists():
        raise SystemExit(f"retrace.py: {workspace} exists; the replay needs it free")
    env = {name: os.environ[name] for name in ("PATH", "HOME", "TMPDIR") if name in os.environ}
    settled = {trail.observed(step): step for step in steps if step["kind"] == "observation"}
    runs = []
    try:
        subprocess.run(["git", "clone", "-q", str((trail_dir / "code.bundle").resolve()), str(workspace)], check=True, capture_output=True)
        if (workspace / "pyproject.toml").exists():
            subprocess.run(["uv", "sync", "--quiet"], cwd=workspace, env=env, check=True, capture_output=True)
        with tempfile.TemporaryDirectory() as scratch:
            for step in (s for s in steps if s["kind"] == "run"):
                observation = settled.get(step["id"])
                command = commands.get(step["command"]["digest"])
                if command is None and trail.digest(step["command"]["shown"].encode()) == step["command"]["digest"]:
                    command = step["command"]["shown"]
                kept = {"run": step["id"], "observation": observation["id"] if observation else None}
                if command is None:
                    runs.append(kept | {"skipped": "the full command is in neither the step nor the session file"})
                    continue
                if cwd and cwd in command:
                    command, kept["cwd_rewritten"] = command.replace(cwd, str(workspace)), True
                git("checkout", "-q", "-f", step["code"]["ref"].split(":")[-1].split("@")[-1], cwd=workspace)
                recorded = (observation or {}).get("duration_ms", 0) / 1000
                limit = max(60.0, factor * recorded)
                trace, before = Path(scratch) / f"{step['id']}.trace", stamp(workspace / METRICS)
                started = time.monotonic()
                process = subprocess.Popen(
                    traced(command, trace),
                    cwd=workspace,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                try:
                    code, timed_out = process.wait(timeout=limit), False
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code, timed_out = process.wait(), True
                after = stamp(workspace / METRICS)
                fresh = after is not None and after != before
                replayed = trail.digest((workspace / METRICS).read_bytes()) if fresh else None
                source = (observation or {}).get("measures_source", {}).get("digest")
                runs.append(
                    kept
                    | {
                        "exit": {"recorded": (observation or {}).get("exit_code"), "replayed": None if timed_out else code},
                        "metrics": {"recorded": source, "replayed": replayed, "same": source == replayed if source or replayed else None},
                        "seconds": {"recorded": round(recorded, 1), "replayed": round(time.monotonic() - started, 1)},
                        **({"timed_out": True} if timed_out else {}),
                        "reads": reads(trace, workspace) if trace.exists() else None,
                    }
                )
    finally:
        shutil.rmtree(workspace.parent if workspace.parent.name.startswith("retrace-") else workspace, ignore_errors=True)
    version = subprocess.run(["strace", "-V"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    return {
        "version": 1,
        "trail": f"{trail.probe_id(steps)}",
        "head": trail.digest(trail.canonical(steps[-1])),
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strace": version,
        "note": "A re-execution of the recorded runs from their code snapshots, not the runs themselves.",
        "runs": runs,
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    out = trail.option(args, "--out")
    factor = trail.option(args, "--timeout-factor")
    if len(args) != 1 or out is None:
        print("usage: retrace.py TRAIL --out FILE [--timeout-factor N]", file=sys.stderr)
        return 2
    if shutil.which("strace") is None:
        print("retrace.py: needs strace", file=sys.stderr)
        return 2
    result = retrace(Path(args[0]), float(factor) if factor else 3)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, indent=2) + "\n")
    done = [run for run in result["runs"] if "metrics" in run]
    same = sum(run["metrics"]["same"] is True for run in done)
    wrote = sum(run["metrics"]["same"] is not None for run in done)
    print(f"{args[0]}: {len(result['runs'])} runs, {same} of {wrote} metrics files reproduced, wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

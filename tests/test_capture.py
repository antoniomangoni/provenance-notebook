"""Capture's rules, each shown by a scripted session: the launcher runs Pi with a provider that
replays fixed tool calls, so no model, key or network is needed. Every scenario's trail must pass
the checker with its store, whatever else it asserts."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

import trail

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "capture-demo"
PI = ROOT / "capture" / "node_modules" / ".bin" / "pi"
pytestmark = pytest.mark.skipif(shutil.which("node") is None or not PI.exists(), reason="needs Node.js 24 and capture's node_modules")

LOOK = {
    "summary": "Look around",
    "reasoning": "See what the task starts from.",
    "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"}],
}
FLOOR = {
    "summary": "Baseline fit",
    "reasoning": "The simplest model first.",
    "expectations": [
        {"name": "runs", "measure": "exit", "comparison": "exit_ok"},
        {"name": "auc-floor", "measure": "auc", "comparison": "ge", "threshold": 0.75},
    ],
}


def plan(given: dict = LOOK, **more) -> list:
    return ["propose_plan", {**given, **more}]


def bash(command: str) -> list:
    return ["bash", {"command": command}]


@dataclass
class Session:
    done: subprocess.CompletedProcess
    directory: Path
    store: Path
    workspace: Path
    steps: list[dict]
    seconds: float

    @property
    def results(self) -> list[tuple[str, bool, str]]:
        """What each tool call gave the model: the tool, whether it was an error, and the text."""
        found = []
        for line in (self.directory / "events.jsonl").read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "tool_execution_end":
                text = "\n".join(part.get("text", "") for part in (event.get("result") or {}).get("content", []))
                found.append((event["toolName"], bool(event.get("isError")), text))
        return found

    def kinds(self) -> list[str]:
        return [step["kind"] for step in self.steps]

    def of(self, kind: str) -> list[dict]:
        return [step for step in self.steps if step["kind"] == kind]


def live(tmp_path: Path, turns: list | Path, name: str = "scripted-run", expect: int = 0, **env: str) -> Session:
    """Runs the launcher on the fixture with these scripted turns. The Pi configuration is an empty
    directory, so the session cannot reach a real model's key, and step 0 must name the scripted one."""
    script = turns if isinstance(turns, Path) else tmp_path / f"{name}.json"
    if not isinstance(turns, Path):
        script.write_text(json.dumps(turns))
    (tmp_path / "work").mkdir(exist_ok=True)
    settings = {
        **os.environ,
        "NOTEBOOK_LIVE": str(tmp_path / "live"),
        "NOTEBOOK_SCRIPT": str(script),
        "TMPDIR": str(tmp_path / "work"),
        "PI_CODING_AGENT_DIR": str(tmp_path / "pi"),
        "PI_OFFLINE": "1",
        **env,
    }
    started = time.monotonic()
    done = subprocess.run(
        [
            str(ROOT / "scripts" / "live.sh"),
            str(FIXTURE),
            name,
            "-e",
            "capture/scripted.ts",
            "--provider",
            "script",
            "--model",
            "scripted-1",
        ],
        cwd=ROOT,
        env=settings,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    seconds = time.monotonic() - started
    assert done.returncode == expect, done.stdout + done.stderr
    directory, store = tmp_path / "live" / name, tmp_path / "live" / "store"
    workspace = Path(next(line.split(" is ", 1)[1] for line in done.stdout.splitlines() if "the workspace is " in line))
    steps = trail.load(directory)
    assert trail.check(steps, store) == []
    if steps:
        assert steps[0]["agent"] == {"name": "pi", "version": "0.84.1", "model": "script/scripted-1"}
    return Session(done, directory, store, workspace, steps, seconds)


def links(step: dict) -> dict[str, str]:
    return {link["relation"]: link["target"] for link in step.get("links", [])}


def git(directory: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_step_0_is_the_task_file_and_the_agent(tmp_path):
    session = live(tmp_path, [])
    (task,) = session.steps
    given = json.loads((FIXTURE / "task.json").read_text())
    assert (task["by"], task["trail"], task["hook"]) == ("human:tester", "scripted-run", "pi:session_start")
    assert {name: task[name] for name in ("summary", "question", "project", "declared_measures", "public_parameters")} == {
        name: given[name] for name in ("summary", "question", "project", "declared_measures", "public_parameters")
    }
    assert (session.directory / "session").is_dir()


def test_a_change_of_approach_is_recorded_from_the_ids_in_the_receipts(tmp_path):
    session = live(tmp_path, FIXTURE / "change.json")
    assert session.kinds() == ["task", "plan", "run", "observation", "plan", "run", "observation", "plan", "run", "observation"]
    look, missed, met = session.of("run")
    assert look["parameters"] == [] and links(look) == {"implements": "step-1"}
    assert [(p["name"], p["value"]) for p in missed["parameters"]] == [("model", "logistic"), ("seed", "7"), ("auc", "0.58")]
    assert [(p["name"], p["value"]) for p in met["parameters"]] == [("model", "logistic"), ("seed", "7"), ("auc", "0.78")]
    assert all(p["digest"] == trail.h(p["value"]) for p in missed["parameters"])
    # Only the declared input that exists is cited, at the digest of the file the run read.
    assert missed["inputs"] == [{"ref": "file:data/telco.csv", "digest": trail.digest((FIXTURE / "workspace/data/telco.csv").read_bytes())}]
    contradicted, replacement = session.steps[6], session.steps[7]
    assert (
        contradicted["outcome"] == "contradicted"
        and {"expectation": "auc-floor", "measured": 0.58, "held": False} in contradicted["checks"]
    )
    assert contradicted["measures"] == [{"name": "auc", "value": 0.58}, {"name": "positive_rate", "value": 0.07}]
    assert replacement["links"] == [
        {"relation": "supersedes", "target": "step-4", "status": "suggested"},
        {"relation": "triggered_by", "target": "step-6", "status": "suggested"},
    ]
    assert session.steps[9]["outcome"] == "as_expected"
    # The model learns the ids it cited from the line that ends each command's result.
    receipts = [text.splitlines()[-1] for tool, _, text in session.results if tool == "bash"]
    assert receipts == [
        "[notebook] run step-2, observation step-3: as_expected",
        "[notebook] run step-5, observation step-6: contradicted (auc 0.58, expected >= 0.75)",
        "[notebook] run step-8, observation step-9: as_expected",
    ]
    assert ("propose_plan", False, "recorded as step-7") in session.results


def test_a_run_is_written_before_its_command_executes(tmp_path):
    session = live(tmp_path, [[plan()], [bash('test -f "$NOTEBOOK_TRAIL/steps/step-2.json"')]])
    assert session.kinds() == ["task", "plan", "run", "observation"]
    assert (session.steps[3]["exit_code"], session.steps[3]["outcome"]) == (0, "as_expected")


def test_a_later_command_is_not_settled_with_earlier_metrics(tmp_path):
    session = live(tmp_path, [[plan(FLOOR)], [bash("python3 fit.py --auc 0.8")], [bash("ls")]])
    measured, stale = session.of("observation")
    assert measured["outcome"] == "as_expected" and measured["measures"] == [{"name": "auc", "value": 0.8}]
    assert stale["outcome"] == "inconclusive" and "measures" not in stale and "measures_source" not in stale
    assert (session.workspace / "out" / "metrics.json").exists()
    assert session.results[-1][2].endswith("inconclusive (no fresh out/metrics.json with auc)")


def test_two_commands_in_one_turn_each_have_their_own_observation(tmp_path):
    session = live(tmp_path, [[plan(FLOOR)], [bash("python3 fit.py --auc 0.8"), bash("ls")]])
    first, second = session.of("run")
    wrote, listed = session.of("observation")
    assert (links(wrote)["observes"], links(listed)["observes"]) == (first["id"], second["id"])
    assert wrote["measures"] == [{"name": "auc", "value": 0.8}] and "measures" not in listed
    # One command at a time: the second run is written, and its code snapshot taken, after the first has ended.
    assert session.kinds() == ["task", "plan", "run", "observation", "run", "observation"]


def test_a_command_without_a_plan_is_blocked_and_nothing_is_written(tmp_path):
    session = live(tmp_path, [[bash("touch ran.txt")]])
    assert session.kinds() == ["task"]
    ((tool, error, text),) = session.results
    assert (tool, error) == ("bash", True) and "propose_plan" in text and "exit_ok" in text
    assert not (session.workspace / "ran.txt").exists()


def test_a_plan_that_does_not_fit_is_refused_with_what_can_be_used(tmp_path):
    undeclared = plan(FLOOR, expectations=[{"name": "f1", "measure": "f1", "comparison": "ge", "threshold": 0.5}])
    twice = plan(
        expectations=[
            {"name": "Runs OK", "measure": "exit", "comparison": "exit_ok"},
            {"name": "runs-ok", "measure": "exit", "comparison": "exit_ok"},
        ]
    )
    session = live(
        tmp_path,
        [[undeclared, plan(), plan(supersedes="step-1"), plan(supersedes="step-9", triggered_by="step-8"), twice, plan(summary="x" * 201)]],
    )
    assert session.kinds() == ["task", "plan"]
    refused = [text for tool, error, text in session.results if error]
    assert len(refused) == 5 and all("not recorded" in text for text in refused)
    assert "The task declares: auc, positive_rate" in refused[0]
    assert "go together" in refused[1] and "Plans: step-1. Observations: none." in refused[1]
    assert "Plans: step-1. Observations: none." in refused[2]
    assert "two expectations are named runs-ok" in refused[3] and "200 characters" in refused[4]


def test_a_failing_command_is_failed_with_an_error_class_and_a_receipt(tmp_path):
    session = live(tmp_path, [[plan(FLOOR)], [bash("python3 fit.py --auc 0.9 --exit 3")]])
    (observation,) = session.of("observation")
    assert (observation["exit_code"], observation["outcome"], observation["error"]) == (3, "failed", {"class": "exit"})
    _, error, text = session.results[-1]
    assert error and text.splitlines()[-1] == "[notebook] run step-2, observation step-3: failed (exit code 3)"


def test_snapshots_follow_the_code_and_leave_the_workspace_alone(tmp_path):
    changed = "import json, pathlib\npathlib.Path('out').mkdir(exist_ok=True)\npathlib.Path('out/metrics.json').write_text(json.dumps({'auc': 0.8}))\n"
    session = live(
        tmp_path,
        [
            [plan(FLOOR)],
            [bash("python3 fit.py --auc 0.8")],
            [["write", {"path": "fit.py", "content": changed}]],
            [bash("python3 fit.py")],
            [bash("python3 fit.py")],
        ],
    )
    first, second, third = (run["code"]["ref"].removeprefix("commit:") for run in session.of("run"))
    assert first != second and second == third
    assert git(session.workspace, "rev-parse", f"refs/heads/notebook/{session.steps[0]['trail']}") == second
    assert git(session.workspace, "show", f"{second}:fit.py") == changed.strip() and "argparse" in git(
        session.workspace, "show", f"{first}:fit.py"
    )
    # The agent's edit is still an unstaged change on the one commit the launcher made.
    assert git(session.workspace, "rev-list", "--count", "HEAD") == "1"
    assert git(session.workspace, "status", "--porcelain") == "M fit.py"
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(session.directory / "code.bundle"), str(clone)], check=True, capture_output=True)
    assert git(clone, "cat-file", "-t", first) == "commit" and git(clone, "cat-file", "-t", second) == "commit"


def test_write_and_edit_to_the_trail_and_the_store_are_blocked(tmp_path):
    steps, store = tmp_path / "live" / "scripted-run" / "steps", tmp_path / "live" / "store"
    session = live(
        tmp_path,
        [
            [plan()],
            [
                ["write", {"path": str(steps / "step-9.json"), "content": "{}"}],
                ["edit", {"path": str(steps / "step-1.json"), "edits": [{"oldText": "Look around", "newText": "Edited"}]}],
                ["write", {"path": str(store / "planted"), "content": "{}"}],
                ["write", {"path": "notes.txt", "content": "kept"}],
            ],
        ],
    )
    blocked = [text for tool, error, text in session.results if error]
    assert len(blocked) == 3 and all("written only by capture" in text for text in blocked)
    assert sorted(path.name for path in steps.iterdir()) == ["step-0.json", "step-1.json"] and not (store / "planted").exists()
    assert session.steps[1]["summary"] == "Look around" and (session.workspace / "notes.txt").read_text() == "kept"


def test_malformed_metrics_give_no_measures_and_a_runner_note(tmp_path):
    session = live(tmp_path, [[plan(FLOOR)], [bash("""python3 fit.py --raw '{"auc": {"mean": 0.58}}'""")]])
    assert session.kinds() == ["task", "plan", "run", "observation", "note"]
    observation, note = session.steps[3:]
    assert observation["outcome"] == "inconclusive" and "measures" not in observation
    assert (note["by"], links(note)) == (trail.RUNNER, {"about": "step-3"}) and "out/metrics.json" in note["text"]
    assert not session.store.exists() or not list(session.store.iterdir())


def stopped(session: Session, counted: str) -> None:
    """The session ran one command, blocked the next without running it, said so once, and ended."""
    assert session.kinds() == ["task", "plan", "run", "observation", "note"]
    note = session.steps[4]
    assert (note["by"], links(note)) == (trail.RUNNER, {"about": "step-0"}) and counted in note["text"]
    assert (session.workspace / "first.txt").exists() and not (session.workspace / "second.txt").exists()
    assert not (session.workspace / "third.txt").exists()
    assert [error for tool, error, _ in session.results if tool == "bash"] == [False, True]
    assert counted in session.results[-1][2]


def test_the_run_ceiling_stops_the_session(tmp_path):
    session = live(
        tmp_path, [[plan()], [bash("touch first.txt")], [bash("touch second.txt")], [bash("touch third.txt")]], NOTEBOOK_MAX_RUNS="1"
    )
    stopped(session, "1 of at most 1 runs")


def test_the_token_ceiling_stops_the_session(tmp_path):
    # The scripted provider reports 110 tokens for the first turn and 210 for the second.
    session = live(
        tmp_path, [[plan()], [bash("touch first.txt")], [bash("touch second.txt")], [bash("touch third.txt")]], NOTEBOOK_MAX_TOKENS="300"
    )
    stopped(session, "320 of at most 300 tokens")


def test_the_wall_clock_stops_a_command_that_does_not_return(tmp_path):
    session = live(tmp_path, [[plan()], [bash("sleep 20")]], NOTEBOOK_WALL="3")
    assert session.seconds < 15 and "stopped at the wall clock of 3 seconds" in session.done.stdout
    assert session.kinds() == ["task", "plan", "run"]
    assert trail.facts(session.steps)[-1] == "step-2: never settled; it has no observation"
    assert (session.directory / "code.bundle").exists()


def test_a_capture_that_cannot_start_fails_the_launcher(tmp_path):
    session = live(tmp_path, [[plan()]], expect=1, NOTEBOOK_MAX_RUNS="many")
    assert session.steps == [] and "NOTEBOOK_MAX_RUNS is a positive integer" in session.done.stderr
    assert "no step was written" in session.done.stdout


def test_the_launcher_refuses_a_name_that_exists_or_does_not_fit(tmp_path):
    live(tmp_path, [])
    for name in ("scripted-run", "Not_A_Name"):
        done = subprocess.run(
            [str(ROOT / "scripts" / "live.sh"), str(FIXTURE), name],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "NOTEBOOK_LIVE": str(tmp_path / "live")},
        )
        assert done.returncode == 2


def test_the_protocol_is_under_200_words_and_names_what_the_agent_must_use():
    protocol = (ROOT / "capture" / "protocol.md").read_text()
    assert len(protocol.split()) < 200
    for word in ("propose_plan", "exit_ok", "out/metrics.json", "[notebook]", "supersedes", "triggered_by"):
        assert word in protocol

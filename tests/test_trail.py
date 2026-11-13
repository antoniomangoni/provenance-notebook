"""The checker's guarantees on the example trails: they regenerate, they check, and a change to a
past step is caught, by the chain if it is left broken and by the cited head if it is re-chained."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import trail

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
CHURN, FEATURES, TUNING = "churn-model-2026-11-11", "churn-features-2026-11-12", "churn-tuning-2026-11-13"


def cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "trail.py"), *map(str, args)], check=False, capture_output=True, text=True)


def files(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "graph" not in path.relative_to(directory).parts
    }


def rechain(steps: list[dict], start: int) -> None:
    for seq in range(start, len(steps)):
        steps[seq]["prev"] = trail.digest(trail.canonical(steps[seq - 1]))


@pytest.fixture
def churn() -> list[dict]:
    return trail.load(EXAMPLES / CHURN)


def test_the_committed_examples_are_what_the_generator_writes(tmp_path):
    assert cli("examples", tmp_path).returncode == 0
    assert files(tmp_path) == files(EXAMPLES)


@pytest.mark.parametrize("name", [CHURN, FEATURES, TUNING])
def test_examples_check_against_the_stored_metrics(name):
    assert trail.check(trail.load(EXAMPLES / name), EXAMPLES / "store") == []


def test_the_change_of_approach_reads_off_step_4(churn):
    links = {link["relation"]: link["target"] for link in churn[4]["links"]}
    assert links == {"supersedes": "step-1", "triggered_by": "step-3"}
    assert churn[3]["outcome"] == "contradicted"
    assert {"expectation": "auc-floor", "measured": 0.58, "held": False} in churn[3]["checks"]
    assert [(step["verdict"], step["links"][0]["target"]) for step in churn if step["kind"] == "review"] == [("confirms", "step-4")]


def test_an_edited_step_breaks_the_chain(churn):
    churn[4]["reasoning"] = "Boosting was always the plan."
    assert any("prev does not match step-4" in error for error in trail.check(churn))


def test_a_rechained_trail_checks_but_no_longer_has_its_cited_head(churn):
    cited = trail.digest(trail.canonical(churn[-1]))
    churn[4]["reasoning"] = "Boosting was always the plan."
    rechain(churn, 5)
    assert trail.check(churn, EXAMPLES / "store") == []
    assert trail.verify(trail.load(EXAMPLES / CHURN), cited) == []
    assert "never had the head" in trail.verify(churn, cited)[0]


def test_a_rewritten_result_is_caught_by_the_stored_metrics(churn):
    """Raising the AUC and re-chaining satisfies the chain and the checks, but not the file the run wrote."""
    churn[3]["measures"][0]["value"] = 0.9
    churn[3]["checks"][1] = {"expectation": "auc-floor", "measured": 0.9, "held": True}
    churn[3]["outcome"] = "as_expected"
    rechain(churn, 4)
    assert trail.check(churn) == []
    assert any("the measures are not the ones in file:out/metrics.json" in error for error in trail.check(churn, EXAMPLES / "store"))


def test_an_outcome_cannot_be_claimed(churn):
    churn[3]["outcome"] = "as_expected"
    assert any("outcome is as_expected, the checks give contradicted" in error for error in trail.check(churn))


def test_a_trail_that_grew_still_has_the_head_it_was_cited_at(churn):
    cited = trail.digest(trail.canonical(churn[-1]))
    grown = copy.deepcopy(churn)
    grown.append(
        {
            "version": 2,
            "id": "step-8",
            "seq": 8,
            "trail": churn[0]["trail"],
            "at": "2026-11-13T09:00:00Z",
            "kind": "note",
            "by": "human:antonio",
            "summary": "Later note",
            "text": "Written after it was cited.",
            "links": [{"relation": "about", "target": "step-6", "status": "confirmed"}],
            "prev": cited,
        }
    )
    assert trail.check(grown) == []
    assert trail.verify(grown, cited) == []


def test_facts_show_the_forking_paths_in_tuning():
    found = trail.facts(trail.load(EXAMPLES / TUNING))
    assert "step-1: first held on attempt 3 of 5, after 2 contradicted" in found
    assert "step-8: repeats step-6, with the same command, code, environment, parameters and inputs" in found
    assert "step-10: never settled; it has no observation" in found


def test_head_and_verify_from_the_command_line(tmp_path):
    head = cli("head", EXAMPLES / CHURN)
    cited = head.stdout.splitlines()[-1]
    assert head.returncode == 0 and cited.startswith("sha256:")
    assert cli("verify", EXAMPLES / CHURN, cited).returncode == 0

    steps = trail.load(EXAMPLES / CHURN)
    steps[4]["reasoning"] = "Boosting was always the plan."
    rechain(steps, 5)
    (tmp_path / "steps").mkdir()
    for step in steps:
        (tmp_path / "steps" / f"{step['id']}.json").write_text(json.dumps(step, indent=2) + "\n")
    assert cli("check", tmp_path).returncode == 0
    rewritten = cli("verify", tmp_path, cited)
    assert rewritten.returncode == 1 and "never had the head" in rewritten.stdout


def grow(steps: list[dict], *new: dict) -> list[dict]:
    """Appends steps after the last, chained and dated with it, as capture would write them."""
    for step in new:
        last = steps[-1]
        steps.append({"version": 2, "id": f"step-{len(steps)}", "seq": len(steps), "trail": steps[0]["trail"], "at": last["at"],
                      **step, "prev": trail.digest(trail.canonical(last))})
    return steps


def explore(steps: list[dict], plan: str, command: str, exit_code: int = 0, outcome: str = "inconclusive", checked: bool = True) -> list[dict]:
    """A command and its observation, which names no metrics file: it measured nothing. Its one check is
    the plan's `runs` expectation, left out when the plan has none."""
    ran = trail.run(plan, command, [], "commit:notebook@3f9c2a1")
    settled = {"kind": "observation", "by": trail.RUNNER, "summary": f"exit {exit_code}", "exit_code": exit_code,
               "checks": [{"expectation": "runs", "held": exit_code == 0}] * checked, "outcome": "failed" if exit_code else outcome,
               "links": [{"relation": "observes", "target": f"step-{len(steps)}", "status": "confirmed"},
                         {"relation": "tests", "target": plan, "status": "confirmed"}]}
    if exit_code:
        settled["error"] = {"class": "exit"}
    return grow(steps, ran, settled)


LOOK = {"kind": "plan", "by": trail.AGENT, "summary": "Look at the data first", "reasoning": "List the files and count the rows.",
        "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"}]}


def test_exploratory_commands_are_counted_apart_from_attempts(churn):
    explore(churn, "step-4", "ls data")
    explore(churn, "step-4", "head data/missing.csv", exit_code=1)
    assert trail.check(churn) == []
    found = trail.facts(churn)
    assert "step-4: 1 run, 1 distinct result: step-5 as_expected" in found
    assert "step-4: 2 commands wrote no metrics, 1 failed" in found


def test_an_exploration_plan_gets_one_line_and_no_attempts(churn):
    grow(churn, LOOK)
    explore(churn, "step-8", "ls data", outcome="as_expected")
    explore(churn, "step-8", "wc -l data/missing.csv", exit_code=1)
    assert trail.check(churn) == []
    found = [fact for fact in trail.facts(churn) if fact.startswith("step-8:")]
    assert found == ["step-8: exploration, 2 commands, 1 failed"]


def test_a_plan_with_only_exploratory_runs_has_no_measured_run(churn):
    grow(churn, {**LOOK, "expectations": [{"name": "auc-floor", "measure": "auc", "comparison": "ge", "threshold": 0.75}]})
    explore(churn, "step-8", "ls data", checked=False)
    assert trail.check(churn) == []
    found = [fact for fact in trail.facts(churn) if fact.startswith("step-8:")]
    assert found == ["step-8: no measured run", "step-8: 1 command wrote no metrics"]


def test_repeats_consider_attempts_only(churn):
    explore(churn, "step-4", "ls data")
    explore(churn, "step-4", "ls data")
    assert trail.check(churn) == []
    assert not any("repeats" in fact for fact in trail.facts(churn))


def test_an_eased_threshold_is_stated(churn):
    churn[4]["expectations"][1]["threshold"] = 0.7
    rechain(churn, 5)
    assert trail.check(churn, EXAMPLES / "store") == []
    assert "step-4: eases auc from >= 0.75 to >= 0.7 after step-3 missed it" in trail.facts(churn)


def test_the_unchanged_churn_trail_eases_nothing(churn):
    assert not any("eases" in fact for fact in trail.facts(churn))


def copied(name: str, tmp_path: Path) -> Path:
    directory = tmp_path / name
    shutil.copytree(EXAMPLES / name, directory)
    return directory


@pytest.mark.parametrize("name", [CHURN, FEATURES, TUNING])
def test_a_review_and_a_note_leave_a_trail_that_checks_and_keeps_its_head(name, tmp_path):
    directory = copied(name, tmp_path)
    cited = trail.digest(trail.canonical(trail.load(directory)[-1]))
    assert cli("review", directory, "step-1", "--verdict", "disputes", "--text", "Too few seeds.", "--by", "reviewer").returncode == 0
    assert cli("note", directory, "step-0", "--text", "Read on the day.", "--by", "reviewer").returncode == 0
    steps = trail.load(directory)
    assert trail.check(steps, EXAMPLES / "store") == []
    assert trail.verify(steps, cited) == []
    review, note = steps[-2:]
    assert (review["kind"], review["by"], review["summary"], review["verdict"]) == ("review", "human:reviewer", "Disputes step-1", "disputes")
    assert review["links"] == [{"relation": "reviews", "target": "step-1", "status": "confirmed"}]
    assert (note["kind"], note["summary"], note["links"][0]["relation"]) == ("note", "Note on step-0", "about")


def test_a_review_after_a_step_dated_later_than_now_keeps_its_time(tmp_path):
    directory = copied(TUNING, tmp_path)
    last = trail.load(directory)[-1]["at"]
    step = trail.respond(trail.load(directory), "step-1", "reviewer", "Later.", "confirms")
    assert step["at"] >= last
    assert cli("review", directory, "step-1", "--verdict", "confirms", "--text", "Later.", "--by", "reviewer").returncode == 0
    assert trail.load(directory)[-1]["at"] >= last


def test_a_review_of_an_unknown_step_writes_nothing(tmp_path):
    directory = copied(CHURN, tmp_path)
    done = cli("review", directory, "step-99", "--verdict", "confirms", "--text", "Fine.", "--by", "reviewer")
    assert done.returncode == 1 and "step-99, which is not an earlier step" in done.stdout
    assert files(directory) == files(EXAMPLES / CHURN)


def test_a_note_on_a_broken_trail_writes_nothing(tmp_path):
    directory = copied(CHURN, tmp_path)
    broken = directory / "steps" / "step-4.json"
    broken.write_text(broken.read_text().replace("Reweight classes", "Boost"))
    before = files(directory)
    done = cli("note", directory, "step-4", "--text", "Fine.", "--by", "reviewer")
    assert done.returncode == 1 and files(directory) == before

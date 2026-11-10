"""The checker's guarantees on the example trails: they regenerate, they check, and a change to a
past step is caught, by the chain if it is left broken and by the cited head if it is re-chained."""

import copy
import json
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

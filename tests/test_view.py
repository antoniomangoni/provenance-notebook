"""What a reviewer reads: `why` answers from the links alone, and the page shows the same, escaped and
the same bytes each time. Changed trails are copies of the examples, re-chained as test_trail does."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import trail
import view

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
CHURN, FEATURES, TUNING = "churn-model-2026-11-11", "churn-features-2026-11-12", "churn-tuning-2026-11-13"


def cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "trail.py"), *map(str, args)], check=False, capture_output=True, text=True)


def rechain(steps: list[dict], start: int) -> None:
    for seq in range(start, len(steps)):
        steps[seq]["prev"] = trail.digest(trail.canonical(steps[seq - 1]))


def in_order(text: str, *parts: str) -> bool:
    at = 0
    for part in parts:
        at = text.find(part, at)
        if at < 0:
            return False
        at += len(part)
    return True


@pytest.fixture
def churn() -> list[dict]:
    return trail.load(EXAMPLES / CHURN)


def test_why_at_step_4_names_plan_trigger_miss_reasoning_and_review(churn):
    answer = "\n".join(view.why(churn, "step-4"))
    assert in_order(answer, "step-1", "step-3", "auc 0.58, expected >= 0.75 (auc-floor)", churn[4]["reasoning"], "step-7", "confirms")


def test_why_without_a_step_gives_one_line_per_change_of_approach(churn):
    assert view.why(churn) == ["At step-4 the plan changed: step-3 measured auc 0.58, expected >= 0.75."]
    assert view.why(trail.load(EXAMPLES / FEATURES)) == ["No plan was replaced."]


def test_why_on_the_trigger_names_the_change_it_caused(churn):
    (line,) = view.why(churn, "step-3")
    assert "observation" in line and "step-4" in line and "the trigger" in line


def test_why_on_an_unknown_step_exits_1():
    done = cli("why", EXAMPLES / CHURN, "step-99")
    assert done.returncode == 1 and "step-99 is not in this trail" in done.stdout
    done = cli("why", EXAMPLES / CHURN, "step-4")
    assert done.returncode == 0 and "auc 0.58, expected >= 0.75 (auc-floor)" in done.stdout


def test_why_reports_the_problems_of_a_trail_that_fails_check(tmp_path, churn):
    churn[4]["reasoning"] = "Boosting was always the plan."
    write(tmp_path, churn)
    done = cli("why", tmp_path, "step-4")
    assert done.returncode == 1 and "prev does not match step-4" in done.stdout


def write(directory: Path, steps: list[dict]) -> Path:
    (directory / "steps").mkdir(parents=True, exist_ok=True)
    for step in steps:
        (directory / "steps" / f"{step['id']}.json").write_text(json.dumps(step, indent=2) + "\n")
    return directory


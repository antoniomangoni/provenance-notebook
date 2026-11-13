"""What a reviewer reads: `why` answers from the links alone, and the page shows the same, escaped and
the same bytes each time. Changed trails are copies of the examples, re-chained as test_trail does."""

import html
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



FORBIDDEN = ("<script", "<link", "<img", "@import", "url(")


def card(page: str, plan: str) -> str:
    start = page.index(f'id="change-{plan}"')
    return page[start:page.index("</article>", start)]


def test_the_churn_page_shows_the_change_of_approach_in_its_card(churn):
    page = view.page(churn)
    assert in_order(card(page, "step-4"), "step-1", "step-3", html.escape("auc 0.58, expected >= 0.75 (auc-floor)"),
                    html.escape(churn[4]["reasoning"]), "step-7", "confirms")
    assert html.escape("At step-4 the plan changed: step-3 measured auc 0.58, expected >= 0.75.") in page
    assert not [construct for construct in FORBIDDEN if construct in page]


def test_step_text_is_escaped(churn):
    churn[4]["reasoning"] = "<script>alert(1)</script>"
    rechain(churn, 5)
    page = view.page(churn)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script" not in page


def test_one_trail_renders_to_the_same_bytes(churn, tmp_path):
    assert view.page(churn) == view.page(trail.load(EXAMPLES / CHURN))
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    assert cli("view", EXAMPLES / CHURN, "--out", first).returncode == 0
    assert cli("view", EXAMPLES / CHURN, "--store", EXAMPLES / "store", "--out", second).returncode == 0
    assert first.read_bytes() == second.read_bytes()


def test_an_exploratory_command_is_folded_away_and_off_the_decision_path(churn):
    last = churn[-1]
    ran = trail.run("step-4", "ls data", [], "commit:notebook@3f9c2a1")
    churn.append({"version": 2, "id": "step-8", "seq": 8, "trail": last["trail"], "at": last["at"], **ran,
                  "prev": trail.digest(trail.canonical(last))})
    churn.append({"version": 2, "id": "step-9", "seq": 9, "trail": last["trail"], "at": last["at"], "kind": "observation",
                  "by": trail.RUNNER, "summary": "exit 0", "exit_code": 0, "checks": [{"expectation": "runs", "held": True}],
                  "outcome": "inconclusive", "links": [{"relation": "observes", "target": "step-8", "status": "confirmed"}],
                  "prev": trail.digest(trail.canonical(churn[-1]))})
    assert trail.check(churn) == []
    page = view.page(churn)
    folded = page[page.index("<details>"):page.index("</details>")]
    assert "1 exploratory command, 0 failed" in folded and 'id="step-8"' in folded
    decision = page[page.index('id="decision-path"'):page.index("</section>", page.index('id="decision-path"'))]
    assert "step-8" not in decision and "step-9" not in decision


@pytest.mark.parametrize("name", [CHURN, FEATURES, TUNING])
def test_every_example_renders(name, tmp_path):
    out = tmp_path / "view.html"
    done = cli("view", EXAMPLES / name, "--out", out)
    assert done.returncode == 0
    page = out.read_text()
    assert page.startswith("<!doctype html>") and not [construct for construct in FORBIDDEN if construct in page]
    assert str(tmp_path) not in page and str(ROOT) not in page


def test_a_trail_that_fails_check_writes_no_page(churn, tmp_path):
    churn[4]["reasoning"] = "Boosting was always the plan."
    write(tmp_path, churn)
    assert cli("view", tmp_path).returncode == 1
    assert not (tmp_path / "view.html").exists()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def test_code_shows_the_diff_between_consecutive_measured_runs(churn, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "fit.py").write_text("weights = None\n")
    git(repo, "add", "fit.py")
    git(repo, "commit", "-qm", "baseline")
    before = git(repo, "rev-parse", "HEAD")
    (repo / "fit.py").write_text("weights = 'balanced'\n")
    git(repo, "commit", "-qam", "reweight")
    after = git(repo, "rev-parse", "HEAD")
    churn[2]["code"]["ref"] = f"commit:notebook@{before}"
    churn[5]["code"]["ref"] = f"commit:notebook@{after}"
    rechain(churn, 3)
    assert trail.check(churn) == []
    page = view.page(churn, repo)
    shown = page[page.index('id="step-5"'):]
    assert html.escape("+weights = 'balanced'") in shown and html.escape("-weights = None") in shown
    assert str(repo) not in page
    without = view.page(churn)
    assert f"Code changed from <code>commit:notebook@{before}</code> to <code>commit:notebook@{after}</code>" in without
    assert view.page(churn, tmp_path / "missing") == without


def test_a_long_diff_is_cut_with_the_count_left_out(churn, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "big.txt").write_text("")
    git(repo, "add", "big.txt")
    git(repo, "commit", "-qm", "empty")
    before = git(repo, "rev-parse", "HEAD")
    (repo / "big.txt").write_text("".join(f"line {n}\n" for n in range(500)))
    git(repo, "commit", "-qam", "big")
    churn[2]["code"]["ref"] = f"commit:{before}"
    churn[5]["code"]["ref"] = f"commit:{git(repo, 'rev-parse', 'HEAD')}"
    rechain(churn, 3)
    page = view.page(churn, repo)
    assert "+line 390" in page and "+line 499" not in page and "more lines left out" in page

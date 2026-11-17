"""Beliefs over the committed Madelon map: the noise arithmetic, the Markov blanket, the blindness of
what a forecaster is shown, and the scoring. Nothing under research/ or live/ is written."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import beliefs
import project

ROOT = Path(__file__).parent.parent
MAP = ROOT / "research" / "madelon-reanalysis" / "map"
LIVE = ROOT / "live"
FORECASTS = MAP.parent / "forecasts"


@pytest.fixture(scope="module")
def loaded():
    revs, trails = beliefs.load(MAP, str(LIVE))
    return revs, trails, beliefs.noise(MAP)


def test_the_standard_error_of_an_auc_is_hanley_and_mcneils():
    # By hand: A 0.8, 100 of each class: Q1 0.6667, Q2 0.7111, (0.16 + 99*0.0267 + 99*0.0711) / 10^4.
    assert beliefs.se_auc(0.8, 100, 100) == pytest.approx(0.03137, abs=5e-5)
    assert round(beliefs.se_auc(0.71, 1100, 1100), 4) == 0.0109


def test_the_declared_noise_is_what_the_held_out_file_gives():
    declared = beliefs.noise(MAP)["holdout_auc"]
    held_out = (ROOT / "demo" / "workspace" / "data" / "heldout.csv").read_text().splitlines()[1:]
    labels = [row.rsplit(",", 1)[1] for row in held_out]
    assert round(beliefs.se_auc(0.71, labels.count("1"), labels.count("-1")), 4) == declared["se"]


def test_the_blanket_of_an_open_milestone_is_its_parent_its_goal_and_its_siblings(loaded):
    revs, _, _ = loaded
    assert beliefs.blanket(revs[-1], "compact-boost") == {
        "parents": ["screen"],
        "children": ["goal:compact"],
        "co_parents": ["compact-forest", "compact-knn", "compact-stable-forest", "compact-svm", "compact-vote"],
    }
    # A shared milestone's children are the next milestones of every route through it.
    assert beliefs.blanket(revs[-1], "nested")["children"] == ["floor-l1", "floor-search", "floor-selected-forest", "goal:explain"]


def test_a_goal_reached_by_one_of_several_routes_says_how_sure_that_is(loaded):
    text = "\n".join(beliefs.show(*loaded))
    assert "✓ compact: 2 of 4 scored routes credited" in text
    assert "P(at least one credited route truly meets it): 0.80 (errors shared) to 0.92 (independent)" in text
    assert "✗ compact-knn: holdout_auc >= 0.71, measured 0.709: -0.09 SE, P 0.46, within noise" in text
    assert "P(reached) 0.49: holdout_auc of 4 co-parents: mean 0.7098" in text


def test_no_question_shows_the_run_that_settles_it(loaded):
    revs, trails, _ = loaded
    milestones, excluded = beliefs.milestone_questions(revs, trails)
    plans, _ = beliefs.plan_questions(trails)
    settled = [q for q in milestones + plans if "settled_by" in q]
    assert len(settled) == 22 and len(milestones) - 8 == len(project.ranked(revs[-1]))
    for question in settled:
        name, step = question["settled_by"].split(":", 1)[1].split("#")
        assert f"{name} {step}" not in question["_text"] and f"{step} observation" not in question["_text"]
        if question["kind"] == "milestone":
            assert question["settled_by"] not in beliefs.milestone_prompt(revs[question["rev"]], question["node"], trails)[1]
    # The one way the map could leak an outcome, a credit moved from one milestone to another, is caught.
    assert any("withdrawn later" in line for line in excluded)


def test_a_plan_question_ends_at_the_plan(loaded):
    _, trails, _ = loaded
    steps = next(s for p, s in trails.steps.items() if p.endswith("madelon-route-knn"))
    text = beliefs.plan_prompt(steps, "step-28")
    assert "step-28 plan (the plan in question)" in text
    assert "step-29 " not in text and "0.709" not in text


def forecast_file(tmp_path: Path, change) -> Path:
    kept = json.loads((FORECASTS / "gemma-backtest.json").read_text())
    change(kept)
    path = tmp_path / "f.json"
    path.write_text(json.dumps(kept))
    return path


def test_a_forecast_that_saw_other_text_is_refused(loaded, tmp_path):
    def tamper(kept):
        kept["forecasts"][0]["saw"] = "sha256:" + "0" * 64

    _, errors = beliefs.score(*loaded, [forecast_file(tmp_path, tamper)])
    assert errors == ["f.json: reproduce at rev-0 saw text the map and trails do not give now"]


def test_a_forecast_of_a_milestone_already_resolved_is_refused(loaded, tmp_path):
    def resolved(kept):
        kept["forecasts"][0]["rev"] = 5

    _, errors = beliefs.score(*loaded, [forecast_file(tmp_path, resolved)])
    assert errors == ["f.json: reproduce at rev-5 is not a question of this map"]


def test_an_unanswered_question_is_not_scored_as_an_even_chance(loaded, tmp_path):
    def unanswer(kept):
        for forecast in kept["forecasts"]:
            if forecast["kind"] == "plan":
                forecast["p"] = None
                break

    lines, errors = beliefs.score(*loaded, [forecast_file(tmp_path, unanswer)])
    assert not errors
    assert "  1 questions unanswered: no probability could be read, so they are not scored" in lines
    assert "  plan questions settled: 13 (backtest); held 8" in lines


def test_a_forecast_at_an_earlier_revision_is_scored_by_the_first_resolution_after_it(loaded):
    revs, trails, _ = loaded
    text, _ = beliefs.milestone_prompt(revs[7], "compact-vote", trails)
    later = beliefs.rebuild_open({"kind": "milestone", "node": "compact-vote", "rev": 7}, revs, trails)
    assert later["saw"] == beliefs.saw(text) and later["holds"] is True and later["settled_by"].endswith("#step-26")
    open_still = beliefs.rebuild_open({"kind": "milestone", "node": "floor-l1", "rev": 5}, revs, trails)
    assert "holds" not in open_still


@pytest.mark.parametrize(
    "answer, p",
    [("p: 0.7\nwhy: x", 0.7), ("**p:** 0.25\n**why:** x", 0.25), ("p: 1\nwhy: x", 1.0), ("p: 70%\nwhy: x", None), ("I think 0.7", None)],
)
def test_only_a_probability_in_the_asked_form_is_read(answer, p):
    assert beliefs.parse_answer(answer)[0] == p


@pytest.mark.parametrize("command, committed", [("show", MAP.parent / "beliefs.txt"), ("score", FORECASTS / "scores.txt")])
def test_a_committed_belief_output_equals_a_rebuild(command, committed):
    done = subprocess.run(
        [sys.executable, str(ROOT / "beliefs.py"), command, str(MAP), "--live", str(LIVE)],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert done.stdout == committed.read_text()


def test_a_plan_asked_after_its_trail_opened_a_sealed_input_is_marked(loaded):
    revs, trails, _ = loaded
    plans, _ = beliefs.plan_questions(trails, revs[-1]["sealed_inputs"])
    final = next(q for q in plans if q["trail"] == "madelon-route-screened-forest" and q["step"] == "step-43")
    # step-41 scored the held-out file on three seeds, and step-43's reasoning quotes what it printed.
    assert "step-41" in final["after_sealed"] and "holdout 0.7300-0.7320" in final["_text"]
    first = next(q for q in plans if q["trail"] == "madelon-route-knn" and q["step"] == "step-28")
    assert first["after_sealed"] == []


def test_a_milestone_question_whose_outcome_was_known_is_marked(loaded):
    revs, trails, _ = loaded
    milestones, _ = beliefs.milestone_questions(revs, trails)
    known = {q["node"]: q["known"] for q in milestones if "holds" in q}
    # rev-0 was written the day after the first trail ran, so its three milestones were never forecasts.
    assert known["reproduce"] == known["miss"] == known["nested"] == ["its run was made before rev-0 was written"]
    # screen was credited after the milestones that follow it, whose runs had shown its measures.
    assert known["screen"] == ["compact-forest, compact-knn, after it on a route, already resolved"]
    assert [node for node, why in known.items() if not why] == ["compact-knn", "compact-forest", "compact-stable-forest", "compact-vote"]


def test_marked_questions_are_scored_apart_and_a_coin_flip_is_a_forecaster(loaded):
    lines, errors = beliefs.score(*loaded, [FORECASTS / "gemma-backtest.json"])
    assert not errors
    text = "\n".join(lines)
    assert "    ‡ 4 of 8: the outcome was known" in text
    assert "      on the other 4: agent:pi/google/gemma-4-31B-it Brier 0.433; code:even Brier 0.250;" in text
    assert "    code:base-rate: Brier 0.311, log loss 1.274 bits, n 8; the forecaster is -0.065 ± 0.151 from it, within noise" in text


def test_a_difference_in_score_comes_with_its_standard_error():
    # Differences -0.1 and +0.1: mean 0, standard deviation 0.1414, over the root of 2.
    assert beliefs.against([0.1, 0.3], [0.2, 0.2]) == "; the forecaster is +0.000 ± 0.100 from it, within noise"
    assert beliefs.against([0.0, 0.01, 0.0, 0.01], [0.5, 0.5, 0.5, 0.5]) == "; the forecaster is -0.495 ± 0.003 from it"
    assert beliefs.against([0.1], [0.2]) == ""


def test_the_pooled_forecast_reads_the_same_criterion_across_the_map(loaded):
    revs, trails, sizes = loaded
    # The floor milestones' blanket holds one score; the map holds five on the same criterion.
    p, how = beliefs.pooled_predictive(revs[-1], "floor-l1", trails, sizes)
    assert round(p, 2) == 0.59 and how.startswith("holdout_auc of 5 milestones with the same criterion: mean 0.7122")
    assert round(beliefs.predictive(revs[-1], "floor-l1", trails, sizes)[0], 2) == 0.75
    assert beliefs.pooled_predictive(revs[0], "miss", trails, sizes) == (0.5, "the base rate of the revision's resolutions")


def test_a_forecast_made_before_its_outcome_is_not_called_a_backtest(loaded, tmp_path):
    def earlier(kept):
        kept["at"] = "2026-11-01T00:00:00Z"

    lines, _ = beliefs.score(*loaded, [forecast_file(tmp_path, earlier)])
    assert "  milestone questions settled: 8 (forecast); held 6" in lines

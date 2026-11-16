"""The research map's rules, on the committed Madelon map's first two revisions and the two live
trails they cite. Every test works on copies; nothing under research/ or live/ is written."""

import copy
import json
import shutil
from pathlib import Path

import pytest

import project
import tamper
import trail

ROOT = Path(__file__).parent.parent
MAP = ROOT / "research" / "madelon-reanalysis" / "map"
LIVE1, LIVE2 = ROOT / "live" / "madelon-2026-11-15-1", ROOT / "live" / "madelon-2026-11-15-2"
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def first_two() -> list[dict]:
    return project.revisions(MAP)[:2]


def trails(*paths: Path) -> project.Trails:
    return project.Trails(list(paths or (LIVE1, LIVE2)))


def ref(path: Path, step: str) -> str:
    steps = trail.load(path)
    return f"probe:{steps[0]['trail']}@{trail.digest(trail.canonical(steps[-1]))}#{step}"


def alone(revision: dict) -> list[dict]:
    """A revision checked as if it were the first, so one change needs no re-chaining."""
    changed = copy.deepcopy(revision)
    changed.pop("prev", None)
    changed["rev"], changed["_file"] = 0, "rev-0.json"
    return [changed]


def test_the_committed_map_checks_against_the_trails_it_cites():
    assert project.check(first_two(), trails()) == []


def test_a_revision_changed_after_it_was_sealed_breaks_the_chain():
    revs = first_two()
    revs[0]["reason"] += " Edited later."
    assert project.check(revs, trails()) == ["rev-1: prev does not match rev-0, so a revision changed after it was sealed"]


def test_a_missing_revision_is_found():
    errors = project.check(first_two()[1:], trails())
    assert errors == ["rev-1.json: expected rev 0; a revision is missing or misnumbered"]


def test_a_route_through_an_unknown_node_a_goal_without_a_route_and_a_node_on_no_route_fail():
    revision = alone(first_two()[0])
    revision[0]["routes"][0]["path"].append("nowhere")
    revision[0]["goals"].append({"id": "unreached", "statement": "Nothing aims here"})
    revision[0]["nodes"].append(
        {"id": "orphan", "statement": "On no route", "criteria": [{"name": "x", "measure": "x", "comparison": "ge", "threshold": 1}]}
    )
    errors = project.check(revision, trails())
    assert "rev-0: route explain passes nowhere, which is not a node" in errors
    assert "rev-0: goal unreached has no route" in errors
    assert "rev-0: node orphan is on no route" in errors


def test_a_resolution_must_agree_with_the_measures_it_cites():
    revision = alone(first_two()[1])
    floor = next(r for r in revision[0]["resolutions"] if r["node"] == "floor-forest")
    floor["holds"] = False
    errors = project.check(revision, trails())
    assert errors == ["rev-0: resolution of floor-forest says it does not hold, but step-19's measures say otherwise"]


def test_a_resolution_where_the_criteria_miss_cannot_claim_the_node():
    revision = alone(first_two()[1])
    # live-2 step-7 is the inherited analysis: holdout_auc 0.5639, below the floor-forest criteria.
    revision[0]["resolutions"].append({"node": "floor-forest", "cites": ref(LIVE2, "step-7"), "holds": True})
    assert project.check(revision, trails()) == ["rev-0: resolution of floor-forest says it holds, but step-7's measures say otherwise"]


def test_a_resolution_must_cite_an_observation_of_a_given_trail_at_a_head_it_had():
    base = alone(first_two()[1])
    unknown_head = ref(LIVE2, "step-19").split("@")[0] + "@sha256:" + "0" * 64 + "#step-19"
    assert project.check(_with(base, "floor-forest", unknown_head), trails()) == [
        f"rev-0: resolution of floor-forest: {unknown_head} cites a head madelon-reanalysis/probe:madelon-2026-11-15-2 never had, so it changed after it was cited"
    ]
    assert project.check(_with(base, "floor-forest", ref(LIVE2, "step-18")), trails()) == [
        "rev-0: resolution of floor-forest cites step-18, a run, not an observation"
    ]
    assert any("not among the trails given" in error for error in project.check(base, trails(LIVE1)))


def _with(revision: list[dict], node: str, cites: str) -> list[dict]:
    changed = copy.deepcopy(revision)
    next(r for r in changed[0]["resolutions"] if r["node"] == node)["cites"] = cites
    return changed


def test_a_criterion_whose_measure_the_observation_lacks_fails():
    revision = alone(first_two()[1])
    revision[0]["resolutions"].append({"node": "screen", "cites": ref(LIVE2, "step-19"), "holds": True})
    assert project.check(revision, trails()) == ["rev-0: resolution of screen: step-19 has no n_features"]


def test_the_live_trails_reach_explain_and_floor_and_leave_compact_open():
    now = project.state(first_two()[1])
    assert now["reached"] == {"reproduce", "miss", "nested", "floor-l1", "floor-forest"}
    assert now["goals"] == {"explain": True, "floor": True, "compact": False}
    assert {route: kept["status"] for route, kept in now["routes"].items()} == {
        "explain": "done",
        "l1": "done",
        "forest": "done",
        "knn": "open",
        "screened-forest": "open",
        "svm": "open",
    }


def test_a_refuted_node_blocks_every_route_through_it_and_next_leaves_them_out():
    revision = copy.deepcopy(first_two()[1])
    revision["resolutions"].append({"node": "screen", "cites": "probe:x@sha256:0#step-1", "holds": False})
    now = project.state(revision)
    assert now["refuted"] == {"screen"}
    assert {now["routes"][route]["status"] for route in ("knn", "screened-forest", "svm")} == {"blocked"}
    assert project.ranked(revision) == []


def test_next_ranks_a_node_shared_by_three_open_routes_above_one_on_a_single_route():
    revision = copy.deepcopy(first_two()[1])
    revision["nodes"].append(
        {"id": "lone", "statement": "Only one route", "criteria": [{"name": "x", "measure": "x", "comparison": "ge", "threshold": 1}]}
    )
    revision["routes"].append({"id": "lone-route", "goal": "compact", "method": "alone", "path": ["lone"], "status": "open"})
    rows = project.ranked(revision)
    assert [(row["node"], row["leads"]) for row in rows] == [("screen", ["knn", "screened-forest", "svm"]), ("lone", ["lone-route"])]


def tagged(tmp_path: Path, route: str) -> Path:
    """live-2 as a briefed route's trail would be: step 0's summary names the route, and the chain is
    recomputed so the copy checks."""
    copy_of = tmp_path / "madelon-tagged"
    steps = trail.load(LIVE2)
    steps[0]["summary"] = f"Route {route}: {steps[0]['summary']}"[:200]
    for step in steps:
        step["trail"] = "madelon-tagged"
    tamper.rechain(steps, 1)
    tamper.write(copy_of, steps)
    assert trail.check(trail.load(copy_of)) == []
    return copy_of


def test_propose_walks_a_route_tagged_trail_against_its_own_route_only(tmp_path):
    draft = project.propose(first_two()[:1], trails(tagged(tmp_path, "forest")))
    found = [(c["node"], c["cites"].split("#")[1], c["routes"], c["holds"]) for c in draft["candidates"]]
    # One observation, the inherited run's, meets reproduce and then miss: the walk moves on.
    assert found == [
        ("reproduce", "step-7", ["forest"], True),
        ("miss", "step-7", ["forest"], True),
        ("floor-forest", "step-19", ["forest"], True),
    ]


def test_propose_on_an_untagged_trail_lists_every_route_a_candidate_could_serve():
    draft = project.propose(first_two()[:1], trails(LIVE2))
    first = draft["candidates"][0]
    assert (first["node"], first["routes"]) == ("reproduce", ["explain", "l1", "forest", "knn", "screened-forest", "svm"])


def test_seal_refuses_a_draft_with_candidates_and_chains_one_without():
    revs = first_two()[:1]
    draft = project.propose(revs, trails())
    assert project.seal(revs, draft, "agent:test", "2026-11-16T12:00:00Z", trails())[1][0].startswith("the draft still has candidates")
    accepted = {key: value for key, value in project.sealed(first_two()[1]).items() if key not in project.SEALED}
    revision, errors = project.seal(revs, accepted, "agent:test", "2026-11-16T12:00:00Z", trails())
    assert errors == []
    assert (revision["rev"], revision["prev"]) == (1, project.digest(revs[0]))


@needs_git
def test_shared_finds_the_inherited_run_repeated_in_both_trails():
    lines = project.shared(first_two()[1], trails())
    assert "  uv run python analysis.py: madelon-2026-11-15-1 step-7, madelon-2026-11-15-2 step-6" in lines
    assert "  screen: on knn, screened-forest, svm; reached by none yet" in lines


@needs_git
def test_brief_cites_what_the_route_has_reached_and_starts_from_its_code(tmp_path):
    record = project.brief(first_two()[1], "knn", trails(), ROOT / "demo", tmp_path / "knn")
    task = json.loads((tmp_path / "knn" / "task.json").read_text())
    # The newest resolution of miss, the last node reached before screen, is live-2's inherited run.
    assert task["builds_on"] == record["builds_on"] == [ref(LIVE2, "step-7")]
    assert task["summary"].startswith("Route knn: ") and task["declared_measures"][-1] == "n_features"
    inherited = {
        str(p.relative_to(ROOT / "demo" / "workspace")): trail.digest(p.read_bytes())
        for p in sorted((ROOT / "demo" / "workspace").rglob("*"))
        if p.is_file() and not {"out", ".venv"} & set(p.parts)
    }
    assert record["workspace"] == inherited
    prompt = (tmp_path / "knn" / "prompt.md").read_text()
    assert "n_features <= 50, cv_auc >= 0.7" in prompt and "do not recompute them" in prompt
    with pytest.raises(project.Usage, match="not an open route"):
        project.brief(first_two()[1], "forest", trails(), ROOT / "demo", tmp_path / "forest")


def test_graph_adds_the_map_to_the_merged_trails():
    revision = first_two()[1]
    nodes, edges, errors = project.graph(revision, trails())
    merged_nodes, merged_edges, _ = trail.merge([trail.load(LIVE1), trail.load(LIVE2)])
    assert errors == [] and edges[: len(merged_edges)] == merged_edges and nodes[: len(merged_nodes)] == merged_nodes
    kinds = {node["id"]: node["kind"] for node in nodes}
    assert kinds["madelon-reanalysis/milestone:screen"] == "milestone" and kinds["madelon-reanalysis/route:knn"] == "route"
    resolved = [edge for edge in edges if edge["relation"] == "resolved_by"]
    assert len(resolved) == sum(r["holds"] for r in revision["resolutions"])
    assert {
        "source": "madelon-reanalysis/milestone:floor-forest",
        "relation": "resolved_by",
        "target": "madelon-reanalysis/probe:madelon-2026-11-15-2#step-19",
        "status": "confirmed",
        "digest": ref(LIVE2, "step-19").split("@")[1].split("#")[0],
        "graph": "madelon-reanalysis/map:rev-1",
    } in resolved


def test_the_command_line_checks_and_refuses_what_it_does_not_know(tmp_path, capsys):
    for revision in first_two():
        (tmp_path / revision["_file"]).write_text(json.dumps(project.sealed(revision)))
    assert project.main(["project.py", "check", str(tmp_path), "--trails", str(LIVE1), str(LIVE2)]) == 0
    assert "ok: 2 revisions, 8 resolutions, 2 trails" in capsys.readouterr().out
    assert project.main(["project.py", "check", str(tmp_path), "--nope"]) == 2
    assert project.main(["project.py", "view", str(tmp_path), "--trails", str(LIVE1)]) == 1

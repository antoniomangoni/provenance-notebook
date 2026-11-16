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


ROUTE1 = ROOT / "live" / "madelon-route-screened-forest"


def head_ref(path: Path, step: str) -> str:
    steps = trail.load(path)
    return f"probe:{steps[0]['trail']}@{trail.digest(trail.canonical(steps[-1]))}#{step}"


def sealed(revision: dict, *resolutions: dict) -> dict:
    changed = copy.deepcopy(revision) | {"sealed_inputs": ["data/heldout.csv"]}
    changed["resolutions"] = [*changed["resolutions"], *resolutions]
    return changed


def test_without_traces_the_command_line_is_the_only_lead():
    hit = {"node": "compact-forest", "cites": head_ref(ROUTE1, "step-45"), "holds": True}
    peeked = dict(project.peeks(sealed(first_two()[1], hit), trails(LIVE1, LIVE2, ROUTE1), hit))
    # step-38 and step-41 name the held-out file in their heredoc scripts; step-44, the cited run, is left out.
    assert peeked["step-38"] == peeked["step-41"] == "names" and "step-44" not in peeked


def test_a_re_execution_replaces_the_command_line_and_is_labelled_as_such(tmp_path):
    hit = {"node": "compact-forest", "cites": head_ref(ROUTE1, "step-45"), "holds": True}
    steps = trail.load(ROUTE1)
    replay = {
        "trail": trail.probe_id(steps),
        "head": trail.digest(trail.canonical(steps[-1])),
        "runs": [
            {"run": "step-38", "reads": [{"ref": "file:data/heldout.csv", "digest": "sha256:" + "0" * 64}]},
            {"run": "step-41", "reads": [{"ref": "file:data/pilot.csv", "digest": "sha256:" + "0" * 64}]},
        ],
    }
    (tmp_path / "replay.json").write_text(json.dumps(replay))
    given = project.Trails([LIVE1, LIVE2, ROUTE1], [tmp_path / "replay.json"])
    peeked = dict(project.peeks(sealed(first_two()[1], hit), given, hit))
    assert peeked["step-38"] == "read on re-execution" and "step-41" not in peeked
    revision = alone(sealed(first_two()[1], hit))
    assert project.check(revision, given) == []
    (tmp_path / "other.json").write_text(json.dumps(replay | {"head": "sha256:" + "1" * 64}))
    assert any(
        "at a head it never had" in error
        for error in project.check(revision, project.Trails([LIVE1, LIVE2, ROUTE1], [tmp_path / "other.json"]))
    )


def test_a_captured_read_of_a_sealed_input_before_a_holding_resolution_fails_check(tmp_path):
    copy_of = tmp_path / "route"
    steps = trail.load(ROUTE1)
    next(s for s in steps if s["id"] == "step-39")["reads"] = [{"ref": "file:data/heldout.csv", "digest": "sha256:" + "0" * 64}]
    tamper.rechain(steps, 40)
    tamper.write(copy_of, steps)
    hit = {"node": "compact-forest", "cites": head_ref(copy_of, "step-45"), "holds": True}
    errors = project.check(alone(sealed(first_two()[1], hit)), trails(LIVE1, LIVE2, copy_of))
    assert errors == ["rev-0: resolution of compact-forest: step-38 read a sealed input before step-45's run"]


def test_a_revision_s_instructions_reach_every_brief_and_must_be_text(tmp_path):
    revision = copy.deepcopy(first_two()[1]) | {"instructions": "Score the held-out file once."}
    project.brief(revision, "knn", trails(), ROOT / "demo", tmp_path / "knn")
    assert "Rules for every route of this map:\nScore the held-out file once." in (tmp_path / "knn" / "prompt.md").read_text()
    assert "rev-0: instructions must be text of at most 4,000 characters" in project.check(alone(revision | {"instructions": ""}), trails())


def test_propose_flags_a_hit_that_came_after_misses_of_the_same_node():
    revs = project.revisions(MAP)[:4]
    draft = project.propose(revs, trails(LIVE1, LIVE2, ROUTE1, ROOT / "live" / "madelon-route-knn"))
    (hit,) = [c for c in draft["candidates"] if c["node"] == "compact-knn"]
    assert (hit["cites"].split("#")[1], hit["holds"], hit["after_misses"]) == ("step-40", True, ["step-30"])


# ---------------------------------------------------------------------------------------------
# The live state (spec 7)

ALL = [LIVE1, LIVE2, ROUTE1, ROOT / "live" / "madelon-route-knn", ROOT / "live" / "madelon-route-svm"]


def test_the_live_state_agrees_with_the_view_on_the_committed_map():
    revs = project.revisions(MAP)
    live = project.live_state(revs, trails(*ALL))
    now = project.state(revs[-1])
    assert {n["id"]: n["state"] for n in live["nodes"]} == {n["id"]: project.node_state(n["id"], now) for n in revs[-1]["nodes"]}
    assert {r["id"]: r["status"] for r in live["routes"]} == {k: v["status"] for k, v in now["routes"].items()}
    assert [t["trail"] for t in live["trails"]] == [p.name for p in ALL]
    assert all(r["sealed"] for n in live["nodes"] for r in n["resolutions"])


def test_what_a_trail_meets_before_it_is_sealed_is_provisional_and_changes_no_state():
    revs = first_two()
    live = project.live_state(revs, trails(LIVE1, LIVE2, ROUTE1))
    screen = next(n for n in live["nodes"] if n["id"] == "screen")
    assert screen["state"] == "open" and screen["resolutions"] == []
    assert screen["provisional"] and all(not r["sealed"] for r in screen["provisional"])
    assert screen["provisional"][0]["probe"] == trail.probe_id(trail.load(ROUTE1))


def test_an_agent_is_not_shown_a_sibling_s_numbers_from_a_run_that_opened_a_sealed_input(tmp_path):
    copy_of = tmp_path / "madelon-route-screened-forest"
    steps = trail.load(ROUTE1)
    next(s for s in steps if s["id"] == "step-39")["reads"] = [{"ref": "file:data/heldout.csv", "digest": "sha256:" + "0" * 64}]
    tamper.rechain(steps, 40)
    tamper.write(copy_of, steps)
    revs = [sealed(r) for r in first_two()]
    given = trails(LIVE2, copy_of)
    other = project.live_state(revs, given, for_probe=trail.probe_id(trail.load(LIVE2)))
    lane = next(t for t in other["trails"] if t["trail"] == "madelon-route-screened-forest")
    step39 = next(s for s in lane["steps"] if s["id"] == "step-39")
    assert step39["withheld"] and step39["measures"] == {} and step39["summary"] == project.WITHHELD
    text = "\n".join(project.status_text(other, project.datetime.now(project.UTC), refs_per_trail=50))
    assert "step-39: " + project.WITHHELD in text
    own = project.live_state(revs, given, for_probe=trail.probe_id(steps))
    lane = next(t for t in own["trails"] if t["trail"] == "madelon-route-screened-forest")
    mine = next(s for s in lane["steps"] if s["id"] == "step-39")
    assert not mine["withheld"] and mine["summary"] == "as expected"


def test_discovery_takes_the_trails_of_the_map_s_project_only(tmp_path):
    shutil.copytree(LIVE2, tmp_path / "ours")
    shutil.copytree(LIVE1, tmp_path / "theirs")
    task = json.loads((tmp_path / "theirs" / "steps" / "step-0.json").read_text()) | {"project": "elsewhere"}
    (tmp_path / "theirs" / "steps" / "step-0.json").write_text(json.dumps(task))
    (tmp_path / "empty").mkdir()
    assert project.discover(tmp_path, "madelon-reanalysis") == [tmp_path / "ours"]


def test_a_trail_ending_in_a_half_written_step_is_kept_and_marked_reading(tmp_path):
    shutil.copytree(LIVE2, tmp_path / "t")
    count = len(trail.load(LIVE2))
    (tmp_path / "t" / "steps" / f"step-{count}.json").write_text('{"version": 2, "id": "st')
    given = project.Trails([tmp_path / "t"])
    probe = trail.probe_id(trail.load(LIVE2))
    assert len(given.steps[probe]) == count and probe in given.reading
    lane = project.live_state(first_two(), given)["trails"][0]
    assert lane["reading"] and lane["problems"] == []


def test_a_second_seal_of_the_same_revision_fails(tmp_path, monkeypatch, capsys):
    shutil.copytree(MAP, tmp_path / "map")
    for extra in sorted((tmp_path / "map").glob("rev-*.json"))[2:]:
        extra.unlink()
    draft = {k: v for k, v in project.sealed(first_two()[1]).items() if k not in project.SEALED} | {"reason": "A test."}
    (tmp_path / "draft.json").write_text(json.dumps(draft))
    stale = project.revisions(tmp_path / "map")
    monkeypatch.setattr(project, "revisions", lambda _: [dict(r) for r in stale])
    argv = [
        "project.py",
        "seal",
        str(tmp_path / "map"),
        str(tmp_path / "draft.json"),
        "--by",
        "agent:test",
        "--trails",
        str(LIVE1),
        str(LIVE2),
    ]
    assert project.main(argv) == 0
    assert project.main(argv) == 1
    assert "rev-2 was sealed meanwhile; propose again" in capsys.readouterr().out


def test_a_step_a_revision_has_judged_is_not_proposed_again():
    revs = project.revisions(MAP)
    judged = {r["cites"].split("@")[0] + "#" + r["cites"].split("#")[1] for rev in revs for r in rev["resolutions"]}
    proposed = project.propose(revs, trails(*ALL))["candidates"]
    assert not [c for c in proposed if c["cites"].split("@")[0] + "#" + c["cites"].split("#")[1] in judged]
    # floor-search, withdrawn in rev-6, cited live-1 step-18; it stays withdrawn.
    assert not [c for c in proposed if c["node"] == "floor-search"]


def test_a_captured_sealed_read_passes_check_only_when_the_revision_excuses_it_and_says_why(tmp_path):
    copy_of = tmp_path / "route"
    steps = trail.load(ROUTE1)
    next(s for s in steps if s["id"] == "step-39")["reads"] = [{"ref": "file:data/heldout.csv", "digest": "sha256:" + "0" * 64}]
    tamper.rechain(steps, 40)
    tamper.write(copy_of, steps)
    given = trails(LIVE1, LIVE2, copy_of)
    ref = head_ref(copy_of, "step-45")
    excused = {"node": "compact-forest", "cites": ref, "holds": True, "excused": [{"run": "step-38", "why": "It counted rows."}]}
    assert project.check(alone(sealed(first_two()[1], excused)), given) == []
    idle = excused | {"excused": [*excused["excused"], {"run": "step-41", "why": "Nothing."}]}
    assert project.check(alone(sealed(first_two()[1], idle)), given) == [
        "rev-0: resolution of compact-forest: excuses step-41, which did not read a sealed input before step-45's run"
    ]
    unsaid = excused | {"excused": [{"run": "step-38", "why": ""}]}
    assert "excused is a list of runs" in project.check(alone(sealed(first_two()[1], unsaid)), given)[0]
    view_lines = "\n".join(project.show(sealed(first_two()[1], excused), given))
    assert "step-38 read (excused: It counted rows.)" in view_lines


def test_an_agent_is_not_shown_that_a_sibling_met_a_milestone_by_a_run_that_opened_a_sealed_input(tmp_path):
    copy_of = tmp_path / "madelon-route-screened-forest"
    steps = trail.load(ROUTE1)
    next(s for s in steps if s["id"] == "step-15")["reads"] = [{"ref": "file:data/heldout.csv", "digest": "sha256:" + "0" * 64}]
    tamper.rechain(steps, 16)
    tamper.write(copy_of, steps)
    revs = [sealed(r) for r in first_two()]
    everyone = project.live_state(revs, trails(LIVE2, copy_of))
    assert any(r["step"] == "step-15" for n in everyone["nodes"] for r in n["provisional"])
    agent = project.live_state(revs, trails(LIVE2, copy_of), for_probe=trail.probe_id(trail.load(LIVE2)))
    assert not any(r["step"] == "step-15" for n in agent["nodes"] for r in n["provisional"])


# ---------------------------------------------------------------------------------------------
# What a credit rests on, and recorded withdrawals (spec 8)

LIVE = ROOT / "live"


def everything() -> project.Trails:
    return project.Trails(project.discover(LIVE, "madelon-reanalysis"), beside=MAP.parent)


def probe(name: str) -> str:
    return f"madelon-reanalysis/probe:{name}"


def test_a_step_rests_on_what_its_trail_built_on_in_other_trails_and_on_what_those_rest_on():
    given = everything()
    # vote's plans at step-13 and step-23 build on the first fleet's vote step-21; its task builds on live-2 step-7.
    assert project.upstream(given, probe("madelon-fleet2-vote"), 26, "madelon-reanalysis") == {
        probe("madelon-fleet-vote"): 21,
        probe("madelon-2026-11-15-2"): 7,
    }
    # boost built on vote and stable-forest, so it rests on what they rest on too.
    boost = project.upstream(given, probe("madelon-fleet2-boost"), 25, "madelon-reanalysis")
    assert boost[probe("madelon-fleet2-vote")] == 22 and boost[probe("madelon-fleet-vote")] == 21
    # Before it built on anyone, boost rested only on its task's citation.
    assert project.upstream(given, probe("madelon-fleet2-boost"), 3, "madelon-reanalysis") == {probe("madelon-2026-11-15-2"): 7}


def test_a_head_without_a_step_rests_on_the_step_that_head_ended_at(tmp_path):
    vote = trail.load(LIVE / "madelon-fleet2-vote")
    head = trail.digest(trail.canonical(vote[22]))
    copy_of = tmp_path / "madelon-fleet2-boost"
    steps = trail.load(LIVE / "madelon-fleet2-boost")
    steps[15]["links"] = [
        {**link, "target": f"probe:madelon-fleet2-vote@{head}"} if link["relation"] == "builds_on" else link for link in steps[15]["links"]
    ]
    tamper.rechain(steps, 16)
    tamper.write(copy_of, steps)
    given = project.Trails([LIVE / "madelon-fleet2-vote", copy_of, LIVE2])
    assert project.upstream(given, probe("madelon-fleet2-boost"), 15, "madelon-reanalysis")[probe("madelon-fleet2-vote")] == 22


def as_version_2(revision: dict) -> list[dict]:
    changed = alone(revision)
    changed[0]["version"] = 2
    return changed


def test_version_2_judges_sealed_reads_in_other_trails_a_credit_rests_on():
    rev9 = project.revisions(MAP)[9]
    given = everything()
    assert project.check(alone(rev9), given) == []  # version 1: the cited trail only
    errors = project.check(as_version_2(rev9), given)
    said = "rev-0: resolution of compact-vote: madelon-fleet-vote#step-5 read a sealed input before step-26's run"
    assert said in errors
    excused = copy.deepcopy(rev9)
    vote = next(r for r in excused["resolutions"] if r["node"] == "compact-vote")
    vote["excused"].append({"run": "madelon-fleet-vote#step-5", "why": "It counted rows."})
    assert said not in project.check(as_version_2(excused), given)
    view_lines = "\n".join(project.show(as_version_2(excused)[0], given))
    assert "madelon-fleet-vote#step-5 read (excused: It counted rows.)" in view_lines
    assert "rests on madelon-2026-11-15-2 to step-7, madelon-fleet-vote to step-21" in view_lines


def test_a_version_2_revision_says_why_it_drops_a_resolution_and_names_only_what_it_drops():
    revs = copy.deepcopy(project.revisions(MAP)[:7])  # rev-6 dropped screen and floor-search
    revs[6]["version"] = 2
    given = everything()
    errors = project.check(revs, given)
    dropped = [e for e in errors if "without saying why in withdrawn" in e]
    assert len(dropped) == 2 and any("resolution of screen by" in e for e in dropped)
    gone = {(r["node"], project.unpinned(r["cites"])) for r in revs[5]["resolutions"]} - {
        (r["node"], project.unpinned(r["cites"])) for r in revs[6]["resolutions"]
    }
    full = {project.unpinned(r["cites"]): r["cites"] for r in revs[5]["resolutions"]}
    revs[6]["withdrawn"] = [{"node": node, "cites": full[ref], "why": "The trace showed a held-out read."} for node, ref in sorted(gone)]
    assert not [e for e in project.check(revs, given) if "withdrawn" in e]
    kept = revs[6]["resolutions"][0]
    revs[6]["withdrawn"].append({"node": kept["node"], "cites": kept["cites"], "why": "Nothing."})
    assert any("which this revision keeps" in e for e in project.check(revs, given))
    revs[6]["version"] = 1
    assert any("only a version 2 revision records withdrawals" in e for e in project.check(revs, given))


def test_history_gives_each_resolution_its_lifetime_and_no_reason_a_version_1_revision_did_not_record():
    lives = project.history(project.revisions(MAP))
    screen = [h for h in lives if h["node"] == "screen" and h["cites"].startswith("probe:madelon-route-screened-forest")]
    assert [(h["from"], h["dropped"], h["why"]) for h in screen] == [(3, 6, None)]
    assert all(h["dropped"] is None for h in lives if h["from"] == 9)


def test_editing_a_draft_does_not_change_the_revision_it_was_drafted_from():
    revs = project.revisions(MAP)
    before = json.dumps(project.sealed(revs[-1]), sort_keys=True)
    draft = project.propose(revs, everything())
    draft["resolutions"][0]["excused"] = [{"run": "step-1", "why": "edited"}]
    assert json.dumps(project.sealed(revs[-1]), sort_keys=True) == before and draft["version"] == 2


def test_the_committed_map_checks_with_every_trail_under_live():
    assert project.check(project.revisions(MAP), everything()) == []

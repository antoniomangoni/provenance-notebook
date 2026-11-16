"""The map drawn as one picture (spec 7): every station, route and lane, escaped text, a static page
that runs nothing, and a server bound to this machine that answers 304 when nothing changed."""

import copy
import re
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

import mapview
import project

ROOT = Path(__file__).parent.parent
MAP = ROOT / "research" / "madelon-reanalysis" / "map"
LIVE = ROOT / "live"
CLOCK = datetime(2026, 11, 16, 18, 0, tzinfo=UTC)


def state() -> dict:
    revs = project.revisions(MAP)
    return project.live_state(revs, project.Trails(project.discover(LIVE, revs[-1]["project"])))


def test_every_station_route_and_lane_is_drawn():
    live = state()
    svg = mapview.picture(live, CLOCK)
    for node in live["nodes"]:
        assert f'id="st-{node["id"]}"' in svg
    assert len(re.findall(r'<path class="line ', svg)) == len(live["routes"])
    for lane in live["trails"]:
        assert f">{lane['trail']}<" in svg
    # The task of each steered run builds on another trail: an arc for each such link.
    builds = [link for lane in live["trails"] for step in lane["steps"] for link in step["links"] if link["relation"] == "builds_on"]
    assert svg.count('<path class="arc"') + svg.count('<path class="arc suggested"') == len(builds)
    # An agent's link is drawn as the agent's: dashed, apart from the runner's and a person's.
    assert svg.count('<path class="arc suggested"') == sum(link["status"] == "suggested" for link in builds) > 0


def test_agent_text_is_escaped():
    live = copy.deepcopy(state())
    live["trails"][0]["steps"][1]["summary"] = "<script>alert(1)</script>"
    live["nodes"][0]["statement"] = '"><img src=x onerror=alert(1)>'
    page = mapview.page(live, CLOCK)
    assert "<script>alert(1)" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page


def test_the_static_page_runs_nothing_and_fetches_nothing():
    page = mapview.page(state(), CLOCK)
    assert "<script" not in page
    assert not re.search(r'(?:src|href)="(?:https?:)?//', page)
    assert "@import" not in page and "url(http" not in page


def test_the_server_is_local_and_answers_304_when_nothing_changed():
    running = mapview.server(MAP, str(LIVE), [], [], 0)
    thread = threading.Thread(target=running.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = running.server_address[:2]
        assert host == "127.0.0.1"
        base = f"http://{host}:{port}"
        with urllib.request.urlopen(base + "/") as response:
            assert "<script>" in response.read().decode()
        with urllib.request.urlopen(base + "/frame") as response:
            tag = response.headers["ETag"]
            assert 'id="st-screen"' in response.read().decode()
        try:
            urllib.request.urlopen(urllib.request.Request(base + "/frame", headers={"If-None-Match": tag}))
            raise AssertionError("expected 304")
        except urllib.error.HTTPError as error:
            assert error.code == 304
        with urllib.request.urlopen(base + "/trail/madelon-route-knn") as response:
            assert "madelon-route-knn" in response.read().decode()
    finally:
        running.shutdown()
        running.server_close()


def test_a_past_revision_is_served_as_it_was_sealed_and_does_not_poll():
    running = mapview.server(MAP, str(LIVE), [], [], 0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{running.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/rev/3") as reply:
            body = reply.read().decode()
        assert "Revision 3, sealed" in body and "as revision 3 sealed it" in body and "<script>" not in body
        assert '<a href="/">rev-' in body and "<span>rev-3</span>" in body
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(f"{base}/rev/99")
        assert missing.value.code == 404
    finally:
        running.shutdown()
        running.server_close()


def test_the_page_lists_every_revision_and_what_was_withdrawn():
    live = state()
    body = mapview.page(live, CLOCK)
    assert body.count("<tr><td class='num'>") >= len(project.revisions(MAP))
    assert "<h2>Withdrawn</h2>" in body and "rev-3 to rev-6" in body
    then = project.live_state(project.revisions(MAP), project.Trails(project.discover(LIVE, "madelon-reanalysis")), upto=5)
    assert then["rev"] == 5 and not any(n["provisional"] for n in then["nodes"])
    assert "rev-3 to rev-6" not in mapview.page(then, CLOCK)

"""The map drawn as one picture (spec 7): every station, route and lane, escaped text, a static page
that runs nothing, and a server bound to this machine that answers 304 when nothing changed."""

import copy
import re
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

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
    assert svg.count('<path class="arc"') == sum(
        1 for lane in live["trails"] for step in lane["steps"] for link in step["links"] if link["relation"] == "builds_on"
    )


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

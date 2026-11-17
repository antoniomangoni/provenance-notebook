"""The countersign page: every judgment with its steps, escaped, and a draft that seal accepts."""

import copy
import json
import re
import threading
import urllib.request
from pathlib import Path

import countersign
import mapview
import project

ROOT = Path(__file__).parent.parent
MAP = ROOT / "research" / "madelon-reanalysis" / "map"
LIVE = ROOT / "live"
AT = "2026-11-17T15:00:00Z"


def inputs():
    revs = project.revisions(MAP)
    trails = project.Trails(project.discover(LIVE, revs[-1]["project"]))
    return revs, trails, project.live_state(revs, trails)


def test_every_excused_read_abandoned_route_and_reason_is_on_the_page():
    revs, _, live = inputs()
    body = countersign.page(live, revs, "research/madelon-reanalysis/map", "live")
    for node in live["nodes"]:
        for res in node["resolutions"]:
            for read in res["reads"]:
                if read["why"]:
                    assert mapview.e(read["why"]) in body
    for route in live["routes"]:
        if route["status"] == "abandoned":
            assert f'id="route-{route["id"]}"' in body and mapview.e(route["why"]) in body
    assert body.count('<article class="card" id="rev-') == len(revs)
    assert f"Countersign revision {len(revs)}" in body and "none by a person" in body


def test_every_step_box_links_to_a_step_on_its_trail():
    revs, _, live = inputs()
    body = countersign.page(live, revs, "research/madelon-reanalysis/map", "live")
    steps = {(lane["trail"], step["id"]) for lane in live["trails"] for step in lane["steps"]}
    links = re.findall(r'href="/trail/([^"#]+)#([^"]+)"', body)
    assert len(links) > 20 and all(link in steps for link in links)


def test_agent_text_is_escaped():
    revs, _, live = inputs()
    live = copy.deepcopy(live)
    live["nodes"][0]["statement"] = '"><img src=x onerror=alert(1)>'
    live["revisions"][0]["reason"] = "</script><script>alert(1)</script>"
    body = countersign.page(live, revs, "m", None)
    assert "<img src=x" not in body and "<script>alert(1)" not in body


def test_the_draft_seals_as_it_stands_and_with_a_credit_disputed():
    revs, trails, live = inputs()
    body = countersign.page(live, revs, "m", None)
    embedded = json.loads(re.search(r'<script type="application/json" id="draft">(.*?)</script>', body, re.DOTALL)[1])
    assert embedded == countersign.draft(revs)
    confirmed = embedded | {"reason": "I confirm every judgment."}
    revision, errors = project.seal(revs, confirmed, "human:tester", AT, trails)
    assert errors == [] and revision["rev"] == len(revs) and revision["by"] == "human:tester"
    # What the page's script does with a dispute: the credit moves to withdrawn, with the note as why.
    disputed = copy.deepcopy(confirmed)
    gone = next(r for r in disputed["resolutions"] if r["node"] == "compact-vote")
    disputed["resolutions"].remove(gone)
    disputed["withdrawn"] = [{"node": gone["node"], "cites": gone["cites"], "why": "The excused read is not good enough."}]
    revision, errors = project.seal(revs, disputed, "human:tester", AT, trails)
    assert errors == [] and project.live_state([*revs, revision], trails)["nodes"]


def test_the_server_offers_review_only_for_the_newest_revision():
    running = mapview.server(MAP, str(LIVE), [], [], 0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{running.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/review") as reply:
            assert "Download the draft" in reply.read().decode()
        with urllib.request.urlopen(f"{base}/frame") as reply:
            assert "href=/review" in reply.read().decode()
        with urllib.request.urlopen(f"{base}/rev/3") as reply:
            assert "/review" not in reply.read().decode()
    finally:
        running.shutdown()
        running.server_close()

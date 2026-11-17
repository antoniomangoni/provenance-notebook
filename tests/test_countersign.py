"""The countersign page: every judgment with its steps, escaped, and a draft that seal accepts."""

import copy
import json
import re
import shutil
import threading
import urllib.error
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


def test_each_excuse_once_and_every_abandoned_route_and_reason_is_on_the_page():
    revs, _, live = inputs()
    body = countersign.page(live, revs, "research/madelon-reanalysis/map", "live")
    found = countersign.excuses(live)
    assert found and body.count('data-kind="excuse"') == len(found)
    for x in found:
        assert body.count(f"<p class='why'>{mapview.e(x['why'])}</p>") >= 1
        assert f'data-key="excuse|{x["trail"]}#{x["step"]}"' in body
    whys = [mapview.e(x["why"]) for x in found]
    for why in set(whys):  # one card per excuse, not one per credit it props up
        assert body.count(f"<p class='why'>{why}</p>") == whys.count(why)
    for route in live["routes"]:
        if route["status"] == "abandoned":
            assert mapview.e(route["why"]) in body
    assert body.count('data-kind="revision"') == len(revs)
    assert f"Countersign revision {len(revs)}" in body
    assert ("none by a person" in body) == (not any(r["by"].startswith("human:") for r in revs))


def test_disputing_an_excuse_withdraws_every_credit_on_it_and_seals():
    revs, trails, live = inputs()
    x = max(countersign.excuses(live), key=lambda x: len(x["credits"]))
    draft = countersign.draft(revs) | {"reason": "I dispute one excuse."}
    keys = {countersign.credit_key(node, res) for node, res in x["credits"] if res["holds"]}
    gone = [r for r in draft["resolutions"] if f"{r['node']}|{project.unpinned(r['cites'])}" in keys]
    assert len(gone) == len(keys) > 0
    draft["resolutions"] = [r for r in draft["resolutions"] if r not in gone]
    draft["withdrawn"] = [{"node": r["node"], "cites": r["cites"], "why": "The excuse does not hold."} for r in gone]
    revision, errors = project.seal(revs, draft, "human:tester", AT, trails)
    assert errors == [] and len(revision["resolutions"]) == len(revs[-1]["resolutions"]) - len(gone)


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


def post(base: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{base}/seal", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_the_seal_button_writes_a_persons_revision_and_refuses_anything_else(tmp_path):
    shutil.copytree(MAP.parent / "map", tmp_path / "madelon-reanalysis" / "map")
    shutil.copytree(MAP.parent / "retrace", tmp_path / "madelon-reanalysis" / "retrace")
    directory = tmp_path / "madelon-reanalysis" / "map"
    revs = project.revisions(directory)
    running = mapview.server(directory, str(LIVE), [], [], 0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{running.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/review") as reply:
            body = reply.read().decode()
        token = re.search(r'data-token="([^"]+)"', body)[1]
        good = {"token": token, "rev": len(revs), "by": "human:tester", "draft": countersign.draft(revs) | {"reason": "I confirm."}}
        assert post(base, good | {"token": "guess"})[0] == 403
        assert post(base, good, {"Origin": "https://example.com"})[0] == 403
        assert post(base, good | {"by": "agent:someone"})[0] == 400
        assert post(base, good | {"draft": countersign.draft(revs)})[0] == 422  # an empty reason fails check
        assert not (directory / f"rev-{len(revs)}.json").exists()
        code, result = post(base, good)
        assert code == 200 and result["ok"] and result["rev"] == len(revs)
        sealed = project.revisions(directory)
        assert sealed[-1]["by"] == "human:tester" and sealed[-1]["reason"] == "I confirm."
        trails = project.Trails(project.discover(LIVE, "madelon-reanalysis"), [], directory.parent)
        assert project.check(sealed, trails) == []
        assert post(base, good)[0] == 409  # reviewed at the old revision
    finally:
        running.shutdown()
        running.server_close()

"""The research map and its trails drawn as one picture: `project.py page` and `project.py serve`.

The map is a metro map. Milestones are stations, laid out left to right by depth. Each route is a
line through its stations to its goal, in the goal's colour. Under it is a lane for each trail,
with its steps in order. Lines join each milestone to the observations that resolved it, and
arcs join steps that cite another trail.

Everything is drawn from `project.live_state`, so the picture shows no more than the state does:
provisional resolutions are dashed and never drawn as sealed. Every string from a step or a
revision is escaped. The static page has no script; the served one polls `/frame`.

docs/specs/07-live-map.md is the specification.
"""

import html
import http.server
import json
import os
import socketserver
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

import project
import trail
import view

# Route lines take their goal's colour: three validated slots (light, dark), then the fourth slot
# for a map with a fourth goal. Line style, not colour, carries a route's state.
GOAL_SLOTS = (("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"))
COLUMN, ROW, LANE, STEP = 150, 46, 34, 13
LEFT, LABELS = 24, 230

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;
--ring:rgba(11,11,11,.10);--g0:#2a78d6;--g1:#eb6834;--g2:#1baf7a;--g3:#eda100}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--surface:#1a1a19;--plane:#0d0d0d;
--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--g0:#3987e5;--g1:#d95926;--g2:#199e70;--g3:#c98500}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--plane:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;
--axis:#383835;--ring:rgba(255,255,255,.10);--g0:#3987e5;--g1:#d95926;--g2:#199e70;--g3:#c98500}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1400px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:28px 0 8px}
.sub{color:var(--ink2);margin:0 0 16px}
.frame{background:var(--surface);border:1px solid var(--ring);border-radius:8px;overflow-x:auto}
svg{display:block}
svg text{font:12px system-ui,-apple-system,"Segoe UI",sans-serif;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}
svg text.glyph{stroke:none}
svg .muted{fill:var(--ink2)}svg .small{font-size:11px}svg .head{font-weight:600}
.line{fill:none;stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.line.blocked{stroke-dasharray:2 6}.line.abandoned{opacity:.3}.line.done{stroke-width:5}
.station{fill:var(--surface);stroke:var(--ink);stroke-width:2}
.station.reached{fill:var(--good);stroke:var(--surface)}.station.refuted{fill:var(--critical);stroke:var(--surface)}
.glyph{fill:#fff;font-size:11px;font-weight:700;pointer-events:none}
.provisional{fill:none;stroke:var(--ink);stroke-width:1.5;stroke-dasharray:3 3}
.lane{stroke:var(--grid);stroke-width:1}
.step{stroke:var(--surface);stroke-width:1.5}
.k-task{fill:var(--ink)}.k-plan{fill:var(--ink2)}.k-run{fill:var(--muted)}.k-note,.k-review{fill:var(--axis)}
.o-as_expected{fill:var(--good)}.o-contradicted{fill:var(--critical)}.o-failed{fill:var(--serious)}.o-inconclusive{fill:var(--axis)}
.sealed-read{fill:none;stroke:var(--warning);stroke-width:2.5}.sealed-read.re{stroke-dasharray:2 2}.sealed-read.names{stroke-dasharray:1 3}
.withheld{fill:var(--axis)!important}
.cx{fill:none;stroke-width:1.2;opacity:.18}.cx.holds{stroke:var(--good)}.cx.refutes{stroke:var(--critical)}.cx.prov{stroke-dasharray:4 3;opacity:.5}
.arc{fill:none;stroke:var(--ink2);stroke-width:1.5;opacity:.6;marker-end:url(#arrow)}
.arc.about{stroke-dasharray:3 3;opacity:.22;stroke-width:1;marker-end:none}
.arc.suggested{stroke-dasharray:7 4}
.k-run.unsettled{fill:var(--surface);stroke:var(--muted);stroke-width:1.5}
.judged{fill:var(--warning);stroke:var(--surface);stroke-width:1.5}
nav.revs{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 12px;font-size:13px}nav.revs a,nav.revs span{padding:1px 7px;border:1px solid var(--ring);border-radius:10px;text-decoration:none}
nav.revs span{background:var(--ink);color:var(--surface)}
.arc:hover{opacity:1}
.newest{fill:none;stroke:var(--ink);stroke-width:1.5;animation:pulse 1.6s ease-in-out infinite}
@keyframes pulse{50%{opacity:.15}}
@media (prefers-reduced-motion:reduce){.newest{animation:none}}
g.node:hover .station{stroke-width:3}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 0;padding:0;list-style:none;color:var(--ink2);font-size:13px}
.legend svg{display:inline-block;vertical-align:-3px;margin-right:6px}
table{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--ring);border-radius:8px;font-size:13px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}td.num{font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}
a{color:inherit}
.live{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:10px;border:1px solid var(--ring);color:var(--ink2);font-size:12px}
"""

STATE_GLYPH = {"reached": "✓", "refuted": "✕", "open": ""}
OUTCOME = {"as_expected": "as expected", "contradicted": "contradicted", "failed": "failed", "inconclusive": "inconclusive"}


def e(text: object) -> str:
    return html.escape(str(text), quote=True)


def depths(live: dict) -> dict[str, int]:
    """Each milestone's longest-path depth over consecutive pairs on route paths: the column it sits in."""
    after: dict[str, set[str]] = {node["id"]: set() for node in live["nodes"]}
    for route in live["routes"]:
        for a, b in zip(route["path"], route["path"][1:], strict=False):
            after[a].add(b)
    depth = dict.fromkeys(after, 0)
    for _ in range(len(after)):
        changed = False
        for a, nexts in after.items():
            for b in nexts:
                if depth[b] < depth[a] + 1:
                    depth[b], changed = depth[a] + 1, True
        if not changed:
            break
    return depth


def layout(live: dict) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]], float, float]:
    """Station and goal positions, and the map panel's width and height."""
    depth = depths(live)
    columns: dict[int, list[str]] = {}
    order = [node for route in live["routes"] for node in route["path"]] + [node["id"] for node in live["nodes"]]
    for node in dict.fromkeys(order):
        columns.setdefault(depth[node], []).append(node)
    tallest = max((len(c) for c in columns.values()), default=1)
    height = max(tallest, len(live["goals"]) * 1.5) * ROW + 70
    stations = {}
    for column, nodes in columns.items():
        top = 50 + (height - 50 - len(nodes) * ROW) / 2
        for i, node in enumerate(nodes):
            stations[node] = (LEFT + 60 + column * COLUMN, top + i * ROW + ROW / 2)
    last = max(columns, default=0) + 1
    # Goals in the order of the stations that lead to them, so lines into them cross as little as can be.
    ends = {g["id"]: [stations[r["path"][-1]][1] for r in live["routes"] if r["goal"] == g["id"] and r["path"]] for g in live["goals"]}
    order = sorted(live["goals"], key=lambda g: sum(ends[g["id"]]) / len(ends[g["id"]]) if ends[g["id"]] else height)
    goals, top = {}, 50 + (height - 50 - len(live["goals"]) * ROW) / 2
    for i, goal in enumerate(order):
        goals[goal["id"]] = (LEFT + 60 + last * COLUMN, top + i * ROW * 1.5 + ROW / 2)
    return stations, goals, LEFT + 60 + last * COLUMN + 160, height


def route_lines(live: dict, stations: dict, goals: dict, slot: dict) -> list[str]:
    out = []
    count = len(live["routes"])
    for i, route in enumerate(live["routes"]):
        off = (i - (count - 1) / 2) * 3.0
        points = [stations[node] for node in route["path"]] + [goals[route["goal"]]]
        d = "M" + " L".join(f"{x:.1f},{y + off:.1f}" for x, y in points)
        why = f" Abandoned: {route['why']}" if "why" in route else ""
        out.append(
            f'<path class="line {e(route["status"])}" stroke="var(--g{slot[route["goal"]]})" d="{d}">'
            f"<title>Route {e(route['id'])} ({e(route['status'])}, for {e(route['goal'])}): {e(route['method'])}.{e(why)}</title></path>"
        )
    return out


def stations_svg(live: dict, stations: dict) -> list[str]:
    out = []
    for node in live["nodes"]:
        x, y = stations[node["id"]]
        r = 11 if node["shared"] else 8
        tip = [f"{node['id']}: {node['statement']}", "Criteria: " + ", ".join(node["criteria"])]
        tip += [
            f"{'sealed' if res['sealed'] else 'provisional'}, {'reached' if res['holds'] else 'refuted'} by {res['cites'].split('@')[0]} {res['step']}: {res['summary']}"
            for res in node["resolutions"] + node["provisional"]
        ]
        for res in node["resolutions"]:
            if res.get("rests_on"):
                tip.append(f"  {res['step']} rests on {', '.join(res['rests_on'])}")
            tip += [
                f"  {x['run']} opened a sealed input ({x['how']})" + (f"; excused by the revision: {x['why']}" if x["why"] else "")
                for x in res.get("reads", [])
            ]
        shape = (
            f'<rect class="station {e(node["state"])}" x="{x - r:.1f}" y="{y - r - 8:.1f}" width="{2 * r}" height="{2 * r + 16}" rx="{r}"/>'
            if node["shared"]
            else f'<circle class="station {e(node["state"])}" cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'
        )
        ring = (
            f'<circle class="provisional" cx="{x:.1f}" cy="{y:.1f}" r="{r + 6}"/>'
            if node["state"] == "open" and any(p["holds"] for p in node["provisional"])
            else ""
        )
        # A credit that stands only because the revision excused a read: a judgment, marked as one.
        judged = (
            f'<circle class="judged" cx="{x + r * 0.75:.1f}" cy="{y - r * 0.75 - (8 if node["shared"] else 0):.1f}" r="4"/>'
            if any(res["holds"] and any(read["why"] for read in res.get("reads", [])) for res in node["resolutions"])
            else ""
        )
        glyph = STATE_GLYPH[node["state"]]
        out.append(
            f'<g class="node" id="st-{e(node["id"])}"><title>{e(chr(10).join(tip))}</title>{shape}{ring}{judged}'
            + (f'<text class="glyph" x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle">{glyph}</text>' if glyph else "")
            + f'<text class="small" x="{x:.1f}" y="{y + r + (22 if node["shared"] else 14):.1f}" text-anchor="middle">{e(node["id"])}</text></g>'
        )
    return out


def goals_svg(live: dict, goals: dict, slot: dict) -> list[str]:
    out = []
    for goal in live["goals"]:
        x, y = goals[goal["id"]]
        mark = "✓ reached" if goal["reached"] else "open"
        out.append(
            f"<g><title>Goal {e(goal['id'])}: {e(goal['statement'])}</title>"
            f'<rect x="{x - 6:.1f}" y="{y - 13:.1f}" width="12" height="26" rx="3" fill="var(--g{slot[goal["id"]]})"/>'
            f'<text class="head" x="{x + 14:.1f}" y="{y - 1:.1f}">{e(goal["id"])}</text>'
            f'<text class="small muted" x="{x + 14:.1f}" y="{y + 13:.1f}">{mark}</text></g>'
        )
    return out


def lanes_svg(live: dict, top: float, clock: datetime, links: bool) -> tuple[list[str], dict[tuple[str, str], tuple[float, float]], float]:
    out, at = [], {}
    for i, lane in enumerate(live["trails"]):
        y = top + i * LANE + LANE / 2
        idle = project.age(lane["last_at"], clock)
        running = idle < project.ACTIVE_S and not lane["problems"]
        state = "reading" if lane["reading"] else (f"running, last step {int(idle)} s ago" if running else "finished")
        name = e(lane["trail"])
        label = f'<a href="trail/{name}">{name}</a>' if links else name
        out.append(
            f'<text x="{LEFT}" y="{y - 2:.1f}" class="head small">{label}</text>'
            f'<text x="{LEFT}" y="{y + 11:.1f}" class="small muted">{e(lane["route"] or "no route")} · {lane["count"]} steps · {e(state)}'
            + (f" · {len(lane['problems'])} problems" if lane["problems"] else "")
            + "</text>"
            f'<line class="lane" x1="{LABELS}" x2="{LABELS + lane["count"] * STEP}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        for j, step in enumerate(lane["steps"]):
            x = LABELS + j * STEP + STEP / 2
            at[(lane["probe"], step["id"])] = (x, y)
            tip = f"{lane['trail']} {step['id']} ({step['kind']}): {step['summary']}"
            if step.get("measures"):
                tip += "\n" + ", ".join(f"{k} {view.number(v)}" for k, v in step["measures"].items())
            if "sealed_read" in step:
                tip += f"\nopened a sealed input ({step['sealed_read']})"
            if step.get("unsettled"):
                tip += "\nno observation: still running, or it never ended"
            if step.get("by"):
                tip += f"\nwritten by {step['by']}"
            title = f"<title>{e(tip)}</title>"
            if step["kind"] == "observation":
                cls = "withheld" if step.get("withheld") else f"o-{e(step['outcome'])}"
                out.append(f'<circle class="step {cls}" cx="{x:.1f}" cy="{y:.1f}" r="5">{title}</circle>')
            elif step["kind"] == "plan":
                out.append(
                    f'<path class="step k-plan" d="M{x:.1f},{y - 6:.1f} L{x + 5:.1f},{y:.1f} L{x:.1f},{y + 6:.1f} L{x - 5:.1f},{y:.1f}Z">{title}</path>'
                )
            elif step["kind"] == "run":
                hollow = " unsettled" if step.get("unsettled") else ""
                out.append(f'<rect class="step k-run{hollow}" x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" rx="1">{title}</rect>')
                if how := step.get("sealed_read"):
                    kind = {"read": "", "read on re-execution": " re", "names": " names"}[how]
                    out.append(f'<circle class="sealed-read{kind}" cx="{x:.1f}" cy="{y:.1f}" r="7.5"/>')
            elif step["kind"] == "task":
                out.append(f'<rect class="step k-task" x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10">{title}</rect>')
            else:
                out.append(
                    f'<path class="step k-{e(step["kind"])}" d="M{x:.1f},{y - 5:.1f} L{x + 5:.1f},{y + 4:.1f} L{x - 5:.1f},{y + 4:.1f}Z">{title}</path>'
                )
        if running and lane["steps"]:
            x, y = at[(lane["probe"], lane["steps"][-1]["id"])]
            out.append(f'<circle class="newest" cx="{x:.1f}" cy="{y:.1f}" r="9"/>')
    width = LABELS + max((lane["count"] for lane in live["trails"]), default=0) * STEP + 30
    return out, at, width


def connectors(live: dict, stations: dict, at: dict) -> list[str]:
    out = []
    for node in live["nodes"]:
        sx, sy = stations[node["id"]]
        for res in node["resolutions"] + node["provisional"]:
            if (res["probe"], res["step"]) not in at:
                continue
            x, y = at[(res["probe"], res["step"])]
            cls = ("holds" if res["holds"] else "refutes") + ("" if res["sealed"] else " prov")
            mid = (sy + y) / 2
            out.append(
                f'<path class="cx {cls} cx-{e(node["id"])}" d="M{sx:.1f},{sy:.1f} C{sx:.1f},{mid:.1f} {x:.1f},{mid:.1f} {x:.1f},{y - 6:.1f}"/>'
            )
    return out


def arcs(live: dict, at: dict) -> list[str]:
    """Steps that cite a step of another trail: the agents' contributions to each other."""
    out = []
    for lane in live["trails"]:
        for step in lane["steps"]:
            for link in step["links"]:
                source, target = at.get((lane["probe"], step["id"])), at.get((link["probe"], link["step"]))
                if not source or not target or link["probe"] == lane["probe"]:
                    continue
                (x1, y1), (x2, y2) = source, target
                bend = -28 if y2 < y1 else 28
                cls = "arc about" if link["relation"] == "about" else ("arc suggested" if link.get("status") == "suggested" else "arc")
                out.append(
                    f'<path class="{cls}" d="M{x1:.1f},{y1:.1f} C{x1 - 30:.1f},{y1 + bend:.1f} {x2 + 30:.1f},{y2 - bend:.1f} {x2:.1f},{y2:.1f}">'
                    f"<title>{e(lane['trail'])} {e(step['id'])} {e(link['relation'])} {e(link['ref'])}"
                    f" ({'the agent says so' if link.get('status') == 'suggested' else 'the runner or a person wrote it'})</title></path>"
                )
    return out


def picture(live: dict, clock: datetime, links: bool = False) -> str:
    slot = {goal["id"]: min(i, len(GOAL_SLOTS) - 1) for i, goal in enumerate(live["goals"])}
    stations, goals, map_width, map_height = layout(live)
    lanes, at, lanes_width = lanes_svg(live, map_height + 40, clock, links)
    width = max(map_width, lanes_width)
    height = map_height + 40 + len(live["trails"]) * LANE + 20
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        f'aria-label="Research map of {e(live["project"])}, revision {live["rev"]}, and its {len(live["trails"])} trails">'
    )
    marker = (
        '<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L8,4 L0,8z" fill="var(--ink2)"/></marker></defs>'
    )
    body = [
        head,
        marker,
        f'<text x="{LEFT}" y="26" class="head">Map, revision {live["rev"]}</text>',
        f'<text x="{LEFT}" y="{map_height + 26:.0f}" class="head">Trails, step by step</text>',
        *connectors(live, stations, at),
        *route_lines(live, stations, goals, slot),
        *stations_svg(live, stations),
        *goals_svg(live, goals, slot),
        *lanes,
        *arcs(live, at),
        "</svg>",
    ]
    return "\n".join(body)


def legend() -> str:
    def swatch(inner: str) -> str:
        return f'<svg width="22" height="16" viewBox="0 0 22 16" aria-hidden="true">{inner}</svg>'

    items = [
        (swatch('<circle class="station reached" cx="11" cy="8" r="6"/>'), "milestone reached (✓)"),
        (swatch('<circle class="station refuted" cx="11" cy="8" r="6"/>'), "refuted (✕)"),
        (swatch('<circle class="station" cx="11" cy="8" r="5"/>'), "open"),
        (swatch('<circle class="provisional" cx="11" cy="8" r="6"/>'), "met in a trail, not yet sealed"),
        (swatch('<rect class="station" x="6" y="1" width="10" height="14" rx="5"/>'), "on several routes"),
        (swatch('<path class="line" stroke="var(--ink2)" d="M2,8 L20,8"/>'), "route, in its goal's colour"),
        (swatch('<path class="line blocked" stroke="var(--ink2)" d="M2,8 L20,8"/>'), "blocked route"),
        (swatch('<path class="step k-plan" d="M11,2 L16,8 L11,14 L6,8Z"/>'), "plan"),
        (swatch('<rect class="step k-run" x="7" y="4" width="8" height="8"/>'), "run"),
        (swatch('<circle class="step o-as_expected" cx="11" cy="8" r="5"/>'), "observation as expected"),
        (swatch('<circle class="step o-contradicted" cx="11" cy="8" r="5"/>'), "contradicted"),
        (swatch('<circle class="step o-failed" cx="11" cy="8" r="5"/>'), "failed"),
        (swatch('<circle class="step o-inconclusive" cx="11" cy="8" r="5"/>'), "inconclusive or withheld"),
        (swatch('<circle class="sealed-read" cx="11" cy="8" r="6"/>'), "opened a sealed input (traced)"),
        (swatch('<circle class="sealed-read re" cx="11" cy="8" r="6"/>'), "… on re-execution"),
        (swatch('<circle class="sealed-read names" cx="11" cy="8" r="6"/>'), "… named on its command line"),
        (swatch('<rect class="step k-run unsettled" x="7" y="4" width="8" height="8"/>'), "run with no observation"),
        (swatch('<circle class="judged" cx="11" cy="8" r="4"/>'), "credit that stands on an excused read"),
        (swatch('<path class="arc" d="M2,8 L18,8"/>'), "builds on another trail's step (a person or the runner)"),
        (swatch('<path class="arc suggested" d="M2,8 L18,8"/>'), "… as the agent says"),
        (swatch('<path class="arc about" style="opacity:.6" d="M2,8 L18,8"/>'), "read the map while that trail stood here"),
    ]
    return '<ul class="legend">' + "".join(f"<li>{mark}{e(text)}</li>" for mark, text in items) + "</ul>"


def tables(live: dict, clock: datetime) -> str:
    rows = "".join(
        f"<tr><td>{e(r['id'])}</td><td>{e(r['goal'])}</td><td>{e(r['status'])}</td><td>{e(' → '.join(r['path']))}</td><td>{e(r['method'])}</td></tr>"
        for r in live["routes"]
    )
    resolved = "".join(
        f"<tr><td>{e(n['id'])}</td><td>{e(n['state'])}</td><td>{'sealed' if res['sealed'] else 'provisional'}</td>"
        f"<td>{'reached' if res['holds'] else 'refuted'}</td><td>{e(res['cites'].split('@')[0])} {e(res['step'])}</td><td>{e(res['summary'])}</td></tr>"
        for n in live["nodes"]
        for res in n["resolutions"] + n["provisional"]
    )
    lanes = "".join(
        f"<tr><td>{e(t['trail'])}</td><td>{e(t['route'] or '')}</td><td>{e(t['agent'] or '')}</td><td class='num'>{t['count']}</td>"
        f"<td class='num'>{int(project.age(t['last_at'], clock))} s</td><td>{'reading' if t['reading'] else ('ok' if not t['problems'] else e('; '.join(t['problems'][:3])))}</td></tr>"
        for t in live["trails"]
    )
    revisions = "".join(
        f"<tr><td class='num'>{r['rev']}</td><td>{e(r['at'])}</td><td>{e(r['by'])}</td><td class='num'>{r['version']}</td>"
        f"<td class='num'>{r['sealed']}</td><td class='num'>{r['dropped']}</td><td>{e(r['reason'][:240] + ('…' if len(r['reason']) > 240 else ''))}</td></tr>"
        for r in live["revisions"]
    )
    withdrawn = "".join(
        f"<tr><td>{e(h['node'])}</td><td>{'reached' if h['holds'] else 'refuted'}</td><td>{e(h['cites'])}</td>"
        f"<td class='num'>rev-{h['from']} to rev-{h['dropped']}</td><td>{e(h['why'] or 'no reason recorded in the data; see that revision')}</td></tr>"
        for h in live["withdrawn"]
    )
    return (
        "<h2>Routes</h2><div class='wrap'><table><tr><th>Route</th><th>Goal</th><th>State</th><th>Path</th><th>Method</th></tr>"
        f"{rows}</table></div>"
        "<h2>What resolved each milestone</h2><div class='wrap'><table><tr><th>Milestone</th><th>State</th><th>Resolution</th><th></th><th>Cites</th><th>Observation</th></tr>"
        f"{resolved}</table></div>"
        "<h2>Trails</h2><div class='wrap'><table><tr><th>Trail</th><th>Route</th><th>Agent</th><th>Steps</th><th>Since last step</th><th>Check</th></tr>"
        f"{lanes}</table></div>"
        + (
            "<h2>Withdrawn</h2><div class='wrap'><table><tr><th>Milestone</th><th></th><th>Cited</th><th>Stood</th><th>Why</th></tr>"
            f"{withdrawn}</table></div>"
            if withdrawn
            else ""
        )
        + "<h2>Revisions</h2><div class='wrap'><table><tr><th>Rev</th><th>Sealed</th><th>By</th><th>Version</th><th>Resolutions sealed</th><th>Dropped</th><th>Reason</th></tr>"
        f"{revisions}</table></div>"
    )


def nav(live: dict) -> str:
    """Every revision, each a link to the map as it sealed it; the newest is the live page."""
    last = live["revisions"][-1]["rev"]
    marks = [
        f"<span>rev-{r['rev']}</span>"
        if r["rev"] == live["rev"]
        else f'<a href="{"/" if r["rev"] == last else f"/rev/{r['rev']}"}">rev-{r["rev"]}</a>'
        for r in live["revisions"]
    ]
    return f"<nav class='revs' aria-label='Revisions'>{''.join(marks)}</nav>"


def content(live: dict, clock: datetime, links: bool = False) -> str:
    then = (
        ""
        if live["latest"]
        else f" This is the map as revision {live['rev']} sealed it, of {live['revisions'][-1]['rev']}; the trails are drawn as they stand now, and nothing provisional is."
    )
    return (
        f"<h1>Research map: {e(live['project'])}</h1>"
        + (nav(live) if links else "")
        + f"<p class='sub'>Revision {live['rev']}, sealed {e(live['at'])} by {e(live['by'])}. "
        f"{len(live['trails'])} trails, drawn {clock.strftime('%Y-%m-%d %H:%M:%S')} UTC.{e(then)}"
        f"{'<span class=live>live</span>' if links and live['latest'] else ''}</p>"
        + (
            f"<p class='sub'>⚠ project.py check finds {len(live['problems'])} problems. The first: {e(live['problems'][0])}</p>"
            if live["problems"]
            else ""
        )
        + f"<div class='frame'>{picture(live, clock, links)}</div>{legend()}{tables(live, clock)}"
    )


POLL = """<script>
let tag = document.body.dataset.etag;
async function poll() {
  try {
    const r = await fetch("frame", { headers: tag ? { "If-None-Match": tag } : {} });
    if (r.status === 200) { tag = r.headers.get("ETag"); document.querySelector("main").innerHTML = await r.text(); }
  } catch (_) {}
  setTimeout(poll, 2000);
}
setTimeout(poll, 2000);
</script>"""


def page(live: dict, clock: datetime, served: bool = False, etag: str = "") -> str:
    """The static page (no script), or the served one: the newest revision polls for changes, an earlier one does not."""
    poll = served and live["latest"]
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{e(live['project'])} map</title><style>{CSS}</style></head>"
        f'<body data-etag="{e(etag)}"><main>{content(live, clock, served)}</main>{POLL if poll else ""}</body></html>\n'
    )


# ---------------------------------------------------------------------------------------------
# serve


class State:
    """Reads the map and its trails again only when a step or a revision file has changed."""

    def __init__(self, directory: Path, live_dir: str | None, paths: list[Path], retraced: list[Path]):
        self.directory, self.live_dir, self.paths, self.retraced = directory, live_dir, paths, retraced
        self.seen, self.live, self.inputs = None, None, None

    def fingerprint(self) -> tuple:
        revs = sorted((p.name, p.stat().st_mtime_ns) for p in self.directory.glob("rev-*.json"))
        roots = list(self.paths)
        if self.live_dir and Path(self.live_dir).is_dir():
            roots += [p for p in Path(self.live_dir).iterdir() if (p / "steps").is_dir()]
        steps = []
        for root in roots:
            files = list((root / "steps").glob("step-*.json"))
            steps.append((str(root), len(files), max((f.stat().st_mtime_ns for f in files), default=0)))
        return (tuple(revs), tuple(sorted(steps)))

    def now(self) -> dict:
        seen = self.fingerprint()
        if seen != self.seen or self.live is None:
            revs = project.revisions(self.directory)
            paths = list(self.paths)
            if self.live_dir:
                paths += [p for p in project.discover(Path(self.live_dir), revs[-1]["project"]) if p not in paths]
            self.inputs = (revs, project.Trails(paths, self.retraced, self.directory.parent))
            self.live, self.seen = project.live_state(*self.inputs), seen
        return self.live

    def at(self, rev: int) -> dict | None:
        """The map as revision `rev` sealed it, beside the trails as they stand now."""
        self.now()
        revs, trails = self.inputs
        return project.live_state(revs, trails, upto=rev) if 0 <= rev < len(revs) else None

    def trail_page(self, name: str) -> str | None:
        live = self.now()
        lane = next((t for t in live["trails"] if t["trail"] == name), None)
        if lane is None:
            return None
        paths = [*self.paths, *(project.discover(Path(self.live_dir), live["project"]) if self.live_dir else [])]
        directory = next((p for p in paths if p.name == name), None)
        if directory is None:
            return None
        steps, _ = project.readable(directory)
        # What the map knows of this trail's reads, and the inputs its last revision sealed.
        revs, trails = self.inputs
        again = {"runs": list(trails.retraced.get(trail.probe_id(steps), {}).values())}
        return view.page(steps, reads=trail.opened(steps, again), sealed=tuple(revs[-1].get("sealed_inputs", ())))


def handler(state: State):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code: int, body: str, kind: str = "text/html; charset=utf-8", headers: dict | None = None) -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            clock = datetime.now(UTC)
            path = unquote(self.path.split("?")[0])
            try:
                live = state.now()
            except (OSError, ValueError, KeyError, IndexError) as error:  # a map that does not read yet: say so, keep serving
                self.send(503, f"<p>{e(type(error).__name__)}: {e(error)}</p>")
                return
            # The minute is part of the tag, so "last step N s ago" does not freeze between steps.
            tag = f'"{live["etag"].split(":")[1][:32]}-{clock.strftime("%H%M")}"'
            if path == "/":
                self.send(200, page(live, clock, served=True, etag=tag))
            elif path == "/frame":
                if self.headers.get("If-None-Match") == tag:
                    self.send_response(304)
                    self.send_header("ETag", tag)
                    self.end_headers()
                else:
                    self.send(200, content(live, clock, links=True), headers={"ETag": tag})
            elif path == "/state.json":
                self.send(200, json.dumps(live, ensure_ascii=False), "application/json")
            elif path.startswith("/trail/") and (found := state.trail_page(path.removeprefix("/trail/"))):
                self.send(200, found)
            elif path.startswith("/rev/") and path[5:].isdigit() and (then := state.at(int(path[5:]))):
                self.send(200, page(then, clock, served=True))
            else:
                self.send(404, "<p>not found</p>")

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def server(directory: Path, live_dir: str | None, paths: list[Path], retraced: list[Path], port: int) -> Server:
    """Bound to 127.0.0.1 only: the page shows step text, which is not for the network."""
    return Server(("127.0.0.1", port), handler(State(directory, live_dir, paths, retraced)))


def serve(directory: Path, live_dir: str | None, paths: list[Path], retraced: list[Path], port: int) -> int:
    running = server(directory, live_dir, paths, retraced, port)
    print(f"serving {directory} on http://127.0.0.1:{running.server_address[1]}/ (ctrl-c stops)", flush=True)
    try:
        running.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        running.server_close()
    return 0


if __name__ == "__main__":
    os.sys.exit(project.main(["project.py", *os.sys.argv[1:]]))

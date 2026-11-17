"""The countersign page: the map's judgments set out for a person to confirm or dispute, `GET /review`.

A revision is sealed by whoever names themselves in its `by`. Before a person seals one, they need to
see what the agents judged: credits that stand only because a revision excused a read of a sealed
input, refutations, abandoned routes, withdrawals, and each revision's reason. Each credit is drawn
as a small graph of the steps it rests on, one row per trail, every box a link to that step on the
trail's page.

The page's script builds the next revision's draft from the person's rulings (a disputed credit moves
to `withdrawn`, with their note as why). Its Seal button posts that draft to the server that served
it, which seals it with the same check as `project.py seal`, for a `human:` actor only, and only with
the random token the review page carries, from this host and origin, as JSON: another site's page can
neither read the token nor send that request. The draft can also be downloaded and sealed by hand.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import project
from mapview import CSS, e

BOX, GAP, ROW, LABEL = 70, 26, 50, 210

REVIEW_CSS = """
.card{background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:12px 14px;margin:0 0 14px}
.card h3{font-size:14px;margin:0 0 4px}.card p{margin:4px 0}
.card .graph{overflow-x:auto;margin:8px 0}
.why{border-left:3px solid var(--warning);padding:2px 0 2px 10px;margin:6px 0;color:var(--ink2)}
.rule{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-top:8px;font-size:13px}
.rule input[type=text]{flex:1;min-width:220px;padding:4px 6px;border:1px solid var(--axis);border-radius:4px;background:var(--plane);color:var(--ink)}
.measures td,.measures th{padding:3px 8px}.measures{width:auto;margin:6px 0}
.ok{color:var(--good)}.no{color:var(--critical)}
.box{stroke-width:1.5;stroke:var(--axis);fill:var(--plane)}
.box.read{stroke:var(--warning);stroke-width:3}.box.read.re{stroke-dasharray:4 3}
.box.hit{fill:var(--good);stroke:var(--surface)}.box.miss{fill:var(--critical);stroke:var(--surface)}
.box.hit+text,.box.miss+text{fill:#fff;stroke:none}
a:hover .box{stroke:var(--ink);stroke-width:2.5}
.feed{fill:none;stroke:var(--ink2);stroke-width:1.5;opacity:.55;marker-end:url(#arrow)}
.row{stroke:var(--grid)}
details{margin:6px 0}summary{cursor:pointer;color:var(--ink2)}
pre.reason{white-space:pre-wrap;font:13px/1.45 system-ui,sans-serif;margin:6px 0 0}
textarea{width:100%;min-height:180px;padding:8px;border:1px solid var(--axis);border-radius:6px;background:var(--surface);color:var(--ink);font:13px/1.45 system-ui,sans-serif}
.seal{padding:10px 0;border-top:1px solid var(--grid)}
button{padding:6px 14px;border-radius:6px;border:1px solid var(--ink);background:var(--ink);color:var(--surface);font:inherit;cursor:pointer}
code.cmd{display:block;white-space:pre-wrap;background:var(--surface);border:1px solid var(--ring);border-radius:6px;padding:8px;margin:8px 0;font-size:12px}
#problem{color:var(--critical)}
"""


def draft(revs: list[dict]) -> dict:
    """The next revision as the last one stands: what a person seals when they confirm everything."""
    last = revs[-1]
    keep = {key: value for key, value in project.sealed(last).items() if key not in (*project.SEALED, "withdrawn")}
    return json.loads(json.dumps(keep)) | {"version": project.VERSION, "triggered_by": [], "reason": ""}


def trail_of(ref: str) -> str:
    """`madelon-fleet-vote#step-5` or `madelon-2026-11-15-2 to step-7` or a probe id: the trail's name."""
    return ref.split("#")[0].split(" to ")[0].split("probe:")[-1]


def seq(step_id: str) -> int:
    return int(step_id.split("-")[1])


def graph(res: dict, lanes: dict[str, dict], cited_trail: str) -> str:
    """The steps a resolution rests on, one row per trail, the cited trail last. Each box links to the step."""
    reads = {}
    for read in res.get("reads", []):
        name = trail_of(read["run"]) if "#" in read["run"] else cited_trail
        reads[(name, read["run"].split("#")[-1])] = read
    ends = {trail_of(r): r.split(" to ")[1] for r in res.get("rests_on", [])}
    names = [*sorted(set(ends) | {n for n, _ in reads} - {cited_trail}), cited_trail]
    names = [n for n in names if n in lanes]
    rows, feeds, at = [], [], {}
    for y, name in enumerate(names):
        steps = {s["id"]: s for s in lanes[name]["steps"]}
        keep = {sid for (n, sid) in reads if n == name}
        if name in ends:
            keep.add(ends[name])
        if name == cited_trail:
            cited = steps.get(res["step"])
            keep |= {res["step"]} | ({cited["observes"]} if cited and cited.get("observes") else set())
            # The cited trail's steps that took something from a sibling drawn here.
            keep |= {s["id"] for s in steps.values() for link in s["links"] if trail_of(link["probe"]) in ends and s["id"] != "step-0"}
        keep = sorted((sid for sid in keep if sid in steps), key=seq)
        rows.append((y, name, keep, steps))
        for x, sid in enumerate(keep):
            at[(name, sid)] = (LABEL + x * (BOX + GAP), 12 + y * ROW)
    width = LABEL + max((len(k) for _, _, k, _ in rows), default=1) * (BOX + GAP)
    out = [
        (
            f'<svg width="{width}" height="{len(rows) * ROW + 8}" role="img" aria-label="Steps the resolution rests on">'
            '<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L8,4 L0,8 z" fill="var(--ink2)"/></marker></defs>'
        )
    ]
    for y, name, keep, steps in rows:
        top = 12 + y * ROW
        out.append(f'<line class="row" x1="{LABEL - 6}" x2="{width}" y1="{top + 14}" y2="{top + 14}"/>')
        tag = "cited trail" if name == cited_trail else f"to {ends[name]}" if name in ends else "a sealed read"
        out.append(
            f'<text x="4" y="{top + 12}" class="small">{e(name)}</text><text x="4" y="{top + 26}" class="small muted">{e(tag)}</text>'
        )
        for sid in keep:
            x, _ = at[(name, sid)]
            step, read = steps[sid], reads.get((name, sid))
            cls = ["box"]
            if read:
                cls += ["read"] + (["re"] if "re-execution" in read["how"] else [])
            if sid == res["step"]:
                cls.append("hit" if res["holds"] else "miss")
            label = sid + (" ✓" if sid == res["step"] and res["holds"] else " ✗" if sid == res["step"] else "")
            tip = f"{name} {sid} ({step['kind']}): {step['summary']}"
            if read:
                tip += f"\nOpened a sealed input ({read['how']})." + (f" Excused: {read['why']}" if read["why"] else " Not excused.")
            out.append(
                f'<a href="/trail/{e(name)}#{e(sid)}"><title>{e(tip)}</title>'
                f'<rect class="{" ".join(cls)}" x="{x}" y="{top}" width="{BOX}" height="28" rx="5"/>'
                f'<text x="{x + BOX / 2}" y="{top + 18}" text-anchor="middle" class="small">{e(label)}</text></a>'
            )
    # From each sibling's last step drawn to the cited trail's step that took it, or else to the cited step.
    cited_steps = next((r[3] for r in rows if r[1] == cited_trail), {})
    for name, end in ends.items():
        if (name, end) not in at or (cited_trail, res["step"]) not in at:
            continue
        taker = next(
            (
                s["id"]
                for s in cited_steps.values()
                if (cited_trail, s["id"]) in at and any(trail_of(l["probe"]) == name for l in s["links"])
            ),
            res["step"],
        )
        (x1, y1), (x2, y2) = at[(name, end)], at[(cited_trail, taker)]
        feeds.append(
            f'<path class="feed" d="M{x1 + BOX / 2},{y1 + 28} C{x1 + BOX / 2},{y2 - 10} {x2 + BOX / 2},{y1 + 40} {x2 + BOX / 2},{y2 - 2}"/>'
        )
    return "".join(out + feeds) + "</svg>"


def measured(node: dict, step: dict | None) -> str:
    if not step or not step.get("measures"):
        return ""
    rows = []
    for criterion in node["criteria"]:
        name = criterion.split(" ")[0]
        value = step["measures"].get(name)
        if value is None:
            rows.append(f"<tr><td>{e(criterion)}</td><td>not measured</td></tr>")
            continue
        op, bound = criterion.split(" ")[1], float(criterion.split(" ")[2])
        holds = value >= bound if op == ">=" else value <= bound if op == "<=" else value == bound
        rows.append(f"<tr><td>{e(criterion)}</td><td class='{'ok' if holds else 'no'}'>{value:g} {'✓' if holds else '✗'}</td></tr>")
    return "<table class='measures'><tr><th>Criterion</th><th>Measured</th></tr>" + "".join(rows) + "</table>"


def rule(kind: str, key: str, dispute: str) -> str:
    return (
        f'<div class="rule" data-kind="{e(kind)}" data-key="{e(key)}">'
        f'<label><input type="radio" name="{e(key)}" value="confirm"> Confirm</label>'
        f'<label><input type="radio" name="{e(key)}" value="dispute"> Dispute</label>'
        f'<input type="text" placeholder="{e(dispute)}" aria-label="Note"></div>'
    )


def resolution_card(node: dict, res: dict, lanes: dict[str, dict]) -> str:
    name = trail_of(res["probe"] or res["cites"])
    step = next((s for s in lanes[name]["steps"] if s["id"] == res["step"]), None) if name in lanes else None
    excused = [r for r in res.get("reads", []) if r["why"]]
    head = f"{node['id']}: {'reached' if res['holds'] else 'refuted'} by {name} {res['step']}"
    parts = [
        f'<article class="card" id="res-{e(node["id"])}-{e(name)}-{e(res["step"])}"><h3>{"✓" if res["holds"] else "✗"} {e(head)}</h3>',
        f"<p class='sub'>{e(node['statement'])}</p>",
    ]
    if step and step.get("plan"):
        parts.append(f"<p>The plan it tested: {e(step['plan'])}</p>")
    parts.append(measured(node, step))
    for read in excused:
        parts.append(
            f"<p class='why'><a href='/trail/{e(trail_of(read['run']) if '#' in read['run'] else name)}#{e(read['run'].split('#')[-1])}'>"
            f"{e(read['run'])}</a> opened data/heldout.csv ({e(read['how'])}). Excused by the revision: {e(read['why'])}</p>"
        )
    others = [r for r in res.get("reads", []) if not r["why"]]
    if others:
        parts.append(
            "<p class='sub'>Reads found only on re-execution, a lead and not proof: "
            + ", ".join(f"{e(r['run'])} ({e(r['how'])})" for r in others)
            + "</p>"
        )
    if res.get("rests_on"):
        parts.append(f"<p class='sub'>Rests on: {e(', '.join(res['rests_on']))}</p>")
    if name in lanes:
        parts.append(f"<div class='graph'>{graph(res, lanes, name)}</div>")
    key = f"res|{node['id']}|{project.unpinned(res['cites'])}"
    question = "Why you dispute this credit (it becomes the withdrawal's why)" if res["holds"] else "A note on this refutation"
    parts.append(rule("resolution", key, question) + "</article>")
    return "".join(parts)


SCRIPT = """<script>
const draft = JSON.parse(document.getElementById("draft").textContent);
const rev = Number(document.body.dataset.next);
function rulings() {
  return [...document.querySelectorAll(".rule")].map(div => ({
    kind: div.dataset.kind, key: div.dataset.key,
    title: div.closest("article").querySelector("h3").textContent.trim(),
    choice: (div.querySelector("input[type=radio]:checked") || {}).value || null,
    note: div.querySelector("input[type=text]").value.trim(),
  }));
}
function compose() {
  const all = rulings(), lines = [];
  const confirmed = all.filter(r => r.choice === "confirm"), disputed = all.filter(r => r.choice === "dispute");
  lines.push(`I reviewed the map at revision ${rev - 1} on the review page, following each credit's steps to the trails. I re-ran nothing.`);
  if (confirmed.length) lines.push(`I confirm: ${confirmed.map(r => r.title + (r.note ? ` (${r.note})` : "")).join("; ")}.`);
  if (disputed.length) lines.push(`I dispute: ${disputed.map(r => r.title + (r.note ? `: ${r.note}` : "")).join("; ")}.`);
  const open = all.filter(r => !r.choice).length;
  if (open) lines.push(`${open} item(s) I did not rule on.`);
  document.getElementById("reason").value = lines.join("\\n\\n");
  count();
}
function count() {
  const n = document.getElementById("reason").value.length;
  document.getElementById("count").textContent = `${n} of 4,000 characters`;
}
function build() {
  const out = JSON.parse(JSON.stringify(draft)), withdrawn = [], problems = [];
  for (const r of rulings()) {
    if (r.kind !== "resolution" || r.choice !== "dispute") continue;
    const [, node, cites] = r.key.split("|");
    if (!r.note) { problems.push(`say why you dispute ${node}`); continue; }
    const i = out.resolutions.findIndex(x => x.node === node && x.cites.replace(/@[^#]*#/, "#") === cites);
    if (i >= 0) { withdrawn.push({ node, cites: out.resolutions[i].cites, why: r.note.slice(0, 1000) }); out.resolutions.splice(i, 1); }
  }
  if (withdrawn.length) out.withdrawn = withdrawn;
  out.reason = document.getElementById("reason").value.trim();
  if (!out.reason) problems.push("write a reason");
  if (out.reason.length > 4000) problems.push("the reason is over 4,000 characters");
  return [out, problems];
}
function download() {
  const [out, problems] = build();
  document.getElementById("problem").textContent = problems.length ? "Not yet: " + problems.join("; ") + "." : "";
  if (problems.length) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2) + "\\n"], { type: "application/json" }));
  a.download = `rev-${rev}-draft.json`;
  a.click();
}
async function seal() {
  const [out, problems] = build(), who = document.getElementById("who").value.trim(), say = document.getElementById("problem");
  if (!/^[A-Za-z0-9._@-]{1,100}$/.test(who)) problems.push("give your name");
  say.textContent = problems.length ? "Not yet: " + problems.join("; ") + "." : "";
  if (problems.length) return;
  if (!confirm(`Seal revision ${rev} as human:${who}? It is written to the map and cannot be unsealed, only followed by another revision.`)) return;
  const button = document.getElementById("seal");
  button.disabled = true;
  say.textContent = "Sealing…";
  try {
    const reply = await fetch("/seal", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: document.body.dataset.token, rev, by: `human:${who}`, draft: out }),
    });
    const result = await reply.json();
    if (result.ok) {
      say.textContent = "";
      document.getElementById("sealed").innerHTML = "";
      const p = document.createElement("p");
      p.className = "ok";
      p.textContent = `Sealed: ${result.path}. ${result.check}`;
      document.getElementById("sealed").append(p);
    } else {
      say.textContent = "Not sealed: " + (result.errors || ["unknown error"]).join("; ");
      button.disabled = false;
    }
  } catch (err) { say.textContent = "Not sealed: " + err; button.disabled = false; }
}
function command() {
  const name = document.getElementById("who").value.trim() || "NAME";
  document.getElementById("cmd").textContent = document.getElementById("cmd").dataset.template.replace("NAME", name);
}
document.addEventListener("change", ev => { if (ev.target.closest(".rule")) compose(); });
document.addEventListener("input", ev => { if (ev.target.closest(".rule")) compose(); });
document.getElementById("reason").addEventListener("input", count);
document.getElementById("who").addEventListener("input", command);
document.getElementById("download").addEventListener("click", download);
if (document.getElementById("seal")) document.getElementById("seal").addEventListener("click", seal);
compose(); command();
</script>"""


def page(live: dict, revs: list[dict], map_dir: str, live_dir: str | None, token: str | None = None) -> str:
    """The review page for the map's next revision: every judgment, with the steps under it, and a draft to download."""
    lanes = {lane["trail"]: lane for lane in live["trails"]}
    nxt = live["rev"] + 1
    excused, refuted, plain = [], [], []
    for node in live["nodes"]:
        for res in node["resolutions"]:
            card = resolution_card(node, res, lanes)
            (excused if any(r["why"] for r in res.get("reads", [])) else plain if res["holds"] else refuted).append(card)
    abandoned = [
        f'<article class="card" id="route-{e(r["id"])}"><h3>Route {e(r["id"])} abandoned</h3>'
        f"<p class='sub'>{e(r['method'])}</p><p class='why'>{e(r['why'])}</p>"
        + rule("route", f"route|{r['id']}", "A note (to reverse it, the draft's route needs editing by hand)")
        + "</article>"
        for r in live["routes"]
        if r["status"] == "abandoned"
    ]
    withdrawn = [
        f'<article class="card"><h3>{e(h["node"])}: a credit withdrawn at rev-{h["dropped"]}</h3>'
        f"<p class='sub'>{e(h['cites'])}, stood rev-{h['from']} to rev-{h['dropped']}</p>"
        f"<p class='why'>{e(h['why'] or 'No reason recorded in the data; see that revision.')}</p>"
        + rule("withdrawn", f"withdrawn|{h['node']}|{h['cites']}", "A note")
        + "</article>"
        for h in live["withdrawn"]
    ]
    reasons = [
        f'<article class="card" id="rev-{r["rev"]}"><h3>Revision {r["rev"]}, sealed by {e(r["by"])}</h3>'
        f"<p class='sub'>{e(r['at'])}: {r['sealed']} resolutions sealed, {r['dropped']} dropped</p>"
        f"<details{' open' if r['rev'] == live['rev'] else ''}><summary>The reason</summary><pre class='reason'>{e(r['reason'])}</pre></details>"
        + rule("revision", f"rev|{r['rev']}", "A note on this revision's judgment")
        + "</article>"
        for r in reversed(live["revisions"])
    ]
    by = sorted({r["by"] for r in live["revisions"]})
    people = [b for b in by if b.startswith("human:")]
    blob = json.dumps(draft(revs), ensure_ascii=False).replace("<", "\\u003c")
    flags = f" --live {live_dir}" if live_dir else ""
    template = f"uv run python project.py seal {map_dir} ~/Downloads/rev-{nxt}-draft.json --by human:NAME{flags}\n" + (
        f"uv run python project.py check {map_dir}{flags}"
    )

    def section(title: str, intro: str, cards: list[str], folded: bool = False) -> str:
        if not cards:
            return ""
        body = "".join(cards)
        if folded:
            body = f"<details><summary>Show {len(cards)}</summary>{body}</details>"
        return f"<h2>{e(title)} ({len(cards)})</h2><p class='sub'>{e(intro)}</p>{body}"

    main = (
        f"<h1>Countersign revision {nxt} of {e(live['project'])}</h1>"
        f"<p class='sub'><a href='/'>← the map</a>. Revision {live['rev']} is the map now. Its {len(live['revisions'])} revisions were sealed by "
        f"{e(', '.join(by))}{'' if people else ', none by a person'}. Rule on each judgment below. Each box in a graph is a step: "
        "click it to read the step on its trail's page. An amber outline is a run that opened data/heldout.csv (dashed: found only on re-execution).</p>"
        + section(
            "Credits that stand on an excused read",
            "A revision judged that these reads of the held-out file reached no design, so the credit stands.",
            excused,
        )
        + section(
            "Refutations", "Measured against the milestone's criteria by check; no judgment is needed, but you may note one.", refuted
        )
        + section("Abandoned routes", "Judgments: an agent ended these routes.", abandoned)
        + section("Withdrawn credits", "Judgments: a revision dropped these credits.", withdrawn)
        + section(
            "Every revision's reason",
            "The judgments the map has no field for (second looks not credited, a held-out look not recorded) are in these.",
            reasons,
        )
        + section("The other credits", "Reached with no sealed read excused.", plain, folded=True)
        + "<section class='seal'><h2>Your reason</h2>"
        "<p class='sub'>Composed from your rulings; edit it freely. A disputed credit is moved to withdrawn, with your note as why.</p>"
        "<textarea id='reason' aria-label='Reason'></textarea><p class='sub' id='count'></p>"
        "<p><label>Your name: human:<input id='who' value='' placeholder='name'></label> "
        + ("<button id='seal' type='button'>Seal revision " + str(nxt) + "</button> " if token else "")
        + "<button id='download' type='button'>Download the draft</button> <span id='problem'></span></p><div id='sealed'></div>"
        + (
            "<p class='sub'>Seal writes the revision to the map after the same check as <code>project.py seal</code>; "
            "commit it afterwards. Or download the draft and seal it yourself:</p>"
            if token
            else "<p class='sub'>Then seal it. This page writes nothing; seal checks the draft.</p>"
        )
        + f"<code class='cmd' id='cmd' data-template='{e(template)}'></code>"
        "</section>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Countersign {e(live['project'])}</title><style>{CSS}{REVIEW_CSS}</style></head>"
        f'<body data-next="{nxt}" data-token="{e(token or "")}"><main>{main}</main>'
        f'<script type="application/json" id="draft">{blob}</script>{SCRIPT}</body></html>\n'
    )


def seal(directory: Path, revs: list[dict], trails: "project.Trails", payload: object) -> tuple[int, dict]:
    """A seal asked for from the page: the same check as `project.py seal`, by a person only, at the revision they reviewed."""
    if not isinstance(payload, dict) or not isinstance(payload.get("draft"), dict) or not isinstance(payload.get("by"), str):
        return 400, {"ok": False, "errors": ["the request needs draft and by"]}
    by = payload["by"]
    if not by.startswith("human:") or not project.ACTOR.fullmatch(by):
        return 400, {"ok": False, "errors": ["by must be human:NAME: the page seals for a person only"]}
    if payload.get("rev") != len(revs):
        return 409, {"ok": False, "errors": [f"the map is at rev-{len(revs) - 1} now; reload the page and review again"]}
    at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    revision, errors = project.seal(revs, payload["draft"], by, at, trails)
    if errors:
        return 422, {"ok": False, "errors": errors}
    path = project.write(directory, revision)
    if path is None:
        return 409, {"ok": False, "errors": [f"rev-{revision['rev']} was sealed meanwhile; reload the page"]}
    return 200, {
        "ok": True,
        "rev": revision["rev"],
        "path": str(path),
        "check": f"check: ok, {len(revs) + 1} revisions, {len(revision['resolutions'])} resolutions, {len(trails.steps)} trails.",
    }

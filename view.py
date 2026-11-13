"""What a reviewer reads of a checked trail: `why`, the answer to "why did the plan change?", and the page.

Nothing here infers. Every sentence is a fixed template filled from steps and their links, and an
agent's text is shown whole and unchanged, so the view can state no cause that a link does not carry.
"""

import html
import subprocess
from pathlib import Path

import trail

OUTCOMES = {"as_expected": "as expected", "contradicted": "contradicted", "failed": "failed", "inconclusive": "inconclusive"}


def number(value: float) -> str:
    return format(value, "g")


def linked(step: dict, relation: str) -> list[str]:
    return [link["target"] for link in step.get("links", []) if link["relation"] == relation]


def implemented(run: dict, by_id: dict) -> dict | None:
    plans = [by_id[target] for target in linked(run, "implements") if target in by_id]
    return plans[0] if plans else None


def missed(observation: dict, by_id: dict) -> list[dict]:
    """What the observation shows against the plan its run implements: the exit code of a failed run,
    and each expectation whose check did not hold."""
    plan = implemented(by_id[trail.observed(observation)], by_id)
    expectations = {e["name"]: e for e in plan["expectations"]} if plan else {}
    found = [{"exit_code": observation["exit_code"]}] if observation["outcome"] == "failed" else []
    for check in observation.get("checks", []):
        expectation = expectations.get(check["expectation"])
        if check["held"] or expectation is None:
            continue
        if expectation["comparison"] in trail.EXIT:
            if not found:
                found.append({"exit_code": observation["exit_code"], **expectation})
            continue
        found.append({**expectation, "measured": check["measured"]})
    return found


def expected(miss: dict) -> str:
    """One missed expectation, as `why` prints it: auc 0.58, expected >= 0.75 (auc-floor)."""
    if "exit_code" in miss:
        return f"exit code {miss['exit_code']}" + (f", expected {miss['comparison']} ({miss['name']})" if "name" in miss else "")
    return f"{miss['measure']} {number(miss['measured'])}, expected {trail.COMPARISONS[miss['comparison']]} {number(miss['threshold'])} ({miss['name']})"


def changes(steps: list[dict]) -> list[dict]:
    """Each change of approach: a plan that supersedes an earlier plan, with the plans it replaced and
    its triggers. A trigger in this trail is its observation; one in another probe stays a citation."""
    by_id = {step["id"]: step for step in steps}
    found = []
    for step in steps:
        replaced = [by_id[target] for target in linked(step, "supersedes") if by_id.get(target, {}).get("kind") == "plan"]
        if step["kind"] == "plan" and replaced:
            found.append(
                {"plan": step, "replaced": replaced, "triggers": [by_id.get(target, target) for target in linked(step, "triggered_by")]}
            )
    return found


def shown(trigger: dict | str, by_id: dict) -> str:
    """The trigger as one clause of the decision path's sentence."""
    if isinstance(trigger, str):
        return f"triggered by {trigger}"
    parts = []
    for miss in missed(trigger, by_id):
        if "exit_code" in miss:
            parts.append(f"exited with code {miss['exit_code']}")
        else:
            parts.append(
                f"measured {miss['measure']} {number(miss['measured'])}, "
                f"expected {trail.COMPARISONS[miss['comparison']]} {number(miss['threshold'])}"
            )
    return f"{trigger['id']} " + ("; ".join(parts) or f"came out {OUTCOMES[trigger['outcome']]}")


def sentence(change: dict, by_id: dict) -> str:
    return f"At {change['plan']['id']} the plan changed: " + "; ".join(shown(t, by_id) for t in change["triggers"]) + "."


def said(steps: list[dict], about: set[str]) -> list[dict]:
    """The reviews and notes on any of these steps, in trail order."""
    return [
        step
        for step in steps
        if step["kind"] in ("review", "note") and any(target in about for target in linked(step, "reviews") + linked(step, "about"))
    ]


def verdict(step: dict) -> str:
    return step.get("verdict", "note")


def involved(change: dict, steps: list[dict]) -> dict[str, list[str]]:
    """Each step that took part in a change of approach other than the new plan, and the parts it took."""
    roles: dict[str, list[str]] = {}
    for trigger in change["triggers"]:
        if isinstance(trigger, dict):
            roles.setdefault(trigger["id"], []).append("the trigger")
            roles.setdefault(trail.observed(trigger), []).append(f"the run the trigger {trigger['id']} observes")
    for plan in change["replaced"]:
        roles.setdefault(plan["id"], []).append(f"the replaced plan {plan['id']}")
        for run in (step for step in steps if step["kind"] == "run" and plan["id"] in linked(step, "implements")):
            roles.setdefault(run["id"], []).append(f"a run under the replaced plan {plan['id']}")
            for observation in (step for step in steps if step["kind"] == "observation" and trail.observed(step) == run["id"]):
                if observation not in change["triggers"]:
                    roles.setdefault(observation["id"], []).append(f"an observation under the replaced plan {plan['id']}")
    return roles


def why(steps: list[dict], step: str | None = None) -> list[str]:
    """The answer to "why did the plan change at STEP?", from the links alone. With no step, one line per
    change of approach. Raises LookupError for a step the trail does not have."""
    by_id = {s["id"]: s for s in steps}
    found = changes(steps)
    if step is None:
        return [sentence(change, by_id) for change in found] or ["No plan was replaced."]
    if step not in by_id:
        raise LookupError(f"{step} is not in this trail")
    change = next((change for change in found if change["plan"]["id"] == step), None)
    if change is None:
        parts = [f"at {c['plan']['id']} as " + " and ".join(roles[step]) for c in found if step in (roles := involved(c, steps))]
        return [
            f"{step} is {trail.a(by_id[step]['kind'])} step, not a change of approach; "
            + (f"it took part in the change of approach {', and '.join(parts)}." if parts else "it took part in no change of approach.")
        ]
    plan = change["plan"]
    lines = [f"Change of approach at {plan['id']}"]
    lines += [f"Replaced plan: {old['id']}, {old['summary']}" for old in change["replaced"]]
    for trigger in change["triggers"]:
        if isinstance(trigger, str):
            lines.append(f"Trigger: {trigger}")
            continue
        lines.append(f"Trigger: {trigger['id']}, {OUTCOMES[trigger['outcome']]}")
        lines += [f"  {expected(miss)}" for miss in missed(trigger, by_id)]
    lines += [f"New plan: {plan['id']}, {plan['summary']}", "Reasoning:", plan["reasoning"]]
    about = {plan["id"], *(old["id"] for old in change["replaced"]), *(t["id"] for t in change["triggers"] if isinstance(t, dict))}
    lines += [f"{s['id']}, {verdict(s)}: {s['text']}" for s in said(steps, about)]
    return lines


# The page: one file, inline CSS, no script and nothing fetched, so it opens anywhere and shows only the
# trail. Every string from a step goes through e(), because an agent wrote it.
CSS = """
:root{color-scheme:light dark;--bg:#faf9f6;--surface:#fff;--fg:#1f1e1c;--muted:#64625d;--line:#e2dfd8;--accent:#2b5c8f;
--code:#f2f0eb;--ok:#2d6a3e;--ok-bg:#e3f1e6;--bad:#a23a22;--bad-bg:#f8e4de;--warn:#7d5a00;--warn-bg:#f5ecd2;--tag:#55534e;--tag-bg:#ebe9e4}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--surface:#1c1c1a;--fg:#e9e7e2;--muted:#a19f99;--line:#34332f;--accent:#8fb6e0;
--code:#252522;--ok:#9ad3a6;--ok-bg:#1f3325;--bad:#f0a08c;--bad-bg:#3b221b;--warn:#e6c26b;--warn-bg:#352c14;--tag:#c4c2bc;--tag-bg:#2b2a27}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:52rem;margin:0 auto;padding:2.5rem 1rem 4rem}
h1{font-size:1.75rem;line-height:1.25;margin:.25rem 0 .75rem}
h2{font-size:1.15rem;margin:2.5rem 0 .75rem;padding-bottom:.35rem;border-bottom:1px solid var(--line)}
h3{font-size:1.02rem;margin:0;line-height:1.4}
h4{font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:1.1rem 0 .3rem}
p{margin:.35rem 0}
a{color:var(--accent)}
code,pre,.id{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.88em}
code{overflow-wrap:anywhere;background:var(--code);padding:.05em .3em;border-radius:4px}
pre{background:var(--code);padding:.75rem;border-radius:6px;overflow-x:auto;max-width:100%;font-size:.8rem;line-height:1.45;margin:.5rem 0}
.eyebrow{color:var(--muted);font-size:.85rem;margin:0;overflow-wrap:anywhere}
.question{font-size:1.05rem}
.meta,.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:.15rem 1rem;font-size:.9rem}
.meta{margin:1rem 0 0}.kv{margin:.4rem 0 0}
.meta dt,.kv dt{color:var(--muted)}
.meta dd,.kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
.path{padding-left:1.25rem}.path li{margin:.4rem 0}
.card,.plan,.task,.loose{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;margin:1rem 0;min-width:0}
.card{border-left:4px solid var(--accent)}
.by{color:var(--muted);font-size:.85rem;overflow-wrap:anywhere}
.reasoning,.text{white-space:pre-wrap;overflow-wrap:anywhere}
.expect,.missed,.said,.facts,.came{padding-left:1.1rem;margin:.35rem 0}
.runs{list-style:none;padding:0;margin:.75rem 0 0}
.run{border-top:1px solid var(--line);padding:.6rem 0;min-width:0}
.outcome{display:inline-block;font-size:.78rem;font-weight:600;padding:0 .45rem;border-radius:999px;white-space:nowrap}
.o-as_expected{color:var(--ok);background:var(--ok-bg)}
.o-contradicted,.o-failed{color:var(--bad);background:var(--bad-bg)}
.o-inconclusive,.o-unsettled{color:var(--warn);background:var(--warn-bg)}
.tag{font-size:.75rem;font-weight:600;color:var(--tag);background:var(--tag-bg);padding:0 .45rem;border-radius:999px;white-space:nowrap}
.v-confirms{color:var(--ok)}.v-disputes{color:var(--bad)}
details{margin:.6rem 0}summary{cursor:pointer;color:var(--muted);font-size:.9rem}
.said li,.came li,.missed li{margin:.3rem 0}
@media (max-width:480px){main{padding:1.5rem 1rem 3rem}h1{font-size:1.4rem}.meta,.kv{grid-template-columns:minmax(0,1fr)}.meta dd,.kv dd{margin-bottom:.3rem}}
"""
DIFF_LINES = 400


def e(text: object) -> str:
    return html.escape(str(text))


def ref(step_id: str) -> str:
    return f'<a class="id" href="#{e(step_id)}">{e(step_id)}</a>'


def outcome(observation: dict | None) -> str:
    kept = observation["outcome"] if observation else "unsettled"
    return f'<span class="outcome o-{e(kept)}">{e(OUTCOMES.get(kept, kept))}</span>'


def promise(expectation: dict) -> str:
    """One expectation in words: auc-floor: auc >= 0.75."""
    comparison = expectation["comparison"]
    if comparison in trail.EXIT:
        said = "the command exits 0" if comparison == "exit_ok" else "the command exits non-zero"
    else:
        said = f"{expectation['measure']} {trail.COMPARISONS[comparison]} {number(expectation['threshold'])}"
    return f"<li>{e(expectation['name'])}: {e(said)}</li>"


def promises(plan: dict) -> str:
    return '<ul class="expect">' + "".join(promise(x) for x in plan["expectations"]) + "</ul>"


def parameters(run: dict) -> str:
    """Public parameters with their values; the others by name only, since the trail keeps only their digest."""
    shown = [f"{p['name']} = {p['value']}" for p in run.get("parameters", []) if "value" in p]
    withheld = [p["name"] for p in run.get("parameters", []) if "value" not in p]
    parts = [e(part) for part in shown] + ([f"withheld: {e(', '.join(withheld))}"] if withheld else [])
    return " · ".join(parts) or "none"


def measures(observation: dict) -> str:
    return " · ".join(e(f"{m['name']} {number(m['value'])}" + (f" {m['unit']}" if "unit" in m else "")) for m in observation.get("measures", []))


def remarks(kept: list[dict]) -> str:
    """Reviews and notes, each with who wrote it and its text whole."""
    if not kept:
        return ""
    items = []
    for step in kept:
        word = verdict(step)
        items.append(f'<li id="{e(step["id"])}">{ref(step["id"])} <b class="v-{e(word)}">{e(word)}</b> '
                     f'<span class="by">by {e(step["by"])} · {e(step["at"])}</span><div class="text">{e(step["text"])}</div></li>')
    return '<ul class="said">' + "".join(items) + "</ul>"


class Trail:
    """The lookups the page needs: each plan's runs, each run's observation, and where each review or note sits."""

    def __init__(self, steps: list[dict], code: Path | None):
        self.steps, self.code = steps, code
        self.by_id = {step["id"]: step for step in steps}
        self.settlement = {trail.observed(step): step for step in steps if step["kind"] == "observation"}
        self.runs: dict[str, list[dict]] = {}
        for step in steps:
            if step["kind"] == "run":
                self.runs.setdefault(linked(step, "implements")[0], []).append(step)
        self.under: dict[str, list[dict]] = {}
        for step in steps:
            if step["kind"] in ("review", "note"):
                self.under.setdefault(self.anchor(step), []).append(step)
        # A code change shows on the measured run whose reference differs from the measured run before it.
        self.code_changes, before = {}, None
        for step in steps:
            if step["kind"] == "run" and self.measured(step):
                if before and before != step["code"]["ref"]:
                    self.code_changes[step["id"]] = (before, step["code"]["ref"])
                before = step["code"]["ref"]

    def anchor(self, step: dict) -> str:
        """The step a review or note sits under: a plan, a run (for its observation too), or the task."""
        targets = linked(step, "reviews") + linked(step, "about")
        target = self.by_id.get(targets[0]) if targets else None
        if target is None:
            return "elsewhere"
        if target["kind"] == "observation":
            return trail.observed(target)
        if target["kind"] in ("review", "note"):
            return self.anchor(target)
        return target["id"]

    def measured(self, run: dict) -> bool:
        return bool(self.settlement.get(run["id"], {}).get("measures_source"))

    def exploratory(self, run: dict) -> bool:
        return run["id"] in self.settlement and not self.measured(run)


def header(steps: list[dict]) -> str:
    task = steps[0]
    agent = task["agent"]
    who = f"{agent['name']} {agent['version']}, model {agent['model']}" + (f", thinking {agent['thinking']}" if "thinking" in agent else "")
    rows = [("Agent", e(who)), ("Trail", e(task["trail"])), ("Steps", str(len(steps))),
            ("Head", f"<code>{e(trail.digest(trail.canonical(steps[-1])))}</code>")]
    rows += [("Builds on", f"<code>{e(target)}</code>") for target in linked(task, "builds_on")]
    return (f'<header><p class="eyebrow">Provenance trail · {e(task.get("project", ""))}</p><h1>{e(task["summary"])}</h1>'
            f'<p class="question">{e(task["question"])}</p><dl class="meta">'
            + "".join(f"<dt>{name}</dt><dd>{value}</dd>" for name, value in rows) + "</dl></header>")


def path(found: list[dict], by_id: dict) -> str:
    if not found:
        return '<section id="decision-path"><h2>Decision path</h2><p>The plan was never replaced.</p></section>'
    items = "".join(f'<li><a href="#change-{e(c["plan"]["id"])}">{e(sentence(c, by_id))}</a></li>' for c in found)
    return f'<section id="decision-path"><h2>Decision path</h2><ol class="path">{items}</ol></section>'


def card(change: dict, view: Trail) -> str:
    plan, by_id = change["plan"], view.by_id
    parts = [f'<article class="card" id="change-{e(plan["id"])}"><h3>At {ref(plan["id"])} the plan changed</h3>']
    for old in change["replaced"]:
        parts.append(f'<h4>Replaced plan</h4><p>{ref(old["id"])} {e(old["summary"])}</p>{promises(old)}')
    for trigger in change["triggers"]:
        if isinstance(trigger, str):
            parts.append(f"<h4>Trigger</h4><p>Another probe: <code>{e(trigger)}</code></p>")
            continue
        run = by_id[trail.observed(trigger)]
        missed_items = "".join(f"<li>{e(expected(miss))}</li>" for miss in missed(trigger, by_id))
        parts.append(f'<h4>Trigger</h4><p>{ref(trigger["id"])} {outcome(trigger)} {e(trigger["summary"])}</p>'
                     f'<dl class="kv"><dt>Run</dt><dd>{ref(run["id"])} <code>{e(run["command"]["shown"])}</code></dd>'
                     f"<dt>Parameters</dt><dd>{parameters(run)}</dd></dl>"
                     + (f'<ul class="missed">{missed_items}</ul>' if missed_items else ""))
    parts.append(f'<h4>New plan</h4><p>{ref(plan["id"])} {e(plan["summary"])}</p>'
                 f'<div class="reasoning">{e(plan["reasoning"])}</div>{promises(plan)}')
    came = [f"<li>{ref(run['id'])} {outcome(view.settlement[run['id']])} {measures(view.settlement[run['id']])}</li>"
            for run in view.runs.get(plan["id"], []) if view.measured(run)]
    parts.append("<h4>How its measured runs came out</h4>" + (f'<ul class="came">{"".join(came)}</ul>' if came else "<p>No measured run.</p>"))
    about = {plan["id"], *(old["id"] for old in change["replaced"]), *(t["id"] for t in change["triggers"] if isinstance(t, dict))}
    kept = said(view.steps, about)
    parts.append("<h4>Reviews and notes</h4>" + (remarks(kept) or "<p>None.</p>") + "</article>")
    return "".join(parts)


def diff(code: Path | None, before: str, after: str) -> str:
    """The code change between two measured runs: the diff from the repository when it has both commits,
    or else the two references."""
    shown = f"<p>Code changed from <code>{e(before)}</code> to <code>{e(after)}</code>.</p>"
    if code is None:
        return shown
    commits = [kept.split("@")[-1].removeprefix("commit:") for kept in (before, after)]
    done = subprocess.run(["git", "-C", str(code), "diff", "--no-color", "--no-ext-diff", *commits],
                          capture_output=True, text=True, check=False)
    if done.returncode:
        return shown
    lines = done.stdout.splitlines()
    cut = f"\n… {len(lines) - DIFF_LINES} more lines left out" if len(lines) > DIFF_LINES else ""
    return (f"<details><summary>Code changed from {e(before)} to {e(after)}: the diff</summary>"
            f"<pre>{e(chr(10).join(lines[:DIFF_LINES]) + cut)}</pre></details>")


def run_item(run: dict, view: Trail) -> str:
    observation = view.settlement.get(run["id"])
    if observation is None:
        result = f"{outcome(None)} no observation: the run never settled"
    else:
        result = f'<span id="{e(observation["id"])}">{ref(observation["id"])}</span> {outcome(observation)} {e(observation["summary"])}'
    rows = [("Parameters", parameters(run)), ("Code", f"<code>{e(run['code']['ref'])}</code>")]
    if observation and observation.get("measures"):
        rows.append(("Measures", measures(observation)))
    rows.append(("Outcome", result))
    change = view.code_changes.get(run["id"])
    return (f'<li class="run" id="{e(run["id"])}"><p>{ref(run["id"])} <code>{e(run["command"]["shown"])}</code></p>'
            '<dl class="kv">' + "".join(f"<dt>{name}</dt><dd>{value}</dd>" for name, value in rows) + "</dl>"
            + (diff(view.code, *change) if change else "") + remarks(view.under.get(run["id"], [])) + "</li>")


def command_item(run: dict, view: Trail) -> str:
    """An exploratory command: what ran and how it exited; it measured nothing."""
    observation = view.settlement[run["id"]]
    return (f'<li class="run" id="{e(run["id"])}"><p>{ref(run["id"])} <code>{e(run["command"]["shown"])}</code></p>'
            f'<p><span id="{e(observation["id"])}">{ref(observation["id"])}</span> {outcome(observation)} '
            f'exit code {e(observation["exit_code"])}</p>{remarks(view.under.get(run["id"], []))}</li>')


def plan_item(plan: dict, view: Trail) -> str:
    runs = view.runs.get(plan["id"], [])
    attempts = [run for run in runs if not view.exploratory(run)]
    explored = [run for run in runs if view.exploratory(run)]
    exploration = all(x["comparison"] in trail.EXIT for x in plan["expectations"])
    links = [f"{relation.replace('_', ' ')} " + (ref(t) if t in view.by_id else f"<code>{e(t)}</code>")
             for relation in ("supersedes", "triggered_by") for t in linked(plan, relation)]
    tag = ' <span class="tag">exploration plan</span>' if exploration else ""
    parts = [f'<article class="plan" id="{e(plan["id"])}"><h3>{ref(plan["id"])} {e(plan["summary"])}{tag}</h3>',
             f'<p class="by">by {e(plan["by"])} · {e(plan["at"])}' + "".join(f" · {link}" for link in links) + "</p>",
             f'<div class="reasoning">{e(plan["reasoning"])}</div>{promises(plan)}']
    if attempts:
        parts.append('<ol class="runs">' + "".join(run_item(run, view) for run in attempts) + "</ol>")
    if explored:
        failed = sum(view.settlement[run["id"]]["outcome"] == "failed" for run in explored)
        count = f"{len(explored)} exploratory command{'s' * (len(explored) != 1)}, {failed} failed"
        parts.append(f'<details><summary>{count}</summary><ol class="runs">'
                     + "".join(command_item(run, view) for run in explored) + "</ol></details>")
    if not runs:
        parts.append('<p class="by">Never run.</p>')
    return "".join(parts) + remarks(view.under.get(plan["id"], [])) + "</article>"


def timeline(view: Trail) -> str:
    task = view.steps[0]
    parts = ['<section id="timeline"><h2>Timeline</h2>',
             (f'<article class="task" id="{e(task["id"])}"><h3>{ref(task["id"])} Task</h3>'
              f'<p class="by">by {e(task["by"])} · {e(task["at"])}</p>{remarks(view.under.get(task["id"], []))}</article>')]
    parts += [plan_item(step, view) for step in view.steps if step["kind"] == "plan"]
    if loose := view.under.get("elsewhere"):
        parts.append(f'<article class="loose"><h3>On other probes</h3>{remarks(loose)}</article>')
    return "".join(parts) + "</section>"


def page(steps: list[dict], code: Path | None = None) -> str:
    """The reviewer's page of a checked trail. The same trail gives the same bytes: nothing in it depends
    on the time, the machine or the paths it was given."""
    view = Trail(steps, code)
    found = changes(steps)
    cards = "".join(card(change, view) for change in found)
    facts = "".join(f"<li>{e(fact)}</li>" for fact in trail.facts(steps)) or "<li>None.</li>"
    body = (header(steps) + path(found, view.by_id)
            + (f'<section id="changes"><h2>Changes of approach</h2>{cards}</section>' if cards else "")
            + timeline(view) + f'<section id="facts"><h2>Facts</h2><ul class="facts">{facts}</ul></section>')
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{e(steps[0]['trail'])}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>\n")

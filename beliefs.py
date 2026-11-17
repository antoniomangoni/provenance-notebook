"""Beliefs over the research map: how sure each ✓ and ✗ is, what bears on an open milestone, and
how well a forecaster foresaw what the trails then showed.

Usage: beliefs.py COMMAND MAP --live DIR [options]

The map is a small belief network: a milestone is a variable, a route is the AND of its path and a
goal the OR of its routes. A milestone's Markov blanket is the milestone before it on each of its
routes, what comes after it (the next milestone, or the goal), and the other milestones that lead
there. It is what a forecaster is shown. It follows the order of the routes, so it leaves out what
that order does not carry: milestones measured on the same criterion over the same sealed file bear
on each other from anywhere on the map. code:pooled forecasts from those, beside code:blanket.

Nothing here changes the map. A ✓ or ✗ is still what `project.py check` recomputes from the trails;
this module only says how far a criterion's measure stands from its threshold, in standard errors
that a person or agent declared in beliefs/assumptions.json beside the map, and what follows if
those errors are right. A model may forecast; code builds the text it is shown, records that text's
digest, and scores the forecast against what the trails show and against code-only forecasters.

  show                       the belief report
  blanket NODE [--rev N]     the text a forecaster is shown for a milestone, from revision N alone
  before TRAIL STEP          the text a forecaster is shown for a plan: the trail up to and including it
  questions --out DIR [--all-open]   one prompt file per question, and questions.json; with --all-open,
                             only every unresolved milestone on an open route, at the last revision
  nominate --out DIR         the text an overseer is shown to choose the routes the next agents run
  choose DIR --by ACTOR --out FILE    the overseer's choice from DIR/answers, checked against the open routes
  collect DIR --by ACTOR --out FILE   a forecast file from DIR/answers; an answer with no probability is unanswered
  score [--truth FILE]       every forecast file in forecasts/ beside the map, scored; with --truth, also
                             against what replicate.py measured on the replication sample
  se --auc A --pos N --neg M the Hanley-McNeil standard error of an AUC

docs/specs/10-beliefs.md is the specification.
"""

import copy
import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist, mean, stdev

import project
import trail
import view

VERSION = 1
NORMAL = NormalDist()
Z95 = 1.645  # one-sided 95%
CLIP = (0.01, 0.99)
PROBABILITY = re.compile(r"^\s*\**p\**\s*[:=]\s*\**\s*([01](?:\.\d+)?|\.\d+)\s*\**\s*$", re.IGNORECASE | re.MULTILINE)
WHY = re.compile(r"^\s*\**why\**\s*[:=]\s*\**\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
ANSWER = """You are asked for a forecast. Answer with exactly two lines and nothing else:
p: <the probability, a number from 0 to 1>
why: <one sentence>"""
MARKS = project.MARKS


class Usage(Exception):
    """The command line was wrong; nothing was read."""


def se_auc(auc: float, pos: int, neg: int) -> float:
    """The standard error of an AUC from pos positive and neg negative cases (Hanley and McNeil, 1982)."""
    q1, q2 = auc / (2 - auc), 2 * auc * auc / (1 + auc)
    return math.sqrt((auc * (1 - auc) + (pos - 1) * (q1 - auc * auc) + (neg - 1) * (q2 - auc * auc)) / (pos * neg))


def noise(directory: Path) -> dict[str, dict]:
    """The declared standard error of each measure, from beliefs/assumptions.json beside the map."""
    path = directory.parent / "beliefs" / "assumptions.json"
    if not path.exists():
        return {}
    found = {entry["measure"]: entry for entry in json.loads(path.read_text())["noise"]}
    for measure, entry in found.items():
        if not isinstance(entry["se"], int | float) or isinstance(entry["se"], bool) or entry["se"] <= 0:
            raise Usage(f"{path}: the standard error of {measure} is not a positive number")
        if not project.ACTOR.fullmatch(entry.get("by", "")):
            raise Usage(f"{path}: {measure} is declared by {entry.get('by')!r}, which is not an actor")
    return found


# ---------------------------------------------------------------------------------------------
# The network


def blanket(revision: dict, node: str) -> dict[str, list[str]]:
    """The node's parents, children and co-parents. A child is the next milestone on a route, or
    goal:ID when the node ends the route. Every route counts, abandoned ones too: the structure is
    the map's, whatever became of a route."""
    parents, children, co = set(), set(), set()
    for route in revision["routes"]:
        if node in route["path"]:
            at = route["path"].index(node)
            if at:
                parents.add(route["path"][at - 1])
            children.add(route["path"][at + 1] if at + 1 < len(route["path"]) else f"goal:{route['goal']}")
    for child in children:
        for route in revision["routes"]:
            if child == f"goal:{route['goal']}":
                co.add(route["path"][-1])
            elif child in route["path"] and route["path"].index(child):
                co.add(route["path"][route["path"].index(child) - 1])
    return {"parents": sorted(parents), "children": sorted(children), "co_parents": sorted(co - {node} - parents)}


def last_resolution(revision: dict, node: str) -> dict | None:
    """The resolution that decides the node's state: its last holding one, else its last."""
    found = [r for r in revision["resolutions"] if r["node"] == node]
    holding = [r for r in found if r["holds"]]
    return (holding or found or [None])[-1]


def evidence(revision: dict, node: str, trails: project.Trails) -> tuple[dict, dict, str] | None:
    """The deciding resolution of a node, the observation it cites and the trail's name."""
    resolution = last_resolution(revision, node)
    if resolution is None:
        return None
    probe, step = trails.cite(resolution["cites"], revision["project"])
    return resolution, step, probe.split(":", 1)[1]


def noisy(node: dict, sizes: dict) -> list[dict]:
    return [c for c in node["criteria"] if c["measure"] in sizes and c["comparison"] in ("lt", "le", "ge", "gt")]


def margin(criterion: dict, value: float, se: float) -> float:
    """How far the value stands from the threshold, in standard errors, positive on the side that meets it."""
    away = value - criterion["threshold"]
    return (away if criterion["comparison"] in ("ge", "gt") else -away) / se


def bound(criterion: dict, value: float, se: float) -> float:
    """The one-sided 95% bound on the side the criterion needs."""
    return value - Z95 * se if criterion["comparison"] in ("ge", "gt") else value + Z95 * se


def p_true(node: dict, step: dict, sizes: dict) -> float:
    """P(the true value meets every noisy criterion), flat prior and independent errors; 1 when none is noisy."""
    found = project.measures(step)
    p = 1.0
    for criterion in noisy(node, sizes):
        if criterion["measure"] in found:
            p *= NORMAL.cdf(margin(criterion, found[criterion["measure"]], sizes[criterion["measure"]]["se"]))
    return p


GRID = 300  # steps of the between-route spread, from 0 to 3 standard errors


def pooled(values: list[float], se: float, criterion: dict, credited: list[int]) -> tuple[float, float]:
    """P(at least one credited route truly meets the criterion) when the routes' true values are
    related: each drawn about a shared mean with a spread tau, each score its true value with error
    se, errors independent. First with tau 0, every route sharing one true value; then with a flat
    prior on the mean and on tau from 0 to 3 se, summed on a fixed grid. A flat prior on each true
    value alone, as p_true takes, is tau without limit."""
    n, centre = len(values), mean(values)
    scatter = sum((value - centre) ** 2 for value in values)
    total = weights = 0.0
    for i in range(GRID + 1):
        tau = 3 * se * i / GRID
        spread = tau * tau + se * se  # the variance of one score about the shared mean
        weight = spread ** (-(n - 1) / 2) * math.exp(-scatter / (2 * spread))
        pull = se * se / spread  # how far a score is drawn to the shared mean
        left = math.sqrt((1 - pull) * se * se)  # the error left in a true value once the mean is known
        some = norm = 0.0
        for j in range(-40, 41):  # the shared mean, four of its standard errors either side
            shared = centre + j / 10 * math.sqrt(spread / n)
            misses = 1.0
            for k in credited:
                at = pull * shared + (1 - pull) * values[k]
                misses *= 1 - (NORMAL.cdf(margin(criterion, at, left)) if left else float(margin(criterion, at, 1.0) >= 0))
            some += math.exp(-((j / 10) ** 2) / 2) * (1 - misses)
            norm += math.exp(-((j / 10) ** 2) / 2)
        total += weight * some / norm
        weights += weight
    return NORMAL.cdf(margin(criterion, centre, se / math.sqrt(n))), total / weights


def rows_needed(away: float) -> str:
    """How many times the rows would bring a measure this many standard errors from its threshold to
    1.645 of them, were it to stay where it is: the error falls as the root of the rows."""
    times = (Z95 / abs(away)) ** 2 if away else math.inf
    return "no number of rows" if times == math.inf else f"{times:.1f} times the rows" if times < 10 else f"{times:,.0f} times the rows"


def laplace(hits: int, n: int) -> float:
    return (hits + 1) / (n + 2)


def from_scores(revision: dict, node_id: str, others: list[str], trails: project.Trails, sizes: dict, whose: str) -> tuple[float, str] | None:
    """P(the node is reached) from the scores of other milestones: for each noisy criterion, a normal
    predictive over those measured on the same criterion. None when any criterion has fewer than two."""
    nodes = {n["id"]: n for n in revision["nodes"]}
    same = ("measure", "comparison", "threshold")
    p, how = 1.0, []
    for criterion in noisy(nodes[node_id], sizes):
        values = []
        for other in others:
            found = evidence(revision, other, trails)
            shared = any(all(c[k] == criterion[k] for k in same) for c in nodes[other]["criteria"])
            if shared and found and criterion["measure"] in project.measures(found[1]):
                values.append(project.measures(found[1])[criterion["measure"]])
        if len(values) < 2:
            return None
        centre, spread = mean(values), stdev(values) * math.sqrt(1 + 1 / len(values))
        p *= NORMAL.cdf(margin(criterion, centre, spread))
        how.append(f"{criterion['measure']} of {len(values)} {whose}: mean {centre:.4f}, predictive sd {spread:.4f}")
    return (p, "; ".join(how)) if how else None


def predictive(revision: dict, node_id: str, trails: project.Trails, sizes: dict) -> tuple[float, str]:
    """P(the node is reached), from its blanket alone. For each noisy criterion, a normal predictive
    over the co-parents scored on the same criterion; with fewer than two of them, the Laplace rate
    of the blanket's resolved milestones."""
    near = blanket(revision, node_id)
    scored = from_scores(revision, node_id, near["co_parents"], trails, sizes, "co-parents")
    if scored:
        return scored
    resolved = [last_resolution(revision, n) for n in near["parents"] + near["co_parents"]]
    resolved = [r for r in resolved if r]
    rate = laplace(sum(r["holds"] for r in resolved), len(resolved))
    return rate, f"Laplace rate of the blanket: {sum(r['holds'] for r in resolved)} of {len(resolved)} resolved milestones hold"


def base_rate(revision: dict) -> float:
    """The Laplace rate of every resolution of a revision."""
    return laplace(sum(r["holds"] for r in revision["resolutions"]), len(revision["resolutions"]))


def pooled_predictive(revision: dict, node_id: str, trails: project.Trails, sizes: dict) -> tuple[float, str]:
    """P(the node is reached), from every milestone of the revision measured on the same criterion,
    wherever it stands on the map; with fewer than two, the revision's base rate. Beside the blanket's
    forecast, it tests whether the blanket is the right scope."""
    others = [n["id"] for n in revision["nodes"] if n["id"] != node_id]
    scored = from_scores(revision, node_id, others, trails, sizes, "milestones with the same criterion")
    return scored or (base_rate(revision), "the base rate of the revision's resolutions")


def node_p(revision: dict, node: str, trails: project.Trails, sizes: dict) -> float:
    """P(the node truly meets its criteria): from its deciding observation when resolved, else from its blanket."""
    found = evidence(revision, node, trails)
    nodes = {n["id"]: n for n in revision["nodes"]}
    return p_true(nodes[node], found[1], sizes) if found else predictive(revision, node, trails, sizes)[0]


def entropy(p: float) -> float:
    return 0.0 if p <= 0 or p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def goal_p(revision: dict, goal: str, trails: project.Trails, sizes: dict) -> float:
    """P(some route that is not abandoned truly meets every noisy criterion on its path), routes independent."""
    routes = [r for r in revision["routes"] if r["goal"] == goal and r["status"] != "abandoned"]
    return 1 - math.prod(1 - math.prod(node_p(revision, n, trails, sizes) for n in r["path"]) for r in routes)


def information(revision: dict, node: str, trails: project.Trails, sizes: dict) -> dict[str, float]:
    """Bits about each goal from settling the node: I(G; X), with routes independent and a route's
    chance the product of its milestones'."""
    p_node = node_p(revision, node, trails, sizes)
    bits = {}
    for goal in revision["goals"]:
        routes = [r for r in revision["routes"] if r["goal"] == goal["id"] and r["status"] != "abandoned"]
        if not any(node in r["path"] for r in routes):
            continue
        chance = {r["id"]: math.prod(node_p(revision, n, trails, sizes) for n in r["path"]) for r in routes}
        miss_without = math.prod(1 - chance[r["id"]] for r in routes if node not in r["path"])
        miss_given = math.prod(1 - chance[r["id"]] / p_node for r in routes if node in r["path"]) if p_node else 1.0
        prior = 1 - miss_without * math.prod(1 - chance[r["id"]] for r in routes if node in r["path"])
        after = p_node * entropy(1 - miss_without * miss_given) + (1 - p_node) * entropy(1 - miss_without)
        bits[goal["id"]] = entropy(prior) - after
    return bits


# ---------------------------------------------------------------------------------------------
# show


def show(revs: list[dict], trails: project.Trails, sizes: dict) -> list[str]:
    last = revs[-1]
    now, nodes = project.state(last), {n["id"]: n for n in last["nodes"]}
    sealed = ", ".join(last.get("sealed_inputs", [])) or "the same data"
    lines = [
        f"Beliefs over {last['project']}, revision {last['rev']} ({last['at']}, {last['by']}).",
        "Advisory: nothing here changes a ✓ or ✗. P is a probability under the assumptions below.",
        "",
        "Assumptions:",
    ]
    for measure, entry in sorted(sizes.items()):
        lines.append(f"  {measure}: standard error {view.number(entry['se'])}, declared by {entry['by']}: {entry['why']}")
    measured = sorted({c["measure"] for n in last["nodes"] for c in n["criteria"]} - set(sizes))
    lines += [
        f"  Taken as measured without error: {', '.join(measured) or 'none'}.",
        "  A flat prior on each true value; errors independent between criteria and between routes, unless said.",
        "",
        "Resolutions at a noisy criterion (P that the true value meets it; within noise when under 1.645 SE, with",
        "how many times the rows would tell the value from the threshold, were it to stay where it is):",
    ]
    for resolution in last["resolutions"]:
        node = nodes[resolution["node"]]
        probe, step = trails.cite(resolution["cites"], last["project"])
        found = project.measures(step)
        for criterion in noisy(node, sizes):
            if criterion["measure"] not in found:
                continue
            value, se = found[criterion["measure"]], sizes[criterion["measure"]]["se"]
            away = margin(criterion, value, se)
            flag = f", within noise ({rows_needed(away)})" if abs(away) < Z95 else ""
            lines.append(
                f"  {MARKS['reached' if resolution['holds'] else 'refuted']} {node['id']}: {project.criterion_text(criterion)}, "
                f"measured {view.number(value)}: {away:+.2f} SE, P {NORMAL.cdf(away):.2f}{flag} "
                f"({probe.split(':', 1)[1]} {step['id']})"
            )
    lines += ["", f"Goals, and the routes scored on {sealed}:"]
    for goal in last["goals"]:
        mark = "✓" if now["goals"][goal["id"]] else "○"
        scored, credited, below, ends = [], [], [], []
        for route in (r for r in last["routes"] if r["goal"] == goal["id"]):
            end = nodes[route["path"][-1]]
            found = evidence(last, end["id"], trails)
            criteria = noisy(end, sizes)
            if not found or not criteria:
                continue
            resolution, step, _ = found
            values = project.measures(step)
            p = p_true(end, step, sizes)
            bounds = ", ".join(
                f"95% bound {bound(c, values[c['measure']], sizes[c['measure']]['se']):.4f}" for c in criteria if c["measure"] in values
            )
            shown = ", ".join(f"{c['measure']} {view.number(values[c['measure']])}" for c in criteria if c["measure"] in values)
            scored.append(f"      {MARKS['reached' if resolution['holds'] else 'refuted']} {route['id']}: {shown}, P {p:.2f}; {bounds}")
            if len(criteria) == 1 and criteria[0]["measure"] in values:
                ends.append((criteria[0], values[criteria[0]["measure"]], resolution["holds"]))
            if resolution["holds"]:
                credited.append(p)
                below += [
                    c for c in criteria if c["measure"] in values and margin(c, values[c["measure"]], sizes[c["measure"]]["se"]) < Z95
                ]
        if not scored:
            lines.append(f"  {mark} {goal['id']}: no route ends in a scored milestone with a noisy criterion")
            continue
        lines.append(f"  {mark} {goal['id']}: {len(credited)} of {len(scored)} scored routes credited")
        lines += scored
        if credited:
            shared, apart = max(credited), 1 - math.prod(1 - p for p in credited)
            lines.append(f"      P(at least one credited route truly meets it): {shared:.2f} (errors shared) to {apart:.2f} (independent)")
            lines.append(
                "      No credited route's 95% bound clears the threshold."
                if len(below) == len(credited)
                else f"      {len(credited) - len(below)} of {len(credited)} credited routes clear the threshold at their 95% bound."
            )
        same = ("measure", "comparison", "threshold")
        if credited and len(ends) == len(scored) > 1 and all(all(c[k] == ends[0][0][k] for k in same) for c, _, _ in ends):
            criterion, found = ends[0][0], [value for _, value, _ in ends]
            se = sizes[criterion["measure"]]["se"]
            one, partial = pooled(found, se, criterion, [k for k, end in enumerate(ends) if end[2]])
            lines.append(
                f"      Were the routes' true values related, not each free: P {one:.2f} if all {len(found)} share one value, "
                f"P {partial:.2f} if each is drawn about a shared mean."
            )
            apart = stdev(found)
            lines.append(
                f"      The scores differ by a standard deviation of {apart:.4f}, "
                + (
                    f"under the {view.number(se)} error of one score: they do not tell the routes apart."
                    if apart < se
                    else f"over the {view.number(se)} error of one score."
                )
            )
    if last.get("sealed_inputs"):
        opened = {}
        for probe, steps in trails.steps.items():
            count = sum(1 for step in steps if step["kind"] == "run" and trails.read(probe, step, last["sealed_inputs"]))
            if count:
                opened[probe.split(":", 1)[1]] = count
        lines += ["", f"Runs that opened {sealed}: {sum(opened.values())} in {len(opened)} trails. Each is a look at what the marks are scored on."]
        lines += [f"  {', '.join(f'{name} {count}' for name, count in sorted(opened.items()))}"] if opened else []
    lines += ["", "Open milestones, their Markov blanket, and P(reached) from the blanket alone and from the whole map:"]
    rows = project.ranked(last)
    for row in rows:
        near = blanket(last, row["node"])
        lines.append(f"  ○ {row['node']}: next on {', '.join(row['leads'])}")
        for role, label in (("parents", "before it"), ("co_parents", "leading to the same place"), ("children", "after it")):
            said = []
            for other in near[role]:
                if other.startswith("goal:"):
                    said.append(f"{other} {'✓' if now['goals'][other[5:]] else '○'}")
                    continue
                found = evidence(last, other, trails)
                if found:
                    values = project.measures(found[1])
                    shown = ", ".join(
                        f"{c['measure']} {view.number(values[c['measure']])}" for c in noisy(nodes[other], sizes) if c["measure"] in values
                    )
                    said.append(f"{other} {MARKS[project.node_state(other, now)]}" + (f" ({shown})" if shown else ""))
                else:
                    said.append(f"{other} ○")
            lines.append(f"      {label}: {', '.join(said) or 'nothing'}")
        p, how = predictive(last, row["node"], trails, sizes)
        lines.append(f"      P(reached) {p:.2f}: {how}")
        p, how = pooled_predictive(last, row["node"], trails, sizes)
        lines.append(f"      from the whole map, P(reached) {p:.2f}: {how}")
    lines += [
        "",
        "Which open milestone tells most about its goal, in bits (an upper bound: routes taken as independent,",
        "and one run taken to settle the milestone). Beside it, the order project.py next gives, the most shared first:",
    ]
    order = {row["node"]: n for n, row in enumerate(rows, 1)}
    lines.append(
        "  P(some route, credited or not, truly meets the goal), open routes at their P(reached): "
        + ", ".join(f"{g['id']} {goal_p(last, g['id'], trails, sizes):.2f}" for g in last["goals"])
    )
    scored_rows = sorted(
        ((sum(information(last, row["node"], trails, sizes).values()), row["node"]) for row in rows), key=lambda x: (-x[0], x[1])
    )
    for bits, node in scored_rows:
        about = information(last, node, trails, sizes)
        detail = ", ".join(f"{bit:.3f} about {goal}" for goal, bit in about.items())
        lines.append(
            f"  {node}: {bits:.3f} bits ({detail}); P(reached) {node_p(last, node, trails, sizes):.2f}; next gives it {order[node]}"
        )
    if scored_rows and scored_rows[0][0] < 0.05:
        agrees = [node for _, node in scored_rows] == [row["node"] for row in rows]
        lines.append(
            "  Every value is under 0.05 bits: no open milestone tells much about its goal. "
            + ("The order is next's." if agrees else "The order is not next's.")
        )
    return lines


# ---------------------------------------------------------------------------------------------
# What a forecaster is shown


def described(revision: dict, node_id: str, trails: project.Trails, now: dict, nodes: dict) -> tuple[str, str | None]:
    """One milestone as a forecaster reads it, and the unpinned reference of the run it rests on."""
    node = nodes[node_id]
    text = f"{node_id} ({project.node_state(node_id, now)}): {node['statement']} ({', '.join(project.criterion_text(c) for c in node['criteria'])})"
    found = evidence(revision, node_id, trails)
    if not found:
        return text, None
    resolution, step, name = found
    said = ", ".join(f"{key} {view.number(value)}" for key, value in project.measures(step).items())
    return f"{text}; {'reached' if resolution['holds'] else 'refuted'} by {name} {step['id']}, which measured {said}", project.unpinned(
        resolution["cites"]
    )


def milestone_prompt(revision: dict, node_id: str, trails: project.Trails) -> tuple[str, set[str]]:
    """The text a forecaster is shown for a milestone, from one revision alone and only its blanket;
    and the runs that text cites. A revision's reason is free text and is not shown."""
    now, nodes = project.state(revision), {n["id"]: n for n in revision["nodes"]}
    goals = {g["id"]: g for g in revision["goals"]}
    near, cited = blanket(revision, node_id), set()
    node = nodes[node_id]
    lines = [
        ANSWER,
        "",
        (
            "A research project keeps a map: goals, routes to each goal, and milestones along the routes. A milestone is "
            "reached when the run credited to it measures values that meet all its criteria, and refuted when that run "
            "misses one. Below is one revision of the map, cut down to one milestone's Markov blanket: the milestones "
            "before it on its routes, what comes after it, and the other milestones that lead to the same place. "
            "Nothing later than this revision is shown."
        ),
        "",
        f"Project {revision['project']}, revision {revision['rev']}.",
    ]
    if revision.get("instructions"):
        lines.append(f"Rules every route follows: {revision['instructions']}")
    lines += [
        "",
        f"The milestone: {node_id}: {node['statement']}",
        f"  criteria: {', '.join(project.criterion_text(c) for c in node['criteria'])}",
    ]
    for route in (r for r in revision["routes"] if node_id in r["path"]):
        status = "abandoned" if route["status"] == "abandoned" else now["routes"][route["id"]]["status"]
        lines.append(f"  on route {route['id']} ({status}), for goal {route['goal']}: {route['method']}; path {' → '.join(route['path'])}")
    lines += ["", "Its blanket:"]
    for role, label in (("parents", "before it"), ("co_parents", "leading to the same place"), ("children", "after it")):
        for other in near[role]:
            if other.startswith("goal:"):
                goal = goals[other[5:]]
                lines.append(
                    f"  {label}: the goal {goal['id']} ({'reached' if now['goals'][goal['id']] else 'not yet reached'}): {goal['statement']}"
                )
                continue
            text, ref = described(revision, other, trails, now, nodes)
            routes = [r for r in revision["routes"] if other in r["path"]]
            if routes and all(r["status"] == "abandoned" for r in routes):
                text += "; its route was abandoned"
            lines.append(f"  {label}: {text}")
            if ref:
                cited.add(ref)
    lines += ["", f"Question: what is the probability that the first run credited to milestone {node_id} meets every one of its criteria?"]
    return "\n".join(lines) + "\n", cited


def plan_prompt(steps: list[dict], plan_id: str) -> str:
    """The text a forecaster is shown for a plan: the trail up to and including it, and nothing after."""
    by_id = {s["id"]: s for s in steps}
    plan = by_id[plan_id]
    task = steps[0]
    lines = [
        ANSWER,
        "",
        (
            "An AI agent is working on a research task. Every step it took is recorded in a trail: its plans, the "
            "commands it ran and what each run measured. Below is the trail up to and including one plan; nothing "
            "after that plan is shown."
        ),
        "",
        f"Task: {task['summary']}",
    ]
    if task.get("question"):
        lines.append(f"Question of the task: {task['question']}")
    for step in steps[1 : plan["seq"] + 1]:
        kind = step["kind"]
        if kind == "plan":
            hard = [e for e in step.get("expectations", []) if e["comparison"] not in trail.EXIT]
            expects = f" Expects: {', '.join(project.criterion_text(e) for e in hard)}." if hard else ""
            mark = " (the plan in question)" if step["id"] == plan_id else ""
            lines.append(f"{step['id']} plan{mark}: {step['summary']}.{expects}")
        elif kind == "run":
            lines.append(f"{step['id']} run: {view.short(step['command']['shown'], 200)}")
        elif kind == "observation":
            said = ", ".join(f"{key} {view.number(value)}" for key, value in project.measures(step).items())
            lines.append(
                f"{step['id']} observation: {view.OUTCOMES.get(step.get('outcome'), step.get('outcome'))}"
                + (f"; measured {said}" if said else "")
            )
        else:
            lines.append(f"{step['id']} {kind}: {step['summary']}")
    if plan.get("reasoning"):
        lines += ["", f"The agent's reasoning for {plan_id}: {plan['reasoning']}"]
    lines += [
        "",
        f"Question: when {plan_id} is run and its run writes its measures, what is the probability that every expectation of {plan_id} holds?",
    ]
    return "\n".join(lines) + "\n"


def saw(text: str) -> str:
    return trail.digest(text.encode())


# ---------------------------------------------------------------------------------------------
# Questions, outcomes and scores


def known_before(asked: dict, node: str, first: dict, trails: project.Trails) -> list[str]:
    """Why a milestone's outcome was known, or followed from the map, at the revision it is asked at."""
    reasons = []
    _, step = trails.cite(first["cites"], asked["project"])
    if datetime.fromisoformat(step["at"]) < datetime.fromisoformat(asked["at"]):
        reasons.append(f"its run was made before rev-{asked['rev']} was written")
    after = {m for r in asked["routes"] if node in r["path"] for m in r["path"][r["path"].index(node) + 1 :]}
    resolved = sorted(after & {r["node"] for r in asked["resolutions"]})
    if resolved:
        reasons.append(f"{', '.join(resolved)}, after it on a route, already resolved")
    return reasons


def milestone_questions(revs: list[dict], trails: project.Trails) -> tuple[list[dict], list[str]]:
    """A milestone is asked about at the last revision before each time it goes from unresolved to
    resolved, and at the last revision when it is the next milestone of an open route. Its outcome is
    that first resolution. A resolution a later revision withdrew, or one whose run the blanket already
    cites, gives no question; both are counted."""
    asked, excluded = [], []
    last = revs[-1]
    standing = {(r["node"], project.unpinned(r["cites"])) for r in last["resolutions"]}
    for node in (n["id"] for n in last["nodes"]):
        for k in range(1, len(revs)):
            before = [r for r in revs[k - 1]["resolutions"] if r["node"] == node]
            first = next((r for r in revs[k]["resolutions"] if r["node"] == node), None)
            if before or first is None:
                continue
            if node not in {n["id"] for n in revs[k - 1]["nodes"]}:
                excluded.append(f"{node} at rev-{k}: it first appeared with its resolution")
                continue
            text, cited = milestone_prompt(revs[k - 1], node, trails)
            ref = project.unpinned(first["cites"])
            if (node, ref) not in standing:
                excluded.append(f"{node} at rev-{k - 1}: its first resolution, in rev-{k}, was withdrawn later")
            elif ref in cited:
                excluded.append(f"{node} at rev-{k - 1}: its blanket already cites the run that settles it, {ref}")
            else:
                asked.append(
                    {
                        "kind": "milestone",
                        "node": node,
                        "rev": k - 1,
                        "saw": saw(text),
                        "settled_by": ref,
                        "holds": first["holds"],
                        "settled_at": revs[k]["at"],
                        "known": known_before(revs[k - 1], node, first, trails),
                        "_text": text,
                    }
                )
    for row in project.ranked(last):
        text, _ = milestone_prompt(last, row["node"], trails)
        asked.append({"kind": "milestone", "node": row["node"], "rev": last["rev"], "saw": saw(text), "_text": text})
    return asked, excluded


def open_questions(revision: dict, trails: project.Trails) -> list[dict]:
    """Every milestone on an open route that is not yet resolved, asked at this revision. A forecast
    of one is settled by its first resolution in a later revision (rebuild_open)."""
    now = project.state(revision)
    open_routes = [r for r in revision["routes"] if now["routes"][r["id"]]["status"] == "open"]
    nodes = sorted({n for r in open_routes for n in r["path"] if project.node_state(n, now) == "open"})
    asked = []
    for node in nodes:
        text, _ = milestone_prompt(revision, node, trails)
        asked.append({"kind": "milestone", "node": node, "rev": revision["rev"], "saw": saw(text), "_text": text})
    return asked


CHOICE = re.compile(r"^\s*\**routes\**\s*[:=]\s*\**\s*(.+?)\s*\**\s*$", re.IGNORECASE | re.MULTILINE)
CHOOSE = 3


def as_of(trails: project.Trails, at: str) -> project.Trails:
    """The trails as they stood at a moment: only the steps made by then, and only trails that had one.
    A text built from them stays the same however the trails grow afterwards."""
    moment = datetime.fromisoformat(at)
    kept = copy.copy(trails)
    kept.steps = {}
    for probe, steps in trails.steps.items():
        if early := [s for s in steps if datetime.fromisoformat(s["at"]) <= moment]:
            kept.steps[probe] = early
    kept.heads = {probe: trail.heads(steps) for probe, steps in kept.steps.items()}
    return kept


def nominate_prompt(revs: list[dict], trails: project.Trails, sizes: dict) -> str:
    """The text an overseer is shown to choose the routes the next agents run: the map as
    project.py view prints it, the belief report, and the open routes. Only steps made before the
    revision count, so the text can be rebuilt later and checked against its digest."""
    last = revs[-1]
    trails = as_of(trails, last["at"])
    now = project.state(last)
    routes = [r for r in last["routes"] if now["routes"][r["id"]]["status"] == "open"]
    lines = [
        (
            f"You oversee the beliefs of a research project. Up to {CHOOSE} AI agents will now run at once, one on each "
            "route you choose, for about 40 minutes. Choose the routes whose results would most improve what the project "
            "knows. Answer with exactly two lines and nothing else:"
        ),
        f"routes: <up to {CHOOSE} route ids from the list below, separated by commas>",
        "why: <one or two sentences>",
        "",
        "The open routes:",
        *(f"  {r['id']}: {r['method']}; next milestone {now['routes'][r['id']]['next']}" for r in routes),
        "",
        "The map, as the project's viewer prints it:",
        *project.show(last, trails, revs),
        "",
        "What code computes from the map (advisory):",
        *show(revs, trails, sizes),
    ]
    return "\n".join(lines) + "\n"


def parse_choice(text: str) -> tuple[list[str] | None, str]:
    found = CHOICE.findall(text)
    why = WHY.findall(text)
    if not found:
        return None, why[-1] if why else ""
    return [r.strip().strip("`*") for r in found[-1].split(",") if r.strip()], (why[-1] if why else "")


def choose(revs: list[dict], trails: project.Trails, sizes: dict, answer: str, by: str, at: str) -> dict:
    """The overseer's choice, checked: one to CHOOSE distinct open routes, read from the asked form only.
    Recorded beside the order project.py next gives and the information ranking, which it may differ from."""
    last = revs[-1]
    now = project.state(last)
    open_routes = [r["id"] for r in last["routes"] if now["routes"][r["id"]]["status"] == "open"]
    routes, why = parse_choice(answer)
    if not routes:
        raise Usage("the answer has no line of the form routes: a, b, c")
    if len(set(routes)) != len(routes) or not 1 <= len(routes) <= CHOOSE:
        raise Usage(f"the answer chooses {len(routes)} routes, or one twice; it may choose 1 to {CHOOSE}")
    if unknown := [r for r in routes if r not in open_routes]:
        raise Usage(f"the answer chooses {', '.join(unknown)}, which is not an open route of rev-{last['rev']}")
    bits = {
        row["node"]: round(sum(information(last, row["node"], trails, sizes).values()), 4) for row in project.ranked(last)
    }
    return {
        "version": VERSION,
        "project": last["project"],
        "rev": last["rev"],
        "by": by,
        "at": at,
        "saw": saw(nominate_prompt(revs, trails, sizes)),
        "routes": routes,
        "why": why,
        "next": [{"node": row["node"], "leads": row["leads"]} for row in project.ranked(last)],
        "information": bits,
    }


def plan_questions(trails: project.Trails, sealed: list[str] = ()) -> tuple[list[dict], list[str]]:
    """A plan with an expectation on a measure is asked about when its first observation settled it:
    as expected or contradicted. A plan never run, or whose first run failed or measured too little, is counted.
    A question records the earlier runs of its trail known to have opened a sealed input: what such a run
    printed is in the text the forecaster is shown, so the question may not be a forecast at all."""
    asked, excluded = [], []
    for probe, steps in trails.steps.items():
        name = probe.split(":", 1)[1]
        for plan in (s for s in steps if s["kind"] == "plan"):
            if not any(e["comparison"] not in trail.EXIT for e in plan.get("expectations", [])):
                continue
            tested = [s for s in steps if s["kind"] == "observation" and plan["id"] in view.linked(s, "tests")]
            if not tested:
                excluded.append(f"{name} {plan['id']}: never run")
            elif tested[0]["outcome"] not in ("as_expected", "contradicted"):
                excluded.append(f"{name} {plan['id']}: its first run {view.OUTCOMES[tested[0]['outcome']]}")
            else:
                text = plan_prompt(steps, plan["id"])
                opened = [s["id"] for s in steps[: plan["seq"]] if s["kind"] == "run" and sealed and trails.read(probe, s, sealed)]
                asked.append(
                    {
                        "kind": "plan",
                        "trail": name,
                        "step": plan["id"],
                        "saw": saw(text),
                        "settled_by": f"probe:{name}#{tested[0]['id']}",
                        "holds": tested[0]["outcome"] == "as_expected",
                        "settled_at": tested[0]["at"],
                        "asked_at": plan["at"],
                        "after_sealed": opened,
                        "_text": text,
                    }
                )
    return asked, excluded


def key(question: dict) -> tuple:
    return (question["kind"], question.get("node"), question.get("rev"), question.get("trail"), question.get("step"))


def label(question: dict) -> str:
    return f"{question['node']} at rev-{question['rev']}" if question["kind"] == "milestone" else f"{question['trail']} {question['step']}"


def baselines(question: dict, revs: list[dict], trails: project.Trails, plans: list[dict], sizes: dict) -> dict[str, float]:
    """Code-only forecasts from what was known when the question was asked."""
    if question["kind"] == "milestone":
        pinned = revs[question["rev"]]
        return {
            "code:even": 0.5,
            "code:base-rate": base_rate(pinned),
            "code:blanket": predictive(pinned, question["node"], trails, sizes)[0],
            "code:pooled": pooled_predictive(pinned, question["node"], trails, sizes)[0],
        }
    known = [q for q in plans if q["settled_at"] < question["asked_at"]]
    return {"code:even": 0.5, "code:base-rate": laplace(sum(q["holds"] for q in known), len(known))}


MARKED = {
    "milestone": ("‡", "the outcome was known, or followed from the map, when the question's revision was written, so these are not forecasts."),
    "plan": ("†", "an earlier run of the trail is known to have opened a sealed input, so what it printed may be in the text shown."),
}


def marked(question: dict) -> str:
    """Why a settled question is not a clean forecast; empty when nothing is known against it."""
    if question["kind"] == "milestone":
        return "; ".join(question.get("known", []))
    return f"after {', '.join(question['after_sealed'])}" if question.get("after_sealed") else ""


def against(mine: list[float], theirs: list[float]) -> str:
    """The mean difference of two forecasters' Brier scores on the same questions, with its standard error."""
    apart = [a - b for a, b in zip(mine, theirs, strict=True)]
    if len(apart) < 2:
        return ""
    error = stdev(apart) / math.sqrt(len(apart))
    shown = round(mean(apart), 3) + 0.0  # so a difference of nothing is +0.000, never -0.000
    return f"; the forecaster is {shown:+.3f} ± {error:.3f} from it" + (", within noise" if abs(mean(apart)) < Z95 * error else "")


def brier(p: float, hit: bool) -> float:
    return (p - hit) ** 2


def log_loss(p: float, hit: bool) -> float:
    p = min(max(p, CLIP[0]), CLIP[1])
    return -math.log2(p if hit else 1 - p)


def score(revs: list[dict], trails: project.Trails, sizes: dict, files: list[Path]) -> tuple[list[str], list[str]]:
    milestones, left_m = milestone_questions(revs, trails)
    sealed = revs[-1].get("sealed_inputs", [])
    plans, left_p = plan_questions(trails, sealed)
    known = {key(q): q for q in milestones + plans}
    lines, errors = [f"Forecasts over {revs[-1]['project']}, scored against revision {revs[-1]['rev']} and the trails."], []
    lines += [
        "Brier score and log loss in bits: lower is better. Probabilities are clipped to 0.01-0.99 for the log loss.",
        "Each forecaster is compared with code-only forecasters on the same questions: code:even, 0.5 every time;",
        "code:base-rate, the Laplace rate of what was settled before the question was asked; code:blanket, the",
        "milestone's Markov blanket alone; code:pooled, every milestone measured on the same criterion, anywhere on",
        "the map. A difference in Brier score is given with its standard error, and is within noise under 1.645 of them.",
        "",
        f"Not asked: {len(left_m)} milestone and {len(left_p)} plan questions.",
        *(f"  {line}" for line in left_m),
    ]
    reasons = {}
    for line in left_p:
        reasons[line.split(": ", 1)[1]] = reasons.get(line.split(": ", 1)[1], 0) + 1
    lines += [f"  plans: {count} {reason}" for reason, count in sorted(reasons.items())]
    for path in files:
        kept = json.loads(path.read_text())
        lines += ["", f"{path.name}: by {kept['by']} at {kept['at']}"]
        rows, pending, unanswered = [], [], 0
        for forecast in kept["forecasts"]:
            question = known.get(key(forecast))
            if question is None and forecast["kind"] == "milestone":
                question = rebuild_open(forecast, revs, trails)
            if question is None:
                errors.append(f"{path.name}: {label(forecast)} is not a question of this map")
                continue
            if forecast["saw"] != question["saw"]:
                errors.append(f"{path.name}: {label(forecast)} saw text the map and trails do not give now")
                continue
            if forecast["p"] is None:
                unanswered += 1
                continue
            if "holds" not in question:
                base = baselines(question, revs, trails, plans, sizes)
                pending.append(
                    f"  pending {label(forecast)}: p {forecast['p']:.2f}; code:blanket {base['code:blanket']:.2f}, "
                    f"code:pooled {base['code:pooled']:.2f}"
                )
                continue
            backtest = "backtest" if kept["at"] > question["settled_at"] else "forecast"
            rows.append((question, forecast["p"], baselines(question, revs, trails, plans, sizes), backtest))
        if unanswered:
            lines.append(f"  {unanswered} questions unanswered: no probability could be read, so they are not scored")
        for kind in ("milestone", "plan"):
            mine = [row for row in rows if row[0]["kind"] == kind]
            if not mine:
                continue
            kinds = sorted({row[3] for row in mine})
            lines.append(f"  {kind} questions settled: {len(mine)} ({', '.join(kinds)}); held {sum(r[0]['holds'] for r in mine)}")
            whos = [kept["by"], *mine[0][2]]

            def scores(who: str, chosen: list, by: str = kept["by"]) -> list[float]:
                return [brier(row[1] if who == by else row[2][who], row[0]["holds"]) for row in chosen]

            for who in whos:
                ps = [(row[1] if who == kept["by"] else row[2][who], row[0]["holds"]) for row in mine]
                apart = "" if who == kept["by"] else against(scores(kept["by"], mine), scores(who, mine))
                lines.append(
                    f"    {who}: Brier {mean(brier(p, h) for p, h in ps):.3f}, "
                    f"log loss {mean(log_loss(p, h) for p, h in ps):.3f} bits, n {len(ps)}{apart}"
                )
            symbol, meaning = MARKED[kind]
            for question, p, base, _ in mine:
                others = ", ".join(f"{who.split(':')[1]} {value:.2f}" for who, value in base.items() if who != "code:even")
                why = f" {symbol} {marked(question)}" if marked(question) else ""
                lines.append(f"      {'held' if question['holds'] else 'missed'}  {label(question)}: p {p:.2f}; {others}{why}")
            subsets = []
            flagged = [row for row in mine if marked(row[0])]
            if flagged:
                lines.append(f"    {symbol} {len(flagged)} of {len(mine)}: {meaning}")
                subsets.append(("on the other", [row for row in mine if not marked(row[0])]))
            if len(kinds) > 1:
                subsets.append(("made before the outcome,", [row for row in mine if row[3] == "forecast"]))
            for name, chosen in subsets:
                if chosen:
                    said = "; ".join(f"{who} Brier {mean(scores(who, chosen)):.3f}" for who in whos)
                    lines.append(f"      {name} {len(chosen)}: {said}")
        lines += pending
    return lines, errors


def settled(revs: list[dict], trails: project.Trails, sizes: dict, path: Path) -> tuple[str, list[tuple[dict, float, dict]]]:
    """A forecast file's settled milestone forecasts that score() accepts: each question, the
    forecast and the code forecasters' values on it."""
    milestones, _ = milestone_questions(revs, trails)
    known = {key(q): q for q in milestones}
    kept, rows = json.loads(path.read_text()), []
    for forecast in kept["forecasts"]:
        if forecast["kind"] != "milestone" or forecast["p"] is None:
            continue
        question = known.get(key(forecast)) or rebuild_open(forecast, revs, trails)
        if question is None or question["saw"] != forecast["saw"] or "holds" not in question:
            continue
        rows.append((question, forecast["p"], baselines(question, revs, trails, [], sizes)))
    return kept["by"], rows


def true_margins(revision: dict, truth: dict, sizes: dict) -> dict[str, float]:
    """Each milestone's true margin in standard errors, from the replicated value of its route's
    held-out criterion: a -holdout milestone's own, and the -cv milestone before it on its route."""
    margins = {}
    for row in truth["rows"]:
        for criterion in row.get("criteria", []):
            if criterion["measure"] in sizes:
                at = margin(criterion, criterion["value"], sizes[criterion["measure"]]["se"])
                margins[row["node"]] = at
                for route in revision["routes"]:
                    if row["node"] in route["path"] and route["path"].index(row["node"]):
                        margins.setdefault(route["path"][route["path"].index(row["node"]) - 1], at)
    return margins


def truth_lines(revs: list[dict], trails: project.Trails, sizes: dict, files: list[Path], truth: dict) -> list[str]:
    """The three predictions of spec 12, scored against the replication sample."""
    last = revs[-1]
    margins = true_margins(last, truth, sizes)
    lines = [
        "",
        f"Against the replication sample ({truth['data']['rows']:,} rows, {truth['data']['digest'][:19]}…), each cited run re-run on it:",
    ]
    for row in truth["rows"]:
        if "criteria" not in row:
            lines.append(f"  {row['node']} ({row['run']}): not replicated: {row.get('problem', 'no measure')}")
            continue
        said = ", ".join(f"{c['measure']} {view.number(c['value'])} {'meets' if c['holds'] else 'misses'} {view.number(c['threshold'])}" for c in row["criteria"])
        lines.append(f"  {MARKS['reached' if row['holds'] else 'refuted']} {row['node']} ({row['run']}): recorded "
                     + ", ".join(f"{c['measure']} {view.number(row['recorded'][c['measure']])}" for c in row["criteria"])
                     + f"; replicated {said}; true margin {margins.get(row['node'], math.nan):+.2f} SE")
    # P2: the calibration of p_true against the replicated outcomes.
    nodes = {n["id"]: n for n in last["nodes"]}
    pairs = []
    for row in truth["rows"]:
        if row.get("criteria"):
            _, step = trails.cite(row["cites"], last["project"])
            pairs.append((p_true(nodes[row["node"]], step, sizes), all(c["holds"] for c in row["criteria"])))
    lines.append("")
    if pairs:
        ours = [brier(p, hit) for p, hit in pairs]
        lines.append(
            f"P2, calibration: P(true value meets it) from each held-out score, against the replicated outcome: "
            f"Brier {mean(ours):.3f} against the coin flip's 0.250, n {len(pairs)}"
            + against(ours, [0.25] * len(ours)).replace("the forecaster is", "it is")
        )
    else:
        lines.append("P2, calibration: no replicated resolution")
    for path in files:
        by, rows = settled(revs, trails, sizes, path)
        if not rows:
            continue
        lines += ["", f"{path.name}: by {by}"]
        whos = [by, *rows[0][2]]

        def scores(who: str, chosen: list, by: str = by) -> list[float]:
            return [brier(row[1] if who == by else row[2][who], row[0]["holds"]) for row in chosen]

        for name, chosen in (
            ("P1, true margin at least 1.645 SE", [r for r in rows if abs(margins.get(r[0]["node"], 0)) >= Z95]),
            ("P1, true margin under 1.645 SE", [r for r in rows if r[0]["node"] in margins and abs(margins[r[0]["node"]]) < Z95]),
        ):
            lines.append(f"  {name}: n {len(chosen)}")
            for who in whos:
                if chosen:
                    lines.append(f"    {who}: Brier {mean(scores(who, chosen)):.3f}" + ("" if who == "code:even" else against(scores(who, chosen), [0.25] * len(chosen)).replace("the forecaster is", "it is").replace(" from it", " from the coin flip")))
        after = [
            r for r in rows
            if r[0]["node"].endswith("-holdout")
            and any(x["node"] == r[0]["node"].removesuffix("-holdout") + "-cv" for x in revs[r[0]["rev"]]["resolutions"])
        ]
        lines.append(f"  P3, -holdout milestones asked after their -cv milestone was resolved: n {len(after)}")
        if after:
            lines.append(f"    {by}: Brier {mean(scores(by, after)):.3f}; code:blanket Brier {mean(scores('code:blanket', after)):.3f}"
                         + against(scores(by, after), scores("code:blanket", after)).replace(" from it", " from code:blanket"))
    return lines


def rebuild_open(forecast: dict, revs: list[dict], trails: project.Trails) -> dict | None:
    """A milestone question asked at a revision that has since been followed by others: valid while the
    milestone stood unresolved at that revision; settled by its first resolution after it."""
    rev = forecast.get("rev")
    if not isinstance(rev, int) or not 0 <= rev < len(revs) or forecast["node"] not in {n["id"] for n in revs[rev]["nodes"]}:
        return None
    if any(r["node"] == forecast["node"] for r in revs[rev]["resolutions"]):
        return None
    text, cited = milestone_prompt(revs[rev], forecast["node"], trails)
    question = {"kind": "milestone", "node": forecast["node"], "rev": rev, "saw": saw(text)}
    for later in revs[rev + 1 :]:
        first = next((r for r in later["resolutions"] if r["node"] == forecast["node"]), None)
        if first:
            if project.unpinned(first["cites"]) in cited:
                return None
            question |= {
                "holds": first["holds"],
                "settled_at": later["at"],
                "settled_by": project.unpinned(first["cites"]),
                "known": known_before(revs[rev], forecast["node"], first, trails),
            }
            break
    return question


def parse_answer(text: str) -> tuple[float | None, str]:
    found = PROBABILITY.findall(text)
    why = WHY.findall(text)
    p = float(found[-1]) if found else None
    return (p if p is not None and 0 <= p <= 1 else None), (why[-1] if why else "")


# ---------------------------------------------------------------------------------------------
# Command line


OPTIONS = ("--live", "--rev", "--out", "--by", "--at", "--auc", "--pos", "--neg", "--truth")
FLAGS = ("--all-open",)


def parse(argv: list[str]) -> tuple[list[str], dict[str, str]]:
    args, named, rest = [], {}, list(argv)
    while rest:
        word = rest.pop(0)
        if word in FLAGS:
            named[word[2:]] = "yes"
        elif word in OPTIONS:
            if not rest:
                raise Usage(f"beliefs.py: {word} needs a value")
            named[word[2:]] = rest.pop(0)
        elif word.startswith("--"):
            raise Usage(f"beliefs.py: unknown option {word}")
        else:
            args.append(word)
    return args, named


def load(directory: Path, live: str | None) -> tuple[list[dict], project.Trails]:
    revs = project.revisions(directory)
    if not revs:
        raise Usage(f"{directory} holds no revisions")
    paths = project.discover(Path(live), revs[-1]["project"]) if live else []
    trails = project.Trails(paths, (), directory.parent)
    errors = project.check(revs, trails)
    if errors:
        raise Usage("the map does not check:\n" + "\n".join(errors))
    return revs, trails


def main(argv: list[str]) -> int:
    try:
        args, named = parse(argv[1:])
        if not args:
            raise Usage("usage: beliefs.py COMMAND MAP --live DIR [options]; see the docstring")
        command = args[0]
        if command == "se":
            if not {"auc", "pos", "neg"} <= set(named):
                raise Usage("usage: beliefs.py se --auc A --pos N --neg M")
            print(f"{se_auc(float(named['auc']), int(named['pos']), int(named['neg'])):.4f}")
            return 0
        if command == "before":
            if len(args) != 3:
                raise Usage("usage: beliefs.py before TRAIL STEP")
            steps = trail.load(Path(args[1]))
            if args[2] not in {s["id"] for s in steps if s["kind"] == "plan"}:
                raise Usage(f"{args[2]} is not a plan of {args[1]}")
            print(plan_prompt(steps, args[2]), end="")
            return 0
        if command == "collect":
            if len(args) != 2 or "by" not in named or "out" not in named:
                raise Usage("usage: beliefs.py collect DIR --by ACTOR --out FILE")
            if not project.ACTOR.fullmatch(named["by"]):
                raise Usage(f"{named['by']} is not an actor: human:NAME or agent:NAME")
            asked = json.loads((Path(args[1]) / "questions.json").read_text())
            forecasts = []
            for question in asked["questions"]:
                answer = Path(args[1]) / "answers" / f"{question['id']}.txt"
                p, why = parse_answer(answer.read_text()) if answer.exists() else (None, "")
                forecasts.append({k: v for k, v in question.items() if k not in ("id", "file")} | {"p": p, "why": why})
            at = named.get("at") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            kept = {"version": VERSION, "project": asked["project"], "by": named["by"], "at": at, "forecasts": forecasts}
            Path(named["out"]).write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")
            print(f"wrote {named['out']}: {sum(f['p'] is not None for f in forecasts)} of {len(forecasts)} answered")
            return 0
        if len(args) < 2:
            raise Usage("usage: beliefs.py COMMAND MAP --live DIR [options]")
        directory = Path(args[1])
        revs, trails = load(directory, named.get("live"))
        sizes = noise(directory)
        if command == "show":
            print("\n".join(show(revs, trails, sizes)))
        elif command == "blanket":
            if len(args) != 3:
                raise Usage("usage: beliefs.py blanket MAP NODE [--rev N] --live DIR")
            rev = int(named.get("rev", len(revs) - 1))
            if not 0 <= rev < len(revs) or args[2] not in {n["id"] for n in revs[rev]["nodes"]}:
                raise Usage(f"{args[2]} is not a milestone of rev-{rev}")
            print(milestone_prompt(revs[rev], args[2], trails)[0], end="")
        elif command == "questions":
            if "out" not in named:
                raise Usage("usage: beliefs.py questions MAP --live DIR --out DIR")
            out = Path(named["out"])
            out.mkdir(parents=True, exist_ok=True)
            if "all-open" in named:
                milestones, plans = open_questions(revs[-1], trails), []
            else:
                milestones, _ = milestone_questions(revs, trails)
                plans, _ = plan_questions(trails)
            listed = []
            for n, question in enumerate(milestones + plans, 1):
                name = f"q{n:02d}"
                (out / f"{name}.md").write_text(question["_text"])
                listed.append(
                    {"id": name, "file": f"{name}.md"}
                    | {k: question[k] for k in ("kind", "node", "rev", "trail", "step", "saw") if k in question}
                )
            (out / "questions.json").write_text(json.dumps({"project": revs[-1]["project"], "questions": listed}, indent=2) + "\n")
            print(f"wrote {len(listed)} questions to {out}: {len(milestones)} milestones, {len(plans)} plans")
        elif command == "nominate":
            if "out" not in named:
                raise Usage("usage: beliefs.py nominate MAP --live DIR --out DIR")
            out = Path(named["out"])
            out.mkdir(parents=True, exist_ok=True)
            text = nominate_prompt(revs, trails, sizes)
            (out / "q01.md").write_text(text)
            asked = {"project": revs[-1]["project"], "questions": [{"id": "q01", "file": "q01.md", "kind": "nominate", "rev": revs[-1]["rev"], "saw": saw(text)}]}
            (out / "questions.json").write_text(json.dumps(asked, indent=2) + "\n")
            print(f"wrote the nomination to {out}: {len(text.splitlines())} lines")
        elif command == "choose":
            if len(args) != 3 or "by" not in named or "out" not in named:
                raise Usage("usage: beliefs.py choose MAP DIR --live DIR --by ACTOR --out FILE")
            if not project.ACTOR.fullmatch(named["by"]):
                raise Usage(f"{named['by']} is not an actor: human:NAME or agent:NAME")
            asked = json.loads((Path(args[2]) / "questions.json").read_text())["questions"][0]
            if asked["saw"] != saw(nominate_prompt(revs, trails, sizes)):
                raise Usage("the nomination was asked of text the map and trails do not give now")
            answer = (Path(args[2]) / "answers" / "q01.txt").read_text()
            at = named.get("at") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            chosen = choose(revs, trails, sizes, answer, named["by"], at)
            Path(named["out"]).write_text(json.dumps(chosen, indent=2, ensure_ascii=False) + "\n")
            print(f"wrote {named['out']}: {', '.join(chosen['routes'])}")
        elif command == "score":
            files = sorted((directory.parent / "forecasts").glob("*.json"))
            lines, errors = score(revs, trails, sizes, files)
            if errors:
                print("\n".join(errors))
                return 1
            if "truth" in named:
                lines += truth_lines(revs, trails, sizes, files, json.loads(Path(named["truth"]).read_text()))
            print("\n".join(lines))
        else:
            raise Usage(f"beliefs.py: unknown command {command}")
        return 0
    except Usage as usage:
        print(usage.args[0], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

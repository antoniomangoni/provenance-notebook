"""The research map: goals, routes to them and the milestones routes share, over many trails.

Usage: project.py COMMAND MAP --trails TRAIL... [options]

MAP is a directory of revisions, rev-0.json, rev-1.json and so on, each a whole snapshot written
once and chained to the one before by `prev`. The last is the map. A milestone is reached only
when a resolution cites an observation whose measures meet its criteria: `check` recomputes
every one from the trails, so the map claims nothing the trails do not show.

  check                      the chain, the ids and every resolution against the trails
  propose [--out FILE]       a draft of the next revision, from what the trails reached
  seal DRAFT --by ACTOR      appends the draft as the next revision
  next                       the open routes' next milestones, the most shared first
  brief ROUTE --out DIR [--demo DIR] [--with ROUTE,...]   a demo directory for scripts/live.sh, starting
                             where the map stands; --with names the routes run alongside it
  shared                     milestones, files, code and computation that trails have in common
  graph --out DIR [--csv]    the merged trails' tables with the map's nodes and edges added
  view                       the map as text
  status [--for TRAIL] [--json]   the live state: the map, provisional resolutions and every trail
  page --out FILE            the map and its trails drawn as one static page
  serve [--port N]           the same page, redrawn as trails grow (127.0.0.1 only)

--live DIR adds every trail under DIR whose task names the map's project. --reads FILE... adds
re-executions by retrace.py; without it, those in retrace/ beside MAP are used for the trails given. With --for TRAIL, a sibling's observation whose run opened a sealed
input is shown without its numbers: what an agent's project_map tool is shown.

docs/specs/05-research-map.md is the specification.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import trail
import view

VERSION = 1
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MEASURE = re.compile(r"[A-Za-z0-9_.-]{1,100}")
ACTOR = re.compile(r"(?:human|agent):[A-Za-z0-9._/@-]{1,100}")
AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
REVISION = re.compile(r"rev-(?:0|[1-9][0-9]*)\.json")
ROUTE_TAG = re.compile(r"Route ([a-z0-9]+(?:-[a-z0-9]+)*): ")
FIELDS = {"version", "project", "rev", "prev", "at", "by", "reason", "triggered_by", "goals", "nodes", "routes", "resolutions"}
# Optional: text every brief carries, and files only the run a resolution cites may read.
OPTIONAL = {"instructions", "sealed_inputs"}
SEALED = ("rev", "prev", "at", "by")
MARKS = {"reached": "✓", "refuted": "✗", "open": "○"}


class Usage(Exception):
    """The command line was wrong; nothing was read."""


# ---------------------------------------------------------------------------------------------
# Reading


def revisions(directory: Path) -> list[dict]:
    files = sorted((path for path in directory.glob("rev-*.json") if REVISION.fullmatch(path.name)), key=lambda path: int(path.stem[4:]))
    return [json.loads(path.read_text()) | {"_file": path.name} for path in files]


def sealed(revision: dict) -> dict:
    return {key: value for key, value in revision.items() if not key.startswith("_")}


def digest(revision: dict) -> str:
    return trail.digest(trail.canonical(sealed(revision)))


def readable(directory: Path) -> tuple[list[dict], bool]:
    """A trail's steps up to the first file that does not parse, and whether one did not. Capture writes
    steps in order, so a trail being written can end in a half-written file, and only there."""
    files = sorted((directory / "steps").glob("step-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    steps = []
    for path in files:
        try:
            steps.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return steps, True
    return steps, False


def discover(directory: Path, project: str) -> list[Path]:
    """The trails under DIR whose task names the project."""
    found = []
    for path in sorted(directory.iterdir()) if directory.is_dir() else []:
        try:
            task = json.loads((path / "steps" / "step-0.json").read_text())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if task.get("project") == project:
            found.append(path)
    return found


class Trails:
    """The trails a map cites, by probe id, with the head after each step and where they live."""

    def __init__(self, paths: list[Path], retraced: list[Path] = (), beside: Path | None = None):
        self.steps, self.heads, self.paths, self.reading = {}, {}, {}, set()
        for path in paths:
            steps, partial = readable(path)
            if not steps:
                continue
            probe = trail.probe_id(steps)
            self.steps[probe], self.heads[probe], self.paths[probe] = steps, trail.heads(steps), path
            if partial:
                self.reading.add(probe)
        # Re-executions by retrace.py, by probe and run: what each run read when it was run again.
        self.retraced, self.problems = {}, []
        for path in retraced:
            kept = json.loads(Path(path).read_text())
            if kept.get("trail") not in self.steps:
                self.problems.append(f"{path}: re-executes {kept.get('trail')}, which is not among the trails given")
            elif kept.get("head") not in self.heads[kept["trail"]]:
                self.problems.append(f"{path}: re-executes {kept['trail']} at a head it never had")
            else:
                self.retraced[kept["trail"]] = {run["run"]: run for run in kept["runs"]}
        # A map's own re-executions, kept beside it in retrace/: used for the trails given, without asking.
        for path in sorted((beside / "retrace").glob("*.json")) if beside and not retraced else []:
            kept = json.loads(path.read_text())
            if kept.get("trail") in self.steps and kept.get("head") in self.heads[kept["trail"]]:
                self.retraced[kept["trail"]] = {run["run"]: run for run in kept["runs"]}

    def read(self, probe: str, run: dict, paths: list[str]) -> str | None:
        """How the trail knows the run opened one of these paths: "read" when its observation was traced,
        "read on re-execution" when only retrace.py saw it, "names" when only its command line does, and
        None when none of them shows it. A traced observation that did not open one settles it: None."""
        refs = {f"file:{path}" for path in paths}
        observation = next((s for s in self.steps[probe] if s["kind"] == "observation" and trail.observed(s) == run["id"]), None)
        if observation is not None and "reads" in observation:
            return "read" if refs & {r["ref"] for r in observation["reads"]} else None
        again = self.retraced.get(probe, {}).get(run["id"])
        if again is not None and again.get("reads") is not None:
            return "read on re-execution" if refs & {r["ref"] for r in again["reads"]} else None
        return "names" if any(path in run["command"]["shown"] for path in paths) else None

    def cite(self, ref: str, project: str) -> tuple[str, dict] | str:
        """The probe and the step a pinned reference names, or what is wrong with it."""
        cites = trail.PROBE_REF.fullmatch(ref)
        if not cites or not cites["step"]:
            return f"{ref} is not a probe reference pinned at a head with a step"
        probe = f"{cites['project'] or project}/probe:{cites['trail']}"
        if probe not in self.steps:
            return f"{ref} cites {probe}, which is not among the trails given"
        if cites["head"] not in self.heads[probe]:
            return f"{ref} cites a head {probe} never had, so it changed after it was cited"
        seq = int(cites["step"].split("-")[1])
        if seq > self.heads[probe][cites["head"]]:
            return f"{ref} cites {cites['step']}, which {probe} had not written at that head"
        return probe, self.steps[probe][seq]

    def pin(self, probe: str, step: dict, project: str) -> str:
        """A reference to the step at the trail's present head, as a map cites it."""
        head = trail.digest(trail.canonical(self.steps[probe][-1]))
        name = probe if not probe.startswith(f"{project}/") else probe.split("/", 1)[1]
        return f"{name}@{head}#{step['id']}"


def measures(step: dict) -> dict[str, float]:
    return {m["name"]: m["value"] for m in step.get("measures", [])}


def meets(node: dict, observation: dict) -> bool | None:
    """Whether the observation meets every criterion of the node; None when it lacks a measure one needs."""
    found = measures(observation)
    results = [trail.holds(criterion, found.get(criterion["measure"]), observation["exit_code"]) for criterion in node["criteria"]]
    return None if None in results else all(results)


def criterion_text(criterion: dict) -> str:
    return f"{criterion['measure']} {trail.COMPARISONS[criterion['comparison']]} {view.number(criterion['threshold'])}"


# ---------------------------------------------------------------------------------------------
# Checking


def check_revision(revision: dict, trails: Trails) -> list[str]:
    where = f"rev-{revision.get('rev')}"
    errors = [f"{where}: unknown field {name}" for name in sorted(set(sealed(revision)) - FIELDS - OPTIONAL)]
    required = FIELDS - ({"prev"} if revision.get("rev") == 0 else set())
    errors += [f"{where}: needs {name}" for name in sorted(required - set(revision))]
    if errors:
        return errors
    if revision["rev"] == 0 and "prev" in revision:
        errors.append(f"{where}: the first revision has no prev")
    if revision["version"] != VERSION:
        errors.append(f"{where}: version must be {VERSION}")
    if not isinstance(revision["project"], str) or not re.fullmatch(trail.NAME, revision["project"]):
        errors.append(f"{where}: project must be a project name")
    if not isinstance(revision["at"], str) or not AT.fullmatch(revision["at"]):
        errors.append(f"{where}: at must be a UTC time such as 2026-11-16T12:00:00Z")
    if not isinstance(revision["by"], str) or not ACTOR.fullmatch(revision["by"]):
        errors.append(f"{where}: by must be human:NAME or agent:NAME")
    if "instructions" in revision and (not isinstance(revision["instructions"], str) or not 0 < len(revision["instructions"]) <= 4000):
        errors.append(f"{where}: instructions must be text of at most 4,000 characters")
    if "sealed_inputs" in revision and (
        not isinstance(revision["sealed_inputs"], list) or not all(isinstance(path, str) and path for path in revision["sealed_inputs"])
    ):
        errors.append(f"{where}: sealed_inputs must be a list of paths")
    if not isinstance(revision["reason"], str) or not 0 < len(revision["reason"]) <= 4000:
        errors.append(f"{where}: reason must be text of at most 4,000 characters")
    project = revision["project"]

    for ref in revision["triggered_by"]:
        if isinstance(found := trails.cite(ref, project), str):
            errors.append(f"{where}: triggered_by {found}")

    def ids(kind: str) -> list[str]:
        found = []
        for item in revision[kind]:
            if not isinstance(item.get("id"), str) or not SLUG.fullmatch(item["id"]):
                errors.append(f"{where}: {kind} need ids of lower-case letters, digits and single hyphens")
            elif item["id"] in found:
                errors.append(f"{where}: {kind} id {item['id']} is used twice")
            else:
                found.append(item["id"])
        return found

    goals, nodes = ids("goals"), ids("nodes")
    ids("routes")
    for goal in revision["goals"]:
        if not isinstance(goal.get("statement"), str) or not goal["statement"]:
            errors.append(f"{where}: goal {goal.get('id')} needs a statement")
        if not any(route.get("goal") == goal.get("id") for route in revision["routes"]):
            errors.append(f"{where}: goal {goal.get('id')} has no route")
    for node in revision["nodes"]:
        here = f"{where}: node {node.get('id')}"
        if not isinstance(node.get("statement"), str) or not node["statement"]:
            errors.append(f"{here} needs a statement")
        criteria = node.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            errors.append(f"{here} needs criteria")
            continue
        for criterion in criteria:
            if (
                set(criterion) != {"name", "measure", "comparison", "threshold"}
                or not SLUG.fullmatch(str(criterion["name"]))
                or not MEASURE.fullmatch(str(criterion["measure"]))
                or criterion["comparison"] not in trail.COMPARISONS
                or isinstance(criterion["threshold"], bool)
                or not isinstance(criterion["threshold"], int | float)
            ):
                errors.append(f"{here}: a criterion is a name, a measure, a comparison of lt, le, eq, ge or gt, and a threshold")
        if len({criterion.get("name") for criterion in criteria}) != len(criteria):
            errors.append(f"{here}: criterion names repeat")
        if not any(node.get("id") in route.get("path", []) for route in revision["routes"]):
            errors.append(f"{here} is on no route")
    for route in revision["routes"]:
        here = f"{where}: route {route.get('id')}"
        if set(route) - {"id", "goal", "method", "path", "status", "why"}:
            errors.append(f"{here} has unknown fields")
        if route.get("goal") not in goals:
            errors.append(f"{here} aims at {route.get('goal')}, which is not a goal")
        if not isinstance(route.get("method"), str) or not route["method"]:
            errors.append(f"{here} needs a method")
        path = route.get("path")
        if not isinstance(path, list) or not path:
            errors.append(f"{here} needs a path of one or more nodes")
        else:
            errors += [f"{here} passes {node}, which is not a node" for node in path if node not in nodes]
            if len(set(path)) != len(path):
                errors.append(f"{here} passes a node twice")
        if route.get("status") not in ("open", "abandoned"):
            errors.append(f"{here}: status is open or abandoned")
        if (route.get("status") == "abandoned") != bool(route.get("why")):
            errors.append(f"{here}: an abandoned route, and only one, says why")
    by_id = {node["id"]: node for node in revision["nodes"] if node.get("id") in nodes}
    seen = set()
    for resolution in revision["resolutions"]:
        here = f"{where}: resolution of {resolution.get('node')}"
        if set(resolution) != {"node", "cites", "holds"} or not isinstance(resolution["holds"], bool):
            errors.append(f"{here} is a node, the observation it cites and whether it holds")
            continue
        if resolution["node"] not in by_id:
            errors.append(f"{here}: no such node")
            continue
        if (resolution["node"], resolution["cites"]) in seen:
            errors.append(f"{here} cites {resolution['cites']} twice")
        seen.add((resolution["node"], resolution["cites"]))
        found = trails.cite(resolution["cites"], project)
        if isinstance(found, str):
            errors.append(f"{here}: {found}")
            continue
        _, step = found
        if step["kind"] != "observation":
            errors.append(f"{here} cites {step['id']}, {trail.a(step['kind'])}, not an observation")
            continue
        recomputed = meets(by_id[resolution["node"]], step)
        if recomputed is None:
            lacking = sorted({c["measure"] for c in by_id[resolution["node"]]["criteria"]} - set(measures(step)))
            errors.append(f"{here}: {step['id']} has no {', '.join(lacking)}")
        elif recomputed != resolution["holds"]:
            said = "holds" if resolution["holds"] else "does not hold"
            errors.append(f"{here} says it {said}, but {step['id']}'s measures say otherwise")
        if resolution["holds"]:
            # Only a traced observation is the run itself; a re-execution or a command line is a lead.
            caught = [run for run, how in peeks(revision, trails, resolution) if how == "read"]
            if caught:
                errors.append(f"{here}: {', '.join(caught)} read a sealed input before {step['id']}'s run")
    return errors


def check(revs: list[dict], trails: Trails) -> list[str]:
    if not revs:
        return ["no revisions"]
    errors = []
    for number, revision in enumerate(revs):
        if revision.get("rev") != number or revision.get("_file", f"rev-{number}.json") != f"rev-{number}.json":
            errors.append(f"{revision.get('_file', 'a revision')}: expected rev {number}; a revision is missing or misnumbered")
            continue
        if number and revision.get("prev") != digest(revs[number - 1]):
            errors.append(f"rev-{number}: prev does not match rev-{number - 1}, so a revision changed after it was sealed")
        errors += check_revision(revision, trails)
        if revision.get("project") != revs[0].get("project"):
            errors.append(f"rev-{number}: the project changed")
    for probe, steps in trails.steps.items():
        errors += [f"{probe}: {error}" for error in trail.check(steps)]
    errors += trail.merge(list(trails.steps.values()))[2]
    return errors + trails.problems


# ---------------------------------------------------------------------------------------------
# What the map shows


def state(revision: dict) -> dict:
    """Reached and refuted nodes, and each route's status and next node: derived, never stored."""
    holding = {r["node"] for r in revision["resolutions"] if r["holds"]}
    refuted = {r["node"] for r in revision["resolutions"] if not r["holds"]} - holding
    routes = {}
    for route in revision["routes"]:
        ahead = [node for node in route["path"] if node not in holding]
        if route["status"] == "abandoned":
            status = "abandoned"
        elif not ahead:
            status = "done"
        elif any(node in refuted for node in route["path"]):
            status = "blocked"
        else:
            status = "open"
        routes[route["id"]] = {"status": status, "next": ahead[0] if ahead and status == "open" else None}
    goals = {
        goal["id"]: any(routes[r["id"]]["status"] == "done" for r in revision["routes"] if r["goal"] == goal["id"])
        for goal in revision["goals"]
    }
    return {"reached": holding, "refuted": refuted, "routes": routes, "goals": goals}


def node_state(node: str, now: dict) -> str:
    return "reached" if node in now["reached"] else "refuted" if node in now["refuted"] else "open"


def ranked(revision: dict) -> list[dict]:
    """The next node of every open route, most shared first: the routes it leads, then the routes
    whose path holds it, then its id."""
    now = state(revision)
    live = [route for route in revision["routes"] if route["status"] != "abandoned"]
    leading = {}
    for route in revision["routes"]:
        if nxt := now["routes"][route["id"]]["next"]:
            leading.setdefault(nxt, []).append(route["id"])
    rows = [
        {
            "node": node,
            "leads": routes,
            "through": sum(node in route["path"] for route in live),
            "open_goals": sorted(
                {route["goal"] for route in revision["routes"] if route["id"] in routes and not now["goals"][route["goal"]]}
            ),
        }
        for node, routes in leading.items()
    ]
    return sorted(rows, key=lambda row: (-len(row["leads"]), -row["through"], row["node"]))


def shared_nodes(revision: dict) -> dict[str, list[str]]:
    routes = {}
    for route in revision["routes"]:
        if route["status"] != "abandoned":
            for node in route["path"]:
                routes.setdefault(node, []).append(route["id"])
    return {node: on for node, on in routes.items() if len(on) > 1}


# ---------------------------------------------------------------------------------------------
# propose and seal


def walk(path: list[str], start: int, nodes: dict, observations: list[dict]) -> tuple[list[tuple[str, dict]], tuple[str, dict] | None]:
    """The nodes a trail's observations meet, in order from `start`: one observation may meet several
    in a row. Then the last observation that measured what the next node needs but missed it."""
    met, at = [], start
    for observation in observations:
        while at < len(path) and meets(nodes[path[at]], observation) is True:
            met.append((path[at], observation))
            at += 1
    missed = None
    if at < len(path):
        tried = [o for o in observations if meets(nodes[path[at]], o) is False]
        missed = (path[at], tried[-1]) if tried else None
    return met, missed


def propose(revs: list[dict], trails: Trails) -> dict:
    last = revs[-1]
    project, now = last["project"], state(last)
    nodes = {node["id"]: node for node in last["nodes"]}
    draft = {key: value for key, value in sealed(last).items() if key not in SEALED}
    cited = {r["cites"].split("#")[0].split("@")[0] + "#" + r["cites"].split("#")[1] for r in last["resolutions"]}
    candidates, notes = {}, []
    for probe, steps in trails.steps.items():
        tag = ROUTE_TAG.match(steps[0]["summary"])
        routes = [
            route for route in last["routes"] if now["routes"][route["id"]]["status"] == "open" and (route["id"] == tag[1] if tag else True)
        ]
        observations = [step for step in steps if step["kind"] == "observation"]
        for route in routes:
            start = route["path"].index(now["routes"][route["id"]]["next"])
            met, missed = walk(route["path"], start, nodes, observations)
            for node, observation, holds in [*((n, o, True) for n, o in met), *([(*missed, False)] if missed else [])]:
                ref = trails.pin(probe, observation, project)
                if ref.split("@")[0] + "#" + observation["id"] in cited:
                    continue
                kept = candidates.setdefault(
                    (node, ref), {"node": node, "cites": ref, "holds": holds, "routes": [], "summary": observation["summary"]}
                )
                kept["routes"].append(route["id"])
                # Earlier observations that measured this node and missed it: a hit after misses may be a
                # second look, which a person has to judge before accepting it.
                if holds and (
                    misses := [o["id"] for o in observations if o["seq"] < observation["seq"] and meets(nodes[node], o) is False]
                ):
                    kept["after_misses"] = misses
        # A replacement plan none of whose observations resolves a node is a path the map does not have yet.
        resolved = {r["cites"].split("#")[1] for r in last["resolutions"] if r["cites"].split("@")[0] == probe.split("/", 1)[1]}
        for step in steps:
            testing = {o["id"] for o in observations if step["id"] in view.linked(o, "tests")}
            if step["kind"] == "plan" and view.linked(step, "supersedes") and not testing & resolved:
                notes.append(f"unmapped: {probe} {step['id']} supersedes {', '.join(view.linked(step, 'supersedes'))}: {step['summary']}")
    draft["candidates"] = list(candidates.values())
    draft["reason"] = "\n".join(["(rewrite this reason before sealing)", *notes])
    draft["triggered_by"] = sorted({c["cites"] for c in draft["candidates"]})
    return draft


def seal(revs: list[dict], draft: dict, by: str, at: str, trails: Trails) -> tuple[dict, list[str]]:
    if "candidates" in draft:
        return {}, ["the draft still has candidates: move the ones you accept into resolutions and delete the rest"]
    extra = sorted(set(draft) & set(SEALED))
    if extra:
        return {}, [f"the draft has {', '.join(extra)}, which seal writes"]
    revision = {**draft, "rev": len(revs), "at": at, "by": by}
    if revs:
        revision["prev"] = digest(revs[-1])
    return revision, check([*revs, revision], trails)


# ---------------------------------------------------------------------------------------------
# brief


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def unbundle(bundle: Path, into: Path) -> Path:
    """A bare repository holding a trail's code snapshots."""
    git("init", "-q", "--bare", str(into))
    git("-C", str(into), "fetch", "-q", str(bundle.resolve()), "refs/*:refs/*")
    return into


def brief(revision: dict, route_id: str, trails: Trails, demo: Path, out: Path, alongside: list[str] = ()) -> dict:
    """Writes a demo directory for one open route. The task cites the results already reached on
    its path, and the workspace is the code of the last of them, so the agent starts there. With
    routes `alongside`, the prompt says agents run them at the same time and how to use their work."""
    now, project = state(revision), revision["project"]
    route = next((r for r in revision["routes"] if r["id"] == route_id), None)
    if route is None or now["routes"][route_id]["status"] != "open":
        raise Usage(f"route {route_id} is not an open route of rev-{revision['rev']}")
    nodes = {node["id"]: node for node in revision["nodes"]}
    goal = next(goal for goal in revision["goals"] if goal["id"] == route["goal"])
    ahead = route["path"][route["path"].index(now["routes"][route_id]["next"]) :]
    behind = route["path"][: len(route["path"]) - len(ahead)]
    builds_on, established = [], []
    for node in behind:
        resolution = [r for r in revision["resolutions"] if r["node"] == node and r["holds"]][-1]
        probe, step = trails.cite(resolution["cites"], project)
        established.append((node, step, resolution["cites"]))
        if resolution["cites"] not in builds_on:
            builds_on.append(resolution["cites"])
    task = json.loads((demo / "task.json").read_text())
    task["summary"] = f"Route {route_id}: {task['summary']}"[:200]
    for node in route["path"]:
        for criterion in nodes[node]["criteria"]:
            if criterion["measure"] not in task["declared_measures"]:
                task["declared_measures"].append(criterion["measure"])
    if builds_on:
        task["builds_on"] = builds_on
    if out.exists():
        raise Usage(f"{out} exists; a brief is written once")
    (out / "workspace").mkdir(parents=True)
    source = "the demo's workspace"
    if established:
        probe, step = trails.cite(established[-1][2], project)
        run = next(s for s in trails.steps[probe] if s["id"] == trail.observed(step))
        commit = run["code"]["ref"].split("@")[-1].split(":")[-1]
        with tempfile.TemporaryDirectory() as work:
            bare = unbundle(trails.paths[probe] / "code.bundle", Path(work) / "code.git")
            archive = subprocess.run(["git", "-C", str(bare), "archive", commit], check=True, capture_output=True).stdout
            subprocess.run(["tar", "-x", "-C", str(out / "workspace"), "--exclude=out", "--exclude=.venv"], input=archive, check=True)
        source = f"the code snapshot of {run['id']} in {probe}, {commit[:7]}"
    else:
        shutil.copytree(demo / "workspace", out / "workspace", dirs_exist_ok=True, ignore=shutil.ignore_patterns("out", ".venv"))
    lines = [
        (demo / "prompt.md").read_text().rstrip(),
        "",
        f"## Your route: {route_id}",
        "",
        (
            f"This task is one route of a research map that has several routes to several goals. Your route's goal: "
            f"{goal['statement']}. Your route's method: {route['method']}."
        ),
    ]
    if established:
        lines += [
            "",
            (
                "The task above is shared by every route, and its first part is already answered. These results are "
                "established by earlier work, which this task cites; do not recompute them:"
            ),
        ]
        cited = {}
        for node, step, ref in established:
            cited.setdefault(ref, (step, []))[1].append(nodes[node]["statement"])
        for ref, (step, statements) in cited.items():
            said = ", ".join(f"{name} {view.number(value)}" for name, value in measures(step).items())
            lines.append(f"- {'; '.join(statements)}: {said} ({step['id']} of {ref.split('@')[0]})")
        lines += ["", f"The workspace is the code that produced the last of these: {source}."]
    if alongside:
        lines += [
            "",
            "## Working alongside other agents",
            "",
            (
                f"Other agents are working on this map at the same time, on routes {', '.join(alongside)}. The `project_map` tool shows "
                "the map and what every trail has found so far. Read it before each new plan. When a result of theirs serves your "
                "route, put its step reference, copied whole from `project_map`, in `propose_plan`'s `builds_on`, and say in the "
                "reasoning how you use it. Numbers from a run that opened a sealed input are withheld from you; do not look for them."
            ),
        ]
    if revision.get("instructions"):
        lines += ["", "Rules for every route of this map:", revision["instructions"]]
    lines += ["", "What your route must reach, in order:"]
    lines += [
        f"{n}. {nodes[node]['statement']}: {', '.join(criterion_text(c) for c in nodes[node]['criteria'])}"
        for n, node in enumerate(ahead, 1)
    ]
    lines += ["", f"Write every one of these measures to `out/metrics.json`: {', '.join(task['declared_measures'])}."]
    (out / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    (out / "prompt.md").write_text("\n".join(lines) + "\n")
    files = {
        str(path.relative_to(out / "workspace")): trail.digest(path.read_bytes())
        for path in sorted((out / "workspace").rglob("*"))
        if path.is_file()
    }
    record = {
        "route": route_id,
        "rev": revision["rev"],
        "map": digest(revision),
        "builds_on": builds_on,
        "workspace_from": source,
        "workspace": files,
        **({"alongside": list(alongside)} if alongside else {}),
    }
    (out / "brief.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


# ---------------------------------------------------------------------------------------------
# shared


def trees(trails: Trails) -> dict[str, dict[str, str]]:
    """For each trail with a code bundle, the tree of every snapshot commit: files that match give the same tree in any repository."""
    found = {}
    with tempfile.TemporaryDirectory() as work:
        for number, (probe, path) in enumerate(trails.paths.items()):
            if not (path / "code.bundle").exists():
                continue
            bare = unbundle(path / "code.bundle", Path(work) / f"code-{number}.git")
            found[probe] = dict(line.split() for line in git("-C", str(bare), "log", "--all", "--format=%H %T").splitlines())
    return found


def shared(revision: dict, trails: Trails) -> list[str]:
    lines = ["Milestones on more than one route, and the trails that reached them:"]
    for node, routes in sorted(shared_nodes(revision).items()):
        by = [
            r["cites"].split("@")[0] + "#" + r["cites"].split("#")[1] for r in revision["resolutions"] if r["node"] == node and r["holds"]
        ]
        lines.append(f"  {node}: on {', '.join(routes)}; reached by {', '.join(by) or 'none yet'}")
    used = {}
    for probe, steps in trails.steps.items():
        for step in steps:
            for kept in step.get("inputs", []) if step["kind"] == "run" else []:
                used.setdefault((kept["ref"], kept["digest"]), set()).add(probe)
    lines += ["", "Files more than one trail used at the same digest:"]
    lines += [
        f"  {ref} {kept[:19]}…: {', '.join(sorted(p.split(':', 1)[1] for p in probes))}"
        for (ref, kept), probes in sorted(used.items())
        if len(probes) > 1
    ] or ["  none"]
    tree_of = trees(trails)
    runs = []
    for probe, steps in trails.steps.items():
        for step in steps:
            if step["kind"] != "run":
                continue
            commit = step["code"]["ref"].split(":")[-1].split("@")[-1]
            tree = next((t for c, t in tree_of.get(probe, {}).items() if c.startswith(commit)), None)
            runs.append((probe, step, tree, commit))
    by_tree = {}
    for probe, _, tree, _ in runs:
        if tree:
            by_tree.setdefault(tree, set()).add(probe)
    lines += ["", "Code more than one trail ran, by tree (a commit differs between repositories, its tree does not):"]
    lines += [
        f"  tree {tree[:7]}: {', '.join(sorted(p.split(':', 1)[1] for p in probes))}"
        for tree, probes in sorted(by_tree.items())
        if len(probes) > 1
    ] or ["  none"]
    repeats = {}
    for probe, step, tree, commit in runs:
        key = (step["command"]["digest"], tree or f"{probe}:{commit}", tuple(sorted(i["digest"] for i in step.get("inputs", []))))
        repeats.setdefault(key, []).append((probe, step))
    lines += ["", "Computation repeated across trails: the same command, code tree and inputs:"]
    found = [ran for ran in repeats.values() if len({probe for probe, _ in ran}) > 1]
    for ran in found:
        lines.append(
            f"  {ran[0][1]['command']['shown'][:60]}: " + ", ".join(f"{probe.split(':', 1)[1]} {step['id']}" for probe, step in ran)
        )
    if not found:
        lines.append("  none")
    if trails.retraced:
        lines += ["", "Re-executed with retrace.py, from each run's code snapshot (a replay, not the run itself):"]
        for probe, runs in sorted(trails.retraced.items()):
            # Only a run whose observation cites a metrics file has something to reproduce.
            wrote = [run for run in runs.values() if (run.get("metrics") or {}).get("recorded")]
            same = [run["run"] for run in wrote if run["metrics"]["recorded"] == run["metrics"]["replayed"]]
            differ = [run["run"] for run in wrote if run["metrics"]["recorded"] != run["metrics"]["replayed"]]
            exits = [run["run"] for run in runs.values() if "exit" in run and run["exit"]["recorded"] != run["exit"]["replayed"]]
            lines.append(
                f"  {probe.split(':', 1)[1]}: {len(runs)} runs; {len(same)} of {len(wrote)} metrics files reproduced byte for byte"
                + (f"; differed: {', '.join(differ)}" if differ else "")
                + (f"; exit code differed: {', '.join(exits)}" if exits else "")
            )
    return lines


# ---------------------------------------------------------------------------------------------
# graph and view


def graph(revision: dict, trails: Trails) -> tuple[list[dict], list[dict], list[str]]:
    nodes, edges, errors = trail.merge(list(trails.steps.values()))
    project, now = revision["project"], state(revision)
    me = f"{project}/map:rev-{revision['rev']}"
    nodes.append(
        {
            "id": me,
            "kind": "map",
            "graph": me,
            "tier": 3,
            "version": digest(revision),
            "at": revision["at"],
            "label": f"Research map, revision {revision['rev']}",
        }
    )

    def edge(source, relation, target, kept=""):
        edges.append({"source": source, "relation": relation, "target": target, "status": "confirmed", "digest": kept, "graph": me})

    def probe_step(ref: str) -> tuple[str, str]:
        cites = trail.PROBE_REF.fullmatch(ref)
        return f"{cites['project'] or project}/probe:{cites['trail']}#{cites['step']}", cites["head"]

    for goal in revision["goals"]:
        nodes.append(
            {
                "id": f"{project}/goal:{goal['id']}",
                "kind": "goal",
                "graph": me,
                "tier": 3,
                "label": goal["statement"][:200],
                "outcome": "reached" if now["goals"][goal["id"]] else "open",
            }
        )
        edge(me, "contains", f"{project}/goal:{goal['id']}")
    for node in revision["nodes"]:
        nodes.append(
            {
                "id": f"{project}/milestone:{node['id']}",
                "kind": "milestone",
                "graph": me,
                "tier": 3,
                "label": node["statement"][:200],
                "outcome": "" if node_state(node["id"], now) == "open" else node_state(node["id"], now),
            }
        )
        edge(me, "contains", f"{project}/milestone:{node['id']}")
    for route in revision["routes"]:
        here = f"{project}/route:{route['id']}"
        nodes.append(
            {
                "id": here,
                "kind": "route",
                "graph": me,
                "tier": 3,
                "label": route["method"][:200],
                "outcome": now["routes"][route["id"]]["status"],
            }
        )
        edge(me, "contains", here)
        edge(here, "aims_at", f"{project}/goal:{route['goal']}")
        for node in route["path"]:
            edge(here, "passes", f"{project}/milestone:{node}")
    for resolution in revision["resolutions"]:
        target, head = probe_step(resolution["cites"])
        edge(f"{project}/milestone:{resolution['node']}", "resolved_by" if resolution["holds"] else "refuted_by", target, head)
    for ref in revision["triggered_by"]:
        target, head = probe_step(ref)
        edge(me, "triggered_by", target, head)
    return nodes, edges, errors


def peeks(revision: dict, trails: Trails, resolution: dict) -> list[tuple[str, str]]:
    """Runs before the cited observation's own run, in its trail, that opened a sealed input, each with
    how that is known (see Trails.read). Only a "read" is the run itself, traced as it ran."""
    sealed_inputs = revision.get("sealed_inputs", [])
    found = trails.cite(resolution["cites"], revision["project"])
    if not sealed_inputs or isinstance(found, str):
        return []
    probe, observation = found
    own = trail.observed(observation)
    return [
        (step["id"], how)
        for step in trails.steps[probe][: observation["seq"]]
        if step["kind"] == "run" and step["id"] != own and (how := trails.read(probe, step, sealed_inputs))
    ]


def show(revision: dict, trails: Trails) -> list[str]:
    now, project = state(revision), revision["project"]
    statement = {node["id"]: node["statement"] for node in revision["nodes"]}
    common = shared_nodes(revision)
    lines = [
        f"Research map of {project}, revision {revision['rev']} ({revision['at']}, {revision['by']}).",
        f"{len(trails.steps)} trails. ✓ reached, ✗ refuted, ○ open; * on more than one route.",
        "",
        "Goals:",
    ]
    lines += [f"  {'✓' if now['goals'][goal['id']] else '○'} {goal['id']}: {goal['statement']}" for goal in revision["goals"]]
    lines += ["", "Routes:"]
    for route in revision["routes"]:
        path = " → ".join(f"{node}{'*' * (node in common)} {MARKS[node_state(node, now)]}" for node in route["path"])
        lines.append(f"  {route['id']} ({now['routes'][route['id']]['status']}, for {route['goal']}): {path}")
        lines.append(f"      {route['method']}" + (f". Abandoned: {route['why']}" if route["status"] == "abandoned" else ""))
    lines += ["", "Milestones and what reached them:"]
    for node in revision["nodes"]:
        criteria = ", ".join(criterion_text(c) for c in node["criteria"])
        lines.append(f"  {MARKS[node_state(node['id'], now)]} {node['id']}: {statement[node['id']]} ({criteria})")
        for resolution in revision["resolutions"]:
            if resolution["node"] == node["id"]:
                _, step = trails.cite(resolution["cites"], project)
                name = resolution["cites"].split("@")[0]
                lines.append(f"      {'reached' if resolution['holds'] else 'refuted'} by {name} {step['id']}: {step['summary']}")
                if peeked := peeks(revision, trails, resolution):
                    lines.append(f"        before it, a sealed input: {', '.join(f'{run} {how}' for run, how in peeked)}")
    lines += ["", "Next, the most shared first:"]
    for row in ranked(revision) or []:
        goals = f"; goals not yet reached: {', '.join(row['open_goals'])}" if row["open_goals"] else ""
        lines.append(f"  {row['node']}: next on {', '.join(row['leads'])}; on {row['through']} route{'s' * (row['through'] != 1)}{goals}")
    if not ranked(revision):
        lines.append("  no open route")
    return lines


# ---------------------------------------------------------------------------------------------
# The live state: what the terminal, the viewer and an agent's project_map tool are shown

WITHHELD = "scored a sealed input; numbers withheld"
ACTIVE_S = 300


def cross_links(step: dict, project: str, trails: Trails) -> list[dict]:
    """A step's links to other probes. One that cites a head and no step points at the step that head
    ended at, when the trail is given: what a project_map note saw of a sibling."""
    found = []
    for link in step.get("links", []):
        if cites := trail.PROBE_REF.fullmatch(link["target"]):
            probe = f"{cites['project'] or project}/probe:{cites['trail']}"
            at = cites["step"]
            if at is None and (seq := trails.heads.get(probe, {}).get(cites["head"])) is not None:
                at = trails.steps[probe][seq]["id"]
            found.append({"relation": link["relation"], "probe": probe, "step": at, "head": cites["head"], "ref": link["target"]})
    return found


def live_state(revs: list[dict], trails: Trails, for_probe: str | None = None) -> dict:
    """The map's latest sealed revision with its derived states, what `propose` would draft now (never
    sealed), and every trail as it stands. For an agent (`for_probe`), a sibling's observation whose run
    opened a sealed input is shown without its numbers."""
    last = revs[-1]
    project, now, common = last["project"], state(last), shared_nodes(last)
    sealed_inputs = last.get("sealed_inputs", [])

    def opened(probe: str, step: dict) -> str | None:
        return trails.read(probe, step, sealed_inputs) if sealed_inputs and step["kind"] == "run" else None

    def hidden(probe: str, observation: dict) -> bool:
        if for_probe is None or probe == for_probe:
            return False
        run = next((s for s in trails.steps[probe] if s["id"] == trail.observed(observation)), None)
        return run is not None and opened(probe, run) is not None

    def resolution(ref: str, holds: bool, sealed_: bool, extra: dict) -> dict:
        found = trails.cite(ref, project)
        probe, step = found if not isinstance(found, str) else (None, None)
        quiet = probe is not None and hidden(probe, step)
        return {
            "cites": ref,
            "probe": probe,
            "step": step["id"] if step else None,
            "holds": holds,
            "sealed": sealed_,
            "summary": WITHHELD if quiet else (step["summary"] if step else found),
            **extra,
        }

    candidates = propose(revs, trails)["candidates"]
    nodes = []
    for node in last["nodes"]:
        nodes.append(
            {
                "id": node["id"],
                "statement": node["statement"],
                "criteria": [criterion_text(c) for c in node["criteria"]],
                "state": node_state(node["id"], now),
                "routes": [route["id"] for route in last["routes"] if node["id"] in route["path"]],
                "shared": node["id"] in common,
                "resolutions": [resolution(r["cites"], r["holds"], True, {}) for r in last["resolutions"] if r["node"] == node["id"]],
                "provisional": [
                    resolution(
                        c["cites"],
                        c["holds"],
                        False,
                        {"routes": c["routes"], **({"after_misses": c["after_misses"]} if "after_misses" in c else {})},
                    )
                    for c in candidates
                    if c["node"] == node["id"]
                ],
            }
        )
    lanes = []
    for probe, steps in trails.steps.items():
        tag = ROUTE_TAG.match(steps[0]["summary"])
        shown = []
        for step in steps:
            entry = {
                "id": step["id"],
                "kind": step["kind"],
                "at": step["at"],
                "summary": step["summary"],
                "links": cross_links(step, project, trails),
            }
            if step["kind"] == "observation":
                quiet = hidden(probe, step)
                tested = view.linked(step, "tests")
                plan = next((s for s in steps if s["id"] in tested), None)
                entry |= {
                    "plan": None if quiet or plan is None else plan["summary"],
                    "observes": trail.observed(step),
                    "outcome": step["outcome"],
                    "measures": {} if quiet else measures(step),
                    "summary": WITHHELD if quiet else step["summary"],
                    "withheld": quiet,
                }
            elif step["kind"] == "run" and (how := opened(probe, step)):
                entry["sealed_read"] = how
            shown.append(entry)
        lanes.append(
            {
                "probe": probe,
                "trail": steps[0]["trail"],
                "route": tag[1] if tag else None,
                "agent": (steps[0].get("agent") or {}).get("model"),
                "head": trail.digest(trail.canonical(steps[-1])),
                "count": len(steps),
                "last_at": steps[-1]["at"],
                "reading": probe in trails.reading,
                "problems": [] if probe in trails.reading else trail.check(steps),
                "steps": shown,
            }
        )
    marker = trail.digest(
        trail.canonical({"rev": digest(last), "heads": sorted((lane["probe"], lane["head"], lane["reading"]) for lane in lanes)})
    )
    return {
        "project": project,
        "problems": check(revs, trails),
        "rev": last["rev"],
        "rev_digest": digest(last),
        "at": last["at"],
        "by": last["by"],
        "for": for_probe,
        "etag": marker,
        "sealed_inputs": sealed_inputs,
        "goals": [{"id": g["id"], "statement": g["statement"], "reached": now["goals"][g["id"]]} for g in last["goals"]],
        "routes": [
            {
                "id": route["id"],
                "goal": route["goal"],
                "method": route["method"],
                "path": route["path"],
                "status": now["routes"][route["id"]]["status"],
                "next": now["routes"][route["id"]]["next"],
                **({"why": route["why"]} if route["status"] == "abandoned" else {}),
            }
            for route in last["routes"]
        ],
        "nodes": nodes,
        "next": ranked(last),
        "trails": lanes,
    }


def age(at: str, clock: datetime) -> float:
    return (clock - datetime.fromisoformat(at)).total_seconds()


def status_text(live: dict, clock: datetime, refs_per_trail: int = 3) -> list[str]:
    """The live state as text: what `status` prints and an agent's project_map tool returns. Each step
    reference it shows is pinned at its trail's present head, so a plan may build on it."""
    marks = {"reached": "✓", "refuted": "✗", "open": "○"}
    lines = [f"Project {live['project']}, map revision {live['rev']} ({live['rev_digest']}, sealed {live['at']} by {live['by']})."]
    if live["problems"]:
        lines.append(f"project.py check finds {len(live['problems'])} problems; the first: {live['problems'][0]}")
    lines.append("Goals: " + ", ".join(f"{'✓' if g['reached'] else '○'} {g['id']}" for g in live["goals"]))
    lines += ["", "Routes:"]
    state_of = {node["id"]: node["state"] for node in live["nodes"]}
    for route in live["routes"]:
        path = " → ".join(f"{node} {marks[state_of[node]]}" for node in route["path"])
        lines.append(f"  {route['id']} ({route['status']}, for {route['goal']}): {path}")
    lines += ["", "Milestones, with what reached them (sealed in the map, or provisional: found in a trail, not yet sealed):"]
    for node in live["nodes"]:
        lines.append(f"  {marks[node['state']]} {node['id']}: {node['statement']} ({', '.join(node['criteria'])})")
        for r in node["resolutions"] + node["provisional"]:
            kind = "sealed" if r["sealed"] else "provisional"
            lines.append(f"      {kind}, {'reached' if r['holds'] else 'refuted'} by {r['cites']}: {r['summary']}")
    lines += ["", "Trails (each reference is pinned at the trail's present head):"]
    for lane in live["trails"]:
        if lane["probe"] == live["for"]:
            continue
        idle = age(lane["last_at"], clock)
        doing = "running" if idle < ACTIVE_S else "idle"
        lines.append(f"  {lane['trail']} (route {lane['route'] or 'none'}, {lane['count']} steps, {doing}, last step {int(idle)} s ago)")
        name = lane["probe"].split("/", 1)[1] if lane["probe"].startswith(live["project"] + "/") else lane["probe"]
        for step in [s for s in lane["steps"] if s["kind"] == "observation"][-refs_per_trail:]:
            said = ", ".join(f"{k} {view.number(v)}" for k, v in step["measures"].items())
            lines.append(
                f"      {name}@{lane['head']}#{step['id']}: {step['summary']}"
                + (f"; {said}" if said and said not in step["summary"] else "")
                + (f" (under the plan: {step['plan']})" if step.get("plan") else "")
            )
    return lines


# ---------------------------------------------------------------------------------------------
# Command line

OPTIONS = ("--trails", "--out", "--by", "--demo", "--at", "--live", "--for", "--port", "--with")
FLAGS = ("--csv", "--json")


def parse(argv: list[str]) -> tuple[list[str], list[Path], list[Path], dict[str, str], set[str]]:
    args, paths, retraced, named, flags = [], [], [], {}, set()
    rest = list(argv)
    while rest:
        word = rest.pop(0)
        if word in FLAGS:
            flags.add(word[2:])
        elif word in ("--trails", "--reads"):
            into = paths if word == "--trails" else retraced
            while rest and not rest[0].startswith("--"):
                into.append(Path(rest.pop(0)))
        elif word in OPTIONS:
            if not rest or rest[0].startswith("--"):
                raise Usage(f"project.py: {word} needs a value")
            named[word[2:]] = rest.pop(0)
        elif word.startswith("--"):
            raise Usage(f"project.py: unknown option {word}")
        else:
            args.append(word)
    return args, paths, retraced, named, flags


def main(argv: list[str]) -> int:
    try:
        args, paths, retraced, named, flags = parse(argv[1:])
        if len(args) < 2:
            raise Usage("usage: project.py COMMAND MAP --trails TRAIL... [options]; see the docstring")
        command, directory = args[0], Path(args[1])
        revs = revisions(directory)
        if command == "serve":
            if not revs or not ("live" in named or paths):
                raise Usage("usage: project.py serve MAP --live DIR [--trails TRAIL...] [--reads FILE...] [--port N]")
            import mapview

            return mapview.serve(directory, named.get("live"), paths, retraced, int(named.get("port", 8077)))
        if "live" in named and revs:
            paths = [*paths, *(found for found in discover(Path(named["live"]), revs[-1]["project"]) if found not in paths)]
        trails = Trails(paths, retraced, directory.parent)
        if command == "seal":
            if len(args) != 3 or "by" not in named:
                raise Usage("usage: project.py seal MAP DRAFT --by ACTOR --trails TRAIL...")
            at = named.get("at") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            revision, errors = seal(revs, json.loads(Path(args[2]).read_text()), named["by"], at, trails)
            if errors:
                print("\n".join(errors))
                return 1
            directory.mkdir(parents=True, exist_ok=True)
            try:
                with (directory / f"rev-{revision['rev']}.json").open("x") as file:
                    file.write(json.dumps(revision, indent=2, ensure_ascii=False) + "\n")
            except FileExistsError:
                print(f"rev-{revision['rev']} was sealed meanwhile; propose again")
                return 1
            print(f"wrote {directory / f'rev-{revision["rev"]}.json'}")
            return 0
        errors = check(revs, trails)
        # The live views show what fails check rather than refusing: a map is watched while it is wrong too.
        if command == "check" or (errors and command not in ("status", "page")):
            print("\n".join(errors) or f"ok: {len(revs)} revisions, {len(revs[-1]['resolutions'])} resolutions, {len(trails.steps)} trails")
            return 1 if errors else 0
        last = revs[-1]
        if command == "propose":
            text = json.dumps(propose(revs, trails), indent=2, ensure_ascii=False) + "\n"
            if "out" in named:
                Path(named["out"]).write_text(text)
                print(f"wrote {named['out']}")
            else:
                print(text, end="")
        elif command == "next":
            print("\n".join(show(last, trails)[-(len(ranked(last)) or 1) - 1 :]))
        elif command == "brief":
            if len(args) != 3 or "out" not in named:
                raise Usage("usage: project.py brief MAP ROUTE --out DIR --trails TRAIL... [--demo DIR]")
            alongside = [route for route in named.get("with", "").split(",") if route and route != args[2]]
            record = brief(last, args[2], trails, Path(named.get("demo", "demo")), Path(named["out"]), alongside)
            print(f"wrote {named['out']}: route {record['route']}, builds on {', '.join(record['builds_on']) or 'nothing'}")
        elif command == "shared":
            print("\n".join(shared(last, trails)))
        elif command == "graph":
            if "out" not in named:
                raise Usage("usage: project.py graph MAP --out DIR --trails TRAIL... [--csv]")
            nodes, edges, problems = graph(last, trails)
            if problems:
                print("\n".join(problems))
                return 1
            trail.write_graph(Path(named["out"]), nodes, edges, ".csv" if "csv" in flags else ".parquet")
        elif command == "view":
            print("\n".join(show(last, trails)))
        elif command == "status":
            for_probe = named.get("for")
            if for_probe is not None and for_probe not in trails.steps:
                for_probe = next((probe for probe in trails.steps if probe.endswith(f"/probe:{for_probe}")), None)
                if for_probe is None:
                    raise Usage(f"project.py: --for {named['for']} is not among the trails")
            live = live_state(revs, trails, for_probe)
            if "json" in flags:
                print(json.dumps(live, indent=2, ensure_ascii=False))
            else:
                print("\n".join(status_text(live, datetime.now(UTC))))
        elif command == "page":
            if "out" not in named:
                raise Usage("usage: project.py page MAP --out FILE --trails TRAIL... [--live DIR]")
            import mapview

            Path(named["out"]).write_text(mapview.page(live_state(revs, trails), datetime.now(UTC)))
            print(f"wrote {named['out']}")
        else:
            raise Usage(f"project.py: unknown command {command}")
        return 0
    except Usage as usage:
        print(usage.args[0], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

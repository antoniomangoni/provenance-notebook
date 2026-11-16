"""Check a provenance trail, write the example ones, or export checked trails as a graph.

    python trail.py check TRAIL_DIR [--store STORE_DIR]
    python trail.py facts TRAIL_DIR [--store STORE_DIR]
    python trail.py head TRAIL_DIR
    python trail.py verify TRAIL_DIR HEAD
    python trail.py examples DIR
    python trail.py graph TRAIL_DIR [--csv]
    python trail.py merge OUT_DIR TRAIL_DIR... [--csv]
    python trail.py why TRAIL_DIR [STEP]
    python trail.py view TRAIL_DIR [--store STORE_DIR] [--code REPO] [--out FILE]
    python trail.py review TRAIL_DIR STEP --verdict confirms|disputes --text TEXT --by NAME
    python trail.py note TRAIL_DIR STEP --text TEXT --by NAME

A trail is a directory of step files, steps/step-N.json, each written once. The JSON Schema
checks one file; this checks what spans files: order, the digest chain, which kinds carry
which fields, who may write them, and that outcomes follow from the measured checks; with
`--store`, that the measures are the ones in the metrics file the run wrote. `facts` lists what
a checked trail shows without judging it: unsettled runs, attempts per plan, repeats. `head`
prints the digest a trail is cited at, and `verify` says whether a checked trail ever had a cited
head: one rewritten and re-chained still passes `check`, but no longer has it. `graph`
writes graph/nodes.parquet and graph/edges.parquet (typed; `--csv` writes text tables instead), the
probe as a named graph; `merge` writes one pair for several probes and resolves each citation of one probe by another (see docs/GRAPH.md).
`why` and `view` are what a reviewer reads (view.py); `review` and `note` append a person's step,
written only when the trail checks with it.
"""

import csv
import hashlib
import hmac
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

SCHEMA = json.loads((Path(__file__).parent / "step.schema.json").read_text())
COMMON = {"version", "id", "seq", "trail", "kind", "at", "by", "hook", "prev", "summary", "redactions", "links"}
# kind: (required fields, optional fields, actors allowed to write it)
KINDS = {
    "task": ({"question", "agent", "project", "declared_measures"}, {"public_parameters"}, {"human", "runner"}),
    "plan": ({"reasoning", "expectations"}, set(), {"agent", "human"}),
    # A run is the intent, written before the command executes; its observation is the settlement,
    # so a run that never finished stays in the trail, unsettled.
    "run": ({"command", "code"}, {"environment", "parameters", "inputs"}, {"runner"}),
    "observation": ({"outcome", "exit_code"},
                    {"outputs", "reads", "duration_ms", "measures", "measures_source", "checks", "error"}, {"runner"}),
    "review": ({"verdict", "text"}, set(), {"human"}),
    "note": ({"text"}, set(), {"agent", "human", "runner"}),
}
# relation: (kinds that may hold it, kind of step it points at)
RELATIONS = {
    "implements": ({"run"}, "plan"),
    "observes": ({"observation"}, "run"),
    "tests": ({"observation"}, "plan"),
    "triggered_by": ({"plan"}, "observation"),
    "supersedes": ({"plan", "note", "review"}, None),
    "reviews": ({"review"}, None),
    "about": ({"note"}, None),
    "builds_on": ({"task", "plan"}, None),
}
# Relations that may point at another probe; the kind of a cited step is checked by merge.
CROSS = {"builds_on", "triggered_by", "about"}
NAME = r"[a-z][a-z0-9_-]*"
PROBE_REF = re.compile(rf"(?:(?P<project>{NAME})/)?probe:(?P<trail>[a-z0-9]+(?:-[a-z0-9]+)*)"
                       r"@(?P<head>sha256:[0-9a-f]{64})(?:#(?P<step>step-(?:0|[1-9][0-9]*)))?")
QUALIFIED = re.compile(rf"{NAME}/{NAME}:")
KIND = re.compile(rf"(?:{NAME}/)?({NAME}):")
# Kinds named across projects: an actor or a URL is the same node wherever it is cited.
GLOBAL = {"url", "agent", "runner", "human"}
EXIT = ("exit_ok", "exit_fail")
COMPARISONS = {"lt": "<", "le": "<=", "eq": "==", "ge": ">=", "gt": ">"}


def a(word: str) -> str:
    return ("an " if word[0] in "aeiou" else "a ") + word


def canonical(step: dict) -> bytes:
    return json.dumps(step, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def keyed(key: bytes, data: bytes) -> str:
    """The digest of a non-public value: HMAC-SHA256 under the trail's secret, kept outside the trail."""
    return "hmac-sha256:" + hmac.new(key, data, hashlib.sha256).hexdigest()


def load(directory: Path) -> list[dict]:
    files = sorted((directory / "steps").glob("step-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    return [json.loads(p.read_text()) for p in files]


def holds(expectation: dict, measured: float | None, exit_code: int) -> bool | None:
    comparison = expectation["comparison"]
    if comparison == "exit_ok":
        return exit_code == 0
    if comparison == "exit_fail":
        return exit_code != 0
    if measured is None:
        return None
    threshold = expectation["threshold"]
    return {
        "lt": measured < threshold,
        "le": measured <= threshold,
        "eq": measured == threshold,
        "ge": measured >= threshold,
        "gt": measured > threshold,
    }[comparison]


def check(steps: list[dict], store: Path | None = None) -> list[str]:
    errors = []
    by_id: dict[str, dict] = {}
    previous = at = None
    public: set[str] = set()
    project = steps[0].get("project") if steps else None
    declared = set(steps[0].get("declared_measures", [])) if steps else set()
    settled: set[str] = set()
    for seq, step in enumerate(steps):
        where = step.get("id", f"#{seq}")
        for error in jsonschema.Draft7Validator(SCHEMA).iter_errors(step):
            errors.append(f"{where}: {error.json_path}: {error.message}")
        if errors and errors[-1].startswith(where):
            by_id[step.get("id", where)] = step
            previous = step
            continue
        kind, actor = step["kind"], step["by"].split(":", 1)[0]
        required, optional, actors = KINDS[kind]
        if step["seq"] != seq or step["id"] != f"step-{seq}":
            errors.append(f"{where}: expected step-{seq}; steps are numbered without gaps")
        if (seq == 0) != (kind == "task"):
            errors.append(f"{where}: a trail starts with exactly one task step")
        if seq == 0 and "prev" in step:
            errors.append(f"{where}: the first step has no prev")
        if seq and step.get("prev") != digest(canonical(previous)):
            errors.append(f"{where}: prev does not match step-{seq - 1}; an earlier step was changed")
        if seq and step["trail"] != steps[0]["trail"]:
            errors.append(f"{where}: trail differs from the task step")
        if at and datetime.fromisoformat(step["at"]) < at:
            errors.append(f"{where}: at is earlier than step-{seq - 1}'s; the capture clock only moves forward")
        at = datetime.fromisoformat(step["at"])
        if actor not in actors:
            errors.append(f"{where}: {a(kind)} step cannot be written by {actor}")
        for field in sorted(required - step.keys()):
            errors.append(f"{where}: {a(kind)} step needs {field}")
        for field in sorted(step.keys() - COMMON - required - optional):
            errors.append(f"{where}: {field} does not belong on {a(kind)} step")
        if kind == "task":
            public = set(step.get("public_parameters", []))
        # A plan promises only what the runner can measure; an expectation of anything else would
        # leave every observation of it inconclusive.
        for expectation in step.get("expectations", []):
            name = expectation["name"]
            if expectation["comparison"] not in EXIT and expectation["measure"] not in declared:
                errors.append(f"{where}: expectation {name} measures {expectation['measure']}, which the task does not declare")
            elif expectation["comparison"] not in EXIT and "threshold" not in expectation:
                errors.append(f"{where}: expectation {name} has no threshold to compare against")
        # A redacted command's plain digest hides only the redacted part, which is reversed by
        # guessing, so it is keyed like a non-public parameter.
        if step.get("redactions") and "command" in step and not step["command"]["digest"].startswith("hmac-sha256:"):
            errors.append(f"{where}: the command was redacted, so its digest is keyed (hmac-sha256)")
        for parameter in step.get("parameters", []):
            name, kept = parameter["name"], parameter["digest"]
            if name not in public:
                if "value" in parameter:
                    errors.append(f"{where}: parameter {name} is not public, so only its digest is kept")
                # A plain hash of a seed or a short key is reversed by guessing; only a digest
                # keyed with the trail's secret hides it.
                if not kept.startswith("hmac-sha256:"):
                    errors.append(f"{where}: parameter {name} is not public, so its digest is keyed (hmac-sha256)")
            elif "value" in parameter and kept != digest(parameter["value"].encode()):
                errors.append(f"{where}: parameter {name}'s digest is not the sha256 of its value")

        targets: dict[str, list[dict]] = {}
        cross: set[str] = set()
        for link in step.get("links", []):
            relation, target = link["relation"], link["target"]
            holders, target_kind = RELATIONS[relation]
            if kind not in holders:
                errors.append(f"{where}: {a(kind)} step cannot hold {relation}")
            if cites := PROBE_REF.fullmatch(target):
                if relation not in CROSS:
                    errors.append(f"{where}: {relation} cannot point at another probe")
                if (cites["project"] or project) == project and cites["trail"] == steps[0]["trail"]:
                    errors.append(f"{where}: a probe cites its own steps as step-N")
                cross.add(relation)
            elif relation == "builds_on":
                errors.append(f"{where}: builds_on points at another probe, pinned at its head")
            elif target.startswith("step-"):
                if target not in by_id:
                    errors.append(f"{where}: {relation} points at {target}, which is not an earlier step")
                    continue
                if target_kind and by_id[target]["kind"] != target_kind:
                    errors.append(f"{where}: {relation} must point at {a(target_kind)} step")
                targets.setdefault(relation, []).append(by_id[target])
            # Only the agent's own reading of events is a suggestion; what the runner
            # measured and what a person reviewed are confirmed.
            expected = "suggested" if actor == "agent" else "confirmed"
            if link["status"] != expected:
                errors.append(f"{where}: links written by {actor} are {expected}")

        if kind == "plan" and "supersedes" in targets and "triggered_by" not in targets.keys() | cross:
            errors.append(f"{where}: a plan that replaces another names the observation that triggered it")
        if kind == "run" and len(targets.get("implements", [])) != 1:
            errors.append(f"{where}: a run implements exactly one plan")
        if kind == "review" and not targets.get("reviews"):
            errors.append(f"{where}: a review names the step it reviews")
        if kind == "observation":
            for run in targets.get("observes", []):
                if run["id"] in settled:
                    errors.append(f"{where}: {run['id']} already has an observation; a run settles once")
                settled.add(run["id"])
            errors += check_observation(where, step, targets, by_id, store)
        by_id[step["id"]] = step
        previous = step
    return errors


def check_measures_source(where, step, store) -> list[str]:
    """Measures are read from a file the run wrote, never typed in: the observation names that file
    among its outputs, and with the store at hand the file is read again and must say the same."""
    if not step.get("measures"):
        return []
    source = step.get("measures_source")
    if not source:
        return [f"{where}: measures come from a file the run wrote; name it in measures_source"]
    if source not in step.get("outputs", []):
        return [f"{where}: measures_source {source['ref']} is not one of the outputs at that digest"]
    if store is None:
        return []
    path = store / source["digest"].split(":", 1)[1]
    if not path.is_file():
        return [f"{where}: {source['ref']} at that digest is not in the store"]
    if digest(path.read_bytes()) != source["digest"]:
        return [f"{where}: the stored {source['ref']} does not match its digest"]
    try:
        kept = json.loads(path.read_bytes())
    except ValueError:
        kept = None
    if kept != {m["name"]: m["value"] for m in step["measures"]}:
        return [f"{where}: the measures are not the ones in {source['ref']}"]
    return []


def check_observation(where, step, targets, by_id, store=None) -> list[str]:
    runs = targets.get("observes", [])
    if len(runs) != 1:
        return [f"{where}: an observation observes exactly one run"]
    run = runs[0]
    plans = [by_id[link["target"]] for link in run.get("links", [])
             if link["relation"] == "implements" and by_id.get(link["target"], {}).get("kind") == "plan"]
    if len(plans) != 1:
        return [f"{where}: {run['id']} implements no single plan, so there are no expectations to check"]
    plan = plans[0]
    errors, results = check_measures_source(where, step, store), []
    if any(tested["id"] != plan["id"] for tested in targets.get("tests", [])):
        errors.append(f"{where}: tests points at {plan['id']}, the plan {run['id']} implements, or nothing")
    expectations = {e["name"]: e for e in plan.get("expectations", [])}
    measures = {m["name"]: m["value"] for m in step.get("measures", [])}
    for check in step.get("checks", []):
        expectation = expectations.get(check["expectation"])
        if expectation is None:
            errors.append(f"{where}: {check['expectation']} is not an expectation of {plan['id']}")
            continue
        measured = measures.get(expectation["measure"])
        result = holds(expectation, measured, step["exit_code"])
        # A check without its measure is a claim the numbers cannot back; it counts for
        # nothing, so the outcome stays inconclusive.
        if result is None:
            errors.append(f"{where}: check {check['expectation']} has no measured {expectation['measure']}; "
                          "leave the check out and the outcome is inconclusive")
            continue
        if check.get("measured") != measured and expectation["comparison"] not in EXIT:
            errors.append(f"{where}: check {check['expectation']} does not use the measured {expectation['measure']}")
        if result != check["held"]:
            errors.append(f"{where}: check {check['expectation']} says held={check['held']}, the numbers say {result}")
        results.append(result)
    if step["exit_code"] != 0 and not any(e["comparison"] == "exit_fail" for e in expectations.values()):
        outcome = "failed"
    elif len(results) < len(expectations):
        outcome = "inconclusive"
    else:
        outcome = "as_expected" if all(results) else "contradicted"
    if step["outcome"] != outcome:
        errors.append(f"{where}: outcome is {step['outcome']}, the checks give {outcome}")
    if outcome == "failed" and "error" not in step:
        errors.append(f"{where}: a failed run records its error class")
    return errors


def observed(step: dict) -> str:
    return next(link["target"] for link in step["links"] if link["relation"] == "observes")


def facts(steps: list[dict]) -> list[str]:
    """What a checked trail shows without judging it: how many attempts each plan took and how they
    came out, runs that never settled, and runs that repeated an earlier run or its outputs. None of
    these is an error; they are what a reviewer asks about, and only the steps can say why."""
    runs = {step["id"]: step for step in steps if step["kind"] == "run"}
    settlement = {observed(step): step for step in steps if step["kind"] == "observation"}
    by_id = {step["id"]: step for step in steps}
    # An attempt is a run that measured something, or one that never settled and might have. A command
    # whose observation names no metrics file is exploration: listing files or reading data is not a
    # try at the plan's expectations, so it neither counts as an attempt nor as a repeat.
    attempts = {rid for rid in runs if rid not in settlement or settlement[rid].get("measures_source")}

    def call(run):
        return digest(canonical({"command": run["command"]["digest"], "code": run["code"], "environment": run.get("environment"),
                                 "parameters": run.get("parameters"), "inputs": run.get("inputs")}))

    def result(rid):
        kept = settlement[rid]
        return digest(canonical({"exit_code": kept["exit_code"], "outputs": sorted(o["digest"] for o in kept.get("outputs", []))}))

    def commands(rids):
        return f"{len(rids)} command{'s' * (len(rids) != 1)}"

    def failures(rids):
        failed = sum(settlement[rid]["outcome"] == "failed" for rid in rids if rid in settlement)
        return f", {failed} failed" if failed else ""

    found = []
    for plan in (step for step in steps if step["kind"] == "plan"):
        implementing = [rid for rid, run in runs.items()
                        if any(link["relation"] == "implements" and link["target"] == plan["id"] for link in run["links"])]
        if not implementing:
            found.append(f"{plan['id']}: never run")
            continue
        if all(expectation["comparison"] in EXIT for expectation in plan["expectations"]):
            found.append(f"{plan['id']}: exploration, {commands(implementing)}{failures(implementing)}")
            continue
        tried = [rid for rid in implementing if rid in attempts]
        if not tried:
            found.append(f"{plan['id']}: no measured run")
        else:
            outcomes = [settlement[rid]["outcome"] if rid in settlement else "unsettled" for rid in tried]
            distinct = len({result(rid) for rid in tried if rid in settlement})
            found.append(f"{plan['id']}: {len(tried)} run{'s' * (len(tried) > 1)}, {distinct} distinct result"
                         f"{'s' * (distinct != 1)}: " + ", ".join(f"{rid} {o}" for rid, o in zip(tried, outcomes)))
            # Re-running a plan until it holds is the garden of forking paths; the trail shows the
            # attempts that came before, which a write-up of the last one would leave out.
            if "as_expected" in outcomes and "contradicted" in outcomes[:outcomes.index("as_expected")]:
                first = outcomes.index("as_expected")
                found.append(f"{plan['id']}: first held on attempt {first + 1} of {len(tried)}, "
                             f"after {outcomes[:first].count('contradicted')} contradicted")
        if explored := [rid for rid in implementing if rid not in attempts]:
            found.append(f"{plan['id']}: {commands(explored)} wrote no metrics{failures(explored)}")
        found += eased(plan, by_id)
    for rid, run in runs.items():
        declared = {kept["ref"] for kept in run.get("inputs", [])}
        if rid in settlement and (beyond := [r["ref"] for r in settlement[rid].get("reads", []) if r["ref"] not in declared]):
            found.append(f"{rid}: read {len(beyond)} file{'s' * (len(beyond) != 1)} beyond its declared inputs: " + ", ".join(beyond[:5]))
    calls, results = {}, {}
    for rid, run in runs.items():
        if rid not in settlement:
            found.append(f"{rid}: never settled; it has no observation")
        if rid not in attempts:
            continue
        if call(run) in calls:
            found.append(f"{rid}: repeats {calls[call(run)]}, with the same command, code, environment, parameters and inputs")
        calls.setdefault(call(run), rid)
        if rid in settlement and settlement[rid].get("outputs"):
            earlier = results.setdefault(result(rid), rid)
            if earlier != rid and call(runs[earlier]) != call(run):
                found.append(f"{rid}: a different run from {earlier}, with the same outputs")
    return found


def eased(plan: dict, by_id: dict[str, dict]) -> list[str]:
    """A plan that replaced one whose expectation its trigger missed, and asks less of the same measure.
    Lowering the bar after missing it is a change a reviewer should see stated, whatever its reason."""
    found = []
    triggers = [by_id[link["target"]] for link in plan.get("links", []) if link["relation"] == "triggered_by" and link["target"] in by_id]
    for link in plan.get("links", []):
        old = by_id.get(link["target"]) if link["relation"] == "supersedes" else None
        if old is None or old["kind"] != "plan":
            continue
        for trigger in triggers:
            run = by_id[observed(trigger)]
            if not any(lk["relation"] == "implements" and lk["target"] == old["id"] for lk in run["links"]):
                continue
            missed = {check["expectation"] for check in trigger.get("checks", []) if not check["held"]}
            for before in old["expectations"]:
                if before["comparison"] in EXIT or before["name"] not in missed:
                    continue
                for after in plan["expectations"]:
                    if (after["measure"], after["comparison"]) != (before["measure"], before["comparison"]):
                        continue
                    lower, higher = after["threshold"] < before["threshold"], after["threshold"] > before["threshold"]
                    if (lower and before["comparison"] in ("ge", "gt")) or (higher and before["comparison"] in ("le", "lt")):
                        sign = COMPARISONS[before["comparison"]]
                        found.append(f"{plan['id']}: eases {before['measure']} from {sign} {format(before['threshold'], 'g')} "
                                     f"to {sign} {format(after['threshold'], 'g')} after {trigger['id']} missed it")
    return found


# column: (type, nullable). Parquet keeps the types and writes an absent value as null; CSV writes
# both as text, an absent value as empty.
NODE_COLUMNS = {"id": ("string", False), "kind": ("string", False), "graph": ("string", True),
                "tier": ("int8", True), "version": ("string", True), "at": ("timestamp", True),
                "label": ("string", True), "outcome": ("string", True)}
EDGE_COLUMNS = {"source": ("string", False), "relation": ("string", False), "target": ("string", False),
                "status": ("string", False), "digest": ("string", True), "graph": ("string", False)}


def probe_id(steps: list[dict]) -> str:
    return f"{steps[0]['project']}/probe:{steps[0]['trail']}"


def qualify(ref: str, project: str) -> str:
    """A reference as the larger graph names it: project-local kinds gain the probe's project."""
    if QUALIFIED.match(ref) or ref.split(":", 1)[0] in GLOBAL:
        return ref
    return f"{project}/{ref}"


def graph(steps: list[dict]) -> tuple[list[dict], list[dict]]:
    """Node and edge tables of a checked trail. The probe's own nodes carry its graph id and tier 3;
    the nodes it cites (actors, commits, inputs, records, other probes) keep theirs, so they carry
    neither, and every edge is asserted by the probe and points from its steps outwards."""
    project, probe = steps[0]["project"], probe_id(steps)
    nodes = {probe: {"id": probe, "kind": "probe", "graph": probe, "tier": 3,
                     "version": digest(canonical(steps[-1])), "at": steps[0]["at"], "label": steps[0]["summary"]}}
    edges = []

    def edge(source, relation, target, status="confirmed", kept=""):
        edges.append({"source": source, "relation": relation, "target": target, "status": status,
                      "digest": kept, "graph": probe})

    def cited(ref):
        ref = qualify(ref, project)
        nodes.setdefault(ref, {"id": ref, "kind": KIND.match(ref)[1]})
        return ref

    for step in steps:
        here = f"{probe}#{step['id']}"
        nodes[here] = {"id": here, "kind": step["kind"], "graph": probe, "tier": 3, "at": step["at"],
                       "label": step["summary"], "outcome": step.get("outcome", "")}
        edge(probe, "contains", here)
        if "prev" in step:
            edge(here, "follows", f"{probe}#step-{step['seq'] - 1}", kept=step["prev"])
        edge(here, "written_by", cited(step["by"]))
        for link in step.get("links", []):
            target, kept = link["target"], ""
            if cites := PROBE_REF.fullmatch(target):
                # The node is the other probe's, unversioned; the head it was cited at is on the edge.
                other = f"{cites['project'] or project}/probe:{cites['trail']}"
                target, kept = other + (f"#{cites['step']}" if cites["step"] else ""), cites["head"]
                nodes.setdefault(target, {"id": target, "kind": "probe"})
            elif target.startswith("step-"):
                target = f"{probe}#{target}"
            else:
                target = cited(target)
            edge(here, link["relation"], target, link["status"], kept)
        if step["kind"] == "run":
            edge(here, "runs_code", cited(step["code"]["ref"]), kept=step["code"].get("dirty", ""))
            for used in step.get("inputs", []):
                edge(here, "used", cited(used["ref"]), kept=used["digest"])
        if step["kind"] == "observation":
            # The run generated the outputs; its observation, the settlement, is where they are kept.
            for made in step.get("outputs", []):
                edge(f"{probe}#{observed(step)}", "generated", cited(made["ref"]), kept=made["digest"])
            # What the run was traced opening, which may differ from the inputs it declared.
            for opened in step.get("reads", []):
                edge(f"{probe}#{observed(step)}", "read", cited(opened["ref"]), kept=opened["digest"])
    return list(nodes.values()), edges


def heads(steps: list[dict]) -> dict[str, int]:
    """The head after each step: a trail cited at any of them is the same trail, grown since."""
    return {digest(canonical(step)): seq for seq, step in enumerate(steps)}


def verify(steps: list[dict], cited: str) -> list[str]:
    """Whether a checked trail is the one cited at a head. The chain fixes every step before a
    head, so a trail that never had it was rewritten, however well it checks."""
    if cited in heads(steps):
        return []
    return [f"{probe_id(steps)}: never had the head {cited}, so it changed after it was cited"]


def merge(trails: list[list[dict]]) -> tuple[list[dict], list[dict], list[str]]:
    """One graph of several checked probes: their tables unioned, each edge kept in the graph that
    asserted it, and every citation of another probe resolved against that probe's chain."""
    errors, chains = [], {}
    for steps in trails:
        if probe_id(steps) in chains:
            errors.append(f"{probe_id(steps)}: merged twice")
        chains[probe_id(steps)] = heads(steps), steps
    nodes, edges = {}, []
    for steps in trails:
        project, probe = steps[0]["project"], probe_id(steps)
        for step in steps:
            for link in step.get("links", []):
                if not (cites := PROBE_REF.fullmatch(link["target"])):
                    continue
                where, other = f"{probe}#{step['id']}", f"{cites['project'] or project}/probe:{cites['trail']}"
                if other not in chains:
                    errors.append(f"{where}: {link['relation']} cites {other}, which is not merged")
                    continue
                had, cited = chains[other]
                if cites["head"] not in had:
                    errors.append(f"{where}: cites {other} at a head it never had, so it changed after it was cited")
                    continue
                if cites["step"]:
                    seq, kind = int(cites["step"].split("-")[1]), RELATIONS[link["relation"]][1]
                    if seq > had[cites["head"]]:
                        errors.append(f"{where}: cites {cites['step']}, which {other} had not written at that head")
                    elif kind and cited[seq]["kind"] != kind:
                        errors.append(f"{where}: {link['relation']} must point at {a(kind)} step")
        part_nodes, part_edges = graph(steps)
        for node in part_nodes:
            # A probe's own node, with its graph and tier, wins over another probe's citation of it.
            if node["id"] not in nodes or node.get("graph"):
                nodes[node["id"]] = node
        edges += part_edges
    return list(nodes.values()), edges, errors


def write_table(path: Path, columns: dict[str, tuple[str, bool]], rows: list[dict]) -> None:
    if path.suffix == ".csv":
        with path.open("w", newline="") as out:
            writer = csv.DictWriter(out, list(columns), restval="")
            writer.writeheader()
            writer.writerows(rows)
        return
    import pyarrow as pa
    import pyarrow.parquet as pq

    types = {"string": pa.string(), "int8": pa.int8(), "timestamp": pa.timestamp("us", tz="UTC")}

    def value(row, name):
        kept = row.get(name)
        if kept in (None, ""):
            return None
        return datetime.fromisoformat(kept) if columns[name][0] == "timestamp" else kept

    schema = pa.schema([pa.field(name, types[kind], nullable) for name, (kind, nullable) in columns.items()])
    pq.write_table(pa.table({name: [value(row, name) for row in rows] for name in columns}, schema=schema), path)


def h(text: str) -> str:
    return digest(text.encode())


# Fixed so the example regenerates byte for byte; a real trail draws its key at random.
EXAMPLE_KEY = b"example-trail-key-not-secret"
AGENT, RUNNER = "agent:pi/glm-5.2", "runner:notebook/0.1"
PI = {"name": "pi", "version": "0.84.1", "model": "glm-5.2", "thinking": "off"}


def chain(trail: str, day: str, steps: list[dict]) -> list[dict]:
    out, previous = [], None
    for seq, step in enumerate(steps):
        record = {"version": 2, "id": f"step-{seq}", "seq": seq, "trail": trail,
                  "at": f"{day}T10:{seq:02d}:00Z", **step}
        if previous is not None:
            record["prev"] = digest(canonical(previous))
        out.append(record)
        previous = record
    return out


def metrics(values: dict) -> bytes:
    """The runner's measures file, out/metrics.json: one JSON object of measure names to numbers."""
    return json.dumps(values, sort_keys=True).encode()


def public(name: str, value: str) -> dict:
    return {"name": name, "digest": h(value), "value": value}


def run(plan: str, command: str, parameters: list[dict], code: str, data: str = "file:data/telco.csv") -> dict:
    """The runner's intent, written before the command executes."""
    return {"kind": "run", "by": RUNNER, "hook": "pi:tool_call", "summary": command,
            "command": {"shown": command, "digest": h(command)}, "code": {"ref": code}, "environment": h("uv.lock"),
            "parameters": parameters, "inputs": [{"ref": data, "digest": h("telco.csv v1")}],
            "links": [{"relation": "implements", "target": plan, "status": "confirmed"}]}


def settle(ran: str, plan: str, summary: str, values: dict, held: dict, duration_ms: int) -> dict:
    """The runner's observation of a finished run: its exit, its outputs, and the measures read back
    from the metrics file it wrote, checked against the plan's expectations."""
    source = {"ref": "file:out/metrics.json", "digest": digest(metrics(values))}
    checks = [{"expectation": "runs", "held": True}]
    checks += [{"expectation": name, "measured": values[measure], "held": ok} for name, (measure, ok) in held.items()]
    return {"kind": "observation", "by": RUNNER, "hook": "pi:tool_result", "summary": summary,
            "exit_code": 0, "duration_ms": duration_ms, "outputs": [source], "measures_source": source,
            "measures": [{"name": name, "value": value} for name, value in values.items()], "checks": checks,
            "outcome": "as_expected" if all(ok for _, ok in held.values()) else "contradicted",
            "links": [{"relation": "observes", "target": ran, "status": "confirmed"},
                      {"relation": "tests", "target": plan, "status": "confirmed"}]}


def examples() -> list[list[dict]]:
    """Three probes in two projects: churn's step 4 changes approach; retention builds on churn's
    result, reading the same data from another path; tuning re-runs one plan until it holds."""
    churn = example()
    cited = f"churn/probe:{churn[0]['trail']}@{digest(canonical(churn[-1]))}"
    command = "python features.py --class-weight balanced --features tenure_band --seed 7"
    retention = chain("churn-features-2026-11-12", "2026-11-12", [
        {"kind": "task", "by": "human:antonio", "summary": "Test tenure bands on the reweighted churn model",
         "question": "Do tenure-band features lift the reweighted churn model to an AUC of at least 0.80?",
         "project": "retention", "agent": PI, "declared_measures": ["auc"],
         "public_parameters": ["seed", "class_weight", "features"],
         "links": [{"relation": "builds_on", "target": cited, "status": "confirmed"}]},
        {"kind": "plan", "by": AGENT, "hook": "pi:propose_plan", "summary": "Add tenure bands to the reweighted model",
         "reasoning": "Churn's reweighted model met its floor at 0.78. Tenure is the usual strongest churn signal, "
                      "so banding it should add the lift to 0.80.",
         "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"},
                          {"name": "auc-target", "measure": "auc", "comparison": "ge", "threshold": 0.80}],
         "links": [{"relation": "triggered_by", "target": f"{cited}#step-6", "status": "suggested"}]},
        run("step-1", command, [public("seed", "7"), public("class_weight", "balanced"), public("features", "tenure_band")],
            "commit:retention@9b1e4d7", "file:inputs/telco.csv"),
        settle("step-2", "step-1", "AUC 0.77, short of 0.80", {"auc": 0.77}, {"auc-target": ("auc", False)}, 5020),
        {"kind": "note", "by": "human:antonio", "summary": "Tenure bands add nothing over class weights",
         "text": "AUC fell from churn's 0.78 to 0.77, so the reweighted model stays the best one.",
         "links": [{"relation": "about", "target": "step-3", "status": "confirmed"}]},
    ])
    return [churn, retention, tuning(cited)]


def example() -> list[dict]:
    baseline = "python fit.py --model logistic --seed 7"
    reweighted = "python fit.py --model logistic --class-weight balanced --seed 7"
    steps = [
        {"kind": "task", "by": "human:antonio", "summary": "Predict 90-day churn from the public telco dataset",
         "question": "Can 90-day churn be predicted from the first month of usage with AUC of at least 0.75?",
         "project": "churn", "agent": PI, "declared_measures": ["auc", "positive_rate"],
         "public_parameters": ["seed", "model", "class_weight"]},
        {"kind": "plan", "by": AGENT, "hook": "pi:propose_plan", "summary": "Baseline: logistic regression on raw features",
         "reasoning": "Start with the simplest model so later gains are measured against it.",
         "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"},
                          {"name": "auc-floor", "measure": "auc", "comparison": "ge", "threshold": 0.75}]},
        run("step-1", baseline, [public("seed", "7"), public("model", "logistic"),
                                 {"name": "api_key", "digest": keyed(EXAMPLE_KEY, b"not-stored")}], "commit:notebook@3f9c2a1"),
        settle("step-2", "step-1", "AUC 0.58, below the 0.75 floor", {"auc": 0.58, "positive_rate": 0.07},
               {"auc-floor": ("auc", False)}, 4120),
        {"kind": "plan", "by": AGENT, "hook": "pi:propose_plan", "summary": "Reweight classes: only 7% of rows churn",
         "reasoning": "The positive rate is 0.07, so an unweighted fit mostly predicts no churn. Weighting classes "
                      "tests whether the gap is imbalance rather than missing signal.",
         "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"},
                          {"name": "auc-floor", "measure": "auc", "comparison": "ge", "threshold": 0.75}],
         "links": [{"relation": "supersedes", "target": "step-1", "status": "suggested"},
                   {"relation": "triggered_by", "target": "step-3", "status": "suggested"}]},
        run("step-4", reweighted, [public("seed", "7"), public("class_weight", "balanced")], "commit:notebook@3f9c2a1"),
        settle("step-5", "step-4", "AUC 0.78, floor met", {"auc": 0.78}, {"auc-floor": ("auc", True)}, 4310),
        {"kind": "review", "by": "human:antonio", "summary": "Accept the change of approach at step 4",
         "verdict": "confirms", "text": "The imbalance reading is right: step 3 measured a 7% positive rate.",
         "links": [{"relation": "reviews", "target": "step-4", "status": "confirmed"}]},
    ]
    return chain("churn-model-2026-11-11", "2026-11-11", steps)


def tuning(cited: str) -> list[dict]:
    """The garden of forking paths: one plan re-run on new seeds until it holds, one exact repeat,
    and a last run stopped by the budget before it settled. Every step passes the checker; what the
    trail shows instead is in `facts`, and the review reads it."""
    def gbm(seed):
        return run("step-1", f"python fit.py --model gbm --class-weight balanced --seed {seed}",
                   [public("seed", seed), public("model", "gbm"), public("class_weight", "balanced")], "commit:notebook@5d2e8b0")

    def auc(ran, value, duration_ms):
        held = value >= 0.80
        return settle(ran, "step-1", f"AUC {value:.2f}, {'target met' if held else 'short of 0.80'}", {"auc": value},
                      {"auc-target": ("auc", held)}, duration_ms)

    return chain("churn-tuning-2026-11-13", "2026-11-13", [
        {"kind": "task", "by": "human:antonio", "summary": "Try gradient boosting on the reweighted churn data",
         "question": "Does gradient boosting reach an AUC of at least 0.80 on the reweighted churn data?",
         "project": "churn", "agent": PI, "declared_measures": ["auc"], "public_parameters": ["seed", "model", "class_weight"],
         "links": [{"relation": "builds_on", "target": cited, "status": "confirmed"}]},
        {"kind": "plan", "by": AGENT, "hook": "pi:propose_plan", "summary": "Gradient boosting with balanced class weights",
         "reasoning": "Class weights fixed the imbalance for logistic regression; boosting should add the non-linear "
                      "lift to 0.80.",
         "expectations": [{"name": "runs", "measure": "exit", "comparison": "exit_ok"},
                          {"name": "auc-target", "measure": "auc", "comparison": "ge", "threshold": 0.80}]},
        gbm("7"), auc("step-2", 0.76, 9800),
        gbm("11"), auc("step-4", 0.78, 9650),
        gbm("23"), auc("step-6", 0.81, 9720),
        gbm("23"), auc("step-8", 0.81, 9700),
        gbm("31"),
        {"kind": "note", "by": RUNNER, "summary": "Stopped step-10 at the task's budget of five runs",
         "text": "The run budget was reached while step-10 was running, so it was stopped before it settled.",
         "links": [{"relation": "about", "target": "step-10", "status": "confirmed"}]},
        {"kind": "review", "by": "human:antonio", "summary": "The 0.80 target held on one seed of three",
         "verdict": "disputes", "text": "Seeds 7 and 11 contradicted the plan; seed 23 met it and step-8 only repeated "
                                        "step-6. Report AUC 0.76 to 0.81 across seeds, not 0.81.",
         "links": [{"relation": "reviews", "target": "step-1", "status": "confirmed"}]},
    ])


def respond(steps: list[dict], target: str, by: str, text: str, verdict: str | None = None) -> dict:
    """A person's review of a step (with a verdict) or note on it, as the next step of the trail. Its time
    is now, or the last step's when that is later: `at` never goes backwards, even past a clock that lags."""
    now, last = datetime.now(UTC).replace(microsecond=0), steps[-1]
    at = last["at"] if datetime.fromisoformat(last["at"]) > now else now.strftime("%Y-%m-%dT%H:%M:%SZ")
    step = {"version": 2, "id": f"step-{len(steps)}", "seq": len(steps), "trail": steps[0]["trail"], "at": at,
            "kind": "review" if verdict else "note", "by": f"human:{by}"}
    if verdict:
        step |= {"summary": f"{verdict.capitalize()} {target}", "verdict": verdict}
    else:
        step["summary"] = f"Note on {target}"
    relation = "reviews" if verdict else "about"
    return step | {"text": text, "links": [{"relation": relation, "target": target, "status": "confirmed"}],
                   "prev": digest(canonical(last))}


def write_graph(directory: Path, nodes: list[dict], edges: list[dict], suffix: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    write_table(directory / f"nodes{suffix}", NODE_COLUMNS, nodes)
    write_table(directory / f"edges{suffix}", EDGE_COLUMNS, edges)
    print(f"{len(nodes)} nodes, {len(edges)} edges in {directory}")


OPTIONS = ("--store", "--code", "--out", "--verdict", "--text", "--by")


def usage(message: str) -> None:
    """One line on standard error and exit code 2: the command line was wrong, the trail was not read."""
    print(message, file=sys.stderr)
    sys.exit(2)


def option(args: list[str], name: str) -> str | None:
    """Takes `name VALUE` out of the arguments and returns VALUE, or None when it is absent. An option
    at the end, or followed by another option, has no value."""
    if name not in args:
        return None
    at = args.index(name)
    if at + 1 == len(args) or args[at + 1] in OPTIONS:
        usage(f"trail.py: {name} needs a value")
    value = args[at + 1]
    del args[at:at + 2]
    return value


if __name__ == "__main__":
    suffix = ".csv" if "--csv" in sys.argv else ".parquet"
    args = [arg for arg in sys.argv[1:] if arg != "--csv"]
    store = Path(kept) if (kept := option(args, "--store")) else None
    code, out = option(args, "--code"), option(args, "--out")
    verdict, text, by = option(args, "--verdict"), option(args, "--text"), option(args, "--by")
    if len(args) < 2:
        usage("usage: trail.py COMMAND DIR [STEP or HEAD] [--store DIR] [--code REPO] [--out FILE] [--csv]")
    command, directory = args[0], Path(args[1])
    if command == "verify" and len(args) < 3:
        usage("usage: trail.py verify DIR HEAD")
    if command in ("review", "note") and (len(args) < 3 or text is None or by is None or (command == "review") != (verdict is not None)):
        sys.exit(f"usage: trail.py {command} DIR STEP" + " --verdict confirms|disputes" * (command == "review") + " --text TEXT --by NAME")
    if command == "examples":
        store = directory / "store"
        store.mkdir(parents=True, exist_ok=True)
        for trail in examples():
            (directory / trail[0]["trail"] / "steps").mkdir(parents=True, exist_ok=True)
            for step in trail:
                (directory / trail[0]["trail"] / "steps" / f"{step['id']}.json").write_text(json.dumps(step, indent=2) + "\n")
                if source := step.get("measures_source"):
                    (store / source["digest"].split(":", 1)[1]).write_bytes(metrics({m["name"]: m["value"] for m in step["measures"]}))
        trails = sorted(path for path in directory.iterdir() if (path / "steps").is_dir())
    else:
        trails = [Path(path) for path in args[2:]] if command == "merge" else [directory]
    problems, loaded = [], []
    for path in trails:
        steps = load(path)
        found = check(steps, store)
        print(f"{path}: " + ("; ".join(found) or f"{len(steps)} steps, no problems"))
        problems += found
        loaded.append(steps)
        if command == "graph" and not found:
            write_graph(path / "graph", *graph(steps), suffix)
        if command == "facts" and not found:
            print("\n".join(f"  {fact}" for fact in facts(steps)))
        if command == "head" and not found:
            print(digest(canonical(steps[-1])))
        if command == "verify" and not found:
            found = verify(steps, args[2])
            problems += found
            print("\n".join(found) or f"had that head after step-{heads(steps)[args[2]]} of {len(steps) - 1}")
        if command == "why" and not found:
            import view

            try:
                print("\n".join(view.why(steps, args[2] if len(args) > 2 else None)))
            except LookupError as error:
                print(error.args[0])
                problems.append(error.args[0])
        if command == "view" and not found:
            import view

            written = Path(out) if out else path / "view.html"
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text(view.page(steps, Path(code) if code else None), encoding="utf-8")
            print(f"wrote {written}")
        if command in ("review", "note") and not found:
            # The new step is checked with the whole trail before anything is written, so a review of a
            # step the trail lacks, or one the schema refuses, leaves the trail as it was.
            step = respond(steps, args[2], by, text, verdict)
            found = check([*steps, step], store)
            problems += found
            if found:
                print("; ".join(found))
            else:
                (path / "steps" / f"{step['id']}.json").write_text(json.dumps(step, indent=2) + "\n")
                print(f"wrote {step['id']}: {step['summary']}")
    if command == "merge" and not problems:
        nodes, edges, problems = merge(loaded)
        print("\n".join(problems)) if problems else write_graph(directory, nodes, edges, suffix)
    sys.exit(1 if problems else 0)

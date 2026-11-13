"""What a reviewer reads of a checked trail: `why`, the answer to "why did the plan change?", and the page.

Nothing here infers. Every sentence is a fixed template filled from steps and their links, and an
agent's text is shown whole and unchanged, so the view can state no cause that a link does not carry.
"""

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

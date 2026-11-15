"""The tamper sequence: what each defence of a trail catches, shown on a copy of a real one.

Usage: tamper.py TRAIL --store STORE --cited HEAD --step STEP --measure NAME --value NUMBER

One measured value of one observation is rewritten in five stages, each more careful than the
last, and after each the copy is read back and given to `trail.check` or `trail.verify`. What
they return is printed as it is. The chain catches a careless edit, the stored metrics catch a
rewritten number, and only a head cited outside the trail catches a complete rewrite.

TRAIL and STORE are never written to: the step files and the store are copied to a temporary
directory, shown as COPY. Exits 0 when every stage came out as expected, 1 when one did not
and 2 when the change asked for cannot be made.
"""

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import trail
import view


class Refused(Exception):
    """The change asked for is not one this sequence can show."""


@dataclass
class Result:
    command: str  # as a reader would type it, with the copy shown as COPY
    found: list[str]  # what trail.check or trail.verify returned
    expected: str
    ok: bool


@dataclass
class Stage:
    done: str
    results: list[Result]


def write(directory: Path, steps: list[dict]) -> None:
    (directory / "steps").mkdir(parents=True, exist_ok=True)
    for step in steps:
        (directory / "steps" / f"{step['id']}.json").write_text(json.dumps(step, indent=2) + "\n")


def rechain(steps: list[dict], start: int) -> None:
    for seq in range(start, len(steps)):
        steps[seq]["prev"] = trail.digest(trail.canonical(steps[seq - 1]))


def plan_of(steps: list[dict], observation: dict) -> dict:
    by_id = {step["id"]: step for step in steps}
    run = by_id[trail.observed(observation)]
    return next(by_id[link["target"]] for link in run["links"] if link["relation"] == "implements")


def rewrite(steps: list[dict], step_id: str, measure: str, value: float) -> float:
    """Puts `value` where the step states the measure: its measures, the checks that used it and its
    summary. Returns the value it replaced.

    A value that turns a check over is refused. The outcome would change with it, and then the plan
    that answered the outcome would have to be rewritten too: a larger forgery than this one shows."""
    step = next((step for step in steps if step["id"] == step_id), None)
    if step is None or step["kind"] != "observation":
        raise Refused(f"{step_id} is not an observation of this trail")
    if step["seq"] == len(steps) - 1:
        raise Refused(f"{step_id} is the last step; choose one with a step after it, whose prev the edit breaks")
    kept = next((m for m in step.get("measures", []) if m["name"] == measure), None)
    if kept is None:
        raise Refused(f"{step_id} has no measure {measure}")
    expectations = {x["name"]: x for x in plan_of(steps, step)["expectations"]}
    used = [check for check in step["checks"] if expectations[check["expectation"]].get("measure") == measure]
    for check in used:
        if trail.holds(expectations[check["expectation"]], value, step["exit_code"]) != check["held"]:
            raise Refused(
                f"{measure} {view.number(value)} changes whether {check['expectation']} held, so {step_id} "
                f"would no longer be {view.OUTCOMES[step['outcome']]}; choose a value that keeps its outcome"
            )
    old, kept["value"] = kept["value"], value
    for check in used:
        check["measured"] = value
    step["summary"] = step["summary"].replace(f"{measure} {view.number(old)}", f"{measure} {view.number(value)}")
    return old


def forge(steps: list[dict], step_id: str, store: Path) -> None:
    """Writes the metrics file the rewritten step would have had, and makes the step cite it."""
    step = next(step for step in steps if step["id"] == step_id)
    content = (json.dumps({m["name"]: m["value"] for m in step["measures"]}, indent=2) + "\n").encode()
    old, new = step["measures_source"]["digest"], trail.digest(content)
    (store / new.split(":", 1)[1]).write_bytes(content)
    for cited in [step["measures_source"], *step["outputs"]]:
        if cited["digest"] == old:
            cited["digest"] = new


def sequence(source: Path, store: Path, cited: str, step_id: str, measure: str, value: float, work: Path) -> list[Stage]:
    """The five stages on a copy under `work`. Every result is what the checker said of the files as
    they were read back, so a stage cannot pass on what this module believes it wrote."""
    copy, kept = work / "trail", work / "store"
    shutil.copytree(source / "steps", copy / "steps")
    shutil.copytree(store, kept)
    steps = trail.load(copy)
    at = next((step["seq"] for step in steps if step["id"] == step_id), None)
    after = f"step-{at + 1}" if at is not None else None

    def check(with_store: bool, expected: str, ok) -> Result:
        found = trail.check(trail.load(copy), kept if with_store else None)
        return Result("check COPY" + " --store COPY-STORE" * with_store, found, expected, ok(found))

    def verify(expected: str, ok) -> Result:
        found = trail.verify(trail.load(copy), cited)
        return Result("verify COPY HEAD", found, expected, ok(found))

    def passes(found: list[str]) -> bool:
        return found == []

    def fails_at(where: str):
        return lambda found: bool(found) and all(error.startswith(f"{where}: ") for error in found)

    stages = [Stage("Nothing is changed.", [check(True, "passes", passes), verify("passes", passes)])]

    old = rewrite(steps, step_id, measure, value)
    write(copy, steps)
    said = f"{measure} {view.number(old)} becomes {view.number(value)}"
    stages.append(
        Stage(
            f"{step_id} is rewritten: {said} in its measures, in the check that used it and in its summary.",
            [check(False, f"fails at {after}, whose prev no longer matches", fails_at(after))],
        )
    )

    rechain(steps, at + 1)
    write(copy, steps)
    stages.append(
        Stage(
            f"Every prev from {after} on is recomputed.",
            [
                check(False, "passes", passes),
                check(True, f"fails at {step_id}, whose measures are not the ones in the stored file", fails_at(step_id)),
            ],
        )
    )

    forge(steps, step_id, kept)
    rechain(steps, at + 1)
    write(copy, steps)
    stages.append(
        Stage(
            f"A metrics file with the new value is put in the store, {step_id} cites its digest, and the chain is recomputed.",
            [check(True, "passes", passes)],
        )
    )

    stages.append(Stage("Nothing more is changed.", [verify("fails, since the trail never had the cited head", bool)]))
    return stages


def report(stages: list[Stage]) -> list[str]:
    lines = []
    for number, stage in enumerate(stages, 1):
        lines += ["", f"Stage {number}. {stage.done}"]
        for result in stage.results:
            lines.append(f"  trail.py {result.command}")
            lines += [f"    {line}" for line in result.found or ["no problems"]]
            lines.append(f"    {'as expected' if result.ok else 'NOT AS EXPECTED'}: {result.expected}")
    wrong = sum(not result.ok for stage in stages for result in stage.results)
    return [
        *lines,
        "",
        "Every stage came out as expected." if not wrong else f"{wrong} result{'s' * (wrong != 1)} did not come out as expected.",
    ]


def main(argv: list[str]) -> int:
    usage = "usage: tamper.py TRAIL --store STORE --cited HEAD --step STEP --measure NAME --value NUMBER"
    names = ("--store", "--cited", "--step", "--measure", "--value")
    args = argv[1:]
    # 2 * 5 option words and the trail; an option at the end has no value for trail.option to take.
    if len(args) != 11 or args[-1] in names or any(args.count(name) != 1 for name in names):
        print(usage, file=sys.stderr)
        return 2
    named = {name[2:]: trail.option(args, name) for name in names}
    try:
        value = float(named["value"])
    except ValueError:
        print(usage, file=sys.stderr)
        return 2
    source = Path(args[0])
    with tempfile.TemporaryDirectory() as work:
        try:
            stages = sequence(source, Path(named["store"]), named["cited"], named["step"], named["measure"], value, Path(work))
        except Refused as refused:
            print(f"tamper.py: {refused.args[0]}", file=sys.stderr)
            return 2
    print(f"The tamper sequence on {source}, {len(trail.load(source))} steps. Nothing is written there: the steps are copied to COPY")
    print("and the store to COPY-STORE, both in a temporary directory.")
    print(f"HEAD, the head cited before any change: {named['cited']}")
    print("\n".join(report(stages)))
    return 0 if all(result.ok for stage in stages for result in stage.results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

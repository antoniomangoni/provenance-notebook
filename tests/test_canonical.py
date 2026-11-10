"""The capture side (TypeScript) and the checker (Python) hash the same bytes for every step.

Capture writes a step file with JSON.stringify and chains the next step from its own canonical
form; the checker parses that file and canonicalises it again. If the two forms differ, `prev`
breaks on a trail nobody edited.
"""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

import trail

CLI = Path(__file__).parent / "canonical_cli.mjs"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js 24")


def both(values: list[str]) -> list[tuple[str, str, str]]:
    """For each JSON text: what JavaScript writes to the file, its canonical form and its digest."""
    result = subprocess.run(["node", str(CLI)], input="\n".join(values), capture_output=True, text=True, check=True)
    # Not splitlines(): it also breaks on U+2028, which a string value may hold.
    return [tuple(line.split("\t")) for line in result.stdout.split("\n") if line]


def recanonical(written: str) -> str:
    return trail.canonical(json.loads(written)).decode()


def test_steps_hash_the_same_on_both_sides():
    steps = [step for example in trail.examples() for step in example]
    for step, (written, canon, kept) in zip(steps, both([json.dumps(step, ensure_ascii=False) for step in steps]), strict=True):
        assert canon == trail.canonical(step).decode()
        assert kept == trail.digest(trail.canonical(step))
        assert recanonical(written) == canon


def test_numbers_and_strings_round_trip():
    numbers = [
        "1.0",
        "100.0",
        "-0.0",
        "0.81",
        "0.30000000000000004",
        "1e16",
        "1e21",
        "123456789012345678901",
        "0.001",
        "0.0001",
        "0.00012",
        "0.00001",
        "1.5e-5",
        "2.5e-7",
        "1e-7",
        "1e-300",
        "5e-324",
        "9007199254740993",
        "5",
    ]
    strings = ['"café \\" \\\\ \\n \\u0007"', '"\U0001f600"', '"\\u2028 \\u00a0"']
    cases = [f'{{"v":{value}}}' for value in numbers + strings] + ['{"z":3,"a":1,"m":[1,{"b":null,"a":true}]}']
    for case, (written, canon, _) in zip(cases, both(cases), strict=True):
        assert recanonical(written) == canon, case


def test_random_doubles_round_trip():
    random.seed(7)
    values = [random.choice([-1, 1]) * random.random() * 10 ** random.randint(-320, 300) for _ in range(100_000)]
    values += [1e-4, 9.999e-5, 1e-5, 1e16, 1e17, 1e21, 1e22]
    differ = [written for written, canon, _ in both([json.dumps(value) for value in values]) if recanonical(written) != canon]
    assert differ == []

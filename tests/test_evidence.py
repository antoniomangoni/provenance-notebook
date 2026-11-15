"""The evidence on the live trail: the tamper sequence, where each stage is what the checker itself
returned, and the reader check, whose key is read off the step files. Nothing here calls a model."""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import tamper
import trail

ROOT = Path(__file__).parent.parent
LIVE = ROOT / "live" / "madelon-2026-11-15-1"
STORE = ROOT / "live" / "store"
EVIDENCE = ROOT / "evidence" / "madelon-2026-11-15-1"
HEAD = "sha256:828598696a283a226b12de4af3abdee6e13a173a85093229061e1a51feee8933"
CHANGE = ("step-8", "holdout_auc", 0.7039)


def tree(*directories: Path) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in directories
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_the_cited_head_is_the_live_trail_s():
    assert trail.digest(trail.canonical(trail.load(LIVE)[-1])) == HEAD


def test_each_tamper_stage_is_caught_where_the_sequence_says(tmp_path):
    before = tree(LIVE, STORE)
    stages = tamper.sequence(LIVE, STORE, HEAD, *CHANGE, tmp_path)
    (untouched, verified), (edited,), (rechained, against_store), (forged,), (cited,) = (stage.results for stage in stages)
    assert all(result.ok for stage in stages for result in stage.results)

    assert untouched.found == [] and verified.found == []
    assert edited.found == ["step-9: prev does not match step-8; an earlier step was changed"]
    assert rechained.found == []
    assert against_store.found == ["step-8: the measures are not the ones in file:out/metrics.json"]
    assert forged.found == []
    assert len(cited.found) == 1 and f"never had the head {HEAD}" in cited.found[0]

    # The results are of the copy as it stands on disk: it checks against its own store, holds the new
    # value where the old one was, and no longer has the head.
    copy, store = trail.load(tmp_path / "trail"), tmp_path / "store"
    assert trail.check(copy, store) == [] and trail.verify(copy, HEAD) != []
    assert copy[8]["summary"] == "contradicted: holdout_auc 0.7039, expected >= 0.71" and copy[8]["outcome"] == "contradicted"
    assert {m["name"]: m["value"] for m in copy[8]["measures"]}["holdout_auc"] == 0.7039
    assert trail.check(copy, STORE) != [], "the forged metrics file is in the copy's store only"
    assert tree(LIVE, STORE) == before


@pytest.mark.parametrize(
    ("change", "said"),
    [
        (("step-8", "holdout_auc", 0.72), "changes whether holds-criterion held"),
        (("step-8", "auc", 0.5), "has no measure auc"),
        (("step-7", "holdout_auc", 0.5), "is not an observation"),
        (("step-25", "holdout_auc", 0.5), "is the last step"),
    ],
)
def test_tamper_refuses_a_change_it_cannot_show(change, said, tmp_path):
    with pytest.raises(tamper.Refused, match=said):
        tamper.sequence(LIVE, STORE, HEAD, *change, tmp_path)


def test_a_stage_that_comes_out_otherwise_is_reported_and_fails(tmp_path):
    """Cited at a head the trail never had, stage 1 fails and the command exits 1."""
    stages = tamper.sequence(LIVE, STORE, "sha256:" + "0" * 64, *CHANGE, tmp_path)
    assert [result.ok for result in stages[0].results] == [True, False]
    assert "NOT AS EXPECTED: passes" in "\n".join(tamper.report(stages))


def test_the_committed_tamper_output_is_what_the_command_prints():
    before = tree(LIVE, STORE)
    done = subprocess.run(
        [sys.executable, "tamper.py", "live/madelon-2026-11-15-1", "--store", "live/store", "--cited", HEAD,
         "--step", CHANGE[0], "--measure", CHANGE[1], "--value", str(CHANGE[2])],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )  # fmt: skip
    assert done.returncode == 0 and done.stderr == ""
    assert done.stdout == (EVIDENCE / "tamper.txt").read_text()
    assert tree(LIVE, STORE) == before


def test_tamper_exits_2_on_a_refused_value_and_on_a_wrong_command_line():
    base = [
        sys.executable,
        "tamper.py",
        "live/madelon-2026-11-15-1",
        "--store",
        "live/store",
        "--cited",
        HEAD,
        "--step",
        "step-8",
        "--measure",
        "holdout_auc",
    ]
    for value in (["--value", "0.72"], ["--value"], ["--value", "high"], []):
        done = subprocess.run([*base, *value], cwd=ROOT, check=False, capture_output=True, text=True)
        assert done.returncode == 2 and done.stdout == "" and len(done.stderr.splitlines()) == 1

"""retrace.py on a trail a scripted capture session makes here: the replay finds what each run read,
reproduces what it measured, and leaves the trail as it was."""

import shutil

import pytest
from test_capture import FLOOR, PI, bash, live, plan

import retrace
import trail

pytestmark = [
    pytest.mark.skipif(shutil.which("strace") is None, reason="needs strace"),
    pytest.mark.skipif(shutil.which("node") is None or not PI.exists(), reason="needs Node.js 24 and capture's node_modules"),
]


def test_a_replay_reproduces_each_run_and_finds_what_it_read(tmp_path):
    session = live(tmp_path, [[plan(FLOOR)], [bash("python3 fit.py --auc 0.8")], [bash("cat data/telco.csv > /dev/null")], [bash("exit 3")]],
                   NOTEBOOK_TRACE="0")
    before = {path: path.read_bytes() for path in session.directory.rglob("*") if path.is_file()}
    result = retrace.retrace(session.directory)
    fit, cat, failing = result["runs"]
    assert (fit["exit"], fit["metrics"]["same"]) == ({"recorded": 0, "replayed": 0}, True)
    assert "file:fit.py" in [r["ref"] for r in fit["reads"]]
    assert cat["reads"] == [{"ref": "file:data/telco.csv", "digest": session.steps[2]["inputs"][0]["digest"]}]
    assert cat["metrics"]["same"] is None and failing["exit"] == {"recorded": 3, "replayed": 3}
    assert result["head"] == trail.digest(trail.canonical(session.steps[-1]))
    assert {path: path.read_bytes() for path in session.directory.rglob("*") if path.is_file()} == before

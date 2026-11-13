"""The demo task's guarantees: the inherited analysis misses its floor on held-out data by a clear
distance, the corrected one agrees with the held-out data, and nothing the agent reads says why.

The analyses run in `demo/workspace` with its own locked environment, so these tests need `uv`.
`DEMO_FULL=1` runs seeds 0 to 4; `DEMO_ARCHIVE=madelon.zip` also rebuilds the data files."""

import functools
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DEMO = ROOT / "demo"
WORKSPACE = DEMO / "workspace"
DATA = ("data/pilot.csv", "data/heldout.csv")

# The acceptance numbers of the spec. The floor is this file's own constant: the task must agree with it.
HEADLINE = 0.76  # the inherited cv_auc at seed 0, to two decimals
FLOOR = 0.71  # the headline less 0.05, fixed before any agent runs the task
HELDOUT = 2200
SEEDS = range(5) if os.environ.get("DEMO_FULL") == "1" else [0]
FORBIDDEN = ("leak", "pitfall", "bias", "optimistic")
TASK_FIELDS = {"summary", "question", "project", "declared_measures", "public_parameters", "inputs", "by"}


def task() -> dict:
    return json.loads((DEMO / "task.json").read_text())


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def make_data():
    spec = importlib.util.spec_from_file_location("make_data", DEMO / "make_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def uv() -> dict:
    """The environment for `uv` in the workspace, synced once from its lock file."""
    if not shutil.which("uv"):
        pytest.skip("needs uv")
    env = {name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}
    subprocess.run(["uv", "sync", "--locked", "--quiet"], cwd=WORKSPACE, env=env, check=True)
    return env


@functools.cache
def measured(script: str, *flags: str) -> tuple[dict, float]:
    """One run's metrics and how long it took. A run is made once and shared by the tests that read it."""
    env = {name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}
    metrics = WORKSPACE / "out" / "metrics.json"
    metrics.unlink(missing_ok=True)
    start = time.monotonic()
    done = subprocess.run(
        ["uv", "run", "--locked", "--directory", WORKSPACE, "python", script, *flags], env=env, capture_output=True, text=True, check=False
    )
    seconds = time.monotonic() - start
    assert done.returncode == 0, done.stderr
    return json.loads(metrics.read_text()), seconds


def inherited(seed: int) -> dict:
    return measured("analysis.py", "--seed", str(seed))[0]


def corrected(seed: int) -> dict:
    return measured("../corrected.py", "--seed", str(seed))[0]


def test_task_file_has_exactly_the_shared_fields():
    assert set(task()) == TASK_FIELDS
    assert task()["declared_measures"] == ["cv_auc", "holdout_auc", "gap"]
    assert task()["public_parameters"] == ["seed", "k", "folds"]
    assert task()["by"] == "human:antonio"


def test_task_names_fit_the_step_schema():
    schema = json.loads((ROOT / "step.schema.json").read_text())["properties"]
    for field in ("declared_measures", "public_parameters"):
        for name in task()[field]:
            assert re.fullmatch(schema[field]["items"]["pattern"], name), name
    assert re.fullmatch(schema["project"]["pattern"], task()["project"])
    assert re.fullmatch(schema["by"]["pattern"], task()["by"])
    assert len(task()["summary"]) <= schema["summary"]["maxLength"]
    assert len(task()["question"]) <= schema["question"]["maxLength"]


def test_task_inputs_are_the_two_data_files_and_exist():
    assert tuple(task()["inputs"]) == DATA
    assert all((WORKSPACE / name).is_file() for name in DATA)


def test_data_files_have_the_recorded_digests():
    readme = (DEMO / "README.md").read_text()
    for name in DATA:
        recorded = re.search(rf"`{re.escape(name)}`.*?`(sha256:[0-9a-f]{{64}})`", readme)
        assert recorded, f"demo/README.md records no digest for {name}"
        assert digest(WORKSPACE / name) == recorded.group(1) == make_data().DIGESTS[Path(name).name]
    assert sum(1 for _ in (WORKSPACE / "data/heldout.csv").open()) - 1 == HELDOUT
    assert sum((WORKSPACE / name).stat().st_size for name in DATA) <= 10_000_000


def test_make_data_refuses_a_source_that_does_not_rebuild_the_recorded_files(tmp_path, capsys):
    before = {name: digest(WORKSPACE / name) for name in DATA}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as source:
        row = " ".join(["1"] * 500) + " \n"
        for values, labels in make_data().PARTS:
            source.writestr(values, row * 2)
            source.writestr(labels, "1\n-1\n")
    (tmp_path / "other.zip").write_bytes(archive.getvalue())
    assert make_data().main(["make_data.py", str(tmp_path / "other.zip")]) == 1
    assert "nothing was written" in capsys.readouterr().err
    assert {name: digest(WORKSPACE / name) for name in DATA} == before


@pytest.mark.skipif(not os.environ.get("DEMO_ARCHIVE"), reason="set DEMO_ARCHIVE to a copy of madelon.zip")
def test_make_data_rebuilds_the_committed_files():
    files = make_data().build(Path(os.environ["DEMO_ARCHIVE"]).read_bytes())
    assert {f"data/{name}": content for name, content in files.items()} == {name: (WORKSPACE / name).read_bytes() for name in DATA}


def test_question_and_prompt_state_the_headline_the_floor_and_the_heldout_count():
    assert round(HEADLINE - 0.05, 2) == FLOOR
    for text in (task()["question"], (DEMO / "prompt.md").read_text()):
        assert f"AUC of {HEADLINE}" in text
        assert f"at least {FLOOR}" in text
        assert f"{HELDOUT} " in text


def test_nothing_the_agent_reads_names_what_is_wrong():
    read = [
        DEMO / "prompt.md",
        *(
            path
            for path in sorted(WORKSPACE.rglob("*"))
            if path.is_file() and not {".venv", "out"} & set(path.relative_to(WORKSPACE).parts)
        ),
    ]
    assert {path.name for path in read} >= {
        "prompt.md",
        "analysis.py",
        "README.md",
        "pyproject.toml",
        "uv.lock",
        "pilot.csv",
        "heldout.csv",
    }
    for path in read:
        text = path.read_text().lower()
        assert not [word for word in FORBIDDEN if word in text], path


def test_headline_is_the_inherited_estimate_at_seed_0(uv):
    assert round(inherited(0)["cv_auc"], 2) == HEADLINE


@pytest.mark.parametrize("seed", SEEDS)
def test_inherited_analysis_misses_the_floor_by_a_clear_distance(uv, seed):
    metrics = inherited(seed)
    assert set(metrics) == set(task()["declared_measures"])
    assert metrics["cv_auc"] >= HEADLINE - 0.03
    assert metrics["gap"] >= 0.15
    assert metrics["holdout_auc"] <= HEADLINE - 0.10
    assert metrics["holdout_auc"] < FLOOR
    assert metrics["gap"] == pytest.approx(metrics["cv_auc"] - metrics["holdout_auc"], abs=2e-4)


@pytest.mark.parametrize("seed", SEEDS)
def test_corrected_analysis_agrees_with_the_heldout_data(uv, seed):
    metrics = corrected(seed)
    assert set(metrics) == set(task()["declared_measures"])
    assert -0.07 <= metrics["gap"] <= 0.07


@pytest.mark.parametrize("seed", SEEDS)
def test_correction_changes_only_the_cross_validated_estimate(uv, seed):
    """The same pipeline fitted on the whole pilot sample scores the held-out data the same, so the
    difference between the two analyses is where the selection sits and nothing else."""
    assert corrected(seed)["holdout_auc"] == inherited(seed)["holdout_auc"]
    assert corrected(seed)["cv_auc"] < inherited(seed)["cv_auc"] - 0.10


def test_defaults_are_the_reported_setting(uv):
    for script in ("analysis.py", "../corrected.py"):
        assert measured(script, "--seed", "0", "--k", "30", "--folds", "5")[0] == measured(script, "--seed", "0")[0] == measured(script)[0]


def test_each_run_takes_under_a_minute(uv):
    for seed in SEEDS:
        for script in ("analysis.py", "../corrected.py"):
            assert measured(script, "--seed", str(seed))[1] < 60

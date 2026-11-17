"""Build the second project's data files from a fixed generator.

Usage: python demo2/make_data.py

Twelve standard normal features, of which five carry the label: a weak linear part (x1, x2), an
interaction (the product of x3 and x4) and a step (x5 above 0.3). The label is drawn from the
logistic of their sum. Every draw comes from NumPy's PCG64 generator with a fixed seed, so the
files are the same on every run.

pilot.csv and heldout.csv go to the workspace an agent starts from. replication.csv, 50,000 more
samples from the same generator, goes beside the research map, where no agent or forecaster can
read it: re-running an analysis on it measures how the analysis truly does.

The files are written only when their digests are the recorded ones, so a changed generator or a
changed NumPy fails here and does not reach the workspace.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
FEATURES = 12
# The coefficients of the linear part, the interaction and the step.
LINEAR, INTERACTION, STEP = 0.8, 4.5, 1.2
FILES = {
    "pilot.csv": (HERE / "workspace" / "data", 1, 1000),
    "heldout.csv": (HERE / "workspace" / "data", 2, 3000),
    "replication.csv": (HERE.parent / "research" / "synthetic-interactions" / "replication", 3, 50000),
}
DIGESTS = {
    "pilot.csv": "sha256:fae1182afe1209ef16c1ab241ebb9ff785812c2310340efe457490dc43075164",
    "heldout.csv": "sha256:494d9fb0256b011886f058f885e722963dac275ed7d19f4ec3e565ab5c1ccd34",
    "replication.csv": "sha256:5ebf670308e524a0597a8b592a67763201ff95ef9a50e6f6d16d08fdb13d646e",
}


def draw(seed: int, rows: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.Generator(np.random.PCG64(seed))
    x = rng.standard_normal((rows, FEATURES))
    logit = LINEAR * (x[:, 0] + 0.5 * x[:, 1]) + INTERACTION * x[:, 2] * x[:, 3] + STEP * (x[:, 4] > 0.3) - STEP * 0.38
    label = (rng.random(rows) < 1 / (1 + np.exp(-logit))).astype(int)
    return x, label


def table(seed: int, rows: int) -> bytes:
    x, label = draw(seed, rows)
    header = ",".join([*(f"x{n}" for n in range(1, FEATURES + 1)), "label"])
    lines = [",".join([*(f"{v:.6f}" for v in row), str(y)]) for row, y in zip(x, label, strict=True)]
    return ("\n".join([header, *lines]) + "\n").encode("ascii")


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def build() -> dict[str, bytes]:
    return {name: table(seed, rows) for name, (_, seed, rows) in FILES.items()}


def main() -> int:
    files = build()
    wrong = [f"{name}: built {digest(content)}, recorded {DIGESTS[name]}" for name, content in files.items() if digest(content) != DIGESTS[name]]
    if wrong:
        print("make_data: the built files differ from the recorded ones; nothing was written", *wrong, sep="\n  ", file=sys.stderr)
        return 1
    for name, content in files.items():
        directory = FILES[name][0]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(content)
        print(f"{directory / name}: {content.count(b'\n') - 1} samples, {digest(content)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

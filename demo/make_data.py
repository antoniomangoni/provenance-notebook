"""Rebuild the demo's two data files from the Madelon archive at the UCI repository.

Usage: python demo/make_data.py [ARCHIVE]

ARCHIVE is a copy of madelon.zip; without it the archive is downloaded. The 2600 labelled
samples (the archive's training and validation sets, in that order) are divided once into a
pilot sample and the rest, held out. Values and labels are written as they are in the source.

The files are written only when their digests are the recorded ones, so a changed source or a
changed rule fails here and does not reach the workspace.
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

SOURCE = "https://archive.ics.uci.edu/static/public/171/madelon.zip"
DATA = Path(__file__).parent / "workspace" / "data"

# Each part is its values and its labels; the validation labels sit at the top of the archive.
PARTS = [("MADELON/madelon_train.data", "MADELON/madelon_train.labels"), ("MADELON/madelon_valid.data", "madelon_valid.labels")]
FEATURES = 500
PER_CLASS = 200  # pilot samples of each label
SALT = "madelon-pilot"

DIGESTS = {
    "pilot.csv": "sha256:11bd022d3a3bd3b394688fb17f5c0c59312f3afdb273d48ad33bbf92ce8d0238",
    "heldout.csv": "sha256:e0b31cbc8eedf1ed84726d9e50066520eccf9ce4f56c182098432fc231784cc1",
}


def samples(archive: bytes) -> list[tuple[list[str], str]]:
    """Every labelled sample as (values, label), in source order."""
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        rows = []
        for values, labels in PARTS:
            part = [line.split() for line in source.read(values).decode("ascii").splitlines()]
            rows += zip(part, source.read(labels).decode("ascii").split(), strict=True)
    if any(len(values) != FEATURES or label not in ("-1", "1") for values, label in rows):
        raise SystemExit("make_data: the archive is not 500 values and a label of -1 or 1 per sample")
    return rows


def pilot(rows: list[tuple[list[str], str]]) -> set[int]:
    """The pilot sample: of each label, the samples whose hashed position sorts first.

    A hash of the position has no seed to choose, and is the same on every platform and version.
    """
    order = sorted(range(len(rows)), key=lambda at: hashlib.sha256(f"{SALT}:{at}".encode()).hexdigest())
    return {at for label in ("-1", "1") for at in [at for at in order if rows[at][1] == label][:PER_CLASS]}


def build(archive: bytes) -> dict[str, bytes]:
    rows = samples(archive)
    chosen = pilot(rows)
    header = ",".join([*(f"x{number}" for number in range(1, FEATURES + 1)), "label"])

    def table(keep: bool) -> bytes:
        lines = [",".join([*values, label]) for at, (values, label) in enumerate(rows) if (at in chosen) == keep]
        return ("\n".join([header, *lines]) + "\n").encode("ascii")

    return {"pilot.csv": table(True), "heldout.csv": table(False)}


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        archive = Path(argv[1]).read_bytes()
    else:
        with urllib.request.urlopen(SOURCE, timeout=120) as response:
            archive = response.read()
    files = build(archive)
    wrong = [
        f"{name}: built {digest(content)}, recorded {DIGESTS[name]}" for name, content in files.items() if digest(content) != DIGESTS[name]
    ]
    if wrong:
        print("make_data: the rebuilt files differ from the recorded ones; nothing was written", *wrong, sep="\n  ", file=sys.stderr)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (DATA / name).write_bytes(content)
        print(f"{DATA / name}: {content.count(b'\n') - 1} samples, {digest(content)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

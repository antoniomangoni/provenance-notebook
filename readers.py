"""The reader check: can a reader who was not there answer the roadmap's four questions?

Usage:
  readers.py texts TRAIL --store STORE --log FILE --out DIR
  readers.py grade DIR --questions FILE --trail TRAIL

`texts` writes the two presentations of one trail: `view.txt`, the text of the reviewer's page,
and `baseline.txt`, what a reviewer has today, Pi's transcript and the agent's git log. `grade`
scores the answers in `DIR/answers.jsonl` against the key in FILE and writes `DIR/table.md`.

Grading is mechanical. An answer is one JSON object, an item of the key is right when the
answer's fields hold one of the accepted values, and a question's score is the share of its
items that are right.
"""

import html.parser
import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import trail
import view

PRESENTATIONS = ("view", "baseline")
TOLERANCE = 0.0005  # numbers are right within this: 0.564 is right for 0.5639, 0.565 is not


# --- texts ---------------------------------------------------------------------------------------


class Text(html.parser.HTMLParser):
    """The text of a page: every tag removed, styles and scripts dropped, a closed <details> kept."""

    BLOCKS = frozenset(
        [
            "p",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "article",
            "section",
            "div",
            "dl",
            "dt",
            "ul",
            "ol",
            "details",
            "summary",
            "pre",
            "header",
            "title",
        ]
    )
    DROPPED = frozenset(("style", "script"))

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROPPED:
            self.dropping += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n\n" if tag in ("h2", "h3", "article") else "\n")
        elif tag == "dd":
            self.parts.append(": ")

    def handle_endtag(self, tag):
        if tag in self.DROPPED:
            self.dropping -= 1
        elif tag == "dd" or (tag in self.BLOCKS and tag != "dt"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.dropping:
            self.parts.append(data)


def page_text(page: str) -> str:
    parser = Text()
    parser.feed(page)
    parser.close()
    lines = [line.rstrip() for line in "".join(parser.parts).split("\n")]
    kept = [line for at, line in enumerate(lines) if line or (at and lines[at - 1])]
    return "\n".join(kept).strip("\n") + "\n"


def view_text(directory: Path, steps: list[dict]) -> str:
    """The page as `trail.py view TRAIL --code CLONE` writes it, with the code from the trail's own bundle."""
    with tempfile.TemporaryDirectory() as work:
        subprocess.run(["git", "clone", "--quiet", str(directory / "code.bundle"), work], check=True, capture_output=True)
        return page_text(view.page(steps, Path(work)))


def argument(name: str, value: object) -> str:
    return f"  {name}: " + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))


def message_text(entry: dict) -> str:
    """One entry of Pi's session file, whole: nothing a reviewer could read there is left out."""
    if entry.get("type") != "message":
        return f"[{entry.get('type')}] " + json.dumps(
            {k: v for k, v in entry.items() if k not in ("type", "id", "parentId")}, ensure_ascii=False
        )
    message = entry["message"]
    role = message["role"]
    lines = [f"[{role}, {entry.get('timestamp', '')}]"]
    if role == "toolResult":
        lines[0] = f"[result of {message.get('toolName')}{', an error' if message.get('isError') else ''}, {entry.get('timestamp', '')}]"
    content = message["content"] if isinstance(message["content"], list) else [{"type": "text", "text": message["content"]}]
    for part in content:
        if part["type"] == "text":
            lines.append(part["text"])
        elif part["type"] == "thinking":
            lines.append(f"(thinking) {part['thinking']}")
        elif part["type"] == "toolCall":
            lines.append(f"(calls {part['name']})")
            lines += [argument(name, value) for name, value in part["arguments"].items()]
        else:
            lines.append(json.dumps(part, ensure_ascii=False))
    if message.get("details"):
        lines.append("(details) " + json.dumps(message["details"], ensure_ascii=False))
    return "\n".join(lines)


def baseline_text(directory: Path, log: Path) -> str:
    sessions = sorted((directory / "session").glob("*.jsonl"))
    entries = [json.loads(line) for session in sessions for line in session.read_text().splitlines() if line.strip()]
    transcript = "\n\n".join(message_text(entry) for entry in entries)
    return f"===== The agent's session: Pi's transcript =====\n\n{transcript}\n\n===== git log --stat of the agent's repository =====\n\n{log.read_text()}"


def texts(directory: Path, store: Path, log: Path, out: Path) -> list[str]:
    steps = trail.load(directory)
    if found := trail.check(steps, store):
        return found
    out.mkdir(parents=True, exist_ok=True)
    (out / "view.txt").write_text(view_text(directory, steps), encoding="utf-8")
    (out / "baseline.txt").write_text(baseline_text(directory, log), encoding="utf-8")
    return []


# --- grade ---------------------------------------------------------------------------------------


def as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value) if isinstance(value, str) else None
    except ValueError:
        return None


def commit(value: object) -> str:
    """The first 7 characters of a commit, with or without the `commit:` the step files write before it."""
    return str(value).strip().lower().removeprefix("commit:")[:7]


def matches(kind: str, given: object, accepted: object) -> bool:
    """Whether one field of an answer is the accepted value, by the rule of its kind."""
    if kind == "step":
        return isinstance(given, str) and given.strip() == accepted
    if kind == "number":
        return (number := as_number(given)) is not None and abs(number - accepted) <= TOLERANCE
    if kind == "commit":
        return isinstance(given, str) and len(commit(given)) == 7 and commit(given) == commit(accepted)
    if kind == "command":
        return isinstance(given, str) and " ".join(given.split()) == " ".join(accepted.split())
    if kind == "name":
        return isinstance(given, str) and given.strip() == accepted
    if kind == "empty":
        return given in ([], {})
    if kind == "entries":
        # A list of objects, one of which holds every accepted field: {"step": ["step", "step-4"]}.
        entries = [entry for entry in given if isinstance(entry, dict)] if isinstance(given, list) else []
        return any(all(matches(sub, entry.get(name), value) for name, (sub, value) in accepted.items()) for entry in entries)
    raise ValueError(f"unknown kind {kind}")


def right(item: dict, answer: dict | None) -> bool:
    """An item is right when, for one accepted alternative, every one of its fields matches. Fields that
    belong together, a run and its code, are one item: each half right for a different run is wrong."""
    if not isinstance(answer, dict):
        return False
    return any(
        all(matches(kind, answer.get(field), value) for field, kind, value in zip(item["fields"], item["kinds"], alternative, strict=True))
        for alternative in item["accepted"]
    )


def score(question: dict, answer: dict | None) -> float:
    return sum(right(item, answer) for item in question["items"]) / len(question["items"])


def occurs(kind: str, accepted: object, text: str) -> bool | None:
    """Whether an accepted value can be read off a presentation. None for a value that is counted or
    absent by nature, such as the number of runs, which no text has to state."""
    if kind == "step":
        return re.search(rf"\b{re.escape(accepted)}\b", text) is not None
    if kind == "number":
        return view.number(accepted) in text
    if kind == "commit":
        return commit(accepted) in text.lower()
    if kind in ("command", "name"):
        return accepted in text
    if kind == "entries":
        return all(occurs(sub, value, text) for sub, value in accepted.values())
    return None


def item_occurs(item: dict, text: str) -> bool | None:
    if not item.get("quoted", True):
        return None
    found = [
        [occurs(kind, value, text) for kind, value in zip(item["kinds"], alternative, strict=True)] for alternative in item["accepted"]
    ]
    return None if any(None in alternative for alternative in found) else any(all(alternative) for alternative in found)


def said(kind: str, accepted: object) -> str:
    if kind == "empty":
        return "none given"
    if kind == "entries":
        return "an entry with " + " and ".join(f"{name} {said(sub, value)}" for name, (sub, value) in accepted.items())
    return f"`{commit(accepted)}`" if kind == "commit" else f"`{view.number(accepted) if kind == 'number' else accepted}`"


def key_problems(questions: dict, steps: list[dict]) -> list[str]:
    """A key is for one trail: its name is the trail's and every step it accepts is a step of it."""
    ids = {step["id"] for step in steps}
    found = [] if steps[0]["trail"] == questions["trail"] else [f"the key is for {questions['trail']}, the trail is {steps[0]['trail']}"]

    def steps_of(kind, value):
        if kind == "step":
            yield value
        elif kind == "entries":
            for sub, inner in value.values():
                yield from steps_of(sub, inner)

    for question in questions["questions"]:
        for item in question["items"]:
            for alternative in item["accepted"]:
                for kind, value in zip(item["kinds"], alternative, strict=True):
                    found += [
                        f"question {question['number']}: {step} is not a step of the trail"
                        for step in steps_of(kind, value)
                        if step not in ids
                    ]
    return found


def spread(scores: list[float]) -> str:
    return f"{statistics.mean(scores):.2f} ({min(scores):.2f} to {max(scores):.2f})" if scores else "no calls"


def table(questions: dict, answers: list[dict], texts: dict[str, str], steps: list[dict]) -> str:
    models = list(dict.fromkeys(line["model"] for line in answers))

    def of(model: str, presentation: str) -> list[dict]:
        return [line for line in answers if line["model"] == model and line["presentation"] == presentation]

    lines = [
        f"# Reader check: {questions['trail']}",
        "",
        (
            f"Written by `readers.py grade` from `answers.jsonl` and `{questions.get('file', 'questions.json')}`. "
            f"The trail's head is `{trail.digest(trail.canonical(steps[-1]))}`."
        ),
        "",
        "A score is the share of a question's key items that an answer got right. Each cell is the mean over",
        "the calls and, in brackets, the lowest and the highest. A failed call or a reply without a JSON",
        "object scores 0 on every item.",
        "",
        "## Scores",
        "",
        "| Model | Question | From the view | From the baseline |",
        "| --- | --- | --- | --- |",
    ]
    for model in models:
        for question in questions["questions"]:
            cells = [spread([score(question, line["answer"]) for line in of(model, presentation)]) for presentation in PRESENTATIONS]
            lines.append(f"| `{model}` | {question['number']}. {question['text']} | {cells[0]} | {cells[1]} |")
    lines += [
        "",
        "## Calls",
        "",
        "| Model | Presentation | Characters | Calls | Failed | Without a JSON object |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for model in models:
        for presentation in PRESENTATIONS:
            calls = of(model, presentation)
            failed = sum(line.get("error") is not None for line in calls)
            unparsed = sum(line.get("error") is None and line["answer"] is None for line in calls)
            lines.append(f"| `{model}` | {presentation} | {len(texts[presentation])} | {len(calls)} | {failed} | {unparsed} |")
    lines += [
        "",
        "## Each item of the key",
        "",
        "How many calls got the item right, and whether an accepted value can be read off each presentation's",
        'text at all. "No" marks an item that presentation cannot answer; "counted" marks a value a reader',
        "has to work out, which no text needs to state.",
        "",
        "| Item | Accepted | In the view | In the baseline | " + " | ".join(f"`{model}`: view, baseline" for model in models) + " |",
        "| --- | --- | --- | --- |" + " --- |" * len(models),
    ]
    for question in questions["questions"]:
        for item in question["items"]:
            accepted = "; or ".join(
                " with ".join(said(kind, value) for kind, value in zip(item["kinds"], alternative, strict=True))
                for alternative in item["accepted"]
            )
            there = [{None: "counted", True: "yes", False: "no"}[item_occurs(item, texts[presentation])] for presentation in PRESENTATIONS]
            counts = [
                ", ".join(
                    f"{sum(right(item, line['answer']) for line in of(model, presentation))} of {len(of(model, presentation))}"
                    for presentation in PRESENTATIONS
                )
                for model in models
            ]
            lines.append(
                f"| {question['number']} {', '.join(f'`{field}`' for field in item['fields'])} | {accepted} | {there[0]} | {there[1]} | "
                + " | ".join(counts)
                + " |"
            )
    return "\n".join(lines) + "\n"


def grade(directory: Path, questions_file: Path, trail_directory: Path) -> list[str]:
    questions = json.loads(questions_file.read_text()) | {"file": questions_file.as_posix()}
    steps = trail.load(trail_directory)
    if found := key_problems(questions, steps):
        return found
    answers = [json.loads(line) for line in (directory / "answers.jsonl").read_text().splitlines() if line.strip()]
    kept = {presentation: (directory / f"{presentation}.txt").read_text(encoding="utf-8") for presentation in PRESENTATIONS}
    (directory / "table.md").write_text(table(questions, answers, kept, steps), encoding="utf-8")
    return []


# --- the command line ------------------------------------------------------------------------------

USAGE = {
    "texts": ("readers.py texts TRAIL --store STORE --log FILE --out DIR", ("--store", "--log", "--out")),
    "grade": ("readers.py grade DIR --questions FILE --trail TRAIL", ("--questions", "--trail")),
}


def main(argv: list[str]) -> int:
    args = argv[1:]
    usage, names = USAGE.get(args[0] if args else "", ("\n       ".join(line for line, _ in USAGE.values()), ()))
    if not names or len(args) != 2 + 2 * len(names) or args[-1] in names or any(args.count(name) != 1 for name in names):
        print(f"usage: {usage}", file=sys.stderr)
        return 2
    named = {name[2:]: Path(trail.option(args, name)) for name in names}
    command, directory = args[0], Path(args[1])
    if command == "texts":
        found = texts(directory, named["store"], named["log"], named["out"])
        print("\n".join(found) or f"wrote {named['out'] / 'view.txt'} and {named['out'] / 'baseline.txt'}")
    else:
        found = grade(directory, named["questions"], named["trail"])
        print("\n".join(found) or f"wrote {directory / 'table.md'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""The reader check: can a reader who was not there answer the roadmap's four questions?

Usage:
  readers.py texts TRAIL --store STORE --log FILE --out DIR
  readers.py ask DIR --questions FILE --repeats N [pi options]
  readers.py grade DIR --questions FILE --trail TRAIL

`texts` writes the two presentations of one trail: `view.txt`, the text of the reviewer's page,
and `baseline.txt`, what a reviewer has today, Pi's transcript and the agent's git log. `ask`
gives each presentation to a model N times, through Pi with no tools, and appends every reply to
`DIR/answers.jsonl`. `grade` scores those answers against the key in FILE and writes `DIR/table.md`.

The model is Pi's to choose and to reach: the options after N go to Pi, over the defaults
`--provider berget --model zai-org/GLM-5.3-Flash --thinking off`, and no key is read here.

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

PRESENTATIONS = ("view", "baseline")  # the first comparison's
EVERY = ("view", "baseline", "plain")  # the second comparison adds the transcript without the notebook
STEP_ID = re.compile(r"\bstep-[0-9]+\b", re.IGNORECASE)
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


def plain_text(directory: Path, log: Path) -> str:
    """What Pi alone would have recorded: the transcript without the notebook's words. The calls to
    `propose_plan` and their results go, the receipts capture added to tool results go, and any step id
    left, in the agent's thinking or text, is replaced, since only the notebook's receipts taught it."""
    sessions = sorted((directory / "session").glob("*.jsonl"))
    entries = [json.loads(line) for session in sessions for line in session.read_text().splitlines() if line.strip()]
    plans = {
        part["id"]
        for entry in entries
        for part in (entry.get("message") or {}).get("content") or []
        if isinstance(part, dict) and part.get("type") == "toolCall" and part.get("name") == "propose_plan"
    }
    kept = []
    for entry in entries:
        message = entry.get("message") or {}
        if message.get("toolCallId") in plans:
            continue
        if isinstance(message.get("content"), list):
            content = [part for part in message["content"] if not (part.get("type") == "toolCall" and part.get("id") in plans)]
            entry = entry | {"message": message | {"content": content}}
        kept.append(message_text(entry))
    lines = "\n\n".join(kept).split("\n")
    transcript = "\n".join(line for line in lines if not line.startswith("[notebook]"))
    transcript = STEP_ID.sub("(step id removed)", transcript)
    return f"===== The agent's session: Pi's transcript =====\n\n{transcript}\n\n===== git log --stat of the agent's repository =====\n\n{log.read_text()}"


def texts(directory: Path, store: Path, log: Path, out: Path) -> list[str]:
    steps = trail.load(directory)
    if found := trail.check(steps, store):
        return found
    out.mkdir(parents=True, exist_ok=True)
    (out / "view.txt").write_text(view_text(directory, steps), encoding="utf-8")
    (out / "baseline.txt").write_text(baseline_text(directory, log), encoding="utf-8")
    (out / "plain.txt").write_text(plain_text(directory, log), encoding="utf-8")
    return []


# --- ask ---------------------------------------------------------------------------------------------

PI = Path(__file__).parent / "capture" / "node_modules" / ".bin" / "pi"
DEFAULTS = {"--provider": "berget", "--model": "zai-org/GLM-5.3-Flash", "--thinking": "off"}
SYSTEM = (
    "You review the record of an analysis that someone else carried out. You were not there. Answer only from the record you are given."
)
SECONDS = 600


class Failed(Exception):
    """A call that gave no reply. It is recorded and counted, never repeated silently."""


def prompt(text: str, questions: dict) -> str:
    """What a reader is given. The words are the same for both presentations: the record, the four
    questions, then the form of the answer."""
    asked = "\n".join(f"{question['number']}. {question['text']}" for question in questions["questions"])
    fields = "\n".join(f'- "{name}": {meaning}' for question in questions["questions"] for name, meaning in question["fields"].items())
    return (
        "Below is the record of an analysis that an AI agent carried out. Read it, then answer the questions after it.\n\n"
        f"===== THE RECORD =====\n{text}\n===== END OF THE RECORD =====\n\n"
        f"Questions:\n{asked}\n\n"
        "Answer with one JSON object and nothing else: no explanation and no code fence. It has exactly these fields.\n"
        f"{fields}\n\n{questions['form']}\n"
    )


def reply(asked: str, options: list[str]) -> str:
    """One call to Pi in print mode: no tools, no extensions, no skills, no context files, no session
    kept, in an empty directory. The prompt goes in on standard input, since a presentation is longer
    than one argument may be (128 kB on Linux). The tests replace this function."""
    command = [str(PI), "-p", "--no-tools", "--no-extensions", "--no-skills", "--no-context-files", "--no-prompt-templates",
               "--no-session", "--system-prompt", SYSTEM, *options]  # fmt: skip
    with tempfile.TemporaryDirectory() as work:
        try:
            done = subprocess.run(command, input=asked, cwd=work, capture_output=True, text=True, timeout=SECONDS, check=False)
        except subprocess.TimeoutExpired:
            raise Failed(f"no reply in {SECONDS} seconds") from None
    if done.returncode != 0 or not done.stdout.strip():
        said = (done.stderr.strip() or done.stdout.strip() or "no output").splitlines()[-1][:300]
        raise Failed(f"exit code {done.returncode}: {said}")
    return done.stdout


def parse(text: str) -> dict | None:
    """The JSON object of a reply: the reply itself, or what lies from its first brace to its last, so
    a code fence or a sentence around the object does not lose it."""
    for candidate in (text, text[text.find("{") : text.rfind("}") + 1]):
        try:
            found = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(found, dict):
            return found
    return None


def ask(
    directory: Path,
    questions: dict,
    repeats: int,
    options: dict[str, str],
    presentations: tuple[str, ...] = PRESENTATIONS,
    answers_file: str = "answers.jsonl",
    comparison: int | None = None,
) -> list[dict]:
    """Each presentation, `repeats` times. A line is appended as soon as its call returns, so the file
    holds every call that was made, whatever happens to the ones after it. A call made for a later
    comparison carries its number, so the first comparison's table is graded from its own calls."""
    chosen = DEFAULTS | options
    model = f"{chosen['--provider']}/{chosen['--model']}"
    asked = {name: prompt((directory / f"{name}.txt").read_text(encoding="utf-8"), questions) for name in presentations}
    lines = []
    for repeat in range(1, repeats + 1):
        for presentation in presentations:
            line = {"presentation": presentation, "repeat": repeat, "model": model, "reply": None, "answer": None}
            if comparison is not None:
                line["comparison"] = comparison
            try:
                line["reply"] = reply(asked[presentation], [word for pair in chosen.items() for word in pair])
                line["answer"] = parse(line["reply"])
            except Failed as failed:
                line["error"] = failed.args[0]
            with (directory / answers_file).open("a", encoding="utf-8") as answers:
                answers.write(json.dumps(line, ensure_ascii=False) + "\n")
            lines.append(line)
    return lines


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
    if kind == "bool":
        return isinstance(given, bool) and given is accepted
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
    return None  # empty and bool: a reader works them out


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
    if kind == "bool":
        return f"`{json.dumps(accepted)}`"
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


def read_answers(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def neutral_questions(comparison: dict, sets: list[dict]) -> list[dict]:
    """Each question with only the items a reader can answer without the notebook's step ids or snapshot
    commits, and the narrower accepted values the comparison gives some of them."""
    chosen = {(entry["question"], tuple(entry["fields"])): entry for entry in comparison["neutral"]}
    found = []
    for questions in sets:
        for question in questions["questions"]:
            items = []
            for item in question["items"]:
                if entry := chosen.get((question["number"], tuple(item["fields"]))):
                    items.append(item | ({"accepted": entry["accepted"]} if "accepted" in entry else {}))
            if items:
                found.append(question | {"items": items})
    return found


def table_2(comparison: dict, sets: list[tuple[dict, list[dict]]], texts: dict[str, str], steps: list[dict]) -> str:
    """The second comparison: three presentations, the neutral items beside the full key, every call."""
    calls = [(questions, line) for questions, answers in sets for line in answers]
    models = list(dict.fromkeys(line["model"] for _, line in calls))
    by_number = {question["number"]: questions for questions, _ in sets for question in questions["questions"]}

    def of(model: str, presentation: str, number: int) -> list[dict]:
        return [
            line
            for questions, line in calls
            if line["model"] == model and line["presentation"] == presentation and questions is by_number[number]
        ]

    def scores_table(questions: list[dict]) -> list[str]:
        rows = ["| Model | Question | " + " | ".join(f"From the {name}" for name in EVERY) + " |", "| --- | --- |" + " --- |" * len(EVERY)]
        for model in models:
            for question in questions:
                cells = [spread([score(question, line["answer"]) for line in of(model, name, question["number"])]) for name in EVERY]
                rows.append(f"| `{model}` | {question['number']}. {question['text']} | " + " | ".join(cells) + " |")
        return rows

    neutral = neutral_questions(comparison, [questions for questions, _ in sets])
    every = [question for questions, _ in sets for question in questions["questions"]]
    lines = [
        f"# Reader check, second comparison: {comparison['trail']}",
        "",
        "**Added after the first result was seen** ([spec 4b](../../docs/specs/04b-second-comparison.md)). The first",
        "comparison's table, `table.md`, is unchanged. Written by `readers.py grade --compare` from "
        + ", ".join(f"`{entry['answers']}`" for entry in comparison["sets"])
        + f". The trail's head is `{trail.digest(trail.canonical(steps[-1]))}`.",
        "",
        "Presentations: `view.txt`, the text of the reviewer's page; `baseline.txt`, Pi's whole transcript, which",
        "holds the notebook's plan calls and receipts; `plain.txt`, the same transcript without them and with",
        "step ids removed, and so without the notebook. A score is the share of a question's items an answer got",
        "right: the mean over the calls and, in brackets, the lowest and the highest.",
        "",
        "## Scores on the items every presentation can answer",
        "",
        "Only the items listed in `comparison-2.json`: none needs a step id or a snapshot commit.",
        "",
        *scores_table(neutral),
        "",
        "## Scores on the whole key",
        "",
        "The plain transcript has no step ids, so it cannot score on the items that ask for one.",
        "",
        *scores_table(every),
        "",
        "## Calls",
        "",
        "| Model | Questions | Presentation | Characters | Calls | Failed | Without a JSON object |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model in models:
        for questions, _ in sets:
            first = questions["questions"][0]["number"]
            for name in EVERY:
                made = of(model, name, first)
                failed = sum(line.get("error") is not None for line in made)
                unparsed = sum(line.get("error") is None and line["answer"] is None for line in made)
                lines.append(f"| `{model}` | {questions['file']} | {name} | {len(texts[name])} | {len(made)} | {failed} | {unparsed} |")
    lines += [
        "",
        "## Each item every presentation can answer",
        "",
        'Whether an accepted value can be read off each text ("counted": a reader works it out), and how many',
        "calls got the item right, in the order view, baseline, plain.",
        "",
        "| Item | Accepted | In the view | In the baseline | In the plain | " + " | ".join(f"`{model}`" for model in models) + " |",
        "| --- | --- | --- | --- | --- |" + " --- |" * len(models),
    ]
    for question in neutral:
        for item in question["items"]:
            accepted = "; or ".join(
                " with ".join(said(kind, value) for kind, value in zip(item["kinds"], alternative, strict=True))
                for alternative in item["accepted"]
            )
            there = [{None: "counted", True: "yes", False: "no"}[item_occurs(item, texts[name])] for name in EVERY]
            counts = [
                ", ".join(
                    f"{sum(right(item, line['answer']) for line in of(model, name, question['number']))} of {len(of(model, name, question['number']))}"
                    for name in EVERY
                )
                for model in models
            ]
            lines.append(
                f"| {question['number']} {', '.join(f'`{f}`' for f in item['fields'])} | {accepted} | " + " | ".join(there + counts) + " |"
            )
    return "\n".join(lines) + "\n"


def compare(directory: Path, comparison_file: Path, trail_directory: Path, out: Path) -> list[str]:
    comparison = json.loads(comparison_file.read_text())
    steps = trail.load(trail_directory)
    sets, found = [], []
    for entry in comparison["sets"]:
        path = comparison_file.parent / entry["questions"]
        questions = json.loads(path.read_text()) | {"file": f"`{entry['questions']}`"}
        found += key_problems(questions, steps)
        sets.append((questions, read_answers(directory / entry["answers"])))
    if found:
        return found
    kept = {name: (directory / f"{name}.txt").read_text(encoding="utf-8") for name in EVERY}
    out.write_text(table_2(comparison, sets, kept, steps), encoding="utf-8")
    return []


def grade(directory: Path, questions_file: Path, trail_directory: Path) -> list[str]:
    questions = json.loads(questions_file.read_text()) | {"file": questions_file.as_posix()}
    steps = trail.load(trail_directory)
    if found := key_problems(questions, steps):
        return found
    answers = [line for line in read_answers(directory / "answers.jsonl") if "comparison" not in line]
    kept = {presentation: (directory / f"{presentation}.txt").read_text(encoding="utf-8") for presentation in PRESENTATIONS}
    (directory / "table.md").write_text(table(questions, answers, kept, steps), encoding="utf-8")
    return []


# --- the command line ------------------------------------------------------------------------------

USAGE = {
    "texts": ("readers.py texts TRAIL --store STORE --log FILE --out DIR", ("--store", "--log", "--out")),
    "ask": (
        "readers.py ask DIR --questions FILE --repeats N [--presentations A,B] [--answers FILE] [--comparison N] [pi options]",
        ("--questions", "--repeats"),
    ),
    "grade": ("readers.py grade DIR --questions FILE --trail TRAIL [--compare FILE --out FILE]", ("--questions", "--trail")),
}
OPTIONAL = {"ask": ("--presentations", "--answers", "--comparison"), "grade": ("--compare", "--out")}


def optional(args: list[str], name: str) -> str | None:
    """Takes `name VALUE` out of the arguments when it is there; a name without a value is left for the usage check."""
    if name not in args or args.index(name) + 1 == len(args):
        return None
    at = args.index(name)
    value = args[at + 1]
    del args[at : at + 2]
    return value


def main(argv: list[str]) -> int:
    args = argv[1:]
    usage, names = USAGE.get(args[0] if args else "", ("\n       ".join(line for line, _ in USAGE.values()), ()))
    extra = {name[2:]: optional(args, name) for name in OPTIONAL.get(args[0] if args else "", ())}
    rest = len(args) - 2 - 2 * len(names)
    # After the command, its directory and its own options, only `ask` takes more: Pi's options, in pairs.
    wrong = rest % 2 != 0 or not all(word.startswith("--") for word in args[2:][::2]) if args[:1] == ["ask"] else rest != 0
    if not names or rest < 0 or wrong or args[-1] in names or any(args.count(name) != 1 for name in names):
        print(f"usage: {usage}", file=sys.stderr)
        return 2
    named = {name[2:]: trail.option(args, name) for name in names}
    command, directory = args[0], Path(args[1])
    if command == "texts":
        found = texts(directory, Path(named["store"]), Path(named["log"]), Path(named["out"]))
        print("\n".join(found) or f"wrote view.txt, baseline.txt and plain.txt in {named['out']}")
    elif command == "ask":
        shown = tuple((extra["presentations"] or ",".join(PRESENTATIONS)).split(","))
        number = extra["comparison"]
        if not named["repeats"].isdigit() or int(named["repeats"]) < 1 or set(shown) - set(EVERY) or (number and not number.isdigit()):
            print(f"usage: {usage}", file=sys.stderr)
            return 2
        lines = ask(
            directory,
            json.loads(Path(named["questions"]).read_text()),
            int(named["repeats"]),
            dict(zip(args[2::2], args[3::2], strict=True)),
            shown,
            extra["answers"] or "answers.jsonl",
            int(number) if number else None,
        )
        for line in lines:
            state = (
                f"failed: {line['error']}" if "error" in line else "no JSON object in the reply" if line["answer"] is None else "answered"
            )
            print(f"{line['model']} {line['presentation']} {line['repeat']}: {state}")
        found = []
    elif extra["compare"] or extra["out"]:
        if not (extra["compare"] and extra["out"]):
            print(f"usage: {usage}", file=sys.stderr)
            return 2
        found = compare(directory, Path(extra["compare"]), Path(named["trail"]), Path(extra["out"]))
        print("\n".join(found) or f"wrote {extra['out']}")
    else:
        found = grade(directory, Path(named["questions"]), Path(named["trail"]))
        print("\n".join(found) or f"wrote {directory / 'table.md'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

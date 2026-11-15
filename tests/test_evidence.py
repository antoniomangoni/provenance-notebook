"""The evidence on the live trail: the tamper sequence, where each stage is what the checker itself
returned, and the reader check, whose key is read off the step files. Nothing here calls a model."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import readers
import tamper
import trail
import view

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


# --- the reader check ------------------------------------------------------------------------------

QUESTIONS = json.loads((ROOT / "evidence" / "questions.json").read_text())
LOG = EVIDENCE / "git-log.txt"


def session() -> list[dict]:
    return [json.loads(line) for path in sorted((LIVE / "session").glob("*.jsonl")) for line in path.read_text().splitlines()]


def test_page_text_keeps_a_closed_details_and_drops_tags_styles_and_scripts():
    page = (
        "<html><head><title>t</title><style>p{color:red}</style></head><body><h2>Timeline</h2>"
        "<details><summary>2 exploratory commands</summary><ol><li>step-5 <code>ls</code></li></ol></details>"
        "<dl><dt>Code</dt><dd>commit:abc</dd></dl><script>go()</script><p>gap &lt;= 0.08 &amp; more</p><pre>a\n  b</pre></body></html>"
    )
    text = readers.page_text(page)
    assert text.splitlines() == [
        "t",
        "",
        "Timeline",
        "",
        "2 exploratory commands",
        "",
        "step-5 ls",
        "",
        "Code: commit:abc",
        "",
        "gap <= 0.08 & more",
        "",
        "a",
        "  b",
    ]
    assert "color" not in text and "go()" not in text


def test_view_txt_is_the_page_s_text_with_the_folded_commands_and_no_tag():
    steps = trail.load(LIVE)
    text = (EVIDENCE / "view.txt").read_text()
    assert text == readers.view_text(LIVE, steps)
    # Folded away on the page, in a closed <details>: the reader of the text still gets them.
    assert "1 exploratory command, 0 failed" in text and "step-6 inconclusive exit code 0" in text
    assert "Code changed from commit:" in text and "+++ b/analysis.py" in text, "the diffs are read from the trail's own bundle"
    assert not re.search(r"</?(span|a|p|li|dd|dt|details|summary|article|section|code|pre|style|h[1-4])\b", text)
    assert ".outcome{" not in text
    assert all(re.search(rf"\b{step['id']}\b", text) for step in steps if step["kind"] == "plan")


def test_baseline_txt_is_the_whole_transcript_and_the_git_log():
    text = (EVIDENCE / "baseline.txt").read_text()
    assert text == readers.baseline_text(LIVE, LOG)
    assert text.endswith(LOG.read_text()) and "cb37651" in LOG.read_text()
    calls = [
        part for entry in session() if entry["type"] == "message" for part in entry["message"]["content"] if part["type"] == "toolCall"
    ]
    assert len(calls) == 23 == sum(entry.get("message", {}).get("role") == "toolResult" for entry in session())
    for name in {call["name"] for call in calls}:
        assert text.count(f"(calls {name})\n") == sum(call["name"] == name for call in calls)
    for call in calls:
        for value in call["arguments"].values():
            assert (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)) in text
    for entry in session():
        for part in entry.get("message", {}).get("content", []):
            assert part.get("text", "") in text and part.get("thinking", "") in text


def accepted(number: int, field: str) -> list:
    question = next(question for question in QUESTIONS["questions"] if question["number"] == number)
    return next(item for item in question["items"] if item["fields"][0] == field)["accepted"]


def test_the_questions_are_the_roadmap_s():
    plan = (ROOT / "PLAN.md").read_text()
    assert [question["number"] for question in QUESTIONS["questions"]] == [1, 2, 3, 4]
    for question in QUESTIONS["questions"]:
        assert f"   {question['number']}. {question['text']}\n" in plan
        assert {field for item in question["items"] for field in item["fields"]} == set(question["fields"])


def test_every_value_of_the_key_is_read_off_the_step_files():
    steps = trail.load(LIVE)
    by_id = {step["id"]: step for step in steps}
    lookups = view.Trail(steps, None)
    assert QUESTIONS["trail"] == steps[0]["trail"] and readers.key_problems(QUESTIONS, steps) == []

    # 1. The one change of approach, its trigger and the expectation the trigger missed.
    (change,) = view.changes(steps)
    (replaced,), (trigger,) = change["replaced"], change["triggers"]
    (miss,) = view.missed(trigger, by_id)
    assert accepted(1, "new_plan") == [[change["plan"]["id"]]]
    assert accepted(1, "replaced_plan") == [[replaced["id"]]]
    assert accepted(1, "trigger") == [[trigger["id"]]]
    assert (accepted(1, "measure"), accepted(1, "measured"), accepted(1, "threshold")) == (
        [[miss["measure"]]],
        [[miss["measured"]]],
        [[miss["threshold"]]],
    )

    # 2. The final result is the last measured observation that met its plan; an earlier run that wrote
    # the same metrics file produced it as much as the last one did.
    held = [step for step in steps if step["kind"] == "observation" and step["outcome"] == "as_expected" and step.get("measures_source")]
    final = [by_id[trail.observed(step)] for step in reversed(held) if step["measures_source"] == held[-1]["measures_source"]]
    assert accepted(2, "run") == [[run["id"], run["code"]["ref"].removeprefix("commit:")] for run in final]
    assert sorted(accepted(2, "command")) == sorted([run["command"]["shown"]] for run in final)
    assert all(run.get("parameters", []) == [] for run in final) and accepted(2, "parameters") == [[None]]

    # 3. The plan of each of those runs, and how many measured runs it took until one met it.
    plans = [view.implemented(run, by_id) for run in final]
    assert accepted(3, "plan") == [[plan["id"]] for plan in plans]
    for plan in plans:
        outcomes = [lookups.settlement[run["id"]]["outcome"] for run in lookups.runs[plan["id"]] if lookups.measured(run)]
        assert accepted(3, "measured_runs") == [[outcomes.index("as_expected") + 1]]

    # 4. What was given up: the replaced plan, or the inherited analysis by the number that ended it,
    # which is the first measured observation of the trail.
    assert accepted(4, "abandoned") == [[{"step": ["step", replaced["id"]]}], [{"result": ["number", miss["measured"]]}]]
    assert next(step for step in steps if step.get("measures_source")) is trigger


def perfect() -> dict:
    """An answer built from the key: the first accepted alternative of every item."""
    answer = {}
    for question in QUESTIONS["questions"]:
        for item in question["items"]:
            for field, kind, value in zip(item["fields"], item["kinds"], item["accepted"][0], strict=True):
                answer[field] = (
                    {} if kind == "empty" else [{name: inner for name, (_, inner) in value.items()}] if kind == "entries" else value
                )
    return answer


def scores(answer: dict | None) -> list[float]:
    return [readers.score(question, answer) for question in QUESTIONS["questions"]]


def test_the_grader_gives_1_to_the_key_0_to_no_answer_and_the_share_to_one_item_wrong():
    assert scores(perfect()) == [1.0, 1.0, 1.0, 1.0]
    assert scores(None) == scores({}) == [0.0, 0.0, 0.0, 0.0]
    assert scores(perfect() | {"trigger": "step-7"}) == [5 / 6, 1.0, 1.0, 1.0]
    assert scores(perfect() | {"parameters": {"seed": 0}}) == [1.0, 2 / 3, 1.0, 1.0]
    assert scores(perfect() | {"measured_runs": 2}) == [1.0, 1.0, 0.5, 1.0]
    assert scores(perfect() | {"abandoned": [{"what": "nothing", "step": "step-9", "result": 0.59}]}) == [1.0, 1.0, 1.0, 0.0]


def test_the_grader_s_rules_for_each_kind_of_value():
    def with_(**fields) -> list[float]:
        return scores(perfect() | fields)

    # Step ids match exactly; numbers within 0.0005, as numbers or as text.
    assert with_(new_plan="14")[0] == with_(new_plan="Step-14")[0] == 5 / 6 and with_(new_plan=" step-14 ")[0] == 1.0
    assert with_(measured=0.56394)[0] == with_(measured="0.5639")[0] == 1.0
    assert with_(measured=0.564)[0] == 1.0, "0.0001 away: a value rounded to three places is right"
    assert with_(measured=0.565)[0] == with_(measured=True)[0] == with_(measured="about 0.56")[0] == 5 / 6
    # A commit by its first 7 characters; the run and its code are one item, right only together.
    assert with_(code="commit:190a214")[1] == with_(code="190A21455D")[1] == 1.0
    assert with_(run="step-17", code="13a6623")[1] == 1.0
    assert with_(code="190a21")[1] == with_(run="step-17")[1] == with_(code="13a66233af7af810106adfa3d624c8fd12d5900e")[1] == 2 / 3
    # A command after collapsing white space; no parameters is an empty list or object, not null.
    assert with_(command="uv  run python analysis.py\n")[1] == with_(command="uv run python analysis.py 2>/dev/null")[1] == 1.0
    assert with_(command="python analysis.py")[1] == with_(parameters=None)[1] == 2 / 3 and with_(parameters=[])[1] == 1.0
    # The final plan is the last one, or the one it only tidied up after.
    assert with_(plan="step-14")[2] == 1.0 and with_(plan="step-4")[2] == 0.5
    # What was abandoned: an entry naming the replaced plan, or one with the number that ended the inherited analysis.
    assert with_(abandoned=[{"what": "the inherited analysis", "step": None, "result": 0.5639}])[3] == 1.0
    assert with_(abandoned=[{"what": "x", "step": "step-9"}, {"step": "step-4"}])[3] == 1.0
    assert with_(abandoned="step-4")[3] == with_(abandoned=["step-4"])[3] == with_(abandoned=None)[3] == 0.0


def test_the_table_counts_every_call_and_marks_what_a_presentation_cannot_answer(tmp_path):
    lines = [
        {"presentation": "view", "repeat": 1, "model": "m/one", "reply": "{...}", "answer": perfect()},
        {"presentation": "view", "repeat": 2, "model": "m/one", "reply": "I cannot say.", "answer": None},
        {
            "presentation": "baseline",
            "repeat": 1,
            "model": "m/one",
            "reply": "{...}",
            "answer": perfect() | {"code": None, "trigger": "step-7"},
        },
        {"presentation": "baseline", "repeat": 2, "model": "m/one", "reply": None, "answer": None, "error": "exit code 1"},
        {"presentation": "view", "repeat": 1, "model": "m/two", "reply": "{...}", "answer": perfect()},
    ]
    for name in ("view.txt", "baseline.txt"):
        (tmp_path / name).write_text((EVIDENCE / name).read_text())
    (tmp_path / "answers.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert readers.grade(tmp_path, ROOT / "evidence" / "questions.json", LIVE) == []
    table = (tmp_path / "table.md").read_text()
    row = {line.split(" | ")[0] + " | " + line.split(" | ")[1]: line for line in table.splitlines() if line.startswith("| ")}

    assert row["| `m/one` | 1. Why did the approach change, and at which step?"].endswith("| 0.50 (0.00 to 1.00) | 0.42 (0.00 to 0.83) |")
    assert row["| `m/one` | 2. Which code and parameters produced the final result?"].endswith(
        "| 0.50 (0.00 to 1.00) | 0.33 (0.00 to 0.67) |"
    )
    assert row["| `m/two` | 4. What was tried and abandoned?"].endswith("| 1.00 (1.00 to 1.00) | no calls |")
    view_chars, baseline_chars = (len((EVIDENCE / name).read_text()) for name in ("view.txt", "baseline.txt"))
    assert row["| `m/one` | view"] == f"| `m/one` | view | {view_chars} | 2 | 0 | 1 |"
    assert row["| `m/one` | baseline"] == f"| `m/one` | baseline | {baseline_chars} | 2 | 1 | 0 |"
    assert row["| `m/two` | baseline"] == f"| `m/two` | baseline | {baseline_chars} | 0 | 0 | 0 |"
    # The snapshot commits are capture's: the page shows them, the transcript and the agent's git log cannot.
    assert row["| 2 `run`, `code` | `step-22` with `190a214`; or `step-17` with `13a6623`"].endswith(
        "| yes | no | 1 of 2, 0 of 2 | 1 of 1, 0 of 0 |"
    )
    assert row["| 3 `measured_runs` | `1`"].endswith("| counted | counted | 1 of 2, 1 of 2 | 1 of 1, 0 of 0 |")
    assert row["| 1 `trigger` | `step-8`"].endswith("| yes | yes | 1 of 2, 0 of 2 | 1 of 1, 0 of 0 |")


def test_a_key_for_another_trail_is_refused(tmp_path):
    other = trail.load(ROOT / "live" / "madelon-2026-11-15-2")
    found = readers.key_problems(QUESTIONS, other)
    assert "the key is for madelon-2026-11-15-1, the trail is madelon-2026-11-15-2" in found
    assert "question 3: step-22 is not a step of the trail" not in found and "question 2: step-22 is not a step of the trail" in found

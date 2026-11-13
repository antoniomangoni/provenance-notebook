"""The graph export's guarantees on the example trails: a probe's edges start at its own nodes, a
citation of another probe is pinned at a head, and merge refuses a citation that does not resolve."""

import copy
import csv
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import trail

EXAMPLES = Path(__file__).parent.parent / "examples"
CHURN, FEATURES, TUNING = (
    "churn/probe:churn-model-2026-11-11",
    "retention/probe:churn-features-2026-11-12",
    "churn/probe:churn-tuning-2026-11-13",
)


def rechain(steps: list[dict], start: int) -> None:
    for seq in range(start, len(steps)):
        steps[seq]["prev"] = trail.digest(trail.canonical(steps[seq - 1]))


@pytest.fixture
def trails() -> dict[str, list[dict]]:
    return {probe: trail.load(EXAMPLES / probe.split(":")[1]) for probe in (CHURN, FEATURES, TUNING)}


@pytest.fixture
def merged(trails) -> tuple[list[dict], list[dict]]:
    nodes, edges, errors = trail.merge(list(trails.values()))
    assert errors == []
    return nodes, edges


def test_the_examples_merge_with_every_edge_between_two_nodes(merged):
    nodes, edges = merged
    ids = [node["id"] for node in nodes]
    assert len(ids) == len(set(ids))
    assert {edge["source"] for edge in edges} | {edge["target"] for edge in edges} <= set(ids)


def test_every_edge_starts_at_a_node_its_own_probe_owns(merged):
    nodes, edges = merged
    owner = {node["id"]: node.get("graph") for node in nodes}
    assert all(owner[edge["source"]] == edge["graph"] for edge in edges)


def test_a_node_a_probe_only_cites_has_no_graph_and_no_tier(merged):
    nodes, _ = merged
    cited = [node for node in nodes if trail.KIND.match(node["id"])[1] != "probe"]
    assert {node["kind"] for node in cited} == {"human", "agent", "runner", "commit", "file"}
    assert all("graph" not in node and "tier" not in node for node in cited)
    assert all(node["graph"] and node["tier"] == 3 for node in nodes if node not in cited)


@pytest.mark.parametrize("order", [(CHURN, FEATURES), (FEATURES, CHURN)])
def test_a_probe_owns_its_node_whichever_way_round_it_is_merged_with_its_citation(trails, order):
    nodes, _, errors = trail.merge([trails[probe] for probe in order])
    assert errors == []
    churn = next(node for node in nodes if node["id"] == CHURN)
    assert churn["graph"] == CHURN and churn["version"] == trail.digest(trail.canonical(trails[CHURN][-1]))


def test_a_citation_of_another_probe_keeps_the_cited_head_on_the_edge(trails, merged):
    _, edges = merged
    head = trail.digest(trail.canonical(trails[CHURN][-1]))
    cites = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in edges
        if edge["target"].startswith(CHURN) and edge["graph"] != CHURN
    }
    assert set(cites) == {
        (f"{FEATURES}#step-0", "builds_on", CHURN),
        (f"{FEATURES}#step-1", "triggered_by", f"{CHURN}#step-6"),
        (f"{TUNING}#step-0", "builds_on", CHURN),
    }
    assert {edge["digest"] for edge in cites.values()} == {head}
    assert cites[f"{FEATURES}#step-1", "triggered_by", f"{CHURN}#step-6"]["status"] == "suggested"


def test_the_same_data_under_two_paths_joins_by_digest(merged):
    _, edges = merged
    read = {edge["target"]: edge["digest"] for edge in edges if edge["relation"] == "used"}
    assert read["churn/file:data/telco.csv"] == read["retention/file:inputs/telco.csv"]


def test_merge_refuses_a_cited_probe_that_was_rewritten_and_rechained(trails):
    churn = copy.deepcopy(trails[CHURN])
    churn[4]["reasoning"] = "Boosting was always the plan."
    rechain(churn, 5)
    assert trail.check(churn) == []
    errors = trail.merge([churn, trails[FEATURES]])[2]
    assert errors and all("a head it never had" in error for error in errors)


def test_merge_refuses_a_citation_of_the_wrong_kind_of_step(trails):
    features = copy.deepcopy(trails[FEATURES])
    link = next(link for link in features[1]["links"] if link["relation"] == "triggered_by")
    link["target"] = link["target"].replace("#step-6", "#step-4")
    rechain(features, 2)
    assert trail.check(features) == []
    assert trail.merge([trails[CHURN], features])[2] == [f"{FEATURES}#step-1: triggered_by must point at an observation step"]


def test_merge_refuses_a_citation_of_a_probe_that_is_not_merged(trails):
    errors = trail.merge([trails[FEATURES]])[2]
    assert errors and all(f"cites {CHURN}, which is not merged" in error for error in errors)


def test_merge_refuses_the_same_probe_twice(trails):
    assert f"{CHURN}: merged twice" in trail.merge([trails[CHURN], trails[CHURN]])[2]


def test_a_cited_probe_that_only_grew_still_merges(trails):
    churn = copy.deepcopy(trails[CHURN])
    churn.append(
        {
            "version": 2,
            "id": "step-8",
            "seq": 8,
            "trail": churn[0]["trail"],
            "at": "2026-11-13T09:00:00Z",
            "kind": "note",
            "by": "human:antonio",
            "summary": "Later note",
            "text": "Written after it was cited.",
            "links": [{"relation": "about", "target": "step-6", "status": "confirmed"}],
            "prev": trail.digest(trail.canonical(churn[-1])),
        }
    )
    assert trail.check(churn) == []
    assert trail.merge([churn, trails[FEATURES]])[2] == []


@pytest.mark.parametrize("table", ["nodes", "edges"])
def test_parquet_and_csv_hold_the_same_rows(tmp_path, merged, table):
    columns = {"nodes": trail.NODE_COLUMNS, "edges": trail.EDGE_COLUMNS}[table]
    rows = merged[0] if table == "nodes" else merged[1]
    for suffix in (".parquet", ".csv"):
        trail.write_table(tmp_path / f"{table}{suffix}", columns, rows)

    def text(value) -> str:
        if value is None:
            return ""
        return value.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(value, "strftime") else str(value)

    typed = pq.read_table(tmp_path / f"{table}.parquet")
    assert typed.schema.names == list(columns)
    with (tmp_path / f"{table}.csv").open(newline="") as lines:
        assert [{name: text(value) for name, value in row.items()} for row in typed.to_pylist()] == list(csv.DictReader(lines))

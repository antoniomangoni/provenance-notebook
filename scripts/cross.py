"""Cross-probe demo over the merged example graph.

    python trail.py examples examples
    python trail.py merge examples/graph examples/churn-model-2026-11-11 examples/churn-features-2026-11-12
    uv run python scripts/cross.py examples

Run from the repository root; it reads the Parquet tables, or the CSV ones if merge ran with --csv.
Queries walk back across probes, join data by digest and list forking paths; then it shows what
merge refuses. With ALMANAQUE_REFS set to the path of Almanaque's graph/refs.py, it also shows that
every reference parses under Almanaque's syntax.
"""
import json, os, sys, importlib.util, duckdb
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trail
ex = Path(sys.argv[1]); g = ex / "graph"
db = duckdb.connect()
for table in ("nodes", "edges"):
    if (g / f"{table}.parquet").exists():
        db.execute(f"create view {table} as select * from read_parquet('{g}/{table}.parquet')")
    else:
        db.execute(f"create view {table} as select * from read_csv('{g}/{table}.csv', all_varchar=true)")
def show(title, sql):
    print(f"\n{title}")
    for row in db.execute(sql).fetchall(): print("  ", " | ".join(str(c) for c in row))
show("1. Why did retention start where it did? Walk back from its plan, across probes", """
  with recursive back(id, depth, via, asserted) as (
    select 'retention/probe:churn-features-2026-11-12#step-1', 0, '', ''
    union all
    select e.target, b.depth + 1, e.relation || ' (' || e.status || ')', e.graph
    from back b join edges e on e.source = b.id
    where e.relation in ('triggered_by', 'supersedes', 'tests') and b.depth < 4)
  select depth, via, split_part(id, '#', 1) as probe, n.kind, n.label
  from back b join nodes n using (id) order by depth""")
show("2. The same data under different names: used edges joined on digest", """
  select distinct a.target, b.target, left(a.digest, 19) || '…'
  from edges a join edges b on a.digest = b.digest and a.target < b.target
  where a.relation = 'used' and b.relation = 'used'""")
show("3. Forking paths on that data: every plan tested on it, in any probe, with its outcome", """
  select split_part(p.id, '#', 1) as probe, p.label as plan, o.label as observed, o.outcome
  from edges u
  join edges i on i.source = u.source and i.relation = 'implements'
  join nodes p on p.id = i.target
  join edges ob on ob.target = u.source and ob.relation = 'observes'
  join nodes o on o.id = ob.source
  where u.relation = 'used' and u.digest = (select digest from edges where target = 'churn/file:data/telco.csv' limit 1)
  order by o.at""")

print("\n4. What merge refuses")
trails = [trail.load(ex / "churn-model-2026-11-11"), trail.load(ex / "churn-features-2026-11-12")]
def rechain(s, start):
    for i in range(start, len(s)): s[i]["prev"] = trail.digest(trail.canonical(s[i - 1]))
def attempt(label, churn, retention):
    found = trail.check(churn) + trail.check(retention)
    print(f"   {label}: check {found or 'passes'}; merge {trail.merge([churn, retention])[2] or 'passes'}")
churn, ret = json.loads(json.dumps(trails))
churn[3]["measures"][0]["value"] = 0.9; churn[3]["checks"][1] = {"expectation": "auc-floor", "measured": 0.9, "held": True}
churn[3]["outcome"] = "as_expected"; rechain(churn, 4)
attempt("churn rewritten at step 3 and re-chained", churn, ret)
churn, ret = json.loads(json.dumps(trails))
ret[1]["links"][0]["target"] = ret[1]["links"][0]["target"].replace("step-6", "step-4"); rechain(ret, 2)
attempt("retention triggered_by churn's plan, not an observation", churn, ret)
churn, ret = json.loads(json.dumps(trails))
print(f"   retention merged without churn: check {trail.check(ret) or 'passes'}; merge {trail.merge([ret])[2]}")
churn, ret = json.loads(json.dumps(trails))
churn.append({"version": 2, "id": "step-8", "seq": 8, "trail": churn[0]["trail"], "at": "2026-11-13T09:00:00Z",
              "kind": "note", "by": "human:antonio", "summary": "Later note", "text": "Written after retention cited churn.",
              "links": [{"relation": "about", "target": "step-6", "status": "confirmed"}],
              "prev": trail.digest(trail.canonical(churn[7]))})
attempt("churn grew after it was cited", churn, ret)

if not os.environ.get("ALMANAQUE_REFS"):
    sys.exit(0)
spec = importlib.util.spec_from_file_location("refs", os.environ["ALMANAQUE_REFS"])
refs = importlib.util.module_from_spec(spec); spec.loader.exec_module(refs)
refs.KINDS.update({k: "" for k in ("probe", "file", "agent", "runner", "human")})
ids = {row[0] for row in db.execute("select id from nodes union select target from edges").fetchall()}
ids |= {l["target"] for s in trails[1] for l in s.get("links", []) if "probe:" in l["target"]}
bad = [i for i in ids if str(refs.parse(i)) != i]
print(f"\n5. {len(ids)} references round-trip through almanaque's parser:", "all" if not bad else bad)

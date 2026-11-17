#!/usr/bin/env bash
# Builds the pages a reader opens first.
#
#     scripts/site.sh [OUT]        # OUT defaults to site/
#
# Every page is generated from files in this repository, with no model and no network:
#   index.html    what each page is
#   trail.html    the reviewer's page of the live trail, with code diffs and what each run opened
#   fleet.html    the page of a trail whose commands were traced as they ran
#   map.html      the research map and its trails
#   synthetic.html the second project's map, whose routes Kimi K3.1 Pro chose
#   *.txt         each project's belief report, and the second project's forecast scores
#   example.html  the constructed example, whose step 4 is a change of approach
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-$REPO/site}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
cd "$REPO"
MAP=research/madelon-reanalysis
CODE=$(mktemp -d)
trap 'rm -rf "$CODE"' EXIT

# The code snapshots travel as a git bundle beside the trail; the page reads the diffs from a clone.
git clone -q -b notebook/madelon-2026-11-15-1 live/madelon-2026-11-15-1/code.bundle "$CODE/live-1"
uv run --quiet python trail.py view live/madelon-2026-11-15-1 --store live/store --code "$CODE/live-1" \
	--reads "$MAP/retrace/madelon-2026-11-15-1.json" --sealed data/heldout.csv --out "$OUT/trail.html"
uv run --quiet python trail.py view live/madelon-fleet2-vote --store live/store --sealed data/heldout.csv --out "$OUT/fleet.html"
uv run --quiet python trail.py view examples/churn-model-2026-11-11 --store examples/store --out "$OUT/example.html"
uv run --quiet python project.py page "$MAP/map" --live live --out "$OUT/map.html"
SYN=research/synthetic-interactions
uv run --quiet python project.py page "$SYN/map" --live live --out "$OUT/synthetic.html"
cp "$MAP/beliefs.txt" "$OUT/madelon-beliefs.txt"
cp "$SYN/beliefs.txt" "$OUT/synthetic-beliefs.txt"
cp "$SYN/forecasts/scores.txt" "$OUT/synthetic-scores.txt"

cat >"$OUT/index.html" <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Provenance notebook</title>
<style>
:root{color-scheme:light dark;--bg:#faf9f6;--surface:#fff;--fg:#1f1e1c;--muted:#64625d;--line:#e2dfd8;--accent:#2b5c8f}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--surface:#1c1c1a;--fg:#e9e7e2;--muted:#a19f99;--line:#34332f;--accent:#8fb6e0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:44rem;margin:0 auto;padding:2.5rem 1rem 4rem}
h1{font-size:1.75rem;line-height:1.25;margin:0 0 .5rem}
p{margin:.4rem 0}
.lead{color:var(--muted);margin-bottom:1.5rem}
a{color:var(--accent)}
.card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;margin:1rem 0;text-decoration:none;color:inherit}
.card:hover,.card:focus-visible{border-color:var(--accent)}
.card strong{color:var(--accent);font-size:1.05rem}
.card span{display:block;color:var(--muted);font-size:.92rem;margin-top:.2rem}
.more{color:var(--muted);font-size:.92rem;margin:-.4rem 0 1rem 1.1rem}
</style></head><body><main>
<h1>Provenance notebook</h1>
<p class="lead">A record of an AI-assisted research task that a reviewer who was not there can read and check. Each page below is generated from the step files in the <a href="https://github.com/antoniomangoni/provenance-notebook">repository</a>; only this index is written by hand. Start with the first.</p>
<a class="card" href="trail.html"><strong>1. The reviewer's page of a live trail</strong>
<span>An agent re-analyses an inherited result on the Madelon data. Read why the plan changed at step 14, which code each run used, and which runs had opened the held-out file before each plan was proposed.</span></a>
<a class="card" href="map.html"><strong>2. The research map</strong>
<span>Fifteen trails toward three goals, drawn as a metro map: the milestones each route passes, the trails that reached them, and every credit that was later withdrawn, with why.</span></a>
<p class="more">How sure each mark is: <a href="madelon-beliefs.txt">the belief report</a> (text). Every ✓ and ✗ at the floor is within noise of it.</p>
<a class="card" href="synthetic.html"><strong>3. A second project, with a known truth</strong>
<span>Synthetic data, so each analysis's true score is known. Before each of three rounds of three agents, a second model (Kimi K3.1 Pro) forecast every open milestone and chose the routes. Over 18 settled forecasts, no forecaster beat a coin flip.</span></a>
<p class="more"><a href="synthetic-scores.txt">The forecast scores</a> and <a href="synthetic-beliefs.txt">the belief report</a> (text); <a href="https://github.com/antoniomangoni/provenance-notebook/blob/main/research/synthetic-interactions/README.md">what each round showed</a>.</p>
<a class="card" href="fleet.html"><strong>4. A trail traced as it ran</strong>
<span>One of three agents that worked at the same time and built on each other's steps. Each run shows the files it opened, recorded while it happened.</span></a>
<a class="card" href="example.html"><strong>5. The constructed example</strong>
<span>Eight steps written to stage the brief's question: why did they change approach at step 4?</span></a>
</main></body></html>
EOF
echo "site.sh: wrote $OUT/index.html, five pages and three reports"

#!/usr/bin/env bash
# Runs several routes of a research map at once, one agent each, all able to read the live map.
#
#     scripts/fleet.sh MAP PREFIX ROUTE... [-- pi options]
#
# For each ROUTE it writes a brief into MAP/../briefs/PREFIX-ROUTE (project.py brief --with the others),
# then starts scripts/live.sh on it as trail PREFIX-ROUTE with NOTEBOOK_MAP and NOTEBOOK_REPO set,
# so capture gives the agent its project_map tool. It waits for every agent and prints each
# trail's check. Watch it with: uv run python project.py serve MAP --live live
# Each agent's launcher output goes to $TMPDIR/fleet-PREFIX-ROUTE.log. NOTEBOOK_DEMO is the demo
# the briefs start from (demo/); NOTEBOOK_LIVE is where trails go (live/).
set -euo pipefail

die() { echo "fleet.sh: $*" >&2; exit 2; }

[[ $# -ge 3 ]] || die "usage: scripts/fleet.sh MAP PREFIX ROUTE... [-- pi options]"
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MAP=$(cd "$1" && pwd)
PREFIX=$2
shift 2
ROUTES=()
while [[ $# -gt 0 && $1 != -- ]]; do ROUTES+=("$1"); shift; done
[[ $# -gt 0 ]] && shift
[[ ${#ROUTES[@]} -le 3 ]] || die "at most three agents at once (spec 7); ask before running more"
LIVE=${NOTEBOOK_LIVE:-$REPO/live}
BRIEFS=$(dirname "$MAP")/briefs
WITH=$(IFS=,; echo "${ROUTES[*]}")

for route in "${ROUTES[@]}"; do
	(cd "$REPO" && uv run --quiet python project.py brief "$MAP" "$route" --out "$BRIEFS/$PREFIX-$route" --live "$LIVE" --with "$WITH" --demo "${NOTEBOOK_DEMO:-$REPO/demo}")
done

PIDS=()
for route in "${ROUTES[@]}"; do
	log=${TMPDIR:-/tmp}/fleet-$PREFIX-$route.log
	NOTEBOOK_MAP=$MAP NOTEBOOK_REPO=$REPO "$REPO/scripts/live.sh" "$BRIEFS/$PREFIX-$route" "$PREFIX-$route" "$@" >"$log" 2>&1 &
	PIDS+=($!)
	echo "fleet.sh: $PREFIX-$route started (log $log)"
done

STATUS=0
for i in "${!ROUTES[@]}"; do
	if wait "${PIDS[$i]}"; then echo "fleet.sh: $PREFIX-${ROUTES[$i]} checks"; else echo "fleet.sh: $PREFIX-${ROUTES[$i]} does not check"; STATUS=1; fi
done
exit $STATUS

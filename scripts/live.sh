#!/usr/bin/env bash
# Runs one task under capture.
#
#     scripts/live.sh DEMO_DIR NAME [pi options]
#
# DEMO_DIR holds task.json, prompt.md and workspace/. The workspace is copied to a new git
# repository outside this one, and Pi runs there with capture loaded. Under live/NAME (or
# $NOTEBOOK_LIVE/NAME) it leaves the trail in steps/, Pi's transcript in session/ and
# events.jsonl, and the code snapshots in code.bundle; metrics files go to live/store by digest.
# NOTEBOOK_WALL is the most seconds Pi may run (1,800). The exit status is the trail's check.
set -euo pipefail

die() { echo "live.sh: $*" >&2; exit 2; }

[[ $# -ge 2 ]] || die "usage: scripts/live.sh DEMO_DIR NAME [pi options]"
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f $1/task.json && -f $1/prompt.md && -d $1/workspace ]] || die "$1 needs task.json, prompt.md and workspace/"
DEMO=$(cd "$1" && pwd)
NAME=$2
shift 2
WALL=${NOTEBOOK_WALL:-1800}
# Pi runs in the workspace, so a relative path among its options would be looked for there. An
# extension named relative to where the launcher was called is made absolute; so is the script
# the scripted provider replays.
OPTIONS=()
while [[ $# -gt 0 ]]; do
	OPTIONS+=("$1")
	if [[ ($1 == -e || $1 == --extension) && $# -ge 2 ]]; then
		shift
		if [[ $1 != /* && -e $1 ]]; then OPTIONS+=("$PWD/$1"); else OPTIONS+=("$1"); fi
	fi
	shift
done
if [[ -n ${NOTEBOOK_SCRIPT:-} && $NOTEBOOK_SCRIPT != /* ]]; then
	export NOTEBOOK_SCRIPT=$PWD/$NOTEBOOK_SCRIPT
fi
[[ $NAME =~ ^[a-z0-9]+(-[a-z0-9]+)*$ && ${#NAME} -le 100 ]] || die "NAME is lower-case letters, digits and single hyphens"
[[ $WALL =~ ^[1-9][0-9]*$ ]] || die "NOTEBOOK_WALL is a positive number of seconds"
mkdir -p "${NOTEBOOK_LIVE:-$REPO/live}"
ROOT=$(cd "${NOTEBOOK_LIVE:-$REPO/live}" && pwd)
[[ ! -e $ROOT/$NAME ]] || die "$ROOT/$NAME exists; a trail is written once"
mkdir -p "$ROOT/$NAME" "$ROOT/store"

# The workspace is a repository of its own: capture snapshots it, and the agent's work stays out of this one.
WORK=$(mktemp -d "${TMPDIR:-/tmp}/notebook-$NAME.XXXXXX")
[[ $(cd "$WORK" && pwd -P)/ != "$(cd "$REPO" && pwd -P)"/* ]] || die "the workspace must be outside this repository; set TMPDIR"
tar -C "$DEMO/workspace" --exclude=./out --exclude=./.venv -cf - . | tar -C "$WORK" -xf -
git -C "$WORK" init -q
printf 'out/\n.venv/\n' >> "$WORK/.git/info/exclude"
git -C "$WORK" add -A
git -C "$WORK" -c user.name=notebook -c user.email=notebook@localhost -c commit.gpgsign=false commit -q -m "The workspace as the task starts"
if [[ -f $WORK/pyproject.toml ]]; then
	(cd "$WORK" && uv sync --quiet)
fi

# Pi's status does not decide anything: a session that crashed or ran out of time still left a trail to check.
# Its prompt is the message, so standard input is closed: in print mode Pi would otherwise wait on it.
set +e
(
	cd "$WORK"
	NOTEBOOK_TASK=$DEMO/task.json NOTEBOOK_TRAIL=$ROOT/$NAME NOTEBOOK_STORE=$ROOT/store \
		timeout --kill-after=5 "$WALL" "$REPO/capture/node_modules/.bin/pi" -p --mode json --no-context-files \
		-e "$REPO/capture/capture.ts" --append-system-prompt "$(cat "$REPO/capture/protocol.md")" \
		--session-dir "$ROOT/$NAME/session" ${OPTIONS[@]+"${OPTIONS[@]}"} "$(cat "$DEMO/prompt.md")"
) < /dev/null > "$ROOT/$NAME/events.jsonl"
status=$?
set -e
if [[ $status -eq 124 || $status -eq 137 ]]; then
	echo "live.sh: Pi was stopped at the wall clock of $WALL seconds"
elif [[ $status -ne 0 ]]; then
	echo "live.sh: Pi exited with status $status"
fi

if git -C "$WORK" rev-parse --quiet --verify "refs/heads/notebook/$NAME" > /dev/null; then
	git -C "$WORK" bundle create --quiet "$ROOT/$NAME/code.bundle" "refs/heads/notebook/$NAME"
else
	echo "live.sh: no run was recorded, so there is no code snapshot to bundle"
fi
echo "live.sh: the workspace is $WORK"
# A trail of no steps has no problems, so its absence is checked here: capture did not load.
[[ -f $ROOT/$NAME/steps/step-0.json ]] || { echo "live.sh: no step was written; capture did not start"; exit 1; }
uv run --quiet --project "$REPO" python "$REPO/trail.py" check "$ROOT/$NAME" --store "$ROOT/store"

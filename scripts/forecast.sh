#!/usr/bin/env bash
# Asks a model each question that beliefs.py questions wrote, once, with no tools and no files.
#
#     scripts/forecast.sh DIR -- [pi options]
#
# DIR holds q*.md; each answer goes to DIR/answers/q*.txt, and a question already answered is not
# asked again. Pi reads the provider's key from its own models file (PI_CODING_AGENT_DIR); nothing
# here reads or passes a key. Then: beliefs.py collect DIR --by ACTOR --out FILE.
set -euo pipefail

die() { echo "forecast.sh: $*" >&2; exit 2; }
[[ $# -ge 1 ]] || die "usage: scripts/forecast.sh DIR -- [pi options]"
DIR=$1
shift
[[ ${1:-} == "--" ]] && shift
REPO=$(cd "$(dirname "$0")/.." && pwd)
PI=$REPO/capture/node_modules/.bin/pi
[[ -x $PI ]] || die "Pi is not installed: run npm ci in capture/"
[[ -f $DIR/questions.json ]] || die "$DIR has no questions.json: run beliefs.py questions first"
SYSTEM="You forecast the outcomes of steps in research projects. You have no tools. Answer only in the format the message asks for."
WALL=${NOTEBOOK_FORECAST_WALL:-180}

mkdir -p "$DIR/answers"
asked=0 failed=0
for question in "$DIR"/q*.md; do
	name=$(basename "$question" .md)
	answer=$DIR/answers/$name.txt
	[[ -s $answer ]] && continue
	asked=$((asked + 1))
	if timeout --kill-after=5 "$WALL" "$PI" -p --no-tools --no-extensions --no-skills --no-context-files --no-session \
		--system-prompt "$SYSTEM" "$@" "$(cat "$question")" < /dev/null > "$answer.part" 2> "$DIR/answers/$name.err"; then
		mv "$answer.part" "$answer"
		rm -f "$DIR/answers/$name.err"
	else
		failed=$((failed + 1))
		echo "forecast.sh: $name failed; see $DIR/answers/$name.err" >&2
		rm -f "$answer.part"
	fi
done
echo "forecast.sh: asked $asked, $failed failed"

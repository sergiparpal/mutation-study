#!/bin/bash
#
# Seventh campaign, generation: every bug of the list in both arms, in the
# order the protocol fixes (data/campaign7/PROTOCOL.md). The sixth campaign's
# bin/run-campaign6.sh with the arms, the paths and the generator changed.
#
#   - bugs in the order of data/campaign7/subjects.txt
#   - both arms of a bug before the next bug, so that a campaign cut short has
#     both arms of what it covered
#   - which arm goes first alternates: f7 first for the 1st, 3rd, 5th ... bug,
#     m7 first for the 2nd, 4th, 6th ...
#   - one agent at a time
#
# It can be run again at any point: a run that has a .status is not repeated.
# It stops, without touching the remaining bugs, when a run ends without one.
# That happens in two cases, both about the plan's usage limits: the generator
# refused to start a run because usage had reached its threshold, or a limit
# cut the run short. Run it again after the limit resets.
#
# Everything a run needs is fixed here once and handed to the generator: the
# CLI's versioned binary, so an update during the campaign changes nothing, and
# the model id. The generator refuses to run from scripts that differ from the
# last commit.
#
# Usage:
#   ./bin/run-campaign7.sh                 # the bugs, into data/campaign7
#   DRY=1 OUT=/tmp/x ./bin/run-campaign7.sh data/campaign7/subjects.txt 3
#       no model call: the developers' trigger-test classes stand in for the
#       agent's suite; the optional number limits the run to the first bugs
#   OUT=data/campaign7/pilot ./bin/run-campaign7.sh data/campaign7/pilot/subjects.txt
#       the pilot: the second campaign's three pilot bugs, outside the sample

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

SUBJECTS=${1:-data/campaign7/subjects.txt}
LIMIT=${2:-0}
OUT=${OUT:-data/campaign7}
DRY=${DRY:-}
export TZ=America/Los_Angeles
export MODEL=${MODEL:-claude-sonnet-5}
D4J_HOME=${D4J_HOME:-$HOME/defects4j}
export PATH="$D4J_HOME/framework/bin:$PATH"

[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
command -v defects4j >/dev/null || { echo "defects4j not found under $D4J_HOME"; exit 1; }
if [ -z "$DRY" ]; then
    command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
    CLAUDE_BIN=$(readlink -f "$(command -v claude)")
    export CLAUDE_BIN
    echo "CLI:    $("$CLAUDE_BIN" --version 2>/dev/null | head -1)  ($CLAUDE_BIN)"
fi
echo "model:  $MODEL"
echo "commit: $(git rev-parse HEAD 2>/dev/null)"
echo "start:  $(date -u +%FT%TZ)"
echo

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
mkdir -p "$OUT_ABS"
LOG=$OUT_ABS/generation.log

i=0
while read -r TAG _rest <&3; do
    TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
    [ -z "$TAG" ] && continue
    case "$TAG" in \#*) continue ;; esac

    i=$((i + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$i" -gt "$LIMIT" ]; then break; fi
    if [ $((i % 2)) -eq 1 ]; then ORDER="f7 m7"; else ORDER="m7 f7"; fi

    for ARM in $ORDER; do
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            continue
        fi
        ARM=$ARM ONLY=$TAG OUT=$OUT DRY=$DRY ./bin/generate-campaign7.sh "$SUBJECTS" >> "$LOG" 2>&1 < /dev/null
        RC=$?
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            printf '%2d  %-10s %s  %s\n' "$i" "$TAG" "$ARM" "$(cat "$OUT_ABS/runs-$ARM/$TAG.status")"
        else
            echo
            echo "STOPPED at $TAG ($ARM): the run did not complete (generator exit $RC)."
            echo "See the end of ${LOG#$ROOT/}. Run this script again after the usage limit resets."
            echo "end:    $(date -u +%FT%TZ)"
            exit 3
        fi
    done
done 3< "$SUBJECTS"

echo
for ARM in f7 m7; do
    printf '%s: %s runs with a status, %s packaged\n' "$ARM" \
        "$(ls "$OUT_ABS/runs-$ARM"/*.status 2>/dev/null | wc -l)" \
        "$(ls "$OUT_ABS/suites"/*-"$ARM".tar.bz2 2>/dev/null | wc -l)"
done
echo "end:    $(date -u +%FT%TZ)"

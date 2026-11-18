#!/bin/bash
#
# Third campaign, generation: every subject of the list in both arms, in the
# order the protocol fixes (data/campaign3/PROTOCOL.md).
#
#   - subjects in the order of data/campaign3/subjects.txt
#   - both arms of a subject before the next subject, so that a campaign cut
#     short has both arms of what it covered
#   - which arm goes first alternates: m3 first for the 1st, 3rd, 5th ...
#     subject, s3 first for the 2nd, 4th, 6th ...
#   - one agent at a time
#
# It can be run again at any point: a run that has a .status is not repeated.
# It stops, without touching the remaining subjects, when a run ends without
# one. That happens in two cases, both about the plan's usage limits: the
# generator refused to start a run because usage had reached its threshold, or
# a limit cut the run short. Run it again after the limit resets.
#
# Everything a run needs is fixed here once and handed to the generator: the
# CLI's versioned binary, so an update during the campaign changes nothing, and
# the model id. The generator refuses to run from scripts that differ from the
# last commit.
#
# Usage:
#   ./bin/run-campaign3.sh                 # the subjects, into data/campaign3
#   DRY=1 OUT=/tmp/x ./bin/run-campaign3.sh data/campaign3/subjects.txt 3
#       no model call: the developers' tests stand in for the agent's; the
#       optional number limits the run to the first subjects

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

SUBJECTS=${1:-data/campaign3/subjects.txt}
LIMIT=${2:-0}
OUT=${OUT:-data/campaign3}
DRY=${DRY:-}
export TZ=America/Los_Angeles
export MODEL=${MODEL:-claude-sonnet-5}

[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
command -v mvn >/dev/null || { echo "mvn not on PATH"; exit 1; }
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
    if [ $((i % 2)) -eq 1 ]; then ORDER="m3 s3"; else ORDER="s3 m3"; fi

    for ARM in $ORDER; do
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            continue
        fi
        ARM=$ARM ONLY=$TAG OUT=$OUT DRY=$DRY ./bin/generate-postcutoff.sh "$SUBJECTS" >> "$LOG" 2>&1 < /dev/null
        RC=$?
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            printf '%2d  %-26s %s  %s\n' "$i" "$TAG" "$ARM" "$(cat "$OUT_ABS/runs-$ARM/$TAG.status")"
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
for ARM in m3 s3; do
    printf '%s: %s runs with a status, %s packaged\n' "$ARM" \
        "$(ls "$OUT_ABS/runs-$ARM"/*.status 2>/dev/null | wc -l)" \
        "$(ls "$OUT_ABS/suites"/*-"$ARM".tar.bz2 2>/dev/null | wc -l)"
done
echo "end:    $(date -u +%FT%TZ)"

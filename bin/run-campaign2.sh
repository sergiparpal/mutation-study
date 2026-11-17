#!/bin/bash
#
# Second campaign, generation: every bug of the sample in both arms, in the
# order the protocol fixes (data/campaign2/PROTOCOL.md).
#
#   - bugs in the order of data/sample.txt
#   - both arms of a bug before the next bug, so that a campaign cut short has
#     both arms of what it covered
#   - which arm goes first alternates: m2 first for the 1st, 3rd, 5th ... bug,
#     s2 first for the 2nd, 4th, 6th ...
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
#   ./bin/run-campaign2.sh                 # the sample, into data/campaign2
#   DRY=1 OUT=/tmp/x ./bin/run-campaign2.sh data/sample.txt 3
#       no model call: the first campaign's suites stand in for the agent's;
#       the optional number limits the run to the first bugs

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
OUT=${OUT:-data/campaign2}
DRY=${DRY:-}
export TZ=America/Los_Angeles
export MODEL=${MODEL:-claude-sonnet-5}

[ -f "$SAMPLE" ] || { echo "sample file not found: $SAMPLE"; exit 1; }
command -v defects4j >/dev/null || { echo "defects4j not on PATH"; exit 1; }
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
while IFS=, read -r P B _rest <&3; do
    P=$(echo "${P:-}" | tr -d '[:space:]')
    B=$(echo "${B:-}" | tr -d '[:space:]')
    [ -z "$P" ] && continue
    case "$P" in \#*) continue ;; esac
    TAG="${P}-${B}"

    i=$((i + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$i" -gt "$LIMIT" ]; then break; fi
    if [ $((i % 2)) -eq 1 ]; then ORDER="m2 s2"; else ORDER="s2 m2"; fi

    for ARM in $ORDER; do
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            continue
        fi
        if [ -n "$DRY" ]; then
            if [ "$ARM" = "m2" ]; then STANDIN=agent; else STANDIN=spec; fi
            ARM=$ARM ONLY=$TAG OUT=$OUT DRY=$STANDIN ./bin/generate-suites.sh "$SAMPLE" >> "$LOG" 2>&1 < /dev/null
        else
            ARM=$ARM ONLY=$TAG OUT=$OUT ./bin/generate-suites.sh "$SAMPLE" >> "$LOG" 2>&1 < /dev/null
        fi
        RC=$?
        if [ -f "$OUT_ABS/runs-$ARM/$TAG.status" ]; then
            printf '%2d  %-8s %s  %s\n' "$i" "$TAG" "$ARM" "$(cat "$OUT_ABS/runs-$ARM/$TAG.status")"
        else
            echo
            echo "STOPPED at $TAG ($ARM): the run did not complete (generator exit $RC)."
            echo "See the end of ${LOG#$ROOT/}. Run this script again after the usage limit resets."
            echo "end:    $(date -u +%FT%TZ)"
            exit 3
        fi
    done
done 3< "$SAMPLE"

echo
for ARM in m2 s2; do
    printf '%s: %s runs with a status, %s packaged\n' "$ARM" \
        "$(ls "$OUT_ABS/runs-$ARM"/*.status 2>/dev/null | wc -l)" \
        "$(ls "$OUT_ABS/suites"/*-"$ARM".1.tar.bz2 2>/dev/null | wc -l)"
done
echo "end:    $(date -u +%FT%TZ)"

#!/bin/bash
#
# Collect raw Major mutation artifacts for every bug in the sample.
#
# For each bug, on the FIXED version:
#   - full developer test suite      -> kill_full.csv
#   - each trigger test in isolation -> kill_trigger_<n>.csv
#   - the mutant catalogue           -> mutants.log
#   - the fix diff (buggy vs fixed)  -> fix.diff
#
# Slow: two or more mutation runs per bug. Idempotent — a bug whose directory
# contains a `done` marker is skipped, so the script can be interrupted and
# resumed, and re-run after adding bugs to the sample.
#
# Analysis lives in analyze-mutation.py, deliberately separate: parsing bugs
# should never cost another hour of defects4j runs.
#
# Usage:
#   ./bin/run-mutation.sh                  # whole sample
#   ./bin/run-mutation.sh data/sample.txt 3  # first 3 bugs only

set -uo pipefail

SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
OUT=data/raw

command -v defects4j >/dev/null || { echo "defects4j not on PATH"; exit 1; }
[ -f "$SAMPLE" ] || { echo "sample file not found: $SAMPLE"; exit 1; }
[ "${TZ:-}" = "America/Los_Angeles" ] || echo "WARNING: TZ is not America/Los_Angeles — results may be unreproducible"

mkdir -p "$OUT"
n=0

while IFS=, read -r P B _rest; do
    P=$(echo "${P:-}" | tr -d '[:space:]')
    B=$(echo "${B:-}" | tr -d '[:space:]')
    [ -z "$P" ] && continue
    case "$P" in \#*) continue ;; esac

    n=$((n + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$n" -gt "$LIMIT" ]; then break; fi

    d="$OUT/${P}-${B}"
    if [ -f "$d/done" ]; then
        echo "[$P-$B] already collected — skipping"
        continue
    fi

    mkdir -p "$d"
    rm -f "$d/error" "$d/done"

    WF=/tmp/mut_${P}_${B}_f
    WB=/tmp/mut_${P}_${B}_b

    fail() { echo "[$P-$B] $1"; echo "$1" > "$d/error"; }

    # ---- checkout both versions -------------------------------------------
    echo "[$P-$B] checkout"
    rm -rf "$WF" "$WB"
    if ! defects4j checkout -p "$P" -v "${B}f" -w "$WF" >/dev/null 2>&1; then
        fail "checkout of ${B}f failed"; continue
    fi
    if ! defects4j checkout -p "$P" -v "${B}b" -w "$WB" >/dev/null 2>&1; then
        fail "checkout of ${B}b failed"; continue
    fi

    # ---- the fix diff, to know which lines the fix ADDS --------------------
    SRC=$(cd "$WF" && defects4j export -p dir.src.classes 2>/dev/null | grep -v '^Running' | tail -1)
    if [ -z "$SRC" ]; then
        fail "could not resolve dir.src.classes"; continue
    fi
    echo "$SRC" > "$d/src_dir.txt"
    diff -ru "$WB/$SRC" "$WF/$SRC" > "$d/fix.diff"

    # ---- trigger tests -----------------------------------------------------
    (cd "$WF" && defects4j export -p tests.trigger) 2>/dev/null \
        | grep '::' > "$d/triggers.txt"
    if [ ! -s "$d/triggers.txt" ]; then
        fail "no trigger tests found"; continue
    fi

    if ! (cd "$WF" && defects4j compile) >/dev/null 2>&1; then
        fail "compile failed"; continue
    fi

    # ---- full suite (relevant tests only; see data/README.md) --------------
    echo "[$P-$B] mutation, relevant test suite"
    if ! (cd "$WF" && defects4j mutation -r) > "$d/summary_full.txt" 2>&1; then
        fail "full mutation run failed"; continue
    fi
    cp "$WF/kill.csv"    "$d/kill_full.csv" 2>/dev/null || { fail "no kill.csv after full run"; continue; }
    cp "$WF/mutants.log" "$d/mutants.log"   2>/dev/null || { fail "no mutants.log"; continue; }

    # ---- one run per trigger test -----------------------------------------
    i=0
    while read -r T; do
        [ -z "$T" ] && continue
        i=$((i + 1))
        echo "[$P-$B] mutation, trigger $i: $T"
        if (cd "$WF" && defects4j mutation -t "$T") > "$d/summary_trigger_$i.txt" 2>&1; then
            cp "$WF/kill.csv" "$d/kill_trigger_$i.csv" 2>/dev/null
        else
            echo "$T" >> "$d/failed_triggers.txt"
        fi
    done < "$d/triggers.txt"

    if ! ls "$d"/kill_trigger_*.csv >/dev/null 2>&1; then
        fail "every trigger run failed"; continue
    fi

    date -Iseconds > "$d/done"
    rm -rf "$WF" "$WB"
    echo "[$P-$B] collected"
done < "$SAMPLE"

echo
echo "Collected: $(ls -d $OUT/*/ 2>/dev/null | wc -l) bug directories"
echo "Errors:    $(ls $OUT/*/error 2>/dev/null | wc -l)"
echo "Next: ./bin/analyze-mutation.py"

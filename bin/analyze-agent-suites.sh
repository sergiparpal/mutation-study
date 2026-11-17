#!/bin/bash
#
# Study B, phase 2: measure the packaged agent suites.
#
# The three defects4j analysis scripts take a FLAT directory of archives and
# process every archive matching the given project, so this runs once per
# project rather than once per bug.
#
# Naming discovered from gen_tests output:
#   <Project>-<bid><b|f>-<generator>[-<variant>].<id>.tar.bz2
# The archive contains the package directories from the root (./org/...), with
# no src/test/java prefix. The directory passed with -d must be flat; the
# nested layout gen_tests writes to (Project/generator/id/) is silently ignored
# and yields header-only CSVs.
#
# MUTATION SCORE
# --------------
# run_mutation.pl's table is not used as it stands. Its mut_killed column is
# every mutant that is not LIVE, which includes the UNCOV ones no test ever
# executes, and its mut_covered column is simply every mutant. The final merge
# step (merge-agent-metrics.py) recomputes both from the kill.csv that
# Defects4J copies into mutation_log/, and keeps the table's own figure as
# mut_killed_d4j.
#
# BROKEN SUITES
# -------------
# run_bug_detection.pl classifies a suite as Broken when it does not compile
# on either revision or has a failing test on the revision it was generated
# for. Such a suite was never validly run against the buggy revision. It is
# not a non-detection and must not be counted as one.
#
# This script DELETES the tables and logs under the results directory before
# it starts: the Defects4J scripts append to their tables. It leaves
# remeasured/ alone (see remeasure-cli-evosuite.sh). To rebuild only the merged
# CSV from results that already exist, run merge-agent-metrics.py on its own.
#
# Usage:
#   ./bin/analyze-agent-suites.sh                    # data/agent-suites
#   ./bin/analyze-agent-suites.sh /tmp/other/suites
#   D4J_BIN=/path/to/defects4j/framework/bin ./bin/analyze-agent-suites.sh
#   OUT=data/campaign2/results ./bin/analyze-agent-suites.sh data/campaign2/suites

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)

SUITES=${1:-data/agent-suites}
OUT=${OUT:-data/agent-results}
D4J_BIN=${D4J_BIN:-$HOME/defects4j/framework/bin}

[ -x "$D4J_BIN/run_bug_detection.pl" ] || { echo "no Defects4J scripts under $D4J_BIN (set D4J_BIN)"; exit 1; }

[ -d "$SUITES" ] || { echo "no suite directory: $SUITES"; exit 1; }
ls "$SUITES"/*.tar.bz2 >/dev/null 2>&1 || { echo "no archives in $SUITES"; exit 1; }

# the analysis scripts append; start clean so reruns are not double-counted
mkdir -p "$OUT"
for item in bug_detection coverage mutation bug_detection_log coverage_log \
            mutation_log agent-metrics.csv; do
    rm -rf "${OUT:?}/$item"
done
rm -f "$OUT"/run_*.log

SUITES_ABS=$(cd "$SUITES" && pwd)
OUT_ABS=$(cd "$OUT" && pwd)

PROJECTS=$(ls "$SUITES"/*.tar.bz2 | xargs -n1 basename | cut -d- -f1 | sort -u)
echo "projects: $(echo $PROJECTS | tr '\n' ' ')"

for P in $PROJECTS; do
    echo
    echo "=== $P ==="
    for STEP in run_bug_detection run_coverage run_mutation; do
        echo "--- $STEP"
        "$D4J_BIN/$STEP.pl" -p "$P" -d "$SUITES_ABS" -o "$OUT_ABS" \
            > "$OUT_ABS/${STEP}_${P}.log" 2>&1 \
            || echo "    $STEP failed for $P — see $OUT/${STEP}_${P}.log"
    done
done

echo
echo "--- merged ---"
# Defects4J's mutation table counts uncovered mutants as killed, so the merge
# recomputes the mutation columns from Major's kill.csv. See the header of
# merge-agent-metrics.py for the detail.
python3 "$ROOT/bin/merge-agent-metrics.py" "$OUT_ABS"

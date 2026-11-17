#!/bin/bash
#
# Re-measure the EvoSuite suites of Commons Cli with one line of Defects4J
# corrected.
#
# WHY
# ---
# Five of the six EvoSuite suites on Cli are classified Broken by
# run_bug_detection.pl and have no coverage figure. They never ran: the suite
# fails to load on both revisions with
#     java.lang.NoClassDefFoundError: org/hamcrest/SelfDescribing
# The cause is in Defects4J v3.0.1, not in the suites. Its build file for the
# project, framework/projects/Cli/Cli.build.xml, sets
#     junit.jar = file://${d4j.home}/framework/projects/lib/junit-4.12.jar
# and the framework does not ship that file. It ships
# junit-4.12-hamcrest-1.3.jar. So a generated JUnit 4 test has Hamcrest only
# where the project supplies it, and the older Cli revisions ship JUnit 3.8.
#
# WHAT THIS DOES
# --------------
# Nothing is changed in the Defects4J installation. Defects4J reads its
# per-project files from $PROJECTS_DIR when that is set, so this script builds
# a directory of symbolic links to the installation's own projects/ in which
# Cli.build.xml alone is a copy, with that one path corrected, and runs
# run_bug_detection.pl and run_coverage.pl through it.
#
# Two runs:
#   1. the six EvoSuite suites        -> <out>/                (the result)
#   2. every Cli suite of every arm   -> <out>/control/        (the check)
# The control shows what the correction does to suites that already ran. It
# should do nothing: on 2026-11-17 all 16 came out as published.
#
# bin/merge-agent-metrics.py applies the rows of <out>/ that differ from the
# stock tables and marks them in the `harness` column. The stock tables and
# logs stay as Defects4J wrote them.
#
# Mutation analysis is not repeated: those suites ran under the mutation
# harness as they were.
#
# Usage:
#   ./bin/remeasure-cli-evosuite.sh
#   D4J_HOME=/path/to/defects4j ./bin/remeasure-cli-evosuite.sh

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
D4J_HOME=${D4J_HOME:-$HOME/defects4j}
SUITES=$ROOT/data/agent-suites
OUT=$ROOT/data/agent-results/remeasured/cli-junit-fix
REAL=$D4J_HOME/framework/projects
BIN=$D4J_HOME/framework/bin

[ -x "$BIN/run_bug_detection.pl" ] || { echo "no Defects4J under $D4J_HOME (set D4J_HOME)"; exit 1; }
[ -f "$REAL/lib/junit-4.12-hamcrest-1.3.jar" ] || { echo "the jar to point at is missing"; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
OV=$WORK/projects
mkdir -p "$OV/Cli"
for e in "$REAL"/*; do
    n=$(basename "$e"); [ "$n" = Cli ] || ln -s "$e" "$OV/$n"
done
for e in "$REAL"/Cli/*; do
    n=$(basename "$e"); [ "$n" = Cli.build.xml ] || ln -s "$e" "$OV/Cli/$n"
done
sed 's|framework/projects/lib/junit-4.12.jar"|framework/projects/lib/junit-4.12-hamcrest-1.3.jar"|' \
    "$REAL/Cli/Cli.build.xml" > "$OV/Cli/Cli.build.xml"

rm -rf "$OUT"
mkdir -p "$OUT/control"
diff -u --label a/framework/projects/Cli/Cli.build.xml --label b/framework/projects/Cli/Cli.build.xml \
    "$REAL/Cli/Cli.build.xml" "$OV/Cli/Cli.build.xml" > "$OUT/Cli.build.xml.patch" || true
[ "$(grep -c '^[-+][^-+]' "$OUT/Cli.build.xml.patch")" = 2 ] \
    || { echo "expected exactly one changed line in Cli.build.xml"; exit 1; }

export TZ=America/Los_Angeles PROJECTS_DIR="$OV"

FLAT=$WORK/evosuite
mkdir -p "$FLAT"
cp "$SUITES"/Cli-*-evosuite.1.tar.bz2 "$FLAT/"

run() {   # run <suite dir> <out dir>
    for STEP in run_bug_detection run_coverage; do
        echo "--- $STEP -> ${2#$ROOT/}"
        "$BIN/$STEP.pl" -p Cli -d "$1" -o "$2" > "$2/${STEP}_Cli.log" 2>&1 \
            || echo "    $STEP failed, see ${2#$ROOT/}/${STEP}_Cli.log"
    done
}

run "$FLAT" "$OUT"
run "$SUITES" "$OUT/control"

# the control's logs repeat what is already archived; its two tables are enough
rm -rf "$OUT/control/bug_detection_log" "$OUT/control/coverage_log"

(cd "$D4J_HOME" && git describe --tags 2>/dev/null) > "$OUT/defects4j-version.txt" || true
date -u +%F >> "$OUT/defects4j-version.txt"

echo
python3 - "$ROOT" "$OUT" <<'EOF'
import csv, sys
root, out = sys.argv[1:3]
def table(path, cols):
    key = lambda r: (r["project_id"], r["version_id"], r["test_suite_source"])
    return {key(r): tuple(r[c] for c in cols) for r in csv.DictReader(open(path))}
changed = same = 0
for name, cols in (("bug_detection", ("test_classification", "num_trigger")),
                   ("coverage", ("lines_total", "lines_covered", "branches_total", "branches_covered"))):
    stock = table(f"{root}/data/agent-results/{name}", cols)
    control = table(f"{out}/control/{name}", cols)
    for k, v in sorted(control.items()):
        if stock.get(k) == v:
            same += 1
        else:
            changed += 1
            print(f"{name:14s} {k[0]}-{k[1]} {k[2]:9s} {','.join(stock.get(k, ('absent',)))} -> {','.join(v)}")
print(f"\n{changed} table rows differ from the stock measurement, {same} are identical")
EOF
echo "Next: ./bin/merge-agent-metrics.py"

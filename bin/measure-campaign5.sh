#!/bin/bash
#
# Fifth campaign, measurement: does each archived suite tell the two revisions
# of its fault apart, and which way? The fourth campaign's
# bin/measure-campaign4.sh with each arm's revisions in its own order, the
# arms, the paths and the subjects' list changed, and one run added
# (data/campaign5/PROTOCOL.md).
#
# Each suite has its own revision, the one the agent was given and the suite
# was accepted on, and the other one:
#
#   m5   own: the fix commit        other: its parent
#   b5   own: the parent            other: the fix commit
#
# For every subject of the list and every arm with a suite in <OUT>/suites:
#
#   - the fix commit and its parent are exported and built, offline, with
#     nothing of the repository's history (bin/campaign3-lib.sh)
#   - the suite, as the agent wrote it, is compiled on its own against each
#     revision's production classes and the project's test libraries
#   - it is run on its own revision with the tests of its excluded.txt left
#     out, the ones that failed there at acceptance. It has to pass again.
#   - it is run on the other revision with the same tests left out
#   - the tests of excluded.txt, and only those, are run on the other revision
#     (a secondary outcome of the protocol)
#
# The runner is bin/AgentTestRunner.java, the same that accepted the suite.
#
# VERDICTS  (<OUT>/results/verdicts.csv, one row per subject and arm)
#
#   Fail     a test that passes on the suite's own revision fails on the other
#            one. In m5 the fault is detected; in b5 the suite certifies it
#   Pass     every test that passes on the own revision passes on the other
#   Broken   no verdict. The suite does not compile against the other
#            revision, or, run again, does not pass on its own.
#
# The fourth campaign's rules, with the revisions in the arm's order. A test
# that is aborted because an assumption does not hold, or skipped, has not
# failed. A class whose set-up fails on the other revision and not on the own
# one counts as a failing test. A suite that finishes on its own revision and
# does not finish on the other one within RUN_TIMEOUT seconds is `Fail`, with
# the note `timeout`; the analysis is repeated with such verdicts read as
# `Pass`.
#
# The left-out tests are run by leaving out everything else: every method of
# the suite's first run at acceptance (runs-<arm>/<subject>.first.tsv) that is
# not in excluded.txt. A class left out as a whole runs whole. The row counts
# the left-out methods that ran on the other revision, and those of them that
# passed there.
#
# Per suite, in <OUT>/results/:
#   <subject>.<arm>.own.log .own.tsv           the run on its own revision
#   <subject>.<arm>.other.log .other.tsv       the run on the other revision
#   <subject>.<arm>.leftout.log .leftout.tsv   the left-out tests, on the other
#   <subject>.<arm>.compile.log                javac, both revisions
#   <subject>.<arm>.verdict                    the row of verdicts.csv
# and per subject <subject>.fixed.build.log, <subject>.faulty.build.log.
#
# A suite that has a .verdict is not measured again (FORCE=1 to redo).
#
# Usage:
#   ./bin/measure-campaign5.sh                       # data/campaign5
#   ONLY="commons-csv-b5940a642" ./bin/measure-campaign5.sh
#   DRY=1 OUT=/tmp/dry ./bin/measure-campaign5.sh /tmp/subjects.txt
#       the suites of a dry run of the generator: developers' tests, which are
#       not self-contained, so each revision's test sources are on the
#       compiler's source path. In m5 every one of them should come out
#       `Fail`. In b5 they should come out `Fail` only where the fix changed
#       one of their assertions.

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
# the fourth campaign's records, reused as they are, and the pool's clones;
# the library reads both when it is sourced
SUBJECT_ROOTS=${SUBJECT_ROOTS:-data/campaign4/subjects}
MINING=${MINING:-$HOME/code/mining-pool}
. "$ROOT/bin/campaign3-lib.sh"
export TZ=America/Los_Angeles

OUT=${OUT:-data/campaign5}
SUBJECTS=${1:-data/campaign5/subjects.txt}
ONLY=${ONLY:-}
DRY=${DRY:-}
FORCE=${FORCE:-}
ARMS=${ARMS:-"b5 m5"}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}
SRC_TESTS=src/test/java

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
RES=$OUT_ABS/results

command -v mvn   >/dev/null || { echo "mvn not on PATH"; exit 1; }
command -v javac >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
[ -d "$SUITES" ] || { echo "no suites under $SUITES"; exit 1; }
mkdir -p "$RES" "$STAGE_ROOT"

SP=""
[ -n "$DRY" ] && SP="-sourcepath $SRC_TESTS"

# csv_field <text>: quoted if it needs to be
csv() { python3 -c 'import csv, sys; csv.writer(sys.stdout, lineterminator="").writerow(sys.argv[1:])' "$@"; }

while read -r TAG _rest; do
    TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
    [ -z "$TAG" ] && continue
    case "$TAG" in \#*) continue ;; esac
    if [ -n "$ONLY" ]; then
        case " $ONLY " in *" $TAG "*) ;; *) continue ;; esac
    fi

    TODO=""
    for ARM in $ARMS; do
        [ -f "$SUITES/${TAG}-${ARM}.tar.bz2" ] || continue
        if [ -f "$RES/$TAG.$ARM.verdict" ] && [ -z "$FORCE" ]; then continue; fi
        TODO="$TODO $ARM"
    done
    [ -z "$TODO" ] && continue

    D=$(subject_dir "$ROOT" "$TAG") || { echo "[$TAG] no record of this subject"; exit 1; }
    REPO=$(subject_field "$D" project)
    SHA=$(subject_field "$D" sha)

    T=$(mktemp -d "$STAGE_ROOT/measure-XXXXXXXX")
    F="$T/fixed"; B="$T/faulty"; RUNNER="$T/runner"
    echo "[$TAG] staging both revisions"
    if ! stage_revision "$REPO" "$SHA" "$F" "$RES/$TAG.fixed.build.log"; then
        echo "[$TAG] the fixed revision does not build"; rm -rf "$T"; exit 1
    fi
    if ! stage_revision "$REPO" "$SHA~1" "$B" "$RES/$TAG.faulty.build.log"; then
        echo "[$TAG] the faulty revision does not build"; rm -rf "$T"; exit 1
    fi
    if ! build_runner "$F" "$RUNNER" "$ROOT" > "$T/runner.log" 2>&1; then
        echo "[$TAG] the runner does not compile"; cat "$T/runner.log"; rm -rf "$T"; exit 1
    fi

    for ARM in $TODO; do
        if [ "$ARM" = "b5" ]; then
            OWN=$B; OTHER=$F; OWN_KIND=faulty; OTHER_KIND=fixed
        else
            OWN=$F; OTHER=$B; OWN_KIND=fixed; OTHER_KIND=faulty
        fi
        P="$RES/$TAG.$ARM"
        rm -f "$P.own.log" "$P.own.tsv" "$P.other.log" "$P.other.tsv" "$P.leftout.log" "$P.leftout.tsv" \
              "$P.compile.log" "$P.verdict"
        SUITE="$T/suite-$ARM"
        mkdir -p "$SUITE"
        tar -xjf "$SUITES/${TAG}-${ARM}.tar.bz2" -C "$SUITE"
        [ -f "$SUITE/excluded.txt" ] || : > "$SUITE/excluded.txt"
        WRITTEN=$(cd "$SUITE" && find . -name '*AgentTest.java' | sort)
        RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
        SRCS=""
        for f in $WRITTEN; do SRCS="$SRCS $SUITE/${f#./}"; done

        VERDICT=""; NOTE=""; FAILING=""; SEC_O=0; SEC_X=0; OTHER_COMPILED=no; LO_RUN=""; LO_PASS=""

        # ---- its own revision ----
        mkdir -p "$OWN/_m-$ARM"
        if ! (cd "$OWN" && c3_env javac -nowarn $(cat "$OWN/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                -cp "target/classes:$(cat "$OWN/.c3/cp-test")" -d "_m-$ARM" $SRCS) > "$P.compile.log" 2>&1; then
            VERDICT=Broken; NOTE="does not compile against its own revision"
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$OWN" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$OWN")" AgentTestRunner \
                --report "$P.own.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.own.log" 2>&1 < /dev/null
            RC=$?; SEC_O=$SECONDS
            case "$RC" in
                0) ;;
                124|137) VERDICT=Broken; NOTE="does not finish on its own revision" ;;
                2) VERDICT=Broken; NOTE="no test method left" ;;
                *) VERDICT=Broken; NOTE="fails on its own revision when run again" ;;
            esac
        fi

        # ---- the other revision ----
        if [ -z "$VERDICT" ]; then
            mkdir -p "$OTHER/_m-$ARM"
            echo "---- the other revision ($OTHER_KIND) ----" >> "$P.compile.log"
            if (cd "$OTHER" && c3_env javac -nowarn $(cat "$OTHER/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                    -cp "target/classes:$(cat "$OTHER/.c3/cp-test")" -d "_m-$ARM" $SRCS) >> "$P.compile.log" 2>&1; then
                OTHER_COMPILED=yes
            else
                VERDICT=Broken; NOTE="does not compile against the other revision"
            fi
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$OTHER" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$OTHER")" AgentTestRunner \
                --report "$P.other.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.other.log" 2>&1 < /dev/null
            RC=$?; SEC_X=$SECONDS
            case "$RC" in
                0) VERDICT=Pass ;;
                1) VERDICT=Fail; FAILING=$(excluded_from "$P.other.tsv" | paste -sd';' -) ;;
                124|137) VERDICT=Fail; NOTE="timeout" ;;
                *) VERDICT=Broken; NOTE="the runner ended with status $RC on the other revision" ;;
            esac
        fi

        # ---- the tests left out at acceptance, on the other revision ----
        LEFT=$(grep -c . "$SUITE/excluded.txt")
        FIRST="$OUT_ABS/runs-$ARM/$TAG.first.tsv"
        if [ "$LEFT" -gt 0 ] && [ "$OTHER_COMPILED" = "yes" ] && [ -f "$FIRST" ]; then
            # everything else is left out: the methods of the first run that were kept
            python3 - "$FIRST" "$SUITE/excluded.txt" > "$T/keep-out-$ARM" <<'EOF'
import sys
first, excl = sys.argv[1:3]
excluded = {l.strip() for l in open(excl) if l.strip()}
for line in open(first, errors="replace"):
    cols = line.rstrip("\n").split("\t")
    if len(cols) > 2 and cols[1] == "method" and cols[2] not in excluded:
        print(cols[2])
EOF
            (cd "$OTHER" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$OTHER")" AgentTestRunner \
                --report "$P.leftout.tsv" --exclude "$T/keep-out-$ARM" $RUN_CLASSES) > "$P.leftout.log" 2>&1 < /dev/null
            read -r LO_RUN LO_PASS <<< "$(python3 - "$P.leftout.tsv" "$SUITE/excluded.txt" <<'EOF'
import sys
report, excl = sys.argv[1:3]
excluded = {l.strip() for l in open(excl) if l.strip()}
def left_out(key):
    if key in excluded:
        return True
    # a method of a class left out as a whole, or of a class nested in one
    parts = key.split("#")[0].split("$")
    return any("$".join(parts[:i]) in excluded for i in range(1, len(parts) + 1))
ran = passed = 0
try:
    rows = [l.rstrip("\n").split("\t") for l in open(report, errors="replace")]
except OSError:
    rows = []
for cols in rows:
    if len(cols) > 2 and cols[1] == "method" and left_out(cols[2]):
        ran += 1
        passed += cols[0] == "SUCCESSFUL"
print(ran, passed)
EOF
)"
        fi

        METHODS=$(awk -F'\t' '$2 == "method"' "$P.own.tsv" 2>/dev/null | wc -l)
        NFAIL=0; [ -n "$FAILING" ] && NFAIL=$(echo "$FAILING" | tr ';' '\n' | wc -l)
        csv "$TAG" "$ARM" "$OWN_KIND" "$VERDICT" "$NOTE" "$METHODS" "$LEFT" "$NFAIL" "$FAILING" \
            "$LO_RUN" "$LO_PASS" "$SEC_O" "$SEC_X" > "$P.verdict"
        echo >> "$P.verdict"
        printf '[%s] %s  %-6s %s%s%s\n' "$TAG" "$ARM" "$VERDICT" "${NOTE:+($NOTE) }" "${NFAIL/#0/}" \
            "${LO_RUN:+  left out: $LO_PASS of $LO_RUN pass on the other revision}"
    done
    rm -rf "$T"
done < "$SUBJECTS"

{
    echo "subject,arm,own_revision,verdict,note,methods_run_on_own,keys_left_out,failing_on_other,failing_keys,left_out_methods_run_on_other,left_out_passing_on_other,seconds_own,seconds_other"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in b5 m5; do
            if [ -f "$RES/$TAG.$ARM.verdict" ]; then cat "$RES/$TAG.$ARM.verdict"; fi
        done
    done < "$SUBJECTS"
} > "$RES/verdicts.csv"

echo
for ARM in b5 m5; do
    printf '%s: ' "$ARM"
    awk -F, -v a="$ARM" 'NR > 1 && $2 == a { n[$4]++ } END { printf "Fail %d, Pass %d, Broken %d\n", n["Fail"], n["Pass"], n["Broken"] }' "$RES/verdicts.csv"
done

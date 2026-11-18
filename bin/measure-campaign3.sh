#!/bin/bash
#
# Third campaign, measurement: does each archived suite detect its fault?
#
# For every subject of the list and every arm with a suite in <OUT>/suites:
#
#   - the fix commit and its parent are exported and built, offline, with
#     nothing of the repository's history (bin/campaign3-lib.sh)
#   - the suite, as the agent wrote it, is compiled on its own against each
#     revision's production classes and the project's test libraries
#   - it is run on the fixed revision with the tests of its excluded.txt left
#     out, the ones that failed there at acceptance. It has to pass again.
#   - it is run on the buggy revision with the same tests left out
#
# The runner is bin/AgentTestRunner.java, the same that accepted the suite.
#
# VERDICTS  (<OUT>/results/verdicts.csv, one row per subject and arm)
#
#   Fail     a test that passes on the fixed revision fails on the buggy one:
#            the fault is detected
#   Pass     every test that passes on the fixed revision passes on the buggy
#            one
#   Broken   no verdict. The suite does not compile against the buggy
#            revision, or, run again, does not pass on the fixed one.
#
# The names are Defects4J's, and so is the rule. A test that is aborted
# because an assumption does not hold, or skipped, has not failed. A class
# whose set-up fails on the buggy revision and not on the fixed one counts as
# a failing test. A suite that finishes on the fixed revision and does not
# finish on the buggy one within RUN_TIMEOUT seconds is `Fail`, with the note
# `timeout`; the analysis is repeated with such verdicts read as `Pass`.
#
# Per suite, in <OUT>/results/:
#   <subject>.<arm>.fixed.log .fixed.tsv     the run on the fixed revision
#   <subject>.<arm>.buggy.log .buggy.tsv     the run on the buggy revision
#   <subject>.<arm>.compile.log              javac, both revisions
#   <subject>.<arm>.verdict                  the row of verdicts.csv
# and per subject <subject>.fixed.build.log, <subject>.buggy.build.log.
#
# A suite that has a .verdict is not measured again (FORCE=1 to redo).
#
# Usage:
#   ./bin/measure-campaign3.sh                       # data/campaign3
#   ONLY="commons-csv-68f17d8a" ./bin/measure-campaign3.sh
#   DRY=1 OUT=/tmp/dry ./bin/measure-campaign3.sh /tmp/subjects.txt
#       the suites of a dry run of the generator: the developers' own tests,
#       which are not self-contained, so each revision's test sources are on
#       the compiler's source path. Every one of them should come out `Fail`.

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/bin/campaign3-lib.sh"
export TZ=America/Los_Angeles

OUT=${OUT:-data/campaign3}
SUBJECTS=${1:-data/campaign3/subjects.txt}
ONLY=${ONLY:-}
DRY=${DRY:-}
FORCE=${FORCE:-}
ARMS=${ARMS:-"m3 s3"}
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
    F="$T/fixed"; B="$T/buggy"; RUNNER="$T/runner"
    echo "[$TAG] staging both revisions"
    if ! stage_revision "$REPO" "$SHA" "$F" "$RES/$TAG.fixed.build.log"; then
        echo "[$TAG] the fixed revision does not build"; rm -rf "$T"; exit 1
    fi
    if ! stage_revision "$REPO" "$SHA~1" "$B" "$RES/$TAG.buggy.build.log"; then
        echo "[$TAG] the buggy revision does not build"; rm -rf "$T"; exit 1
    fi
    if ! build_runner "$F" "$RUNNER" "$ROOT" > "$T/runner.log" 2>&1; then
        echo "[$TAG] the runner does not compile"; cat "$T/runner.log"; rm -rf "$T"; exit 1
    fi

    for ARM in $TODO; do
        P="$RES/$TAG.$ARM"
        rm -f "$P.fixed.log" "$P.fixed.tsv" "$P.buggy.log" "$P.buggy.tsv" "$P.compile.log" "$P.verdict"
        SUITE="$T/suite-$ARM"
        mkdir -p "$SUITE"
        tar -xjf "$SUITES/${TAG}-${ARM}.tar.bz2" -C "$SUITE"
        [ -f "$SUITE/excluded.txt" ] || : > "$SUITE/excluded.txt"
        WRITTEN=$(cd "$SUITE" && find . -name '*AgentTest.java' | sort)
        RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
        SRCS=""
        for f in $WRITTEN; do SRCS="$SRCS $SUITE/${f#./}"; done

        VERDICT=""; NOTE=""; FAILING=""; SEC_F=0; SEC_B=0

        # ---- fixed revision ----
        mkdir -p "$F/_m-$ARM"
        if ! (cd "$F" && c3_env javac -nowarn $(cat "$F/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                -cp "target/classes:$(cat "$F/.c3/cp-test")" -d "_m-$ARM" $SRCS) > "$P.compile.log" 2>&1; then
            VERDICT=Broken; NOTE="does not compile against the fixed revision"
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$F" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$F")" AgentTestRunner \
                --report "$P.fixed.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.fixed.log" 2>&1 < /dev/null
            RC=$?; SEC_F=$SECONDS
            case "$RC" in
                0) ;;
                124|137) VERDICT=Broken; NOTE="does not finish on the fixed revision" ;;
                2) VERDICT=Broken; NOTE="no test method left" ;;
                *) VERDICT=Broken; NOTE="fails on the fixed revision when run again" ;;
            esac
        fi

        # ---- buggy revision ----
        if [ -z "$VERDICT" ]; then
            mkdir -p "$B/_m-$ARM"
            echo "---- buggy revision ----" >> "$P.compile.log"
            if ! (cd "$B" && c3_env javac -nowarn $(cat "$B/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                    -cp "target/classes:$(cat "$B/.c3/cp-test")" -d "_m-$ARM" $SRCS) >> "$P.compile.log" 2>&1; then
                VERDICT=Broken; NOTE="does not compile against the buggy revision"
            fi
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$B" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$B")" AgentTestRunner \
                --report "$P.buggy.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.buggy.log" 2>&1 < /dev/null
            RC=$?; SEC_B=$SECONDS
            case "$RC" in
                0) VERDICT=Pass ;;
                1) VERDICT=Fail; FAILING=$(excluded_from "$P.buggy.tsv" | paste -sd';' -) ;;
                124|137) VERDICT=Fail; NOTE="timeout" ;;
                *) VERDICT=Broken; NOTE="the runner ended with status $RC on the buggy revision" ;;
            esac
        fi

        METHODS=$(awk -F'\t' '$2 == "method"' "$P.fixed.tsv" 2>/dev/null | wc -l)
        LEFT=$(grep -c . "$SUITE/excluded.txt")
        NFAIL=0; [ -n "$FAILING" ] && NFAIL=$(echo "$FAILING" | tr ';' '\n' | wc -l)
        csv "$TAG" "$ARM" "$VERDICT" "$NOTE" "$METHODS" "$LEFT" "$NFAIL" "$FAILING" "$SEC_F" "$SEC_B" > "$P.verdict"
        echo >> "$P.verdict"
        printf '[%s] %s  %-6s %s%s\n' "$TAG" "$ARM" "$VERDICT" "${NOTE:+($NOTE) }" "${NFAIL/#0/}"
    done
    rm -rf "$T"
done < "$SUBJECTS"

{
    echo "subject,arm,verdict,note,methods_run_on_fixed,keys_left_out,failing_on_buggy,failing_keys,seconds_fixed,seconds_buggy"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in m3 s3; do
            [ -f "$RES/$TAG.$ARM.verdict" ] && cat "$RES/$TAG.$ARM.verdict"
        done
    done < "$SUBJECTS"
} > "$RES/verdicts.csv"

echo
for ARM in m3 s3; do
    printf '%s: ' "$ARM"
    awk -F, -v a="$ARM" 'NR > 1 && $2 == a { n[$3]++ } END { printf "Fail %d, Pass %d, Broken %d\n", n["Fail"], n["Pass"], n["Broken"] }' "$RES/verdicts.csv"
done

#!/bin/bash
#
# Sixth campaign, measurement: does each archived suite tell the two revisions
# of its fault apart, and which way? The fifth campaign's
# bin/measure-campaign5.sh with the arms, the paths and the subjects' list
# changed, and the tests left out at acceptance run as the protocol requires
# (data/campaign6/PROTOCOL.md).
#
# Each suite has its own revision, the one the agent was given and the suite
# was accepted on, and the other one:
#
#   m6   own: the fix commit        other: its parent
#   f6   own: the parent            other: the fix commit
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
#   - the tests of excluded.txt, and only those, are run one class at a time:
#     in m6 on the other revision, as in the fifth campaign, a secondary
#     outcome; in f6 on both revisions, which gives f6's detection. In f6 the
#     suite is compiled against the other revision, and its left-out tests
#     are run, whatever the rest of the suite did on its own revision.
#
# The runner is bin/AgentTestRunner.java, the same that accepted the suite.
#
# VERDICTS  (<OUT>/results/verdicts.csv, one row per subject and arm)
#
#   verdict      the suite as accepted, run on the other revision:
#     Fail       a test that passes on the suite's own revision fails on the
#                other one. In m6 the fault is detected; in f6 the suite
#                certifies it
#     Pass       every test that passes on the own revision passes on the other
#     Broken     no verdict. The suite does not compile against the other
#                revision, or, run again, does not pass on its own.
#     none       f6 only: acceptance left every test out, so no test is left
#                to run
#   detection    the primary outcome of both arms. In m6 it is the verdict. In
#                f6 it is Fail when a left-out test detects the fault: it fails
#                again on the faulty revision, or does not finish there, and
#                passes on the fix commit. Otherwise it is Pass, also when
#                acceptance left nothing out. It is Broken when the suite does
#                not compile against both revisions.
#
# The fourth campaign's rules, with the revisions in the arm's order. A test
# that is aborted because an assumption does not hold, or skipped, has not
# failed, and has not passed. A class whose set-up fails on the other revision
# and not on the own one counts as a failing test. A suite that finishes on its
# own revision and does not finish on the other one within RUN_TIMEOUT seconds
# is `Fail`, with the note `timeout`; the analysis is repeated with such
# verdicts read as `Pass`.
#
# THE LEFT-OUT TESTS
#   Each class of the suite that holds a left-out test is run on its own, with
#   every other method of the suite's first run at acceptance
#   (runs-<arm>/<subject>.first.tsv) left out, so that only its left-out tests
#   run. A class left out as a whole runs whole. (In the fifth campaign the
#   methods of a class left out as a whole were themselves left out of that
#   run when the class's set-up had failed at acceptance, since the first run
#   lists them. Every key that campaign left out was a method's, so none of
#   its figures depends on this.) Each class has RUN_TIMEOUT seconds; one that
#   does not finish is recorded as such, with the line
#   `NOT_FINISHED<tab>class<tab><class>` in the report. One that ends the
#   runner without its report, which the runner writes whenever it gets to the
#   end, has the line `NO_REPORT<tab>class<tab><class>`: its JVM died on the
#   way, as one does when a test exhausts its heap. Below, a class that does
#   not finish is either.
#
#   A left-out method fails again on the faulty revision when it fails there,
#   when a class it belongs to fails there as a whole, or when its class does
#   not finish there. It passes on the fix commit when the runner reports it
#   successful. In f6, a left-out method that fails again on the faulty
#   revision and passes on the fix commit detects the fault; one that fails
#   again and does not pass on the fix commit is a false alarm; one that does
#   not fail again is unstable. A class that finishes on neither revision, so
#   that none of its methods is known, counts as one false alarm. f6's
#   detection has the note `timeout` when every test that detects belongs to
#   a class that ran out of time (NOT_FINISHED) on the faulty revision, and
#   failed there for no other reason. A class that ended without a report
#   gives no note, as m6's verdict has none when its suite ends without a
#   report on the faulty revision.
#
# Columns of verdicts.csv: the fifth campaign's thirteen, then detection,
# detection_note, left_out_failing_again_on_own, left_out_detecting,
# left_out_false_alarms, left_out_unstable and detecting_keys. In m6 the last
# five are empty.
#
# Per suite, in <OUT>/results/:
#   <subject>.<arm>.own.log .own.tsv           the run on its own revision
#   <subject>.<arm>.other.log .other.tsv       the run on the other revision
#   <subject>.<arm>.leftout.log .leftout.tsv   the left-out tests, on the other
#   <subject>.<arm>.leftown.log .leftown.tsv   f6: the left-out tests, on its own
#   <subject>.<arm>.compile.log                javac, both revisions
#   <subject>.<arm>.verdict                    the row of verdicts.csv
# and per subject <subject>.fixed.build.log, <subject>.faulty.build.log.
#
# A suite that has a .verdict is not measured again (FORCE=1 to redo).
#
# Usage:
#   ./bin/measure-campaign6.sh                       # data/campaign6
#   ONLY="commons-csv-b5940a642" ./bin/measure-campaign6.sh
#   DRY=1 OUT=/tmp/dry ./bin/measure-campaign6.sh /tmp/subjects.txt
#       the suites of a dry run of the generator: the developers' tests of the
#       fix, which are not self-contained, so each revision's test sources are
#       on the compiler's source path. In m6 every one of them should come out
#       `Fail`. In f6 their trigger tests were left out at acceptance, so its
#       detection should come out `Fail`.

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
# the fourth campaign's records, reused as they are, and the pool's clones;
# the library reads both when it is sourced
SUBJECT_ROOTS=${SUBJECT_ROOTS:-data/campaign4/subjects}
MINING=${MINING:-$HOME/code/mining-pool}
. "$ROOT/bin/campaign3-lib.sh"
export TZ=America/Los_Angeles

OUT=${OUT:-data/campaign6}
SUBJECTS=${1:-data/campaign6/subjects.txt}
ONLY=${ONLY:-}
DRY=${DRY:-}
FORCE=${FORCE:-}
ARMS=${ARMS:-"f6 m6"}
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

# left_out_runs <revision dir> <prefix> <first.tsv> <excluded.txt> <tmp dir>
#
# The left-out tests on one revision, one class at a time, from the classes
# compiled into <revision dir>/_m-$ARM. Writes <prefix>.log and <prefix>.tsv:
# the runner's reports one after another, NOT_FINISHED for a class that does
# not finish within RUN_TIMEOUT seconds and NO_REPORT for one that ends the
# runner without its report.
left_out_runs() {
    local rev=$1 prefix=$2 first=$3 excl=$4 t=$5 C RC
    : > "$prefix.log"; : > "$prefix.tsv"
    # everything else is left out: the methods of the first run that were kept
    python3 - "$first" "$excl" > "$t/keep-out-$ARM" <<'EOF'
import sys
first, excl = sys.argv[1:3]
excluded = {l.strip() for l in open(excl) if l.strip()}
def left_out(key):
    if key in excluded:
        return True
    # a method of a class left out as a whole, or of a class nested in one
    parts = key.split("#")[0].split("$")
    return any("$".join(parts[:i]) in excluded for i in range(1, len(parts) + 1))
for line in open(first, errors="replace"):
    cols = line.rstrip("\n").split("\t")
    if len(cols) > 2 and cols[1] == "method" and not left_out(cols[2]):
        print(cols[2])
EOF
    for C in $(python3 - "$excl" $RUN_CLASSES <<'EOF'
import sys
keys = [l.strip() for l in open(sys.argv[1]) if l.strip()]
for c in sys.argv[2:]:
    if any(k == c or k.startswith(c + "#") or k.startswith(c + "$") for k in keys):
        print(c)
EOF
); do
        echo "---- $C ----" >> "$prefix.log"
        rm -f "$t/one.tsv"
        (cd "$rev" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(run_cp "$rev")" AgentTestRunner \
            --report "$t/one.tsv" --exclude "$t/keep-out-$ARM" "$C") >> "$prefix.log" 2>&1 < /dev/null
        RC=$?
        if [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then
            printf 'NOT_FINISHED\tclass\t%s\t0\t0\tdid not finish within %s seconds\n' "$C" "$RUN_TIMEOUT" >> "$prefix.tsv"
        elif [ -f "$t/one.tsv" ]; then
            cat "$t/one.tsv" >> "$prefix.tsv"
        else
            printf 'NO_REPORT\tclass\t%s\t0\t0\tthe runner ended without its report (exit %s)\n' "$C" "$RC" >> "$prefix.tsv"
        fi
    done
}

# left_out_counts <own report or -> <other report> <excluded.txt> <first.tsv>
#
# Prints, separated by the character 0x1f, which no key holds and which `read`
# does not merge as it does tabs: the left-out methods that ran on the other revision,
# those that passed there; and with the own revision's report (f6): those that
# failed again on the own revision, those that detect, the false alarms, the
# unstable, the keys that detect, and `timeout` when every test that detects
# rests only on a class that ran out of time on the own revision.
left_out_counts() {
    python3 - "$@" <<'EOF'
import sys
own_path, other_path, excl_path, first_path = sys.argv[1:5]
excluded = {l.strip() for l in open(excl_path) if l.strip()}

def chain(key):
    """The classes a key belongs to, outermost first."""
    parts = key.split("#")[0].split("$")
    return ["$".join(parts[:i]) for i in range(1, len(parts) + 1)]

def left_out(key):
    return key in excluded or any(c in excluded for c in chain(key))

def read(path):
    """Methods and their status, classes failed as a whole, classes that did
    not finish (out of time or without a report), classes out of time."""
    methods, failed, unfinished, out_of_time = {}, set(), set(), set()
    try:
        rows = [l.rstrip("\n").split("\t") for l in open(path, errors="replace")]
    except OSError:
        rows = []
    for cols in rows:
        if len(cols) < 3:
            continue
        status, kind, key = cols[:3]
        if status in ("NOT_FINISHED", "NO_REPORT"):
            unfinished.add(key)
            if status == "NOT_FINISHED":
                out_of_time.add(key)
        elif kind == "method":
            if left_out(key):
                methods[key] = status
        elif status == "FAILED":
            failed.add(key)
    return methods, failed, unfinished, out_of_time

other = read(other_path)
own = read(own_path) if own_path != "-" else None
known = set(other[0]) | (set(own[0]) if own else set())
for line in open(first_path, errors="replace"):
    cols = line.rstrip("\n").split("\t")
    if len(cols) > 2 and cols[1] == "method" and left_out(cols[2]):
        known.add(cols[2])

def passes(key):
    return other[0].get(key) == "SUCCESSFUL"

ran = sum(1 for k in known if k in other[0])
passed = sum(1 for k in known if passes(k))
if own is None:
    print("\x1f".join(str(x) for x in (ran, passed, "", "", "", "", "", "")))
    raise SystemExit

def failed_own(key):
    return own[0].get(key) == "FAILED" or any(c in own[1] for c in chain(key))

def unfinished_own(key):
    return chain(key)[0] in own[2]

def out_of_time_own(key):
    return chain(key)[0] in own[3]

again = [k for k in known if failed_own(k) or unfinished_own(k)]
detect = sorted(k for k in again if passes(k))
alarms = [k for k in again if not passes(k)]
unstable = [k for k in known if not (failed_own(k) or unfinished_own(k))]
# a class that finished on neither revision: none of its methods is known
blind = [c for c in own[2] if c in other[2] and not any(chain(k)[0] == c for k in known)]
timeout = bool(detect) and all(out_of_time_own(k) and not failed_own(k) for k in detect)
print("\x1f".join(str(x) for x in (ran, passed, len(again) + len(blind), len(detect),
                                 len(alarms) + len(blind), len(unstable), ";".join(detect),
                                 "timeout" if timeout else "")))
EOF
}

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
        if [ "$ARM" = "f6" ]; then
            OWN=$B; OTHER=$F; OWN_KIND=faulty; OTHER_KIND=fixed
        else
            OWN=$F; OTHER=$B; OWN_KIND=fixed; OTHER_KIND=faulty
        fi
        P="$RES/$TAG.$ARM"
        rm -f "$P.own.log" "$P.own.tsv" "$P.other.log" "$P.other.tsv" "$P.leftout.log" "$P.leftout.tsv" \
              "$P.leftown.log" "$P.leftown.tsv" "$P.compile.log" "$P.verdict"
        SUITE="$T/suite-$ARM"
        mkdir -p "$SUITE"
        tar -xjf "$SUITES/${TAG}-${ARM}.tar.bz2" -C "$SUITE"
        [ -f "$SUITE/excluded.txt" ] || : > "$SUITE/excluded.txt"
        WRITTEN=$(cd "$SUITE" && find . -name '*AgentTest.java' | sort)
        RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
        SRCS=""
        for f in $WRITTEN; do SRCS="$SRCS $SUITE/${f#./}"; done

        VERDICT=""; NOTE=""; FAILING=""; SEC_O=0; SEC_X=0; OWN_COMPILED=no; OTHER_COMPILED=no
        LO_RUN=""; LO_PASS=""; LO_AGAIN=""; LO_DETECT=""; LO_ALARM=""; LO_UNSTABLE=""; DET_KEYS=""; LO_TIMEOUT=""
        DET=""; DET_NOTE=""

        # ---- its own revision ----
        mkdir -p "$OWN/_m-$ARM"
        if ! (cd "$OWN" && c3_env javac -nowarn $(cat "$OWN/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                -cp "target/classes:$(cat "$OWN/.c3/cp-test")" -d "_m-$ARM" $SRCS) > "$P.compile.log" 2>&1; then
            VERDICT=Broken; NOTE="does not compile against its own revision"
        else
            OWN_COMPILED=yes
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
        METHODS=$(awk -F'\t' '$2 == "method"' "$P.own.tsv" 2>/dev/null | wc -l)
        # f6: acceptance left every test out, so none is left to run
        if [ "$ARM" = "f6" ] && [ -z "$VERDICT" ] && [ "$METHODS" -eq 0 ]; then
            VERDICT=none; NOTE="every test was left out at acceptance"
        fi

        # ---- the other revision ----
        # In m6, as in the fifth campaign, only for a suite that passed again on
        # its own revision. In f6 for any suite that compiles on its own, since
        # its left-out tests are run there whatever the rest did.
        if [ "$OWN_COMPILED" = "yes" ] && { [ -z "$VERDICT" ] || [ "$ARM" = "f6" ]; }; then
            mkdir -p "$OTHER/_m-$ARM"
            echo "---- the other revision ($OTHER_KIND) ----" >> "$P.compile.log"
            if (cd "$OTHER" && c3_env javac -nowarn $(cat "$OTHER/.c3/javac-level") -Xlint:-options -encoding UTF-8 $SP \
                    -cp "target/classes:$(cat "$OTHER/.c3/cp-test")" -d "_m-$ARM" $SRCS) >> "$P.compile.log" 2>&1; then
                OTHER_COMPILED=yes
            elif [ -z "$VERDICT" ] || [ "$VERDICT" = "none" ]; then
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

        # ---- the tests left out at acceptance ----
        LEFT=$(grep -c . "$SUITE/excluded.txt")
        FIRST="$OUT_ABS/runs-$ARM/$TAG.first.tsv"
        if [ "$LEFT" -gt 0 ] && [ "$OTHER_COMPILED" = "yes" ] && [ -f "$FIRST" ]; then
            left_out_runs "$OTHER" "$P.leftout" "$FIRST" "$SUITE/excluded.txt" "$T"
            OWN_REPORT=-
            if [ "$ARM" = "f6" ]; then
                left_out_runs "$OWN" "$P.leftown" "$FIRST" "$SUITE/excluded.txt" "$T"
                OWN_REPORT="$P.leftown.tsv"
            fi
            IFS=$'\x1f' read -r LO_RUN LO_PASS LO_AGAIN LO_DETECT LO_ALARM LO_UNSTABLE DET_KEYS LO_TIMEOUT \
                <<< "$(left_out_counts "$OWN_REPORT" "$P.leftout.tsv" "$SUITE/excluded.txt" "$FIRST")"
        fi

        # ---- detection, the primary outcome ----
        if [ "$ARM" = "m6" ]; then
            DET=$VERDICT; DET_NOTE=$NOTE
        elif [ "$OWN_COMPILED" != "yes" ]; then
            DET=Broken; DET_NOTE="does not compile against its own revision"
        elif [ "$OTHER_COMPILED" != "yes" ]; then
            DET=Broken; DET_NOTE="does not compile against the other revision"
        elif [ "$LEFT" -eq 0 ]; then
            DET=Pass; DET_NOTE="nothing was left out at acceptance"
        elif [ ! -f "$FIRST" ]; then
            DET=Broken; DET_NOTE="no record of the first run at acceptance"
        elif [ -z "$LO_RUN" ] || [ -z "$LO_DETECT" ]; then
            DET=Broken; DET_NOTE="the left-out tests could not be counted"
        elif [ "$LO_DETECT" -gt 0 ]; then
            DET=Fail; DET_NOTE=$LO_TIMEOUT
        else
            DET=Pass
        fi

        NFAIL=0; [ -n "$FAILING" ] && NFAIL=$(echo "$FAILING" | tr ';' '\n' | wc -l)
        csv "$TAG" "$ARM" "$OWN_KIND" "$VERDICT" "$NOTE" "$METHODS" "$LEFT" "$NFAIL" "$FAILING" \
            "$LO_RUN" "$LO_PASS" "$SEC_O" "$SEC_X" "$DET" "$DET_NOTE" "$LO_AGAIN" "$LO_DETECT" "$LO_ALARM" \
            "$LO_UNSTABLE" "$DET_KEYS" > "$P.verdict"
        echo >> "$P.verdict"
        if [ "$ARM" = "f6" ]; then
            printf '[%s] %s  detection %-6s %s certification %-6s %s%s\n' "$TAG" "$ARM" "$DET" "${DET_NOTE:+($DET_NOTE) }" \
                "$VERDICT" "${NOTE:+($NOTE) }" \
                "${LO_RUN:+  left out: $LO_AGAIN fail again, $LO_DETECT detect, $LO_ALARM false alarms, $LO_UNSTABLE unstable}"
        else
            printf '[%s] %s  %-6s %s%s%s\n' "$TAG" "$ARM" "$VERDICT" "${NOTE:+($NOTE) }" "${NFAIL/#0/}" \
                "${LO_RUN:+  left out: $LO_PASS of $LO_RUN pass on the other revision}"
        fi
    done
    rm -rf "$T"
done < "$SUBJECTS"

{
    echo "subject,arm,own_revision,verdict,note,methods_run_on_own,keys_left_out,failing_on_other,failing_keys,left_out_methods_run_on_other,left_out_passing_on_other,seconds_own,seconds_other,detection,detection_note,left_out_failing_again_on_own,left_out_detecting,left_out_false_alarms,left_out_unstable,detecting_keys"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in f6 m6; do
            if [ -f "$RES/$TAG.$ARM.verdict" ]; then cat "$RES/$TAG.$ARM.verdict"; fi
        done
    done < "$SUBJECTS"
} > "$RES/verdicts.csv"

echo
# the keys can hold commas, so the file is read as CSV
python3 - "$RES/verdicts.csv" <<'EOF'
import collections, csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
for arm in ("f6", "m6"):
    v = collections.Counter(r["verdict"] for r in rows if r["arm"] == arm)
    d = collections.Counter(r["detection"] for r in rows if r["arm"] == arm)
    print(f"{arm}: verdict: Fail {v['Fail']}, Pass {v['Pass']}, Broken {v['Broken']}, none {v['none']}; "
          f"detection: Fail {d['Fail']}, Pass {d['Pass']}, Broken {d['Broken']}")
EOF

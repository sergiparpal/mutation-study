#!/bin/bash
#
# Seventh campaign, measurement: does each archived suite tell the two
# versions of its bug apart, and which way? The sixth campaign's
# bin/measure-campaign6.sh with the arms, the paths and the subjects' list
# changed, Defects4J's two versions of the bug in place of the fix commit and
# its parent, and bin/AgentTestRunner4.java in place of bin/AgentTestRunner.java
# (data/campaign7/PROTOCOL.md).
#
# Each suite has its own version, the one the agent was given and the suite
# was accepted on, and the other one:
#
#   m7   own: the fixed version (<id>f)     other: the buggy version (<id>b)
#   f7   own: the buggy version             other: the fixed version
#
# For every bug of the list and every arm with a suite in <OUT>/suites:
#
#   - both versions are staged as the generator stages them
#     (bin/campaign7-lib.sh): checked out by Defects4J, without the history
#     and without the developer test files that hold the trigger tests, and
#     compiled by Defects4J
#   - the suite, as the agent wrote it, is compiled on its own against each
#     version, at the project's -source level, on the class path the agent's
#     test.sh uses
#   - it is run on its own version with the tests of its excluded.txt left
#     out, the ones that failed there at acceptance. It has to pass again.
#   - it is run on the other version with the same tests left out
#   - the tests of excluded.txt, and only those, are run one class at a time:
#     in m7 on the other version, a secondary outcome; in f7 on both versions,
#     which gives f7's detection. In f7 the suite is compiled against the
#     other version, and its left-out tests are run, whatever the rest of the
#     suite did on its own version.
#
# The runner is bin/AgentTestRunner4.java, the same that accepted the suite.
#
# VERDICTS  (<OUT>/results/verdicts.csv, one row per bug and arm)
#
#   verdict      the suite as accepted, run on the other version:
#     Fail       a test that passes on the suite's own version fails on the
#                other one. In m7 the fault is detected; in f7 the suite
#                certifies it
#     Pass       every test that passes on the own version passes on the other
#     Broken     no verdict. The suite does not compile against the other
#                version, or, run again, does not pass on its own.
#     none       f7 only: acceptance left every test out, so no test is left
#                to run
#   detection    the primary outcome of both arms. In m7 it is the verdict. In
#                f7 it is Fail when a left-out test detects the fault: it fails
#                again on the buggy version, or does not finish there, and
#                passes on the fixed version. Otherwise it is Pass, also when
#                acceptance left nothing out. It is Broken when the suite does
#                not compile against both versions.
#
# The sixth campaign's rules, with the versions in the arm's order. A test
# that is aborted because an assumption does not hold, or ignored, has not
# failed, and has not passed. A class whose set-up fails on the other version
# and not on the own one counts as a failing test. A suite that finishes on its
# own version and does not finish on the other one within RUN_TIMEOUT seconds
# is `Fail`, with the note `timeout`; the analysis is repeated with such
# verdicts read as `Pass`.
#
# THE LEFT-OUT TESTS
#   As in the sixth campaign. Each class of the suite that holds a left-out
#   test is run on its own, with every other method of the suite's first run
#   at acceptance (runs-<arm>/<bug>.first.tsv) left out, so that only its
#   left-out tests run. A class left out as a whole runs whole. Each class has
#   RUN_TIMEOUT seconds; one that does not finish is recorded as such, with the
#   line `NOT_FINISHED<tab>class<tab><class>` in the report. One that ends the
#   runner without its report, which the runner writes whenever it gets to the
#   end, has the line `NO_REPORT<tab>class<tab><class>`: its JVM died on the
#   way, as one does when a test exhausts its heap. Below, a class that does
#   not finish is either.
#
#   A left-out method fails again on the buggy version when it fails there,
#   when a class it belongs to fails there as a whole, or when its class does
#   not finish there. It passes on the fixed version when the runner reports it
#   successful. In f7, a left-out method that fails again on the buggy version
#   and passes on the fixed version detects the fault; one that fails again and
#   does not pass on the fixed version is a false alarm; one that does not fail
#   again is unstable. A class that finishes on neither version, so that none
#   of its methods is known, counts as one false alarm. f7's detection has the
#   note `timeout` when every test that detects belongs to a class that ran out
#   of time (NOT_FINISHED) on the buggy version, and failed there for no other
#   reason. A class that ended without a report gives no note, as m7's verdict
#   has none when its suite ends without a report on the buggy version.
#
# Columns of verdicts.csv: the sixth campaign's twenty, with "subject" for the
# bug. In m7 the last five are empty.
#
# Per suite, in <OUT>/results/:
#   <bug>.<arm>.own.log .own.tsv           the run on its own version
#   <bug>.<arm>.other.log .other.tsv       the run on the other version
#   <bug>.<arm>.leftout.log .leftout.tsv   the left-out tests, on the other
#   <bug>.<arm>.leftown.log .leftown.tsv   f7: the left-out tests, on its own
#   <bug>.<arm>.compile.log                javac, both versions
#   <bug>.<arm>.verdict                    the row of verdicts.csv
# and per bug <bug>.fixed.build.log and <bug>.buggy.build.log, Defects4J's
# compilation of each version (with .build.log2 where stubs were needed).
#
# A suite that has a .verdict is not measured again (FORCE=1 to redo).
#
# Usage:
#   ./bin/measure-campaign7.sh                       # data/campaign7
#   ONLY="Lang-43" ./bin/measure-campaign7.sh
#   DRY=1 OUT=/tmp/dry ./bin/measure-campaign7.sh
#       the suites of a dry run of the generator: the developers' test classes
#       that hold the trigger tests, which are not self-contained, so each
#       version's test sources are on the compiler's source path. In m7 every
#       one of them should come out `Fail`. In f7 their trigger tests were left
#       out at acceptance, so its detection should come out `Fail`.

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/bin/campaign7-lib.sh"

OUT=${OUT:-data/campaign7}
SUBJECTS=${1:-data/campaign7/subjects.txt}
ONLY=${ONLY:-}
DRY=${DRY:-}
FORCE=${FORCE:-}
ARMS=${ARMS:-"f7 m7"}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
RES=$OUT_ABS/results

command -v defects4j >/dev/null || { echo "defects4j not found under $D4J_HOME"; exit 1; }
command -v javac >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
[ -d "$SUITES" ] || { echo "no suites under $SUITES"; exit 1; }
WHY=$(c7_check_env) || { echo "$WHY"; exit 1; }
mkdir -p "$RES" "$STAGE_ROOT"


# csv_field <text>: quoted if it needs to be
csv() { python3 -c 'import csv, sys; csv.writer(sys.stdout, lineterminator="").writerow(sys.argv[1:])' "$@"; }

# left_out_runs <version dir> <prefix> <first.tsv> <excluded.txt> <tmp dir>
#
# The left-out tests on one version, one class at a time, from the classes
# compiled into <version dir>/_m-$ARM. Writes <prefix>.log and <prefix>.tsv:
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
    # a method of a class left out as a whole, or of a class nested in one; a
    # class's own name may hold a $, so the classes are matched by prefix
    cls = key.split("#")[0]
    return any(cls == e or cls.startswith(e + "$") for e in excluded if "#" not in e)
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
        (cd "$rev" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(cat "$rev/.c7/cp-test")" AgentTestRunner4 \
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
# does not merge as it does tabs: the left-out methods that ran on the other version,
# those that passed there; and with the own version's report (f7): those that
# failed again on the own revision, those that detect, the false alarms, the
# unstable, the keys that detect, and `timeout` when every test that detects
# rests only on a class that ran out of time on the own version.
left_out_counts() {
    python3 - "$@" <<'EOF'
import sys
own_path, other_path, excl_path, first_path = sys.argv[1:5]
excluded = {l.strip() for l in open(excl_path) if l.strip()}

def within(key, outer):
    """A key's class is outer or nested in it. A class's own name may hold a $
    (Gson's $Gson$Types), so the classes are not read by cutting at each $."""
    cls = key.split("#")[0]
    return cls == outer or cls.startswith(outer + "$")

def left_out(key):
    return key in excluded or any(within(key, e) for e in excluded if "#" not in e)

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
    return own[0].get(key) == "FAILED" or any(within(key, c) for c in own[1])

def unfinished_own(key):
    return any(within(key, c) for c in own[2])

def out_of_time_own(key):
    return any(within(key, c) for c in own[3])

again = [k for k in known if failed_own(k) or unfinished_own(k)]
detect = sorted(k for k in again if passes(k))
alarms = [k for k in again if not passes(k)]
unstable = [k for k in known if not (failed_own(k) or unfinished_own(k))]
# a class that finished on neither revision: none of its methods is known
blind = [c for c in own[2] if c in other[2] and not any(within(k, c) for k in known)]
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

    PRJ=${TAG%-*}; BID=${TAG##*-}

    T=$(mktemp -d "$STAGE_ROOT/measure-XXXXXXXX")
    F="$T/fixed"; B="$T/buggy"; RUNNER="$T/runner"
    echo "[$TAG] staging both versions"
    if ! stage_bug "$PRJ" "$BID" f "$F" "$RES/$TAG.fixed.build.log"; then
        echo "[$TAG] the fixed version could not be staged: $STAGE_FAIL"; rm -rf "$T"; exit 1
    fi
    if ! stage_bug "$PRJ" "$BID" b "$B" "$RES/$TAG.buggy.build.log"; then
        echo "[$TAG] the buggy version could not be staged: $STAGE_FAIL"; rm -rf "$T"; exit 1
    fi
    if ! build_runner4 "$F" "$RUNNER" > "$T/runner.log" 2>&1; then
        echo "[$TAG] the runner does not compile"; cat "$T/runner.log"; rm -rf "$T"; exit 1
    fi

    for ARM in $TODO; do
        if [ "$ARM" = "f7" ]; then
            OWN=$B; OTHER=$F; OWN_KIND=buggy; OTHER_KIND=fixed
        else
            OWN=$F; OTHER=$B; OWN_KIND=fixed; OTHER_KIND=buggy
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

        # ---- its own version ----
        mkdir -p "$OWN/_m-$ARM"
        SP=""
        [ -n "$DRY" ] && SP="-sourcepath $(cat "$OWN/.c7/src-tests")"
        if ! (cd "$OWN" && c3_env javac -nowarn $(javac_level "$OWN") -Xlint:-options -encoding UTF-8 $SP \
                -cp "$(cat "$OWN/.c7/cp-test")" -d "_m-$ARM" $SRCS) > "$P.compile.log" 2>&1; then
            VERDICT=Broken; NOTE="does not compile against its own version"
        else
            OWN_COMPILED=yes
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$OWN" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(cat "$OWN/.c7/cp-test")" AgentTestRunner4 \
                --report "$P.own.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.own.log" 2>&1 < /dev/null
            RC=$?; SEC_O=$SECONDS
            case "$RC" in
                0) ;;
                124|137) VERDICT=Broken; NOTE="does not finish on its own version" ;;
                2) VERDICT=Broken; NOTE="no test method left" ;;
                *) VERDICT=Broken; NOTE="fails on its own version when run again" ;;
            esac
        fi
        METHODS=$(awk -F'\t' '$2 == "method"' "$P.own.tsv" 2>/dev/null | wc -l)
        # f7: acceptance left every test out, so none is left to run
        if [ "$ARM" = "f7" ] && [ -z "$VERDICT" ] && [ "$METHODS" -eq 0 ]; then
            VERDICT=none; NOTE="every test was left out at acceptance"
        fi

        # ---- the other version ----
        # In m7, as in m6, only for a suite that passed again on its own
        # version. In f7 for any suite that compiles on its own, since its
        # left-out tests are run there whatever the rest did.
        if [ "$OWN_COMPILED" = "yes" ] && { [ -z "$VERDICT" ] || [ "$ARM" = "f7" ]; }; then
            mkdir -p "$OTHER/_m-$ARM"
            echo "---- the other version ($OTHER_KIND) ----" >> "$P.compile.log"
            SP=""
            [ -n "$DRY" ] && SP="-sourcepath $(cat "$OTHER/.c7/src-tests")"
            if (cd "$OTHER" && c3_env javac -nowarn $(javac_level "$OTHER") -Xlint:-options -encoding UTF-8 $SP \
                    -cp "$(cat "$OTHER/.c7/cp-test")" -d "_m-$ARM" $SRCS) >> "$P.compile.log" 2>&1; then
                OTHER_COMPILED=yes
            elif [ -z "$VERDICT" ] || [ "$VERDICT" = "none" ]; then
                VERDICT=Broken; NOTE="does not compile against the other version"
            fi
        fi
        if [ -z "$VERDICT" ]; then
            SECONDS=0
            (cd "$OTHER" && c3_env timeout "$RUN_TIMEOUT" java -cp "_m-$ARM:$RUNNER:$(cat "$OTHER/.c7/cp-test")" AgentTestRunner4 \
                --report "$P.other.tsv" --exclude "$SUITE/excluded.txt" $RUN_CLASSES) > "$P.other.log" 2>&1 < /dev/null
            RC=$?; SEC_X=$SECONDS
            case "$RC" in
                0) VERDICT=Pass ;;
                1) VERDICT=Fail; FAILING=$(excluded_from "$P.other.tsv" | paste -sd';' -) ;;
                124|137) VERDICT=Fail; NOTE="timeout" ;;
                *) VERDICT=Broken; NOTE="the runner ended with status $RC on the other version" ;;
            esac
        fi

        # ---- the tests left out at acceptance ----
        LEFT=$(grep -c . "$SUITE/excluded.txt")
        FIRST="$OUT_ABS/runs-$ARM/$TAG.first.tsv"
        if [ "$LEFT" -gt 0 ] && [ "$OTHER_COMPILED" = "yes" ] && [ -f "$FIRST" ]; then
            left_out_runs "$OTHER" "$P.leftout" "$FIRST" "$SUITE/excluded.txt" "$T"
            OWN_REPORT=-
            if [ "$ARM" = "f7" ]; then
                left_out_runs "$OWN" "$P.leftown" "$FIRST" "$SUITE/excluded.txt" "$T"
                OWN_REPORT="$P.leftown.tsv"
            fi
            IFS=$'\x1f' read -r LO_RUN LO_PASS LO_AGAIN LO_DETECT LO_ALARM LO_UNSTABLE DET_KEYS LO_TIMEOUT \
                <<< "$(left_out_counts "$OWN_REPORT" "$P.leftout.tsv" "$SUITE/excluded.txt" "$FIRST")"
        fi

        # ---- detection, the primary outcome ----
        if [ "$ARM" = "m7" ]; then
            DET=$VERDICT; DET_NOTE=$NOTE
        elif [ "$OWN_COMPILED" != "yes" ]; then
            DET=Broken; DET_NOTE="does not compile against its own version"
        elif [ "$OTHER_COMPILED" != "yes" ]; then
            DET=Broken; DET_NOTE="does not compile against the other version"
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
        if [ "$ARM" = "f7" ]; then
            printf '[%s] %s  detection %-6s %s certification %-6s %s%s\n' "$TAG" "$ARM" "$DET" "${DET_NOTE:+($DET_NOTE) }" \
                "$VERDICT" "${NOTE:+($NOTE) }" \
                "${LO_RUN:+  left out: $LO_AGAIN fail again, $LO_DETECT detect, $LO_ALARM false alarms, $LO_UNSTABLE unstable}"
        else
            printf '[%s] %s  %-6s %s%s%s\n' "$TAG" "$ARM" "$VERDICT" "${NOTE:+($NOTE) }" "${NFAIL/#0/}" \
                "${LO_RUN:+  left out: $LO_PASS of $LO_RUN pass on the other version}"
        fi
    done
    rm -rf "$T"
done < "$SUBJECTS"

{
    echo "subject,arm,own_version,verdict,note,methods_run_on_own,keys_left_out,failing_on_other,failing_keys,left_out_methods_run_on_other,left_out_passing_on_other,seconds_own,seconds_other,detection,detection_note,left_out_failing_again_on_own,left_out_detecting,left_out_false_alarms,left_out_unstable,detecting_keys"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in f7 m7; do
            if [ -f "$RES/$TAG.$ARM.verdict" ]; then cat "$RES/$TAG.$ARM.verdict"; fi
        done
    done < "$SUBJECTS"
} > "$RES/verdicts.csv"

echo
# the keys can hold commas, so the file is read as CSV
python3 - "$RES/verdicts.csv" <<'EOF'
import collections, csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
for arm in ("f7", "m7"):
    v = collections.Counter(r["verdict"] for r in rows if r["arm"] == arm)
    d = collections.Counter(r["detection"] for r in rows if r["arm"] == arm)
    print(f"{arm}: verdict: Fail {v['Fail']}, Pass {v['Pass']}, Broken {v['Broken']}, none {v['none']}; "
          f"detection: Fail {d['Fail']}, Pass {d['Pass']}, Broken {d['Broken']}")
EOF

#!/bin/bash
#
# Seventh campaign: mutation score and line coverage of the accepted suites,
# with Major and Cobertura through Defects4J, as in the second campaign
# (data/campaign7/PROTOCOL.md). The coverage and mutation steps of
# bin/analyze-agent-suites.sh, run suite by suite on the version each suite
# was accepted on.
#
# For every bug of the list and every arm with a suite in <OUT>/suites:
#   - the suite as accepted is written out: the test classes as the agent
#     wrote them, with the tests left out at acceptance (excluded.txt)
#     disabled in the source, as the second campaign disabled the tests that
#     failed at its acceptance. bin/disable-tests-campaign7.py does it, finding
#     each by its key: its @Test is put in a comment and a JUnit 3 test is
#     renamed, as bin/prune-failing-tests.py does, but in the declaration the
#     key names, in its own class, wherever its @Test is written (that script
#     looks by the method's name alone, and for @Test on the lines above it).
#     A class left out as a whole, or every test of which was left out, is left
#     out of the archive, since JUnit fails a class with no test left; a nested
#     class in that case is marked @Ignore. An f7 suite whose every test was
#     left out has no figure (status `none`).
#   - the developers' test classes it uses are added to it. Defects4J compiles
#     an archive on its own, without the developers' tests, while the suite was
#     compiled at acceptance in the staged version, with the developers' tests
#     that stay in the working copy. So the version is staged again, the suite
#     is compiled there with those tests' sources on javac's source path and
#     not their classes on its class path, and every source file javac reads
#     from that path is added to the archive: the classes the suite uses, and
#     those they use in turn. None of them is named *AgentTest, and Defects4J
#     runs only the classes that are (-f '*AgentTest.java'), so the suite's
#     own classes are what is run, as they were at acceptance.
#   - the archive is checked before Defects4J runs it: what javac compiled
#     there is run with bin/AgentTestRunner4.java in the staged version, on
#     the class path Defects4J gives it (no compiled developers' tests), and
#     the test methods it runs must be those acceptance kept, by key. If they
#     are not, or the archive does not compile, the suite has no figure, and
#     the note says why. Kept tests that fail in this run are noted.
#   - it is packaged as Defects4J's scripts read a suite, named for the
#     version it was accepted on: <P>-<id>b-f7.1.tar.bz2 in f7 and
#     <P>-<id>f-m7.1.tar.bz2 in m7, the package directories from the root.
#   - run_coverage.pl and then run_mutation.pl measure it, each on its own
#     checkout of that version, on the classes the fix modifies (Defects4J's
#     classes.modified). Gson-14 and Gson-16 are kept out of the mutation step,
#     as in the second campaign: Major's compiler rejects the class both modify
#     (com.google.gson.internal.$Gson$Types). Each step is stopped after
#     STEP_LIMIT seconds (default two hours), and the suite then has no figure
#     for it.
#   - a suite run_coverage.pl calls broken, because a kept test fails in
#     Defects4J's build, has no figure from either step, and the note gives
#     the failure: Major would run it anyway and count what the failing tests
#     do not cover. One case is fixed in advance, as in the second campaign: on
#     Cli, a suite that does not load for want of Hamcrest
#     (NoClassDefFoundError: org/hamcrest/SelfDescribing) is measured through
#     bin/remeasure-cli-evosuite.sh's one-line correction of Cli.build.xml, and
#     the note says so.
#   - bin/merge-agent-metrics.py merges the two tables, counting the mutants
#     detected from Major's kill.csv: FAIL, TIME and EXC.
#
# Output in <OUT>/mutation/:
#   mutation.csv                 one row per bug and arm (below)
#   <bug>.<arm>.archive.log      what was disabled in, left out of or added to
#                                the archive, and what the check run found
#   <bug>.<arm>.check.tsv        the check run's report
#   <bug>.<arm>.failing.log      Defects4J's log of the tests that failed, for a
#                                suite it calls broken (and -stock, with the
#                                coverage log, before the Cli correction)
#   <bug>.<arm>.coverage.log     run_coverage.pl, as it ran
#   <bug>.<arm>.mutation.log     run_mutation.pl, as it ran
#   <bug>.<arm>.kill.csv         Major's verdict on every mutant
#   <bug>.<arm>.row              the row of mutation.csv
#
# Columns of mutation.csv: bug, arm, version, status (ok, none, failed), note,
# mut_generated, mut_covered, mut_killed, mut_killed_d4j, lines_total,
# lines_covered, branches_total, branches_covered, methods_kept,
# methods_left_out, keys_excluded, files_left_out, files_added, seconds.
# files_added counts the developers' test files added to the archive.
#
# A suite that has a .row is not measured again (FORCE=1 to redo).
#
# Usage:
#   ./bin/mutation-campaign7.sh                      # data/campaign7
#   ONLY="Lang-43" ./bin/mutation-campaign7.sh
#   OUT=/tmp/dry ./bin/mutation-campaign7.sh /tmp/dry/subjects.txt

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/bin/campaign7-lib.sh"

OUT=${OUT:-data/campaign7}
SUBJECTS=${1:-data/campaign7/subjects.txt}
ONLY=${ONLY:-}
FORCE=${FORCE:-}
ARMS=${ARMS:-"f7 m7"}
NO_MUTATION=${NO_MUTATION:-"Gson-14 Gson-16"}
STEP_LIMIT=${STEP_LIMIT:-7200}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}
D4J_BIN=$D4J_HOME/framework/bin

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
MUT=$OUT_ABS/mutation

[ -x "$D4J_BIN/run_mutation.pl" ] || { echo "no Defects4J scripts under $D4J_BIN"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
[ -d "$SUITES" ] || { echo "no suites under $SUITES"; exit 1; }
WHY=$(c7_check_env) || { echo "$WHY"; exit 1; }
mkdir -p "$MUT" "$STAGE_ROOT"

# cli_overlay                    sets CLI_OVERLAY, built the first time it is needed
#
# The second campaign's contingency (bin/remeasure-cli-evosuite.sh): Defects4J
# v3.0.1's Cli.build.xml names framework/projects/lib/junit-4.12.jar, which the
# framework does not ship, so a JUnit 4 test that uses Hamcrest does not load
# on the older Cli versions. Nothing in the installation is changed: Defects4J
# reads its projects from $PROJECTS_DIR, so a directory of links to its own
# projects is made, in which Cli.build.xml alone is a copy, with that one path
# corrected to the junit-4.12-hamcrest-1.3.jar the framework ships.
CLI_OVERLAY=""
cli_overlay() {
    [ -n "$CLI_OVERLAY" ] && return 0
    local real="$D4J_HOME/framework/projects" ov e n
    ov=$(mktemp -d "$STAGE_ROOT/cli-overlay-XXXXXXXX")
    mkdir -p "$ov/Cli"
    for e in "$real"/*; do n=$(basename "$e"); [ "$n" = Cli ] || ln -s "$e" "$ov/$n"; done
    for e in "$real"/Cli/*; do n=$(basename "$e"); [ "$n" = Cli.build.xml ] || ln -s "$e" "$ov/Cli/$n"; done
    sed 's|framework/projects/lib/junit-4.12.jar"|framework/projects/lib/junit-4.12-hamcrest-1.3.jar"|' \
        "$real/Cli/Cli.build.xml" > "$ov/Cli/Cli.build.xml"
    if [ "$(diff "$real/Cli/Cli.build.xml" "$ov/Cli/Cli.build.xml" | grep -c '^[<>]')" != 2 ]; then
        echo "the correction of Cli.build.xml does not change exactly one line" >&2; rm -rf "$ov"; return 1
    fi
    CLI_OVERLAY=$ov
    trap 'rm -rf "$CLI_OVERLAY"' EXIT
}

csv() { python3 -c 'import csv, sys; csv.writer(sys.stdout, lineterminator="").writerow(sys.argv[1:])' "$@"; }

# run_limited <seconds> <log> <command...>
# Runs the command in a process group of its own, and ends the whole group if
# it lasts longer than <seconds>. Returns the command's status, or 124.
run_limited() {
    local secs=$1 log=$2 pid waited=0
    shift 2
    setsid "$@" > "$log" 2>&1 < /dev/null &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$waited" -ge "$secs" ]; then
            kill -TERM -- "-$pid" 2>/dev/null; sleep 20; kill -KILL -- "-$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            return 124
        fi
        sleep 5; waited=$((waited + 5))
    done
    wait "$pid"
}

while read -r TAG _rest; do
    TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
    [ -z "$TAG" ] && continue
    case "$TAG" in \#*) continue ;; esac
    if [ -n "$ONLY" ]; then
        case " $ONLY " in *" $TAG "*) ;; *) continue ;; esac
    fi
    P=${TAG%-*}; B=${TAG##*-}

    for ARM in $ARMS; do
        [ -f "$SUITES/${TAG}-${ARM}.tar.bz2" ] || continue
        Q="$MUT/$TAG.$ARM"
        if [ -f "$Q.row" ] && [ -z "$FORCE" ]; then continue; fi
        rm -f "$Q.row" "$Q.archive.log" "$Q.check.tsv" "$Q.coverage.log" "$Q.coverage-stock.log" "$Q.failing.log" \
            "$Q.failing-stock.log" "$Q.mutation.log" "$Q.kill.csv"
        if [ "$ARM" = "f7" ]; then V=b; else V=f; fi
        FIRST="$OUT_ABS/runs-$ARM/$TAG.first.tsv"
        A=$(mktemp -d "$STAGE_ROOT/mutation-XXXXXXXX")
        mkdir -p "$A/suite" "$A/pkg" "$A/out"
        tar -xjf "$SUITES/${TAG}-${ARM}.tar.bz2" -C "$A/suite"
        [ -f "$A/suite/excluded.txt" ] || : > "$A/suite/excluded.txt"
        STATUS=ok; NOTE=""; SECONDS=0

        # ---- the suite as accepted ----
        # the counts go to standard error, which is what is captured here; the
        # keys kept go to kept.txt, the classes to run to run.txt
        COUNTS=$(python3 - "$A/suite" "$A/pkg" "$FIRST" "$ROOT/bin/disable-tests-campaign7.py" "$A" 2>&1 > "$Q.archive.log" <<'EOF'
import os, shutil, subprocess, sys
suite, pkg, first, disable, work = sys.argv[1:6]
excluded = {l.strip() for l in open(os.path.join(suite, "excluded.txt")) if l.strip()}
methods = []
if os.path.isfile(first):
    for line in open(first, errors="replace"):
        cols = line.rstrip("\n").split("\t")
        if len(cols) > 2 and cols[1] == "method":
            methods.append(cols[2])

def within(cls, outer):
    """cls is outer or a class nested in it; a class's own name may hold a $
    (Gson's $Gson$Types), so the chain is not read by cutting at each $"""
    return cls == outer or cls.startswith(outer + "$")

def left_out(key):
    cls = key.split("#")[0]
    return key in excluded or any(within(cls, e) for e in excluded if "#" not in e)

kept = [m for m in methods if not left_out(m)]
files = sorted(os.path.relpath(os.path.join(dp, f), suite)
               for dp, _, fn in os.walk(suite) for f in fn if f.endswith(".java"))
tops = [rel[:-5].replace(os.sep, ".") for rel in files]

def owner(cls):
    """the top-level class of the suite a class is, or is nested in: the longest
    that holds it"""
    hold = [t for t in tops if within(cls, t)]
    return max(hold, key=len) if hold else None

dropped, expect, run = 0, [], []
for rel in files:
    top = rel[:-5].replace(os.sep, ".")
    mine = [m for m in methods if owner(m.split("#")[0]) == top]
    if top in excluded or (mine and all(left_out(m) for m in mine)):
        print(f"left out of the archive: {rel} ({'the class' if top in excluded else 'every test'} was left out)")
        dropped += 1
        continue
    dest = os.path.join(pkg, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy(os.path.join(suite, rel), dest)
    run.append(top)
    expect += [m for m in mine if not left_out(m)]
    keys = sorted(m for m in mine if left_out(m))
    keys += sorted(c for c in excluded if "#" not in c and c != top and owner(c) == top)
    if keys:
        out = subprocess.run([disable, dest, top] + keys, capture_output=True, text=True)
        lines = out.stdout.splitlines()
        for line in lines[:-1]:
            print(f"{rel}: {line}")
        counts = lines[-1].split() if lines else []
        done_of = f"{counts[0]} of {counts[1]}" if len(counts) == 2 else "?"
        print(f"disabled in {rel}: {done_of} keys" + (f" ({out.stderr.strip()})" if out.stderr.strip() else ""))
open(os.path.join(work, "kept.txt"), "w").write("".join(k + "\n" for k in sorted(set(expect))))
open(os.path.join(work, "run.txt"), "w").write("".join(c + "\n" for c in run))
print(f"{len(kept)} {len(methods) - len(kept)} {len(excluded)} {dropped}", file=sys.stderr)
EOF
        ) || { STATUS=failed; NOTE="the archive could not be written: $COUNTS"; COUNTS="0 0 0 0"; }
        read -r KEPT LEFT KEYS DROPPED <<< "$(echo "$COUNTS" | tail -1)"
        GEN=""; COV=""; KILL=""; KD4J=""; LT=""; LC=""; BT=""; BC=""; ADDED=0
        if [ "$STATUS" = ok ] && [ -z "$(find "$A/pkg" -name '*.java' -print -quit)" ]; then
            STATUS=none; NOTE="every test was left out at acceptance"
        fi

        # ---- the developers' test classes the suite uses ----
        if [ "$STATUS" = ok ]; then
            S="$A/stage"
            if ! stage_bug "$P" "$B" "$V" "$S" "$A/stage.log"; then
                STATUS=failed; NOTE="the version could not be staged: $STAGE_FAIL"
            fi
        fi
        if [ "$STATUS" = ok ]; then
            SRC_TESTS=$(cat "$S/.c7/src-tests")
            CPN=$(python3 -c 'import os, sys
cp, drop = sys.argv[1], os.path.normpath(sys.argv[2])
print(":".join(e for e in cp.split(":") if e and os.path.normpath(e) != drop))' \
                  "$(cat "$S/.c7/cp-test")" "$S/$(cat "$S/.c7/bin-tests")")
            mkdir -p "$A/closure"
            if ! (cd "$S" && c3_env javac -verbose -nowarn $(javac_level "$S") -Xlint:-options -encoding UTF-8 \
                    -proc:none -implicit:class -sourcepath "$SRC_TESTS" -cp "$CPN" -d "$A/closure" \
                    $(find "$A/pkg" -name '*.java')) > "$A/closure.log" 2>&1; then
                WHY=$(grep -m1 "error:" "$A/closure.log" | sed -E 's|^.*/([^/]+\.java)|\1|')
                grep -m3 "error:" "$A/closure.log" | sed 's/^/javac, with the developers'"'"' tests: /' >> "$Q.archive.log"
                STATUS=failed; NOTE="the archive does not compile on its own in the staged version: $WHY"
            fi
        fi
        if [ "$STATUS" = ok ]; then
            while read -r REL; do
                [ -z "$REL" ] && continue
                [ -e "$A/pkg/$REL" ] && continue
                mkdir -p "$A/pkg/$(dirname "$REL")"
                cp "$S/$SRC_TESTS/$REL" "$A/pkg/$REL"
                echo "added from the developers' tests: $REL" >> "$Q.archive.log"
                ADDED=$((ADDED + 1))
            done <<< "$(python3 - "$A/closure.log" "$SRC_TESTS" <<'EOF'
import re, sys
log, src = sys.argv[1], sys.argv[2].rstrip("/")
seen = []
for line in open(log, errors="replace"):
    m = re.match(r"\[parsing started DirectoryFileObject\[([^:\]]*):([^\]]+\.java)\]\]$", line.strip())
    if m and m.group(1).rstrip("/") == src and m.group(2) not in seen:
        seen.append(m.group(2))
print("\n".join(seen))
EOF
)"
        fi

        # ---- the check run: does the archive run the tests acceptance kept? ----
        if [ "$STATUS" = ok ]; then
            build_runner4 "$S" "$A/runner" > "$A/runner.log" 2>&1
            (cd "$S" && c3_env timeout "$RUN_TIMEOUT" java -cp "$A/closure:$A/runner:$CPN" \
                AgentTestRunner4 --report "$Q.check.tsv" $(cat "$A/run.txt")) > "$A/check.log" 2>&1
            CHECK=$(python3 - "$Q.check.tsv" "$A/kept.txt" <<'EOF'
import sys
report, kept = sys.argv[1:3]
want = {l.strip() for l in open(kept) if l.strip()}
got, failed, classes = set(), [], []
try:
    for line in open(report, errors="replace"):
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 3:
            continue
        if cols[1] == "method":
            got.add(cols[2])
            if cols[0] == "FAILED":
                failed.append(cols[2])
        elif cols[1] == "class" and cols[0] == "FAILED":
            classes.append(cols[2])
except OSError:
    print("differs|the check run gave no report")
    sys.exit()
extra, missing = sorted(got - want), sorted(want - got)
if extra or missing or classes:
    why = []
    if extra:
        why.append(f"{len(extra)} test(s) run that acceptance left out, e.g. {extra[0]}")
    if missing:
        why.append(f"{len(missing)} kept test(s) not run, e.g. {missing[0]}")
    if classes:
        why.append(f"{len(classes)} class(es) failing as a whole, e.g. {classes[0]}")
    print("differs|" + "; ".join(why))
else:
    print(f"same|{len(got)} {len(failed)}" + (f"|{failed[0]}" if failed else ""))
EOF
)
            case "$CHECK" in
                same\|*)
                    read -r NRUN NFAIL <<< "$(echo "$CHECK" | cut -d'|' -f2)"
                    echo "check run: the archive runs the $NRUN tests acceptance kept; $NFAIL of them fail there" >> "$Q.archive.log"
                    [ "$NFAIL" -gt 0 ] && NOTE="${NOTE:+$NOTE; }$NFAIL kept test(s) fail in the check run, e.g. $(echo "$CHECK" | cut -d'|' -f3)"
                    ;;
                *)
                    echo "check run: ${CHECK#differs|}" >> "$Q.archive.log"
                    STATUS=failed; NOTE="the archive does not run the tests acceptance kept: ${CHECK#differs|}"
                    ;;
            esac
        fi

        if [ "$STATUS" = ok ]; then
            (cd "$A/pkg" && tar cjf "$A/${P}-${B}${V}-${ARM}.1.tar.bz2" .)
            mkdir -p "$A/d"; mv "$A/${P}-${B}${V}-${ARM}.1.tar.bz2" "$A/d/"
            HARNESS=()
            run_limited "$STEP_LIMIT" "$Q.coverage.log" "$D4J_BIN/run_coverage.pl" -p "$P" -d "$A/d" -o "$A/out" -t "$A" \
                -f '*AgentTest.java'
            [ $? -eq 124 ] && NOTE="${NOTE:+$NOTE; }coverage stopped after ${STEP_LIMIT}s"
            # ---- a test that fails in Defects4J's build ----
            # run_coverage.pl calls the suite broken; Major would run it and count
            # what it does not cover, so the figure would be another suite's
            if grep -q "Broken test suite" "$Q.coverage.log"; then
                FL=$(find "$A/out/coverage_log" -name '*.failing.log' 2>/dev/null | head -1)
                [ -n "$FL" ] && cp "$FL" "$Q.failing.log"
                if [ "$P" = Cli ] && grep -q "org/hamcrest/SelfDescribing" "$Q.failing.log" 2>/dev/null \
                        && cli_overlay; then
                    # the contingency the protocol fixes, as in the second campaign:
                    # the one-line correction of Cli.build.xml
                    HARNESS=(env "PROJECTS_DIR=$CLI_OVERLAY")
                    NOTE="${NOTE:+$NOTE; }measured through bin/remeasure-cli-evosuite.sh's one-line correction of Cli.build.xml: on Defects4J's own the suite does not load (NoClassDefFoundError: org/hamcrest/SelfDescribing)"
                    mv "$Q.coverage.log" "$Q.coverage-stock.log"; mv "$Q.failing.log" "$Q.failing-stock.log"
                    rm -rf "$A/out"; mkdir -p "$A/out"
                    run_limited "$STEP_LIMIT" "$Q.coverage.log" "${HARNESS[@]}" "$D4J_BIN/run_coverage.pl" -p "$P" -d "$A/d" \
                        -o "$A/out" -t "$A" -f '*AgentTest.java'
                    FL=$(find "$A/out/coverage_log" -name '*.failing.log' 2>/dev/null | head -1)
                    [ -n "$FL" ] && cp "$FL" "$Q.failing.log"
                fi
                if grep -q "Broken test suite" "$Q.coverage.log"; then
                    WHY=$(grep -m1 -v -E '^---|^[[:space:]]+at |^[[:space:]]*$' "$Q.failing.log" 2>/dev/null | cut -c1-200)
                    STATUS=failed
                    NOTE="${NOTE:+$NOTE; }a kept test fails in Defects4J's build, so neither step is counted: ${WHY:-see the failing log}"
                fi
            fi
            if [ "$STATUS" = ok ]; then
                case " $NO_MUTATION " in
                    *" $TAG "*) NOTE="${NOTE:+$NOTE; }kept out of the mutation step, as in the second campaign" ;;
                    *)
                        run_limited "$STEP_LIMIT" "$Q.mutation.log" "${HARNESS[@]}" "$D4J_BIN/run_mutation.pl" -p "$P" -d "$A/d" \
                            -o "$A/out" -t "$A" -f '*AgentTest.java'
                        [ $? -eq 124 ] && NOTE="${NOTE:+$NOTE; }mutation stopped after ${STEP_LIMIT}s"
                        KC=$(find "$A/out/mutation_log" -name '*.kill.csv' 2>/dev/null | head -1)
                        [ -n "$KC" ] && cp "$KC" "$Q.kill.csv"
                        ;;
                esac
                python3 "$ROOT/bin/merge-agent-metrics.py" "$A/out" -o "$A/out/agent-metrics.csv" > "$A/merge.log" 2>&1
                IFS=, read -r GEN COV KILL KD4J LT LC BT BC <<< "$(python3 - "$A/out/agent-metrics.csv" <<'EOF'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
r = rows[0] if rows else {}
print(",".join(r.get(k, "") or "" for k in ("mut_generated", "mut_covered", "mut_killed", "mut_killed_d4j",
                                             "lines_total", "lines_covered", "branches_total", "branches_covered")))
EOF
)"
                grep -h "WARNING" "$A/merge.log" >> "$Q.archive.log"
                if [ -z "$LT" ] && [ -z "$KILL" ]; then
                    STATUS=failed; NOTE="${NOTE:+$NOTE; }neither coverage nor mutation gave a figure"
                    # the first thing the compiler said, when the archive did not compile
                    WHY=$(cat "$Q.coverage.log" "$Q.mutation.log" 2>/dev/null | grep -m1 "\[javac\].*error:" \
                          | sed -E 's/^.*\[javac\] *//; s|^.*/([^/]+\.java)|\1|')
                    [ -n "$WHY" ] && NOTE="$NOTE; the archive does not compile in Defects4J: $WHY"
                fi
            fi
        fi
        csv "$TAG" "$ARM" "${B}${V}" "$STATUS" "$NOTE" "$GEN" "$COV" "$KILL" "$KD4J" "$LT" "$LC" "$BT" "$BC" \
            "${KEPT:-}" "${LEFT:-}" "${KEYS:-}" "${DROPPED:-}" "$ADDED" "$SECONDS" > "$Q.row"
        echo >> "$Q.row"
        printf '[%s] %s  %s  mutants %s/%s  lines %s/%s  developers'"'"' files added %s  %s\n' "$TAG" "$ARM" "$STATUS" \
            "${KILL:--}" "${GEN:--}" "${LC:--}" "${LT:--}" "$ADDED" "${NOTE}"
        rm -rf "$A"
    done
done < "$SUBJECTS"

{
    echo "bug,arm,version,status,note,mut_generated,mut_covered,mut_killed,mut_killed_d4j,lines_total,lines_covered,branches_total,branches_covered,methods_kept,methods_left_out,keys_excluded,files_left_out,files_added,seconds"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in f7 m7; do
            [ -f "$MUT/$TAG.$ARM.row" ] && cat "$MUT/$TAG.$ARM.row"
        done
    done < "$SUBJECTS"
} > "$MUT/mutation.csv"

python3 - "$MUT/mutation.csv" <<'EOF'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
for arm in ("f7", "m7"):
    r = [x for x in rows if x["arm"] == arm]
    ok = [x for x in r if x["mut_generated"].isdigit() and x["mut_killed"].isdigit() and int(x["mut_generated"]) > 0]
    g = sum(int(x["mut_generated"]) for x in ok); k = sum(int(x["mut_killed"]) for x in ok)
    lt = sum(int(x["lines_total"]) for x in r if x["lines_total"].isdigit())
    lc = sum(int(x["lines_covered"]) for x in r if x["lines_covered"].isdigit())
    print(f"{arm}: {len(r)} suites, {len(ok)} with a mutation figure; pooled mutation score "
          f"{100 * k / g:.1f}%" if g else f"{arm}: {len(r)} suites, no mutation figure", end="")
    print(f"; pooled line coverage {100 * lc / lt:.1f}%" if lt else "")
EOF

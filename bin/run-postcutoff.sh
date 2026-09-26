#!/bin/bash
#
# Post-cutoff replication. Both arms, detection only.
#
# WHY DETECTION ONLY
# ------------------
# This corpus exists to test one threat: that the implementation-visible arm's
# 72% reflects recall of faults seen in training rather than test-writing.
# Recall affects *detection* — the model remembers the fault and writes the
# test that catches it. It does not affect mutation score, which measures
# assertion strength against whatever code is in front of the agent and does
# not depend on remembering anything. Coverage likewise.
#
# So mutation and coverage are not measured here. They are already measured
# over 36 Defects4J bugs and are not what is in question. Standing up JaCoCo
# and PIT across four Maven projects would cost a day and, at n=11, would add
# nothing to a result resting on 36 pairs.
#
# WHAT IS MEASURED
# ----------------
# For each subject and arm: does the generated suite pass on the fixed revision
# and fail on the buggy one? Same criterion as Defects4J's run_bug_detection.
#
# Subjects come from bin/mine-postcutoff.sh, which validated fail-to-pass for
# each and recorded the metadata this script consumes.
#
# Usage:
#   ARM=agent MODEL=sonnet ./bin/run-postcutoff.sh
#   ARM=spec  MODEL=sonnet ./bin/run-postcutoff.sh

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
MINING=${MINING:-$HOME/code/mining}
SUBJECTS=data/postcutoff
RUNS=data/postcutoff-runs
ARM=${ARM:-agent}
MODEL=${MODEL:-sonnet}
MAX_TURNS=${MAX_TURNS:-50}
MAX_DEAD=${MAX_DEAD:-2}

case "$ARM" in
  agent|spec) ;;
  *) echo "ARM must be 'agent' (implementation-visible) or 'spec'"; exit 1 ;;
esac
command -v mvn    >/dev/null || { echo "mvn not on PATH"; exit 1; }
command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
[ "$ARM" = spec ] && { command -v javadoc >/dev/null || { echo "javadoc not on PATH"; exit 1; }; }

mkdir -p "$ROOT/$RUNS"
DEAD=0
ABORTED=no

for D in "$ROOT/$SUBJECTS"/*/; do
    [ "$(cat "$D/status" 2>/dev/null)" = "ok" ] || continue

    TAG=$(basename "$D")
    REPO=$(grep '^project=' "$D/meta.txt" | cut -d= -f2)
    SHA=$(grep '^sha='     "$D/meta.txt" | cut -d= -f2)
    R="$MINING/$REPO"

    STATUS="$ROOT/$RUNS/${TAG}.${ARM}.status"
    if [ -f "$STATUS" ]; then
        echo "[$TAG/$ARM] already attempted ($(cat "$STATUS")) — skipping"
        continue
    fi
    fail() { echo "[$TAG/$ARM] $1"; echo "$1" > "$STATUS"; }

    WF=/tmp/pcF_${TAG}_${ARM}      # worktree at the fixed commit
    WB=/tmp/pcB_${TAG}_${ARM}      # worktree at the parent (buggy) commit
    SPEC=/tmp/pcS_${TAG}           # spec-arm sandbox

    echo "[$TAG/$ARM] worktrees"
    git -C "$R" worktree remove --force "$WF" 2>/dev/null
    git -C "$R" worktree remove --force "$WB" 2>/dev/null
    rm -rf "$WF" "$WB" "$SPEC"
    git -C "$R" worktree add -q --detach "$WF" "$SHA"    || { fail "worktree (fixed) failed"; continue; }
    git -C "$R" worktree add -q --detach "$WB" "$SHA~1"  || { fail "worktree (buggy) failed"; continue; }

    CLASSES=$(cat "$D/classes.txt")
    TESTCLASSES=$(cat "$D/testclasses.txt")

    # the developer tests that expose the fault must not be visible
    for tc in $TESTCLASSES; do
        rm -f "$WF/src/test/java/$(echo "$tc" | tr '.' '/').java"
    done
    if ! (cd "$WF" && mvn -q test-compile -Drat.skip=true -Dcheckstyle.skip=true -Dpmd.skip=true -Dspotbugs.skip=true) \
            > "$ROOT/$RUNS/${TAG}.${ARM}.precompile" 2>&1; then
        fail "test-compile fails after removing developer tests"; continue
    fi

    EXPECTED=$(for c in $CLASSES; do echo "${c##*.}AgentTest"; done | paste -sd, -)
    CLASS_LIST=$(printf '  - %s\n' $CLASSES)

    # ---- arm-specific workspace and prompt --------------------------------
    if [ "$ARM" = agent ]; then
        WORKDIR="$WF"
        PROMPT="Write JUnit test classes for these classes:

$CLASS_LIST

Requirements:
- One test class per class above, named <ClassName>AgentTest, in the same
  package, under src/test/java/
- Self-contained: do not extend or import any other test class or helper.
- Match the JUnit version and assertion style of the other tests in this
  project. Check them before writing.
- Test only the public API. Assert on returned values and observable state,
  not merely that no exception is thrown. Cover boundary and error cases.
- Do not modify or create any file other than the test classes named above.

Restrictions:
- Do not inspect version control history. Do not run git.
- Do not search the web.

Verify with: mvn test -Dtest=$EXPECTED"
    else
        mkdir -p "$SPEC/api" "$SPEC/lib" "$SPEC/tests"
        WORKDIR="$SPEC"

        SRC_FILES=""
        for c in $CLASSES; do
            SRC_FILES="$SRC_FILES $WF/src/main/java/$(echo "$c" | tr '.' '/').java"
        done
        (cd "$WF" && mvn -q dependency:build-classpath -Dmdep.outputFile=/tmp/cp_$TAG.txt) \
            >/dev/null 2>&1
        CP=$(cat /tmp/cp_$TAG.txt 2>/dev/null)

        javadoc -quiet -package -Xdoclint:none \
            -d "$SPEC/api" -sourcepath "$WF/src/main/java" -classpath "$CP" \
            $SRC_FILES > "$ROOT/$RUNS/${TAG}.javadoc" 2>&1
        [ -f "$SPEC/api/index.html" ] || { fail "javadoc failed"; continue; }

        (cd "$WF" && mvn -q test-compile) >/dev/null 2>&1
        (cd "$WF/target/classes" && jar cf "$SPEC/lib/project.jar" .) \
            || { fail "could not jar the compiled classes"; continue; }
        echo "$CP" | tr ':' '\n' | grep -iE 'junit|hamcrest|opentest4j|apiguardian' \
            | while read -r j; do [ -f "$j" ] && cp "$j" "$SPEC/lib/"; done
        ls "$SPEC/lib" | grep -qi junit || { fail "no junit jar for the sandbox"; continue; }

        cat > "$SPEC/compile.sh" <<'EOS'
#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p out
find tests -name '*.java' > .sources
javac -nowarn -cp "lib/*" -d out @.sources
echo "compiled OK"
EOS
        chmod +x "$SPEC/compile.sh"

        PROMPT="Write JUnit test classes for these classes:

$CLASS_LIST

You do NOT have the implementation source. You have:
  api/          generated javadoc for the classes above — this is your spec
  lib/          the compiled project and JUnit
  compile.sh    compiles everything under tests/ against lib/

Requirements:
- One test class per class above, named <ClassName>AgentTest, in the same
  package, under tests/ following the package directory structure.
- Self-contained: do not extend or import any other test class or helper.
- Match the JUnit version present in lib/.
- Assert on returned values and observable state, not merely that no exception
  is thrown. Cover boundary and error cases.
- Base every expectation on the documented contract in api/.

Restrictions:
- Do NOT run the tests. Compile them with ./compile.sh, nothing else.
- Do NOT decompile or disassemble lib/ (no javap -c, no decompilers).
- Do not inspect version control history. Do not search the web.

Finish when ./compile.sh reports success."
    fi

    # ---- invoke ------------------------------------------------------------
    echo "[$TAG/$ARM] invoking agent ($MODEL)"
    (cd "$WORKDIR" && claude -p "$PROMPT" \
        --model "$MODEL" --allowedTools "Read,Write,Bash" \
        --permission-mode acceptEdits --max-turns "$MAX_TURNS" \
        --output-format json) > "$ROOT/$RUNS/${TAG}.${ARM}.json" 2>/dev/null

    VERDICT=$(python3 -c "
import json
try:
    d = json.load(open('$ROOT/$RUNS/${TAG}.${ARM}.json'))
except Exception:
    print('dead|unparseable|0|0'); raise SystemExit
cost = d.get('total_cost_usd') or 0
turns = d.get('num_turns') or 0
err = bool(d.get('is_error'))
res = (d.get('result') or '').replace('|', ' ')[:100]
limit = 'session limit' in res or 'rate limit' in res or d.get('api_error_status') == 429
print(('ok' if not err else ('dead' if (cost == 0 or limit) else 'error'))
      + f'|{res}|{cost:.3f}|{turns}')" 2>/dev/null)
    STATE="${VERDICT%%|*}"; REST="${VERDICT#*|}"; MSG="${REST%%|*}"; NUMS="${REST#*|}"
    echo "[$TAG/$ARM] agent done: \$${NUMS%|*} turns=${NUMS#*|} state=$STATE"

    if [ "$STATE" = dead ]; then
        DEAD=$((DEAD + 1)); echo "[$TAG/$ARM] $MSG"
        [ "$DEAD" -ge "$MAX_DEAD" ] && { echo; echo "ABORTING: usage limit."; ABORTED=yes; break; }
        continue
    fi
    DEAD=0
    [ "$STATE" = error ] && { fail "agent run returned an error"; continue; }

    # ---- collect what was written -----------------------------------------
    if [ "$ARM" = spec ]; then
        WRITTEN=$(cd "$SPEC/tests" && find . -name "*AgentTest.java" 2>/dev/null)
        [ -z "$WRITTEN" ] && { fail "agent produced no test file"; continue; }
        for f in $WRITTEN; do
            mkdir -p "$WF/src/test/java/$(dirname "$f")"
            cp "$SPEC/tests/$f" "$WF/src/test/java/$f"
        done
    else
        WRITTEN=$(cd "$WF/src/test/java" && find . -name "*AgentTest.java" 2>/dev/null)
        [ -z "$WRITTEN" ] && { fail "agent produced no test file"; continue; }
    fi
    RUN_ARG=$(echo "$WRITTEN" | sed 's|.*/||; s|\.java$||' | paste -sd, -)
    echo "$WRITTEN" > "$ROOT/$RUNS/${TAG}.${ARM}.written"

    # ---- acceptance: prune failing methods, keep the rest ------------------
    #
    # Rejecting a whole suite over one wrong expectation is not an option here.
    # On the Defects4J corpus the specification-only arm needed 3.3% of tests
    # disabled; applying an all-or-nothing filter to this corpus discarded half
    # the suites outright, and the survivors were a biased sample — only those
    # that happened to come out perfect. Both arms use the same filter, so the
    # between-arm comparison stays clean.
    #
    # Note the .class deletion: editing a @Test annotation changes the .java by
    # a few bytes within the same second, and Maven's incremental compile can
    # skip the rebuild, leaving the previous bytecode in place and the loop
    # never converging.
    METHODS_TOTAL=0
    for f in $WRITTEN; do
        C=$(grep -cE "@Test|public void test" "$WF/src/test/java/$f" 2>/dev/null || echo 0)
        METHODS_TOTAL=$((METHODS_TOTAL + C))
    done
    PRUNED_TOTAL=0
    ACCEPTED=no

    for round in 1 2 3 4 5; do
        if (cd "$WF" && mvn test -Dtest="$RUN_ARG" -DfailIfNoTests=false -Drat.skip=true -Dcheckstyle.skip=true -Dpmd.skip=true -Dspotbugs.skip=true) \
                > "$ROOT/$RUNS/${TAG}.${ARM}.fixed.log" 2>&1; then
            ACCEPTED=yes; break
        fi

        if grep -q "COMPILATION ERROR" "$ROOT/$RUNS/${TAG}.${ARM}.fixed.log"; then
            fail "agent tests do not compile in the project"; break
        fi

        # surefire lists failures as "  ClassName.methodName:LINE ..."
        FAILING=$(grep -oP '^\[ERROR\]\s+\K\w+\.\w+(?=[:(])' \
                    "$ROOT/$RUNS/${TAG}.${ARM}.fixed.log" \
                  | sed 's|.*\.||' | sort -u)
        if [ -z "$FAILING" ]; then
            fail "tests fail on the fixed revision but no method names parsed"; break
        fi

        NPRUNED=0
        for f in $WRITTEN; do
            OUT=$("$ROOT/bin/prune-failing-tests.py" "$WF/src/test/java/$f" $FAILING)
            NPRUNED=$((NPRUNED + ${OUT%% *}))
            REL="${f#./}"; REL="${REL%.java}"
            rm -f "$WF/target/test-classes/$REL.class" "$WF/target/test-classes/$REL"\$*.class
        done
        PRUNED_TOTAL=$((PRUNED_TOTAL + NPRUNED))
        echo "[$TAG/$ARM] round $round: disabled $NPRUNED failing test(s)"
        [ "$NPRUNED" -eq 0 ] && { fail "failing methods could not be disabled"; break; }
    done
    [ -f "$STATUS" ] && continue
    [ "$ACCEPTED" != yes ] && { fail "suite did not converge after pruning"; continue; }

    echo "$PRUNED_TOTAL $METHODS_TOTAL" > "$ROOT/$RUNS/${TAG}.${ARM}.pruned"
    if [ "$METHODS_TOTAL" -gt 0 ] && [ "$PRUNED_TOTAL" -ge "$METHODS_TOTAL" ]; then
        fail "every test failed on the fixed revision"; continue
    fi
    echo "[$TAG/$ARM] pruned $PRUNED_TOTAL of $METHODS_TOTAL tests"

    # ---- detection: copy into the buggy worktree and run -------------------
    for f in $WRITTEN; do
        mkdir -p "$WB/src/test/java/$(dirname "$f")"
        cp "$WF/src/test/java/$f" "$WB/src/test/java/$f"
    done
    (cd "$WB" && mvn test -Dtest="$RUN_ARG" -DfailIfNoTests=false) \
        > "$ROOT/$RUNS/${TAG}.${ARM}.buggy.log" 2>&1
    BUGGY_RC=$?

    if grep -q "COMPILATION ERROR" "$ROOT/$RUNS/${TAG}.${ARM}.buggy.log"; then
        VERDICT_DET="uncompilable_on_buggy"
    elif [ "$BUGGY_RC" -ne 0 ]; then
        VERDICT_DET="Fail"
    else
        VERDICT_DET="Pass"
    fi
    echo "$VERDICT_DET" > "$ROOT/$RUNS/${TAG}.${ARM}.detection"
    echo "ok" > "$STATUS"
    echo "[$TAG/$ARM] detection: $VERDICT_DET"

    git -C "$R" worktree remove --force "$WF" 2>/dev/null
    git -C "$R" worktree remove --force "$WB" 2>/dev/null
done

echo
[ "$ABORTED" = yes ] && echo "*** aborted early — rerun to resume ***" && echo
TOT=$(ls "$ROOT/$RUNS"/*.${ARM}.detection 2>/dev/null | wc -l)
DET=$(grep -lx Fail "$ROOT/$RUNS"/*.${ARM}.detection 2>/dev/null | wc -l)
echo "arm $ARM: $DET/$TOT detected"
echo "pruned:  $(cd "$ROOT" && awk '{p+=$1; t+=$2} END{if(t) printf "%d of %d (%.1f%%)", p, t, 100*p/t}' "$RUNS"/*.$ARM.pruned 2>/dev/null)"
echo "cost:    \$$(cd "$ROOT" && python3 - <<EOF
import json, glob
t = 0.0
for f in glob.glob('$RUNS/*.$ARM.json'):
    try:
        t += json.load(open(f)).get('total_cost_usd', 0) or 0
    except Exception:
        pass
print(f"{t:.2f}")
EOF
)"

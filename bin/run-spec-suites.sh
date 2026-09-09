#!/bin/bash
#
# Study B, spec arm: generate test suites from the PUBLIC API ONLY.
#
# The implementation-visible arm (run-agent-suites.sh) reached 72% real-fault
# detection, but that figure is a ceiling rather than a capability measure: the
# agent reads the fixed source, which already contains the repair, so writing a
# test for the current behaviour is enough to catch the fault by construction.
#
# This arm removes that shortcut. The agent works in a sandbox containing:
#   api/     generated javadoc for the classes under test
#   lib/     the compiled project jar and JUnit, so tests can be COMPILED
#   tests/   where it writes
# It never sees a line of implementation source, and it may not execute the
# tests it writes — executing would let it observe behaviour and become a
# mirror through the back door, which is the very thing being measured.
#
# Measured on the first nine bugs: 1/9 real-fault detection against 8/9 for the
# same bugs in the M arm, at a slightly HIGHER mutation score. Writing from the
# javadoc produces suites that discriminate behaviour just as well and catch
# almost no real faults.
#
# PER-METHOD FILTER
# -----------------
# Failing methods are disabled individually (bin/prune-failing-tests.py) rather
# than discarding the whole suite. Measured prune rate: 2 of 365 methods (1%).
# Writing from the javadoc alone turns out to produce almost no wrong
# expectations, which retires the hypothesis that the spec arm would guess.
#
# Declared bias: that filter uses the implementation as an oracle, so what
# survives is precisely the subset agreeing with the code. It only removes,
# never rewrites, and the survivors were written blind — but the selection is
# biased and must be reported as such. The M arm carries the same bias, so the
# comparison between arms stays clean.
#
# JAVADOC INVOCATION
# ------------------
# Four details had to line up, all found the hard way:
#   - Pass FILE PATHS, not fully-qualified class names. Given a qualified name
#     without .java, javadoc treats it as a package (Lang-43).
#   - Keep -sourcepath anyway, so sibling classes referenced by the source
#     resolve — otherwise "cannot find symbol: class Validate".
#   - Use -package, not -public: some classes under test are package-private
#     and -public documents nothing at all (Lang-62, "No public or protected
#     classes found to document"). -package gives the agent what a developer
#     in the same package would see, which is the situation being modelled.
#   - Judge success by the existence of api/index.html, never by exit status:
#     this vintage of source produces warnings javadoc reports as non-zero.
#
# SOURCE LEVEL
# ------------
# The sandbox must compile with the project's own -source level. Lang-65 was
# lost because the agent wrote 1_017_320_701_000L, valid under the sandbox's
# default javac but not under the project's -source 1.6. The level is read
# from the project's default.properties and passed both to compile.sh and to
# the prompt.
#
# STALE CLASS FILES AFTER PRUNING
# -------------------------------
# Disabling a method only comments out its @Test annotation, so the .java file
# changes by a few bytes within the same second. Ant compares timestamps at
# one-second granularity and skips the recompile, and the next run executes the
# OLD .class — the same methods fail round after round and the loop gives up
# (Lang-21). `touch` does not help for the same reason. The compiled test
# classes are therefore DELETED before recompiling, inner classes included.
#
# KNOWN LIMITATION
# ----------------
# lib/ contains compiled classes, so a decompiler or `javap -c` would recover
# the logic. The prompt forbids it, but this is an honour-system control, not
# a technical one. The sandboxes are kept (not deleted after a successful run)
# so the transcript and workspace can be audited.
#
# Usage:
#   ARM=spec MODEL=sonnet MAX_TURNS=50 ./bin/run-spec-suites.sh

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)

SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
SUITES=data/agent-suites
RUNS=data/spec-runs
ARM=${ARM:-spec}
MODEL=${MODEL:-sonnet}
MAX_TURNS=${MAX_TURNS:-50}
MAX_DEAD=${MAX_DEAD:-2}
MAX_PRUNE_ROUNDS=5

command -v defects4j >/dev/null || { echo "defects4j not on PATH"; exit 1; }
command -v claude    >/dev/null || { echo "claude not on PATH"; exit 1; }
command -v javadoc   >/dev/null || { echo "javadoc not on PATH (install a JDK)"; exit 1; }
[ -f "$SAMPLE" ] || { echo "sample file not found: $SAMPLE"; exit 1; }
[ "${TZ:-}" = "America/Los_Angeles" ] || echo "WARNING: TZ is not America/Los_Angeles"

mkdir -p "$ROOT/$SUITES" "$ROOT/$RUNS"

write_stub() {
    local path=$1 fqcn=$2 j3=$3
    local pkg="${fqcn%.*}" cls="${fqcn##*.}"
    mkdir -p "$(dirname "$path")"
    if [ "$j3" = "yes" ]; then
        cat > "$path" <<EOF
package $pkg;

import junit.framework.Test;
import junit.framework.TestCase;
import junit.framework.TestSuite;

/** Stub: developer tests removed for the agent test-generation experiment. */
public class $cls extends TestCase {
    public $cls(String name) { super(name); }
    public static Test suite() { return new TestSuite($cls.class); }
    public void testStub() { assertTrue(true); }
}
EOF
    else
        cat > "$path" <<EOF
package $pkg;

import static org.junit.Assert.assertTrue;
import org.junit.Test;

/** Stub: developer tests removed for the agent test-generation experiment. */
public class $cls {
    @Test public void testStub() { assertTrue(true); }
}
EOF
    fi
}

count_tests() {   # count_tests <file...>
    local total=0 f c
    for f in "$@"; do
        c=$(grep -cE "@Test|public void test" "$f" 2>/dev/null || echo 0)
        total=$((total + c))
    done
    echo "$total"
}

n=0
DEAD=0
ABORTED=no

while IFS=, read -r P B _rest; do
    P=$(echo "${P:-}" | tr -d '[:space:]')
    B=$(echo "${B:-}" | tr -d '[:space:]')
    [ -z "$P" ] && continue
    case "$P" in \#*) continue ;; esac

    n=$((n + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$n" -gt "$LIMIT" ]; then break; fi

    TAG="${P}-${B}"
    ARCHIVE="$ROOT/$SUITES/${P}-${B}f-${ARM}.1.tar.bz2"
    RUNDIR="$ROOT/$RUNS"
    STATUS="$RUNDIR/${TAG}.status"

    if [ -f "$STATUS" ]; then
        echo "[$TAG] already attempted ($(cat "$STATUS")) — skipping"
        continue
    fi

    W=/tmp/specB_${P}_${B}_f
    SPEC=/tmp/specW_${P}_${B}
    fail() { echo "[$TAG] $1"; echo "$1" > "$STATUS"; }

    echo "[$TAG] checkout"
    rm -rf "$W" "$SPEC"
    if ! defects4j checkout -p "$P" -v "${B}f" -w "$W" >/dev/null 2>&1; then
        fail "checkout failed"; continue
    fi

    SRC_TESTS=$(cd "$W" && defects4j export -p dir.src.tests 2>/dev/null | grep -v '^Running' | tail -1)
    SRC_CLASSES=$(cd "$W" && defects4j export -p dir.src.classes 2>/dev/null | grep -v '^Running' | tail -1)
    BIN_CLASSES=$(cd "$W" && defects4j export -p dir.bin.classes 2>/dev/null | grep -v '^Running' | tail -1)
    BIN_TESTS=$(cd "$W" && defects4j export -p dir.bin.tests 2>/dev/null | grep -v '^Running' | tail -1)
    CP_COMPILE=$(cd "$W" && defects4j export -p cp.compile 2>/dev/null | grep -v '^Running' | tail -1)
    CLASSES=$(cd "$W" && defects4j export -p classes.modified 2>/dev/null | grep -v '^Running' | grep -v '^$')
    TRIGGERS=$(cd "$W" && defects4j export -p tests.trigger 2>/dev/null | grep '::')

    if [ -z "$SRC_TESTS" ] || [ -z "$SRC_CLASSES" ] || [ -z "$CLASSES" ]; then
        fail "could not export metadata"; continue
    fi
    printf '%s\n' "$CLASSES" > "$RUNDIR/${TAG}.classes"

    # the project's own -source level; the sandbox must not be more permissive
    SRC_LEVEL=$(grep -h "^compile\.source" "$W"/*.properties 2>/dev/null \
                  | head -1 | cut -d= -f2 | tr -d '[:space:]')
    SRC_LEVEL=${SRC_LEVEL:-8}
    echo "$SRC_LEVEL" > "$RUNDIR/${TAG}.srclevel"

    rm -rf "$W/.git"

    DELETED=""
    while read -r T; do
        [ -z "$T" ] && continue
        CLS="${T%%::*}"
        F="$W/$SRC_TESTS/$(echo "$CLS" | tr '.' '/').java"
        [ -f "$F" ] || continue
        if grep -q "extends TestCase\|junit.framework" "$F"; then J3=yes; else J3=no; fi
        DELETED="$DELETED $CLS:$J3"
        rm -f "$F"
    done <<< "$TRIGGERS"

    if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.precompile" 2>&1; then
        echo "[$TAG] compile broke after deletion, writing stubs"
        for D in $DELETED; do
            write_stub "$W/$SRC_TESTS/$(echo "${D%%:*}" | tr '.' '/').java" \
                       "${D%%:*}" "${D##*:}"
        done
        if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.precompile2" 2>&1; then
            fail "compile fails even with stubs"; continue
        fi
    fi

    CP=$(cd "$W" && defects4j export -p cp.test 2>/dev/null | grep -v '^Running' | tail -1)
    EXTRA=$(find ~/defects4j/framework/projects/"$P"/lib -name '*.jar' 2>/dev/null | tr '\n' ':')
    CP="$CP:$EXTRA"

    # ---- build the spec-only sandbox ---------------------------------------
    mkdir -p "$SPEC/api" "$SPEC/lib" "$SPEC/tests"

    SRC_FILES=""
    for C in $CLASSES; do
        SRC_FILES="$SRC_FILES $W/$SRC_CLASSES/$(echo "$C" | tr '.' '/').java"
    done

    javadoc -quiet -package -Xdoclint:none \
        -d "$SPEC/api" \
        -sourcepath "$W/$SRC_CLASSES" \
        -classpath "$CP_COMPILE" \
        $SRC_FILES > "$RUNDIR/${TAG}.javadoc" 2>&1
    [ -f "$SPEC/api/index.html" ] || { fail "javadoc failed"; continue; }

    if [ -n "$BIN_CLASSES" ] && [ -d "$W/$BIN_CLASSES" ]; then
        (cd "$W/$BIN_CLASSES" && jar cf "$SPEC/lib/project.jar" .) \
            || { fail "could not jar the compiled classes"; continue; }
    else
        fail "could not locate dir.bin.classes"; continue
    fi
    find ~/defects4j/framework/projects/"$P"/lib -name 'junit*.jar' \
        -exec cp {} "$SPEC/lib/" \; 2>/dev/null
    echo "$CP" | tr ':' '\n' | grep -i 'junit.*\.jar$' | while read -r j; do
        [ -f "$j" ] && cp "$j" "$SPEC/lib/" 2>/dev/null
    done
    if ! ls "$SPEC/lib" | grep -qi junit; then
        fail "no junit jar found for the sandbox"; continue
    fi

    cat > "$SPEC/compile.sh" <<EOS
#!/bin/bash
# Compile the tests under tests/ against the project's public API, using the
# same -source level as the project itself.
# There is no run script: executing the tests is not part of this task.
set -e
cd "\$(dirname "\$0")"
mkdir -p out
find tests -name '*.java' > .sources
javac -nowarn -source $SRC_LEVEL -target $SRC_LEVEL -cp "lib/*" -d out @.sources
echo "compiled OK"
EOS
    chmod +x "$SPEC/compile.sh"

    # ---- prompt -------------------------------------------------------------
    CLASS_LIST=$(printf '  - %s\n' $CLASSES)
    JUNIT_HINT=$(ls "$SPEC/lib" | grep -i junit | head -1)

    PROMPT="Write JUnit test classes for these classes:

$CLASS_LIST

You do NOT have the implementation source. You have:
  api/          generated javadoc for the classes above — this is your spec
  lib/          the compiled project and JUnit ($JUNIT_HINT)
  compile.sh    compiles everything under tests/ against lib/

Requirements:
- One test class per class above, named <ClassName>AgentTest, in the same
  package, under tests/ following the package directory structure.
- The test class must be SELF-CONTAINED: do not extend or import any other
  test class or test helper. Any fixture you need, define inside your file.
- Match the JUnit version present in lib/. Some of these projects ship
  JUnit 3.8 only, where org.junit.Test and org.junit.Assert do not exist.
- This project compiles with -source $SRC_LEVEL. Use only syntax valid at that
  level: no underscores in numeric literals, no diamond operator, no lambdas,
  no try-with-resources unless the level allows them.
- Assert on returned values and on observable state, not merely that no
  exception is thrown.
- Cover boundary and error cases, not just the happy path.
- Base every expectation on the documented contract in api/. Where the javadoc
  is silent, prefer asserting what the contract implies over guessing at an
  implementation detail.

Restrictions:
- Do NOT run the tests. Compile them with ./compile.sh, nothing else.
- Do NOT decompile, disassemble or inspect the bytecode in lib/ (no javap -c,
  no decompilers). Read api/ for the API.
- Do not inspect version control history. Do not run git.
- Do not search the web.

Finish when ./compile.sh reports success."

    echo "[$TAG] invoking agent ($MODEL, spec arm, -source $SRC_LEVEL)"
    (cd "$SPEC" && claude -p "$PROMPT" \
        --model "$MODEL" \
        --allowedTools "Read,Write,Bash" \
        --permission-mode acceptEdits \
        --max-turns "$MAX_TURNS" \
        --output-format json) > "$RUNDIR/${TAG}.json" 2>"$RUNDIR/${TAG}.stderr"

    VERDICT=$(python3 -c "
import json
try:
    d = json.load(open('$RUNDIR/${TAG}.json'))
except Exception:
    print('dead|unparseable|0|0'); raise SystemExit
cost = d.get('total_cost_usd') or 0
turns = d.get('num_turns') or 0
err = bool(d.get('is_error'))
res = (d.get('result') or '').replace('|', ' ')[:120]
limit = 'session limit' in res or 'rate limit' in res or d.get('api_error_status') == 429
state = 'ok' if not err else ('dead' if (cost == 0 or limit) else 'error')
print(f'{state}|{res}|{cost:.3f}|{turns}')" 2>/dev/null)

    STATE="${VERDICT%%|*}"; REST="${VERDICT#*|}"
    MSG="${REST%%|*}";      NUMS="${REST#*|}"
    echo "[$TAG] agent done: \$${NUMS%|*} turns=${NUMS#*|} state=$STATE"

    if [ "$STATE" = "dead" ]; then
        DEAD=$((DEAD + 1))
        echo "[$TAG] no usable API call: $MSG"
        if [ "$DEAD" -ge "$MAX_DEAD" ]; then
            echo; echo "ABORTING: $DEAD consecutive runs hit a usage limit."
            echo "Remaining bugs untouched; rerun this script later to resume."
            ABORTED=yes; break
        fi
        continue
    fi
    DEAD=0
    [ "$STATE" = "error" ] && { fail "agent run returned an error"; continue; }

    WRITTEN=$(cd "$SPEC/tests" && find . -name "*AgentTest.java" 2>/dev/null)
    [ -z "$WRITTEN" ] && { fail "agent produced no test file"; continue; }

    # ---- move into the real checkout and prune failing methods -------------
    for f in $WRITTEN; do
        mkdir -p "$W/$SRC_TESTS/$(dirname "$f")"
        cp "$SPEC/tests/$f" "$W/$SRC_TESTS/$f"
    done

    if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.compile" 2>&1; then
        fail "agent tests do not compile in the project"; continue
    fi

    # counted BEFORE any pruning, so the denominator is the suite as written
    TEST_PATHS=""
    for f in $WRITTEN; do TEST_PATHS="$TEST_PATHS $W/$SRC_TESTS/$f"; done
    METHODS_TOTAL=$(count_tests $TEST_PATHS)

    RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
    JUNIT3=no
    PRUNED_TOTAL=0

    for round in $(seq 1 $MAX_PRUNE_ROUNDS); do
        : > "$RUNDIR/${TAG}.junit"
        if [ "$JUNIT3" = "no" ] \
           && (cd "$W" && java -cp "$CP" org.junit.runner.JUnitCore $RUN_CLASSES) \
                > "$RUNDIR/${TAG}.junit" 2>&1; then
            break
        fi
        if grep -q "Could not find or load main class org.junit.runner.JUnitCore" \
                "$RUNDIR/${TAG}.junit"; then
            JUNIT3=yes
            : > "$RUNDIR/${TAG}.junit"
            ALLOK=yes
            for RC in $RUN_CLASSES; do
                (cd "$W" && java -cp "$CP" junit.textui.TestRunner "$RC") \
                    >> "$RUNDIR/${TAG}.junit" 2>&1 || ALLOK=no
            done
            [ "$ALLOK" = "yes" ] && break
        fi

        # "1) someTest(pkg.FooAgentTest)" in both runners. The `test` prefix is
        # optional under JUnit 4, so do not assume it.
        FAILING=$(grep -oP '^\d+\)\s*\K\w+(?=\()' "$RUNDIR/${TAG}.junit" | sort -u)
        if [ -z "$FAILING" ]; then
            fail "tests fail but no method names could be parsed (round $round)"
            break
        fi

        NPRUNED=0
        for f in $WRITTEN; do
            OUT=$("$ROOT/bin/prune-failing-tests.py" "$W/$SRC_TESTS/$f" $FAILING)
            NPRUNED=$((NPRUNED + ${OUT%% *}))
            # delete the compiled classes: ant's one-second timestamp
            # granularity otherwise skips the recompile and the next run
            # executes the pre-prune bytecode
            if [ -n "$BIN_TESTS" ]; then
                REL="${f#./}"; REL="${REL%.java}"
                rm -f "$W/$BIN_TESTS/$REL.class" "$W/$BIN_TESTS/$REL"\$*.class
            fi
        done
        PRUNED_TOTAL=$((PRUNED_TOTAL + NPRUNED))
        echo "[$TAG] round $round: disabled $NPRUNED failing methods"

        if [ "$NPRUNED" -eq 0 ]; then
            fail "failing methods could not be disabled (round $round)"; break
        fi
        if ! (cd "$W" && defects4j compile) >> "$RUNDIR/${TAG}.compile" 2>&1; then
            fail "compile broke after pruning"; break
        fi
    done
    [ -f "$STATUS" ] && continue

    echo "$PRUNED_TOTAL $METHODS_TOTAL" > "$RUNDIR/${TAG}.pruned"
    echo "[$TAG] pruned $PRUNED_TOTAL of $METHODS_TOTAL tests"

    if [ "$METHODS_TOTAL" -gt 0 ] && [ "$PRUNED_TOTAL" -ge "$METHODS_TOTAL" ]; then
        fail "every test failed on the fixed version"; continue
    fi

    STAGE=$(mktemp -d)
    for f in $WRITTEN; do
        mkdir -p "$STAGE/$(dirname "$f")"
        cp "$W/$SRC_TESTS/$f" "$STAGE/$f"
    done
    (cd "$STAGE" && tar cjf "$ARCHIVE" .) || { fail "packaging failed"; rm -rf "$STAGE"; continue; }
    rm -rf "$STAGE"

    echo "ok" > "$STATUS"
    rm -rf "$W"          # $SPEC is kept: it is the audit trail for this arm
    echo "[$TAG] packaged: $SUITES/$(basename "$ARCHIVE")"
done < "$SAMPLE"

echo
[ "$ABORTED" = "yes" ] && echo "*** run aborted early — resume by rerunning ***" && echo
echo "spec suites packaged: $(ls "$ROOT/$SUITES"/*-${ARM}.1.tar.bz2 2>/dev/null | wc -l)"
echo "failures:             $(grep -Lx 'ok' "$ROOT/$RUNS"/*.status 2>/dev/null | wc -l)"
echo "pruned tests:         $(cd "$ROOT" && awk '{p+=$1; t+=$2} END{if(t)printf "%d of %d (%.0f%%)", p, t, 100*p/t}' "$RUNS"/*.pruned 2>/dev/null)"
echo "total cost:           \$$(cd "$ROOT" && python3 - <<EOF
import json, glob
t = 0.0
for f in glob.glob('$RUNS/*.json'):
    try:
        t += json.load(open(f)).get('total_cost_usd', 0) or 0
    except Exception:
        pass
print(f"{t:.2f}")
EOF
)"

FAILED=$(grep -Lx 'ok' "$ROOT/$RUNS"/*.status 2>/dev/null)
if [ -n "$FAILED" ]; then
    echo; echo "failed bugs:"
    echo "$FAILED" | while read -r s; do echo "  $(basename "$s" .status): $(cat "$s")"; done
fi
echo
echo "Next: ./bin/analyze-agent-suites.sh"

#!/bin/bash
#
# Study B, phase 1: generate one agent-written test suite per bug.
#
# For each bug in the sample, on the FIXED version:
#   - export the metadata needed (BEFORE removing .git)
#   - delete .git                      contamination control, see below
#   - delete the developer test files that contain the trigger tests
#   - if that breaks the build, replace them with empty stubs (see below)
#   - invoke the coding agent
#   - verify the suite compiles and passes on the fixed version
#   - package it as <Project>-<bid>f-agent.1.tar.bz2 into a FLAT directory
#
# Analysis is phase 2 (analyze-agent-suites.sh), deliberately separate: this
# phase costs real money (~$1-2/bug) and must never be repeated to fix a
# parsing bug downstream.
#
# CONTAMINATION CONTROL
# ---------------------
# A defects4j checkout ships the project's full git history, including the fix
# commit itself. For Lang-13 the log subject line reads
#   [LANG-788] SerializationUtils throws ClassNotFoundException when cloning
#   primitive classes
# and tags D4J_Lang_13_BUGGY_VERSION / _FIXED_VERSION make `git diff` yield the
# patch. The first pilot run produced a test citing "LANG-788" in a comment.
#
# `.git` is therefore removed before the agent starts, and the prompt forbids
# git and web search. Metadata exports run first, since they may need git.
#
# Measured effect on the pilot: none on mutation score or fault detection
# (identical), +6 covered lines. The history is a real leak but a weak one when
# the agent can already read the fixed implementation. It matters more for a
# future spec-only arm, where the code is withheld.
#
# STUB FALLBACK
# -------------
# Deleting the whole developer test file breaks compilation in the JUnit 3-era
# projects, where aggregator classes reference each test class by name:
#   TextTestSuite.java:53: cannot find symbol
#       suite.addTest(ExtendedMessageFormatTest.suite());
#
# Measured across the sample: 6 of 40 bugs break this way, all of them Lang
# 2.x (43, 52, 56, 62, 63, 65). Excluding them is not an option — they are half
# the Lang subsample and the older, JUnit 3 half, which is plausibly where an
# agent performs worst. Dropping them would bias the result toward modern code.
#
# So the file is replaced by a stub carrying the same class name, a `suite()`
# and one trivial passing test. The aggregator compiles, and the agent sees no
# developer test for the class under test. The stub is never packaged: only
# *AgentTest.java goes into the archive.
#
# CIRCUIT BREAKER
# ---------------
# The first full run burned through 35 bugs in minutes after hitting a usage
# limit: every call returned `is_error` with $0.00 and 1 turn, and the loop
# marked each bug as failed. Those .status files then have to be cleaned up by
# hand before a retry.
#
# Two consecutive zero-cost errors now abort the whole run, leaving the
# remaining bugs untouched so a later resume picks them up cleanly.
#
# Usage:
#   ./bin/run-agent-suites.sh                    # whole sample
#   ./bin/run-agent-suites.sh data/sample.txt 3  # first 3 bugs

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)

SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
SUITES=data/agent-suites          # flat: every archive lives here
RUNS=data/agent-runs              # one JSON + log per bug
ARM=${ARM:-agent}                 # generator label inside the archive name
MODEL=${MODEL:-opus}
MAX_TURNS=${MAX_TURNS:-25}
MAX_DEAD=${MAX_DEAD:-2}           # consecutive zero-cost errors before aborting

command -v defects4j >/dev/null || { echo "defects4j not on PATH"; exit 1; }
command -v claude    >/dev/null || { echo "claude not on PATH"; exit 1; }
[ -f "$SAMPLE" ] || { echo "sample file not found: $SAMPLE"; exit 1; }
[ "${TZ:-}" = "America/Los_Angeles" ] || echo "WARNING: TZ is not America/Los_Angeles"

mkdir -p "$ROOT/$SUITES" "$ROOT/$RUNS"

# write_stub <file> <fqcn> <junit3?>
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

    public $cls(String name) {
        super(name);
    }

    public static Test suite() {
        return new TestSuite($cls.class);
    }

    public void testStub() {
        assertTrue(true);
    }
}
EOF
    else
        cat > "$path" <<EOF
package $pkg;

import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Stub: developer tests removed for the agent test-generation experiment. */
public class $cls {

    @Test
    public void testStub() {
        assertTrue(true);
    }
}
EOF
    fi
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

    W=/tmp/agentB_${P}_${B}_f
    fail() { echo "[$TAG] $1"; echo "$1" > "$STATUS"; }

    echo "[$TAG] checkout"
    rm -rf "$W"
    if ! defects4j checkout -p "$P" -v "${B}f" -w "$W" >/dev/null 2>&1; then
        fail "checkout failed"; continue
    fi

    # --- metadata FIRST: exports may need git, which is about to go ---------
    SRC_TESTS=$(cd "$W" && defects4j export -p dir.src.tests 2>/dev/null \
                  | grep -v '^Running' | tail -1)
    CLASSES=$(cd "$W" && defects4j export -p classes.modified 2>/dev/null \
                  | grep -v '^Running' | grep -v '^$')
    TRIGGERS=$(cd "$W" && defects4j export -p tests.trigger 2>/dev/null | grep '::')

    if [ -z "$SRC_TESTS" ] || [ -z "$CLASSES" ]; then
        fail "could not export metadata"; continue
    fi
    printf '%s\n' "$CLASSES"  > "$RUNDIR/${TAG}.classes"
    printf '%s\n' "$TRIGGERS" > "$RUNDIR/${TAG}.triggers"

    # --- contamination control ---------------------------------------------
    rm -rf "$W/.git"

    # Delete whole developer test FILES holding trigger tests, not just the
    # failing methods: the rest of the class would show what is tested and how.
    # Record class name and JUnit style first, in case a stub is needed.
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

    STUBBED=no
    if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.precompile" 2>&1; then
        echo "[$TAG] compile broke after deletion, writing stubs"
        for D in $DELETED; do
            write_stub "$W/$SRC_TESTS/$(echo "${D%%:*}" | tr '.' '/').java" \
                       "${D%%:*}" "${D##*:}"
        done
        STUBBED=yes
        if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.precompile2" 2>&1; then
            fail "compile fails even with stubs"; continue
        fi
    fi
    echo "$STUBBED" > "$RUNDIR/${TAG}.stubbed"

    # --- build the prompt ---------------------------------------------------
    CLASS_LIST=$(printf '  - %s\n' $CLASSES)
    EXPECTED=$(for c in $CLASSES; do echo "${c}AgentTest"; done | tr '\n' ' ')

    PROMPT="Write JUnit test classes for the following classes:

$CLASS_LIST

Requirements:
- One test class per class above, named <ClassName>AgentTest, in the same
  package, under $SRC_TESTS/
- Match the JUnit version and assertion style used by the other test classes
  already in this project. Check them before writing.
- Test only the public API.
- Assert on returned values and on observable state, not merely that no
  exception is thrown.
- Cover boundary and error cases, not just the happy path.
- Do not modify or create any file other than the test classes named above.

Restrictions:
- Do not inspect version control history. Do not run git.
- Read only files under the project source tree and the build configuration
  you need to compile.
- Do not search the web.

Verify with:
  defects4j compile
  java -cp \"\$(defects4j export -p cp.test)\" org.junit.runner.JUnitCore $EXPECTED"

    echo "[$TAG] invoking agent ($MODEL)"
    (cd "$W" && claude -p "$PROMPT" \
        --model "$MODEL" \
        --allowedTools "Read,Write,Bash" \
        --permission-mode acceptEdits \
        --max-turns "$MAX_TURNS" \
        --output-format json) > "$RUNDIR/${TAG}.json" 2>"$RUNDIR/${TAG}.stderr"

    # verdict: ok | error | dead   (dead = errored with no API call billed)
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

    STATE="${VERDICT%%|*}"
    REST="${VERDICT#*|}"
    MSG="${REST%%|*}"
    NUMS="${REST#*|}"
    echo "[$TAG] agent done: \$${NUMS%|*} turns=${NUMS#*|} state=$STATE"

    if [ "$STATE" = "dead" ]; then
        DEAD=$((DEAD + 1))
        echo "[$TAG] no API call was billed: $MSG"
        if [ "$DEAD" -ge "$MAX_DEAD" ]; then
            echo
            echo "ABORTING: $DEAD consecutive runs failed without being billed."
            echo "Most likely a usage or rate limit. Remaining bugs untouched;"
            echo "rerun this script later to resume."
            ABORTED=yes
            break
        fi
        continue                     # no .status: this bug stays retryable
    fi
    DEAD=0

    if [ "$STATE" = "error" ]; then
        fail "agent run returned an error — see ${TAG}.json"; continue
    fi

    # --- assured filter: exists, compiles, passes ---------------------------
    WRITTEN=$(cd "$W/$SRC_TESTS" && find . -name "*AgentTest.java" 2>/dev/null)
    if [ -z "$WRITTEN" ]; then
        fail "agent produced no test file"; continue
    fi

    if ! (cd "$W" && defects4j compile) > "$RUNDIR/${TAG}.compile" 2>&1; then
        fail "agent tests do not compile"; continue
    fi

    CP=$(cd "$W" && defects4j export -p cp.test 2>/dev/null | grep -v '^Running' | tail -1)
    RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
    if ! (cd "$W" && java -cp "$CP" org.junit.runner.JUnitCore $RUN_CLASSES) \
            > "$RUNDIR/${TAG}.junit" 2>&1; then
        fail "agent tests fail on the fixed version"; continue
    fi

    # --- package (flat dir, evosuite-compatible layout) ---------------------
    # only *AgentTest.java: any stub stays behind in the working copy
    STAGE=$(mktemp -d)
    for f in $WRITTEN; do
        mkdir -p "$STAGE/$(dirname "$f")"
        cp "$W/$SRC_TESTS/$f" "$STAGE/$f"
    done
    if ! (cd "$STAGE" && tar cjf "$ARCHIVE" .); then
        fail "packaging failed"; rm -rf "$STAGE"; continue
    fi
    rm -rf "$STAGE"

    echo "ok" > "$STATUS"
    rm -rf "$W"
    echo "[$TAG] packaged: $SUITES/$(basename "$ARCHIVE")"
done < "$SAMPLE"

TOTAL=$(grep -c '[^[:space:]]' "$SAMPLE" 2>/dev/null || echo "?")
echo
[ "$ABORTED" = "yes" ] && echo "*** run aborted early — resume by rerunning ***" && echo
echo "sample size:     $TOTAL"
echo "suites packaged: $(ls "$ROOT/$SUITES"/*.tar.bz2 2>/dev/null | wc -l)"
echo "stubbed bugs:    $(grep -lx 'yes' "$ROOT/$RUNS"/*.stubbed 2>/dev/null | wc -l)"
echo "failures:        $(grep -Lx 'ok' "$ROOT/$RUNS"/*.status 2>/dev/null | wc -l)"
echo "total cost:      \$$(cd "$ROOT" && python3 - <<'EOF'
import json, glob
t = 0.0
for f in glob.glob('data/agent-runs/*.json'):
    try:
        t += json.load(open(f)).get('total_cost_usd', 0) or 0
    except Exception:
        pass
print(f"{t:.2f}")
EOF
)"

FAILED=$(grep -Lx 'ok' "$ROOT/$RUNS"/*.status 2>/dev/null)
if [ -n "$FAILED" ]; then
    echo
    echo "failed bugs:"
    echo "$FAILED" | while read -r s; do
        echo "  $(basename "$s" .status): $(cat "$s")"
    done
fi
echo
echo "Next: ./bin/analyze-agent-suites.sh"

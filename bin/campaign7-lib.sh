#!/bin/bash
#
# Seventh campaign: what the generator and the measurement share. Sourced, not
# run.
#
# A subject is one of the sample's Defects4J bugs, <project>-<id>, and each of
# its two versions, the buggy one (b) and the fixed one (f), is staged the way
# the second campaign's generator (bin/generate-suites.sh) staged the fixed
# one for m2:
#   - Defects4J checks the version out and the repository's history goes;
#   - the developer test files that hold the trigger tests are removed, and if
#     the build then fails, a stub takes each one's place;
#   - Defects4J compiles the production classes and the developers' tests that
#     stay.
# The buggy version is Defects4J's: the fixed version with the bug's source
# patch applied, which takes the repair back out (framework/core/Project.pm,
# checkout_vid). The two versions have the same tests, so the same files are
# removed from both.
#
# The helpers of bin/campaign3-lib.sh that do not build with Maven are used as
# they are: c3_env, excluded_from and count_methods, and RUN_TIMEOUT.

ROOT_LIB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
. "$ROOT_LIB/bin/campaign3-lib.sh"

D4J_HOME=${D4J_HOME:-$HOME/defects4j}
case ":$PATH:" in *":$D4J_HOME/framework/bin:"*) ;; *) PATH="$D4J_HOME/framework/bin:$PATH" ;; esac
export TZ=America/Los_Angeles

# c7_check_env [cli]
#
# Refuses, with the reason, an environment other than the one the protocol
# fixes: Java 11, java and javac as the runs find them; Defects4J
# v3.0.1-7-g8c16da82; and, with `cli`, Claude Code 2.1.316 at $CLAUDE_BIN. In
# the fifth campaign an update of the system's Java to 21, during the runs,
# made 111 runs fail at staging. A script stops before its first bug instead.
C7_JAVA=11
C7_D4J=v3.0.1-7-g8c16da82
C7_CLI="2.1.316 (Claude Code)"
c7_check_env() {
    local j jc d c
    j=$(c3_env java -version 2>&1 | head -1 | sed -nE 's/.*version "([0-9]+)[."].*/\1/p')
    jc=$(c3_env javac -version 2>&1 | head -1 | sed -nE 's/^javac ([0-9]+)[.].*/\1/p')
    if [ "$j" != "$C7_JAVA" ] || [ "$jc" != "$C7_JAVA" ]; then
        echo "java ${j:-?} and javac ${jc:-?}: the protocol fixes Java $C7_JAVA"; return 1
    fi
    d=$(git -C "$D4J_HOME" describe --tags 2>/dev/null)
    if [ "$d" != "$C7_D4J" ]; then
        echo "Defects4J ${d:-unknown}: the protocol fixes $C7_D4J"; return 1
    fi
    if [ "${1:-}" = cli ]; then
        c=$("${CLAUDE_BIN:-claude}" --version 2>/dev/null | head -1)
        if [ "$c" != "$C7_CLI" ]; then
            echo "Claude Code ${c:-unknown}: the protocol fixes $C7_CLI"; return 1
        fi
    fi
    return 0
}

# write_stub <file> <fqcn> <junit3?>      the second campaign's stub, unchanged
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

/** Stub: the tests of this class are not part of this working copy. */
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

/** Stub: the tests of this class are not part of this working copy. */
public class $cls {
    @Test public void testStub() { assertTrue(true); }
}
EOF
    fi
}

# d4j_export <checkout> <property>          one property, as the second campaign read it
d4j_export() { (cd "$1" && defects4j export -p "$2" 2>/dev/null) | grep -v '^Running' | tail -1; }

# stage_bug <project> <id> <b|f> <dest> <log>
#
# Stages one version into <dest>, which must not exist. Leaves in <dest>/.c7/:
#   src-tests src-classes bin-classes bin-tests   Defects4J's directories
#   classes       the classes under test (classes.modified), one per line
#   triggers      the trigger tests, class::method, one per line
#   issue         the report Defects4J gives for the bug
#   srclevel      the project's -source level, as the second campaign read it
#   stubbed       yes if stubs had to replace removed files
#   removed       the classes whose files were removed, class:junit3?
#   trigger-src/  the removed files as they were, for a dry run's stand-ins
#   cp-test       the class path the tests run on: Defects4J's cp.test and
#                 every jar Defects4J keeps for the project, as in the second
#                 campaign (cli2 declares jars in cp.test that were never
#                 materialised)
#   cp-compile    Defects4J's cp.compile
#   junit         4 if JUnit 4's JUnitCore is on cp-test, 3 otherwise
# As in the second campaign, what Defects4J prints at checkout is not kept,
# its compilation goes to <log>, and its compilation with stubs to <log>2.
# Returns non-zero, with the reason in STAGE_FAIL, if a step fails.
STAGE_FAIL=""
stage_bug() {
    local P=$1 B=$2 V=$3 dest=$4 log=$5 T F CLS J3
    STAGE_FAIL=""
    rm -f "$log" "${log}2"
    if ! defects4j checkout -p "$P" -v "${B}${V}" -w "$dest" > /dev/null 2>&1; then
        STAGE_FAIL="checkout failed"; return 1
    fi
    mkdir -p "$dest/.c7/trigger-src"
    local c7="$dest/.c7"
    d4j_export "$dest" dir.src.tests   > "$c7/src-tests"
    d4j_export "$dest" dir.src.classes > "$c7/src-classes"
    d4j_export "$dest" dir.bin.classes > "$c7/bin-classes"
    d4j_export "$dest" dir.bin.tests   > "$c7/bin-tests"
    d4j_export "$dest" cp.compile      > "$c7/cp-compile"
    (cd "$dest" && defects4j export -p classes.modified 2>/dev/null) | grep -v '^Running' | grep -v '^$' > "$c7/classes"
    (cd "$dest" && defects4j export -p tests.trigger 2>/dev/null) | grep '::' > "$c7/triggers"
    awk -F, -v b="$B" '$1 == b { print $4 }' "$D4J_HOME/framework/projects/$P/active-bugs.csv" > "$c7/issue"
    local SRC_TESTS SRC_LEVEL
    SRC_TESTS=$(cat "$c7/src-tests")
    if [ -z "$SRC_TESTS" ] || [ -z "$(cat "$c7/src-classes")" ] || [ ! -s "$c7/classes" ]; then
        STAGE_FAIL="could not export metadata"; return 1
    fi
    # the project's own -source level; the agent's compiler must not be more
    # permissive than the build that will judge the suite
    SRC_LEVEL=$(grep -h "^compile\.source" "$dest"/*.properties 2>/dev/null \
                  | head -1 | cut -d= -f2 | tr -d '[:space:]')
    echo "${SRC_LEVEL:-8}" > "$c7/srclevel"

    # ---- no history, no trigger tests ----
    rm -rf "$dest/.git"
    : > "$c7/removed"
    while read -r T; do
        [ -z "$T" ] && continue
        # a nested class's tests are in its outer class's file, and a class's
        # own name may hold a $ (Gson's $Gson$Types): the file is the class's
        # own if there is one, else that of the class it is nested in. No
        # trigger test of the sample's 40 bugs is in a nested class or in a
        # class with a $ in its name
        CLS="${T%%::*}"
        while [ ! -f "$dest/$SRC_TESTS/$(echo "$CLS" | tr '.' '/').java" ] && [ "${CLS%\$*}" != "$CLS" ]; do
            CLS="${CLS%\$*}"
        done
        F="$dest/$SRC_TESTS/$(echo "$CLS" | tr '.' '/').java"
        [ -f "$F" ] || continue
        if grep -q "extends TestCase\|junit.framework" "$F"; then J3=yes; else J3=no; fi
        grep -qx "$CLS:$J3" "$c7/removed" && continue
        echo "$CLS:$J3" >> "$c7/removed"
        mkdir -p "$c7/trigger-src/$(dirname "$(echo "$CLS" | tr '.' '/')")"
        cp "$F" "$c7/trigger-src/$(echo "$CLS" | tr '.' '/').java"
        rm -f "$F"
    done < "$c7/triggers"

    echo no > "$c7/stubbed"
    if ! (cd "$dest" && defects4j compile) > "$log" 2>&1; then
        while IFS=: read -r CLS J3; do
            write_stub "$dest/$SRC_TESTS/$(echo "$CLS" | tr '.' '/').java" "$CLS" "$J3"
        done < "$c7/removed"
        echo yes > "$c7/stubbed"
        if ! (cd "$dest" && defects4j compile) > "${log}2" 2>&1; then
            STAGE_FAIL="compile fails even with stubs"; return 1
        fi
    fi

    local CP EXTRA
    CP=$(d4j_export "$dest" cp.test)
    EXTRA=$(find "$D4J_HOME/framework/projects/$P/lib" -name '*.jar' 2>/dev/null | tr '\n' ':')
    echo "$CP:$EXTRA" > "$c7/cp-test"
    if javap -cp "$CP:$EXTRA" org.junit.runner.JUnitCore > /dev/null 2>&1; then
        echo 4 > "$c7/junit"
    else
        echo 3 > "$c7/junit"
    fi
    return 0
}

# build_runner4 <staged dir> <dest dir>     compiles bin/AgentTestRunner4.java
build_runner4() {
    mkdir -p "$2"
    javac -nowarn --release 8 -Xlint:-options -encoding UTF-8 \
        -cp "$(cat "$1/.c7/cp-test")" -d "$2" "$ROOT_LIB/bin/AgentTestRunner4.java"
}

# javac_level <staged dir>                  the compiler's options, as _tools/test.sh gives them
javac_level() { local l; l=$(cat "$1/.c7/srclevel"); echo "-source $l -target $l"; }

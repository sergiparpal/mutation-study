#!/bin/bash
#
# Second campaign: generate one test suite per bug and per arm, with the agent
# isolated from the benchmark, from the network and from the operator's
# profile, and with a transcript of every run.
#
#   ARM=m2   implementation-visible: the agent works in the project's tree
#   ARM=s2   specification-only: the agent has javadoc and a compiled jar
#
# WHY A SECOND SCRIPT
# -------------------
# run-agent-suites.sh and run-spec-suites.sh are left as they ran: they are the
# record of how the first campaign's suites were produced. That campaign's M
# arm was told more than the implementation (data/README.md, "What those
# controls do not close"), nothing its prompts forbade was enforced, no
# transcript was kept, and the model was named by an alias. This script is the
# rerun its header asked for. It changes the protocol, so its suites are a
# second campaign and are never pooled with the first.
#
# WHAT THE AGENT GETS
# -------------------
# m2: a copy of the Defects4J checkout of the FIXED revision, from which these
#     have been removed before the agent starts:
#       - .git
#       - the developer test files that hold the trigger tests (a stub replaces
#         one where the build needs the class name; same rule as before)
#       - defects4j.build.properties and .defects4j.config
#       - every *.bak: Defects4J's backups, among them complete copies of some
#         trigger test classes
#       - changelogs, release notes and upgrade guides
#       - the word "Defects4J" in the comments it leaves on tests it disabled,
#         and the paths into its installation in the build files it rewrites
#     and to which _tools/ has been added: the jars the tests need, and
#     test.sh, which compiles the agent's test classes and runs them. The
#     defects4j command is not available. File times are flattened.
# s2: api/ (javadoc of the classes under test, generated with -package),
#     lib/ (the compiled classes as a jar, and JUnit), tests/ and compile.sh.
#     No source and no way to run a test.
#
# Both working copies live in a directory with a random name. The checkout
# with Defects4J's metadata, where the suite is verified afterwards, is in a
# place the agent cannot read.
#
# WHAT IS ENFORCED, NOT ASKED
# ---------------------------
# - Bash runs in Claude Code's sandbox: no network, its own process namespace,
#   and of /home, /tmp, /mnt, /opt and the like it can read only its working
#   copy. Defects4J, this repository, other working copies, earlier transcripts
#   and the processes of this script are out of reach. /tmp is, to each
#   command, an empty directory of its own: what a command writes there is gone
#   when it ends.
# - The file tools are confined to the working copy (--restricted).
# - No web tools, no subagents, no skills, no MCP servers, no plugins; user,
#   project and local settings are ignored; persistent memory is off.
# - s2 only: of the JDK's launchers only javac can be read, so nothing in
#   lib/ can be run, disassembled or unpacked with the JDK's own tools; unzip,
#   python and perl are hidden too. Other general-purpose tools remain, which
#   is why the transcript is kept and audited (bin/audit-transcripts.py).
#
# WHAT IS RECORDED, PER RUN (data/campaign2/runs-<arm>/<bug>.*)
# -------------------------------------------------------------
#   .stream.jsonl.xz  every message of the run: text, tool calls and results
#                     (the CLI also interleaves events about the account's
#                     usage limits; those are not messages and are dropped)
#   .json             the closing result message (cost, turns, final text)
#   .prompt           the prompt as sent
#   .settings.json    the sandbox and permission settings as sent
#   .meta.json        model id, CLI version, flags, working-copy id, timings
#   .leakscan         what a search of the working copy for the trigger tests'
#                     names, the issue id and the benchmark's name still finds
#   .stripped         the files removed as changelogs
#   .touched          every file the agent created or changed
#   .classes .triggers .srclevel .stubbed .precompile .compile .junit .pruned
#                     as in the first campaign
#
# ACCEPTANCE
# ----------
# The same for both arms: the suite is copied into the real checkout, compiled
# there, and each test that fails on the fixed revision is disabled
# (bin/prune-failing-tests.py). In the first campaign an M-arm suite had to
# pass whole.
#
# The model is named by its full id. An alias moves. For the same reason the
# CLI is run from its versioned binary and told not to update itself, and each
# run records the commit of this repository it was made from.
#
# USAGE LIMITS
# ------------
# On a subscription the runs draw on the plan's usage limits. Each run reports
# how much of the limit is used; when that reaches USAGE_STOP (default 0.95)
# the script stops before starting another run, and picks up where it left off
# when run again. A run that a limit cuts short all the same leaves no .status
# and is made again; its record moves to cut-short/ and its tests are not used.
#
# The campaign's protocol is data/campaign2/PROTOCOL.md, and run-campaign2.sh
# calls this script in the order it fixes.
#
# Usage:
#   ARM=m2 ./bin/generate-suites.sh                     # whole sample
#   ARM=s2 ./bin/generate-suites.sh data/sample.txt 3   # first 3 bugs
#   ARM=m2 ONLY="Lang-63 Csv-4" ./bin/generate-suites.sh
#   ARM=m2 DRY=agent OUT=/tmp/dry ./bin/generate-suites.sh
#       no model call: the first campaign's suite stands in for the agent's,
#       to exercise the harness (DRY=agent for m2, DRY=spec for s2)
#   KEEP=1 keeps the working copy of a successful run, for inspection

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)

ARM=${ARM:-}
case "$ARM" in
    m2|s2) ;;
    *) echo "set ARM=m2 (implementation-visible) or ARM=s2 (specification-only)"; exit 1 ;;
esac

SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
ONLY=${ONLY:-}
MODEL=${MODEL:-claude-sonnet-5}
MAX_TURNS=${MAX_TURNS:-50}
MAX_BUDGET=${MAX_BUDGET:-5}
MAX_DEAD=${MAX_DEAD:-2}
MAX_PRUNE_ROUNDS=5
OUT=${OUT:-data/campaign2}
DRY=${DRY:-}
D4J_HOME=${D4J_HOME:-$HOME/defects4j}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}    # under /home: the agent cannot read it
USAGE_STOP=${USAGE_STOP:-0.95}      # share of the plan's usage limit at which to stop
USAGE_FILE=$STAGE_ROOT/usage        # last reported usage; never in the repository
TOOLS="Bash,Read,Write,Edit,Glob,Grep"
AGENT_PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
SUITES=$OUT_ABS/suites
RUNDIR=$OUT_ABS/runs-$ARM

command -v defects4j >/dev/null || { echo "defects4j not on PATH"; exit 1; }
command -v javac     >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
command -v javadoc   >/dev/null || { echo "javadoc not on PATH (install a JDK)"; exit 1; }
[ -n "$DRY" ] || command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
[ -f "$SAMPLE" ] || { echo "sample file not found: $SAMPLE"; exit 1; }
[ "${TZ:-}" = "America/Los_Angeles" ] || { echo "set TZ=America/Los_Angeles"; exit 1; }
case "$MODEL" in
    claude-*-[0-9]*) ;;
    *) echo "MODEL must be a full model id, not an alias: $MODEL"; exit 1 ;;
esac

JDK_BIN=$(dirname "$(readlink -f "$(command -v javac)")")

# The binary itself, not the `claude` link: an update moves the link.
CLAUDE_BIN=${CLAUDE_BIN:-$( [ -n "$DRY" ] || readlink -f "$(command -v claude)")}
CLI_VERSION=$( [ -n "$DRY" ] && echo "dry run" || "$CLAUDE_BIN" --version 2>/dev/null | head -1)

# A run is tied to the commit of the scripts that made it. Outside a dry run,
# refuse to start if they differ from that commit.
COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
if [ -z "$DRY" ] && [ -z "${ALLOW_DIRTY:-}" ] \
   && [ -n "$(git -C "$ROOT" status --porcelain -- bin data/sample.txt 2>/dev/null)" ]; then
    echo "bin/ or data/sample.txt differs from the last commit: commit first, or set ALLOW_DIRTY=1"
    exit 1
fi

mkdir -p "$SUITES" "$RUNDIR" "$STAGE_ROOT"

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

count_tests() { "$ROOT/bin/prune-failing-tests.py" --count "$@"; }

n=0
DEAD=0
ABORTED=no

while IFS=, read -r P B _rest; do
    P=$(echo "${P:-}" | tr -d '[:space:]')
    B=$(echo "${B:-}" | tr -d '[:space:]')
    [ -z "$P" ] && continue
    case "$P" in \#*) continue ;; esac

    TAG="${P}-${B}"
    if [ -n "$ONLY" ]; then
        case " $ONLY " in *" $TAG "*) ;; *) continue ;; esac
    fi

    n=$((n + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$n" -gt "$LIMIT" ]; then break; fi

    ARCHIVE="$SUITES/${P}-${B}f-${ARM}.1.tar.bz2"
    STATUS="$RUNDIR/${TAG}.status"
    R="$RUNDIR/${TAG}"

    if [ -f "$STATUS" ]; then
        echo "[$TAG] already attempted ($(cat "$STATUS")) — skipping"
        continue
    fi

    # Do not start a run the plan's usage limit would cut short: a run that
    # dies half-way has to be made again, and a second attempt is what the
    # protocol wants least. The last run reported how much of the limit is
    # used and when it resets.
    if [ -z "$DRY" ] && [ -f "$USAGE_FILE" ] && python3 - "$USAGE_FILE" "$USAGE_STOP" <<'EOF'
import sys, time
used, resets = (float(x) for x in open(sys.argv[1]).read().split()[:2])
sys.exit(0 if used >= float(sys.argv[2]) and time.time() < resets else 1)
EOF
    then
        echo
        echo "STOPPING before $TAG: the plan's usage is at or above the threshold"
        echo "(USAGE_STOP=$USAGE_STOP). Rerun this script after the limit resets."
        ABORTED=yes; break
    fi

    # one random id names both directories, so no path says which bug this is
    W=$(mktemp -d /tmp/w-XXXXXXXX)
    ID=$(basename "$W")
    S="$STAGE_ROOT/$ID"
    fail() { echo "[$TAG] $1"; echo "$1" > "$STATUS"; rm -rf "$W" "$S"; }

    echo "[$TAG] checkout ($ID)"
    rm -rf "$S"
    if ! defects4j checkout -p "$P" -v "${B}f" -w "$S" >/dev/null 2>&1; then
        fail "checkout failed"; continue
    fi

    exp() { (cd "$S" && defects4j export -p "$1" 2>/dev/null) | grep -v '^Running' | tail -1; }
    SRC_TESTS=$(exp dir.src.tests)
    SRC_CLASSES=$(exp dir.src.classes)
    BIN_CLASSES=$(exp dir.bin.classes)
    BIN_TESTS=$(exp dir.bin.tests)
    CP_COMPILE=$(exp cp.compile)
    CLASSES=$( (cd "$S" && defects4j export -p classes.modified 2>/dev/null) \
                 | grep -v '^Running' | grep -v '^$')
    TRIGGERS=$( (cd "$S" && defects4j export -p tests.trigger 2>/dev/null) | grep '::')
    ISSUE=$(awk -F, -v b="$B" '$1 == b { print $4 }' "$D4J_HOME/framework/projects/$P/active-bugs.csv")

    if [ -z "$SRC_TESTS" ] || [ -z "$SRC_CLASSES" ] || [ -z "$CLASSES" ]; then
        fail "could not export metadata"; continue
    fi
    printf '%s\n' "$CLASSES"  > "$R.classes"
    printf '%s\n' "$TRIGGERS" > "$R.triggers"

    # the project's own -source level; the agent's compiler must not be more
    # permissive than the build that will judge the suite
    SRC_LEVEL=$(grep -h "^compile\.source" "$S"/*.properties 2>/dev/null \
                  | head -1 | cut -d= -f2 | tr -d '[:space:]')
    SRC_LEVEL=${SRC_LEVEL:-8}
    echo "$SRC_LEVEL" > "$R.srclevel"

    # ---- the staged checkout: no history, no trigger tests ------------------
    rm -rf "$S/.git"

    DELETED=""
    while read -r T; do
        [ -z "$T" ] && continue
        CLS="${T%%::*}"
        F="$S/$SRC_TESTS/$(echo "$CLS" | tr '.' '/').java"
        [ -f "$F" ] || continue
        if grep -q "extends TestCase\|junit.framework" "$F"; then J3=yes; else J3=no; fi
        DELETED="$DELETED $CLS:$J3"
        rm -f "$F"
    done <<< "$TRIGGERS"

    STUBBED=no
    if ! (cd "$S" && defects4j compile) > "$R.precompile" 2>&1; then
        echo "[$TAG] compile broke after deletion, writing stubs"
        for D in $DELETED; do
            write_stub "$S/$SRC_TESTS/$(echo "${D%%:*}" | tr '.' '/').java" \
                       "${D%%:*}" "${D##*:}"
        done
        STUBBED=yes
        if ! (cd "$S" && defects4j compile) > "$R.precompile2" 2>&1; then
            fail "compile fails even with stubs"; continue
        fi
    fi
    echo "$STUBBED" > "$R.stubbed"

    CP=$(exp cp.test)
    # cli2 declares jars in cp.test that were never materialised; fall back to
    # the copies Defects4J keeps per project
    EXTRA=$(find "$D4J_HOME/framework/projects/$P/lib" -name '*.jar' 2>/dev/null | tr '\n' ':')
    CP="$CP:$EXTRA"

    if javap -cp "$CP" org.junit.runner.JUnitCore >/dev/null 2>&1; then JUNIT=4; else JUNIT=3; fi

    CLASS_LIST=$(printf '  - %s\n' $CLASSES)

    # ---- the working copy ---------------------------------------------------
    if [ "$ARM" = "m2" ]; then
        cp -a "$S/." "$W/"
        rm -f "$W/defects4j.build.properties" "$W/.defects4j.config"
        find "$W" -type f -name '*.bak' -delete
        (cd "$W" && find . -type f \( \
              -iname 'RELEASE-NOTES*' -o -iname 'RELEASE_NOTES*' \
           -o -iname 'CHANGELOG' -o -iname 'CHANGELOG.*' \
           -o -iname 'CHANGES' -o -iname 'CHANGES.*' -o -iname 'changes.xml' \
           -o -iname 'release-history.xml' -o -iname 'upgradeto*.xml' \
           -o -iname 'NEWS' -o -iname 'NEWS.*' \
           -o -iname 'HISTORY' -o -iname 'HISTORY.*' \) -print -delete) > "$R.stripped"
        # the marker Defects4J leaves on the test methods it disabled, and the
        # paths into its installation that it writes into some build files
        grep -rlI 'Defects4J' "$W" 2>/dev/null | while read -r f; do
            sed -i 's/Defects4J: flaky method/disabled: flaky/g; s/Defects4J/the build/g' "$f"
        done
        grep -rlIF "$D4J_HOME" "$W" 2>/dev/null | while read -r f; do
            sed -i "s|$D4J_HOME/framework/projects|/opt/build|g; s|$D4J_HOME|/opt/build|g" "$f"
        done

        # the jars the tests need, and a script standing in for the defects4j
        # command: paths inside the checkout become relative, the rest is copied
        mkdir -p "$W/_tools/lib"
        REL_CP=$(python3 - "$S" "$W" "$CP" <<'EOF'
import os, shutil, sys
stage, work, cp = sys.argv[1:4]
out, seen, k = [], set(), 0
for e in cp.split(":"):
    if not e or e in seen:
        continue
    seen.add(e)
    if e == stage or e.startswith(stage + "/"):
        rel = os.path.relpath(e, stage)
        if os.path.exists(os.path.join(work, rel)):
            out.append(rel)
    elif os.path.isfile(e):
        k += 1
        name = f"{k:02d}-{os.path.basename(e)}"
        shutil.copy(e, os.path.join(work, "_tools", "lib", name))
        out.append("_tools/lib/" + name)
print(":".join(out))
EOF
)
        if [ "$JUNIT" = "4" ]; then
            RUNLINE='java -cp "_tools/out:$CP" org.junit.runner.JUnitCore "$@"'
        else
            RUNLINE='for c in "$@"; do java -cp "_tools/out:$CP" junit.textui.TestRunner "$c" || exit 1; done'
        fi
        cat > "$W/_tools/test.sh" <<EOS
#!/bin/bash
# Compiles every *AgentTest.java under $SRC_TESTS/ at the project's own
# -source level, then runs the test classes named on the command line
# (fully qualified), or all of them if none is named.
#
#   ./_tools/test.sh
#   ./_tools/test.sh org.example.FooAgentTest
set -e
cd "\$(dirname "\$0")/.."
export TZ=America/Los_Angeles
CP="$REL_CP"
rm -rf _tools/out && mkdir -p _tools/out
find $SRC_TESTS -name '*AgentTest.java' > _tools/.sources
[ -s _tools/.sources ] || { echo "no *AgentTest.java under $SRC_TESTS/"; exit 1; }
javac -nowarn -source $SRC_LEVEL -target $SRC_LEVEL -cp "\$CP" -d _tools/out @_tools/.sources
echo "compiled OK"
if [ \$# -eq 0 ]; then
    set -- \$(sed -e 's|^$SRC_TESTS/||' -e 's|\\.java\$||' -e 's|/|.|g' _tools/.sources)
fi
$RUNLINE
EOS
        chmod +x "$W/_tools/test.sh"
        TESTS_DIR="$SRC_TESTS"

        PROMPT="Write JUnit test classes for the following classes:

$CLASS_LIST

You are in the project's source tree. The classes are under $SRC_CLASSES/ and
the project's existing tests under $SRC_TESTS/.

Requirements:
- One test class per class above, named <ClassName>AgentTest, in the same
  package, under $SRC_TESTS/ following the package directory structure.
- The test class must be SELF-CONTAINED: do not extend or import any other
  test class or test helper. Any fixture you need, define inside your file.
- Match the JUnit version used by the other test classes in this project.
  Check them before writing. Some of these projects ship JUnit 3.8 only, where
  org.junit.Test and org.junit.Assert do not exist.
- This project compiles with -source $SRC_LEVEL. Use only syntax valid at that
  level: no underscores in numeric literals, no diamond operator, no lambdas,
  no try-with-resources unless the level allows them.
- Assert on returned values and on observable state, not merely that no
  exception is thrown.
- Cover boundary and error cases, not just the happy path.
- Do not modify or create any file other than the test classes named above.

Compile and run your tests with ./_tools/test.sh, which compiles every
*AgentTest.java under $SRC_TESTS/ and runs it. Finish when all your tests
pass."
    else
        mkdir -p "$W/api" "$W/lib" "$W/tests"

        SRC_FILES=""
        for C in $CLASSES; do
            SRC_FILES="$SRC_FILES $S/$SRC_CLASSES/$(echo "$C" | tr '.' '/').java"
        done
        # see run-spec-suites.sh for why file paths, -sourcepath and -package
        javadoc -quiet -package -Xdoclint:none -notimestamp \
            -d "$W/api" \
            -sourcepath "$S/$SRC_CLASSES" \
            -classpath "$CP_COMPILE" \
            $SRC_FILES > "$R.javadoc" 2>&1
        [ -f "$W/api/index.html" ] || { fail "javadoc failed"; continue; }

        if [ -n "$BIN_CLASSES" ] && [ -d "$S/$BIN_CLASSES" ]; then
            (cd "$S/$BIN_CLASSES" && jar cf "$W/lib/project.jar" .) \
                || { fail "could not jar the compiled classes"; continue; }
        else
            fail "could not locate dir.bin.classes"; continue
        fi
        find "$D4J_HOME/framework/projects/$P/lib" -name 'junit*.jar' \
            -exec cp {} "$W/lib/" \; 2>/dev/null
        echo "$CP" | tr ':' '\n' | grep -i 'junit.*\.jar$' | while read -r j; do
            [ -f "$j" ] && cp "$j" "$W/lib/" 2>/dev/null
        done
        if ! ls "$W/lib" | grep -qi junit; then
            fail "no junit jar found for the sandbox"; continue
        fi

        cat > "$W/compile.sh" <<EOS
#!/bin/bash
# Compile the tests under tests/ against the project's API, at the project's
# own -source level. There is no run script: executing the tests is not part
# of this task.
set -e
cd "\$(dirname "\$0")"
rm -rf out && mkdir -p out
find tests -name '*.java' > .sources
javac -nowarn -source $SRC_LEVEL -target $SRC_LEVEL -cp "lib/*" -d out @.sources
echo "compiled OK"
EOS
        chmod +x "$W/compile.sh"
        TESTS_DIR="tests"
        JUNIT_HINT=$(ls "$W/lib" | grep -i junit | head -1)

        PROMPT="Write JUnit test classes for the following classes:

$CLASS_LIST

You do NOT have the implementation source. You have:
  api/          generated javadoc for the classes above: this is your spec
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
- Do not modify or create any file other than the test classes named above.

Restrictions:
- Do NOT run the tests. Compile them with ./compile.sh, nothing else.
- Do NOT decompile, disassemble, unpack or otherwise inspect lib/. Read api/
  for the API.

Finish when ./compile.sh reports success."
    fi

    # one timestamp for every file: nothing is newer than anything else
    find "$W" -exec touch -h -d '2020-01-01 00:00:00 UTC' {} + 2>/dev/null

    # ---- what a search of the working copy still finds ----------------------
    python3 - "$W" "$P" "$B" "$ISSUE" "$ID" "$R.triggers" > "$R.leakscan" <<'EOF'
import os, re, sys
work, project, bug, issue, wid, trig_file = sys.argv[1:7]
names = sorted({l.strip().split("::")[1] for l in open(trig_file) if "::" in l})
pats = [("benchmark", re.compile(r"defects4j|\bd4j\b", re.I)),
        ("bug id", re.compile(rf"\b{project}[-_ ]{bug}\b", re.I)),
        ("staging path", re.compile(r"gen-stage|" + re.escape(wid)))]
m = re.match(r"([A-Za-z]+)-(\d+)$", issue or "")
if m:
    # not followed by ".1" or ".x": "CLI-1" must not match "commons-cli-1.1"
    pats.append(("issue id", re.compile(rf"\b{m.group(1)}[-_ ]?{m.group(2)}\b(?!\.[0-9x])", re.I)))
for nme in names:
    pats.append(("trigger name", re.compile(rf"\b{re.escape(nme)}\b")))
for dp, dn, fn in os.walk(work):
    dn[:] = [d for d in dn if not (dp == work and d == "_tools")]
    for f in fn:
        path = os.path.join(dp, f)
        rel = os.path.relpath(path, work)
        for kind, pat in pats:
            if kind != "staging path" and pat.search(rel):
                print(f"{kind}\t{rel}\t(file name)")
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        if b"\0" in data[:4096] and not f.endswith((".class", ".jar")):
            continue
        text = data.decode("latin-1")
        for kind, pat in pats:
            for hit in pat.finditer(text):
                line = text.count("\n", 0, hit.start()) + 1
                start = text.rfind("\n", 0, hit.start()) + 1
                end = text.find("\n", hit.end())
                snippet = " ".join(text[start:end if end >= 0 else None].split())[:140]
                snippet = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in snippet)
                print(f"{kind}\t{rel}:{line}\t{snippet}")
EOF
    LEAKS=$(cut -f1 "$R.leakscan" | sort | uniq -c | tr -s ' ' | tr '\n' ';')
    echo "[$TAG] leak scan: ${LEAKS:-clean}"

    # ---- settings: sandbox for Bash, nothing from the operator's profile ----
    # sent from a path that does not name the bug; a copy goes into the record
    SETTINGS="$STAGE_ROOT/$ID.settings.json"
    python3 - "$W" "$ARM" "$JDK_BIN" > "$SETTINGS" <<'EOF'
import json, os, shutil, sys
work, arm, jdk_bin = sys.argv[1:4]
deny = ["/home", "/mnt", "/tmp", "/var/tmp", "/opt", "/root", "/srv", "/media"]
allow = [work]
if arm == "s2":
    # nothing that runs, disassembles or unpacks what is in lib/
    deny += [jdk_bin, "/usr/bin/unzip", "/usr/bin/zipinfo", "/usr/bin/funzip",
             "/usr/bin/zipgrep", "/usr/bin/bsdtar"]
    # a jar is a zip: the scripting languages that could unpack it go too
    for tool in ("python3", "python", "perl"):
        found = shutil.which(tool)
        if found:
            deny += sorted({found, os.path.realpath(found)})
    allow += [os.path.join(jdk_bin, "javac")]
print(json.dumps({
    "autoMemoryEnabled": False,
    "sandbox": {
        "enabled": True,
        "failIfUnavailable": True,
        "allowUnsandboxedCommands": False,
        "filesystem": {"denyRead": deny, "allowRead": allow, "allowWrite": [work]},
        "network": {"allowedDomains": [], "strictAllowlist": True},
    },
}, indent=2))
EOF
    cp "$SETTINGS" "$R.settings.json"
    printf '%s\n' "$PROMPT" > "$R.prompt"
    touch "$W/.start" && touch -h -d '2020-01-01 00:00:01 UTC' "$W/.start"

    # ---- the agent ----------------------------------------------------------
    STARTED=$(date -u +%FT%TZ)
    if [ -n "$DRY" ]; then
        echo "[$TAG] DRY RUN: the first campaign's $DRY suite stands in for the agent"
        OLD="$ROOT/data/agent-suites/${P}-${B}f-${DRY}.1.tar.bz2"
        if [ -f "$OLD" ]; then
            mkdir -p "$W/$TESTS_DIR" && tar -xjf "$OLD" -C "$W/$TESTS_DIR"
        fi
        if [ "$ARM" = "m2" ]; then
            (cd "$W" && ./_tools/test.sh) > "$R.dry" 2>&1 < /dev/null; echo "exit=$?" >> "$R.dry"
        else
            (cd "$W" && ./compile.sh) > "$R.dry" 2>&1; echo "exit=$?" >> "$R.dry"
        fi
        echo "[$TAG] harness: $(tail -1 "$R.dry"), $(grep -c -E '^OK|^Tests run' "$R.dry") result lines"
        echo '{"type":"result","is_error":false,"total_cost_usd":0,"num_turns":0,"result":"dry run"}' > "$R.json"
    else
        echo "[$TAG] invoking agent ($MODEL, $ARM)"
        (cd "$W" && env -i HOME="$HOME" PATH="$AGENT_PATH" TZ=America/Los_Angeles LANG=C.UTF-8 \
                CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 \
                DISABLE_AUTOUPDATER=1 \
            "$CLAUDE_BIN" -p "$PROMPT" \
                --model "$MODEL" \
                --restricted --strict-mcp-config --disable-slash-commands \
                --tools "$TOOLS" \
                --settings "$SETTINGS" \
                --permission-mode acceptEdits --permission-prompts none \
                --no-session-persistence \
                --max-turns "$MAX_TURNS" --max-budget-usd "$MAX_BUDGET" \
                --output-format stream-json --verbose < /dev/null) \
            > "$R.stream.jsonl" 2> "$R.stderr"
        # Keep every message of the run. Drop what is not one: the events in
        # which the CLI reports the state of the account's usage limits. The
        # latest of those goes to a file outside the repository, for the check
        # at the top of the loop.
        python3 - "$R.stream.jsonl" "$USAGE_FILE" > "$R.json" <<'EOF'
import json, os, sys
path, usage_file = sys.argv[1:3]
last, kept, usage = None, [], None
for line in open(path, errors="replace"):
    try:
        o = json.loads(line)
    except ValueError:
        kept.append(line)
        continue
    if isinstance(o, dict) and o.get("type") == "rate_limit_event":
        info = o.get("rate_limit_info") or {}
        windows = list((info.get("unifiedWindows") or {}).values()) or [info]
        worst = max(windows, key=lambda w: w.get("utilization") or 0)
        usage = (worst.get("utilization") or 0, worst.get("resetsAt") or 0)
        continue
    kept.append(line)
    if isinstance(o, dict) and o.get("type") == "result":
        last = o
with open(path + ".tmp", "w") as fh:
    fh.writelines(kept)
os.replace(path + ".tmp", path)
if usage is not None:
    with open(usage_file, "w") as fh:
        fh.write(f"{usage[0]} {usage[1]}\n")
print(json.dumps(last if last is not None else {"is_error": True, "result": "no result message"}))
EOF
        REPORTED=$(python3 - "$R.stream.jsonl" <<'EOF'
import json, sys
for line in open(sys.argv[1], errors="replace"):
    try:
        o = json.loads(line)
    except ValueError:
        continue
    if isinstance(o, dict) and o.get("type") == "system" and o.get("subtype") == "init":
        print(f"{o.get('model', '')} {o.get('claude_code_version', '')}")
        break
EOF
)
        xz -9 -f "$R.stream.jsonl"
    fi
    FINISHED=$(date -u +%FT%TZ)
    rm -f "$SETTINGS"
    REPORTED=${REPORTED:-}

    (cd "$W" && find . -type f -newer .start ! -path './_tools/out/*' ! -name '.start' \
        ! -name '.sources' ! -path './out/*' | sort) > "$R.touched"

    python3 - "$R.meta.json" <<EOF
import json, sys
json.dump({
    "bug": "$TAG", "arm": "$ARM", "working_copy": "$ID",
    "model": "$MODEL", "cli": "$CLI_VERSION", "tools": "$TOOLS",
    "model_reported_by_run": "${REPORTED%% *}", "cli_reported_by_run": "${REPORTED##* }",
    "commit": "$COMMIT",
    "max_turns": $MAX_TURNS, "max_budget_usd": $MAX_BUDGET,
    "flags": "--restricted --strict-mcp-config --disable-slash-commands --no-session-persistence --permission-mode acceptEdits --permission-prompts none",
    "environment": "env -i HOME PATH TZ=America/Los_Angeles LANG=C.UTF-8 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 DISABLE_AUTOUPDATER=1",
    "junit": $JUNIT, "source_level": "$SRC_LEVEL", "stubbed": "$STUBBED",
    "issue": "$ISSUE", "started": "$STARTED", "finished": "$FINISHED",
    "dry_run": "$DRY",
}, open(sys.argv[1], "w"), indent=2)
EOF

    VERDICT=$(python3 -c "
import json
try:
    d = json.load(open('$R.json'))
except Exception:
    print('dead|unparseable|0|0'); raise SystemExit
cost = d.get('total_cost_usd') or 0
turns = d.get('num_turns') or 0
err = bool(d.get('is_error'))
res = (d.get('result') or '').replace('|', ' ').replace('\n', ' ')[:120]
limit = 'session limit' in res or 'rate limit' in res or 'usage limit' in res or d.get('api_error_status') == 429
state = 'ok' if not err else ('dead' if (cost == 0 or limit) else 'error')
print(f'{state}|{res}|{cost:.3f}|{turns}')" 2>/dev/null)

    STATE="${VERDICT%%|*}"; REST="${VERDICT#*|}"
    MSG="${REST%%|*}";      NUMS="${REST#*|}"
    echo "[$TAG] agent done: \$${NUMS%|*} turns=${NUMS#*|} state=$STATE"

    if [ "$STATE" = "dead" ]; then
        DEAD=$((DEAD + 1))
        echo "[$TAG] no usable API call: $MSG"
        # the attempt is recorded, apart from the run that will replace it
        mkdir -p "$RUNDIR/cut-short"
        STAMP=$(date -u +%Y%m%dT%H%M%SZ)
        for x in stream.jsonl.xz json meta.json touched stderr; do
            [ -f "$R.$x" ] && mv "$R.$x" "$RUNDIR/cut-short/$TAG.$STAMP.$x"
        done
        rm -rf "$W" "$S"
        if [ "$DEAD" -ge "$MAX_DEAD" ]; then
            echo; echo "ABORTING: $DEAD consecutive runs hit a usage limit."
            echo "Remaining bugs untouched; rerun this script later to resume."
            ABORTED=yes; break
        fi
        continue                     # no .status: this bug stays retryable
    fi
    DEAD=0
    # a run that ends on its turn or budget limit still counts: what it wrote
    # is judged like any other suite
    SUBTYPE=$(python3 -c "import json; print(json.load(open('$R.json')).get('subtype') or '')" 2>/dev/null)
    if [ "$STATE" = "error" ] && [ "${SUBTYPE#error_max_}" = "$SUBTYPE" ]; then
        fail "agent run returned an error — see ${TAG}.json"; continue
    fi

    WRITTEN=$(cd "$W/$TESTS_DIR" 2>/dev/null && find . -name "*AgentTest.java" 2>/dev/null)
    [ -z "$WRITTEN" ] && { fail "agent produced no test file"; continue; }

    # ---- acceptance, in the real checkout: compile, disable what fails ------
    for f in $WRITTEN; do
        mkdir -p "$S/$SRC_TESTS/$(dirname "$f")"
        cp "$W/$TESTS_DIR/$f" "$S/$SRC_TESTS/$f"
    done

    if ! (cd "$S" && defects4j compile) > "$R.compile" 2>&1; then
        fail "agent tests do not compile in the project"; continue
    fi

    TEST_PATHS=""
    for f in $WRITTEN; do TEST_PATHS="$TEST_PATHS $S/$SRC_TESTS/$f"; done
    METHODS_TOTAL=$(count_tests $TEST_PATHS)

    RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
    PRUNED_TOTAL=0

    for round in $(seq 1 $MAX_PRUNE_ROUNDS); do
        : > "$R.junit"
        if [ "$JUNIT" = "4" ]; then
            (cd "$S" && java -cp "$CP" org.junit.runner.JUnitCore $RUN_CLASSES) \
                > "$R.junit" 2>&1 < /dev/null && break
        else
            ALLOK=yes
            for RC in $RUN_CLASSES; do
                (cd "$S" && java -cp "$CP" junit.textui.TestRunner "$RC") \
                    >> "$R.junit" 2>&1 < /dev/null || ALLOK=no
            done
            [ "$ALLOK" = "yes" ] && break
        fi

        # "1) someTest(pkg.FooAgentTest)" in both runners
        FAILING=$(grep -oP '^\d+\)\s*\K\w+(?=\()' "$R.junit" | sort -u)
        if [ -z "$FAILING" ]; then
            fail "tests fail but no method names could be parsed (round $round)"
            break
        fi

        NPRUNED=0
        for f in $WRITTEN; do
            PR=$("$ROOT/bin/prune-failing-tests.py" "$S/$SRC_TESTS/$f" $FAILING)
            NPRUNED=$((NPRUNED + ${PR%% *}))
            # delete the compiled classes: ant's one-second timestamp
            # granularity otherwise skips the recompile
            if [ -n "$BIN_TESTS" ]; then
                REL="${f#./}"; REL="${REL%.java}"
                rm -f "$S/$BIN_TESTS/$REL.class" "$S/$BIN_TESTS/$REL"\$*.class
            fi
        done
        PRUNED_TOTAL=$((PRUNED_TOTAL + NPRUNED))
        echo "[$TAG] round $round: disabled $NPRUNED failing methods"

        if [ "$NPRUNED" -eq 0 ]; then
            fail "failing methods could not be disabled (round $round)"; break
        fi
        if ! (cd "$S" && defects4j compile) >> "$R.compile" 2>&1; then
            fail "compile broke after pruning"; break
        fi
    done
    [ -f "$STATUS" ] && continue

    echo "$PRUNED_TOTAL $METHODS_TOTAL" > "$R.pruned"
    echo "[$TAG] pruned $PRUNED_TOTAL of $METHODS_TOTAL tests"

    if [ "$METHODS_TOTAL" -gt 0 ] && [ "$PRUNED_TOTAL" -ge "$METHODS_TOTAL" ]; then
        fail "every test failed on the fixed version"; continue
    fi

    PKG=$(mktemp -d)
    for f in $WRITTEN; do
        mkdir -p "$PKG/$(dirname "$f")"
        cp "$S/$SRC_TESTS/$f" "$PKG/$f"
    done
    (cd "$PKG" && tar cjf "$ARCHIVE" .) || { rm -rf "$PKG"; fail "packaging failed"; continue; }
    rm -rf "$PKG"

    # the specification the s2 agent was given is part of the record: the
    # pages, without the scripts and styles javadoc bundles with them
    [ "$ARM" = "s2" ] && (cd "$W" && tar cJf "$R.api.tar.xz" \
        --exclude='*.js' --exclude='*.zip' --exclude='*.css' --exclude='*.png' \
        --exclude='api/legal' --exclude='api/jquery' --exclude='api/resources' api)

    echo "ok" > "$STATUS"
    rm -rf "$S"
    [ -n "${KEEP:-}" ] && echo "[$TAG] working copy kept: $W" || rm -rf "$W"
    echo "[$TAG] packaged: $(basename "$ARCHIVE")"
done < "$SAMPLE"

echo
[ "$ABORTED" = "yes" ] && echo "*** run aborted early — resume by rerunning ***" && echo
echo "$ARM suites packaged: $(ls "$SUITES"/*-${ARM}.1.tar.bz2 2>/dev/null | wc -l)"
echo "failures:           $(grep -Lx 'ok' "$RUNDIR"/*.status 2>/dev/null | wc -l)"
echo "disabled tests:     $(awk '{p+=$1; t+=$2} END{if(t)printf "%d of %d (%.1f%%)", p, t, 100*p/t}' "$RUNDIR"/*.pruned 2>/dev/null)"
echo "cost, as reported:  \$$(python3 - "$RUNDIR" <<'EOF'
import glob, json, sys
t = 0.0
for f in glob.glob(sys.argv[1] + "/*.json"):
    if f.endswith((".meta.json", ".settings.json")):
        continue
    try:
        t += json.load(open(f)).get("total_cost_usd", 0) or 0
    except Exception:
        pass
print(f"{t:.2f}")
EOF
)"

FAILED=$(grep -Lx 'ok' "$RUNDIR"/*.status 2>/dev/null)
if [ -n "$FAILED" ]; then
    echo; echo "failed bugs:"
    echo "$FAILED" | while read -r s; do echo "  $(basename "$s" .status): $(cat "$s")"; done
fi

# 3: stopped early, on a usage limit or at the usage threshold
[ "$ABORTED" = "yes" ] && exit 3
exit 0

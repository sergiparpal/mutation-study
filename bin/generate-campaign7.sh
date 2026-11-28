#!/bin/bash
#
# Seventh campaign: generate one test suite per bug of the sample and per arm,
# with the agent shown Defects4J's buggy version of the bug and asked to look
# for faults, or shown its fixed version.
#
#   ARM=f7   implementation-visible on Defects4J's buggy version (<id>b),
#            asked to look for faults, with f6's request
#   ARM=m7   implementation-visible on the fixed version (<id>f): the second
#            campaign's m2 made a second time
#
# WHY A SEVENTH SCRIPT
# --------------------
# generate-campaign6.sh and generate-suites.sh are part of the sixth and the
# second campaigns' records and stay as they ran. This script is the sixth's,
# with the second's staging and working copy in place of the export from a
# mirror and Maven's build (data/campaign7/PROTOCOL.md):
#   - a version of the bug is staged by Defects4J as generate-suites.sh staged
#     m2's (bin/campaign7-lib.sh): checked out, without its history, without
#     the developer test files that hold the trigger tests (a stub replaces one
#     where the build needs the class), and compiled by Defects4J;
#   - the working copy is m2's, made from the arm's version, with m2's
#     _tools/test.sh, which runs JUnitCore;
#   - m7's prompt is m2's, word for word. f7's is m2's with its last sentence,
#     "Finish when all your tests pass.", replaced by f6's paragraph, word for
#     word;
#   - acceptance is the sixth campaign's, on the arm's version, with f6's two
#     rules in f7. Its runner is bin/AgentTestRunner4.java, since the sample's
#     class paths have JUnit 4 and no JUnit Platform;
#   - in a dry run, both arms' stand-in suite is the developers' test classes
#     that hold the trigger tests, renamed; in f7 they are staged on the buggy
#     version, where their trigger tests should fail.
# The sandbox, the record and the handling of usage limits are the sixth's.
#
# WHAT THE AGENT GETS
# -------------------
# A copy of the staged version, from which these have been removed before the
# agent starts, as generate-suites.sh removed them for m2:
#   - .git
#   - the developer test files that hold the trigger tests (a stub replaces one
#     where the build needs the class name)
#   - defects4j.build.properties and .defects4j.config
#   - every *.bak: Defects4J's backups, among them complete copies of some
#     trigger test classes
#   - changelogs, release notes and upgrade guides
#   - the word "Defects4J" in the comments it leaves on tests it disabled, and
#     the paths into its installation in the build files it rewrites
# and to which _tools/ has been added: the jars the tests need, and test.sh,
# which compiles the agent's test classes and runs them with JUnitCore. The
# defects4j command is not available. File times are flattened. The two
# versions have the same tests, so the same files are removed in both arms,
# and the two working copies differ only in the hunks of the bug's source
# patch. The prompt says neither which version the agent has nor that a bug
# is there.
#
# The working copy lives in a directory with a random name. The staged
# version, where the suite is verified afterwards, is in a place the agent
# cannot read.
#
# WHAT IS ENFORCED, NOT ASKED
# ---------------------------
# The sixth campaign's, for the implementation-visible arm:
# - Bash runs in Claude Code's sandbox: no network, its own process namespace,
#   and of /home, /tmp, /mnt, /opt and the like it can read only its working
#   copy. /tmp is, to each command, an empty directory of its own, and its
#   $TMPDIR is the run's own directory, empty when the run starts.
# - The operating system's jars, its Maven and its package notes
#   (/usr/share/java, maven-repo, maven and doc) cannot be read, and the mvn on
#   the PATH does not start.
# - The file tools are confined to the working copy (--restricted). The Read
#   tool can also open the tool-results directory of the run's own session,
#   and nothing else of the home (bin/probe-saved-copies.py).
# - No web tools, no subagents, no skills, no MCP servers, no plugins; user,
#   project and local settings are ignored; persistent memory is off.
#
# WHAT IS RECORDED, PER RUN (data/campaign7/runs-<arm>/<bug>.*)
# -------------------------------------------------------------
#   .stream.jsonl.xz  every message of the run: text, tool calls and results
#                     (the CLI's events about the account's usage limits are
#                     not messages and are dropped)
#   .json             the closing result message (cost, turns, final text)
#   .prompt           the prompt as sent
#   .settings.json    the sandbox and permission settings as sent
#   .tmp.tar.xz       what the run left in its own temporary directory, if
#                     anything
#   .meta.json        model id, CLI version, flags, version, working-copy id,
#                     timings
#   .leakscan         what a search of the working copy for the trigger tests'
#                     names, the issue, the bug's identifier and the
#                     benchmark's name still finds
#   .stripped         the files removed as changelogs
#   .touched          every file the agent created or changed
#   .classes .triggers .srclevel .stubbed .precompile(2) .compile
#   .first.log .first.tsv        the suite as written, run on the arm's version
#   .accepted.log .accepted.tsv  the last run there, after the tests that
#                                failed there were left out
#   .excluded         the tests left out, one key per line
#   .pruned           "<left out> <total>" test methods
#   .split            in f7, the classes left out at acceptance because they
#                     did not finish, or ended the runner without its report,
#                     when run on their own
#
# ACCEPTANCE
# ----------
# The sixth campaign's, on the arm's own version. The suite is copied into the
# staged version and compiled there on its own, at the project's -source level,
# against the class path the agent's test.sh uses. It is run, and each test
# method that fails there is left out by name (.excluded); a class that fails
# as a whole is left out as a whole. The source is kept as the agent wrote it.
#
# In f7 the tests left out are the suite's findings, and two of m4's rules for
# a failed run do not apply. A suite whose every test fails is kept. A suite
# that does not finish within RUN_TIMEOUT, or that ends the runner without its
# report, is run again one class at a time, with the same limit, and a class
# that does either is left out as a whole; if the rest, run together again,
# still does not finish or still ends without a report, the run has no suite.
# In m7, as in m4, such a run is a suite that fails with nothing more to leave
# out.
#
# The model is named by its full id, the CLI is run from its versioned binary
# and told not to update itself, and each run records the commit of this
# repository it was made from.
#
# USAGE LIMITS
# ------------
# As in the fourth to sixth campaigns: when the plan's usage reaches
# USAGE_STOP (default 0.95) the script stops before starting another run and
# picks up where it left off when run again. A run that a limit cuts short
# leaves no .status and is made again; its record moves to cut-short/ and its
# tests are not used.
#
# Usage:
#   ARM=f7 ./bin/generate-campaign7.sh                        # every bug
#   ARM=m7 ./bin/generate-campaign7.sh data/campaign7/subjects.txt 3
#   ARM=f7 ONLY="Lang-43" ./bin/generate-campaign7.sh
#   ARM=f7 DRY=1 OUT=/tmp/dry ./bin/generate-campaign7.sh
#       DRY=1: no model call. The scripts given to the agent are tried on a
#       two-test class written here, and developers' tests stand in for the
#       agent's suite: in both arms the test classes that hold the trigger
#       tests, renamed, which in f7 are staged on the buggy version. They are
#       not self-contained, so in a dry run, and only there, the project's test
#       sources are on the compiler's source path.
#   KEEP=1 keeps the working copy of a successful run, for inspection

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/bin/campaign7-lib.sh"

ARM=${ARM:-}
case "$ARM" in
    f7) REV_KIND=buggy; V=b ;;
    m7) REV_KIND=fixed; V=f ;;
    *) echo "set ARM=f7 (the buggy version, asked to look for faults) or ARM=m7 (the fixed version)"; exit 1 ;;
esac

SUBJECTS=${1:-data/campaign7/subjects.txt}
LIMIT=${2:-0}
ONLY=${ONLY:-}
MODEL=${MODEL:-claude-sonnet-5}
MAX_TURNS=${MAX_TURNS:-50}
MAX_BUDGET=${MAX_BUDGET:-5}
MAX_DEAD=${MAX_DEAD:-2}
MAX_ROUNDS=5
OUT=${OUT:-data/campaign7}
DRY=${DRY:-}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}    # under /home: the agent cannot read it
USAGE_STOP=${USAGE_STOP:-0.95}      # share of the plan's usage limit at which to stop
USAGE_FILE=$STAGE_ROOT/usage        # last reported usage; never in the repository
TOOLS="Bash,Read,Write,Edit,Glob,Grep"
AGENT_PATH="$C3_PATH"

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
RUNDIR=$OUT_ABS/runs-$ARM

command -v defects4j >/dev/null || { echo "defects4j not found under $D4J_HOME"; exit 1; }
command -v javac     >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
[ -n "$DRY" ] || command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
case "$MODEL" in
    claude-*-[0-9]*) ;;
    *) echo "MODEL must be a full model id, not an alias: $MODEL"; exit 1 ;;
esac

JDK_BIN=$(dirname "$(readlink -f "$(command -v javac)")")
JAVA_VERSION=$(java -version 2>&1 | head -1 | tr -d '"')
D4J_VERSION=$(git -C "$D4J_HOME" describe --tags 2>/dev/null || echo unknown)

# The binary itself, not the `claude` link: an update moves the link.
CLAUDE_BIN=${CLAUDE_BIN:-$( [ -n "$DRY" ] || readlink -f "$(command -v claude)")}
CLI_VERSION=$( [ -n "$DRY" ] && echo "dry run" || "$CLAUDE_BIN" --version 2>/dev/null | head -1)

# Java, Defects4J and, outside a dry run, the CLI must be the protocol's
WHY=$(c7_check_env $( [ -n "$DRY" ] || echo cli )) || { echo "$WHY"; exit 1; }

# A run is tied to the commit of the scripts that made it. Outside a dry run,
# refuse to start if they differ from that commit.
COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
if [ -z "$DRY" ] && [ -z "${ALLOW_DIRTY:-}" ] \
   && [ -n "$(git -C "$ROOT" status --porcelain -- bin "$SUBJECTS" 2>/dev/null)" ]; then
    echo "bin/ or the subject list differs from the last commit: commit first, or set ALLOW_DIRTY=1"
    exit 1
fi

mkdir -p "$SUITES" "$RUNDIR" "$STAGE_ROOT"

n=0
DEAD=0
ABORTED=no

while read -r TAG _rest; do
    TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
    [ -z "$TAG" ] && continue
    case "$TAG" in \#*) continue ;; esac

    if [ -n "$ONLY" ]; then
        case " $ONLY " in *" $TAG "*) ;; *) continue ;; esac
    fi

    n=$((n + 1))
    if [ "$LIMIT" -gt 0 ] && [ "$n" -gt "$LIMIT" ]; then break; fi

    P=${TAG%-*}
    B=${TAG##*-}
    ARCHIVE="$SUITES/${TAG}-${ARM}.tar.bz2"
    STATUS="$RUNDIR/${TAG}.status"
    R="$RUNDIR/${TAG}"

    if [ -f "$STATUS" ]; then
        echo "[$TAG] already attempted ($(cat "$STATUS")) — skipping"
        continue
    fi

    # Do not start a run the plan's usage limit would cut short.
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
    RUNNER="$STAGE_ROOT/$ID.runner"
    fail() { echo "[$TAG] $1"; echo "$1" > "$STATUS"; rm -rf "$W" "$S" "$RUNNER"; }

    echo "[$TAG] staging the $REV_KIND version ($ID)"
    rm -rf "$S" "$RUNNER"
    if ! stage_bug "$P" "$B" "$V" "$S" "$R.precompile"; then
        fail "the $REV_KIND version could not be staged: $STAGE_FAIL"; continue
    fi
    C7="$S/.c7"
    SRC_TESTS=$(cat "$C7/src-tests")
    SRC_CLASSES=$(cat "$C7/src-classes")
    SRC_LEVEL=$(cat "$C7/srclevel")
    CLASSES=$(cat "$C7/classes")
    ISSUE=$(cat "$C7/issue")
    CP=$(cat "$C7/cp-test")
    STUBBED=$(cat "$C7/stubbed")
    cp "$C7/classes" "$R.classes"
    cp "$C7/triggers" "$R.triggers"
    echo "$SRC_LEVEL" > "$R.srclevel"
    echo "$STUBBED" > "$R.stubbed"
    [ "$(cat "$C7/junit")" = "4" ] || { fail "JUnit 4 is not on the class path"; continue; }

    if ! build_runner4 "$S" "$RUNNER" > "$R.runner" 2>&1; then
        fail "the runner does not compile against the project's JUnit"; continue
    fi
    rm -f "$R.runner"

    CLASS_LIST=$(printf '  - %s\n' $CLASSES)

    # ---- the working copy: m2's ---------------------------------------------
    cp -a "$S/." "$W/"
    rm -rf "$W/.c7"
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
    RUNLINE='java -cp "_tools/out:$CP" org.junit.runner.JUnitCore "$@"'
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

    # m2's last sentence; in f7, the paragraph that replaces it, f6's
    ENDING=" Finish when all your tests
pass."
    if [ "$ARM" = "f7" ]; then
        ENDING="

The classes may contain bugs, and your tests are meant to find them. Write
each test for the behaviour the class should have, as its documentation and
the rest of the project describe it, not for whatever the code happens to
do. When a test fails, decide whether the test or the code is wrong: correct
a wrong test, and leave a test that fails because the code is wrong as it
is. Finish when every test that still fails is one you believe shows a bug,
and name those tests in your final message, with the bug each one shows."
    fi

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
*AgentTest.java under $SRC_TESTS/ and runs it.$ENDING"

    # one timestamp for every file: nothing is newer than anything else
    find "$W" -exec touch -h -d '2020-01-01 00:00:00 UTC' {} + 2>/dev/null

    # ---- what a search of the working copy still finds: m2's search ---------
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
    # both arms see the implementation: the implementation-visible arm's settings
    python3 "$ROOT/bin/agent-sandbox.py" settings "$W" m "$JDK_BIN" > "$SETTINGS" \
        || { fail "the sandbox settings could not be written"; continue; }
    cp "$SETTINGS" "$R.settings.json"
    printf '%s\n' "$PROMPT" > "$R.prompt"
    touch "$W/.start" && touch -h -d '2020-01-01 00:00:01 UTC' "$W/.start"

    # ---- the agent ----------------------------------------------------------
    STARTED=$(date -u +%FT%TZ)
    RUN_TMP=""
    DRY_SOURCEPATH=""
    REPORTED=""
    if [ -n "$DRY" ]; then
        echo "[$TAG] DRY RUN: the agent's scripts on a two-test class, then the developers' trigger-test classes as the suite, on the $REV_KIND version"
        # 1. the scripts the agent is given, on a class that needs nothing else
        C1=$(echo "$CLASSES" | head -1)
        PKG1="${C1%.*}"; CLS1="${C1##*.}"
        PROBE="$W/$TESTS_DIR/$(echo "$PKG1" | tr '.' '/')/${CLS1}AgentTest.java"
        mkdir -p "$(dirname "$PROBE")"
        cat > "$PROBE" <<EOF
package $PKG1;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.fail;

import org.junit.Test;

public class ${CLS1}AgentTest {
    @Test
    public void classIsThere() throws Exception {
        assertNotNull(Class.forName("$C1"));
    }

    @Test
    public void failsOnPurpose() {
        fail("dry run");
    }
}
EOF
        (cd "$W" && c3_env ./_tools/test.sh) > "$R.dry" 2>&1 < /dev/null; echo "exit=$?" >> "$R.dry"
        rm -rf "$W/_tools/out" "$W/_tools/.sources"
        rm -f "$PROBE"
        echo "[$TAG] agent's script: $(grep -E '^Tests run|^compiled OK|^OK' "$R.dry" | paste -sd' ' -), $(tail -1 "$R.dry")"
        # 2. developers' tests, renamed, as the suite: in both arms the test
        # classes that hold the trigger tests, which in f7 are staged on the
        # buggy version
        python3 - "$C7/trigger-src" "$W/$TESTS_DIR" <<'EOF' || { fail "the stand-in suite could not be written"; continue; }
import os, re, sys
src, dest = sys.argv[1:3]
files = [os.path.join(dp, f) for dp, _, fn in os.walk(src) for f in fn if f.endswith(".java")]
if not files:
    sys.exit("no trigger-test file")
def renamed(simple):
    return (simple[:-4] if simple.endswith("Test") else simple) + "AgentTest"
table = {os.path.basename(f)[:-5]: renamed(os.path.basename(f)[:-5]) for f in files}
for f in files:
    text = open(f, encoding="utf-8", errors="replace").read()
    for old, new in table.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    rel = os.path.dirname(os.path.relpath(f, src))
    out = os.path.join(dest, rel, table[os.path.basename(f)[:-5]] + ".java")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
EOF
        DRY_SOURCEPATH="-sourcepath $SRC_TESTS"
        echo '{"type":"result","is_error":false,"total_cost_usd":0,"num_turns":0,"result":"dry run"}' > "$R.json"
    else
        echo "[$TAG] invoking agent ($MODEL, $ARM)"
        # the run's own temporary directory; the name is short so that the CLI
        # does not fall back to the one all sessions share (bin/agent-sandbox.py)
        RUN_TMP=$(mktemp -d /tmp/t-XXXXXXXX)
        (cd "$W" && env -i HOME="$HOME" PATH="$AGENT_PATH" TZ=America/Los_Angeles LANG=C.UTF-8 \
                CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 \
                DISABLE_AUTOUPDATER=1 CLAUDE_CODE_TMPDIR="$RUN_TMP" \
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
        # what the run left in its temporary directory goes into its record
        if [ -n "$(find "$RUN_TMP" -mindepth 1 -print -quit 2>/dev/null)" ]; then
            tar -C "$RUN_TMP" -cJf "$R.tmp.tar.xz" .
        fi
        rm -rf "$RUN_TMP"
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

    (cd "$W" && find . -type f -newer .start ! -path './_tools/out/*' ! -name '.start' \
        ! -name '.sources' ! -path './out/*' | sort) > "$R.touched"

    python3 - "$R.meta.json" <<EOF
import json, sys
json.dump({
    "bug": "$TAG", "arm": "$ARM", "working_copy": "$ID",
    "project": "$P", "bug_id": "$B", "version": "${B}${V}", "version_kind": "$REV_KIND",
    "issue": "$ISSUE",
    "model": "$MODEL", "cli": "$CLI_VERSION", "tools": "$TOOLS",
    "model_reported_by_run": "${REPORTED%% *}", "cli_reported_by_run": "${REPORTED##* }",
    "commit": "$COMMIT",
    "max_turns": $MAX_TURNS, "max_budget_usd": $MAX_BUDGET,
    "flags": "--restricted --strict-mcp-config --disable-slash-commands --no-session-persistence --permission-mode acceptEdits --permission-prompts none",
    "environment": "env -i HOME PATH TZ=America/Los_Angeles LANG=C.UTF-8 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 DISABLE_AUTOUPDATER=1 CLAUDE_CODE_TMPDIR=<the run's own directory>",
    "settings": "bin/agent-sandbox.py settings", "tmpdir": "${RUN_TMP:-}",
    "source_level": "$SRC_LEVEL", "junit": 4, "stubbed": "$STUBBED",
    "java": "$JAVA_VERSION", "defects4j": "$D4J_VERSION",
    "started": "$STARTED", "finished": "$FINISHED",
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
        for x in stream.jsonl.xz json meta.json touched stderr tmp.tar.xz; do
            [ -f "$R.$x" ] && mv "$R.$x" "$RUNDIR/cut-short/$TAG.$STAMP.$x"
        done
        rm -rf "$W" "$S" "$RUNNER"
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

    WRITTEN=$(cd "$W/$TESTS_DIR" 2>/dev/null && find . -name "*AgentTest.java" 2>/dev/null | sort)
    [ -z "$WRITTEN" ] && { fail "agent produced no test file"; continue; }

    # ---- acceptance, in the staged version ----------------------------------
    SRCS=""
    for f in $WRITTEN; do
        mkdir -p "$S/$SRC_TESTS/$(dirname "$f")"
        cp "$W/$TESTS_DIR/$f" "$S/$SRC_TESTS/$f"
        SRCS="$SRCS $SRC_TESTS/${f#./}"
    done
    mkdir -p "$S/_acc/out"
    if ! (cd "$S" && c3_env javac -nowarn $(javac_level "$S") -Xlint:-options -encoding UTF-8 $DRY_SOURCEPATH \
            -cp "$CP" -d _acc/out $SRCS) > "$R.compile" 2>&1; then
        fail "agent tests do not compile in the project"; continue
    fi

    RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
    CP_RUN="_acc/out:$RUNNER:$CP"
    : > "$R.excluded"
    rm -f "$R.split"
    ACCEPTED=no
    for round in $(seq 1 $MAX_ROUNDS); do
        rm -f "$S/_acc/report.tsv"
        (cd "$S" && c3_env timeout "$RUN_TIMEOUT" java -cp "$CP_RUN" AgentTestRunner4 \
            --report "$S/_acc/report.tsv" --exclude "$R.excluded" $RUN_CLASSES) \
            > "$R.accepted.log" 2>&1 < /dev/null
        RC=$?
        cp "$S/_acc/report.tsv" "$R.accepted.tsv" 2>/dev/null || : > "$R.accepted.tsv"
        # the first run that ends with a report: round 1, or in f7 the run after a split
        if [ "$round" -eq 1 ] || [ ! -s "$R.first.tsv" ]; then
            cp "$R.accepted.log" "$R.first.log"; cp "$R.accepted.tsv" "$R.first.tsv"
        fi
        # in f7, a run that ends without the runner's report has not finished either
        WHY=""
        if [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then
            WHY="does not finish"
        elif [ "$ARM" = "f7" ] && [ ! -f "$S/_acc/report.tsv" ]; then
            WHY="ends without the runner's report (exit $RC)"
        fi
        if [ -n "$WHY" ]; then
            if [ "$ARM" = "f7" ] && [ ! -f "$R.split" ]; then
                # one class at a time; a class that does not finish, or ends
                # without a report, is left out whole
                : > "$R.split"
                for C in $RUN_CLASSES; do
                    rm -f "$S/_acc/class.tsv"
                    (cd "$S" && c3_env timeout "$RUN_TIMEOUT" java -cp "$CP_RUN" AgentTestRunner4 \
                        --report "$S/_acc/class.tsv" --exclude "$R.excluded" "$C") > /dev/null 2>&1 < /dev/null
                    RCC=$?
                    if [ "$RCC" -eq 124 ] || [ "$RCC" -eq 137 ] || [ ! -f "$S/_acc/class.tsv" ]; then
                        echo "$C" >> "$R.split"; echo "$C" >> "$R.excluded"
                    fi
                done
                rm -f "$S/_acc/class.tsv"
                echo "[$TAG] round $round: the suite $WHY; $(grep -c . "$R.split") class(es) left out as a whole"
                [ -s "$R.split" ] && continue
            fi
            if [ "$WHY" = "does not finish" ]; then
                fail "the suite does not finish on the $REV_KIND version (${RUN_TIMEOUT}s)"
            else
                fail "the suite $WHY on the $REV_KIND version"
            fi
            break
        fi
        [ "$RC" -eq 0 ] && { ACCEPTED=yes; break; }
        if [ "$RC" -eq 2 ]; then
            fail "the suite holds no test method"; break
        fi
        NEW=$(excluded_from "$R.accepted.tsv" | grep -vxF -f "$R.excluded")
        if [ -z "$NEW" ]; then
            fail "the suite fails on the $REV_KIND version and nothing more can be left out (round $round)"
            break
        fi
        printf '%s\n' "$NEW" >> "$R.excluded"
        echo "[$TAG] round $round: left out $(printf '%s\n' "$NEW" | wc -l) failing test(s)"
    done
    [ -f "$STATUS" ] && continue
    [ "$ACCEPTED" = "yes" ] || { fail "the suite did not settle in $MAX_ROUNDS rounds"; continue; }

    read -r LEFT_OUT METHODS_TOTAL <<< "$(count_methods "$R.first.tsv" "$R.excluded")"
    echo "$LEFT_OUT $METHODS_TOTAL" > "$R.pruned"
    echo "[$TAG] left out $LEFT_OUT of $METHODS_TOTAL tests"
    # in f7, a class left out because it did not finish has no method counted
    if [ "$METHODS_TOTAL" -eq 0 ] && [ ! -s "$R.split" ]; then
        fail "the suite holds no test method"; continue
    fi
    # in f7 a suite whose every test fails is kept: its tests are its findings
    if [ "$ARM" != "f7" ] && [ "$LEFT_OUT" -ge "$METHODS_TOTAL" ]; then
        fail "every test failed on the $REV_KIND version"; continue
    fi

    # the suite as the agent wrote it, and the list of what was left out
    PKG=$(mktemp -d)
    for f in $WRITTEN; do
        mkdir -p "$PKG/$(dirname "$f")"
        cp "$W/$TESTS_DIR/$f" "$PKG/$f"
    done
    cp "$R.excluded" "$PKG/excluded.txt"
    (cd "$PKG" && tar cjf "$ARCHIVE" .) || { rm -rf "$PKG"; fail "packaging failed"; continue; }
    rm -rf "$PKG"

    echo "ok" > "$STATUS"
    rm -rf "$S" "$RUNNER"
    [ -n "${KEEP:-}" ] && echo "[$TAG] working copy kept: $W" || rm -rf "$W"
    echo "[$TAG] packaged: $(basename "$ARCHIVE")"
done < "$SUBJECTS"

echo
[ "$ABORTED" = "yes" ] && echo "*** run aborted early — resume by rerunning ***" && echo
echo "$ARM suites packaged: $(ls "$SUITES"/*-${ARM}.tar.bz2 2>/dev/null | wc -l)"
echo "failures:           $(grep -Lx 'ok' "$RUNDIR"/*.status 2>/dev/null | wc -l)"
echo "tests left out:     $(awk '{p+=$1; t+=$2} END{if(t)printf "%d of %d (%.1f%%)", p, t, 100*p/t}' "$RUNDIR"/*.pruned 2>/dev/null)"
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

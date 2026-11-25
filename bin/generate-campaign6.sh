#!/bin/bash
#
# Sixth campaign: generate one test suite per post-cutoff subject and per arm,
# under the conditions of the fifth campaign, with the agent shown the faulty
# revision and asked to look for faults, or shown the fix commit.
#
#   ARM=f6   implementation-visible on the faulty revision: the parent of the
#            fix commit (<fix>~1, the parent the measurement calls buggy),
#            asked to look for faults
#   ARM=m6   implementation-visible on the fix commit: the fourth campaign's m4
#
# WHY A SIXTH SCRIPT
# ------------------
# generate-campaign5.sh is part of the fifth campaign's record and stays as
# it ran. This script is that one with these changes and no other
# (data/campaign6/PROTOCOL.md):
#   - the arms are f6, staged as b5 was, on <fix>~1, and m6, staged as m5 was,
#     on the fix commit;
#   - m6's prompt is m4's, word for word. f6's is m4's with its last sentence,
#     "Finish when all your tests pass.", replaced by a paragraph that asks
#     for faults;
#   - at acceptance in f6, a suite whose every test fails on the faulty
#     revision is kept, and a suite that does not finish there, or ends the
#     runner without its report, is run again one class at a time, a class
#     that does either being left out as a whole (.split);
#   - the first run at acceptance (.first.log, .first.tsv) is the first that
#     ends with a report, which in f6 can be the one after that split;
#   - each run at acceptance starts with the previous run's report removed,
#     so that a run that ends without one cannot be read as having written it;
#   - in a dry run, both arms' stand-in suite is the developers' test classes
#     for the fix, renamed, as m5's was; in f6 they are staged on the faulty
#     revision, where their trigger tests should fail;
#   - the subjects are the sixth campaign's list, the fourth campaign's 115 in
#     a new order, with the fourth campaign's records (data/campaign4/subjects/).
# What the scripts share with the measurement is bin/campaign3-lib.sh, the
# third campaign's, unchanged.
#
# WHAT THE AGENT GETS
# -------------------
# The tree of the arm's revision, exported without its history, from which
# these have been removed before the agent starts:
#   - every test file the fix commit touches. In m6 these are the files that
#     hold the trigger tests. In f6 they are those files as they were before
#     the fix, removed so that the two working copies hold the same files
#   - changelogs, release notes and upgrade guides
#   - what the build leaves under target/, except the compiled classes
# and to which _tools/ has been added: the jars the tests need, the runner
# (bin/AgentTestRunner.java, compiled) and test.sh, which compiles the agent's
# test classes and runs them. Maven is not available. File times are
# flattened. The prompt is m4's, word for word in m6 and with its last
# sentence replaced in f6; neither says which revision the agent has.
#
# The working copy lives in a directory with a random name. The staged
# revision, where the suite is verified afterwards, is in a place the agent
# cannot read.
#
# WHAT IS ENFORCED, NOT ASKED
# ---------------------------
# The fourth campaign's, for its implementation-visible arm:
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
# WHAT IS RECORDED, PER RUN (data/campaign6/runs-<arm>/<subject>.*)
# -----------------------------------------------------------------
#   .stream.jsonl.xz  every message of the run: text, tool calls and results
#                     (the CLI's events about the account's usage limits are
#                     not messages and are dropped)
#   .json             the closing result message (cost, turns, final text)
#   .prompt           the prompt as sent
#   .settings.json    the sandbox and permission settings as sent
#   .tmp.tar.xz       what the run left in its own temporary directory, if
#                     anything
#   .meta.json        model id, CLI version, flags, revision, working-copy id,
#                     timings
#   .leakscan         what a search of the working copy for the trigger tests'
#                     names, the issue and the commit still finds
#   .stripped         the files removed as changelogs
#   .touched          every file the agent created or changed
#   .classes .testclasses .triggers .javac .precompile .compile
#   .first.log .first.tsv        the suite as written, run on the arm's revision
#   .accepted.log .accepted.tsv  the last run there, after the tests that
#                                failed there were left out
#   .excluded         the tests left out, one key per line
#   .pruned           "<left out> <total>" test methods
#   .split            in f6, the classes left out at acceptance because they
#                     did not finish, or ended the runner without its report,
#                     when run on their own
#
# ACCEPTANCE
# ----------
# m4's, on the arm's own revision. The suite is copied into the staged
# revision and compiled there on its own, against the production classes and
# the project's test libraries. It is run, and each test method that fails
# there is left out by name (.excluded); a class that fails as a whole is left
# out as a whole. The source is kept as the agent wrote it.
#
# In f6 the tests left out are the suite's findings, and two of m4's rules for
# a failed run do not apply. A suite whose every test fails is kept. A suite
# that does not finish within RUN_TIMEOUT, or that ends the runner without its
# report, is run again one class at a time, with the same limit, and a class
# that does either is left out as a whole; if the rest, run together again,
# still does not finish or still ends without a report, the run has no suite.
# The runner writes its report whenever it gets to the end, so a run without
# one died on the way, as a JVM does when a test exhausts its heap. In m6, as
# in m4, such a run is a suite that fails with nothing more to leave out.
#
# The model is named by its full id, the CLI is run from its versioned binary
# and told not to update itself, and each run records the commit of this
# repository it was made from.
#
# USAGE LIMITS
# ------------
# As in the fourth campaign: when the plan's usage reaches USAGE_STOP (default
# 0.95) the script stops before starting another run and picks up where it
# left off when run again. A run that a limit cuts short leaves no .status and
# is made again; its record moves to cut-short/ and its tests are not used.
#
# Usage:
#   ARM=f6 ./bin/generate-campaign6.sh                        # every subject
#   ARM=m6 ./bin/generate-campaign6.sh data/campaign6/subjects.txt 3
#   ARM=f6 ONLY="commons-csv-b5940a642" ./bin/generate-campaign6.sh
#   ARM=f6 DRY=1 OUT=/tmp/dry ./bin/generate-campaign6.sh
#   the pilot, on the third campaign's two pilot subjects and their records:
#   SUBJECT_ROOTS=data/campaign3/pilot/subjects OUT=data/campaign6/pilot \
#       ARM=f6 ./bin/generate-campaign6.sh data/campaign3/pilot/subjects.txt
#       DRY=1: no model call. The scripts given to the agent are tried on a
#       two-test class written here, and developers' tests stand in for the
#       agent's suite: in both arms their test classes for the fix, renamed,
#       which in f6 are staged on the faulty revision. They are not
#       self-contained, so in a dry run, and
#       only there, the project's test sources are on the compiler's source
#       path.
#   KEEP=1 keeps the working copy of a successful run, for inspection

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
# the fourth campaign's records, reused as they are, and the pool's clones;
# the library reads both when it is sourced
SUBJECT_ROOTS=${SUBJECT_ROOTS:-data/campaign4/subjects}
MINING=${MINING:-$HOME/code/mining-pool}
. "$ROOT/bin/campaign3-lib.sh"
export TZ=America/Los_Angeles

ARM=${ARM:-}
case "$ARM" in
    f6) REV_KIND=faulty ;;
    m6) REV_KIND=fixed ;;
    *) echo "set ARM=f6 (the faulty revision, asked to look for faults) or ARM=m6 (the fixed revision)"; exit 1 ;;
esac

SUBJECTS=${1:-data/campaign6/subjects.txt}
LIMIT=${2:-0}
ONLY=${ONLY:-}
MODEL=${MODEL:-claude-sonnet-5}
MAX_TURNS=${MAX_TURNS:-50}
MAX_BUDGET=${MAX_BUDGET:-5}
MAX_DEAD=${MAX_DEAD:-2}
MAX_ROUNDS=5
OUT=${OUT:-data/campaign6}
DRY=${DRY:-}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}    # under /home: the agent cannot read it
USAGE_STOP=${USAGE_STOP:-0.95}      # share of the plan's usage limit at which to stop
USAGE_FILE=$STAGE_ROOT/usage        # last reported usage; never in the repository
TOOLS="Bash,Read,Write,Edit,Glob,Grep"
AGENT_PATH="$C3_PATH"
SRC_CLASSES=src/main/java
SRC_TESTS=src/test/java

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
RUNDIR=$OUT_ABS/runs-$ARM

command -v mvn     >/dev/null || { echo "mvn not on PATH"; exit 1; }
command -v javac   >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
[ -n "$DRY" ] || command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
case "$MODEL" in
    claude-*-[0-9]*) ;;
    *) echo "MODEL must be a full model id, not an alias: $MODEL"; exit 1 ;;
esac

JDK_BIN=$(dirname "$(readlink -f "$(command -v javac)")")
JAVA_VERSION=$(java -version 2>&1 | head -1 | tr -d '"')
MAVEN_VERSION=$(mvn -v 2>/dev/null | head -1 | sed 's/ (.*//')

# The binary itself, not the `claude` link: an update moves the link.
CLAUDE_BIN=${CLAUDE_BIN:-$( [ -n "$DRY" ] || readlink -f "$(command -v claude)")}
CLI_VERSION=$( [ -n "$DRY" ] && echo "dry run" || "$CLAUDE_BIN" --version 2>/dev/null | head -1)

# A run is tied to the commit of the scripts that made it. Outside a dry run,
# refuse to start if they differ from that commit.
COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
if [ -z "$DRY" ] && [ -z "${ALLOW_DIRTY:-}" ] \
   && [ -n "$(git -C "$ROOT" status --porcelain -- bin "$SUBJECTS" $SUBJECT_ROOTS 2>/dev/null)" ]; then
    echo "bin/, the subject list or the subjects' records differ from the last commit: commit first, or set ALLOW_DIRTY=1"
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

    ARCHIVE="$SUITES/${TAG}-${ARM}.tar.bz2"
    STATUS="$RUNDIR/${TAG}.status"
    R="$RUNDIR/${TAG}"

    if [ -f "$STATUS" ]; then
        echo "[$TAG] already attempted ($(cat "$STATUS")) — skipping"
        continue
    fi

    D=$(subject_dir "$ROOT" "$TAG") || { echo "[$TAG] no record of this subject"; exit 1; }
    [ "$(cat "$D/status" 2>/dev/null)" = "ok" ] || { echo "[$TAG] the subject was not validated"; exit 1; }

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

    REPO=$(subject_field "$D" project)
    SHA=$(subject_field "$D" sha)
    # the revision the agent is given and the suite is accepted on: the fix
    # commit in m6, its parent in f6, which is the parent the measurement uses
    if [ "$ARM" = "f6" ]; then REV="$SHA~1"; else REV="$SHA"; fi
    SUBJECT=$(subject_field "$D" subject)
    CLASSES=$(cat "$D/classes.txt")
    TESTCLASSES=$(cat "$D/testclasses.txt")
    ISSUE=$(echo "$SUBJECT" | grep -o -E '\b[A-Z]{2,}-[0-9]+\b' | head -1)
    PULL=$(echo "$SUBJECT" | grep -o -E '#[0-9]+' | tail -1 | tr -d '#')

    # one random id names both directories, so no path says which subject this is
    W=$(mktemp -d /tmp/w-XXXXXXXX)
    ID=$(basename "$W")
    S="$STAGE_ROOT/$ID"
    RUNNER="$STAGE_ROOT/$ID.runner"
    fail() { echo "[$TAG] $1"; echo "$1" > "$STATUS"; rm -rf "$W" "$S" "$RUNNER"; }

    echo "[$TAG] staging the $REV_KIND revision ($ID)"
    rm -rf "$S" "$RUNNER"
    if ! stage_revision "$REPO" "$REV" "$S" "$R.precompile"; then
        fail "the $REV_KIND revision does not build"; continue
    fi
    printf '%s\n' "$CLASSES"     > "$R.classes"
    printf '%s\n' "$TESTCLASSES" > "$R.testclasses"
    cp "$D/triggers.txt" "$R.triggers"

    # the project's own compiler level; the agent's compiler must not be more
    # permissive than the one that will judge the suite
    LEVEL=$(cat "$S/.c3/javac-level")
    echo "$LEVEL" > "$R.javac"

    # ---- the staged revision: no history, none of the fix's tests -----------
    for T in $TESTCLASSES; do
        rm -f "$S/$SRC_TESTS/$(echo "$T" | tr '.' '/').java"
    done

    if ! build_runner "$S" "$RUNNER" "$ROOT" > "$R.runner" 2>&1; then
        fail "the runner does not compile against the project's JUnit"; continue
    fi
    rm -f "$R.runner"

    JUNIT_HINT=$(awk -F'\t' '$2 == "junit-jupiter-api" || $2 == "junit" { print $3 }' "$S/.c3/deps.tsv" \
                   | head -1 | xargs -r basename)
    [ -n "$JUNIT_HINT" ] || { fail "the project declares no JUnit"; continue; }

    CLASS_LIST=$(printf '  - %s\n' $CLASSES)

    # ---- the working copy ---------------------------------------------------
    if [ "$ARM" = "f6" ] || [ "$ARM" = "m6" ]; then   # m4's working copy
        cp -a "$S/." "$W/"
        rm -rf "$W/.c3"
        find "$W/target" -mindepth 1 -maxdepth 1 ! -name classes -exec rm -rf {} +
        (cd "$W" && find . -type f \( \
              -iname 'RELEASE-NOTES*' -o -iname 'RELEASE_NOTES*' \
           -o -iname 'CHANGELOG' -o -iname 'CHANGELOG.*' \
           -o -iname 'CHANGES' -o -iname 'CHANGES.*' -o -iname 'changes.xml' \
           -o -iname 'release-history.xml' -o -iname 'upgradeto*.xml' \
           -o -iname 'NEWS' -o -iname 'NEWS.*' \
           -o -iname 'HISTORY' -o -iname 'HISTORY.*' \) -print -delete) > "$R.stripped"

        # the jars the tests need and the runner, copied in; Maven is not there
        mkdir -p "$W/_tools/lib" "$W/_tools/runner"
        cp -r "$RUNNER/." "$W/_tools/runner/"
        REL_CP=$(python3 - "$S" "$W" "$(run_cp "$S")" <<'EOF'
import os, shutil, sys
stage, work, cp = sys.argv[1:4]
out, seen, k = [], set(), 0
for e in cp.split(":"):
    if not e or e in seen:
        continue
    seen.add(e)
    if not os.path.isabs(e):
        if os.path.exists(os.path.join(work, e)):
            out.append(e)
    elif os.path.isfile(e):
        k += 1
        name = f"{k:02d}-{os.path.basename(e)}"
        shutil.copy(e, os.path.join(work, "_tools", "lib", name))
        out.append("_tools/lib/" + name)
print(":".join(out))
EOF
)
        cat > "$W/_tools/test.sh" <<EOS
#!/bin/bash
# Compiles every *AgentTest.java under $SRC_TESTS/ at the project's own
# compiler level, then runs the test classes named on the command line
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
javac -nowarn $LEVEL -Xlint:-options -encoding UTF-8 -cp "\$CP" -d _tools/out @_tools/.sources
echo "compiled OK"
if [ \$# -eq 0 ]; then
    set -- \$(sed -e 's|^$SRC_TESTS/||' -e 's|\\.java\$||' -e 's|/|.|g' _tools/.sources)
fi
java -cp "_tools/out:_tools/runner:\$CP" AgentTestRunner "\$@"
EOS
        chmod +x "$W/_tools/test.sh"
        TESTS_DIR="$SRC_TESTS"

        # m4's last sentence; in f6, the paragraph that replaces it
        ENDING=" Finish when all your tests
pass."
        if [ "$ARM" = "f6" ]; then
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
  Check them before writing.
- This project compiles with $LEVEL. Use only syntax valid at that
  level: no underscores in numeric literals, no diamond operator, no lambdas,
  no try-with-resources unless the level allows them.
- Assert on returned values and on observable state, not merely that no
  exception is thrown.
- Cover boundary and error cases, not just the happy path.
- Do not modify or create any file other than the test classes named above.

Compile and run your tests with ./_tools/test.sh, which compiles every
*AgentTest.java under $SRC_TESTS/ and runs it.$ENDING"
    fi

    # one timestamp for every file: nothing is newer than anything else
    find "$W" -exec touch -h -d '2020-01-01 00:00:00 UTC' {} + 2>/dev/null

    # ---- what a search of the working copy still finds ----------------------
    python3 - "$W" "$ISSUE" "$PULL" "$SHA" "$ID" "$R.triggers" "$SUBJECT" > "$R.leakscan" <<'EOF'
import os, re, sys
work, issue, pull, sha, wid, trig_file, subject = sys.argv[1:8]
names = sorted({l.strip().split(".")[-1] for l in open(trig_file) if l.strip()})
pats = [("commit", re.compile(re.escape(sha[:9]), re.I)),
        ("staging path", re.compile(r"gen-stage|" + re.escape(wid)))]
m = re.match(r"([A-Za-z]+)-(\d+)$", issue or "")
if m:
    pats.append(("issue id", re.compile(rf"\b{m.group(1)}[-_ ]?{m.group(2)}\b(?!\.[0-9x])", re.I)))
if pull:
    pats.append(("pull request", re.compile(rf"(?:#|pull/){pull}\b")))
# the commit's own words: its subject line without the issue and the pull request
words = re.sub(r"^\[?[A-Z]+-\d+\]?:?\s*", "", subject)
words = re.sub(r"\s*\(#\d+\)\.?\s*$", "", words).strip().rstrip(".")
if len(words) >= 20:
    pats.append(("commit subject", re.compile(re.escape(words), re.I)))
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
    # sent from a path that does not name the subject; a copy goes into the record
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
        echo "[$TAG] DRY RUN: the agent's scripts on a two-test class, then the developers' tests of the fix as the suite, on the $REV_KIND revision"
        # 1. the scripts the agent is given, on a class that needs nothing else
        C1=$(echo "$CLASSES" | head -1)
        PKG1="${C1%.*}"; CLS1="${C1##*.}"
        PROBE="$W/$TESTS_DIR/$(echo "$PKG1" | tr '.' '/')/${CLS1}AgentTest.java"
        mkdir -p "$(dirname "$PROBE")"
        cat > "$PROBE" <<EOF
package $PKG1;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

import org.junit.jupiter.api.Test;

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
        echo "[$TAG] agent's script: $(grep -E '^Tests run|^compiled OK' "$R.dry" | paste -sd' ' -), $(tail -1 "$R.dry")"
        # 2. developers' tests, renamed, as the suite: in both arms their test
        # classes for the fix, which in f6 are staged on the faulty revision
        python3 - "$MINING/$REPO" "$SHA" "$W/$TESTS_DIR" "$ARM" $TESTCLASSES <<'EOF'
import os, re, subprocess, sys
repo, rev, dest, arm = sys.argv[1:5]
classes = sys.argv[5:]
def renamed(simple):
    return (simple[:-4] if simple.endswith("Test") else simple) + "AgentTest"
table = {c.split(".")[-1]: renamed(c.split(".")[-1]) for c in classes}
for c in classes:
    path = "src/test/java/" + c.replace(".", "/") + ".java"
    shown = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True)
    if shown.returncode != 0:
        sys.exit(f"{path} is not in {rev}")
    text = shown.stdout.decode("utf-8", "replace")
    for old, new in table.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    pkg = c.rsplit(".", 1)[0].replace(".", "/") if "." in c else ""
    out = os.path.join(dest, pkg, table[c.split(".")[-1]] + ".java")
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

    python3 - "$R.meta.json" "$SUBJECT" <<EOF
import json, sys
json.dump({
    "subject": "$TAG", "arm": "$ARM", "working_copy": "$ID",
    "project": "$REPO", "commit_of_the_fix": "$SHA", "commit_subject": sys.argv[2],
    "revision": "$REV", "revision_kind": "$REV_KIND",
    "issue": "$ISSUE", "pull_request": "$PULL",
    "model": "$MODEL", "cli": "$CLI_VERSION", "tools": "$TOOLS",
    "model_reported_by_run": "${REPORTED%% *}", "cli_reported_by_run": "${REPORTED##* }",
    "commit": "$COMMIT",
    "max_turns": $MAX_TURNS, "max_budget_usd": $MAX_BUDGET,
    "flags": "--restricted --strict-mcp-config --disable-slash-commands --no-session-persistence --permission-mode acceptEdits --permission-prompts none",
    "environment": "env -i HOME PATH TZ=America/Los_Angeles LANG=C.UTF-8 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 DISABLE_AUTOUPDATER=1 CLAUDE_CODE_TMPDIR=<the run's own directory>",
    "settings": "bin/agent-sandbox.py settings", "tmpdir": "${RUN_TMP:-}",
    "javac_level": "$LEVEL", "junit": "$JUNIT_HINT",
    "java": "$JAVA_VERSION", "maven": "$MAVEN_VERSION",
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
            echo "Remaining subjects untouched; rerun this script later to resume."
            ABORTED=yes; break
        fi
        continue                     # no .status: this subject stays retryable
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

    # ---- acceptance, in the staged revision ---------------------------------
    SRCS=""
    for f in $WRITTEN; do
        mkdir -p "$S/$SRC_TESTS/$(dirname "$f")"
        cp "$W/$TESTS_DIR/$f" "$S/$SRC_TESTS/$f"
        SRCS="$SRCS $SRC_TESTS/${f#./}"
    done
    mkdir -p "$S/_acc/out"
    if ! (cd "$S" && c3_env javac -nowarn $LEVEL -Xlint:-options -encoding UTF-8 $DRY_SOURCEPATH \
            -cp "target/classes:$(cat "$S/.c3/cp-test")" -d _acc/out $SRCS) > "$R.compile" 2>&1; then
        fail "agent tests do not compile in the project"; continue
    fi

    RUN_CLASSES=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g' | tr '\n' ' ')
    CP_RUN="_acc/out:$RUNNER:$(run_cp "$S")"
    : > "$R.excluded"
    rm -f "$R.split"
    ACCEPTED=no
    for round in $(seq 1 $MAX_ROUNDS); do
        rm -f "$S/_acc/report.tsv"
        (cd "$S" && c3_env timeout "$RUN_TIMEOUT" java -cp "$CP_RUN" AgentTestRunner \
            --report "$S/_acc/report.tsv" --exclude "$R.excluded" $RUN_CLASSES) \
            > "$R.accepted.log" 2>&1 < /dev/null
        RC=$?
        cp "$S/_acc/report.tsv" "$R.accepted.tsv" 2>/dev/null || : > "$R.accepted.tsv"
        # the first run that ends with a report: round 1, or in f6 the run after a split
        if [ "$round" -eq 1 ] || [ ! -s "$R.first.tsv" ]; then
            cp "$R.accepted.log" "$R.first.log"; cp "$R.accepted.tsv" "$R.first.tsv"
        fi
        # in f6, a run that ends without the runner's report has not finished either
        WHY=""
        if [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then
            WHY="does not finish"
        elif [ "$ARM" = "f6" ] && [ ! -f "$S/_acc/report.tsv" ]; then
            WHY="ends without the runner's report (exit $RC)"
        fi
        if [ -n "$WHY" ]; then
            if [ "$ARM" = "f6" ] && [ ! -f "$R.split" ]; then
                # one class at a time; a class that does not finish, or ends
                # without a report, is left out whole
                : > "$R.split"
                for C in $RUN_CLASSES; do
                    rm -f "$S/_acc/class.tsv"
                    (cd "$S" && c3_env timeout "$RUN_TIMEOUT" java -cp "$CP_RUN" AgentTestRunner \
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
                fail "the suite does not finish on the $REV_KIND revision (${RUN_TIMEOUT}s)"
            else
                fail "the suite $WHY on the $REV_KIND revision"
            fi
            break
        fi
        [ "$RC" -eq 0 ] && { ACCEPTED=yes; break; }
        if [ "$RC" -eq 2 ]; then
            fail "the suite holds no test method"; break
        fi
        NEW=$(excluded_from "$R.accepted.tsv" | grep -vxF -f "$R.excluded")
        if [ -z "$NEW" ]; then
            fail "the suite fails on the $REV_KIND revision and nothing more can be left out (round $round)"
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
    # in f6, a class left out because it did not finish has no method counted
    if [ "$METHODS_TOTAL" -eq 0 ] && [ ! -s "$R.split" ]; then
        fail "the suite holds no test method"; continue
    fi
    # in f6 a suite whose every test fails is kept: its tests are its findings
    if [ "$ARM" != "f6" ] && [ "$LEFT_OUT" -ge "$METHODS_TOTAL" ]; then
        fail "every test failed on the $REV_KIND revision"; continue
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
    echo; echo "failed subjects:"
    echo "$FAILED" | while read -r s; do echo "  $(basename "$s" .status): $(cat "$s")"; done
fi

# 3: stopped early, on a usage limit or at the usage threshold
[ "$ABORTED" = "yes" ] && exit 3
exit 0

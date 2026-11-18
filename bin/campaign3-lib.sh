#!/bin/bash
#
# Third campaign: what the generator and the measurement share. Sourced, not run.
#
# A subject is a fix commit in one of the upstream repositories cloned under
# $MINING, mined and validated by bin/mine-postcutoff.sh. Its record is a
# directory (data/postcutoff/<tag> or data/postcutoff-first/<tag>) with
# meta.txt, classes.txt, testclasses.txt and triggers.txt.
#
# Nothing here uses the network or the repository's history: a revision is
# exported with `git archive`, built with Maven offline, and its tests are
# compiled and run with javac and bin/AgentTestRunner.java.

MINING=${MINING:-$HOME/code/mining}
RUN_TIMEOUT=${RUN_TIMEOUT:-1200}        # seconds for one run of a suite

# The environment a suite is compiled and run in, the agent's included: fixed
# time zone and locale, so that a result does not depend on the machine's.
C3_PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
c3_env() { env -i HOME="$HOME" PATH="$C3_PATH" TZ=America/Los_Angeles LANG=C.UTF-8 "$@"; }

# subject_field <subject dir> <key>          a field of meta.txt
subject_field() { grep "^$2=" "$1/meta.txt" | head -1 | cut -d= -f2-; }

# subject_dir <root> <tag>                   where the subject's record is
#
# The two corpora, unless SUBJECT_ROOTS names other directories: the pilot's
# subjects are outside both.
SUBJECT_ROOTS=${SUBJECT_ROOTS:-"data/postcutoff data/postcutoff-first"}
subject_dir() {
    local d r
    for r in $SUBJECT_ROOTS; do
        d="$1/$r/$2"
        [ -f "$d/meta.txt" ] && { echo "$d"; return 0; }
    done
    return 1
}

# stage_revision <repo> <revision> <dest> <log>
#
# Exports the revision into <dest> (which must not exist), compiles its
# production classes and resolves its dependencies. Leaves in <dest>/.c3/:
#   javac-level   the level the project compiles at, as javac options
#   deps.tsv      scope <tab> artifactId <tab> jar, in Maven's order
#   cp-test       the jars of every scope, colon-separated
#   cp-compile    the jars of scope compile and provided
#   cp-api        those of cp-compile that the compiled production classes
#                 refer to (jdeps): what a test needs besides the project to
#                 compile against its API
#   dropped       jars left out of all three: a released version of the
#                 project itself, which Maven resolves when a test library
#                 depends on it. The production classes come from the tree,
#                 and an older release beside them would show what changed.
# Returns non-zero if the export or the build fails.
stage_revision() {
    local repo=$1 rev=$2 dest=$3 log=$4
    mkdir -p "$dest" || return 1
    git -C "$MINING/$repo" archive "$rev" | tar -x -C "$dest" || return 1
    mkdir -p "$dest/.c3"
    # -X only to read the compiler's options; the debug lines are not kept
    (cd "$dest" && mvn -o -B -X compile \
            -Drat.skip=true -Dcheckstyle.skip=true -Dpmd.skip=true -Dspotbugs.skip=true \
            -Danimal.sniffer.skip=true -Denforcer.skip=true) > "$log.debug" 2>&1
    local rc=$?
    grep -v '^\[DEBUG\]' "$log.debug" | grep -v '^\s*$' > "$log"
    local level
    level=$(grep -o -E -- '--release [0-9]+' "$log.debug" | head -1)
    if [ -z "$level" ]; then
        local s t
        s=$(grep -o -E -- '-source [0-9.]+' "$log.debug" | head -1)
        t=$(grep -o -E -- '-target [0-9.]+' "$log.debug" | head -1)
        level="$s $t"
    fi
    rm -f "$log.debug"
    [ "$rc" -eq 0 ] || return 1
    [ -d "$dest/target/classes" ] || return 1
    level=$(echo "$level" | sed 's/  */ /g; s/^ //; s/ $//')
    [ -n "$level" ] || return 1
    echo "$level" > "$dest/.c3/javac-level"

    (cd "$dest" && mvn -o -q -B dependency:list -DoutputFile="$dest/.c3/deps.raw" \
            -DoutputAbsoluteArtifactFilename=true) >> "$log" 2>&1 || return 1
    python3 - "$dest/.c3/deps.raw" "$dest/.c3" "$dest/pom.xml" <<'EOF' || return 1
import os, sys
import xml.etree.ElementTree as ET
raw, out, pom = sys.argv[1:4]
root = ET.parse(pom).getroot()
ns = root.tag[:root.tag.index("}") + 1] if root.tag.startswith("{") else ""
own = root.find(ns + "artifactId").text.strip()
rows, dropped = [], []
for line in open(raw, errors="replace"):
    line = line.strip()
    if ":" not in line or ".jar" not in line:
        continue
    line = line.split(" -- ")[0].strip()
    jar = line[line.index(":/") + 1:] if ":/" in line else ""
    head = line[:line.index(":/")] if ":/" in line else line
    parts = head.split(":")
    if not jar or len(parts) < 5 or not os.path.isfile(jar):
        sys.exit(f"cannot read dependency line: {line}")
    if parts[1] == own:
        dropped.append(os.path.basename(jar))
        continue
    rows.append((parts[-1], parts[1], jar))
with open(os.path.join(out, "deps.tsv"), "w") as fh:
    for scope, artifact, jar in rows:
        fh.write(f"{scope}\t{artifact}\t{jar}\n")
open(os.path.join(out, "cp-test"), "w").write(":".join(j for _, _, j in rows) + "\n")
open(os.path.join(out, "cp-compile"), "w").write(
    ":".join(j for s, _, j in rows if s in ("compile", "provided")) + "\n")
open(os.path.join(out, "dropped"), "w").write("".join(d + "\n" for d in dropped))
EOF
    rm -f "$dest/.c3/deps.raw"

    # which of the compile-scope jars the production classes refer to
    local cpc used
    cpc=$(cat "$dest/.c3/cp-compile")
    : > "$dest/.c3/cp-api"
    if [ -n "$cpc" ]; then
        used=$(cd "$dest" && jdeps --multi-release base -s -cp "$cpc" target/classes 2>> "$log" \
                 | sed -n 's/^.* -> \(\/.*\.jar\)$/\1/p' | sort -u) || return 1
        if [ -n "$used" ]; then
            echo "$cpc" | tr ':' '\n' | grep -xF -f <(echo "$used") | paste -sd: - > "$dest/.c3/cp-api"
        fi
    fi
    return 0
}

# launcher_jar <staged dir>
#
# The junit-platform-launcher jar the runner needs: the project's own if it
# declares one, otherwise the one of the same version as its platform engine,
# from the local repository.
launcher_jar() {
    local d=$1 j v
    j=$(awk -F'\t' '$2 == "junit-platform-launcher" { print $3 }' "$d/.c3/deps.tsv" | head -1)
    if [ -z "$j" ]; then
        v=$(awk -F'\t' '$2 == "junit-platform-engine" { print $3 }' "$d/.c3/deps.tsv" | head -1)
        v=$(basename "$(dirname "$v")")
        j="$HOME/.m2/repository/org/junit/platform/junit-platform-launcher/$v/junit-platform-launcher-$v.jar"
        [ -f "$j" ] || return 1
        echo "$j"; echo "extra"
        return 0
    fi
    echo "$j"; echo "declared"
}

# build_runner <staged dir> <dest dir> <repository root>
#                                           compiles bin/AgentTestRunner.java
build_runner() {
    local d=$1 dest=$2 root=$3 lj
    # no pipe here: under pipefail a reader that stops early fails the writer
    lj=$(launcher_jar "$d") || return 1
    lj=${lj%%$'\n'*}
    mkdir -p "$dest"
    javac -nowarn --release 8 -Xlint:-options -encoding UTF-8 \
        -cp "$(cat "$d/.c3/cp-test"):$lj" -d "$dest" "$root/bin/AgentTestRunner.java"
}

# run_cp <staged dir>                       class path to run tests in <staged dir>,
#                                           relative to it, without the tests themselves
run_cp() {
    local d=$1 cp lj
    cp="target/classes"
    [ -d "$d/src/test/resources" ] && cp="$cp:src/test/resources"
    cp="$cp:$(cat "$d/.c3/cp-test")"
    lj=$(launcher_jar "$d") || return 1
    [ "${lj##*$'\n'}" = "extra" ] && cp="$cp:${lj%%$'\n'*}"
    echo "$cp"
}

# excluded_from <report.tsv>                the keys that failed, one per line
excluded_from() { awk -F'\t' '$1 == "FAILED" { print $3 }' "$1"; }

# count_methods <first report> <excluded file>   prints "<left out> <total>"
#
# Total: the test methods of the suite as written. Left out: those that failed
# on the fixed revision, and every method of a class that failed as a whole.
count_methods() {
    python3 - "$1" "$2" <<'EOF'
import sys
report, excl = sys.argv[1:3]
excluded = {l.strip() for l in open(excl) if l.strip()}
methods = [l.split("\t")[2] for l in open(report) if l.split("\t")[1] == "method"]
def out(key):
    cls = key.split("#")[0]
    if key in excluded:
        return True
    # the class itself, or a class it is nested in
    parts = cls.split("$")
    return any("$".join(parts[:i]) in excluded for i in range(1, len(parts) + 1))
print(sum(1 for m in methods if out(m)), len(methods))
EOF
}

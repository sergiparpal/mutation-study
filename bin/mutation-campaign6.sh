#!/bin/bash
#
# Sixth campaign: mutation score and line coverage of the archived suites,
# measured with PIT on the revision each suite was accepted on
# (data/campaign6/PROTOCOL.md, step 4).
#
# The fifth campaign's bin/mutation-campaign5.sh with the arms, the paths and
# the subjects' list changed, and one rule added: an f6 suite whose every test
# was left out at acceptance has no figure, since nothing of it passes on its
# own revision. Each suite is measured on its own revision: the fix commit in
# m6, its parent in f6. As in the fifth campaign, it is a step of the
# protocol, run after the measurement and before the analysis:
#
#     with PIT and its default mutators, on the classes the fix modifies,
#     with the suite as accepted
#
# For every subject of the list and every arm with a suite in <OUT>/suites:
#
#   - the suite's own revision is exported and built offline, as
#     bin/measure-campaign6.sh does it (stage_revision, bin/campaign3-lib.sh)
#   - the suite, as the agent wrote it, is compiled on its own against the
#     production classes and the project's test libraries, as there
#   - PIT mutates the classes the fix modifies (the subject's classes.txt),
#     with the classes nested in them, which are in the same source file, and
#     runs the suite against each mutant
#   - the test methods that failed at acceptance (the suite's excluded.txt)
#     are left out, as in the measurement, by bin/ExcludedTestsFilter.java,
#     which applies bin/AgentTestRunner.java's rule on the JUnit Platform that
#     PIT drives
#
# PIT 1.30.2 with pitest-junit5-plugin 1.2.3, on the JDK of the measurement and
# in its environment (c3_env: fixed time zone and locale). PIT's options are
# its defaults but for these:
#   --threads 8                  mutants are run eight at a time, as in the
#                                third campaign. A test that writes a file of
#                                a fixed name could be disturbed by another
#                                process; the third campaign's 56 suites had
#                                none.
#   --jvmArgs -Xmx1g             a ceiling on the heap of each process that runs
#                                tests, so that eight fit in the machine
#   --includeLaunchClasspath=false
#                                PIT's command line otherwise puts its own class
#                                path on the tests', and PIT's dependencies
#                                include a released Commons Lang (3.18.0). The
#                                tests' class path is the measurement's.
#   --failWhenNoMutations=false  a class with no mutant is recorded, not an error
#   --outputFormats XML, --timestampedReports=false, --verbosity NO_SPINNER
# PIT's own additions to its test processes are kept, -ea among them. It turns
# on Java's assert statements, which the measurement's runs leave off.
#
# WHAT IS RECORDED
#   Mutation score = detected / generated. Generated is every mutant PIT makes
#   in those classes, those no test reaches included. Detected is what PIT
#   counts as detected, and what its own score counts: KILLED, TIMED_OUT,
#   MEMORY_ERROR, RUN_ERROR, NON_VIABLE, and EQUIVALENT, which PIT does not
#   report without its commercial extensions. Each status is counted too.
#   Line coverage is what PIT reports for the same classes: lines of the
#   mutated classes that the suite executes, over those that hold code.
#
#   A suite has no figure (status `none`, with the reason) when, in f6, every
#   test was left out at acceptance, when it does not compile against its own
#   revision, when PIT stops (it does so when a test
#   fails on the unmutated code; it is not allowed to skip such a test, since
#   the suite measured would then not be the suite as accepted), or when PIT
#   does not finish within PIT_TIMEOUT seconds.
#
#   The filter records each test method the platform asks it about, kept or
#   left out. bin/analyze-campaign6.py compares the methods kept with the
#   methods the measurement ran on the suite's own revision, suite by suite.
#
# Per suite, in <OUT>/mutation/:
#   <subject>.<arm>.pit.log            what PIT printed
#   <subject>.<arm>.mutations.xml.xz   PIT's record of each mutant
#   <subject>.<arm>.tests              the filter's record, sorted, once per key
#   <subject>.<arm>.compile.log        javac
#   <subject>.<arm>.row                the row of mutation.csv
# and <OUT>/mutation/mutation.csv, one row per subject and arm.
#
# A suite that has a .row is not measured again (FORCE=1 to redo).
#
# PIT's jars are fetched once from Maven Central, by Maven, into PIT_DIR, and
# each is checked against the SHA-256 below before every run. Nothing else
# uses the network.
#
# Usage:
#   ./bin/mutation-campaign6.sh                      # data/campaign6
#   ONLY="commons-csv-b5940a642" ./bin/mutation-campaign6.sh
#   DRY=1 OUT=/tmp/dry ./bin/mutation-campaign6.sh /tmp/subjects.txt
#       the suites of a dry run of the generator: developers' own tests,
#       which are not self-contained, so the revision's test sources are on
#       the compiler's source path, as in the measurement's dry run

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
# the fourth campaign's records, reused as they are, and the pool's clones;
# the library reads both when it is sourced
SUBJECT_ROOTS=${SUBJECT_ROOTS:-data/campaign4/subjects}
MINING=${MINING:-$HOME/code/mining-pool}
. "$ROOT/bin/campaign3-lib.sh"
export TZ=America/Los_Angeles

OUT=${OUT:-data/campaign6}
SUBJECTS=${1:-data/campaign6/subjects.txt}
ONLY=${ONLY:-}
FORCE=${FORCE:-}
DRY=${DRY:-}
ARMS=${ARMS:-"f6 m6"}
STAGE_ROOT=${STAGE_ROOT:-$HOME/.cache/gen-stage}
PIT_VERSION=1.30.2
PIT_JUNIT5_VERSION=1.2.3
PIT_DIR=${PIT_DIR:-$HOME/.cache/pit-$PIT_VERSION}
PIT_THREADS=8
PIT_TIMEOUT=${PIT_TIMEOUT:-7200}

case "$OUT" in /*) OUT_ABS=$OUT ;; *) OUT_ABS=$ROOT/$OUT ;; esac
case "$SUBJECTS" in /*) ;; *) SUBJECTS=$ROOT/$SUBJECTS ;; esac
SUITES=$OUT_ABS/suites
MUT=$OUT_ABS/mutation

# What Maven resolves for pitest-command-line 1.30.2 and pitest-junit5-plugin
# 1.2.3 at runtime scope, and nothing else.
PIT_JARS="88fbda4b912596b9f56e8e12e580cc954bacfb51776ecfddd3e18fc1cf56dc4c  antlr-2.7.7.jar
5fe3b469b8646e5bc53a897840952d63b712d4923d2a7a26aebc585f1fec7676  asm-9.11.jar
a1421c20978ca0a330f241b17923a751a23fb1c9423fda1aba7591bb086b01d8  asm-analysis-9.11.jar
fcff37e6a0227a9f5ee81a7c07f51249307fa15889b56a359ae6f773c164c22b  asm-commons-9.11.jar
da8ad24d0bf7efb0674a906f59a7d441692b641718371f3bce6762b191a169fd  asm-tree-9.11.jar
d5a23a677f31b8a7d2419895906e1fcbd9ac995beffb20944c8610c1bc377609  asm-util-9.11.jar
4eeeae8d20c078abb64b015ec158add383ac581571cddc45c68f0c9ae0230720  commons-lang3-3.18.0.jar
121fce2282910c8f0c3ba793a5436b31beb710423cbe2d574a3fb7a73c508e92  commons-text-1.14.0.jar
26c5856e954b5f864db76f13b86919b59c6eecf9fd930b96baa8884626baf2f5  jopt-simple-4.9.jar
8f142c43e6f5f2d26baae4f317fc6c37a4b4b765b30481f21db721b89f15ee81  pitest-1.30.2.jar
e2bbe643656f87893c1568809f1cb343a3816bfe3c367bd83bc181de9532ccbc  pitest-command-line-1.30.2.jar
775ccf7d2d99f5fa99baecd3fa9fd84fecf14132d63cfef22ff81e409d73a34c  pitest-entry-1.30.2.jar
434bd857d2a926b6bf1742d8d86a40391b2094af72ea6ece5de4b85dae1f962d  pitest-html-report-1.30.2.jar
d3e2fcc8db5fd52c0c4ac2fe0d937e64da3df39b657093a1581b5fd463f9be64  pitest-junit5-plugin-1.2.3.jar
f66ce72e965e5301cb0f020e54d2ba6ad76feb91b3cbfc30dbbf00c06a6df6d7  stringtemplate-3.2.1.jar"

command -v mvn   >/dev/null || { echo "mvn not on PATH"; exit 1; }
command -v javac >/dev/null || { echo "javac not on PATH (install a JDK)"; exit 1; }
command -v xz    >/dev/null || { echo "xz not on PATH"; exit 1; }
[ -f "$SUBJECTS" ] || { echo "subject list not found: $SUBJECTS"; exit 1; }
[ -d "$SUITES" ] || { echo "no suites under $SUITES"; exit 1; }
mkdir -p "$MUT" "$STAGE_ROOT"

fetch_pit() {
    local t
    t=$(mktemp -d "$STAGE_ROOT/pit-fetch-XXXXXXXX") || return 1
    cat > "$t/pom.xml" <<EOF
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>local.study</groupId>
  <artifactId>pit-fetch</artifactId>
  <version>1</version>
  <packaging>pom</packaging>
  <dependencies>
    <dependency><groupId>org.pitest</groupId><artifactId>pitest-command-line</artifactId><version>$PIT_VERSION</version></dependency>
    <dependency><groupId>org.pitest</groupId><artifactId>pitest-junit5-plugin</artifactId><version>$PIT_JUNIT5_VERSION</version></dependency>
  </dependencies>
</project>
EOF
    (cd "$t" && mvn -B -q dependency:copy-dependencies -DoutputDirectory="$PIT_DIR" -DincludeScope=runtime)
    local rc=$?
    rm -rf "$t"
    return $rc
}

# every jar listed, with its hash, and no other
check_pit() {
    [ -d "$PIT_DIR" ] || return 1
    (cd "$PIT_DIR" && echo "$PIT_JARS" | sha256sum --check --quiet --strict -) || return 1
    [ "$(find "$PIT_DIR" -maxdepth 1 -name '*.jar' | wc -l)" -eq "$(echo "$PIT_JARS" | wc -l)" ]
}

if ! check_pit; then
    if [ -d "$PIT_DIR" ] && [ -n "$(ls -A "$PIT_DIR")" ]; then
        echo "$PIT_DIR holds something other than the jars listed in this script"; exit 1
    fi
    echo "fetching PIT $PIT_VERSION into $PIT_DIR"
    fetch_pit || { echo "could not fetch PIT"; exit 1; }
    check_pit || { echo "the jars fetched are not the ones listed in this script"; exit 1; }
fi
PIT_CP=$(echo "$PIT_JARS" | awk -v d="$PIT_DIR" '{ print d "/" $2 }' | paste -sd: -)

# row <file> <subject> <arm> <status> <note> <pit dir> <pit log> <tests file> <excluded file> <seconds>
row() {
    python3 - "$@" <<'EOF'
import csv, os, re, sys
import xml.etree.ElementTree as ET
out, tag, arm, status, note, pit, log, tests, excluded, seconds = sys.argv[1:11]
STATUSES = ("KILLED", "TIMED_OUT", "MEMORY_ERROR", "RUN_ERROR", "NON_VIABLE", "EQUIVALENT",
            "SURVIVED", "NO_COVERAGE", "NOT_STARTED", "STARTED")
counts = dict.fromkeys(STATUSES, 0)
generated = detected = 0
covered = total = ""
xml = os.path.join(pit, "mutations.xml")
if status == "ok":
    for m in ET.parse(xml).getroot().iter("mutation"):
        generated += 1
        counts[m.get("status")] = counts.get(m.get("status"), 0) + 1
        detected += m.get("detected") == "true"
    text = open(log, errors="replace").read()
    lc = re.search(r"Line Coverage \(for mutated classes only\): (\d+)/(\d+)", text)
    if lc:
        covered, total = lc.group(1), lc.group(2)
    elif generated == 0:
        covered, total = "0", "0"
    else:
        status, note = "none", "PIT printed no line coverage"
    g = re.search(r">> Generated (\d+) mutations Killed (\d+) ", text)
    if generated and not (g and int(g.group(1)) == generated and int(g.group(2)) == detected):
        status, note = "none", "PIT's statistics do not match its XML report"
    if counts["NOT_STARTED"] or counts["STARTED"]:
        status, note = "none", "mutants left unfinished"
kept, left = set(), set()
if os.path.exists(tests):
    for line in open(tests, errors="replace"):
        s, _, key = line.rstrip("\n").partition("\t")
        if "#" in key:
            (kept if s == "kept" else left).add(key)
want = {l.strip() for l in open(excluded) if l.strip()}
missing = want - left
if status == "ok" and missing:
    status, note = "none", f"{len(missing)} key(s) of excluded.txt never met by the filter"
with open(out, "w", newline="") as fh:
    csv.writer(fh, lineterminator="\n").writerow(
        [tag, arm, status, note, generated, detected]
        + [counts[s] for s in STATUSES[:8]]
        + [covered, total, len(kept), len(left), len(want), seconds])
EOF
}

HEADER="subject,arm,status,note,generated,detected,killed,timed_out,memory_error,run_error,non_viable,equivalent,survived,no_coverage,lines_covered,lines_total,methods_kept,methods_left_out,keys_excluded,seconds"

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
        if [ -f "$MUT/$TAG.$ARM.row" ] && [ -z "$FORCE" ]; then continue; fi
        TODO="$TODO $ARM"
    done
    [ -z "$TODO" ] && continue

    D=$(subject_dir "$ROOT" "$TAG") || { echo "[$TAG] no record of this subject"; exit 1; }
    REPO=$(subject_field "$D" project)
    SHA=$(subject_field "$D" sha)
    # each class the fix modifies, and the classes nested in it
    TARGETS=$(grep . "$D/classes.txt" | sed 's/.*/&,&$*/' | paste -sd, -)
    [ -n "$TARGETS" ] || { echo "[$TAG] classes.txt is empty"; exit 1; }

    T=$(mktemp -d "$STAGE_ROOT/mutation-XXXXXXXX")

    for ARM in $TODO; do
        # the suite's own revision: the fix commit in m6, its parent in f6
        if [ "$ARM" = "f6" ]; then REV="$SHA~1"; KIND=faulty; else REV="$SHA"; KIND=fixed; fi
        F="$T/$KIND"
        echo "[$TAG] staging the $KIND revision"
        if ! stage_revision "$REPO" "$REV" "$F" "$T/$KIND.build.log"; then
            echo "[$TAG] the $KIND revision does not build"; cp "$T/$KIND.build.log" "$MUT/$TAG.$KIND.build.log"
            rm -rf "$T"; exit 1
        fi
        LJ=$(launcher_jar "$F") || { echo "[$TAG] no junit-platform-launcher"; rm -rf "$T"; exit 1; }
        LJ_PATH=${LJ%%$'\n'*}
        LJ_KIND=${LJ##*$'\n'}
        mkdir -p "$T/filter-$ARM/META-INF/services"
        if ! javac -nowarn --release 8 -Xlint:-options -encoding UTF-8 \
                -cp "$(cat "$F/.c3/cp-test"):$LJ_PATH" -d "$T/filter-$ARM" "$ROOT/bin/ExcludedTestsFilter.java" > "$T/filter.log" 2>&1; then
            echo "[$TAG] the filter does not compile"; cat "$T/filter.log"; rm -rf "$T"; exit 1
        fi
        echo ExcludedTestsFilter > "$T/filter-$ARM/META-INF/services/org.junit.platform.launcher.PostDiscoveryFilter"

        P="$MUT/$TAG.$ARM"
        rm -f "$P.pit.log" "$P.mutations.xml.xz" "$P.tests" "$P.compile.log" "$P.row"
        SUITE="$T/suite-$ARM"
        mkdir -p "$SUITE"
        tar -xjf "$SUITES/${TAG}-${ARM}.tar.bz2" -C "$SUITE"
        [ -f "$SUITE/excluded.txt" ] || : > "$SUITE/excluded.txt"
        WRITTEN=$(cd "$SUITE" && find . -name '*AgentTest.java' | sort)
        TESTS=$(echo "$WRITTEN" | sed 's|^\./||; s|\.java$||; s|/|.|g; s/.*/&,&$*/' | paste -sd, -)
        SRCS=""
        for f in $WRITTEN; do SRCS="$SRCS $SUITE/${f#./}"; done

        STATUS=ok; NOTE=""; SECS=0
        mkdir -p "$F/_m-$ARM" "$T/pit-$ARM"
        # in f6, a suite whose every test was left out at acceptance: nothing to run
        if [ "$ARM" = "f6" ] && awk '{ exit !($1 >= $2) }' "$OUT_ABS/runs-$ARM/$TAG.pruned" 2>/dev/null; then
            STATUS=none; NOTE="every test was left out at acceptance"
        elif ! (cd "$F" && c3_env javac -nowarn $(cat "$F/.c3/javac-level") -Xlint:-options -encoding UTF-8 \
                ${DRY:+-sourcepath src/test/java} \
                -cp "target/classes:$(cat "$F/.c3/cp-test")" -d "_m-$ARM" $SRCS) > "$P.compile.log" 2>&1; then
            STATUS=none; NOTE="does not compile against its own revision"
        fi
        if [ "$STATUS" = ok ]; then
            CPL="$F/_m-$ARM,$F/target/classes"
            [ -d "$F/src/test/resources" ] && CPL="$CPL,$F/src/test/resources"
            CPL="$CPL,$(tr ':' ',' < "$F/.c3/cp-test" | tr -d '\n')"
            [ "$LJ_KIND" = "extra" ] && CPL="$CPL,$LJ_PATH"
            CPL="$CPL,$T/filter-$ARM"
            : > "$T/tests-$ARM"
            SECONDS=0
            (cd "$F" && c3_env timeout "$PIT_TIMEOUT" java -cp "$PIT_CP" \
                org.pitest.mutationtest.commandline.MutationCoverageReport \
                --reportDir "$T/pit-$ARM" --targetClasses "$TARGETS" --targetTests "$TESTS" \
                --sourceDirs src/main/java --classPath "$CPL" --includeLaunchClasspath=false \
                --mutators DEFAULTS --threads "$PIT_THREADS" \
                --jvmArgs "-Xmx1g,-Dc3.exclude=$SUITE/excluded.txt,-Dc3.report=$T/tests-$ARM" \
                --outputFormats XML --timestampedReports=false --failWhenNoMutations=false \
                --verbosity NO_SPINNER) > "$P.pit.log" 2>&1 < /dev/null
            RC=$?; SECS=$SECONDS
            case "$RC" in
                0) [ -f "$T/pit-$ARM/mutations.xml" ] || { STATUS=none; NOTE="PIT wrote no report"; } ;;
                124|137) STATUS=none; NOTE="PIT did not finish within $PIT_TIMEOUT seconds" ;;
                *) STATUS=none
                   NOTE=$(grep -m1 -E 'did not pass without mutation|Exception|ERROR' "$P.pit.log" | cut -c1-200)
                   NOTE="PIT stopped (status $RC)${NOTE:+: $NOTE}" ;;
            esac
            sort -u "$T/tests-$ARM" > "$P.tests"
            [ -f "$T/pit-$ARM/mutations.xml" ] && xz -9 -c "$T/pit-$ARM/mutations.xml" > "$P.mutations.xml.xz"
        fi
        row "$P.row" "$TAG" "$ARM" "$STATUS" "$NOTE" "$T/pit-$ARM" "$P.pit.log" "$P.tests" "$SUITE/excluded.txt" "$SECS"
        python3 - "$P.row" <<'EOF'
import csv, sys
r = next(csv.reader(open(sys.argv[1])))
tag, arm, status, note, gen, det = r[:6]
cov, tot = r[14], r[15]
score = f"{100 * int(det) / int(gen):.1f}%" if status == "ok" and int(gen) else "-"
lines = f"{100 * int(cov) / int(tot):.1f}%" if status == "ok" and tot not in ("", "0") else "-"
print(f"[{tag}] {arm}  {status:4}  mutants {gen:>5}  detected {det:>5}  score {score:>6}  lines {lines:>6}"
      f"  {r[19]}s{'  (' + note + ')' if note else ''}")
EOF
    done
    rm -rf "$T"
done < "$SUBJECTS"

{
    echo "$HEADER"
    while read -r TAG _rest; do
        TAG=$(echo "${TAG:-}" | tr -d '[:space:]')
        [ -z "$TAG" ] && continue
        case "$TAG" in \#*) continue ;; esac
        for ARM in f6 m6; do
            if [ -f "$MUT/$TAG.$ARM.row" ]; then cat "$MUT/$TAG.$ARM.row"; fi
        done
    done < "$SUBJECTS"
} > "$MUT/mutation.csv"

#!/bin/bash
#
# Line coverage of Csv-4's seven suites measured with Cobertura, measured again
# with JaCoCo beside it.
#
# WHY
# ---
# Defects4J measures line coverage with Cobertura 2.0.3. In CSVParser, the class
# Csv-4's fix changes, Cobertura gives no line counter to the constructor nor to
# any method that follows parse(URL, Charset, CSVFormat) in the class, so their
# lines read as never executed whatever a suite runs. The cause is a conditional
# inside two nested constructor calls in that method, and no other class of the
# sample is affected (bin/check-cobertura-instrumentation.py). Csv-4's suites
# were credited with 21 to 28 of CSVParser's 100 lines in the first, second and
# seventh campaigns.
#
# WHAT THIS DOES
# --------------
# It runs Defects4J's coverage step again for each suite, as its campaign ran
# it, with JaCoCo's agent attached to every JVM the step starts
# (JAVA_TOOL_OPTIONS). The agent is limited to CSVParser and its inner classes
# and dumps the classes it instruments, so that what it recorded is read against
# the bytes that ran. Nothing in the Defects4J installation is changed. Over the
# lines of Cobertura's own report of the run, a line counts as executed if
# Cobertura recorded a hit or JaCoCo saw one of its instructions run. Cobertura
# records no hit that did not happen. JaCoCo leaves out a line whose only call
# throws, which Cobertura counts when the line starts.
#
#   - The first and second campaigns' archives (data/agent-suites/,
#     data/campaign2/suites/) are run by run_coverage.pl as
#     bin/analyze-agent-suites.sh runs it.
#   - The seventh campaign measured archives that bin/mutation-campaign7.sh
#     builds from data/campaign7/suites/ and deletes once measured. They are
#     built again by that script, run from a copy of bin/ in which
#     mutation-campaign7.sh has one more line, which keeps the archive
#     (keep-archive.patch). Its mutation step is skipped, and the archives are
#     then measured with its run_coverage.pl call.
#   - EvoSuite's runtime defines the class under test in a class loader of its
#     own, which the agent does not instrument. For that suite,
#     `defects4j coverage -s` runs twice in one working copy: as it is, and then
#     with Cobertura's instrumented CSVParser classes replaced by JaCoCo's
#     offline instrumentation of the same classes. Defects4J reuses the
#     instrumented directory when it is up to date, and the script checks that
#     it did.
#
# Every run's Cobertura figure must equal the one its campaign's table records,
# or the script stops. Two checks:
#   check-Csv-7f-m2       Csv-7's CSVParser, which Cobertura instruments fully:
#                         the count must equal Cobertura's
#   check-offline-agent   the first campaign's M suite measured the way
#                         EvoSuite's is: the count must equal its run with the
#                         agent
#
# Output in data/csv4-coverage/:
#   corrected.tsv         the seven suites: the table and row their figure is
#                         recorded in, Cobertura's figure as recorded and as
#                         measured again, JaCoCo's, and the count described above
#   checks.tsv            the two checks
#   lines/<run>.tsv       line by line: class, line, Cobertura's hits, and JaCoCo
#                         (1 ran, 0 did not, - no code in JaCoCo's view)
#   keep-archive.patch    the one added line
#
# The campaigns' tables stay as they are. bin/report-figures.py applies
# corrected.tsv to a copy of them, and prints them as recorded with
# --as-recorded.
#
# Needs Defects4J v3.0.1-7-g8c16da82 at $D4J_HOME (default ~/defects4j), Java 11
# and Maven 3.9+. JaCoCo and ASM are fetched once from Maven Central into
# $JACOCO_DIR, by Maven, and checked against the hashes written here. No model
# is run. Takes about 15 minutes.
#
# Usage:
#   ./bin/remeasure-csv4-coverage.sh

set -euo pipefail
shopt -s inherit_errexit

ROOT=$(cd "$(dirname "$0")/.." && pwd)
D4J_HOME=${D4J_HOME:-$HOME/defects4j}
D4J_BIN=$D4J_HOME/framework/bin
D4J_REVISION=v3.0.1-7-g8c16da82
OUT=$ROOT/data/csv4-coverage
INCLUDES='org.apache.commons.csv.CSVParser:org.apache.commons.csv.CSVParser$*'

JACOCO_VERSION=0.8.16
ASM_VERSION=9.11.1
JACOCO_DIR=${JACOCO_DIR:-$HOME/.cache/jacoco-$JACOCO_VERSION}
JACOCO_JARS="37ae2f374ad77e85c59c6e5b46565226c3ac3cb460ac19de0bcb844ac2f43e33  org.jacoco.agent-$JACOCO_VERSION-runtime.jar
5d2db23c5d698e5645f47f07d1b6019ccd03e15cc933d60d1d4e798ac6bd1f84  org.jacoco.core-$JACOCO_VERSION.jar
ae4e6e10d59d0a1500317764b21881ad883f8550e33c66e6142f7032c6fb566c  asm-$ASM_VERSION.jar
6a5095ec53726156a78b2cd2efd45bc4e877754eca7c234f61224a53d6bfa661  asm-commons-$ASM_VERSION.jar
2b15c3c1b288a9fad3bb2cd6d988ba9521554914ed1f2a2029141fa3f483154a  asm-tree-$ASM_VERSION.jar"

[ -x "$D4J_BIN/run_coverage.pl" ] || { echo "no Defects4J under $D4J_HOME (set D4J_HOME)"; exit 1; }
REV=$(git -C "$D4J_HOME" describe --tags 2>/dev/null || true)
[ "$REV" = "$D4J_REVISION" ] || { echo "Defects4J ${REV:-unknown}: the measurements used $D4J_REVISION"; exit 1; }
JV=$(java -version 2>&1 | head -1 | sed -nE 's/.*version "([0-9]+)[."].*/\1/p')
[ "$JV" = 11 ] || { echo "java ${JV:-?}: the measurements used Java 11"; exit 1; }
for c in mvn javac python3; do command -v "$c" >/dev/null || { echo "$c not found"; exit 1; }; done

check_jacoco() {
    [ -d "$JACOCO_DIR" ] || return 1
    (cd "$JACOCO_DIR" && echo "$JACOCO_JARS" | sha256sum --check --quiet --strict -) || return 1
    [ "$(find "$JACOCO_DIR" -maxdepth 1 -name '*.jar' | wc -l)" -eq "$(echo "$JACOCO_JARS" | wc -l)" ]
}
fetch_jacoco() {
    local t
    t=$(mktemp -d) || return 1
    cat > "$t/pom.xml" <<EOF
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>local</groupId>
  <artifactId>jacoco-fetch</artifactId>
  <version>1</version>
  <dependencies>
    <dependency><groupId>org.jacoco</groupId><artifactId>org.jacoco.core</artifactId><version>$JACOCO_VERSION</version></dependency>
    <dependency><groupId>org.jacoco</groupId><artifactId>org.jacoco.agent</artifactId><version>$JACOCO_VERSION</version><classifier>runtime</classifier></dependency>
  </dependencies>
</project>
EOF
    mkdir -p "$JACOCO_DIR"
    (cd "$t" && mvn -B -q dependency:copy-dependencies -DoutputDirectory="$JACOCO_DIR" -DincludeScope=runtime) || { rm -rf "$t"; return 1; }
    rm -rf "$t"
}
if ! check_jacoco; then
    if [ -d "$JACOCO_DIR" ] && [ -n "$(ls -A "$JACOCO_DIR")" ]; then
        echo "$JACOCO_DIR holds something other than the jars listed in this script"; exit 1
    fi
    echo "fetching JaCoCo $JACOCO_VERSION into $JACOCO_DIR"
    fetch_jacoco || { echo "could not fetch JaCoCo"; exit 1; }
    check_jacoco || { echo "the jars fetched are not the ones listed in this script"; exit 1; }
fi
AGENT=$JACOCO_DIR/org.jacoco.agent-$JACOCO_VERSION-runtime.jar
JCP=$(echo "$JACOCO_JARS" | awk -v d="$JACOCO_DIR" '$2 !~ /agent/ { print d "/" $2 }' | paste -sd: -)

export TZ=America/Los_Angeles
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/jl"
javac -nowarn -cp "$JCP" -d "$WORK/jl" "$ROOT/bin/JacocoLines.java"
jacoco_lines() { java -cp "$WORK/jl:$JCP" JacocoLines "$@"; }

rm -rf "$OUT/lines" "$OUT/corrected.tsv" "$OUT/checks.tsv" "$OUT/keep-archive.patch"
mkdir -p "$OUT/lines"

# recorded <table> <key columns> <key>  ->  "lines_total lines_covered" of that row
recorded() {
    python3 - "$ROOT/$1" "$2" "$3" <<'EOF'
import csv, sys
path, cols, key = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
rows = [r for r in csv.DictReader(open(path, newline="")) if [r[c] for c in cols] == key]
if len(rows) != 1:
    sys.exit(f"{path}: {len(rows)} rows for {key}")
print(rows[0]["lines_total"], rows[0]["lines_covered"])
EOF
}

# merge <run> <cobertura xml> <JacocoLines output>  ->  lines/<run>.tsv; prints "lines cobertura jacoco union"
merge() {
    python3 - "$1" "$2" "$3" "$OUT/lines/$1.tsv" <<'EOF'
import sys, xml.etree.ElementTree as ET
run, xml_path, jac_path, out = sys.argv[1:5]
jac = {}
for line in open(jac_path):
    f = line.rstrip("\n").split("\t")
    if f[0] == "NO-MATCH":
        sys.exit(f"{run}: JaCoCo's data are for other bytes of {f[1]}")
    if f[0] == "LINE":
        jac[(f[1], int(f[2]))] = f[3] == "1"
rows, n, cob, jc, union = [], 0, 0, 0, 0
for c in ET.parse(xml_path).iter("class"):
    name = c.get("name").replace(".", "/")
    lines = c.find("lines")
    for l in (lines.findall("line") if lines is not None else []):
        k, h = (name, int(l.get("number"))), int(l.get("hits"))
        j = jac.get(k)
        n += 1; cob += h > 0; jc += j is True; union += h > 0 or j is True
        rows.append((name, k[1], h, "-" if j is None else int(j)))
with open(out, "w") as fh:
    fh.write("class\tline\tcobertura_hits\tjacoco\n")
    for r in sorted(rows):
        fh.write("\t".join(map(str, r)) + "\n")
print(n, cob, jc, union)
EOF
}

# agent_run <run> <archive> [run_coverage.pl arguments]  ->  "lines cobertura jacoco union"
agent_run() {
    local run=$1 archive=$2 E x; shift 2
    E=$WORK/$run; mkdir -p "$E/d" "$E/out" "$E/tmp" "$E/dump"
    cp "$archive" "$E/d/"
    JAVA_TOOL_OPTIONS="-javaagent:$AGENT=destfile=$E/jacoco.exec,append=true,includes=$INCLUDES,classdumpdir=$E/dump" \
        "$D4J_BIN/run_coverage.pl" -p Csv -d "$E/d" -o "$E/out" -t "$E/tmp" "$@" > "$E/run.log" 2>&1 \
        || { echo "$run: run_coverage.pl failed" >&2; tail -5 "$E/run.log" >&2; return 1; }
    x=$(find "$E/out" -name '*.xml' -print -quit)
    [ -n "$x" ] || { echo "$run: no Cobertura report" >&2; return 1; }
    jacoco_lines lines "$E/jacoco.exec" "$E/dump" > "$E/jacoco.txt" || { echo "$run: JaCoCo's data do not match" >&2; return 1; }
    merge "$run" "$x" "$E/jacoco.txt"
}

# offline_run <run> <archive> <version>  ->  "lines cobertura jacoco union"
offline_run() {
    local run=$1 archive=$2 vid=$3 E WD f pairs=()
    E=$WORK/$run; WD=$E/wd; mkdir -p "$E"
    "$D4J_BIN/defects4j" checkout -p Csv -v "$vid" -w "$WD" > "$E/checkout.log" 2>&1
    "$D4J_BIN/defects4j" coverage -w "$WD" -s "$archive" > "$E/cobertura.log" 2>&1
    cp "$WD/coverage.xml" "$E/cobertura.xml"
    for f in "$WD"/target/classes/org/apache/commons/csv/CSVParser*.class; do
        pairs+=("$f=$WD/.classes_instrumented/org/apache/commons/csv/$(basename "$f")")
    done
    jacoco_lines instrument "${pairs[@]}"
    JAVA_TOOL_OPTIONS="-javaagent:$AGENT=destfile=$E/jacoco.exec,append=true,includes=none" \
        "$D4J_BIN/defects4j" coverage -w "$WD" -s "$archive" > "$E/jacoco-run.log" 2>&1
    javap -p "$WD/.classes_instrumented/org/apache/commons/csv/CSVParser.class" > "$E/javap.txt"
    grep -q 'jacocoInit' "$E/javap.txt" || { echo "$run: Defects4J instrumented the classes again" >&2; return 1; }
    jacoco_lines lines "$E/jacoco.exec" "$WD"/target/classes/org/apache/commons/csv/CSVParser*.class > "$E/jacoco.txt" \
        || { echo "$run: JaCoCo's data do not match" >&2; return 1; }
    merge "$run" "$E/cobertura.xml" "$E/jacoco.txt"
}

printf 'run\ttable\tkey_columns\tkey\tlines_total\trecorded\tcobertura\tjacoco\tcorrected\tmethod\n' > "$OUT/corrected.tsv"
# result <run> <table> <key columns> <key> <method> <lines cobertura jacoco union>
result() {
    local run=$1 table=$2 cols=$3 key=$4 method=$5 n=$6 cob=$7 jac=$8 uni=$9 rec
    rec=$(recorded "$table" "$cols" "$key")
    [ "$rec" = "$n $cob" ] || { echo "$run: Cobertura measured $n $cob again, the table records $rec"; exit 1; }
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$run" "$table" "$cols" "$key" "$n" "${rec#* }" "$cob" "$jac" "$uni" "$method" \
        >> "$OUT/corrected.tsv"
    echo "$run: $n lines; Cobertura $cob (as recorded), JaCoCo $jac, either $uni"
}

C1=data/agent-metrics-final.csv
C2=data/campaign2/results/agent-metrics.csv
C7=data/campaign7/mutation/mutation.csv
K12=project_id,version_id,test_suite_source

for arm in agent spec; do
    R=$(agent_run "c1-$arm" "$ROOT/data/agent-suites/Csv-4f-$arm.1.tar.bz2")
    result "c1-$arm" "$C1" "$K12" "Csv,4f,$arm" agent $R
done
R=$(offline_run c1-evosuite "$ROOT/data/agent-suites/Csv-4f-evosuite.1.tar.bz2" 4f)
result c1-evosuite "$C1" "$K12" Csv,4f,evosuite offline $R
for arm in m2 s2; do
    R=$(agent_run "c2-$arm" "$ROOT/data/campaign2/suites/Csv-4f-$arm.1.tar.bz2")
    result "c2-$arm" "$C2" "$K12" "Csv,4f,$arm" agent $R
done

# ---- the seventh campaign's archives, built again by its own script -------------
OV=$WORK/c7root; C7OUT=$WORK/c7; KEEP=$WORK/keep
mkdir -p "$OV/bin" "$C7OUT/suites" "$C7OUT/runs-f7" "$C7OUT/runs-m7" "$KEEP"
for f in "$ROOT"/bin/*; do [ "$(basename "$f")" = mutation-campaign7.sh ] || ln -s "$f" "$OV/bin/"; done
python3 - "$ROOT/bin/mutation-campaign7.sh" "$OV/bin/mutation-campaign7.sh" <<'EOF'
import sys
src, dst = sys.argv[1:3]
s = open(src).read()
end = '        rm -rf "$A"\n    done\ndone < "$SUBJECTS"\n'
if s.count(end) != 1:
    sys.exit("mutation-campaign7.sh does not end as this script expects")
keep = '        [ -d "$A/d" ] && cp -a "$A/d" "$KEEP/$TAG.$ARM.d"\n'
open(dst, "w").write(s.replace(end, keep + end))
EOF
chmod +x "$OV/bin/mutation-campaign7.sh"
diff -u --label a/bin/mutation-campaign7.sh --label b/bin/mutation-campaign7.sh \
    "$ROOT/bin/mutation-campaign7.sh" "$OV/bin/mutation-campaign7.sh" > "$OUT/keep-archive.patch" || true
[ "$(grep -c '^+[^+]' "$OUT/keep-archive.patch" || true)" = 1 ] && [ "$(grep -c '^-[^-]' "$OUT/keep-archive.patch" || true)" = 0 ] \
    || { echo "expected exactly one added line in mutation-campaign7.sh"; exit 1; }
cp "$ROOT"/data/campaign7/suites/Csv-4-f7.tar.bz2 "$ROOT"/data/campaign7/suites/Csv-4-m7.tar.bz2 "$C7OUT/suites/"
cp "$ROOT"/data/campaign7/runs-f7/Csv-4.* "$C7OUT/runs-f7/"
cp "$ROOT"/data/campaign7/runs-m7/Csv-4.* "$C7OUT/runs-m7/"
grep -E '^Csv-4[[:space:]]' "$ROOT/data/campaign7/subjects.txt" > "$C7OUT/subjects.txt"
OUT=$C7OUT ONLY=Csv-4 NO_MUTATION="Gson-14 Gson-16 Csv-4" STAGE_ROOT=$WORK/stage KEEP=$KEEP \
    bash "$OV/bin/mutation-campaign7.sh" "$C7OUT/subjects.txt" > "$WORK/c7.log" 2>&1 \
    || { echo "mutation-campaign7.sh failed"; tail -5 "$WORK/c7.log"; exit 1; }
for arm in m7 f7; do
    case $arm in m7) v=4f ;; f7) v=4b ;; esac
    a=$KEEP/Csv-4.$arm.d/Csv-$v-$arm.1.tar.bz2
    [ -f "$a" ] || { echo "the $arm archive was not built: $(tail -2 "$WORK/c7.log")"; exit 1; }
    R=$(agent_run "c7-$arm" "$a" -f '*AgentTest.java')
    result "c7-$arm" "$C7" bug,arm "Csv-4,$arm" agent $R
done

# ---- the checks ----------------------------------------------------------------
printf 'check\twhat\texpected\tgot\tholds\n' > "$OUT/checks.tsv"
check() {   # <check> <what> <expected> <got>
    local h=no; [ "$3" = "$4" ] && h=yes
    printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$h" >> "$OUT/checks.tsv"
    echo "$1: expected $3, got $4"
    [ "$h" = yes ]
}
R=$(agent_run check-Csv-7f-m2 "$ROOT/data/campaign2/suites/Csv-7f-m2.1.tar.bz2")
read -r n cob jac uni <<< "$R"
[ "$(recorded "$C2" "$K12" Csv,7f,m2)" = "$n $cob" ] || { echo "check-Csv-7f-m2: Cobertura does not reproduce the table"; exit 1; }
OK=0
check check-Csv-7f-m2 "Csv-7's m2 suite: lines counted either way, against Cobertura's count" "$cob" "$uni" || OK=1
R=$(offline_run check-offline-agent "$ROOT/data/agent-suites/Csv-4f-agent.1.tar.bz2" 4f)
read -r n cob jac uni <<< "$R"
AGENT_UNION=$(awk -F'\t' '$1 == "c1-agent" { print $9 }' "$OUT/corrected.tsv")
check check-offline-agent "the first campaign's M suite measured offline, against its run with the agent" "$AGENT_UNION" "$uni" || OK=1
exit $OK

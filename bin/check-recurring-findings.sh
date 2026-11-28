#!/bin/bash
#
# The behaviours the find-faults runs named in more than one run, tried on the
# projects' latest releases.
#
# WHY
# ---
# The sixth and seventh campaigns count a test that fails on the faulty code
# and does not pass on the fix as a false alarm. Four behaviours were named by
# more than one run, and none of them is the fault of a subject:
#   - StopWatch.split() called twice without unsplit()         (f6: 3 runs)
#   - StrBuilder.equalsIgnoreCase(null) throwing               (f6: 2 runs)
#   - ExtendedMessageFormat not trimming a format name
#     followed by a space                                      (f6: 2 runs; f7: Lang-23)
#   - CSVFormat.withRecordSeparator(String) accepting
#     any string                                               (f7: Csv-14, Csv-15)
# Whether each is a bug at all was checked on 28 November 2026 against the
# projects' sources, histories and issue tracker (data/README.md, "The
# recurring findings, checked against the projects"). This script is the part
# of that check that runs code: what each behaviour does in the releases.
#
# WHAT THIS DOES
# --------------
# Fetches commons-lang3 3.22.0, commons-text 1.15.0 and commons-csv 1.14.1, the
# latest releases on 28 November 2026, with commons-io and commons-codec, which
# commons-csv needs. Maven fetches them from Maven Central, once, into
# $JARS_DIR, and they are checked against the hashes written here. The script
# then compiles bin/RecurringFindings.java against them and runs it.
#
# Output: data/recurring-findings.txt
#
# Needs Java 11 and Maven 3.9+. No model and no Defects4J.
#
# Usage:
#   ./bin/check-recurring-findings.sh

set -euo pipefail
shopt -s inherit_errexit

ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$ROOT/data/recurring-findings.txt
JARS_DIR=${JARS_DIR:-$HOME/.cache/recurring-findings-jars}
JARS="5c3881e4f556855e9c532927ee0c9dfde94cc66760d5805c031a59887070af5f  commons-codec-1.19.0.jar
32be0e1e76673092f5d12cb790bd2acb6c2ab04c4ea6efc69ea5ee17911c24fe  commons-csv-1.14.1.jar
df90bba0fe3cb586b7f164e78fe8f8f4da3f2dd5c27fa645f888100ccc25dd72  commons-io-2.20.0.jar
2ea88052c8662bf51874f4159467ba24b040b22dfd54d2596e11936896c76192  commons-lang3-3.22.0.jar
58d2da30f058512a1e7f914e39241deca4dff5c27a085b4ed2faa9e7208067f6  commons-text-1.15.0.jar"

for c in java javac mvn; do command -v "$c" >/dev/null || { echo "$c not found"; exit 1; }; done

check_jars() {
    [ -d "$JARS_DIR" ] || return 1
    (cd "$JARS_DIR" && echo "$JARS" | sha256sum --check --quiet --strict -) || return 1
    [ "$(find "$JARS_DIR" -maxdepth 1 -name '*.jar' | wc -l)" -eq "$(echo "$JARS" | wc -l)" ]
}
fetch_jars() {
    local t
    t=$(mktemp -d) || return 1
    cat > "$t/pom.xml" <<'EOF'
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>local</groupId>
  <artifactId>recurring-findings-fetch</artifactId>
  <version>1</version>
  <dependencies>
    <dependency><groupId>org.apache.commons</groupId><artifactId>commons-lang3</artifactId><version>3.22.0</version></dependency>
    <dependency><groupId>org.apache.commons</groupId><artifactId>commons-text</artifactId><version>1.15.0</version></dependency>
    <dependency><groupId>org.apache.commons</groupId><artifactId>commons-csv</artifactId><version>1.14.1</version></dependency>
  </dependencies>
</project>
EOF
    mkdir -p "$JARS_DIR"
    (cd "$t" && mvn -B -q dependency:copy-dependencies -DoutputDirectory="$JARS_DIR" -DincludeScope=runtime) || { rm -rf "$t"; return 1; }
    rm -rf "$t"
}
if ! check_jars; then
    if [ -d "$JARS_DIR" ] && [ -n "$(ls -A "$JARS_DIR")" ]; then
        echo "$JARS_DIR holds something other than the jars listed in this script"; exit 1
    fi
    echo "fetching the releases into $JARS_DIR"
    fetch_jars || { echo "could not fetch the releases"; exit 1; }
    check_jars || { echo "the jars fetched are not the ones listed in this script"; exit 1; }
fi
CP=$(echo "$JARS" | awk -v d="$JARS_DIR" '{ print d "/" $2 }' | paste -sd: -)

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
javac -nowarn -cp "$CP" -d "$WORK" "$ROOT/bin/RecurringFindings.java" 2>&1 | { grep -v '^Note:' || true; }
java -cp "$WORK:$CP" RecurringFindings > "$OUT"
echo "wrote ${OUT#$ROOT/}"

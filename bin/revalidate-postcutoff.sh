#!/bin/bash
# revalidate-postcutoff.sh <clones-dir> <list> <out-dir>
#
# Validates post-cutoff candidates under the subject contract of
# bin/mine-postcutoff.sh: with the parent's production code and the fix's test
# files, at least one test fails; with the fix commit, those tests pass. Same
# Maven command. Written on 2026-11-19 to count the candidates available for a
# larger corpus. Doing so showed that every rejection recorded for the two
# post-cutoff corpora gives the wrong reason (data/README.md, "Post-cutoff
# corpora"); its runs of those candidates are in data/postcutoff-revalidation/.
#
# <list> holds "<repo> <sha>" lines, and <clones-dir>/<repo> must be a clone of
# that upstream repository. The clone is reset and cleaned (git reset --hard,
# git clean -fdx) before every state: do not point it at a working copy.
# Several instances can run at once on separate clones if MAVEN_ARGS carries
# -Daether.syncContext.named.factory=file-lock
# -Daether.syncContext.named.nameMapper=file-gav, so that they can share the
# local Maven repository.
#
# Differences from bin/mine-postcutoff.sh:
#   - the clone is reset and cleaned before each state, so no file of one
#     candidate reaches the next;
#   - no cap on production files (their number is recorded in meta.txt);
#   - the trigger pattern also reads failures inside lambdas, errors with no
#     line in the test class, and logs with NUL bytes;
#   - on the parent, a test JVM that runs out of memory, or tests that do not
#     finish within LIMIT seconds, count as failing, and the status says so;
#   - a rejection says why the build stopped.
set -uo pipefail
CL=$1; LIST=$2; OUT=$3
# Hard wall-clock limit per Maven run. A fault can make a test loop forever on
# the parent, where JUnit's own timeout cannot interrupt a busy loop on the
# main thread; timeout(1) kills the build's whole process group, fork included.
LIMIT=${LIMIT:-600}
mkdir -p "$OUT"
fqcn() { echo "$1" | sed -E 's#^.*src/(main|test)/java/##; s#\.java$##; s#/#.#g'; }
fresh() { git -C "$1" reset -q --hard && git -C "$1" clean -fdxq; }
why() {   # reason a build failed without a failing test
    if grep -aq 'COMPILATION ERROR' "$1"; then echo "test sources do not compile"
    elif grep -aq 'maven-enforcer-plugin' "$1"; then echo "build stopped by the enforcer"
    else echo "build failed before any test failed"; fi
}
while read -r REPO SHA; do
    [ -z "${REPO:-}" ] && continue
    R=$CL/$REPO
    SHORT=$(git -C "$R" rev-parse --short=9 "$SHA" 2>/dev/null) || { echo "[$REPO $SHA] unknown commit"; continue; }
    D=$OUT/$REPO-$SHORT
    [ -f "$D/status" ] && continue
    mkdir -p "$D"
    FILES=$(git -C "$R" show --name-only --format= "$SHA" | grep -v '^$')
    PROD=$(grep 'src/main/java/.*\.java$' <<<"$FILES" || true)
    TESTS=$(grep 'src/test/java/.*\.java$' <<<"$FILES" || true)
    {
        echo "repo=$REPO"; echo "sha=$SHA"
        echo "date=$(git -C "$R" log -1 --format=%ad --date=short "$SHA")"
        echo "nprod=$(grep -c . <<<"$PROD")"; echo "ntest=$(grep -c . <<<"$TESTS")"
        echo "subject=$(git -C "$R" log -1 --format=%s "$SHA")"
    } > "$D/meta.txt"
    if [ -z "$PROD" ] || [ -z "$TESTS" ]; then echo "no production or no test change" > "$D/status"; continue; fi
    TEST_ARG=$(for f in $TESTS; do fqcn "$f"; done | sed 's|.*\.||' | paste -sd, -)

    # ---- parent state: parent production code + the fix's tests ---------
    fresh "$R"
    if ! git -C "$R" checkout -q --detach "$SHA~1" 2>/dev/null; then echo "cannot check out parent" > "$D/status"; continue; fi
    for f in $TESTS; do git -C "$R" checkout -q "$SHA" -- "$f" 2>/dev/null; done
    (cd "$R" && timeout -k 30 "$LIMIT" mvn test -Dtest="$TEST_ARG" -DfailIfNoTests=false) > "$D/buggy.log" 2>&1
    RC=$?
    HUNG=""; { [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; } && HUNG=1
    # -a: a test's output can hold NUL bytes, which make grep call the log binary.
    # [\w$]: a failure inside a lambda is reported as Class.lambda$name$N:line.
    # (?=[:( ]): an error with no line in the test class reads "Class.method » ...".
    grep -aoP '^\[ERROR\]\s+\K[\w$]+\.[\w$]+(?=[:( ])' "$D/buggy.log" | sort -u > "$D/triggers.txt"
    OOM=""
    if [ "$RC" -eq 0 ]; then echo "tests pass on the parent" > "$D/status"; continue; fi
    if [ -n "$HUNG" ]; then
        echo "(the parent's tests did not finish within ${LIMIT}s)" >> "$D/triggers.txt"
    elif [ ! -s "$D/triggers.txt" ]; then
        if grep -aq -E 'Java heap space|OutOfMemoryError' "$D/buggy.log"; then
            echo "(the test JVM ran out of memory)" > "$D/triggers.txt"; OOM=1
        else echo "parent: $(why "$D/buggy.log")" > "$D/status"; continue; fi
    fi

    # ---- fixed state: everything from the fix commit ---------------------
    fresh "$R"
    git -C "$R" checkout -q --detach "$SHA" 2>/dev/null || { echo "cannot check out fix" > "$D/status"; continue; }
    (cd "$R" && timeout -k 30 "$LIMIT" mvn test -Dtest="$TEST_ARG" -DfailIfNoTests=false) > "$D/fixed.log" 2>&1
    FRC=$?
    if [ "$FRC" -ne 0 ]; then
        if [ "$FRC" -eq 124 ] || [ "$FRC" -eq 137 ]; then echo "tests do not finish on the fix" > "$D/status"
        elif grep -aq '^\[ERROR\] Tests run:.*Failures' "$D/fixed.log"; then echo "tests fail on the fix" > "$D/status"
        else echo "fix: $(why "$D/fixed.log")" > "$D/status"; fi
        continue
    fi
    if [ -n "$HUNG" ]; then echo "ok, the parent's tests did not finish" > "$D/status"
    elif [ -n "$OOM" ]; then echo "ok, the parent's test JVM ran out of memory" > "$D/status"
    else echo ok > "$D/status"; fi
done < "$LIST"

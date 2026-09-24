#!/bin/bash
#
# Mine post-cutoff bug subjects from upstream repositories.
#
# Why this exists. The memorisation probe bounds training-data contamination
# but cannot rule out recall *cued* by the source, because withholding the
# source also withholds the cue. Only faults the model cannot have seen settle
# that. GitBug-Java does not serve: its 199 bugs come from 2023 histories,
# chosen in early 2024 because that postdated the cutoffs of the day.
#
# So we build a small corpus from the same four projects already used, taking
# fix commits recent enough to postdate the model's training data. Same
# projects means the only thing that changes between this corpus and the
# Defects4J sample is the date — not the codebase, the style or the domain.
#
# What counts as a subject. The same contract Defects4J enforces:
#   - the fix commit changes both src/main/java and src/test/java
#   - with the parent's production code and the fix's tests, at least one test
#     FAILS  (the trigger tests)
#   - with the fix's production code and the fix's tests, all tests PASS
#   - the production change is small enough to be one fault, not a refactor
#
# Output, one directory per subject under data/postcutoff/<Project>-<sha>/:
#   meta.txt        project, sha, date, subject line
#   classes.txt     modified production classes, fully qualified
#   testclasses.txt test classes touched by the fix
#   triggers.txt    test methods that fail on the parent — the trigger tests
#   fix.diff        production-code diff, buggy -> fixed
#   status          ok, or the reason it was rejected
#
# Requires Maven 3.9+ on PATH. Java 11 suffices: all four projects still
# target Java 8 or 11.
#
# Usage:
#   ./bin/mine-postcutoff.sh candidates.txt
#     where each line is:  <repo-dir> <sha>

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
MINING=${MINING:-$HOME/code/mining}
LIST=${1:-data/postcutoff-candidates.txt}
OUT=data/postcutoff
MAX_PROD_FILES=${MAX_PROD_FILES:-3}   # more than this looks like a refactor

command -v mvn >/dev/null || { echo "mvn not on PATH"; exit 1; }
case "$(mvn -v 2>/dev/null | head -1)" in
  *" 3.9."*|*" 4."*) ;;
  *) echo "Maven 3.9+ required (Commons enforces it); found:"; mvn -v | head -1; exit 1 ;;
esac
[ -f "$ROOT/$LIST" ] || { echo "candidate list not found: $LIST"; exit 1; }
mkdir -p "$ROOT/$OUT"

fqcn() {   # path -> fully qualified class name
    echo "$1" | sed -E 's#^.*src/(main|test)/java/##; s#\.java$##; s#/#.#g'
}

while read -r REPO SHA _rest; do
    REPO=$(echo "${REPO:-}" | tr -d '[:space:]')
    SHA=$(echo "${SHA:-}"  | tr -d '[:space:]')
    [ -z "$REPO" ] && continue
    case "$REPO" in \#*) continue ;; esac

    R="$MINING/$REPO"
    [ -d "$R/.git" ] || { echo "[$REPO] not a git repo at $R"; continue; }

    SHORT=$(git -C "$R" rev-parse --short "$SHA" 2>/dev/null)
    [ -z "$SHORT" ] && { echo "[$REPO $SHA] unknown commit"; continue; }
    TAG="${REPO}-${SHORT}"
    D="$ROOT/$OUT/$TAG"

    if [ -f "$D/status" ]; then
        echo "[$TAG] already attempted ($(cat "$D/status")) — skipping"
        continue
    fi
    mkdir -p "$D"
    reject() { echo "[$TAG] $1"; echo "$1" > "$D/status"; }

    # ---- classify the files the fix touches ------------------------------
    FILES=$(git -C "$R" show --name-only --format= "$SHA" | grep -v '^$')
    PROD=$(echo "$FILES" | grep 'src/main/java/.*\.java$' || true)
    TESTS=$(echo "$FILES" | grep 'src/test/java/.*\.java$' || true)

    if [ -z "$PROD" ] || [ -z "$TESTS" ]; then
        reject "commit does not change both production and test code"; continue
    fi
    NPROD=$(echo "$PROD" | wc -l)
    if [ "$NPROD" -gt "$MAX_PROD_FILES" ]; then
        reject "touches $NPROD production files — likely a refactor, not one fault"
        continue
    fi

    {
        echo "project=$REPO"
        echo "sha=$(git -C "$R" rev-parse "$SHA")"
        echo "short=$SHORT"
        echo "date=$(git -C "$R" log -1 --format=%ad --date=short "$SHA")"
        echo "subject=$(git -C "$R" log -1 --format=%s "$SHA")"
    } > "$D/meta.txt"
    for f in $PROD;  do fqcn "$f"; done > "$D/classes.txt"
    for f in $TESTS; do fqcn "$f"; done > "$D/testclasses.txt"

    TEST_ARG=$(sed 's|.*\.||' "$D/testclasses.txt" | paste -sd, -)

    # ---- buggy state: parent production code + the fix's tests -----------
    echo "[$TAG] buggy state"
    git -C "$R" checkout -q --detach "$SHA~1" 2>/dev/null \
        || { reject "cannot check out parent commit"; continue; }
    for f in $TESTS; do
        git -C "$R" checkout -q "$SHA" -- "$f" 2>/dev/null
    done

    (cd "$R" && mvn test -Dtest="$TEST_ARG" -DfailIfNoTests=false) \
        > "$D/buggy.log" 2>&1
    BUGGY_RC=$?

    # surefire prints "  ClassName.methodName:LINE ..." under Failures/Errors
    grep -oP '^\[ERROR\]\s+\K\w+\.\w+(?=[:(])' "$D/buggy.log" \
        | sort -u > "$D/triggers.txt"

    if [ "$BUGGY_RC" -eq 0 ] || [ ! -s "$D/triggers.txt" ]; then
        reject "tests pass on the parent — the fix's tests do not expose the fault"
        git -C "$R" checkout -q -- . 2>/dev/null
        continue
    fi

    # ---- fixed state: everything from the fix commit ---------------------
    echo "[$TAG] fixed state"
    git -C "$R" checkout -q -- . 2>/dev/null
    git -C "$R" checkout -q --detach "$SHA" 2>/dev/null \
        || { reject "cannot check out fix commit"; continue; }

    (cd "$R" && mvn test -Dtest="$TEST_ARG" -DfailIfNoTests=false) \
        > "$D/fixed.log" 2>&1
    if [ $? -ne 0 ]; then
        reject "tests still fail on the fix commit — not a clean subject"; continue
    fi

    git -C "$R" diff "$SHA~1" "$SHA" -- $PROD > "$D/fix.diff"

    echo "ok" > "$D/status"
    echo "[$TAG] ok — $(wc -l < "$D/triggers.txt") trigger test(s): $(paste -sd' ' "$D/triggers.txt")"
done < "$ROOT/$LIST"

# leave every repo on its default branch, not detached
for R in "$MINING"/*/; do
    [ -d "$R/.git" ] || continue
    git -C "$R" checkout -q -- . 2>/dev/null
    git -C "$R" checkout -q master 2>/dev/null || git -C "$R" checkout -q main 2>/dev/null
done

echo
echo "subjects accepted: $(grep -lx ok "$ROOT/$OUT"/*/status 2>/dev/null | wc -l)"
echo "rejected:          $(grep -Lx ok "$ROOT/$OUT"/*/status 2>/dev/null | wc -l)"
REJ=$(grep -Lx ok "$ROOT/$OUT"/*/status 2>/dev/null)
if [ -n "$REJ" ]; then
    echo
    echo "rejections:"
    echo "$REJ" | while read -r s; do
        echo "  $(basename "$(dirname "$s")"): $(cat "$s")"
    done
fi

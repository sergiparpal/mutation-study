#!/bin/bash
#
# Show the production diff of a mined post-cutoff subject, for hand
# classification under the Study A fault taxonomy.
#
# The post-cutoff corpus was selected with criteria — small, ticket-tracked,
# fix-plus-test in one commit — that plausibly bias it toward well-specified
# boundary faults, which is exactly the class the specification-only arm
# catches. Classifying it under the same taxonomy as the Defects4J sample is
# what makes the two corpora comparable, or shows that they are not.
#
# Usage: ./bin/show-postcutoff.sh              list all subjects
#        ./bin/show-postcutoff.sh <TAG>        show one subject's diff
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
D="$ROOT/data/postcutoff"

if [ $# -eq 0 ]; then
    printf "%-26s %-11s %s\n" TAG DATE SUBJECT
    for d in "$D"/*/; do
        [ "$(cat "$d/status" 2>/dev/null)" = ok ] || continue
        printf "%-26s %-11s %s\n" "$(basename "$d")" \
            "$(grep '^date=' "$d/meta.txt" | cut -d= -f2)" \
            "$(grep '^subject=' "$d/meta.txt" | cut -d= -f2- | cut -c1-70)"
    done
    exit 0
fi

d="$D/$1"
[ -d "$d" ] || { echo "no such subject: $1"; exit 1; }
echo "=== $1"
cat "$d/meta.txt"
echo "--- classes: $(paste -sd' ' "$d/classes.txt")"
echo "--- triggers: $(paste -sd' ' "$d/triggers.txt")"
echo "--- diffstat"
git -C "$HOME/code/mining/$(grep '^project=' "$d/meta.txt" | cut -d= -f2)" \
    diff --stat "$(grep '^sha=' "$d/meta.txt" | cut -d= -f2)~1" \
                "$(grep '^sha=' "$d/meta.txt" | cut -d= -f2)" \
    -- $(sed 's|\.|/|g; s|$|.java|; s|^|src/main/java/|' "$d/classes.txt" | paste -sd' ')
echo "--- production diff"
cat "$d/fix.diff"

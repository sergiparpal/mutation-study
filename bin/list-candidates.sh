#!/bin/bash
#
# List post-cutoff fix-commit candidates for the matched corpus, newest first.
#
# Deliberately does NOT filter by commit size or by ticket reference. Those
# were the criteria that skewed the first post-cutoff corpus toward
# extreme-value faults (§3.8 of the paper). The only structural requirement is
# that the commit changes both production and test code, since a subject needs
# a trigger test.
#
# Output is one candidate per line:
#   <repo> <sha> <date> <prod-file-count> <subject>
#
# Walk it top to bottom, classify each from its diff, and fill the quotas in
# data/matched-quotas.md. Order of appearance is the selection rule.
#
# Usage: ./bin/list-candidates.sh [since-date]
set -uo pipefail
MINING=${MINING:-$HOME/code/mining}
SINCE=${1:-2026-06-01}

for r in commons-lang commons-csv commons-cli gson; do
    [ -d "$MINING/$r/.git" ] || continue
    git -C "$MINING/$r" log --since="$SINCE" --format='@@%H %ad %s' --date=short \
        --name-only \
    | awk -v repo="$r" '
        /^@@/ {
            if (c != "" && m > 0 && t > 0) print repo, sha, date, m, subj
            line = substr($0, 3)
            sha = substr(line, 1, 40)
            date = substr(line, 42, 10)
            subj = substr(line, 53)
            c = line; m = 0; t = 0
            next
        }
        /src\/main\/java\/.*\.java$/ { m++ }
        /src\/test\/java\/.*\.java$/ { t++ }
        END { if (c != "" && m > 0 && t > 0) print repo, sha, date, m, subj }
    '
done | sort -k3,3r

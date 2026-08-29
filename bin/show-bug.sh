#!/bin/bash
# Show the source diff between the buggy and fixed versions of a Defects4J bug.
# Usage: ./bin/show-bug.sh <project> <bug_id>
set -u

P=${1:?usage: show-bug.sh <project> <bug_id>}
B=${2:?usage: show-bug.sh <project> <bug_id>}

if ! defects4j bids -p "$P" | grep -qx "$B"; then
  echo "Bug $P-$B is not valid or is deprecated" >&2; exit 1
fi

[ -d "/tmp/${P}_${B}_b" ] || defects4j checkout -p "$P" -v "${B}b" -w "/tmp/${P}_${B}_b"
[ -d "/tmp/${P}_${B}_f" ] || defects4j checkout -p "$P" -v "${B}f" -w "/tmp/${P}_${B}_f"

SRC=$(defects4j export -p dir.src.classes -w "/tmp/${P}_${B}_b" 2>/dev/null | tail -1)
diff -ru "/tmp/${P}_${B}_b/$SRC" "/tmp/${P}_${B}_f/$SRC"

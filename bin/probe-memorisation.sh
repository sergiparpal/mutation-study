#!/bin/bash
#
# Memorisation probe.
#
# Threat being tested: the implementation-visible arm's 72% detection rate
# might reflect recall of faults seen during pretraining rather than
# test-writing ability. Defects4J has been public for years.
#
# GitBug-Java, the obvious replication corpus, does not resolve this: its 199
# bugs come from 2023 commit histories, chosen because that postdated the
# training cutoff of models available in early 2024. It no longer does.
#
# This probe asks the model directly, with no tools, no web access and no
# context, two questions per bug:
#
#   A — identifier cue:  "What is Defects4J bug Lang-13?"
#       Answering requires having seen the benchmark itself.
#
#   B — location cue:    "Was there a known bug in <Class> in <project>
#                         around that era?"
#       This is closer to what the M-arm agent actually had: project and
#       class, never the bug id.
#
# Interpretation. Recall on A or B is evidence the threat is real. Silence on
# both rules out *spontaneous* recall, but not recall cued by the source code
# itself — the design cannot separate those, as §5.1 of the paper states.
#
# Usage:
#   MODEL=sonnet ./bin/probe-memorisation.sh
#   MODEL=sonnet ./bin/probe-memorisation.sh data/sample.txt 3

set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SAMPLE=${1:-data/sample.txt}
LIMIT=${2:-0}
OUT=data/memorisation
MODEL=${MODEL:-sonnet}

command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }
[ -f "$ROOT/$SAMPLE" ] || { echo "sample not found: $SAMPLE"; exit 1; }
mkdir -p "$ROOT/$OUT"

ask() {   # ask <outfile> <prompt>
    local out=$1 prompt=$2
    [ -s "$out" ] && return 0
    claude -p "$prompt" \
        --model "$MODEL" \
        --allowedTools "" \
        --max-turns 1 \
        --output-format json > "$out" 2>/dev/null
}

n=0
while IFS=, read -r P B _rest; do
    P=$(echo "${P:-}" | tr -d '[:space:]')
    B=$(echo "${B:-}" | tr -d '[:space:]')
    [ -z "$P" ] && continue
    case "$P" in \#*) continue ;; esac
    n=$((n + 1))
    [ "$LIMIT" -gt 0 ] && [ "$n" -gt "$LIMIT" ] && break

    TAG="${P}-${B}"
    CLASSES_FILE="$ROOT/data/agent-runs/${TAG}.classes"
    CLASS=$(head -1 "$CLASSES_FILE" 2>/dev/null)
    CLASS=${CLASS:-unknown}

    echo "[$TAG] probing ($CLASS)"

    ask "$ROOT/$OUT/${TAG}.A.json" \
"What is Defects4J bug $TAG? Describe the specific fault: which method was
wrong and in what way. If you do not know this specific bug, say exactly
'I do not know this bug' and nothing else. Do not guess or reason from the
identifier. Answer in at most four sentences."

    ask "$ROOT/$OUT/${TAG}.B.json" \
"In the Java library $P (the Apache Commons / Google project of that name),
was there a known bug in the class $CLASS that was fixed at some point in its
history? Describe the specific fault if you recall one. If you do not recall a
specific bug in that class, say exactly 'I do not recall a bug in this class'
and nothing else. Do not speculate about what bugs such a class might plausibly
have. Answer in at most four sentences."
done < "$ROOT/$SAMPLE"

echo
echo "probes written: $(ls "$ROOT/$OUT"/*.json 2>/dev/null | wc -l)"
echo "total cost:     \$$(cd "$ROOT" && python3 - <<'EOF'
import json, glob
t = 0.0
for f in glob.glob('data/memorisation/*.json'):
    try:
        t += json.load(open(f)).get('total_cost_usd', 0) or 0
    except Exception:
        pass
print(f"{t:.2f}")
EOF
)"
echo "Next: ./bin/grade-memorisation.py"

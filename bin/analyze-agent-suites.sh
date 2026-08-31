#!/bin/bash
#
# Study B, phase 2: measure the packaged agent suites.
#
# The three defects4j analysis scripts take a FLAT directory of archives and
# process every archive matching the given project, so this runs once per
# project rather than once per bug.
#
# Naming discovered from gen_tests output:
#   <Project>-<bid><b|f>-<generator>[-<variant>].<id>.tar.bz2
# The archive contains the package directories from the root (./org/...), with
# no src/test/java prefix. The directory passed with -d must be flat; the
# nested layout gen_tests writes to (Project/generator/id/) is silently ignored
# and yields header-only CSVs.
#
# Usage:
#   ./bin/analyze-agent-suites.sh                    # data/agent-suites
#   ./bin/analyze-agent-suites.sh /tmp/other/suites

set -uo pipefail

SUITES=${1:-data/agent-suites}
OUT=data/agent-results
D4J_BIN=~/defects4j/framework/bin

[ -d "$SUITES" ] || { echo "no suite directory: $SUITES"; exit 1; }
ls "$SUITES"/*.tar.bz2 >/dev/null 2>&1 || { echo "no archives in $SUITES"; exit 1; }

# the analysis scripts append; start clean so reruns are not double-counted
rm -rf "$OUT"
mkdir -p "$OUT"

SUITES_ABS=$(cd "$SUITES" && pwd)
OUT_ABS=$(cd "$OUT" && pwd)

PROJECTS=$(ls "$SUITES"/*.tar.bz2 | xargs -n1 basename | cut -d- -f1 | sort -u)
echo "projects: $(echo $PROJECTS | tr '\n' ' ')"

for P in $PROJECTS; do
    echo
    echo "=== $P ==="
    for STEP in run_bug_detection run_coverage run_mutation; do
        echo "--- $STEP"
        "$D4J_BIN/$STEP.pl" -p "$P" -d "$SUITES_ABS" -o "$OUT_ABS" \
            > "$OUT_ABS/${STEP}_${P}.log" 2>&1 \
            || echo "    $STEP failed for $P — see $OUT/${STEP}_${P}.log"
    done
done

echo
echo "--- merged ---"
python3 - "$OUT_ABS" <<'EOF'
import csv, os, sys
out = sys.argv[1]
rows = {}
for name, keep in [("bug_detection", ["test_classification", "num_trigger"]),
                   ("coverage", ["lines_total", "lines_covered",
                                 "branches_total", "branches_covered"]),
                   ("mutation", ["mut_generated", "mut_excluded",
                                 "mut_covered", "mut_killed"])]:
    path = os.path.join(out, name)
    if not os.path.exists(path):
        continue
    with open(path) as fh:
        for r in csv.DictReader(fh):
            key = (r["project_id"], r["version_id"], r["test_suite_source"])
            rows.setdefault(key, {})
            for k in keep:
                rows[key][k] = r.get(k, "")

cols = ["project_id", "version_id", "test_suite_source", "test_classification",
        "num_trigger", "lines_total", "lines_covered", "branches_total",
        "branches_covered", "mut_generated", "mut_covered", "mut_killed"]
dest = os.path.join(out, "agent-metrics.csv")
with open(dest, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for (p, v, s), vals in sorted(rows.items()):
        w.writerow({"project_id": p, "version_id": v,
                    "test_suite_source": s, **vals})

n = len(rows)
det = sum(1 for v in rows.values() if v.get("test_classification") == "Fail")
print(f"{n} suites measured -> {dest}")
if n:
    print(f"real fault detected: {det}/{n} ({100*det/n:.0f}%)")
    ms = [(int(v["mut_killed"]), int(v["mut_generated"]))
          for v in rows.values()
          if v.get("mut_generated", "").isdigit() and int(v["mut_generated"]) > 0]
    if ms:
        k = sum(a for a, _ in ms)
        g = sum(b for _, b in ms)
        print(f"mutation score (pooled): {k}/{g} ({100*k/g:.0f}%)")
    cov = [(int(v["lines_covered"]), int(v["lines_total"]))
           for v in rows.values()
           if v.get("lines_total", "").isdigit() and int(v["lines_total"]) > 0]
    if cov:
        c = sum(a for a, _ in cov)
        t = sum(b for _, b in cov)
        print(f"line coverage (pooled):  {c}/{t} ({100*c/t:.0f}%)")
    print("\nNote: 'Fail' means at least one test fails on the buggy version. "
          "In the\nimplementation-visible arm this is a ceiling, not a "
          "capability measure — the\nagent read the fixed code, which already "
          "contains the repair.")
EOF

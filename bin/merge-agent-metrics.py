#!/usr/bin/env python3
"""
Merge Defects4J's three result tables into one row per suite, and recompute
the mutation columns from Major's own output.

WHY THE MUTATION COLUMNS ARE RECOMPUTED
---------------------------------------
Defects4J's run_mutation.pl does not report what its column names say. In
framework/core/Mutation.pm (_build_data_hash, v3.0.1):

    $cov  = scalar(keys %{$mut_map});          # every mutant in kill.csv
    next if $mut_map->{$mut_id} =~ /LIVE/;     # everything else ...
    ++$kill;                                   # ... counts as killed

Major's kill.csv lists every generated mutant with one of
FAIL | TIME | EXC | LIVE | UNCOV. So in the `mutation` table:

    mut_covered = all mutants               (always equal to mut_generated)
    mut_killed  = FAIL + TIME + EXC + UNCOV (uncovered mutants count as killed)

A suite that executes less code therefore scores HIGHER. The extreme case in
this study is the EvoSuite suite for Gson-3: 0 of 94 lines covered, 34 of 34
mutants "killed". Major's summary.csv for the same run says 0 covered, 0
killed.

An earlier version of this repository reported mut_killed / mut_generated from
that table as the mutation score (72% vs 70% for the two agent arms). The
figures were wrong by exactly the share of uncovered mutants: 13.6 points in
the implementation-visible arm, 25.6 in the specification-only arm.

This script reads the per-suite kill.csv that Defects4J copies next to its
table and writes:

    mut_generated   as reported by Defects4J
    mut_covered     mutants with a status other than UNCOV
    mut_killed      FAIL + TIME + EXC
    mut_killed_d4j  what the Defects4J table calls mut_killed, kept so the
                    earlier figures can be traced

It needs no Defects4J installation: it only re-reads files already produced.

Usage:
    merge-agent-metrics.py [results_dir] [-o out.csv]

    results_dir defaults to data/agent-results; the output defaults to
    <results_dir>/agent-metrics.csv.
"""

import csv
import os
import sys
from collections import Counter

KILLED = ("FAIL", "TIME", "EXC")        # Major's kill statuses
COLS = ["project_id", "version_id", "test_suite_source",
        "test_classification", "num_trigger",
        "lines_total", "lines_covered", "branches_total", "branches_covered",
        "mut_generated", "mut_covered", "mut_killed", "mut_killed_d4j"]


def read_table(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def read_kill_csv(path):
    """Status counts from one Major kill.csv, or None if it is missing."""
    if not os.path.exists(path):
        return None
    counts = Counter()
    with open(path) as fh:
        next(fh, None)                  # header
        for line in fh:
            line = line.strip()
            if line:
                counts[line.split(",")[1]] += 1
    return counts


def is_count(value):
    return isinstance(value, str) and value.isdigit()


def main():
    args = sys.argv[1:]
    out_path = None
    if "-o" in args:
        i = args.index("-o")
        out_path = args[i + 1]
        del args[i:i + 2]
    results = args[0] if args else "data/agent-results"
    out_path = out_path or os.path.join(results, "agent-metrics.csv")

    rows = {}

    def row(r):
        key = (r["project_id"], r["version_id"], r["test_suite_source"])
        return rows.setdefault(key, {"_test_id": r.get("test_id", "1")})

    for r in read_table(os.path.join(results, "bug_detection")):
        row(r).update(test_classification=r["test_classification"],
                      num_trigger=r["num_trigger"])
    for r in read_table(os.path.join(results, "coverage")):
        row(r).update({k: r[k] for k in ("lines_total", "lines_covered",
                                         "branches_total", "branches_covered")})

    warnings = []
    for r in read_table(os.path.join(results, "mutation")):
        dest = row(r)
        dest["mut_generated"] = r["mut_generated"]
        dest["mut_killed_d4j"] = r["mut_killed"]
        tag = f"{r['project_id']}-{r['version_id']} {r['test_suite_source']}"
        kill_path = os.path.join(
            results, "mutation_log", r["project_id"], r["test_suite_source"],
            f"{r['version_id']}.{r.get('test_id', '1')}.kill.csv")
        counts = read_kill_csv(kill_path)
        if counts is None:
            warnings.append(f"{tag}: no kill.csv — mutation columns left empty")
            continue
        total = sum(counts.values())
        dest["mut_covered"] = str(total - counts["UNCOV"])
        dest["mut_killed"] = str(sum(counts[s] for s in KILLED))
        # the table and the raw file must describe the same run
        if is_count(r["mut_generated"]) and is_count(r.get("mut_excluded", "0")):
            if total != int(r["mut_generated"]) - int(r["mut_excluded"]):
                warnings.append(f"{tag}: kill.csv has {total} mutants, the "
                                f"table says {r['mut_generated']}")
        if is_count(r["mut_killed"]) and \
                int(r["mut_killed"]) != total - counts["LIVE"]:
            warnings.append(f"{tag}: table mut_killed={r['mut_killed']} is not "
                            f"the non-LIVE count {total - counts['LIVE']}")

    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for (p, v, s), vals in sorted(rows.items()):
            w.writerow({"project_id": p, "version_id": v,
                        "test_suite_source": s, **vals})

    print(f"{len(rows)} suites merged -> {out_path}")
    for msg in warnings:
        print(f"  WARNING {msg}")

    by_source = {}
    for (_, _, s), vals in rows.items():
        by_source.setdefault(s, []).append(vals)

    print()
    print(f"{'source':<10} {'suites':>6}  {'detected':>14}  {'broken':>6}  "
          f"{'mutation':>8}  {'uncovered':>9}  {'D4J table':>9}  {'line cov':>8}")
    for s in sorted(by_source):
        suites = by_source[s]
        valid = [v for v in suites
                 if v.get("test_classification") in ("Pass", "Fail")]
        det = sum(1 for v in valid if v["test_classification"] == "Fail")
        broken = sum(1 for v in suites
                     if v.get("test_classification") == "Broken")
        mut = [v for v in suites if is_count(v.get("mut_killed"))
               and is_count(v.get("mut_generated"))
               and int(v["mut_generated"]) > 0]
        gen = sum(int(v["mut_generated"]) for v in mut)
        killed = sum(int(v["mut_killed"]) for v in mut)
        covered = sum(int(v["mut_covered"]) for v in mut)
        d4j = sum(int(v["mut_killed_d4j"]) for v in mut
                  if is_count(v.get("mut_killed_d4j")))
        cov = [v for v in suites if is_count(v.get("lines_total"))
               and int(v["lines_total"]) > 0]
        lt = sum(int(v["lines_total"]) for v in cov)
        lc = sum(int(v["lines_covered"]) for v in cov)

        def pct(a, b):
            return f"{100 * a / b:.1f}%" if b else "-"

        detected = f"{det}/{len(valid)} ({pct(det, len(valid))})"
        print(f"{s:<10} {len(suites):>6}  {detected:>14}  {broken:>6}  "
              f"{pct(killed, gen):>8}  {pct(gen - covered, gen):>9}  "
              f"{pct(d4j, gen):>9}  {pct(lc, lt):>8}")

    print("""
mutation   = killed / generated, pooled over the suites of that source
uncovered  = mutants no test executes
D4J table  = what run_mutation.pl reports: killed + uncovered
detected   = suites classified Fail, over suites classified Pass or Fail;
             Broken suites were never validly run against the buggy revision

'Fail' means at least one test fails on the buggy revision. In the
implementation-visible arm this is a ceiling, not a capability measure: the
agent read the fixed code, which already contains the repair.""")


if __name__ == "__main__":
    main()

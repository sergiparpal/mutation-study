#!/usr/bin/env python3
"""
Turn the raw Major artifacts collected by run-mutation.sh into one metrics row
per bug.

The question this answers, per bug:

    Inside the methods the fix touches, which mutants does the test that
    catches the real fault kill, and which operators generate them?

The method restriction matters. Without it, "coupled" means "killed by the
trigger test run alone", which is a bad superset: Lang-43's one-line fix yields
85 such mutants across the whole class, of which one sits on a fix line. The
unfiltered figures are still reported so the two can be compared — the ratio is
itself a result about how much a naive coupling measure overestimates.

Method spans are inferred from the mutants themselves (min..max line per method
signature), not by parsing Java. Cheap, and accurate enough to say whether a
method overlaps the fix; it would be wrong for a method whose mutants cluster
away from its edges.

Reads:  data/raw/<Project>-<Bug>/
Writes: data/mutation-metrics.csv
"""

import csv
import os
import re
import sys
from collections import Counter, defaultdict

RAW = "data/raw"
OUT = "data/mutation-metrics.csv"

KILLED = {"FAIL", "TIME", "EXC"}          # Major's kill statuses


def read_kill(path):
    """mutant id (int) -> status string. Skips the header line."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("MutantNo"):
                continue
            parts = line.split(",")
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            out[int(parts[0])] = parts[1].strip()
    return out


def read_mutants(path):
    """
    mutant id -> {operator, sig, cls, line}

    Line format:
      id:OP:from:to:pkg.Class$Inner@method(params):line:col:description
    """
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split(":", 7)
            if len(f) < 7 or not f[0].isdigit():
                continue
            sig = f[4]
            try:
                lineno = int(f[5])
            except ValueError:
                continue
            out[int(f[0])] = {
                "operator": f[1],
                "sig": sig,
                "cls": sig.split("@", 1)[0],
                "line": lineno,
            }
    return out


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def read_touched_lines(path):
    """
    Parse a unified diff -> {source_path: set(line numbers in the NEW file
    touched by the fix)}.

    Touched means either a line the fix adds, or the position at which the fix
    removes lines. Deletion positions matter: a fix that only deletes (Cli-32,
    Gson-4) adds almost nothing, and would otherwise be invisible here.
    """
    touched = defaultdict(set)
    current, lineno = None, 0
    if not os.path.exists(path):
        return touched
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("+++ "):
                current = line[4:].split("\t")[0].strip()
                touched[current]                      # ensure key exists
                continue
            m = HUNK.match(line)
            if m:
                lineno = int(m.group(1))
                continue
            if current is None:
                continue
            if line.startswith("+"):
                touched[current].add(lineno)
                lineno += 1
            elif line.startswith("-"):
                touched[current].add(lineno)          # deletion anchor
            elif line.startswith("\\"):
                pass
            else:
                lineno += 1                           # context
    return touched


def lines_for_class(touched, cls):
    """Match a mutant's class to a diff path. Inner classes share the file."""
    outer = cls.split("$", 1)[0]
    suffix = outer.replace(".", "/") + ".java"
    hits = set()
    for path, lines in touched.items():
        if path.endswith(suffix):
            hits |= lines
    return hits


def fix_methods(mutants, touched):
    """
    Signatures of methods that overlap the fix.

    A method's span is min..max line over its own mutants. It counts as
    fix-touched if any touched line of its class falls inside that span.
    """
    spans = defaultdict(lambda: [10**9, -1])
    for m in mutants.values():
        s = spans[m["sig"]]
        s[0] = min(s[0], m["line"])
        s[1] = max(s[1], m["line"])

    out = set()
    per_class = {}
    for sig, (lo, hi) in spans.items():
        cls = sig.split("@", 1)[0]
        if cls not in per_class:
            per_class[cls] = lines_for_class(touched, cls)
        if any(lo <= ln <= hi for ln in per_class[cls]):
            out.add(sig)
    return out


def fmt(counter):
    """Counter -> 'STD:12|ROR:2', commonest first, empty -> '-'."""
    if not counter:
        return "-"
    return "|".join(f"{k}:{v}" for k, v in sorted(counter.items(),
                                                  key=lambda kv: (-kv[1], kv[0])))


def analyse(d):
    bug = os.path.basename(d)
    row = {"bug_id": bug}

    if os.path.exists(os.path.join(d, "error")):
        row["status"] = open(os.path.join(d, "error")).read().strip()
        return row
    if not os.path.exists(os.path.join(d, "done")):
        row["status"] = "incomplete"
        return row

    mutants = read_mutants(os.path.join(d, "mutants.log"))
    full = read_kill(os.path.join(d, "kill_full.csv"))
    touched = read_touched_lines(os.path.join(d, "fix.diff"))

    coupled, n_triggers = set(), 0
    for name in sorted(os.listdir(d)):
        if name.startswith("kill_trigger_"):
            n_triggers += 1
            for mid, st in read_kill(os.path.join(d, name)).items():
                if st in KILLED:
                    coupled.add(mid)

    killed_full = {m for m, s in full.items() if s in KILLED}
    methods = fix_methods(mutants, touched)

    in_methods = {m for m, info in mutants.items() if info["sig"] in methods}
    coupled_in = coupled & in_methods

    on_lines = set()
    for mid in coupled:
        info = mutants.get(mid)
        if info and info["line"] in lines_for_class(touched, info["cls"]):
            on_lines.add(mid)

    row.update({
        "status": "ok",
        "n_triggers": n_triggers,
        "n_mutants": len(mutants),
        "n_killed_full": len(killed_full),
        "n_live_full": sum(1 for s in full.values() if s == "LIVE"),
        "n_uncov_full": sum(1 for s in full.values() if s == "UNCOV"),
        "n_coupled": len(coupled),
        "n_killed_only_by_others": len(killed_full - coupled),

        # --- restricted to the methods the fix touches ---
        "n_fix_methods": len(methods),
        "n_mutants_in_fix_methods": len(in_methods),
        "n_coupled_in_fix_methods": len(coupled_in),
        "n_coupled_on_touch_lines": len(on_lines),
        "ops_coupled_in_fix_methods": fmt(Counter(
            mutants[m]["operator"] for m in coupled_in)),
        "kill_kinds_coupled_in_fix_methods": fmt(Counter(
            full.get(m, "?") for m in coupled_in)),
        "live_in_fix_methods": sum(
            1 for m in in_methods if full.get(m) == "LIVE"),

        # --- unrestricted, for comparison ---
        "ops_all": fmt(Counter(m["operator"] for m in mutants.values())),
        "ops_coupled": fmt(Counter(
            mutants[m]["operator"] for m in coupled if m in mutants)),
        "kill_kinds_coupled": fmt(Counter(full.get(m, "?") for m in coupled)),
        "kill_kinds_full": fmt(Counter(full.values())),
    })
    return row


COLS = ["bug_id", "status", "n_triggers", "n_mutants", "n_killed_full",
        "n_live_full", "n_uncov_full", "n_coupled", "n_killed_only_by_others",
        "n_fix_methods", "n_mutants_in_fix_methods", "n_coupled_in_fix_methods",
        "n_coupled_on_touch_lines", "live_in_fix_methods",
        "ops_coupled_in_fix_methods", "kill_kinds_coupled_in_fix_methods",
        "ops_all", "ops_coupled", "kill_kinds_coupled", "kill_kinds_full"]


def agg_ops(rows, col):
    total = Counter()
    for r in rows:
        if r.get(col, "-") != "-":
            for part in r[col].split("|"):
                k, v = part.split(":")
                total[k] += int(v)
    return total


def main():
    if not os.path.isdir(RAW):
        sys.exit(f"{RAW} not found — run bin/run-mutation.sh first")

    dirs = sorted(os.path.join(RAW, x) for x in os.listdir(RAW)
                  if os.path.isdir(os.path.join(RAW, x)))
    rows = [analyse(d) for d in dirs]

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    ok = [r for r in rows if r.get("status") == "ok"]
    print(f"{len(rows)} bug directories, {len(ok)} analysed -> {OUT}")
    for r in rows:
        if r.get("status") != "ok":
            print(f"  SKIPPED {r['bug_id']}: {r.get('status')}")
    if not ok:
        return

    raw_c = sum(r["n_coupled"] for r in ok)
    fix_c = sum(r["n_coupled_in_fix_methods"] for r in ok)
    line_c = sum(r["n_coupled_on_touch_lines"] for r in ok)

    print("\ncoupled mutants (killed by a trigger test alone)")
    print(f"  anywhere in the mutated classes   : {raw_c}")
    print(f"  in the methods the fix touches    : {fix_c}"
          + (f"  ({100*fix_c/raw_c:.0f}% of raw)" if raw_c else ""))
    print(f"  on the exact lines the fix touches: {line_c}")
    if fix_c:
        print(f"  unrestricted count overestimates by {raw_c/fix_c:.1f}x")

    print(f"\noperators, coupled in fix methods : "
          f"{fmt(agg_ops(ok, 'ops_coupled_in_fix_methods'))}")
    print(f"kill kinds, coupled in fix methods: "
          f"{fmt(agg_ops(ok, 'kill_kinds_coupled_in_fix_methods'))}")
    print(f"kill kinds, whole relevant suite  : "
          f"{fmt(agg_ops(ok, 'kill_kinds_full'))}")

    print("\nper bug:")
    print(f"  {'bug':<10} {'muts':>5} {'inFix':>6} {'cpl':>4} {'cplFix':>7} "
          f"{'liveFix':>8}  ops in fix methods")
    for r in ok:
        print(f"  {r['bug_id']:<10} {r['n_mutants']:>5} "
              f"{r['n_mutants_in_fix_methods']:>6} {r['n_coupled']:>4} "
              f"{r['n_coupled_in_fix_methods']:>7} "
              f"{r['live_in_fix_methods']:>8}  "
              f"{r['ops_coupled_in_fix_methods']}")

    print("\nCaveat: method spans are inferred from mutant line numbers, not "
          "parsed from Java.\nA method whose mutants cluster away from its "
          "edges may be mis-attributed.")


if __name__ == "__main__":
    main()

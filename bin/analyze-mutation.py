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
unfiltered figures are still reported so the two can be compared.

METHOD SPANS
------------
Major reports a method signature and a line for every mutant, but nothing about
where methods begin and end. Spans are therefore inferred.

A first version used min..max over each method's own mutants and failed on
Lang-8: the line the fix adds (`TimeZone zone = calendar.getTimeZone();`) has
no operators or literals, so it generates no mutant and sits one line *above*
the method's first mutant. It fell outside the span and the method was missed.

That failure is systematic, not incidental — lines with nothing mutable are
exactly the lines this study cares about. Spans are now extended downwards to
just after the previous method's last mutant (and upwards to just before the
next method's first), capped by GAP_CAP lines so a large field block between
methods is not swallowed.

Bugs where the fix touches a class but no method matches are flagged in the
`attribution` column rather than silently reported as zero.

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

KILLED = {"FAIL", "TIME", "EXC"}   # Major's kill statuses
GAP_CAP = 30                       # max lines a span may be extended either way
MANY_TRIGGERS = 5                  # above this, coupling is diluted — flagged


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
    Gson-4) adds almost nothing and would otherwise be invisible here.
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


def method_spans(mutants):
    """
    signature -> (lo, hi), widened into the gaps between neighbouring methods.

    Grouped per source file rather than per class, because inner classes are
    interleaved with their outer class in the same file and their line ranges
    must be ordered together.
    """
    raw = defaultdict(lambda: [10**9, -1])
    for m in mutants.values():
        s = raw[m["sig"]]
        s[0] = min(s[0], m["line"])
        s[1] = max(s[1], m["line"])

    by_file = defaultdict(list)
    for sig, (lo, hi) in raw.items():
        outer = sig.split("@", 1)[0].split("$", 1)[0]
        by_file[outer].append((lo, hi, sig))

    spans = {}
    for _, entries in by_file.items():
        entries.sort()
        for i, (lo, hi, sig) in enumerate(entries):
            prev_hi = entries[i - 1][1] if i > 0 else None
            next_lo = entries[i + 1][0] if i + 1 < len(entries) else None
            low = lo - GAP_CAP if prev_hi is None else max(prev_hi + 1, lo - GAP_CAP)
            high = hi + GAP_CAP if next_lo is None else min(next_lo - 1, hi + GAP_CAP)
            spans[sig] = (low, high)
    return spans


def fix_methods(mutants, touched):
    """Signatures of methods whose (widened) span contains a touched line."""
    spans = method_spans(mutants)
    per_class, out = {}, set()
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

    on_lines = {mid for mid in coupled
                if mid in mutants
                and mutants[mid]["line"] in lines_for_class(touched,
                                                            mutants[mid]["cls"])}

    # diagnosis: is a zero real, or did attribution fail?
    any_touched = any(lines_for_class(touched, m["cls"]) for m in mutants.values())
    if not mutants:
        attribution = "no_mutants"
    elif not any_touched:
        attribution = "fix_outside_mutated_classes"
    elif not methods:
        attribution = "NO_METHOD_MATCHED"
    else:
        attribution = "ok"
    if n_triggers > MANY_TRIGGERS:
        attribution += f";many_triggers({n_triggers})"

    row.update({
        "status": "ok",
        "attribution": attribution,
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
        "live_in_fix_methods": sum(1 for m in in_methods
                                   if full.get(m) == "LIVE"),
        "ops_coupled_in_fix_methods": fmt(Counter(
            mutants[m]["operator"] for m in coupled_in)),
        "kill_kinds_coupled_in_fix_methods": fmt(Counter(
            full.get(m, "?") for m in coupled_in)),

        # --- unrestricted, for comparison ---
        "ops_all": fmt(Counter(m["operator"] for m in mutants.values())),
        "ops_coupled": fmt(Counter(mutants[m]["operator"]
                                   for m in coupled if m in mutants)),
        "kill_kinds_coupled": fmt(Counter(full.get(m, "?") for m in coupled)),
        "kill_kinds_full": fmt(Counter(full.values())),
    })
    return row


COLS = ["bug_id", "status", "attribution", "n_triggers", "n_mutants",
        "n_killed_full", "n_live_full", "n_uncov_full", "n_coupled",
        "n_killed_only_by_others", "n_fix_methods", "n_mutants_in_fix_methods",
        "n_coupled_in_fix_methods", "n_coupled_on_touch_lines",
        "live_in_fix_methods", "ops_coupled_in_fix_methods",
        "kill_kinds_coupled_in_fix_methods", "ops_all", "ops_coupled",
        "kill_kinds_coupled", "kill_kinds_full"]


def agg_ops(rows, col):
    total = Counter()
    for r in rows:
        if r.get(col, "-") != "-":
            for part in r[col].split("|"):
                k, v = part.split(":")
                total[k] += int(v)
    return total


def report(rows, label):
    raw_c = sum(r["n_coupled"] for r in rows)
    fix_c = sum(r["n_coupled_in_fix_methods"] for r in rows)
    line_c = sum(r["n_coupled_on_touch_lines"] for r in rows)
    print(f"\n--- {label} ({len(rows)} bugs) ---")
    print(f"  coupled anywhere in mutated classes : {raw_c}")
    print(f"  coupled in the fix's methods        : {fix_c}"
          + (f"  ({100*fix_c/raw_c:.0f}% of raw)" if raw_c else ""))
    print(f"  coupled on the fix's exact lines    : {line_c}")
    print(f"  operators : {fmt(agg_ops(rows, 'ops_coupled_in_fix_methods'))}")
    print(f"  kill kinds: {fmt(agg_ops(rows, 'kill_kinds_coupled_in_fix_methods'))}")


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

    bad = [r for r in ok if "NO_METHOD_MATCHED" in r["attribution"]]
    many = [r for r in ok if "many_triggers" in r["attribution"]]
    clean = [r for r in ok if r["attribution"] == "ok"]

    report(ok, "all analysed")
    report(clean, "clean only: attribution ok and <=%d triggers" % MANY_TRIGGERS)

    if bad:
        print(f"\nattribution failed ({len(bad)}): "
              + ", ".join(r["bug_id"] for r in bad))
    if many:
        print(f"many triggers, coupling diluted ({len(many)}): "
              + ", ".join(f"{r['bug_id']}({r['n_triggers']})" for r in many))

    print("\nper bug:")
    print(f"  {'bug':<10} {'trg':>3} {'muts':>5} {'inFix':>6} {'cpl':>4} "
          f"{'cplFix':>7} {'liveFix':>8}  ops in fix methods")
    for r in ok:
        mark = "  " if r["attribution"] == "ok" else " *"
        print(f" {mark}{r['bug_id']:<10} {r['n_triggers']:>3} "
              f"{r['n_mutants']:>5} {r['n_mutants_in_fix_methods']:>6} "
              f"{r['n_coupled']:>4} {r['n_coupled_in_fix_methods']:>7} "
              f"{r['live_in_fix_methods']:>8}  "
              f"{r['ops_coupled_in_fix_methods']}")
    print("  (* = attribution not clean; see the attribution column)")


if __name__ == "__main__":
    main()

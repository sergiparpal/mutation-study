#!/usr/bin/env python3
"""
Print every figure quoted in §3 of the write-up, recomputed from data/.

Needs no Defects4J installation and no model access: it reads the merged
per-suite measurements, the run records and the probe grades already in the
repository. Rebuilding those from the packaged suites is a separate, slower
step (bin/analyze-agent-suites.sh).

Conventions, all of them stated in the write-up:

- Mutation score and coverage are POOLED: mutants killed over mutants
  generated, summed across the suites of a population. The per-suite mean is
  printed next to it, because the two differ by several points.
- Mutation score counts FAIL + TIME + EXC as killed. It is not the mut_killed
  of Defects4J's table, which also counts uncovered mutants; see
  bin/merge-agent-metrics.py.
- A detection rate is over suites classified Pass or Fail. A suite classified
  Broken was never validly run against the buggy revision and is left out of
  the denominator, not counted as a miss.

Usage: ./bin/report-figures.py        (from the repository root)
"""

import csv
import glob
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS = "data/agent-metrics-final.csv"
PROJECTS = [("Lang", "Commons Lang"), ("Csv", "Commons CSV"),
            ("Gson", "Gson"), ("Cli", "Commons CLI")]


def num(x):
    return isinstance(x, str) and x.isdigit()


def pct(a, b, digits=1):
    return f"{100 * a / b:.{digits}f}%" if b else "-"


def binom_two_sided(b, c):
    """Exact two-sided sign / McNemar test on b vs c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def load():
    arms = defaultdict(dict)
    with open(METRICS) as fh:
        for r in csv.DictReader(fh):
            arms[r["test_suite_source"]][(r["project_id"],
                                          r["version_id"].rstrip("f"))] = r
    return arms


def valid(r):
    return r["test_classification"] in ("Pass", "Fail")


def detected(r):
    return r["test_classification"] == "Fail"


def summary(rows):
    """Pooled and per-suite figures for one population of suites."""
    v = [r for r in rows if valid(r)]
    mut = [r for r in rows if num(r["mut_killed"]) and int(r["mut_generated"])]
    cov = [r for r in rows if num(r["lines_total"]) and int(r["lines_total"])]
    gen = sum(int(r["mut_generated"]) for r in mut)
    killed = sum(int(r["mut_killed"]) for r in mut)
    covered = sum(int(r["mut_covered"]) for r in mut)
    d4j = sum(int(r["mut_killed_d4j"]) for r in mut)
    lt = sum(int(r["lines_total"]) for r in cov)
    lc = sum(int(r["lines_covered"]) for r in cov)
    return {
        "n": len(rows), "n_valid": len(v), "det": sum(map(detected, v)),
        "broken": sum(r["test_classification"] == "Broken" for r in rows),
        "mut": pct(killed, gen), "mut_mean": pct(
            sum(int(r["mut_killed"]) / int(r["mut_generated"]) for r in mut),
            len(mut)),
        "uncov": pct(gen - covered, gen), "kill_cov": pct(killed, covered),
        "d4j": pct(d4j, gen), "n_cov": len(cov), "cov": pct(lc, lt),
        "cov_mean": pct(sum(int(r["lines_covered"]) / int(r["lines_total"])
                            for r in cov), len(cov)),
    }


def line(label, s):
    det = f"{s['det']}/{s['n_valid']} ({pct(s['det'], s['n_valid'], 0)})"
    print(f"  {label:<26} suites {s['n']:>2}  detected {det:<12} "
          f"mutation {s['mut']:>6} (mean {s['mut_mean']:>6})  "
          f"coverage {s['cov']:>6} (mean {s['cov_mean']:>6}, n={s['n_cov']})")


def section(title):
    print()
    print(title)
    print("-" * len(title))


def main():
    os.chdir(ROOT)
    arms = load()
    A, S, E, O = (arms[k] for k in ("agent", "spec", "evosuite", "agentopus"))

    # ---- §3.1 ------------------------------------------------------------
    both = sorted(set(A) & set(S))
    section(f"§3.1  Paired, {len(both)} bugs measured in both agent arms")
    sa, ss = summary([A[k] for k in both]), summary([S[k] for k in both])
    line("M (implementation-visible)", sa)
    line("S (specification-only)", ss)
    for name, s in (("M", sa), ("S", ss)):
        print(f"    {name}: mutants uncovered {s['uncov']}, kill rate on "
              f"covered mutants {s['kill_cov']}; Defects4J's table would "
              f"report {s['d4j']}")
    m_only = [k for k in both if detected(A[k]) and not detected(S[k])]
    s_only = [k for k in both if detected(S[k]) and not detected(A[k])]
    both_det = [k for k in both if detected(A[k]) and detected(S[k])]
    print(f"  detected by M only {len(m_only)}, by S only {len(s_only)}, by "
          f"both {len(both_det)} "
          f"({', '.join('-'.join(k) for k in both_det)}), by neither "
          f"{len(both) - len(m_only) - len(s_only) - len(both_det)}")
    print(f"  exact McNemar, two-sided: p = "
          f"{binom_two_sided(len(m_only), len(s_only)):.2e}")

    def ms(r):
        return int(r["mut_killed"]) / int(r["mut_generated"])
    diffs = [ms(A[k]) - ms(S[k]) for k in both]
    up, down = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    print(f"  mutation score per bug: M higher in {up}, S higher in {down}; "
          f"mean difference {100 * sum(diffs) / len(diffs):+.1f} points; "
          f"sign test p = {binom_two_sided(up, down):.1e}")

    print()
    print("  Every suite measured, per population:")
    line("M, Sonnet", summary(list(A.values())))
    line("S, Sonnet", summary(list(S.values())))
    line("EvoSuite", summary(list(E.values())))
    line("M, Opus", summary(list(O.values())))
    line("  M, Sonnet, same 6 bugs", summary([A[k] for k in O if k in A]))
    for name, arm in (("S", S), ("EvoSuite", E)):
        broken = sorted("-".join(k) for k, r in arm.items()
                        if r["test_classification"] == "Broken")
        print(f"  {name} suites classified Broken: {', '.join(broken)}")

    # ---- §3.2 ------------------------------------------------------------
    section("§3.2  Per project (paired bugs)")
    for pid, name in PROJECTS:
        ks = [k for k in both if k[0] == pid]
        print(f"  {name:<13} n={len(ks):>2}  M detected "
              f"{sum(detected(A[k]) for k in ks)}  S detected "
              f"{sum(detected(S[k]) for k in ks)}")

    # ---- §3.4 ------------------------------------------------------------
    section("§3.4  Tests disabled in the specification-only arm")
    per = defaultdict(lambda: [0, 0])
    for f in glob.glob("data/spec-runs/*.pruned"):
        p, t = map(int, open(f).read().split())
        pid = os.path.basename(f).split("-")[0]
        per[pid][0] += p
        per[pid][1] += t
    P, T = (sum(v[i] for v in per.values()) for i in (0, 1))
    print(f"  all 40 suites: {P} of {T} ({pct(P, T)})")
    for pid, name in sorted(PROJECTS, key=lambda x: per[x[0]][0] / per[x[0]][1]):
        p, t = per[pid]
        print(f"  {name:<13} {p:>2} / {t:<4} {pct(p, t)}")

    # ---- §3.5 ------------------------------------------------------------
    three_all = sorted(set(A) & set(S) & set(E))
    three = [k for k in three_all if valid(A[k]) and valid(S[k]) and valid(E[k])]
    section(f"§3.5  Three generators: {len(three)} bugs with a valid "
            f"detection verdict for all three (of {len(three_all)} with a "
            f"suite from each)")
    line("M (implementation-visible)", summary([A[k] for k in three]))
    line("EvoSuite", summary([E[k] for k in three]))
    line("S (specification-only)", summary([S[k] for k in three]))
    pairs = [(detected(A[k]), detected(E[k])) for k in three]
    b2 = sum(a and e for a, e in pairs)
    a1 = sum(a and not e for a, e in pairs)
    e1 = sum(e and not a for a, e in pairs)
    print(f"  M and EvoSuite: both {b2}, M only {a1}, EvoSuite only {e1}, "
          f"neither {len(three) - b2 - a1 - e1}; union {b2 + a1 + e1} "
          f"({pct(b2 + a1 + e1, len(three), 0)})")
    print("  left out: " + ", ".join(
        "-".join(k) for k in three_all if k not in three))
    print(f"  for reference, all {len(three_all)} bugs (mutation and coverage "
          f"do not need a detection verdict):")
    line("  M", summary([A[k] for k in three_all]))
    line("  EvoSuite", summary([E[k] for k in three_all]))
    line("  S", summary([S[k] for k in three_all]))

    # ---- §3.6 ------------------------------------------------------------
    section("§3.6  Cost at list prices (from the run records)")
    for label, pattern, statuses in (
            ("M, Sonnet", "data/agent-runs/*.json", "data/agent-runs"),
            ("M, Opus", "data/agent-runs-opus/*.json", "data/agent-runs-opus"),
            ("S, Sonnet", "data/spec-runs/*.json", "data/spec-runs")):
        total = accepted = 0.0
        runs = ok = 0
        for f in glob.glob(pattern):
            try:
                cost = json.load(open(f)).get("total_cost_usd") or 0
            except Exception:
                continue
            if cost:
                runs += 1
            total += cost
            st = f[:-5] + ".status"
            if os.path.exists(st) and open(st).read().strip() == "ok":
                ok += 1
                accepted += cost
        print(f"  {label:<10} ${total:6.2f} over {runs} billed runs; "
              f"{ok} accepted suites cost ${accepted:.2f} "
              f"(${accepted / ok:.2f} each)")

    # ---- §3.7 ------------------------------------------------------------
    section("§3.7  Memorisation probe")
    grades = list(csv.DictReader(open("data/memorisation-grades.csv")))
    for probe in "AB":
        c = Counter(r[f"{probe}_verdict"] for r in grades)
        print(f"  probe {probe}: " + ", ".join(
            f"{k} {v}" for k, v in sorted(c.items())))
    readings = list(csv.DictReader(open("data/memorisation-readings.csv")))
    c = Counter(r["reading"] for r in readings)
    print("  hand readings of the answers that did not disclaim: " + ", ".join(
        f"{k} {v}" for k, v in sorted(c.items())))
    for r in readings:
        if "recall" in r["reading"]:
            print(f"    {r['bug_id']:<8} {r['reading']:<38} -> {r['refers_to']}")

    # ---- §3.8 ------------------------------------------------------------
    section("§3.8  Post-cutoff corpora")
    sys.stdout.flush()
    subprocess.run([sys.executable, "bin/tally-postcutoff.py"], check=False)


if __name__ == "__main__":
    main()

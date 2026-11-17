#!/usr/bin/env python3
"""
The analysis of the second campaign, as data/campaign2/PROTOCOL.md fixes it.

This file was committed with the protocol, before any run on the sample, so
that the analysis could not be chosen after seeing the data. Change it after
the first run and the change is a deviation: record it in the protocol.

WHAT IT COMPUTES
----------------
Sets
  paired    bugs with a detection verdict (Pass or Fail) in both arms
  complete  paired bugs that also have a mutation score and a line-coverage
            figure in both arms
  A run listed in violations.txt is treated as having produced no suite.

H1  The arms differ in real-fault detection.
    Exact McNemar test, two-sided, on the paired set. alpha = 0.05.

H2  Detection falls further than mutation score does. Assessed only if H1 is
    rejected with m2 above s2 (fixed sequence, so no correction).
    On the complete set, for X in detection rate D, pooled mutation score M,
    pooled line coverage C:
        fall(X) = 1 - X(s2) / X(m2)
    The statistic is  fall(D) - fall(M).  Its 95% interval is a percentile
    bootstrap over bugs: 10,000 resamples of the complete set with
    replacement, both arms of a bug kept together, random.Random(20261117),
    bounds at sorted[249] and sorted[9749]. A resample in which m2 detects no
    fault has no fall(D): such resamples are left out, their number is printed,
    and the bounds are taken at the same quantiles of the rest.
    H2 is supported if the lower bound is above 0. The same is reported for
    fall(D) - fall(C), as a secondary result.

Then, none of it confirmatory: per-arm and per-project figures, tests disabled
at acceptance, cost; the sensitivity analyses the protocol lists; the first
campaign's arms beside the second's; EvoSuite beside both.

Reads only files already produced. Needs neither Defects4J nor the model.

Usage:
    ./bin/analyze-campaign2.py                 # data/campaign2
    ./bin/analyze-campaign2.py /path/to/root   # a directory with results/
"""

import contextlib
import csv
import glob
import importlib.util
import io
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRST = os.path.join(ROOT, "data", "agent-metrics-final.csv")
SEED = 20261117
RESAMPLES = 10_000
ALPHA = 0.05
PROJECTS = ("Lang", "Csv", "Gson", "Cli")


def is_count(x):
    return isinstance(x, str) and x.isdigit()


def mcnemar(b, c):
    """Exact two-sided McNemar test on b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def load_metrics(path):
    """{source: {(project, bug): row}} from a merged metrics file."""
    arms = {}
    if not os.path.exists(path):
        return arms
    with open(path) as fh:
        for r in csv.DictReader(fh):
            key = (r["project_id"], r["version_id"].rstrip("f"))
            arms.setdefault(r["test_suite_source"], {})[key] = r
    return arms


def verdict(row):
    return row.get("test_classification") if row else None


def has_verdict(row):
    return verdict(row) in ("Pass", "Fail")


def detected(row):
    return verdict(row) == "Fail"


def has_mutation(row):
    return bool(row) and is_count(row.get("mut_generated")) \
        and int(row["mut_generated"]) > 0 and is_count(row.get("mut_killed"))


def has_coverage(row):
    return bool(row) and is_count(row.get("lines_total")) \
        and int(row["lines_total"]) > 0 and is_count(row.get("lines_covered"))


def rates(arm, keys):
    """Detection rate, pooled mutation score, pooled line coverage."""
    n = len(keys)
    d = sum(detected(arm[k]) for k in keys) / n if n else float("nan")
    gen = sum(int(arm[k]["mut_generated"]) for k in keys if has_mutation(arm[k]))
    kill = sum(int(arm[k]["mut_killed"]) for k in keys if has_mutation(arm[k]))
    lt = sum(int(arm[k]["lines_total"]) for k in keys if has_coverage(arm[k]))
    lc = sum(int(arm[k]["lines_covered"]) for k in keys if has_coverage(arm[k]))
    return d, (kill / gen if gen else float("nan")), (lc / lt if lt else float("nan"))


def mean_mutation(arm, keys):
    vals = [int(arm[k]["mut_killed"]) / int(arm[k]["mut_generated"])
            for k in keys if has_mutation(arm[k])]
    return sum(vals) / len(vals) if vals else float("nan")


def fall(m, s):
    return 1 - s / m if m else float("nan")


def pct(x, digits=1):
    return "-" if x != x else f"{100 * x:.{digits}f}%"


def bootstrap(keys, stat):
    """Percentile interval of stat(resampled keys); None values are dropped."""
    rng = random.Random(SEED)
    n = len(keys)
    values, dropped = [], 0
    for _ in range(RESAMPLES):
        sample = [keys[i] for i in rng.choices(range(n), k=n)]
        v = stat(sample)
        if v is None or v != v:
            dropped += 1
        else:
            values.append(v)
    values.sort()
    if len(values) < RESAMPLES * 0.5:
        return None, None, dropped
    lo = values[int(0.025 * len(values))] if dropped else values[249]
    hi = values[math.ceil(0.975 * len(values)) - 1] if dropped else values[9749]
    return lo, hi, dropped


def two_by_two(a, b, keys):
    both = sum(detected(a[k]) and detected(b[k]) for k in keys)
    only_a = sum(detected(a[k]) and not detected(b[k]) for k in keys)
    only_b = sum(detected(b[k]) and not detected(a[k]) for k in keys)
    neither = len(keys) - both - only_a - only_b
    return both, only_a, only_b, neither


def contrast(M, S, label, lines):
    """H1 and H2 on the given arms; returns the decision tuple."""
    out = lines.append
    paired = sorted(k for k in M if k in S and has_verdict(M[k]) and has_verdict(S[k]))
    complete = [k for k in paired if all(f(a[k]) for a in (M, S)
                                         for f in (has_mutation, has_coverage))]
    out(f"{label}")
    out(f"  paired set {len(paired)} bugs, complete set {len(complete)} bugs")
    if not paired:
        out("  no paired bugs: nothing to test")
        return None
    both, m_only, s_only, neither = two_by_two(M, S, paired)
    dm = (both + m_only) / len(paired)
    ds = (both + s_only) / len(paired)
    p = mcnemar(m_only, s_only)
    out(f"  H1  detection  m2 {both + m_only}/{len(paired)} ({pct(dm)})   "
        f"s2 {both + s_only}/{len(paired)} ({pct(ds)})")
    out(f"      both {both}, m2 only {m_only}, s2 only {s_only}, neither {neither}")
    out(f"      exact McNemar, two-sided: p = {p:.3g}")
    lo, hi, _ = bootstrap(paired, lambda ks: sum(detected(M[k]) for k in ks) / len(ks)
                          - sum(detected(S[k]) for k in ks) / len(ks))
    out(f"      difference {100 * (dm - ds):+.1f} points, 95% bootstrap interval "
        f"[{100 * lo:+.1f}, {100 * hi:+.1f}]")
    h1 = p < ALPHA and dm > ds
    if p < ALPHA and ds > dm:
        out("      *** the difference is significant in the direction opposite to the hypothesis ***")

    if not complete:
        out("  H2  no complete bugs")
        return h1, None, p
    d_m, m_m, c_m = rates(M, complete)
    d_s, m_s, c_s = rates(S, complete)
    out(f"  H2  on the complete set:")
    out(f"      detection       m2 {pct(d_m)}  s2 {pct(d_s)}  fall {pct(fall(d_m, d_s))}")
    out(f"      mutation score  m2 {pct(m_m)}  s2 {pct(m_s)}  fall {pct(fall(m_m, m_s))}"
        f"   (per-suite means {pct(mean_mutation(M, complete))}, {pct(mean_mutation(S, complete))})")
    out(f"      line coverage   m2 {pct(c_m)}  s2 {pct(c_s)}  fall {pct(fall(c_m, c_s))}")

    def stat(which):
        def f(ks):
            dm_, mm_, cm_ = rates(M, ks)
            ds_, ms_, cs_ = rates(S, ks)
            if dm_ == 0:
                return None
            other = fall(mm_, ms_) if which == "M" else fall(cm_, cs_)
            return fall(dm_, ds_) - other
        return f

    h2 = None
    for which, name in (("M", "mutation score"), ("C", "line coverage")):
        point = stat(which)(complete)
        lo, hi, dropped = bootstrap(complete, stat(which))
        if point is None or lo is None:
            out(f"      fall(detection) - fall({name}): not defined (m2 detects nothing)")
            continue
        note = f"; {dropped} resamples without an m2 detection left out" if dropped else ""
        out(f"      fall(detection) - fall({name}) = {100 * point:+.1f} points, "
            f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]{note}")
        if which == "M":
            h2 = lo > 0
    return h1, h2, p


def read_violations(root):
    path = os.path.join(root, "violations.txt")
    out = set()
    if os.path.exists(path):
        for line in open(path):
            parts = line.split("#")[0].split()
            if len(parts) >= 2:
                project, bug = parts[1].rsplit("-", 1)
                out.add((parts[0], (project, bug)))
    return out


def knew_runs(root):
    """Runs whose transcript shows the agent knew the bug (audit-transcripts)."""
    spec = importlib.util.spec_from_file_location(
        "audit", os.path.join(ROOT, "bin", "audit-transcripts.py"))
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    found = set()
    for arm in ("m2", "s2"):
        for path in sorted(glob.glob(os.path.join(root, f"runs-{arm}", "*.stream.jsonl*"))):
            with contextlib.redirect_stdout(io.StringIO()):
                _, _, knew, _ = audit.audit(path, arm, False)
            if knew:
                tag = os.path.basename(path).split(".stream.jsonl")[0]
                project, bug = tag.rsplit("-", 1)
                found.add((arm, (project, bug)))
    return found


def run_records(root, lines):
    out = lines.append
    out("Runs")
    for arm in ("m2", "s2"):
        metas = sorted(glob.glob(os.path.join(root, f"runs-{arm}", "*.meta.json")))
        if not metas:
            out(f"  {arm}: no run records under {root}")
            continue
        models, clis, commits, statuses = set(), set(), set(), {}
        cost = turns = 0
        pruned = total = 0
        for m in metas:
            base = m[:-len(".meta.json")]
            meta = json.load(open(m))
            models.add(meta.get("model_reported_by_run") or meta.get("model"))
            clis.add(meta.get("cli_reported_by_run") or meta.get("cli"))
            commits.add(meta.get("commit"))
            try:
                statuses[os.path.basename(base)] = open(base + ".status").read().strip()
            except OSError:
                statuses[os.path.basename(base)] = "no status"
            try:
                rec = json.load(open(base + ".json"))
                cost += rec.get("total_cost_usd") or 0
                turns += rec.get("num_turns") or 0
            except (OSError, ValueError):
                pass
            try:
                a, b = open(base + ".pruned").read().split()[:2]
                pruned += int(a)
                total += int(b)
            except (OSError, ValueError):
                pass
        ok = sum(1 for s in statuses.values() if s == "ok")
        out(f"  {arm}: {len(metas)} runs, {ok} with an accepted suite; "
            f"${cost:.2f} at list prices, {turns / len(metas):.1f} turns a run")
        out(f"      model {sorted(x for x in models if x)}  CLI {sorted(x for x in clis if x)}  "
            f"commits {sorted(str(c)[:7] for c in commits)}")
        if len(models) > 1 or len(clis) > 1 or len(commits) > 1:
            out("      *** the runs of this arm were not all made under the same model, CLI and commit ***")
        if total:
            out(f"      tests disabled at acceptance: {pruned} of {total} ({pct(pruned / total)})")
        for tag, s in sorted(statuses.items()):
            if s != "ok":
                out(f"      {tag}: {s}")
        cut = glob.glob(os.path.join(root, f"runs-{arm}", "cut-short", "*.json"))
        if cut:
            out(f"      runs cut short by a usage limit and made again: {len(cut)}")
    out("")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = args[0] if args else os.path.join(ROOT, "data", "campaign2")
    lines = []
    out = lines.append

    arms = load_metrics(os.path.join(root, "results", "agent-metrics.csv"))
    if "m2" not in arms or "s2" not in arms:
        print(f"no m2 and s2 rows in {root}/results/agent-metrics.csv: "
              "the campaign has not been measured")
        return
    M, S = arms["m2"], arms["s2"]

    run_records(root, lines)

    violations = read_violations(root)
    out(f"Violations listed in violations.txt: {len(violations)}")
    for arm, key in sorted(violations):
        out(f"  {arm} {'-'.join(key)}")
    out("")

    def without(arm_rows, arm, drop):
        return {k: v for k, v in arm_rows.items() if (arm, k) not in drop}

    Mp, Sp = without(M, "m2", violations), without(S, "s2", violations)

    out("=" * 72)
    decision = contrast(Mp, Sp, "PRIMARY ANALYSIS (runs with a violation left out)", lines)
    out("=" * 72)
    out("")
    if decision:
        h1, h2, p = decision
        out("Decision, by the rule fixed in the protocol:")
        if not h1:
            out("  H1 is not rejected in favour of m2: the central effect is not "
                "supported under controlled conditions.")
        elif h2:
            out("  H1 rejected, and the interval of H2 lies above 0: detection falls "
                "further than mutation score.")
        else:
            out("  H1 rejected, but the interval of H2 includes 0: the fall in "
                "detection is not shown to exceed the fall in mutation score.")
        out("")

    # ---- secondary: per project ------------------------------------------
    paired = sorted(k for k in Mp if k in Sp and has_verdict(Mp[k]) and has_verdict(Sp[k]))
    out("Per project (paired set)")
    for pid in PROJECTS:
        ks = [k for k in paired if k[0] == pid]
        if ks:
            out(f"  {pid:<5} n={len(ks):>2}  m2 detected {sum(detected(Mp[k]) for k in ks)}  "
                f"s2 detected {sum(detected(Sp[k]) for k in ks)}")
    out("")

    out("Suites without a verdict")
    for name, arm in (("m2", M), ("s2", S)):
        bad = sorted("-".join(k) + f" ({verdict(r) or 'none'})" for k, r in arm.items()
                     if not has_verdict(r))
        out(f"  {name}: {', '.join(bad) if bad else 'none'}")
    out("")

    # ---- sensitivity -----------------------------------------------------
    out("SENSITIVITY ANALYSES (none confirmatory)")
    if violations:
        contrast(M, S, "1. Runs with a violation included", lines)
    else:
        out("1. Runs with a violation included: there are none, same as the primary analysis")

    # intention to treat: every bug of the sample attempted in both arms counts,
    # runs with a violation included as measured; no suite or no verdict is a
    # non-detection
    attempted = {}
    for arm in ("m2", "s2"):
        attempted[arm] = set()
        for s in glob.glob(os.path.join(root, f"runs-{arm}", "*.status")):
            project, bug = os.path.basename(s)[:-len(".status")].rsplit("-", 1)
            attempted[arm].add((project, bug))
    itt = sorted(attempted["m2"] & attempted["s2"])
    if itt:
        dm = [bool(k in M and detected(M[k])) for k in itt]
        ds = [bool(k in S and detected(S[k])) for k in itt]
        b = sum(a and not c for a, c in zip(dm, ds))
        c = sum(c and not a for a, c in zip(dm, ds))
        out(f"2. Intention to treat ({len(itt)} bugs attempted in both arms; no suite or no "
            f"verdict counts as not detected; runs with a violation as measured)")
        out(f"      m2 {sum(dm)}/{len(itt)} ({pct(sum(dm) / len(itt))})   "
            f"s2 {sum(ds)}/{len(itt)} ({pct(sum(ds) / len(itt))})   "
            f"m2 only {b}, s2 only {c}; exact McNemar p = {mcnemar(b, c):.3g}")
    else:
        out("2. Intention to treat: no run records found")

    try:
        knew = knew_runs(root)
    except Exception as exc:                      # the transcripts may be absent
        knew = set()
        out(f"3. Runs showing knowledge of the bug: could not read transcripts ({exc})")
    else:
        out(f"3. Runs whose transcript shows the agent knew its bug: {len(knew)}"
            + (" (" + ", ".join(f"{a} {'-'.join(k)}" for a, k in sorted(knew)) + ")" if knew else ""))
        if knew:
            contrast(without(Mp, "m2", knew), without(Sp, "s2", knew),
                     "   with those runs left out", lines)
    out("")

    # ---- the first campaign beside the second ------------------------------
    first = load_metrics(FIRST)
    out("THE FIRST CAMPAIGN BESIDE THE SECOND (descriptive: the campaigns differ in")
    out("more than one respect, see the protocol)")
    for old_name, old_label, new, new_label in (("agent", "first M", Mp, "m2"),
                                                ("spec", "first S", Sp, "s2")):
        old = first.get(old_name, {})
        ks = sorted(k for k in new if k in old and has_verdict(new[k]) and has_verdict(old[k]))
        if not ks:
            out(f"  {old_label} / {new_label}: no bugs in common")
            continue
        both, o_only, n_only, neither = two_by_two(old, new, ks)
        out(f"  {old_label} {both + o_only}/{len(ks)} ({pct((both + o_only) / len(ks))})   "
            f"{new_label} {both + n_only}/{len(ks)} ({pct((both + n_only) / len(ks))})   "
            f"both {both}, {old_label} only {o_only}, {new_label} only {n_only}, neither {neither}; "
            f"exact McNemar p = {mcnemar(o_only, n_only):.3g}")
    evo = first.get("evosuite", {})
    ks = sorted(k for k in Mp if k in Sp and k in evo
                and all(has_verdict(a[k]) for a in (Mp, Sp, evo)))
    if ks:
        out(f"  three generators, {len(ks)} bugs with a verdict from each: "
            f"m2 {sum(detected(Mp[k]) for k in ks)}, "
            f"EvoSuite {sum(detected(evo[k]) for k in ks)}, "
            f"s2 {sum(detected(Sp[k]) for k in ks)} detected")

    print("\n".join(lines))


if __name__ == "__main__":
    main()

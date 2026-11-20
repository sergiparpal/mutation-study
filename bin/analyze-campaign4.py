#!/usr/bin/env python3
"""
Fourth campaign: the analysis its protocol fixes (data/campaign4/PROTOCOL.md).

Written and committed with the protocol, before any run of the campaign. It
reads

  data/campaign4/subjects.txt              the subjects, in the order of the runs,
                                           with the date of the fix, its fault
                                           type and whether the strict reading of
                                           the pool's screen keeps it
  data/campaign4/results/verdicts.csv      bin/measure-campaign4.sh
  data/campaign4/mutation/mutation.csv     bin/mutation-campaign4.sh
  data/campaign4/runs-<arm>/               the records of the runs
  data/campaign4/violations.txt            runs with a violation, decided at
                                           the audit: `arm subject reason`
  data/campaign4/direct-javac.txt          s4 runs that called javac themselves,
                                           listed at the audit, same format
  data/fault-taxonomy.csv                  the Defects4J sample, for the weights

and prints the primary analysis, H2, the composition analysis, the
sensitivity analyses and the descriptive comparisons, in that order. Nothing
in it is chosen after the data.

PRIMARY ANALYSIS
  Paired set: the subjects with a verdict, Pass or Fail, in both arms, runs
  with a violation left out.
  H1: the arms differ in detection. Exact McNemar test, two-sided, at 0.05.
  The difference in detection rate is given with a 95% percentile interval
  from a bootstrap over subjects: 10,000 resamples, both arms of a subject
  kept together, random.Random(20261120).

H2, ASSESSED ONLY IF H1 IS REJECTED WITH m4 ABOVE s4
  The second campaign's H2, computed with that campaign's own functions
  (bin/analyze-campaign2.py), as the third campaign's mutation analysis did:
  on the complete set (paired, and with a mutation score and a line-coverage
  figure in both arms), fall(X) = 1 - X(s4) / X(m4) for detection rate,
  pooled mutation score and pooled line coverage; the statistic is
  fall(D) - fall(M), with that campaign's percentile bootstrap, its seed
  (20261117) and its bounds. Supported if the lower bound is above zero.

COMPOSITION (secondary, no decision rule)
  The detection rate of each fault type in each arm, on the paired set,
  weighted by the type's share in the Defects4J sample: data/fault-taxonomy.csv
  as classified, Csv-16 counted as STATE, API weighing nothing. The difference
  of the weighted rates has a 95% interval from a bootstrap that resamples each
  type's paired subjects within the type: 10,000 resamples,
  random.Random(20261120). A type with no paired subject is reported, and the
  other weights are scaled to sum to one.

Usage:
    ./bin/analyze-campaign4.py                 # data/campaign4
    ./bin/analyze-campaign4.py <directory>     # a dry run's output
"""

import collections
import csv
import glob
import importlib.util
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ("m4", "s4")
SEED = 20261120
RESAMPLES = 10_000
ALPHA = 0.05
WINDOW_END = "2026-09-22"   # the end of the window mined for the matched corpus
TYPES = ("OMISSION", "ALGORITHM", "SUBSTITUTION", "STATE", "MISSING_CLAUSE", "API")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mcnemar(b, c):
    """Exact two-sided McNemar test on b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def pct(x, digits=1):
    return "-" if x != x else f"{100 * x:.{digits}f}%"


def interval(values):
    values = sorted(values)
    return values[int(0.025 * len(values))], values[math.ceil(0.975 * len(values)) - 1]


def bootstrap_difference(pairs, seed=SEED):
    """95% interval of rate(first) - rate(second) over resampled pairs."""
    rng = random.Random(seed)
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    values = []
    for _ in range(RESAMPLES):
        sample = [pairs[i] for i in rng.choices(range(n), k=n)]
        values.append(sum(a - b for a, b in sample) / n)
    return interval(values)


def read_subjects(root):
    """[{tag, date, type, strict}] in the order of the file. A dry run's
    directory may have no list of its own: then the campaign's is read."""
    path = os.path.join(root, "subjects.txt")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "data", "campaign4", "subjects.txt")
    out = []
    for line in open(path):
        parts = line.split("#")[0].split()
        if parts:
            out.append({"tag": parts[0], "date": parts[1], "type": parts[2],
                        "strict": parts[3] == "yes"})
    return out


def read_verdicts(root):
    """{(arm, tag): row}"""
    path = os.path.join(root, "results", "verdicts.csv")
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                out[(r["arm"], r["subject"])] = r
    return out


def read_mutation(root):
    """{(arm, tag): row} from mutation/mutation.csv"""
    path = os.path.join(root, "mutation", "mutation.csv")
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                out[(r["arm"], r["subject"])] = r
    return out


def read_violations(root, name="violations.txt"):
    path = os.path.join(root, name)
    out = set()
    if os.path.exists(path):
        for line in open(path):
            parts = line.split("#")[0].split()
            if len(parts) >= 2:
                out.add((parts[0], parts[1]))
    return out


def status_of(root, arm, tag):
    try:
        return open(os.path.join(root, f"runs-{arm}", tag + ".status")).read().strip()
    except OSError:
        return ""


class Data:
    def __init__(self, root):
        self.root = root
        self.subjects = read_subjects(root)
        self.tags = [s["tag"] for s in self.subjects]
        self.info = {s["tag"]: s for s in self.subjects}
        self.verdicts = read_verdicts(root)
        self.mutation = read_mutation(root)
        self.violations = read_violations(root)

    def verdict(self, arm, tag, timeouts_pass=False):
        row = self.verdicts.get((arm, tag))
        if not row:
            return None
        v = row["verdict"]
        if timeouts_pass and v == "Fail" and row.get("note") == "timeout":
            return "Pass"
        return v

    def paired(self, tags, skip=(), timeouts_pass=False):
        """Tags with Pass or Fail in both arms; runs in `skip` count as absent."""
        out = []
        for t in tags:
            if any((a, t) in skip for a in ARMS):
                continue
            if all(self.verdict(a, t, timeouts_pass) in ("Pass", "Fail") for a in ARMS):
                out.append(t)
        return out

    def detected(self, arm, tag, timeouts_pass=False):
        return self.verdict(arm, tag, timeouts_pass) == "Fail"


def contrast(data, tags, lines, label, skip=(), timeouts_pass=False, intent=False):
    """Detection in the two arms over a set of subjects. Returns (n, m only, s only, p)."""
    out = lines.append
    if intent:
        keys = list(tags)

        def det(arm, t):
            return data.verdict(arm, t) == "Fail"
    else:
        keys = data.paired(tags, skip, timeouts_pass)

        def det(arm, t):
            return data.detected(arm, t, timeouts_pass)
    n = len(keys)
    if n == 0:
        out(f"  {label}: no subject")
        return 0, 0, 0, 1.0
    m = [det("m4", t) for t in keys]
    s = [det("s4", t) for t in keys]
    both = sum(a and b for a, b in zip(m, s))
    m_only = sum(a and not b for a, b in zip(m, s))
    s_only = sum(b and not a for a, b in zip(m, s))
    neither = n - both - m_only - s_only
    p = mcnemar(m_only, s_only)
    lo, hi = bootstrap_difference(list(zip(m, s)))
    out(f"  {label}: {n} subjects")
    out(f"      detection  m4 {sum(m)}/{n} ({pct(sum(m) / n)})   s4 {sum(s)}/{n} ({pct(sum(s) / n)})")
    out(f"      both {both}, m4 only {m_only}, s4 only {s_only}, neither {neither}")
    out(f"      exact McNemar, two-sided: p = {p:.3g}")
    out(f"      difference {100 * (sum(m) - sum(s)) / n:+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    return n, m_only, s_only, p


def run_records(data, lines):
    out = lines.append
    out("Runs")
    for arm in ARMS:
        d = os.path.join(data.root, f"runs-{arm}")
        statuses = {t: status_of(data.root, arm, t) for t in data.tags}
        done = [t for t in data.tags if statuses[t]]
        ok = [t for t in done if statuses[t] == "ok"]
        cost = turns = 0.0
        models, clis, commits = set(), set(), set()
        for t in done:
            try:
                r = json.load(open(os.path.join(d, t + ".json")))
                cost += r.get("total_cost_usd") or 0
                turns += r.get("num_turns") or 0
            except (OSError, ValueError):
                pass
            try:
                m = json.load(open(os.path.join(d, t + ".meta.json")))
                models.add(m.get("model_reported_by_run") or m.get("model"))
                clis.add(m.get("cli_reported_by_run") or m.get("cli"))
                commits.add((m.get("commit") or "")[:7])
            except (OSError, ValueError):
                pass
        left = total = 0
        for t in ok:
            try:
                a, b = open(os.path.join(d, t + ".pruned")).read().split()[:2]
                left += int(a)
                total += int(b)
            except (OSError, ValueError):
                pass
        out(f"  {arm}: {len(done)} runs of {len(data.tags)}, {len(ok)} with an accepted suite; "
            f"${cost:.2f} at list prices, {turns / len(done) if done else 0:.1f} turns a run")
        out(f"      model {sorted(x for x in models if x)}  CLI {sorted(x for x in clis if x)}  "
            f"commits {sorted(x for x in commits if x)}")
        out(f"      tests left out at acceptance: {left} of {total}"
            + (f" ({pct(left / total)})" if total else ""))
        for t in done:
            if statuses[t] != "ok":
                out(f"      no suite: {t}: {statuses[t]}")
    out("")


def without_verdict(data, lines):
    out = lines.append
    out("Subjects outside the paired set")
    any_listed = False
    for t in data.tags:
        reasons = []
        for arm in ARMS:
            if (arm, t) in data.violations:
                reasons.append(f"{arm}: violation")
                continue
            st = status_of(data.root, arm, t)
            row = data.verdicts.get((arm, t))
            if st != "ok":
                reasons.append(f"{arm}: {st or 'no run'}")
            elif not row:
                reasons.append(f"{arm}: not measured")
            elif row["verdict"] not in ("Pass", "Fail"):
                reasons.append(f"{arm}: {row['verdict']} ({row.get('note') or 'no note'})")
        if reasons:
            any_listed = True
            out(f"  {t}: " + "; ".join(reasons))
    if not any_listed:
        out("  none")
    out("")


# ---- H2 ----------------------------------------------------------------------

def rows_for(arm, data, skip=()):
    """The arm's suites in the format the second campaign's functions read."""
    out = {}
    for t in data.tags:
        if (arm, t) in skip:
            continue
        v = data.verdicts.get((arm, t))
        if not v:
            continue
        r = {"test_classification": v["verdict"]}
        m = data.mutation.get((arm, t))
        if m and m["status"] == "ok":
            r.update(mut_generated=m["generated"], mut_killed=m["detected"],
                     lines_total=m["lines_total"], lines_covered=m["lines_covered"])
        out[t] = r
    return out


def h2(c2, M, S, label, lines):
    """The second campaign's H2 on m4 and s4. Returns (point, lo, hi) or None."""
    out = lines.append
    paired = sorted(k for k in M if k in S and c2.has_verdict(M[k]) and c2.has_verdict(S[k]))
    complete = [k for k in paired if all(f(x[k]) for x in (M, S)
                                         for f in (c2.has_mutation, c2.has_coverage))]
    out(label)
    out(f"  paired set {len(paired)} subjects, complete set {len(complete)} subjects")
    if not complete:
        out("  no complete subject: nothing to compute")
        return None
    d_m, m_m, c_m = c2.rates(M, complete)
    d_s, m_s, c_s = c2.rates(S, complete)
    n_m = sum(c2.detected(M[k]) for k in complete)
    n_s = sum(c2.detected(S[k]) for k in complete)
    out(f"      detection       m4 {n_m}/{len(complete)} {pct(d_m)}  s4 {n_s}/{len(complete)} {pct(d_s)}"
        f"  fall {pct(c2.fall(d_m, d_s))}")
    out(f"      mutation score  m4 {pct(m_m)}  s4 {pct(m_s)}  fall {pct(c2.fall(m_m, m_s))}"
        f"   (per-suite means {pct(c2.mean_mutation(M, complete))}, {pct(c2.mean_mutation(S, complete))})")
    out(f"      line coverage   m4 {pct(c_m)}  s4 {pct(c_s)}  fall {pct(c2.fall(c_m, c_s))}")

    def stat(which):
        def f(ks):
            dm_, mm_, cm_ = c2.rates(M, ks)
            ds_, ms_, cs_ = c2.rates(S, ks)
            if dm_ == 0:
                return None
            other = c2.fall(mm_, ms_) if which == "M" else c2.fall(cm_, cs_)
            return c2.fall(dm_, ds_) - other
        return f

    result = None
    for which, name in (("M", "mutation score"), ("C", "line coverage")):
        point = stat(which)(complete)
        lo, hi, dropped = c2.bootstrap(complete, stat(which))
        if point is None or lo is None:
            out(f"      fall(detection) - fall({name}): not defined (m4 detects nothing)")
            continue
        note = f"; {dropped} resamples without an m4 detection left out" if dropped else ""
        out(f"      fall(detection) - fall({name}) = {100 * point:+.1f} points, "
            f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]{note}")
        if which == "M":
            result = (point, lo, hi)
    return result


# ---- composition -------------------------------------------------------------

def sample_weights():
    """{type: share} of the Defects4J sample, Csv-16 counted as STATE."""
    counts = collections.Counter()
    with open(os.path.join(ROOT, "data", "fault-taxonomy.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["phase"] == "pilot":
                continue
            counts["STATE" if r["bug_id"] == "Csv-16" else r["fault_type"]] += 1
    total = sum(counts.values())
    return {t: counts[t] / total for t in TYPES}


def weighted_difference(groups, weights):
    """groups: {type: [(m detected, s detected)]}. Weighted rates and their
    difference, over the types that have a subject; weights rescaled to them."""
    present = [t for t in TYPES if weights[t] > 0 and groups.get(t)]
    total = sum(weights[t] for t in present)
    if not total:
        return float("nan"), float("nan"), float("nan")
    m = sum(weights[t] / total * sum(a for a, _ in groups[t]) / len(groups[t]) for t in present)
    s = sum(weights[t] / total * sum(b for _, b in groups[t]) / len(groups[t]) for t in present)
    return m, s, m - s


def composition(data, lines, skip):
    out = lines.append
    weights = sample_weights()
    keys = data.paired(data.tags, skip)
    groups = collections.defaultdict(list)
    for t in keys:
        groups[data.info[t]["type"]].append((data.detected("m4", t), data.detected("s4", t)))
    out("  type              weight   n   m4 detected   s4 detected")
    for t in TYPES:
        g = groups.get(t, [])
        out(f"  {t:<16} {pct(weights[t]):>7} {len(g):>3}   "
            f"{sum(a for a, _ in g):>4} {pct(sum(a for a, _ in g) / len(g)) if g else '-':>7}"
            f"   {sum(b for _, b in g):>4} {pct(sum(b for _, b in g) / len(g)) if g else '-':>7}")
    missing = [t for t in TYPES if weights[t] > 0 and not groups.get(t)]
    if missing:
        out(f"  no paired subject of type {', '.join(missing)}: the other weights are scaled to sum to one")
    m, s, d = weighted_difference(groups, weights)
    if d != d:
        out("  nothing to weight")
        return
    rng = random.Random(SEED)
    values = []
    for _ in range(RESAMPLES):
        resampled = {t: [g[i] for i in rng.choices(range(len(g)), k=len(g))]
                     for t, g in groups.items() if g}
        values.append(weighted_difference(resampled, weights)[2])
    lo, hi = interval(values)
    out(f"  weighted detection  m4 {pct(m)}  s4 {pct(s)}")
    out(f"  weighted difference {100 * d:+.1f} points, 95% bootstrap interval "
        f"(stratified by type) [{100 * lo:+.1f}, {100 * hi:+.1f}]")


# ---- other campaigns beside this one ------------------------------------------

def beside(lines, label_other, pairs_other, pairs4):
    """Two campaigns' differences, and the difference between them. Descriptive."""
    out = lines.append
    n_o, n4 = len(pairs_other), len(pairs4)
    if not n_o or not n4:
        out("  nothing to compare")
        return
    d_o = sum(a - b for a, b in pairs_other) / n_o
    d4 = sum(a - b for a, b in pairs4) / n4
    out(f"  {label_other}: {sum(a for a, _ in pairs_other)}/{n_o} ({pct(sum(a for a, _ in pairs_other) / n_o)})"
        f" against {sum(b for _, b in pairs_other)}/{n_o} ({pct(sum(b for _, b in pairs_other) / n_o)})"
        f"   difference {100 * d_o:+.1f} points")
    out(f"  fourth campaign, post-cutoff pool: m4 {sum(a for a, _ in pairs4)}/{n4} ({pct(sum(a for a, _ in pairs4) / n4)})"
        f" against s4 {sum(b for _, b in pairs4)}/{n4} ({pct(sum(b for _, b in pairs4) / n4)})"
        f"   difference {100 * d4:+.1f} points")
    rng = random.Random(SEED)
    values = []
    for _ in range(RESAMPLES):
        r4 = [pairs4[i] for i in rng.choices(range(n4), k=n4)]
        ro = [pairs_other[i] for i in rng.choices(range(n_o), k=n_o)]
        values.append(sum(a - b for a, b in r4) / n4 - sum(a - b for a, b in ro) / n_o)
    lo, hi = interval(values)
    out(f"  difference between the two differences {100 * (d4 - d_o):+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")


def third_campaign_pairs():
    c3 = load("analyze3", "analyze-campaign3.py")
    d3 = c3.Data(os.path.join(ROOT, "data", "campaign3"))
    keys = d3.paired(d3.tags, d3.violations)
    return [(d3.verdict("m3", t) == "Fail", d3.verdict("s3", t) == "Fail") for t in keys]


def second_campaign_pairs():
    a2 = load("analyze2", "analyze-campaign2.py")
    c2 = os.path.join(ROOT, "data", "campaign2")
    metrics = a2.load_metrics(os.path.join(c2, "results", "agent-metrics.csv"))
    m2, s2 = metrics.get("m2", {}), metrics.get("s2", {})
    violations = a2.read_violations(c2)
    keys = sorted(k for k in set(m2) & set(s2)
                  if a2.has_verdict(m2[k]) and a2.has_verdict(s2[k])
                  and ("m2", k) not in violations and ("s2", k) not in violations)
    return [(a2.detected(m2[k]), a2.detected(s2[k])) for k in keys]


def by_group(data, lines, label, key):
    out = lines.append
    out(label)
    paired = data.paired(data.tags, data.violations)
    groups = collections.defaultdict(list)
    for t in paired:
        groups[key(t)].append(t)
    for g in sorted(groups):
        tags = groups[g]
        m = sum(data.detected("m4", t) for t in tags)
        s = sum(data.detected("s4", t) for t in tags)
        out(f"  {g:<22} n={len(tags):>3}  m4 detected {m:>3}  s4 detected {s:>3}")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign4")
    data = Data(root)
    lines = []
    out = lines.append

    run_records(data, lines)
    out(f"Violations listed in violations.txt: {len(data.violations)}")
    for arm, tag in sorted(data.violations):
        out(f"  {arm} {tag}")
    out("")

    out("=" * 72)
    out("PRIMARY ANALYSIS (runs with a violation left out)")
    n, m_only, s_only, p = contrast(data, data.tags, lines, "H1, paired set", skip=data.violations)
    out("=" * 72)
    out("")
    h1_m4_above = n > 0 and p < ALPHA and m_only > s_only
    out("Decision on H1, by the rule fixed in the protocol:")
    if n == 0:
        out("  no paired subject: nothing to decide.")
    elif h1_m4_above:
        out("  H1 rejected with m4 above s4: on faults that postdate the model's training")
        out("  data, the arms differ in detection in the direction they do on Defects4J.")
    elif p < ALPHA:
        out("  H1 rejected with s4 above m4: the direction is reversed on these faults.")
    else:
        out("  H1 not rejected: this corpus does not show a difference between the arms.")
        out("  That is not evidence that there is none; the interval above says what it allows.")
    out("")
    without_verdict(data, lines)

    out("=" * 72)
    out("H2: DETECTION FALLS FURTHER THAN MUTATION SCORE (the second campaign's)")
    c2 = load("analyze2", "analyze-campaign2.py")
    expected = {(arm, t) for t in data.tags for arm in ARMS
                if os.path.exists(os.path.join(root, "suites", f"{t}-{arm}.tar.bz2"))}
    for arm in ARMS:
        measured = sum(1 for k in data.mutation if k[0] == arm)
        with_figure = sum(1 for k, r in data.mutation.items() if k[0] == arm and r["status"] == "ok"
                          and int(r["generated"] or 0) > 0 and int(r["lines_total"] or 0) > 0)
        out(f"  {arm}: {measured} of {sum(1 for k in expected if k[0] == arm)} archived suites "
            f"measured with PIT, {with_figure} with a figure")
    result = h2(c2, rows_for("m4", data, data.violations), rows_for("s4", data, data.violations),
                "Complete set, runs with a violation left out", lines)
    out("=" * 72)
    out("Decision on H2, by the rule fixed in the protocol:")
    if not h1_m4_above:
        out("  not assessed: H1 is not rejected with m4 above s4. The figures above are")
        out("  reported, and no decision follows from them.")
    elif result is None:
        out("  H2 cannot be computed: no complete subject, or m4 detects nothing.")
    elif result[1] > 0:
        out("  H2 supported: the lower bound is above zero. Detection falls further between")
        out("  the arms than mutation score does, on faults that postdate the training data.")
    else:
        out("  H2 not supported: the interval includes zero or lies below it. That detection")
        out("  falls further than mutation score is not shown on these faults.")
    out("")

    out("COMPOSITION: DETECTION WEIGHTED BY THE DEFECTS4J SAMPLE'S FAULT TYPES (secondary)")
    composition(data, lines, data.violations)
    out("")

    out("SENSITIVITY ANALYSES (none confirmatory)")
    if data.violations:
        contrast(data, data.tags, lines, "1. Runs with a violation included")
    else:
        out("  1. Runs with a violation included: there are none, same as the primary analysis")
    contrast(data, data.tags, lines,
             "2. Intention to treat (every subject; no suite or no verdict counts as not detected; "
             "runs with a violation as measured)", intent=True)
    try:
        knew = load("audit4", "audit-campaign4.py").knew_runs(root)
    except Exception as exc:
        knew = set()
        out(f"  3. the transcripts could not be read: {exc}")
    out(f"  3. Runs whose transcript names the fix: {len(knew)}"
        + (f" ({', '.join(f'{a} {t}' for a, t in sorted(knew))})" if knew else ""))
    if knew:
        contrast(data, data.tags, lines, "   with those runs left out", skip=data.violations | knew)
    timeouts = sorted(k for k, r in data.verdicts.items() if r["verdict"] == "Fail" and r.get("note") == "timeout")
    out(f"  4. Verdicts that are Fail by timeout: {len(timeouts)}"
        + (f" ({', '.join(f'{a} {t}' for a, t in timeouts)})" if timeouts else ""))
    if timeouts:
        contrast(data, data.tags, lines, "   with those read as Pass", skip=data.violations, timeouts_pass=True)
    direct = read_violations(root, "direct-javac.txt")
    out(f"  5. s4 runs in which the agent called javac itself: {len(direct)}"
        + (f" ({', '.join(t for _, t in sorted(direct))})" if direct else ""))
    if direct:
        contrast(data, data.tags, lines, "   with those runs left out", skip=data.violations | direct)
    strict = [t for t in data.tags if data.info[t]["strict"]]
    contrast(data, strict, lines, f"6. Only the subjects the strict reading keeps ({len(strict)})",
             skip=data.violations)
    out("")

    out("DESCRIPTIVE (no test of this protocol)")
    by_group(data, lines, "By project", lambda t: t.rsplit("-", 1)[0])
    by_group(data, lines, "By fault type", lambda t: data.info[t]["type"])
    by_group(data, lines, f"By date of the fix (up to {WINDOW_END}, the end of the matched corpus's window)",
             lambda t: f"up to {WINDOW_END}" if data.info[t]["date"] <= WINDOW_END else f"after {WINDOW_END}")
    out("")
    keys = data.paired(data.tags, data.violations)
    pairs4 = [(data.detected("m4", t), data.detected("s4", t)) for t in keys]
    out("THE THIRD CAMPAIGN BESIDE THE FOURTH (descriptive: different subjects, selected by")
    out("different rules, run in different sandboxes)")
    try:
        beside(lines, "third campaign, m3 against s3", third_campaign_pairs(), pairs4)
    except Exception as exc:                      # the comparison is not part of any test
        out(f"  the third campaign's results could not be read: {exc}")
    out("")
    out("THE SECOND CAMPAIGN BESIDE THE FOURTH (descriptive: the campaigns differ in more")
    out("than the date of the faults, see the protocol)")
    try:
        beside(lines, "second campaign, Defects4J, m2 against s2", second_campaign_pairs(), pairs4)
    except Exception as exc:
        out(f"  the second campaign's results could not be read: {exc}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()

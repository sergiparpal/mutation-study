#!/usr/bin/env python3
"""
Fifth campaign: the analysis its protocol fixes (data/campaign5/PROTOCOL.md).

Written and committed with the protocol, before any run of the campaign. It
reads

  data/campaign5/subjects.txt              the subjects, in the order of the runs,
                                           with the date of the fix, its fault
                                           type and whether the strict reading of
                                           the pool's screen keeps it
  data/campaign5/results/verdicts.csv      bin/measure-campaign5.sh
  data/campaign5/mutation/mutation.csv     bin/mutation-campaign5.sh
  data/campaign5/runs-<arm>/               the records of the runs
  data/campaign5/violations.txt            runs with a violation, decided at
                                           the audit: `arm subject reason`
  data/campaign5/closing-b5.txt            b5 runs whose closing message says
                                           the code under test is wrong, listed
                                           at the audit: `b5 subject words`
  data/campaign4/results/verdicts.csv      the fourth campaign's verdicts, for
                                           the descriptive comparisons

and prints the estimate, H1, the secondary outcomes, the sensitivity analyses
and the descriptive comparisons, in that order. Nothing in it is chosen after
the data.

THE ESTIMATE
  The certification rate: b5's share of Fail among its subjects with a
  verdict, runs with a violation left out, with a 95% percentile interval
  from 10,000 bootstrap resamples of those subjects, random.Random(20261122).

PRIMARY ANALYSIS
  Paired set: the subjects with a verdict, Pass or Fail, in both arms, runs
  with a violation left out. A Fail is certification in b5 and detection in
  m5.
  H1: certification in b5 and detection in m5 differ. Exact McNemar test,
  two-sided, at 0.05. The difference b5 - m5 is given with a 95% percentile
  interval from a bootstrap over subjects: 10,000 resamples, both arms of a
  subject kept together, random.Random(20261122).

MUTATION SCORE (secondary, no decision rule)
  On the complete set (paired, and with a mutation score and a line-coverage
  figure in both arms): each arm's pooled mutation score and line coverage on
  its own revision, and the difference b5 - m5 with a 95% interval from
  10,000 bootstrap resamples of the subjects. The pooled scores of the suites
  that certify (b5) and of those that detect (m5) are also given.

Usage:
    ./bin/analyze-campaign5.py                 # data/campaign5
    ./bin/analyze-campaign5.py <directory>     # a dry run's output
"""

import csv
import importlib.util
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ("b5", "m5")
SEED = 20261122
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


def bootstrap_rate(flags, seed=SEED):
    """95% interval of the share of True among resampled flags."""
    rng = random.Random(seed)
    n = len(flags)
    if n == 0:
        return float("nan"), float("nan")
    return interval([sum(flags[i] for i in rng.choices(range(n), k=n)) / n
                     for _ in range(RESAMPLES)])


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
    """[{tag, date, type, strict, project}] in the order of the file. A dry
    run's directory may have no list of its own: then the campaign's is read."""
    path = os.path.join(root, "subjects.txt")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "data", "campaign5", "subjects.txt")
    out = []
    for line in open(path):
        parts = line.split("#")[0].split()
        if parts:
            out.append({"tag": parts[0], "date": parts[1], "type": parts[2],
                        "strict": parts[3] == "yes", "project": parts[0].rsplit("-", 1)[0]})
    return out


def read_csv(path):
    """{(arm, tag): row}"""
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                out[(r["arm"], r["subject"])] = r
    return out


def read_listed(root, name):
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
        self.verdicts = read_csv(os.path.join(root, "results", "verdicts.csv"))
        self.mutation = read_csv(os.path.join(root, "mutation", "mutation.csv"))
        self.violations = read_listed(root, "violations.txt")
        self.closing = read_listed(root, "closing-b5.txt")

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
        return [t for t in tags
                if not any((a, t) in skip for a in ARMS)
                and all(self.verdict(a, t, timeouts_pass) in ("Pass", "Fail") for a in ARMS)]

    def fail(self, arm, tag, timeouts_pass=False):
        return self.verdict(arm, tag, timeouts_pass) == "Fail"

    def scored(self, arm, tag):
        """A mutation row with a figure: status ok, mutants and lines counted."""
        r = self.mutation.get((arm, tag))
        return bool(r) and r["status"] == "ok" and int(r["generated"] or 0) > 0 \
            and int(r["lines_total"] or 0) > 0


# ---- the estimate and H1 -------------------------------------------------------

def certification_rate(data, lines, skip):
    out = lines.append
    keys = [t for t in data.tags if ("b5", t) not in skip
            and data.verdict("b5", t) in ("Pass", "Fail")]
    flags = [data.fail("b5", t) for t in keys]
    out("The certification rate (b5)")
    if not keys:
        out("  no b5 subject has a verdict")
        out("")
        return
    lo, hi = bootstrap_rate(flags)
    out(f"  {sum(flags)} of {len(keys)} suites certify the fault ({pct(sum(flags) / len(keys))}); "
        f"95% bootstrap interval [{pct(lo)}, {pct(hi)}]")
    out("")


def contrast(data, tags, lines, label, skip=(), timeouts_pass=False, intent=False):
    """Certification in b5 against detection in m5. Returns (n, b5 only, m5 only, p)."""
    out = lines.append
    if intent:
        keys = list(tags)

        def fail(arm, t):
            return data.verdict(arm, t) == "Fail"
    else:
        keys = data.paired(tags, skip, timeouts_pass)

        def fail(arm, t):
            return data.fail(arm, t, timeouts_pass)
    n = len(keys)
    if n == 0:
        out(f"  {label}: no subject")
        return 0, 0, 0, 1.0
    b = [fail("b5", t) for t in keys]
    m = [fail("m5", t) for t in keys]
    both = sum(x and y for x, y in zip(b, m))
    b_only = sum(x and not y for x, y in zip(b, m))
    m_only = sum(y and not x for x, y in zip(b, m))
    neither = n - both - b_only - m_only
    p = mcnemar(b_only, m_only)
    lo, hi = bootstrap_difference(list(zip(b, m)))
    out(f"  {label}: {n} subjects")
    out(f"      b5 certifies {sum(b)}/{n} ({pct(sum(b) / n)})   m5 detects {sum(m)}/{n} ({pct(sum(m) / n)})")
    out(f"      both {both}, b5 only {b_only}, m5 only {m_only}, neither {neither}")
    out(f"      exact McNemar, two-sided: p = {p:.3g}")
    out(f"      difference b5 - m5 {100 * (sum(b) - sum(m)) / n:+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    return n, b_only, m_only, p


def decision(n, b_only, m_only, p, lines):
    out = lines.append
    if n == 0:
        out("  Outcome: no paired subject, so no outcome")
    elif p >= ALPHA:
        out("  Outcome: H1 not rejected. Shown the faulty code, the agent's suites lock the")
        out("  fault in about as often as, shown the repaired code, they detect it; the")
        out("  interval says how far apart the two rates could be")
    elif b_only < m_only:
        out("  Outcome: H1 rejected, b5 below m5. The sign of the effect follows the")
        out("  revision the agent reads, but its size does not")
    else:
        out("  Outcome: H1 rejected, b5 above m5. The fault is locked in more often than")
        out("  the repair is detected")


# ---- secondary outcomes ----------------------------------------------------------

def pooled(data, arm, keys):
    det = sum(int(data.mutation[(arm, t)]["detected"]) for t in keys)
    gen = sum(int(data.mutation[(arm, t)]["generated"]) for t in keys)
    cov = sum(int(data.mutation[(arm, t)]["lines_covered"]) for t in keys)
    tot = sum(int(data.mutation[(arm, t)]["lines_total"]) for t in keys)
    return (det / gen if gen else float("nan")), (cov / tot if tot else float("nan"))


def mutation_section(data, lines, skip):
    out = lines.append
    out("Mutation score and line coverage, each arm on its own revision (secondary)")
    paired = data.paired(data.tags, skip)
    keys = [t for t in paired if all(data.scored(a, t) for a in ARMS)]
    out(f"  complete set: {len(keys)} of the {len(paired)} paired subjects")
    if not keys:
        out("")
        return
    rng = random.Random(SEED)
    for what, index in (("mutation score", 0), ("line coverage", 1)):
        b = pooled(data, "b5", keys)[index]
        m = pooled(data, "m5", keys)[index]
        values = []
        for _ in range(RESAMPLES):
            sample = [keys[i] for i in rng.choices(range(len(keys)), k=len(keys))]
            values.append(pooled(data, "b5", sample)[index] - pooled(data, "m5", sample)[index])
        lo, hi = interval([v for v in values if v == v])
        out(f"  pooled {what}: b5 {pct(b)}   m5 {pct(m)}   difference {100 * (b - m):+.1f} points, "
            f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    cert = [t for t in keys if data.fail("b5", t)]
    det = [t for t in keys if data.fail("m5", t)]
    for arm, label, group in (("b5", "b5 suites that certify", cert), ("m5", "m5 suites that detect", det)):
        if group:
            s, c = pooled(data, arm, group)
            out(f"  {label}: {len(group)}; pooled mutation score {pct(s)}, line coverage {pct(c)}")
        else:
            out(f"  {label}: none")
    out("")


def kept_methods(data, lines):
    """PIT's kept methods against the methods the measurement ran on the own revision."""
    out = lines.append
    out("The tests PIT ran against the tests the measurement ran")
    checked = agree = 0
    for arm in ARMS:
        for t in data.tags:
            r, v = data.mutation.get((arm, t)), data.verdicts.get((arm, t))
            if not r or not v or r["status"] != "ok":
                continue
            checked += 1
            if int(r["methods_kept"]) == int(v["methods_run_on_own"] or -1) \
                    and r["methods_left_out"] == r["keys_excluded"]:
                agree += 1
            else:
                out(f"  {t} {arm}: kept {r['methods_kept']}, measurement ran {v['methods_run_on_own']}; "
                    f"left out {r['methods_left_out']} of {r['keys_excluded']} keys")
    out(f"  {agree} of {checked} suites with a mutation figure agree")
    out("")


def left_out_section(data, lines, skip):
    out = lines.append
    out("Tests left out at acceptance, run on the other revision (secondary)")
    for arm, meaning in (("b5", "expected the repaired behaviour"), ("m5", "expected the faulty behaviour")):
        suites = ran = passed = with_any = 0
        for t in data.tags:
            v = data.verdicts.get((arm, t))
            if not v or (arm, t) in skip or not v.get("left_out_methods_run_on_other"):
                continue
            suites += 1
            ran += int(v["left_out_methods_run_on_other"])
            p = int(v["left_out_passing_on_other"] or 0)
            passed += p
            with_any += p > 0
        out(f"  {arm}: {suites} suites had tests left out and run on the other revision; "
            f"{passed} of {ran} such methods pass there ({meaning}), in {with_any} suites")
    out(f"  b5 runs whose closing message says the code under test is wrong: "
        f"{sum(1 for a, _ in data.closing if a == 'b5')}")
    out("")


# ---- records, exclusions --------------------------------------------------------

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
    listed = False
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
            listed = True
            out(f"  {t}: " + "; ".join(reasons))
    if not listed:
        out("  none")
    out("")


# ---- descriptive comparisons ------------------------------------------------------

def by_group(data, lines, label, key, skip):
    out = lines.append
    out(f"  by {label}")
    groups = {}
    for t in data.paired(data.tags, skip):
        groups.setdefault(key(data.info[t]), []).append(t)
    for g in sorted(groups):
        ts = groups[g]
        b = sum(data.fail("b5", t) for t in ts)
        m = sum(data.fail("m5", t) for t in ts)
        out(f"      {g:<22} {len(ts):>3} subjects   b5 certifies {b:>3}   m5 detects {m:>3}")


def agreement(lines, label, first, second, tags):
    """Two sets of verdicts on the same subjects: counts and Cohen's kappa."""
    out = lines.append
    keys = [t for t in tags if first.get(t) in ("Pass", "Fail") and second.get(t) in ("Pass", "Fail")]
    n = len(keys)
    if not n:
        out(f"  {label}: no subject with a verdict in both")
        return
    a = [first[t] == "Fail" for t in keys]
    b = [second[t] == "Fail" for t in keys]
    both = sum(x and y for x, y in zip(a, b))
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    po = (n - only_a - only_b) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    out(f"  {label}: {n} subjects; Fail in both {both}, only the first {only_a}, only the second "
        f"{only_b}; agreement {pct(po)}, Cohen's kappa {kappa:.2f}")


def descriptive(data, lines, skip):
    out = lines.append
    out("Descriptive comparisons (none is a test of the protocol)")
    by_group(data, lines, "project", lambda s: s["project"], skip)
    by_group(data, lines, "fault type", lambda s: s["type"], skip)
    by_group(data, lines, f"date of the fix (up to {WINDOW_END} or after)",
             lambda s: "up to " + WINDOW_END if s["date"] <= WINDOW_END else "after", skip)
    four = read_csv(os.path.join(ROOT, "data", "campaign4", "results", "verdicts.csv"))
    tags = [t for t in data.tags if not any((a, t) in skip for a in ARMS)]
    m4 = {t: four[("m4", t)]["verdict"] for t in tags if ("m4", t) in four}
    s4 = {t: four[("s4", t)]["verdict"] for t in tags if ("s4", t) in four}
    m5 = {t: data.verdict("m5", t) for t in tags}
    b5 = {t: data.verdict("b5", t) for t in tags}
    agreement(lines, "m4 (first) beside m5 (second), the same condition run twice", m4, m5, tags)
    agreement(lines, "s4 (first) beside b5 (second), neither shown the repair", s4, b5, tags)
    out("")


# ---- main -------------------------------------------------------------------------

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign5")
    data = Data(root)
    lines = []
    out = lines.append
    out(f"Fifth campaign: {len(data.tags)} subjects, arms {', '.join(ARMS)}; "
        f"seed {SEED}, {RESAMPLES} resamples")
    out("")
    run_records(data, lines)
    without_verdict(data, lines)
    skip = data.violations
    out("Runs with a violation: " + (", ".join(f"{a} {t}" for a, t in sorted(skip)) or "none"))
    out("")
    certification_rate(data, lines, skip)
    out("H1: certification in b5 and detection in m5 differ")
    n, b_only, m_only, p = contrast(data, data.tags, lines, "paired set", skip=skip)
    decision(n, b_only, m_only, p, lines)
    out("")
    mutation_section(data, lines, skip)
    kept_methods(data, lines)
    left_out_section(data, lines, skip)

    out("Sensitivity analyses (none is confirmatory)")
    contrast(data, data.tags, lines, "1. runs with a violation included")
    contrast(data, data.tags, lines, "2. intention to treat", intent=True)
    try:
        knew = load("audit_campaign5", "audit-campaign5.py").knew_runs(root)
    except Exception as e:                     # a dry run has no transcripts
        knew = set()
        out(f"  (the runs that name the fix could not be read: {e})")
    out(f"  runs that name the fix: {len(knew)}"
        + (" — " + ", ".join(f"{a} {t}" for a, t in sorted(knew)) if knew else ""))
    contrast(data, data.tags, lines, "3. runs that name the fix left out", skip=skip | knew)
    contrast(data, data.tags, lines, "4. Fail by timeout read as Pass", skip=skip, timeouts_pass=True)
    strict = [t for t in data.tags if data.info[t]["strict"]]
    contrast(data, strict, lines, f"5. the strict screen's subjects only ({len(strict)})", skip=skip)
    out("")
    descriptive(data, lines, skip)
    print("\n".join(lines))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Third campaign: the analysis its protocol fixes (data/campaign3/PROTOCOL.md).

Written and committed before any run of the campaign. It reads

  data/campaign3/subjects.txt              the subjects, in the order of the runs
  data/campaign3/results/verdicts.csv      bin/measure-campaign3.sh
  data/campaign3/runs-<arm>/               the records of the runs
  data/campaign3/violations.txt            runs with a violation, decided at
                                           the audit: `arm subject reason`

and prints the primary analysis, the sensitivity analyses and the descriptive
comparisons, in that order. Nothing in it is chosen after the data.

PRIMARY ANALYSIS
  Paired set: the subjects with a verdict, Pass or Fail, in both arms, runs
  with a violation left out.
  H1: the arms differ in detection. Exact McNemar test, two-sided, at 0.05.
  The difference in detection rate is given with a 95% percentile interval
  from a bootstrap over subjects: 10,000 resamples, both arms of a subject
  kept together, random.Random(20261118).

Mutation score and coverage are not measured in this campaign, so the second
campaign's H2 has no counterpart here.

Usage:
    ./bin/analyze-campaign3.py                 # data/campaign3
    ./bin/analyze-campaign3.py <directory>     # a dry run's output
"""

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
ARMS = ("m3", "s3")
SEED = 20261118
RESAMPLES = 10_000
ALPHA = 0.05


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
    """[(tag, corpus, fault type)] in the order of the file."""
    out = []
    for line in open(os.path.join(root, "subjects.txt")):
        parts = line.split("#")[0].split()
        if parts:
            out.append((parts[0], parts[1] if len(parts) > 1 else "",
                        parts[2] if len(parts) > 2 else "-"))
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


def read_violations(root):
    path = os.path.join(root, "violations.txt")
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
        self.tags = [s[0] for s in self.subjects]
        self.verdicts = read_verdicts(root)
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
            return data.verdict(arm, t, timeouts_pass) == "Fail"
    n = len(keys)
    if n == 0:
        out(f"  {label}: no subject")
        return 0, 0, 0, 1.0
    m = [det("m3", t) for t in keys]
    s = [det("s3", t) for t in keys]
    both = sum(a and b for a, b in zip(m, s))
    m_only = sum(a and not b for a, b in zip(m, s))
    s_only = sum(b and not a for a, b in zip(m, s))
    neither = n - both - m_only - s_only
    p = mcnemar(m_only, s_only)
    lo, hi = bootstrap_difference(list(zip(m, s)))
    out(f"  {label}: {n} subjects")
    out(f"      detection  m3 {sum(m)}/{n} ({pct(sum(m) / n)})   s3 {sum(s)}/{n} ({pct(sum(s) / n)})")
    out(f"      both {both}, m3 only {m_only}, s3 only {s_only}, neither {neither}")
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


def second_campaign(data, lines, m3_s3_pairs):
    """The second campaign's paired set beside this one's. Descriptive."""
    out = lines.append
    try:
        a2 = load("analyze2", "analyze-campaign2.py")
        c2 = os.path.join(ROOT, "data", "campaign2")
        metrics = a2.load_metrics(os.path.join(c2, "results", "agent-metrics.csv"))
        m2, s2 = metrics.get("m2", {}), metrics.get("s2", {})
        violations = a2.read_violations(c2)
        keys = sorted(k for k in set(m2) & set(s2)
                      if a2.has_verdict(m2[k]) and a2.has_verdict(s2[k])
                      and ("m2", k) not in violations and ("s2", k) not in violations)
    except Exception as exc:                      # the comparison is not part of any test
        out(f"  the second campaign's results could not be read: {exc}")
        return
    pairs2 = [(a2.detected(m2[k]), a2.detected(s2[k])) for k in keys]
    n2, n3 = len(pairs2), len(m3_s3_pairs)
    if not n2 or not n3:
        out("  nothing to compare")
        return
    d2 = sum(a - b for a, b in pairs2) / n2
    d3 = sum(a - b for a, b in m3_s3_pairs) / n3
    out(f"  second campaign, Defects4J:   m2 {sum(a for a, _ in pairs2)}/{n2} ({pct(sum(a for a, _ in pairs2) / n2)})"
        f"   s2 {sum(b for _, b in pairs2)}/{n2} ({pct(sum(b for _, b in pairs2) / n2)})"
        f"   difference {100 * d2:+.1f} points")
    out(f"  third campaign, post-cutoff:  m3 {sum(a for a, _ in m3_s3_pairs)}/{n3} ({pct(sum(a for a, _ in m3_s3_pairs) / n3)})"
        f"   s3 {sum(b for _, b in m3_s3_pairs)}/{n3} ({pct(sum(b for _, b in m3_s3_pairs) / n3)})"
        f"   difference {100 * d3:+.1f} points")
    # each campaign's subjects resampled on their own
    rng = random.Random(SEED)
    values = []
    for _ in range(RESAMPLES):
        r3 = [m3_s3_pairs[i] for i in rng.choices(range(n3), k=n3)]
        r2 = [pairs2[i] for i in rng.choices(range(n2), k=n2)]
        values.append(sum(a - b for a, b in r3) / n3 - sum(a - b for a, b in r2) / n2)
    lo, hi = interval(values)
    out(f"  difference between the two differences {100 * (d3 - d2):+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")


def earlier_runs(data, lines):
    """The two earlier post-cutoff corpora beside this campaign, subject by subject."""
    out = lines.append
    try:
        tally = load("tally", "tally-postcutoff.py")
    except Exception as exc:
        out(f"  the earlier runs could not be read: {exc}")
        return
    earlier = {}                                   # (old arm, tag) -> verdict, latest corpus wins
    for d in ("postcutoff-first-runs", "postcutoff-runs"):
        for arm in ("agent", "spec"):
            for path in glob.glob(os.path.join(ROOT, "data", d, f"*.{arm}.status")):
                tag = os.path.basename(path).split(".")[0]
                if (tally.read(path) or "").strip() != "ok":
                    continue
                log = tally.read(path[:-len("status")] + "buggy.log")
                v = tally.derive(log) if log is not None else ""
                if v in ("Pass", "Fail"):
                    earlier[(arm, tag)] = v
    for old, new, label in (("agent", "m3", "implementation-visible"), ("spec", "s3", "specification-only")):
        keys = [t for t in data.tags if (old, t) in earlier
                and data.verdict(new, t) in ("Pass", "Fail") and (new, t) not in data.violations]
        a = [earlier[(old, t)] == "Fail" for t in keys]
        b = [data.verdict(new, t) == "Fail" for t in keys]
        n = len(keys)
        if not n:
            out(f"  {label}: no subject with a valid verdict in both")
            continue
        both = sum(x and y for x, y in zip(a, b))
        only_old = [t for t, x, y in zip(keys, a, b) if x and not y]
        only_new = [t for t, x, y in zip(keys, a, b) if y and not x]
        out(f"  {label}, {n} subjects with a valid verdict in both: earlier {sum(a)}, {new} {sum(b)}, both {both}")
        out(f"      earlier only: {', '.join(only_old) or 'none'}")
        out(f"      {new} only: {', '.join(only_new) or 'none'}")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign3")
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
    out("Decision, by the rule fixed in the protocol:")
    if n == 0:
        out("  no paired subject: nothing to decide.")
    elif p < ALPHA and m_only > s_only:
        out("  H1 rejected with m3 above s3: on faults that postdate the model's training")
        out("  data, the arms differ in detection in the direction of the earlier campaigns.")
    elif p < ALPHA:
        out("  H1 rejected with s3 above m3: the direction of the earlier campaigns is reversed.")
    else:
        out("  H1 not rejected: this corpus does not show a difference between the arms.")
        out("  That is not evidence that there is none; the interval above says what it allows.")
    out("")
    without_verdict(data, lines)

    out("SENSITIVITY ANALYSES (none confirmatory)")
    if data.violations:
        contrast(data, data.tags, lines, "1. Runs with a violation included")
    else:
        out("  1. Runs with a violation included: there are none, same as the primary analysis")
    contrast(data, data.tags, lines,
             "2. Intention to treat (every subject; no suite or no verdict counts as not detected; "
             "runs with a violation as measured)", intent=True)
    try:
        knew = load("audit3", "audit-campaign3.py").knew_runs(root)
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
    out("")

    out("DESCRIPTIVE (no test of this protocol)")
    out("By corpus the subject was mined for")
    for corpus, label in (("matched", "matched corpus"), ("first", "first corpus")):
        tags = [t for t, c, _ in data.subjects if c in (corpus, "both")]
        contrast(data, tags, lines, label, skip=data.violations)
    out("By project")
    for project in sorted({t.rsplit("-", 1)[0] for t in data.tags}):
        tags = [t for t in data.paired(data.tags, data.violations) if t.rsplit("-", 1)[0] == project]
        m = sum(data.verdict("m3", t) == "Fail" for t in tags)
        s = sum(data.verdict("s3", t) == "Fail" for t in tags)
        out(f"  {project:<13} n={len(tags):>2}  m3 detected {m}  s3 detected {s}")
    out("By fault type (subjects of the matched corpus, as classified when it was built)")
    paired = set(data.paired(data.tags, data.violations))
    for ftype in sorted({f for _, _, f in data.subjects if f != "-"}):
        tags = [t for t, _, f in data.subjects if f == ftype and t in paired]
        m = sum(data.verdict("m3", t) == "Fail" for t in tags)
        s = sum(data.verdict("s3", t) == "Fail" for t in tags)
        out(f"  {ftype:<15} n={len(tags):>2}  m3 detected {m}  s3 detected {s}")
    out("")
    out("THE SECOND CAMPAIGN BESIDE THE THIRD (descriptive: the campaigns differ in more")
    out("than the date of the faults, see the protocol)")
    keys = data.paired(data.tags, data.violations)
    second_campaign(data, lines, [(data.verdict("m3", t) == "Fail", data.verdict("s3", t) == "Fail") for t in keys])
    out("")
    out("THE EARLIER POST-CUTOFF RUNS BESIDE THIS CAMPAIGN (descriptive)")
    earlier_runs(data, lines)

    print("\n".join(lines))


if __name__ == "__main__":
    main()

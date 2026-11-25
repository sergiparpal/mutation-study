#!/usr/bin/env python3
"""
Sixth campaign: the analysis its protocol fixes (data/campaign6/PROTOCOL.md).

Written with the protocol, before any run of the campaign, from the fifth
campaign's bin/analyze-campaign5.py. It reads

  data/campaign6/subjects.txt              the subjects, in the order of the runs,
                                           with the date of the fix, its fault
                                           type and whether the strict reading of
                                           the pool's screen keeps it
  data/campaign6/results/verdicts.csv      bin/measure-campaign6.sh
  data/campaign6/mutation/mutation.csv     bin/mutation-campaign6.sh
  data/campaign6/runs-<arm>/               the records of the runs
  data/campaign6/violations.txt            runs with a violation, decided at
                                           the audit: `arm subject reason`
  data/campaign6/closing-f6.txt            f6 runs whose closing message names a
                                           test as showing a bug, listed at the
                                           audit: `f6 subject fault|other words`
  data/campaign5/results/verdicts.csv      the fifth campaign's verdicts, and
  data/campaign5/runs-b5/                  its b5 runs, for the certification
                                           beside b5's and the descriptive
                                           comparisons
  data/campaign4/results/verdicts.csv      the fourth campaign's verdicts, for
                                           the descriptive comparisons

and prints the estimate, H1, the secondary outcomes, the sensitivity analyses
and the descriptive comparisons, in that order. Nothing in it is chosen after
the data.

THE ESTIMATE
  The detection rate when asked to look for faults: f6's share of Fail in
  detection among its subjects with a detection verdict, runs with a violation
  left out, with a 95% percentile interval from 10,000 bootstrap resamples of
  those subjects, random.Random(20261125).

PRIMARY ANALYSIS
  Paired set: the subjects with a detection verdict, Pass or Fail, in both
  arms, runs with a violation left out.
  H1: detection in f6 and detection in m6 differ. Exact McNemar test,
  two-sided, at 0.05. The difference f6 - m6 is given with a 95% percentile
  interval from a bootstrap over subjects: 10,000 resamples, both arms of a
  subject kept together, random.Random(20261125).

SECONDARY (no decision rule)
  Certification in f6, with its interval, beside b5's on the same subjects;
  the false alarms; the closing messages; the left-out tests of m6; mutation
  score and line coverage on the complete set, pooled, f6 - m6 with a 95%
  interval from 10,000 bootstrap resamples of the subjects.

Usage:
    ./bin/analyze-campaign6.py                 # data/campaign6
    ./bin/analyze-campaign6.py <directory>     # a dry run's output
"""

import csv
import importlib.util
import json
import math
import os
import random
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ("f6", "m6")
SEED = 20261125
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
        path = os.path.join(ROOT, "data", "campaign6", "subjects.txt")
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


def read_closing(root):
    """{subject: 'fault' or 'other'} from closing-f6.txt"""
    path = os.path.join(root, "closing-f6.txt")
    out = {}
    if os.path.exists(path):
        for line in open(path):
            parts = line.split("#")[0].split()
            if len(parts) >= 3 and parts[0] == "f6":
                if parts[2] not in ("fault", "other"):
                    sys.exit(f"closing-f6.txt: neither fault nor other: {line.strip()}")
                out[parts[1]] = parts[2]
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
        self.closing = read_closing(root)

    def detection(self, arm, tag, timeouts_none=False):
        row = self.verdicts.get((arm, tag))
        if not row:
            return None
        v = row["detection"]
        if timeouts_none and v == "Fail" and row.get("detection_note") == "timeout":
            return "Pass"
        return v

    def paired(self, tags, skip=(), timeouts_none=False):
        """Tags with a detection verdict in both arms; runs in `skip` count as absent."""
        return [t for t in tags
                if not any((a, t) in skip for a in ARMS)
                and all(self.detection(a, t, timeouts_none) in ("Pass", "Fail") for a in ARMS)]

    def detects(self, arm, tag, timeouts_none=False):
        return self.detection(arm, tag, timeouts_none) == "Fail"

    def certification(self, tag):
        """f6's verdict on the suite as accepted: Fail certifies the fault."""
        row = self.verdicts.get(("f6", tag))
        return row["verdict"] if row else None

    def scored(self, arm, tag):
        """A mutation row with a figure: status ok, mutants and lines counted."""
        r = self.mutation.get((arm, tag))
        return bool(r) and r["status"] == "ok" and int(r["generated"] or 0) > 0 \
            and int(r["lines_total"] or 0) > 0


# ---- the estimate and H1 -------------------------------------------------------

def detection_rate(data, lines, skip):
    out = lines.append
    keys = [t for t in data.tags if ("f6", t) not in skip
            and data.detection("f6", t) in ("Pass", "Fail")]
    flags = [data.detects("f6", t) for t in keys]
    out("The detection rate when asked to look for faults (f6)")
    if not keys:
        out("  no f6 subject has a detection verdict")
        out("")
        return
    lo, hi = bootstrap_rate(flags)
    out(f"  {sum(flags)} of {len(keys)} suites detect the fault ({pct(sum(flags) / len(keys))}); "
        f"95% bootstrap interval [{pct(lo)}, {pct(hi)}]")
    out("")


def contrast(data, tags, lines, label, skip=(), timeouts_none=False, intent=False, f6_detects=None):
    """Detection in f6 against detection in m6. Returns (n, f6 only, m6 only, p)."""
    out = lines.append
    if intent:
        keys = list(tags)

        def det(arm, t):
            return data.detection(arm, t) == "Fail"
    else:
        keys = data.paired(tags, skip, timeouts_none)

        def det(arm, t):
            return data.detects(arm, t, timeouts_none)
    if f6_detects is not None:
        inner = det

        def det(arm, t):
            return f6_detects(t) if arm == "f6" else inner(arm, t)
    n = len(keys)
    if n == 0:
        out(f"  {label}: no subject")
        return 0, 0, 0, 1.0
    f = [det("f6", t) for t in keys]
    m = [det("m6", t) for t in keys]
    both = sum(x and y for x, y in zip(f, m))
    f_only = sum(x and not y for x, y in zip(f, m))
    m_only = sum(y and not x for x, y in zip(f, m))
    neither = n - both - f_only - m_only
    p = mcnemar(f_only, m_only)
    lo, hi = bootstrap_difference(list(zip(f, m)))
    out(f"  {label}: {n} subjects")
    out(f"      f6 detects {sum(f)}/{n} ({pct(sum(f) / n)})   m6 detects {sum(m)}/{n} ({pct(sum(m) / n)})")
    out(f"      both {both}, f6 only {f_only}, m6 only {m_only}, neither {neither}")
    out(f"      exact McNemar, two-sided: p = {p:.3g}")
    out(f"      difference f6 - m6 {100 * (sum(f) - sum(m)) / n:+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    return n, f_only, m_only, p


def decision(n, f_only, m_only, p, lines):
    out = lines.append
    if n == 0:
        out("  Outcome: no paired subject, so no outcome")
    elif p >= ALPHA:
        out("  Outcome: H1 not rejected. Asked to look for faults, the agent shown the faulty")
        out("  code detects the fault about as often as the agent shown the repair; the")
        out("  interval says how far apart the two rates could be")
    elif f_only < m_only:
        out("  Outcome: H1 rejected, f6 below m6. Even asked to look for faults, the agent")
        out("  shown the faulty code detects the fault less often than the regression setting")
        out("  credits; the difference and its interval measure by how much")
    else:
        out("  Outcome: H1 rejected, f6 above m6. Asked to look for faults, the agent")
        out("  detects more than the regression setting credits")


# ---- secondary outcomes ----------------------------------------------------------

def certification_section(data, lines, skip):
    out = lines.append
    out("Certification under the request (secondary)")
    keys = [t for t in data.tags if ("f6", t) not in skip and data.certification(t) in ("Pass", "Fail")]
    flags = [data.certification(t) == "Fail" for t in keys]
    none = [t for t in data.tags if data.certification(t) == "none"]
    if keys:
        lo, hi = bootstrap_rate(flags)
        out(f"  f6: {sum(flags)} of {len(keys)} suites certify the fault ({pct(sum(flags) / len(keys))}); "
            f"95% bootstrap interval [{pct(lo)}, {pct(hi)}]")
    else:
        out("  f6: no suite has a certification verdict")
    out(f"  f6 suites whose every test was left out, so with no certification verdict: {len(none)}")
    fifth = read_csv(os.path.join(ROOT, "data", "campaign5", "results", "verdicts.csv"))
    both_keys = [t for t in keys if fifth.get(("b5", t), {}).get("verdict") in ("Pass", "Fail")]
    if both_keys:
        f = [data.certification(t) == "Fail" for t in both_keys]
        b = [fifth[("b5", t)]["verdict"] == "Fail" for t in both_keys]
        both = sum(x and y for x, y in zip(f, b))
        f_only = sum(x and not y for x, y in zip(f, b))
        b_only = sum(y and not x for x, y in zip(f, b))
        out(f"  beside b5, the fifth campaign's, on the {len(both_keys)} subjects with a verdict in both:")
        out(f"      f6 certifies {sum(f)}, b5 {sum(b)}; both {both}, f6 only {f_only}, b5 only {b_only}, "
            f"neither {len(both_keys) - both - f_only - b_only}")
        out(f"      exact McNemar p = {mcnemar(f_only, b_only):.3g}, a description: b5 ran in another campaign")
    out("")


def false_alarms(data, lines, skip):
    out = lines.append
    out("The tests f6 left out at acceptance: its findings (secondary)")
    suites = again = detect = alarms = unstable = with_alarm = 0
    alarms_in_detecting = []
    for t in data.tags:
        v = data.verdicts.get(("f6", t))
        if not v or ("f6", t) in skip or v.get("left_out_failing_again_on_own") in (None, ""):
            continue
        suites += 1
        a = int(v["left_out_failing_again_on_own"])
        d = int(v["left_out_detecting"])
        fa = int(v["left_out_false_alarms"])
        again += a
        detect += d
        alarms += fa
        unstable += int(v["left_out_unstable"])
        with_alarm += fa > 0
        if v["detection"] == "Fail":
            alarms_in_detecting.append(fa)
    out(f"  {suites} f6 suites had tests left out and run on both revisions")
    out(f"  failing again on the faulty revision: {again}; of them, detecting {detect} and false alarms {alarms}"
        + (f"; share detecting {pct(detect / again)}" if again else ""))
    out(f"  left out but passing on the faulty revision when run again (unstable): {unstable}")
    out(f"  suites with at least one false alarm: {with_alarm}")
    if alarms_in_detecting:
        out(f"  false alarms in the {len(alarms_in_detecting)} suites that detect: "
            f"{sum(alarms_in_detecting)} in all, median {sorted(alarms_in_detecting)[len(alarms_in_detecting) // 2]}")
    out("")


def closing_section(data, lines, skip):
    out = lines.append
    out("Closing messages of f6, read at the audit (secondary)")
    named = [t for t in data.tags if t in data.closing and ("f6", t) not in skip]
    fault = [t for t in named if data.closing[t] == "fault"]
    out(f"  runs whose message names a test as showing a bug: {len(named)}; "
        f"of them, naming the fault: {len(fault)}")
    rows = [("names the fault", fault), ("names another bug", [t for t in named if t not in fault]),
            ("names no bug", [t for t in data.tags if t not in data.closing and ("f6", t) not in skip])]
    for label, ts in rows:
        ds = [t for t in ts if data.detection("f6", t) in ("Pass", "Fail")]
        out(f"      {label:<18} {len(ts):>3} runs; detection Fail in {sum(data.detects('f6', t) for t in ds)} "
            f"of the {len(ds)} with a verdict")
    out("")


def pooled(data, arm, keys):
    det = sum(int(data.mutation[(arm, t)]["detected"]) for t in keys)
    gen = sum(int(data.mutation[(arm, t)]["generated"]) for t in keys)
    cov = sum(int(data.mutation[(arm, t)]["lines_covered"]) for t in keys)
    tot = sum(int(data.mutation[(arm, t)]["lines_total"]) for t in keys)
    return (det / gen if gen else float("nan")), (cov / tot if tot else float("nan"))


def mutation_section(data, lines, skip):
    out = lines.append
    out("Mutation score and line coverage, each arm on its own revision (secondary)")
    out("  f6's tests that fail on the faulty revision, its findings, are not in its score")
    paired = data.paired(data.tags, skip)
    keys = [t for t in paired if all(data.scored(a, t) for a in ARMS)]
    out(f"  complete set: {len(keys)} of the {len(paired)} paired subjects")
    if not keys:
        out("")
        return
    rng = random.Random(SEED)
    for what, index in (("mutation score", 0), ("line coverage", 1)):
        f = pooled(data, "f6", keys)[index]
        m = pooled(data, "m6", keys)[index]
        values = []
        for _ in range(RESAMPLES):
            sample = [keys[i] for i in rng.choices(range(len(keys)), k=len(keys))]
            values.append(pooled(data, "f6", sample)[index] - pooled(data, "m6", sample)[index])
        lo, hi = interval([v for v in values if v == v])
        out(f"  pooled {what}: f6 {pct(f)}   m6 {pct(m)}   difference {100 * (f - m):+.1f} points, "
            f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    for arm in ARMS:
        group = [t for t in keys if data.detects(arm, t)]
        if group:
            s, c = pooled(data, arm, group)
            out(f"  {arm} suites that detect: {len(group)}; pooled mutation score {pct(s)}, line coverage {pct(c)}")
        else:
            out(f"  {arm} suites that detect: none")
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


def left_out_m6(data, lines, skip):
    out = lines.append
    out("Tests m6 left out at acceptance, run on the faulty revision (secondary)")
    suites = ran = passed = with_any = 0
    for t in data.tags:
        v = data.verdicts.get(("m6", t))
        if not v or ("m6", t) in skip or not v.get("left_out_methods_run_on_other"):
            continue
        suites += 1
        ran += int(v["left_out_methods_run_on_other"])
        p = int(v["left_out_passing_on_other"] or 0)
        passed += p
        with_any += p > 0
    out(f"  m6: {suites} suites had tests left out and run on the faulty revision; "
        f"{passed} of {ran} such methods pass there (expected the faulty behaviour), in {with_any} suites")
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
        limited = []
        models, clis, commits = set(), set(), set()
        for t in done:
            try:
                r = json.load(open(os.path.join(d, t + ".json")))
                cost += r.get("total_cost_usd") or 0
                turns += r.get("num_turns") or 0
                if (r.get("subtype") or "").startswith("error_max_"):
                    limited.append(t)
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
        split = []
        for t in ok:
            try:
                a, b = open(os.path.join(d, t + ".pruned")).read().split()[:2]
                left += int(a)
                total += int(b)
            except (OSError, ValueError):
                pass
            try:
                if os.path.getsize(os.path.join(d, t + ".split")) > 0:
                    split.append(t)
            except OSError:
                pass
        out(f"  {arm}: {len(done)} runs of {len(data.tags)}, {len(ok)} with an accepted suite; "
            f"${cost:.2f} at list prices, {turns / len(done) if done else 0:.1f} turns a run")
        out(f"      model {sorted(x for x in models if x)}  CLI {sorted(x for x in clis if x)}  "
            f"commits {sorted(x for x in commits if x)}")
        out(f"      tests left out at acceptance: {left} of {total}"
            + (f" ({pct(left / total)})" if total else ""))
        out(f"      runs that reached the limit of turns or budget: {len(limited)}"
            + (" — " + ", ".join(limited) if limited else ""))
        if arm == "f6":
            out(f"      suites with a class left out because it did not finish: {len(split)}"
                + (" — " + ", ".join(split) if split else ""))
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
            elif row["detection"] not in ("Pass", "Fail"):
                reasons.append(f"{arm}: {row['detection']} ({row.get('detection_note') or 'no note'})")
        if reasons:
            listed = True
            out(f"  {t}: " + "; ".join(reasons))
    if not listed:
        out("  none")
    out("")


# ---- sensitivity 6 ----------------------------------------------------------------

def named_in_closing(data):
    """f6 subjects whose closing message names one of the tests that detect."""
    named = set()
    for t in data.tags:
        v = data.verdicts.get(("f6", t))
        if not v or v["detection"] != "Fail":
            continue
        try:
            text = json.load(open(os.path.join(data.root, "runs-f6", t + ".json"))).get("result") or ""
        except (OSError, ValueError):
            text = ""
        for key in filter(None, v["detecting_keys"].split(";")):
            name = key.split("#", 1)[1].split("(", 1)[0] if "#" in key else key.rsplit(".", 1)[-1]
            if re.search(rf"\b{re.escape(name)}\b", text):
                named.add(t)
                break
    return named


# ---- descriptive comparisons ------------------------------------------------------

def by_group(data, lines, label, key, skip):
    out = lines.append
    out(f"  by {label}")
    groups = {}
    for t in data.paired(data.tags, skip):
        groups.setdefault(key(data.info[t]), []).append(t)
    for g in sorted(groups):
        ts = groups[g]
        f = sum(data.detects("f6", t) for t in ts)
        m = sum(data.detects("m6", t) for t in ts)
        out(f"      {g:<22} {len(ts):>3} subjects   f6 detects {f:>3}   m6 detects {m:>3}")


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


def three_runs(lines, runs, tags):
    """The same condition run three times: subjects by how many runs detect, Fleiss' kappa."""
    out = lines.append
    keys = [t for t in tags if all(r.get(t) in ("Pass", "Fail") for r in runs.values())]
    n, k = len(keys), len(runs)
    if not n:
        out("  m4, m5, m6: no subject with a verdict in all three")
        return
    counts = [sum(r[t] == "Fail" for r in runs.values()) for t in keys]
    spread = [sum(1 for c in counts if c == i) for i in range(k + 1)]
    p_fail = sum(counts) / (n * k)
    p_i = [(c * (c - 1) + (k - c) * (k - c - 1)) / (k * (k - 1)) for c in counts]
    p_bar = sum(p_i) / n
    p_e = p_fail ** 2 + (1 - p_fail) ** 2
    fleiss = (p_bar - p_e) / (1 - p_e) if p_e < 1 else float("nan")
    out(f"  m4, m5 and m6, the same condition run three times: {n} subjects; detected in none "
        f"{spread[0]}, in one {spread[1]}, in two {spread[2]}, in all three {spread[3]}; "
        f"Fleiss' kappa {fleiss:.2f}")


def descriptive(data, lines, skip):
    out = lines.append
    out("Descriptive comparisons (none is a test of the protocol)")
    by_group(data, lines, "project", lambda s: s["project"], skip)
    by_group(data, lines, "fault type", lambda s: s["type"], skip)
    by_group(data, lines, f"date of the fix (up to {WINDOW_END} or after)",
             lambda s: "up to " + WINDOW_END if s["date"] <= WINDOW_END else "after", skip)
    four = read_csv(os.path.join(ROOT, "data", "campaign4", "results", "verdicts.csv"))
    fifth = read_csv(os.path.join(ROOT, "data", "campaign5", "results", "verdicts.csv"))
    tags = [t for t in data.tags if not any((a, t) in skip for a in ARMS)]
    m4 = {t: four[("m4", t)]["verdict"] for t in tags if ("m4", t) in four}
    s4 = {t: four[("s4", t)]["verdict"] for t in tags if ("s4", t) in four}
    m5 = {t: fifth[("m5", t)]["verdict"] for t in tags if ("m5", t) in fifth}
    m6 = {t: data.detection("m6", t) for t in tags}
    f6 = {t: data.detection("f6", t) for t in tags}
    agreement(lines, "m4 (first) beside m6 (second), the same condition", m4, m6, tags)
    agreement(lines, "m5 (first) beside m6 (second), the same condition", m5, m6, tags)
    three_runs(lines, {"m4": m4, "m5": m5, "m6": m6}, tags)
    agreement(lines, "s4 (first) beside f6's detection (second), neither shown the repair", s4, f6, tags)
    b5_found = sum(1 for t in tags if int(fifth.get(("b5", t), {}).get("left_out_passing_on_other") or 0) > 0)
    out(f"  f6 beside b5, the same revision under another request: f6 detects "
        f"{sum(1 for t in tags if f6.get(t) == 'Fail')}; b5's left-out tests detect in {b5_found}")
    for arm, root in (("f6", data.root), ("b5", os.path.join(ROOT, "data", "campaign5"))):
        left = total = 0
        for t in tags:
            try:
                a, b = open(os.path.join(root, f"runs-{arm}", t + ".pruned")).read().split()[:2]
                left += int(a)
                total += int(b)
            except (OSError, ValueError):
                pass
        out(f"      {arm}: tests left out at acceptance {left} of {total}"
            + (f" ({pct(left / total)})" if total else ""))
    keys = [t for t in tags if f6.get(t) in ("Pass", "Fail")]
    if keys:
        out(f"  §6's table gains the row 'faulty implementation, asked to look for faults': "
            f"{pct(sum(f6[t] == 'Fail' for t in keys) / len(keys))}")
    out("")


# ---- main -------------------------------------------------------------------------

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign6")
    data = Data(root)
    lines = []
    out = lines.append
    out(f"Sixth campaign: {len(data.tags)} subjects, arms {', '.join(ARMS)}; "
        f"seed {SEED}, {RESAMPLES} resamples")
    out("")
    run_records(data, lines)
    without_verdict(data, lines)
    skip = data.violations
    out("Runs with a violation: " + (", ".join(f"{a} {t}" for a, t in sorted(skip)) or "none"))
    out("")
    detection_rate(data, lines, skip)
    out("H1: detection in f6 and detection in m6 differ")
    n, f_only, m_only, p = contrast(data, data.tags, lines, "paired set", skip=skip)
    decision(n, f_only, m_only, p, lines)
    out("")
    certification_section(data, lines, skip)
    false_alarms(data, lines, skip)
    closing_section(data, lines, skip)
    left_out_m6(data, lines, skip)
    mutation_section(data, lines, skip)
    kept_methods(data, lines)

    out("Sensitivity analyses (none is confirmatory)")
    contrast(data, data.tags, lines, "1. runs with a violation included")
    contrast(data, data.tags, lines, "2. intention to treat", intent=True)
    try:
        knew = load("audit_campaign6", "audit-campaign6.py").knew_runs(root)
    except Exception as e:                     # a dry run has no transcripts
        knew = set()
        out(f"  (the runs that name the fix could not be read: {e})")
    out(f"  runs that name the fix: {len(knew)}"
        + (" — " + ", ".join(f"{a} {t}" for a, t in sorted(knew)) if knew else ""))
    contrast(data, data.tags, lines, "3. runs that name the fix left out", skip=skip | knew)
    contrast(data, data.tags, lines, "4. detection by timeout read as none", skip=skip, timeouts_none=True)
    strict = [t for t in data.tags if data.info[t]["strict"]]
    contrast(data, strict, lines, f"5. the strict screen's subjects only ({len(strict)})", skip=skip)
    named = named_in_closing(data)
    contrast(data, data.tags, lines, "6. f6 detection only where the closing message names a test that detects",
             skip=skip, f6_detects=lambda t: data.detects("f6", t) and t in named)
    out("")
    descriptive(data, lines, skip)
    print("\n".join(lines))


if __name__ == "__main__":
    main()

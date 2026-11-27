#!/usr/bin/env python3
"""
Seventh campaign: the analysis its protocol fixes (data/campaign7/PROTOCOL.md).

Written with the protocol, before any run of the campaign, from the sixth
campaign's bin/analyze-campaign6.py. It reads

  data/campaign7/subjects.txt              the bugs, in the order of the runs,
                                           with their fault type and issue
  data/campaign7/results/verdicts.csv      bin/measure-campaign7.sh
  data/campaign7/mutation/mutation.csv     bin/mutation-campaign7.sh
  data/campaign7/runs-<arm>/               the records of the runs
  data/campaign7/violations.txt            runs with a violation, decided at
                                           the audit: `arm bug reason`
  data/campaign7/closing-f7.txt            f7 runs whose closing message names a
                                           test as showing a bug, listed at the
                                           audit: `f7 bug fault|other words`
  data/campaign6/subjects.txt, results/    the sixth campaign's subjects and
                                           verdicts, for the corpus comparison
  data/campaign5/results/verdicts.csv      b5's certification, as a description
  data/campaign2/results/agent-metrics.csv m2's and s2's verdicts, and
  data/agent-metrics-final.csv             the first campaign's, for the
                                           descriptive comparisons
  data/fault-taxonomy.csv                  the sample's fault types, for the
                                           weights of the corpus comparison

and prints the estimate, H1, the secondary outcomes, the sensitivity analyses
and the descriptive comparisons, in that order. Nothing in it is chosen after
the data.

THE ESTIMATE
  The detection rate when asked to look for faults: f7's share of Fail in
  detection among its bugs with a detection verdict, runs with a violation
  left out, with a 95% percentile interval from 10,000 bootstrap resamples of
  those bugs, random.Random(20261127).

PRIMARY ANALYSIS
  Paired set: the bugs with a detection verdict, Pass or Fail, in both arms,
  runs with a violation left out.
  H1: detection in f7 and detection in m7 differ. Exact McNemar test,
  two-sided, at 0.05. The difference f7 - m7 is given with a 95% percentile
  interval from a bootstrap over bugs: 10,000 resamples, both arms of a bug
  kept together, random.Random(20261127).

SECONDARY (no decision rule)
  The corpus: f7 beside the sixth campaign's f6 and m7 beside its m6, the
  difference f - m in each campaign, and the share of m's detections that f
  also makes, each on the campaign's paired set. Each difference between the
  campaigns has a 95% interval from 10,000 bootstrap resamples in which each
  campaign's subjects are resampled on their own. f6 and m6 are also weighted
  to the sample's fault types, as the fourth campaign's analysis weighted m4
  and s4 (Csv-16 counted as STATE, API weighing nothing), with an interval
  from resamples within each type.
  Certification in f7, with its interval, beside b5's rate; the false alarms;
  the closing messages; the left-out tests of m7; mutation score and line
  coverage on the complete set, pooled, f7 - m7 with a 95% interval from
  10,000 bootstrap resamples of the bugs.

Usage:
    ./bin/analyze-campaign7.py                 # data/campaign7
    ./bin/analyze-campaign7.py <directory>     # a dry run's output
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
ARMS = ("f7", "m7")
SEED = 20261127
RESAMPLES = 10_000
ALPHA = 0.05
TYPES = ("OMISSION", "ALGORITHM", "SUBSTITUTION", "STATE", "MISSING_CLAUSE", "API")
# the bugs the memorisation probe found recalled (Lang-13, Gson-16) or
# recognised (Lang-43, Lang-8): PREPRINT.md, section 3.7
PROBE = ("Lang-8", "Lang-13", "Lang-43", "Gson-16")


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
    """[{tag, type, issue, project}] in the order of the file. A dry run's
    directory may have no list of its own: then the campaign's is read. A list
    with the tag alone takes the type from data/fault-taxonomy.csv."""
    path = os.path.join(root, "subjects.txt")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "data", "campaign7", "subjects.txt")
    types = sample_types(raw=True)
    out = []
    for line in open(path):
        parts = line.split("#")[0].split()
        if parts:
            out.append({"tag": parts[0], "type": parts[1] if len(parts) > 1 else types.get(parts[0], "-"),
                        "issue": parts[2] if len(parts) > 2 else "-",
                        "project": parts[0].rsplit("-", 1)[0]})
    return out


def sample_types(raw=False):
    """{bug: fault type} of the sample: as classified (raw), or as the fourth
    campaign weighted it, Csv-16 counted as STATE."""
    out = {}
    with open(os.path.join(ROOT, "data", "fault-taxonomy.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["phase"] == "sample":
                out[r["bug_id"]] = r["fault_type"] if raw or r["bug_id"] != "Csv-16" else "STATE"
    return out


def read_csv(path, key="subject"):
    """{(arm, tag): row}"""
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                out[(r["arm"], r[key])] = r
    return out


def read_d4j(path, source):
    """{bug: test_classification} of one source in a merged Defects4J table."""
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["test_suite_source"] == source:
                    out[f"{r['project_id']}-{r['version_id'].rstrip('bf')}"] = r["test_classification"]
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
    """{bug: 'fault' or 'other'} from closing-f7.txt"""
    path = os.path.join(root, "closing-f7.txt")
    out = {}
    if os.path.exists(path):
        for line in open(path):
            parts = line.split("#")[0].split()
            if len(parts) >= 3 and parts[0] == "f7":
                if parts[2] not in ("fault", "other"):
                    sys.exit(f"closing-f7.txt: neither fault nor other: {line.strip()}")
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
        self.mutation = read_csv(os.path.join(root, "mutation", "mutation.csv"), key="bug")
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
        """f7's verdict on the suite as accepted: Fail certifies the fault."""
        row = self.verdicts.get(("f7", tag))
        return row["verdict"] if row else None

    def scored(self, arm, tag):
        """A mutation row with a figure: status ok, mutants and lines counted."""
        r = self.mutation.get((arm, tag))
        return bool(r) and r["status"] == "ok" and (r["mut_generated"] or "").isdigit() \
            and int(r["mut_generated"]) > 0 and (r["mut_killed"] or "").isdigit() \
            and (r["lines_total"] or "").isdigit() and int(r["lines_total"]) > 0


# ---- the estimate and H1 -------------------------------------------------------

def detection_rate(data, lines, skip):
    out = lines.append
    keys = [t for t in data.tags if ("f7", t) not in skip
            and data.detection("f7", t) in ("Pass", "Fail")]
    flags = [data.detects("f7", t) for t in keys]
    out("The detection rate when asked to look for faults (f7)")
    if not keys:
        out("  no f7 bug has a detection verdict")
        out("")
        return
    lo, hi = bootstrap_rate(flags)
    out(f"  {sum(flags)} of {len(keys)} suites detect the fault ({pct(sum(flags) / len(keys))}); "
        f"95% bootstrap interval [{pct(lo)}, {pct(hi)}]")
    out("")


def contrast(data, tags, lines, label, skip=(), timeouts_none=False, intent=False, f7_detects=None):
    """Detection in f7 against detection in m7. Returns (n, f7 only, m7 only, p)."""
    out = lines.append
    if intent:
        keys = list(tags)

        def det(arm, t):
            return data.detection(arm, t) == "Fail"
    else:
        keys = data.paired(tags, skip, timeouts_none)

        def det(arm, t):
            return data.detects(arm, t, timeouts_none)
    if f7_detects is not None:
        inner = det

        def det(arm, t):
            return f7_detects(t) if arm == "f7" else inner(arm, t)
    n = len(keys)
    if n == 0:
        out(f"  {label}: no bug")
        return 0, 0, 0, 1.0
    f = [det("f7", t) for t in keys]
    m = [det("m7", t) for t in keys]
    both = sum(x and y for x, y in zip(f, m))
    f_only = sum(x and not y for x, y in zip(f, m))
    m_only = sum(y and not x for x, y in zip(f, m))
    neither = n - both - f_only - m_only
    p = mcnemar(f_only, m_only)
    lo, hi = bootstrap_difference(list(zip(f, m)))
    out(f"  {label}: {n} bugs")
    out(f"      f7 detects {sum(f)}/{n} ({pct(sum(f) / n)})   m7 detects {sum(m)}/{n} ({pct(sum(m) / n)})")
    out(f"      both {both}, f7 only {f_only}, m7 only {m_only}, neither {neither}")
    out(f"      exact McNemar, two-sided: p = {p:.3g}")
    out(f"      difference f7 - m7 {100 * (sum(f) - sum(m)) / n:+.1f} points, "
        f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    return n, f_only, m_only, p


def decision(n, f_only, m_only, p, lines):
    out = lines.append
    if n == 0:
        out("  Outcome: no paired bug, so no outcome")
    elif p >= ALPHA:
        out("  Outcome: H1 not rejected. On Defects4J, asked to look for faults, the agent shown")
        out("  the faulty code detects the fault about as often as the agent shown the repair;")
        out("  the interval says how far apart the two rates could be")
    elif f_only < m_only:
        out("  Outcome: H1 rejected, f7 below m7. On Defects4J too, the agent asked to look for")
        out("  faults detects the fault less often than the regression setting credits; the")
        out("  difference and its interval measure by how much")
    else:
        out("  Outcome: H1 rejected, f7 above m7. Asked to look for faults on Defects4J, the")
        out("  agent detects more than the regression setting credits")


# ---- secondary outcomes ----------------------------------------------------------

def certification_section(data, lines, skip):
    out = lines.append
    out("Certification under the request (secondary)")
    keys = [t for t in data.tags if ("f7", t) not in skip and data.certification(t) in ("Pass", "Fail")]
    flags = [data.certification(t) == "Fail" for t in keys]
    none = [t for t in data.tags if data.certification(t) == "none"]
    if keys:
        lo, hi = bootstrap_rate(flags)
        out(f"  f7: {sum(flags)} of {len(keys)} suites certify the fault ({pct(sum(flags) / len(keys))}); "
            f"95% bootstrap interval [{pct(lo)}, {pct(hi)}]")
    else:
        out("  f7: no suite has a certification verdict")
    out(f"  f7 suites whose every test was left out, so with no certification verdict: {len(none)}")
    fifth = read_csv(os.path.join(ROOT, "data", "campaign5", "results", "verdicts.csv"))
    b5 = [r["verdict"] == "Fail" for (arm, _), r in fifth.items() if arm == "b5" and r["verdict"] in ("Pass", "Fail")]
    if b5:
        out(f"  beside b5's rate on the post-cutoff faults, a description: {sum(b5)} of {len(b5)} "
            f"({pct(sum(b5) / len(b5))}). No Defects4J arm was shown the buggy version without the request")
    out("")


def false_alarms(data, lines, skip):
    out = lines.append
    out("The tests f7 left out at acceptance: its findings (secondary)")
    suites = again = detect = alarms = unstable = with_alarm = 0
    alarms_in_detecting = []
    for t in data.tags:
        v = data.verdicts.get(("f7", t))
        if not v or ("f7", t) in skip or v.get("left_out_failing_again_on_own") in (None, ""):
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
    out(f"  {suites} f7 suites had tests left out and run on both versions")
    out(f"  failing again on the buggy version: {again}; of them, detecting {detect} and false alarms {alarms}"
        + (f"; share detecting {pct(detect / again)}" if again else ""))
    out(f"  left out but passing on the buggy version when run again (unstable): {unstable}")
    out(f"  suites with at least one false alarm: {with_alarm}")
    if alarms_in_detecting:
        out(f"  false alarms in the {len(alarms_in_detecting)} suites that detect: "
            f"{sum(alarms_in_detecting)} in all, median {sorted(alarms_in_detecting)[len(alarms_in_detecting) // 2]}")
    out("")


def closing_section(data, lines, skip):
    out = lines.append
    out("Closing messages of f7, read at the audit (secondary)")
    named = [t for t in data.tags if t in data.closing and ("f7", t) not in skip]
    fault = [t for t in named if data.closing[t] == "fault"]
    out(f"  runs whose message names a test as showing a bug: {len(named)}; "
        f"of them, naming the fault: {len(fault)}")
    rows = [("names the fault", fault), ("names another bug", [t for t in named if t not in fault]),
            ("names no bug", [t for t in data.tags if t not in data.closing and ("f7", t) not in skip])]
    for label, ts in rows:
        ds = [t for t in ts if data.detection("f7", t) in ("Pass", "Fail")]
        out(f"      {label:<18} {len(ts):>3} runs; detection Fail in {sum(data.detects('f7', t) for t in ds)} "
            f"of the {len(ds)} with a verdict")
    out("")


def pooled(data, arm, keys):
    det = sum(int(data.mutation[(arm, t)]["mut_killed"]) for t in keys)
    gen = sum(int(data.mutation[(arm, t)]["mut_generated"]) for t in keys)
    cov = sum(int(data.mutation[(arm, t)]["lines_covered"]) for t in keys)
    tot = sum(int(data.mutation[(arm, t)]["lines_total"]) for t in keys)
    return (det / gen if gen else float("nan")), (cov / tot if tot else float("nan"))


def mutation_section(data, lines, skip):
    out = lines.append
    out("Mutation score and line coverage, each arm on its own version (secondary)")
    out("  f7's tests that fail on the buggy version, its findings, are not in its score")
    paired = data.paired(data.tags, skip)
    keys = [t for t in paired if all(data.scored(a, t) for a in ARMS)]
    out(f"  complete set: {len(keys)} of the {len(paired)} paired bugs")
    # why the others are not in it, as bin/mutation-campaign7.sh recorded it
    for t in paired:
        if t in keys:
            continue
        why = []
        for a in ARMS:
            if data.scored(a, t):
                continue
            r = data.mutation.get((a, t))
            why.append(f"{a} " + ((r["status"] + (f", {r['note']}" if r["note"] else "")) if r else "no row"))
        out(f"    {t}: " + "; ".join(why))
    corrected = sorted(f"{t} {a}" for (a, t), r in data.mutation.items()
                       if "one-line correction of Cli.build.xml" in (r.get("note") or ""))
    if corrected:
        out(f"  measured through the one-line correction of Cli.build.xml: {', '.join(corrected)}")
    if not keys:
        out("")
        return
    rng = random.Random(SEED)
    for what, index in (("mutation score", 0), ("line coverage", 1)):
        f = pooled(data, "f7", keys)[index]
        m = pooled(data, "m7", keys)[index]
        values = []
        for _ in range(RESAMPLES):
            sample = [keys[i] for i in rng.choices(range(len(keys)), k=len(keys))]
            values.append(pooled(data, "f7", sample)[index] - pooled(data, "m7", sample)[index])
        lo, hi = interval([v for v in values if v == v])
        out(f"  pooled {what}: f7 {pct(f)}   m7 {pct(m)}   difference {100 * (f - m):+.1f} points, "
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
    """The methods kept in the archive Major measured, against those the
    measurement ran on the own version."""
    out = lines.append
    out("The tests in the archive for Major against the tests the measurement ran")
    checked = agree = 0
    for arm in ARMS:
        for t in data.tags:
            r, v = data.mutation.get((arm, t)), data.verdicts.get((arm, t))
            if not r or not v or r["status"] != "ok":
                continue
            checked += 1
            if (r["methods_kept"] or "").isdigit() and r["methods_kept"] == v["methods_run_on_own"]:
                agree += 1
            else:
                out(f"  {t} {arm}: kept {r['methods_kept']}, measurement ran {v['methods_run_on_own']}")
    out(f"  {agree} of {checked} suites with a figure agree")
    out("")


def left_out_m7(data, lines, skip):
    out = lines.append
    out("Tests m7 left out at acceptance, run on the buggy version (secondary)")
    suites = ran = passed = with_any = 0
    for t in data.tags:
        v = data.verdicts.get(("m7", t))
        if not v or ("m7", t) in skip or not v.get("left_out_methods_run_on_other"):
            continue
        suites += 1
        ran += int(v["left_out_methods_run_on_other"])
        p = int(v["left_out_passing_on_other"] or 0)
        passed += p
        with_any += p > 0
    out(f"  m7: {suites} suites had tests left out and run on the buggy version; "
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
        if arm == "f7":
            out(f"      suites with a class left out because it did not finish: {len(split)}"
                + (" — " + ", ".join(split) if split else ""))
        for t in done:
            if statuses[t] != "ok":
                out(f"      no suite: {t}: {statuses[t]}")
    out("")


def without_verdict(data, lines):
    out = lines.append
    out("Bugs outside the paired set")
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
    """f7 bugs whose closing message names one of the tests that detect."""
    named = set()
    for t in data.tags:
        v = data.verdicts.get(("f7", t))
        if not v or v["detection"] != "Fail":
            continue
        try:
            text = json.load(open(os.path.join(data.root, "runs-f7", t + ".json"))).get("result") or ""
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
        f = sum(data.detects("f7", t) for t in ts)
        m = sum(data.detects("m7", t) for t in ts)
        out(f"      {g:<22} {len(ts):>3} bugs   f7 detects {f:>3}   m7 detects {m:>3}")


def agreement(lines, label, first, second, tags):
    """Two sets of verdicts on the same subjects: counts and Cohen's kappa."""
    out = lines.append
    keys = [t for t in tags if first.get(t) in ("Pass", "Fail") and second.get(t) in ("Pass", "Fail")]
    n = len(keys)
    if not n:
        out(f"  {label}: no bug with a verdict in both")
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
    out(f"  {label}: {n} bugs; Fail in both {both}, only the first {only_a}, only the second "
        f"{only_b}; agreement {pct(po)}, Cohen's kappa {kappa:.2f}")


def sixth_campaign():
    """The sixth campaign's paired set: [(subject, fault type, f6 detects, m6 detects)]."""
    root = os.path.join(ROOT, "data", "campaign6")
    v6 = read_csv(os.path.join(root, "results", "verdicts.csv"))
    viol = read_listed(root, "violations.txt")
    out = []
    for line in open(os.path.join(root, "subjects.txt")):
        parts = line.split("#")[0].split()
        if not parts:
            continue
        t = parts[0]
        det = {a: (v6.get((a, t)) or {}).get("detection") for a in ("f6", "m6")}
        if any((a, t) in viol for a in det) or any(d not in ("Pass", "Fail") for d in det.values()):
            continue
        out.append((t, parts[2], det["f6"] == "Fail", det["m6"] == "Fail"))
    return out


def corpus(data, lines, skip):
    """f7 beside f6 and m7 beside m6 (secondary, no decision rule)."""
    out = lines.append
    out("The corpus: the seventh campaign beside the sixth (secondary, no decision rule)")
    six = sixth_campaign()
    pairs6 = [(f, m) for _, _, f, m in six]
    pairs7 = [(data.detects("f7", t), data.detects("m7", t)) for t in data.paired(data.tags, skip)]
    if not pairs6 or not pairs7:
        out("  no paired set in one of the two campaigns")
        out("")
        return

    def stats(pairs):
        n = len(pairs)
        f = sum(a for a, _ in pairs)
        m = sum(b for _, b in pairs)
        both = sum(a and b for a, b in pairs)
        return f / n, m / n, (f - m) / n, (both / m if m else float("nan"))

    s7, s6 = stats(pairs7), stats(pairs6)
    rng = random.Random(SEED)
    boot = []
    for _ in range(RESAMPLES):
        a = [pairs7[i] for i in rng.choices(range(len(pairs7)), k=len(pairs7))]
        b = [pairs6[i] for i in rng.choices(range(len(pairs6)), k=len(pairs6))]
        boot.append(tuple(x - y for x, y in zip(stats(a), stats(b))))
    out(f"  paired sets: seventh {len(pairs7)} bugs, sixth {len(pairs6)} subjects")
    labels = ("detection asked to look for faults (f7, f6)", "detection shown the repair (m7, m6)",
              "the difference inside the campaign, f - m", "the share of m's detections that f also makes")
    for i, label in enumerate(labels):
        lo, hi = interval([b[i] for b in boot if b[i] == b[i]])
        show = (lambda x: f"{100 * x:+.1f} points") if i == 2 else pct
        out(f"  {label}: seventh {show(s7[i])}, sixth {show(s6[i])}; seventh - sixth "
            f"{100 * (s7[i] - s6[i]):+.1f} points, 95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]")
    # the sixth weighted to the sample's fault types, the fourth campaign's way
    counts = {}
    for ty in sample_types().values():
        counts[ty] = counts.get(ty, 0) + 1
    weights = {ty: counts.get(ty, 0) / sum(counts.values()) for ty in TYPES}
    groups = {}
    for _, ty, f, m in six:
        groups.setdefault(ty, []).append((f, m))

    def weighted(g):
        present = [ty for ty in TYPES if weights[ty] > 0 and g.get(ty)]
        total = sum(weights[ty] for ty in present)
        wf = sum(weights[ty] / total * sum(a for a, _ in g[ty]) / len(g[ty]) for ty in present)
        wm = sum(weights[ty] / total * sum(b for _, b in g[ty]) / len(g[ty]) for ty in present)
        return wf, wm, present

    wf, wm, present = weighted(groups)
    rng = random.Random(SEED)
    wboot = []
    for _ in range(RESAMPLES):
        g = {ty: [v[i] for i in rng.choices(range(len(v)), k=len(v))] for ty, v in groups.items()}
        x, y, _ = weighted(g)
        wboot.append((x, y, x - y))
    missing = [ty for ty in TYPES if weights[ty] > 0 and ty not in present]
    lo_f, hi_f = interval([b[0] for b in wboot])
    lo_m, hi_m = interval([b[1] for b in wboot])
    lo_d, hi_d = interval([b[2] for b in wboot])
    out(f"  the sixth campaign weighted to the sample's fault types: f6 {pct(wf)} [{pct(lo_f)}, {pct(hi_f)}], "
        f"m6 {pct(wm)} [{pct(lo_m)}, {pct(hi_m)}], f6 - m6 {100 * (wf - wm):+.1f} points "
        f"[{100 * lo_d:+.1f}, {100 * hi_d:+.1f}]" + (f"; no subject of type {', '.join(missing)}" if missing else ""))
    out("  The corpora differ in project, kind of fault, build and the way the faulty code is made, as")
    out("  well as in date: none of these figures says how much of a difference is recall")
    out("")


def descriptive(data, lines, skip):
    out = lines.append
    out("Descriptive comparisons (none is a test of the protocol)")
    by_group(data, lines, "project", lambda s: s["project"], skip)
    by_group(data, lines, "fault type", lambda s: s["type"], skip)
    tags = [t for t in data.tags if not any((a, t) in skip for a in ARMS)]
    m7 = {t: data.detection("m7", t) for t in tags}
    f7 = {t: data.detection("f7", t) for t in tags}
    second = os.path.join(ROOT, "data", "campaign2", "results", "agent-metrics.csv")
    m2, s2 = read_d4j(second, "m2"), read_d4j(second, "s2")
    first = read_d4j(os.path.join(ROOT, "data", "agent-metrics-final.csv"), "agent")
    agreement(lines, "m2 (second campaign) beside m7, one condition run twice", m2, m7, tags)
    agreement(lines, "the first campaign's M beside m7 (its working copy held Defects4J's files)", first, m7, tags)
    agreement(lines, "s2 beside f7's detection, neither shown the repair", s2, f7, tags)
    # recall
    paired = data.paired(data.tags, skip)
    for label, ts in (("the four bugs the memorisation probe flagged", [t for t in paired if t in PROBE]),
                      ("the other bugs", [t for t in paired if t not in PROBE])):
        out(f"  {label}: {len(ts)} paired; f7 detects {sum(data.detects('f7', t) for t in ts)}, "
            f"m7 detects {sum(data.detects('m7', t) for t in ts)}"
            + (f" ({', '.join(ts)})" if 0 < len(ts) <= 4 else ""))
    try:
        knew = load("audit_campaign7", "audit-campaign7.py").knew_runs(data.root)
    except Exception:                          # a dry run has no transcripts
        knew = set()
    for arm in ARMS:
        ts = sorted(t for a, t in knew if a == arm)
        out(f"  {arm} runs that name the bug: {len(ts)}" + (" — " + ", ".join(ts) if ts else ""))
    cite = []
    for t, kind in sorted(data.closing.items()):
        if kind != "fault":
            continue
        issue = data.info.get(t, {}).get("issue") or ""
        m = re.match(r"([A-Za-z]+)-(\d+)$", issue)
        try:
            text = json.load(open(os.path.join(data.root, "runs-f7", t + ".json"))).get("result") or ""
        except (OSError, ValueError):
            text = ""
        if m and re.search(rf"\b{m.group(1)}[-_ ]?{m.group(2)}\b", text, re.I):
            cite.append(t)
    out(f"  f7 closing messages that name the fault: {sum(1 for k in data.closing.values() if k == 'fault')}; "
        f"of them, citing the bug's issue: {len(cite)}" + (" — " + ", ".join(cite) if cite else ""))
    keys = [t for t in tags if f7.get(t) in ("Pass", "Fail")]
    if keys:
        out(f"  §6's table gains the row 'faulty implementation, asked to look for faults, on Defects4J': "
            f"{pct(sum(f7[t] == 'Fail' for t in keys) / len(keys))}")
    out("")


# ---- main -------------------------------------------------------------------------

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign7")
    data = Data(root)
    lines = []
    out = lines.append
    out(f"Seventh campaign: {len(data.tags)} bugs, arms {', '.join(ARMS)}; "
        f"seed {SEED}, {RESAMPLES} resamples")
    out("")
    run_records(data, lines)
    without_verdict(data, lines)
    skip = data.violations
    out("Runs with a violation: " + (", ".join(f"{a} {t}" for a, t in sorted(skip)) or "none"))
    out("")
    detection_rate(data, lines, skip)
    out("H1: detection in f7 and detection in m7 differ")
    n, f_only, m_only, p = contrast(data, data.tags, lines, "paired set", skip=skip)
    decision(n, f_only, m_only, p, lines)
    out("")
    corpus(data, lines, skip)
    certification_section(data, lines, skip)
    false_alarms(data, lines, skip)
    closing_section(data, lines, skip)
    left_out_m7(data, lines, skip)
    mutation_section(data, lines, skip)
    kept_methods(data, lines)

    out("Sensitivity analyses (none is confirmatory)")
    contrast(data, data.tags, lines, "1. runs with a violation included")
    contrast(data, data.tags, lines, "2. intention to treat", intent=True)
    try:
        knew = load("audit_campaign7", "audit-campaign7.py").knew_runs(root)
    except Exception as e:                     # a dry run has no transcripts
        knew = set()
        out(f"  (the runs that name the bug could not be read: {e})")
    out(f"  runs that name the bug: {len(knew)}"
        + (" — " + ", ".join(f"{a} {t}" for a, t in sorted(knew)) if knew else ""))
    contrast(data, data.tags, lines, "3. runs that name the bug left out", skip=skip | knew)
    contrast(data, data.tags, lines, "4. detection by timeout read as none", skip=skip, timeouts_none=True)
    contrast(data, [t for t in data.tags if t not in PROBE], lines,
             f"5. the four bugs the memorisation probe flagged left out ({', '.join(PROBE)})", skip=skip)
    named = named_in_closing(data)
    contrast(data, data.tags, lines, "6. f7 detection only where the closing message names a test that detects",
             skip=skip, f7_detects=lambda t: data.detects("f7", t) and t in named)
    out("")
    descriptive(data, lines, skip)
    print("\n".join(lines))


if __name__ == "__main__":
    main()

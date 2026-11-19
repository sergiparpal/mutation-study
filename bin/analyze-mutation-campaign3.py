#!/usr/bin/env python3
"""
Third campaign: the second campaign's H2 on the third campaign's suites, with
the mutation score and line coverage that bin/mutation-campaign3.sh measures.

Written on 19 November 2026, after the campaign had been run, audited,
measured and analysed, and committed with bin/mutation-campaign3.sh before
either was run on the campaign's subjects. It is not one of the scripts
data/campaign3/PROTOCOL.md fixes. What it computes is what that protocol says
would be computed if mutation score and coverage were measured later ("Not
measured: mutation score and coverage"):

    the statistic and interval of the second campaign's H2 will be computed as
    that protocol defines them, on the subjects with every measure in both
    arms, and reported as a secondary result whatever they are. This corpus
    was not sized for that test.

So, with the second campaign's own functions (bin/analyze-campaign2.py):

  complete set  the subjects of the third campaign's paired set (a verdict,
                Pass or Fail, in both arms, runs with a violation left out, as
                in its primary analysis) that also have a mutation score and a
                line-coverage figure in both arms
  D, M, C       detection rate, mutation score pooled over the suites
                (detected / generated, each summed), line coverage pooled
  fall(X)       1 - X(s3) / X(m3)
  statistic     fall(D) - fall(M); fall(D) - fall(C) as a secondary figure
  interval      the second campaign's: percentile bootstrap over subjects,
                10,000 resamples of the complete set with replacement, both
                arms of a subject kept together, random.Random(20261117),
                bounds at sorted[249] and sorted[9749]. Resamples in which m3
                detects nothing are left out and counted, and the bounds are
                taken at the same quantiles of the rest. The subjects are in
                sorted order, as the second campaign's keys are.

The seed is the second campaign's because its protocol defines the interval
with it; the third campaign's own seed, 20261118, is that of its H1 interval.

There is no decision rule. The third campaign's H1 is not tested again: its
decision is in data/campaign3/analysis.txt and stands.

Then, as in the second campaign and none of it confirmatory: the same with
the runs with a violation included, and with the runs whose transcript names
the fix left out (bin/audit-campaign3.py decides which); the mean of the
suites' mutation scores beside each pooled one. Then, descriptive: every suite
with a figure, by arm and by project; mutants by PIT's status; the suites
without a figure; whether PIT ran the tests the measurement ran; the second
campaign's H2 beside this one.

Reads only files already produced. Needs neither PIT nor the model.

Usage:
    ./bin/analyze-mutation-campaign3.py > data/campaign3/mutation-analysis.txt
"""

import csv
import importlib.util
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C3 = os.path.join(ROOT, "data", "campaign3")
C2 = os.path.join(ROOT, "data", "campaign2")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c2 = load("analyze_campaign2", "analyze-campaign2.py")
c3 = load("analyze_campaign3", "analyze-campaign3.py")
pct = c2.pct

STATUSES = ("killed", "timed_out", "memory_error", "run_error", "non_viable", "equivalent",
            "survived", "no_coverage")


def read_mutation(root):
    """{(arm, subject): row} from mutation/mutation.csv"""
    path = os.path.join(root, "mutation", "mutation.csv")
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                out[(r["arm"], r["subject"])] = r
    return out


def rows_for(arm, data, mut, skip=()):
    """The arm's suites in the format the second campaign's functions read."""
    out = {}
    for t in data.tags:
        if (arm, t) in skip:
            continue
        v = data.verdicts.get((arm, t))
        if not v:
            continue
        r = {"test_classification": v["verdict"]}
        m = mut.get((arm, t))
        if m and m["status"] == "ok":
            r.update(mut_generated=m["generated"], mut_killed=m["detected"],
                     lines_total=m["lines_total"], lines_covered=m["lines_covered"])
        out[t] = r
    return out


def h2(M, S, label, lines, names=("m3", "s3")):
    """The second campaign's H2 on two arms. Returns (point, lo, hi) or None."""
    out = lines.append
    a, b = names
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
    out(f"      detection       {a} {n_m}/{len(complete)} {pct(d_m)}  {b} {n_s}/{len(complete)} {pct(d_s)}"
        f"  fall {pct(c2.fall(d_m, d_s))}")
    out(f"      mutation score  {a} {pct(m_m)}  {b} {pct(m_s)}  fall {pct(c2.fall(m_m, m_s))}"
        f"   (per-suite means {pct(c2.mean_mutation(M, complete))}, {pct(c2.mean_mutation(S, complete))})")
    out(f"      line coverage   {a} {pct(c_m)}  {b} {pct(c_s)}  fall {pct(c2.fall(c_m, c_s))}")

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
            out(f"      fall(detection) - fall({name}): not defined ({a} detects nothing)")
            continue
        note = f"; {dropped} resamples without an {a} detection left out" if dropped else ""
        out(f"      fall(detection) - fall({name}) = {100 * point:+.1f} points, "
            f"95% bootstrap interval [{100 * lo:+.1f}, {100 * hi:+.1f}]{note}")
        if which == "M":
            result = (point, lo, hi)
    return result


def pooled(rows):
    gen = sum(int(r["generated"]) for r in rows)
    det = sum(int(r["detected"]) for r in rows)
    tot = sum(int(r["lines_total"] or 0) for r in rows)
    cov = sum(int(r["lines_covered"] or 0) for r in rows)
    scores = [int(r["detected"]) / int(r["generated"]) for r in rows if int(r["generated"])]
    return (det / gen if gen else float("nan"), sum(scores) / len(scores) if scores else float("nan"),
            cov / tot if tot else float("nan"), gen)


def main():
    data = c3.Data(C3)
    mut = read_mutation(C3)
    lines = []
    out = lines.append
    if not mut:
        print(f"no {C3}/mutation/mutation.csv: the suites have not been measured with PIT")
        return

    expected = {(arm, t) for t in data.tags for arm in c3.ARMS
                if os.path.exists(os.path.join(C3, "suites", f"{t}-{arm}.tar.bz2"))}
    ok = {k for k, r in mut.items() if r["status"] == "ok"}
    out("Suites measured with PIT")
    for arm in c3.ARMS:
        n = sum(1 for k in expected if k[0] == arm)
        m = sum(1 for k in mut if k[0] == arm)
        g = sum(1 for k in ok if k[0] == arm)
        out(f"  {arm}: {m} of {n} archived suites measured, {g} with a figure")
    missing = sorted(expected - set(mut))
    if missing:
        out(f"  *** not measured: {', '.join(f'{a} {t}' for a, t in missing)} ***")
    out("")

    Mp = rows_for("m3", data, mut, data.violations)
    Sp = rows_for("s3", data, mut, data.violations)
    out("=" * 72)
    out("THE SECOND CAMPAIGN'S H2, ON THIS CAMPAIGN (secondary; the corpus was not sized for it)")
    result = h2(Mp, Sp, "Complete set, runs with a violation left out", lines)
    paired = sorted(k for k in Mp if k in Sp and c2.has_verdict(Mp[k]) and c2.has_verdict(Sp[k]))
    if paired != sorted(data.paired(data.tags, data.violations)):
        out("  *** the paired set differs from that of bin/analyze-campaign3.py ***")
    out("=" * 72)
    if result:
        point, lo, hi = result
        if lo > 0:
            out("The lower bound of the interval is above 0: on this corpus too, detection falls")
            out("further between the arms than mutation score does.")
        else:
            out("The interval includes 0: on this corpus the fall in detection is not shown to")
            out("exceed the fall in mutation score.")
        out("No decision follows from it: the protocol fixes none, and the corpus was not sized")
        out("for this test. The third campaign's H1, which the second campaign's sequence would")
        out("require first, is not rejected (analysis.txt).")
    out("")

    out("OUTSIDE THE COMPLETE SET")
    for t in data.tags:
        reasons = []
        for arm in c3.ARMS:
            if (arm, t) in data.violations:
                reasons.append(f"{arm}: violation")
                continue
            v = data.verdicts.get((arm, t))
            if not v or v["verdict"] not in ("Pass", "Fail"):
                reasons.append(f"{arm}: {v['verdict'] if v else 'no suite'}"
                               + (f" ({v['note']})" if v and v["note"] else ""))
            m = mut.get((arm, t))
            if not m:
                reasons.append(f"{arm}: not measured with PIT")
            elif m["status"] != "ok":
                reasons.append(f"{arm}: no mutation figure ({m['note']})")
            elif not int(m["generated"]) or not int(m["lines_total"] or 0):
                reasons.append(f"{arm}: no mutant or no line in the classes")
        if reasons:
            out(f"  {t}: {'; '.join(reasons)}")
    out("")

    out("SENSITIVITY ANALYSES, as in the second campaign (none confirmatory)")
    M = rows_for("m3", data, mut)
    S = rows_for("s3", data, mut)
    h2(M, S, "1. Runs with a violation included", lines)
    out("2. Intention to treat concerns detection alone; there is nothing to add to analysis.txt")
    try:
        knew = load("audit3", "audit-campaign3.py").knew_runs(C3)
    except Exception as exc:
        knew = set()
        out(f"3. the transcripts could not be read: {exc}")
    out(f"3. Runs whose transcript names the fix: {len(knew)}"
        + (f" ({', '.join(f'{a} {t}' for a, t in sorted(knew))})" if knew else ""))
    if knew:
        skip = data.violations | knew
        h2(rows_for("m3", data, mut, skip), rows_for("s3", data, mut, skip),
           "   with those runs left out", lines)
    out("4. Mutation score as the mean over suites: beside each pooled figure above")
    out("")

    out("DESCRIPTIVE (no test)")
    out("Every suite with a figure, runs with a violation included")
    for arm in c3.ARMS:
        rows = [r for k, r in mut.items() if k[0] == arm and r["status"] == "ok"]
        score, mean, cov, gen = pooled(rows)
        out(f"  {arm}: {len(rows)} suites, {gen} mutants; mutation score {pct(score)} pooled, "
            f"{pct(mean)} mean; line coverage {pct(cov)} pooled")
    out("By project (complete set of the primary analysis)")
    complete = [k for k in paired if all(f(x[k]) for x in (Mp, Sp)
                                         for f in (c2.has_mutation, c2.has_coverage))]
    for project in sorted({t.rsplit("-", 1)[0] for t in data.tags}):
        ks = [k for k in complete if k.rsplit("-", 1)[0] == project]
        if not ks:
            continue
        parts = []
        for arm in c3.ARMS:
            score, _, cov, _ = pooled([mut[(arm, k)] for k in ks])
            det = sum(data.verdicts[(arm, k)]["verdict"] == "Fail" for k in ks)
            parts.append(f"{arm} detected {det}, mutation {pct(score)}, lines {pct(cov)}")
        out(f"  {project:<13} n={len(ks):>2}  " + ";  ".join(parts))
    out("Mutants by PIT's status (every suite with a figure)")
    for arm in c3.ARMS:
        rows = [r for k, r in mut.items() if k[0] == arm and r["status"] == "ok"]
        out(f"  {arm}: " + ", ".join(f"{s} {sum(int(r[s]) for r in rows)}" for s in STATUSES))
    out("")

    out("Did PIT run the tests the measurement ran?")
    out("  (methods the filter kept, against methods_run_on_fixed of results/verdicts.csv;")
    out("   methods it left out, against the keys of the suite's excluded.txt)")
    agree = 0
    for (arm, t), r in sorted(mut.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if r["status"] != "ok":
            continue
        v = data.verdicts.get((arm, t))
        ran = int(v["methods_run_on_fixed"]) if v else -1
        if int(r["methods_kept"]) == ran and r["methods_left_out"] == r["keys_excluded"]:
            agree += 1
        else:
            out(f"  {t} {arm}: kept {r['methods_kept']}, measurement ran {ran}; "
                f"left out {r['methods_left_out']} of {r['keys_excluded']} keys")
    out(f"  {agree} of {len(ok)} suites with a figure agree on both counts")
    out("")

    out("THE SECOND CAMPAIGN'S H2, AS ITS ANALYSIS COMPUTES IT (for comparison; the")
    out("campaigns differ in more than the date of the faults, and in the mutation tool)")
    arms2 = c2.load_metrics(os.path.join(C2, "results", "agent-metrics.csv"))
    v2 = c2.read_violations(C2)
    M2 = {k: r for k, r in arms2.get("m2", {}).items() if ("m2", k) not in v2}
    S2 = {k: r for k, r in arms2.get("s2", {}).items() if ("s2", k) not in v2}
    h2(M2, S2, "Second campaign, complete set, runs with a violation left out", lines,
       names=("m2", "s2"))

    print("\n".join(lines))


if __name__ == "__main__":
    main()

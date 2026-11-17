#!/usr/bin/env python3
"""
Re-derive and tally the post-cutoff detection verdicts from the archived logs.

WHY THE VERDICTS ARE RE-DERIVED
-------------------------------
Until 2026-09-30 run-postcutoff.sh ran the generated suite on the buggy
revision with a bare `mvn test` and recorded `Fail` — a detection — whenever
Maven exited non-zero. The fixed-revision run passed -Drat.skip=true; the
buggy-revision run did not.

Apache Commons builds run the RAT licence audit before the tests. A test file
written in the specification-only sandbox carries no licence header, so on the
buggy revision the build stopped at rat-check and not one test executed:

    Files with unapproved licenses:
      /src/test/java/org/apache/commons/lang3/math/FractionAgentTest.java

Every specification-only "detection" in the first post-cutoff corpus was that:
seven of seven. The implementation-visible arm was not affected, because an
agent working inside the project copies the licence header from the tests
around it.

run-postcutoff.sh now skips RAT on both revisions and records `Fail` only when
the log shows a failing test of the generated suite. This script applies that
same rule to every archived buggy-revision log, so the published figures do
not rest on the .detection files written by the old rule:

    COMPILATION ERROR in the log            -> uncompilable_on_buggy
    a failing <...>AgentTest.<method> line  -> Fail
    BUILD FAILURE otherwise                 -> build_failed_not_detection
    otherwise                               -> Pass

A verdict counts only if the run's .status is `ok`. A subject whose latest run
failed can still have a .detection file left behind by an earlier attempt
(commons-lang-e4380908b, specification-only arm, in the matched corpus).

Usage:
    tally-postcutoff.py [runs_dir ...]          report
    tally-postcutoff.py --rewrite [runs_dir ...] also correct .detection files

    runs_dir defaults to data/postcutoff-first-runs and data/postcutoff-runs.
"""

import glob
import math
import os
import re
import sys

FAILING_TEST = re.compile(r"^\[ERROR\]\s+\w+AgentTest\.\w+[:(]", re.M)
SUREFIRE = re.compile(
    r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)\s*$",
    re.M)
ARMS = (("agent", "implementation-visible"), ("spec", "specification-only"))


def read(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def derive(log):
    """The verdict the current run-postcutoff.sh rule gives this log."""
    if "COMPILATION ERROR" in log:
        return "uncompilable_on_buggy"
    if FAILING_TEST.search(log):
        return "Fail"
    if "BUILD FAILURE" in log:
        return "build_failed_not_detection"
    return "Pass"


def executed(log):
    """Tests run in the last surefire summary of a log, or None."""
    if not log:
        return None
    runs = SUREFIRE.findall(log)
    return int(runs[-1][0]) if runs else None


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def tally(runs_dir, rewrite):
    print(f"=== {runs_dir}")
    subjects = sorted({os.path.basename(p).split(".")[0]
                       for p in glob.glob(os.path.join(runs_dir, "*.status"))})
    verdict = {}                                   # (subject, arm) -> verdict
    for arm, label in ARMS:
        ran = detected = pruned = tests = 0
        void, unusable, stale = [], [], []
        for s in subjects:
            base = os.path.join(runs_dir, f"{s}.{arm}")
            status = (read(base + ".status") or "").strip()
            recorded = (read(base + ".detection") or "").strip()
            log = read(base + ".buggy.log")
            derived = derive(log) if log is not None else ""

            if recorded and derived and recorded != derived:
                stale.append(f"{s}: recorded {recorded}, log says {derived}")
                if rewrite:
                    with open(base + ".detection", "w") as fh:
                        fh.write(derived + "\n")

            if status != "ok":
                unusable.append(f"{s}: {status or 'no status'}")
                continue
            ran += 1
            p = (read(base + ".pruned") or "0 0").split()
            n_run = executed(read(base + ".fixed.log"))
            pruned += int(p[0])
            tests += (n_run if n_run is not None else int(p[1]) - int(p[0])) \
                + int(p[0])
            if derived in ("Pass", "Fail"):
                verdict[(s, arm)] = derived
                detected += derived == "Fail"
            else:
                void.append(f"{s}: {derived or 'no buggy-revision log'}")

        valid = sum(1 for (s, a) in verdict if a == arm)
        rate = f" ({100 * detected / valid:.0f}%)" if valid else ""
        print(f"\n{label}: {ran} suites accepted, {valid} with a valid "
              f"verdict, {detected}/{valid} detected{rate}")
        if tests:
            print(f"  pruned {pruned} of {tests} tests "
                  f"({100 * pruned / tests:.1f}%)  [tests executed on the "
                  f"fixed revision, plus those pruned]")
        for title, items in (("no valid verdict", void),
                             ("not usable in this arm", unusable),
                             (".detection disagrees with the log"
                              + (" — rewritten" if rewrite else ""), stale)):
            if items:
                print(f"  {title}:")
                for item in items:
                    print(f"    {item}")

    both = sorted(s for s in subjects
                  if (s, "agent") in verdict and (s, "spec") in verdict)
    if both:
        m = sum(verdict[(s, "agent")] == "Fail" for s in both)
        sp = sum(verdict[(s, "spec")] == "Fail" for s in both)
        m_only = [s for s in both if verdict[(s, "agent")] == "Fail"
                  and verdict[(s, "spec")] != "Fail"]
        s_only = [s for s in both if verdict[(s, "spec")] == "Fail"
                  and verdict[(s, "agent")] != "Fail"]
        n = len(both)
        print(f"\npaired, {n} subjects with a valid verdict in both arms:")
        print(f"  implementation-visible {m}/{n} ({100 * m / n:.0f}%)   "
              f"specification-only {sp}/{n} ({100 * sp / n:.0f}%)")
        print(f"  detected by M only: {len(m_only)}   by S only: {len(s_only)}"
              f"   exact McNemar p = {mcnemar_exact(len(m_only), len(s_only)):.3f}")
    else:
        print("\nno subject has a valid verdict in both arms")
    print()


def main():
    args = sys.argv[1:]
    rewrite = "--rewrite" in args
    dirs = [a for a in args if a != "--rewrite"] or \
        ["data/postcutoff-first-runs", "data/postcutoff-runs"]
    for d in dirs:
        if not os.path.isdir(d):
            sys.exit(f"{d} not found")
        tally(d, rewrite)


if __name__ == "__main__":
    main()

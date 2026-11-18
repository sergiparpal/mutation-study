#!/usr/bin/env python3
"""
Descriptive figures of the second campaign, as quoted in the write-up.

None of this is a test. The tests the protocol fixes, and the decision they
lead to, are printed by bin/analyze-campaign2.py, which was committed before
the runs. This script was written after them. It adds what a reader needs to
follow the result bug by bug: which faults each arm detects, where the gap in
mutation score comes from, the tests disabled at acceptance per project, the
cost of the runs, how often the agents ran or compiled their tests and how
many of their calls the harness refused, the first campaign's arms beside the
second's, and EvoSuite beside both.

It reads only files already in data/ and uses the definitions of
analyze-campaign2.py (verdict, detection, pooled scores) by importing them.

Usage: ./bin/describe-campaign2.py        (from anywhere in the repository)
"""

import glob
import importlib.util
import json
import lzma
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C2 = os.path.join(ROOT, "data", "campaign2")

_spec = importlib.util.spec_from_file_location(
    "analysis", os.path.join(ROOT, "bin", "analyze-campaign2.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

ORDER = {p: i for i, p in enumerate(A.PROJECTS)}

# The first campaign's implementation-visible detections in which the suite,
# the closing message or the agent's note shows it knew the bug or its trigger
# test (write-up §3.9, bin/audit-trigger-leaks.py).
TRACE = [("Cli", "12"), ("Cli", "17"), ("Csv", "4"), ("Csv", "5"), ("Csv", "6"),
         ("Csv", "8"), ("Lang", "13"), ("Lang", "43"), ("Lang", "52"),
         ("Lang", "62"), ("Lang", "63")]


def ordered(keys):
    return sorted(keys, key=lambda k: (ORDER.get(k[0], 9), int(k[1])))


def names(keys):
    keys = ordered(keys)
    return ", ".join("-".join(k) for k in keys) if keys else "none"


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


def mutants(arm, keys):
    """generated, covered, killed, killed as Defects4J's table has it."""
    rows = [arm[k] for k in keys if A.has_mutation(arm[k])]
    return tuple(sum(int(r[c]) for r in rows) for c in
                 ("mut_generated", "mut_covered", "mut_killed", "mut_killed_d4j"))


def lines(arm, keys, what="lines"):
    rows = [arm[k] for k in keys if A.has_coverage(arm[k])]
    return (sum(int(r[f"{what}_covered"]) for r in rows),
            sum(int(r[f"{what}_total"]) for r in rows))


def score(row):
    return int(row["mut_killed"]) / int(row["mut_generated"])


def transcript(path, script):
    """Uses of the arm's script, whether the last one succeeded, calls refused.

    A use is a shell command that invokes the script (./test.sh, ./compile.sh)
    and got an answer from it. A refused call is one the harness did not
    perform: the permission layer's refusal, or a file tool sent outside the
    working copy. The sandbox denying a program is not counted here.
    """
    invoked = re.compile(r"(?<![\w.-])(?:\./|\./_tools/|_tools/|bash\s+|sh\s+)" + re.escape(script))
    commands, uses, last, refused = {}, 0, None, 0
    with lzma.open(path, "rt", errors="replace") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            message = obj.get("message") if isinstance(obj, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            for part in content if isinstance(content, list) else []:
                if part.get("type") == "tool_use" and part.get("name") == "Bash":
                    commands[part.get("id")] = (part.get("input") or {}).get("command", "")
                elif part.get("type") == "tool_result":
                    body = part.get("content")
                    if not isinstance(body, str):
                        body = " ".join(x.get("text", "") for x in body or []
                                        if isinstance(x, dict))
                    if body.startswith("Permission for this tool use was denied") \
                            or "--restricted confines" in body:
                        refused += 1
                        continue
                    if not invoked.search(commands.get(part.get("tool_use_id"), "")):
                        continue
                    if script == "test.sh":
                        if not re.search(r"JUnit version|OK \(\d+ tests?\)|FAILURES!!!", body):
                            continue
                        ok = bool(re.search(r"OK \(\d+ tests?\)", body)) and "FAILURES!!!" not in body
                    else:
                        ok = "compiled OK" in body
                    uses += 1
                    last = ok
    return uses, last, refused


def section(title):
    print()
    print(title)
    print("-" * len(title))


def main():
    new = A.load_metrics(os.path.join(C2, "results", "agent-metrics.csv"))
    old = A.load_metrics(A.FIRST)
    if "m2" not in new or "s2" not in new:
        print("the second campaign has not been measured")
        return
    M, S = new["m2"], new["s2"]
    FM, FS, EVO = old.get("agent", {}), old.get("spec", {}), old.get("evosuite", {})

    paired = ordered(k for k in M if k in S and A.has_verdict(M[k]) and A.has_verdict(S[k]))
    complete = [k for k in paired if all(f(a[k]) for a in (M, S)
                                         for f in (A.has_mutation, A.has_coverage))]

    section(f"Detections, on the {len(paired)} bugs of the paired set")
    dm = [k for k in paired if A.detected(M[k])]
    ds = [k for k in paired if A.detected(S[k])]
    print(f"  m2 ({len(dm)}): {names(dm)}")
    print(f"  s2 ({len(ds)}): {names(ds)}")
    print(f"  both ({len(set(dm) & set(ds))}): {names(set(dm) & set(ds))}")
    print(f"  m2 only ({len(set(dm) - set(ds))}): {names(set(dm) - set(ds))}")
    print(f"  s2 only ({len(set(ds) - set(dm))}): {names(set(ds) - set(dm))}")
    for label, arm in (("m2", M), ("s2", S)):
        fails = sorted(int(arm[k]["num_trigger"]) for k in paired if A.detected(arm[k]))
        print(f"  {label}: tests failing on the buggy revision, per detecting suite: "
              f"{fails}; one test only in {sum(n == 1 for n in fails)} of {len(fails)}")
    print("  outside the paired set: " + "; ".join(
        f"{'-'.join(k)} (m2 {A.verdict(M[k])}, s2 {A.verdict(S.get(k))})"
        for k in ordered(M) if k not in paired))
    print("  in the paired set without a mutation score in both arms: "
          + names(k for k in paired if k not in complete))

    section(f"Mutation score and coverage, on the {len(complete)} bugs of the complete set")
    for label, arm in (("m2", M), ("s2", S)):
        gen, cov, kill, d4j = mutants(arm, complete)
        lc, lt = lines(arm, complete)
        bc, bt = lines(arm, complete, "branches")
        print(f"  {label}: {kill} of {gen} mutants killed ({pct(kill, gen)}); "
              f"never executed {pct(gen - cov, gen)}; killed among those executed "
              f"{pct(kill, cov)}; Defects4J's table would say {pct(d4j, gen)}")
        print(f"      lines {pct(lc, lt)}, branches {pct(bc, bt)}")
    diffs = [score(M[k]) - score(S[k]) for k in complete]
    up, down = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    print(f"  mutation score per bug: m2 higher in {up}, s2 higher in {down}, equal in "
          f"{len(diffs) - up - down}; mean difference {100 * sum(diffs) / len(diffs):+.1f} "
          f"points; sign test p = {A.mcnemar(up, down):.1e}")
    print("      not higher in m2: " + ", ".join(
        f"{'-'.join(k)} ({100 * score(M[k]):.0f}% and {100 * score(S[k]):.0f}%)"
        for k in complete if score(M[k]) <= score(S[k])))
    cov_up = sum(int(M[k]["lines_covered"]) > int(S[k]["lines_covered"]) for k in complete)
    print(f"  line coverage per bug: m2 higher in {cov_up} of {len(complete)}")

    section("Tests disabled at acceptance, per project")
    for arm in ("m2", "s2"):
        per = {}
        for f in glob.glob(os.path.join(C2, f"runs-{arm}", "*.pruned")):
            pruned, total = map(int, open(f).read().split()[:2])
            entry = per.setdefault(os.path.basename(f).split("-")[0], [0, 0, 0])
            entry[0] += pruned
            entry[1] += total
            entry[2] += pruned > 0
        p, t, n = (sum(v[i] for v in per.values()) for i in range(3))
        print(f"  {arm}: {p} of {t} ({pct(p, t)}), in {n} suites")
        for pid in A.PROJECTS:
            if pid in per and per[pid][0]:
                print(f"      {pid:<5} {per[pid][0]:>3} / {per[pid][1]:<4} {pct(*per[pid][:2])}")

    section("Runs")
    for arm in ("m2", "s2"):
        cost, turns, minutes, capped = [], [], [], []
        for f in sorted(glob.glob(os.path.join(C2, f"runs-{arm}", "*.meta.json"))):
            rec = json.load(open(f[:-len(".meta.json")] + ".json"))
            cost.append(rec.get("total_cost_usd") or 0)
            turns.append(rec.get("num_turns") or 0)
            minutes.append((rec.get("duration_ms") or 0) / 60000)
            if rec.get("subtype") != "success":
                capped.append(f"{os.path.basename(f)[:-len('.meta.json')]} ({rec.get('subtype')})")
        n = len(cost)
        print(f"  {arm}: {n} runs; list price ${sum(cost):.2f}, ${sum(cost) / n:.2f} a suite, "
              f"at most ${max(cost):.2f}; turns {sum(turns) / n:.1f} a run, median "
              f"{sorted(turns)[n // 2]}, at most {max(turns)}; {sum(minutes):.0f} minutes in all")
        print("      not ended by the agent: " + (", ".join(capped) if capped else "none"))

    section("What the transcripts show")
    for arm, script in (("m2", "test.sh"), ("s2", "compile.sh")):
        runs = used = last_ok = uses = refused = refused_runs = 0
        for path in sorted(glob.glob(os.path.join(C2, f"runs-{arm}", "*.stream.jsonl.xz"))):
            n, last, denied = transcript(path, script)
            runs += 1
            used += n > 0
            uses += n
            last_ok += bool(last)
            refused += denied
            refused_runs += denied > 0
        what = "ran their tests" if arm == "m2" else "compiled their tests"
        print(f"  {arm}: {used} of {runs} agents {what} with {script}, {uses} times in all; "
              f"the last time succeeded in {last_ok}")
        print(f"      calls the harness refused: {refused}, in {refused_runs} runs")

    section("The first campaign's arms beside the second's (descriptive)")
    for old_arm, new_arm, a, b in ((FM, M, "first M", "m2"), (FS, S, "first S", "s2")):
        ks = ordered(k for k in new_arm if k in old_arm
                     and A.has_verdict(new_arm[k]) and A.has_verdict(old_arm[k]))
        was = {k for k in ks if A.detected(old_arm[k])}
        now = {k for k in ks if A.detected(new_arm[k])}
        print(f"  {len(ks)} bugs with a verdict in both: {a} {len(was)}, {b} {len(now)}, "
              f"both {len(was & now)}")
        print(f"      {a} only: {names(was - now)}")
        print(f"      {b} only: {names(now - was)}")
        print("      without a verdict in the first campaign: " + "; ".join(
            f"{'-'.join(k)} ({b} {A.verdict(new_arm[k])})"
            for k in ordered(new_arm) if k not in ks))
    trace = [k for k in TRACE if k in M and A.has_verdict(M[k])]
    plain = [k for k in FM if A.detected(FM[k]) and k not in TRACE
             and k in M and A.has_verdict(M[k])]
    print(f"  of the {len(trace)} first-campaign detections with a trace of the benchmark's "
          f"metadata, m2 detects {sum(A.detected(M[k]) for k in trace)}; not "
          + names(k for k in trace if not A.detected(M[k])))
    print(f"  of the {len(plain)} without one, m2 detects "
          f"{sum(A.detected(M[k]) for k in plain)}; not "
          + names(k for k in plain if not A.detected(M[k])))

    three = ordered(k for k in M if k in S and k in EVO
                    and all(A.has_verdict(a[k]) for a in (M, S, EVO)))
    section(f"EvoSuite beside both arms, on the {len(three)} bugs with a verdict from each")
    for label, arm in (("m2", M), ("EvoSuite", EVO), ("s2", S)):
        gen, cov, kill, _ = mutants(arm, three)
        lc, lt = lines(arm, three)
        det = sum(A.detected(arm[k]) for k in three)
        with_mut = [k for k in three if A.has_mutation(arm[k])]
        mean = sum(score(arm[k]) for k in with_mut) / len(with_mut)
        print(f"  {label:<9} detected {det}/{len(three)} ({pct(det, len(three))})  "
              f"mutation {pct(kill, gen)} (mean {100 * mean:.1f}%, n={len(with_mut)})  "
              f"killed among executed {pct(kill, cov)}  "
              f"lines {pct(lc, lt)} (n={sum(A.has_coverage(arm[k]) for k in three)})")
    for label, arm in (("m2", M), ("s2", S)):
        both, only, evo_only, neither = A.two_by_two(arm, EVO, three)
        print(f"  {label} and EvoSuite: both {both}, {label} only {only}, EvoSuite only "
              f"{evo_only}, neither {neither}; union {both + only + evo_only} "
              f"({pct(both + only + evo_only, len(three))}); "
              f"exact McNemar p = {A.mcnemar(only, evo_only):.3g}")
    print("  not among them: " + names(k for k in M if k not in three))


if __name__ == "__main__":
    main()

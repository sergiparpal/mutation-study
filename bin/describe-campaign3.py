#!/usr/bin/env python3
"""
Descriptive figures of the third campaign, as quoted in the write-up.

None of this is a test. The test the protocol fixes, and the decision it
leads to, are printed by bin/analyze-campaign3.py, which was committed before
the runs. This script was written after them. It adds what a reader needs to
follow the result subject by subject: which faults each arm detects, the tests
left out at acceptance per project, turns and cost, how the agents used the
scripts they were given, and the counts behind the audit's account of what
the agents tried: the shared temporary directory, searches of the whole file
system, the jars in lib/, python, direct calls to the compiler. Last, added on
19 November 2026 after bin/mutation-campaign3.sh had been run: mutation score
and line coverage subject by subject, which bin/analyze-mutation-campaign3.py
gives only pooled.

It reads only files already in data/campaign3 and takes the transcript reader
of bin/audit-campaign3.py and the definitions of bin/analyze-campaign3.py by
importing them.

Usage: ./bin/describe-campaign3.py        (from anywhere in the repository)
"""

import collections
import csv
import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C3 = os.path.join(ROOT, "data", "campaign3")
ARMS = ("m3", "s3")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("analysis3", "analyze-campaign3.py")
AUDIT = load("audit3", "audit-campaign3.py")

HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n\1\b", re.S)
REFUSED = "Permission for this tool use was denied"
RESTRICTED = "--restricted confines"


def project(tag):
    return tag.rsplit("-", 1)[0]


def short(tags):
    tags = sorted(tags)
    return ", ".join(tags) if tags else "none"


def section(title):
    print()
    print(title)
    print("-" * len(title))


def commands(arm, tag):
    """(command without here-document bodies, result) for every shell command."""
    path = os.path.join(C3, f"runs-{arm}", tag + ".stream.jsonl.xz")
    _, cmds, _, _, results, _ = AUDIT.transcript(path)
    return [(HEREDOC.sub(" ", cmd), results.get(cid, "")) for cid, cmd in cmds]


def main():
    data = A.Data(C3)
    tags = data.tags
    viol = data.violations

    section("Runs")
    for arm in ARMS:
        turns, cost, left, total, suites = [], [], 0, 0, 0
        per = collections.defaultdict(lambda: [0, 0])
        for t in tags:
            base = os.path.join(C3, f"runs-{arm}", t)
            r = json.load(open(base + ".json"))
            turns.append(r["num_turns"])
            cost.append(r["total_cost_usd"])
            a, b = (int(x) for x in open(base + ".pruned").read().split())
            left += a
            total += b
            suites += a > 0
            per[project(t)][0] += a
            per[project(t)][1] += b
        print(f"  {arm}: {total} tests, {left} left out at acceptance "
              f"({100 * left / total:.1f}%), in {suites} of {len(tags)} suites")
        print("      per project: " + "; ".join(
            f"{p} {a} of {b} ({100 * a / b:.1f}%)" for p, (a, b) in sorted(per.items())))
        print(f"      turns a run: mean {sum(turns) / len(turns):.1f}, fewest {min(turns)}, "
              f"most {max(turns)}; ${sum(cost):.2f}, ${sum(cost) / len(cost):.2f} a suite")

    section("Verdicts")
    for arm in ARMS:
        c = collections.Counter(data.verdict(arm, t) for t in tags)
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda x: str(x[0]))))
    for label, skip in (("paired set (runs with a violation left out)", viol),
                        ("with those runs included", set())):
        paired = data.paired(tags, skip)
        dm = {t for t in paired if data.verdict("m3", t) == "Fail"}
        ds = {t for t in paired if data.verdict("s3", t) == "Fail"}
        print(f"  {label}: {len(paired)} subjects")
        print(f"      both ({len(dm & ds)}): {short(dm & ds)}")
        print(f"      m3 only ({len(dm - ds)}): {short(dm - ds)}")
        print(f"      s3 only ({len(ds - dm)}): {short(ds - dm)}")

    section("What the agents did (from the transcripts)")
    for arm, script, ok in (("m3", "_tools/test.sh", r"(^|\n)OK\b"), ("s3", "compile.sh", "compiled OK")):
        last_ok = 0
        for t in tags:
            last = None
            for cmd, res in commands(arm, t):
                if REFUSED in res[:200]:
                    continue
                for part in re.split(r"&&|\|\||[;\n]", cmd):
                    if re.match(r"\s*(\w+=\S+\s+)*(bash\s+|sh\s+)?(\./)?" + re.escape(script) + r"\b", part):
                        last = res
            last_ok += bool(last and re.search(ok, last))
        print(f"  {arm}: runs in which the last execution of {script} succeeded: {last_ok} of {len(tags)}")

    names = collections.defaultdict(set)
    refused = collections.Counter()
    for arm in ARMS:
        for t in tags:
            path = os.path.join(C3, f"runs-{arm}", t + ".stream.jsonl.xz")
            for obj in AUDIT.read_stream(path):
                if obj.get("type") == "system" and obj.get("subtype") == "permission_denied":
                    refused[arm] += 1
            for cmd, res in commands(arm, t):
                if re.search(r"\$\{?TMPDIR\b|/tmp/claude-\d+", cmd):
                    names[(arm, "name the shared temporary directory")].add(t)
                if re.search(r"\bfind\s+/\s", cmd):
                    names[(arm, "search the whole file system by name")].add(t)
                if re.search(r"/usr/share\b", cmd):
                    names[(arm, "name /usr/share")].add(t)
                if arm == "s3":
                    if re.search(r"(?<![\w/.-])(unzip|jar\s+-?[a-z]*t[a-z]*)\b[^|;&\n]*\.jar", cmd):
                        names[(arm, "call unzip or jar on a jar of lib/")].add(t)
                    if re.search(r"(?<![\w/.-])python3?\b", cmd):
                        names[(arm, "call python")].add(t)
                    if re.search(r"(?<![\w/.-])javac\s+[^|;&\n]*\.java\b", cmd) and REFUSED not in res[:200]:
                        names[(arm, "call javac on a source file")].add(t)
    for arm in ARMS:
        print(f"  {arm}: calls the harness refused: {refused[arm]}")
        for (a, what), runs in sorted(names.items()):
            if a == arm:
                print(f"      runs that {what} ({len(runs)}): {short(runs)}")

    mutation(data)


def mutation(data):
    """Mutation score and line coverage, subject by subject.

    Added on 19 November 2026, after bin/mutation-campaign3.sh had been run.
    The set is the complete set of bin/analyze-mutation-campaign3.py: the
    paired set, runs with a violation left out, with a PIT figure in both arms.
    """
    section("Mutation score and line coverage with PIT (bin/mutation-campaign3.sh), subject by subject")
    path = os.path.join(C3, "mutation", "mutation.csv")
    if not os.path.exists(path):
        print("  not measured")
        return
    with open(path) as fh:
        mut = {(r["arm"], r["subject"]): r for r in csv.DictReader(fh)}

    def score(arm, t):
        r = mut[(arm, t)]
        return int(r["detected"]) / int(r["generated"])

    def lines(arm, t):
        r = mut[(arm, t)]
        return int(r["lines_covered"]) / int(r["lines_total"])

    complete = [t for t in data.paired(data.tags, data.violations)
                if all(mut.get((a, t), {}).get("status") == "ok" and int(mut[(a, t)]["generated"])
                       and int(mut[(a, t)]["lines_total"] or 0) for a in ARMS)]
    print(f"  complete set: {len(complete)} subjects")
    print("  subject                    detected     mutation score    line coverage")
    print("                             m3    s3      m3      s3       m3      s3")
    for t in sorted(complete, key=lambda t: (project(t), t)):
        print(f"  {t:<26} {data.verdict('m3', t):<5} {data.verdict('s3', t):<5}"
              f"  {100 * score('m3', t):5.1f}%  {100 * score('s3', t):5.1f}%"
              f"   {100 * lines('m3', t):5.1f}%  {100 * lines('s3', t):5.1f}%")
    for label, f in (("mutation score", score), ("line coverage", lines)):
        higher = {t for t in complete if f("m3", t) > f("s3", t)}
        lower = {t for t in complete if f("m3", t) < f("s3", t)}
        same = set(complete) - higher - lower
        print(f"  {label}: m3 higher in {len(higher)}, s3 higher in {len(lower)} ({short(lower)}), "
              f"equal in {len(same)} ({short(same)})")
    for arm in ARMS:
        det = sum(int(mut[(arm, t)]["detected"]) for t in complete)
        gen = sum(int(mut[(arm, t)]["generated"]) for t in complete)
        unreached = sum(int(mut[(arm, t)]["no_coverage"]) for t in complete)
        print(f"  {arm}: of the {gen} mutants, {gen - unreached} reached by a test; "
              f"detected {det}, {100 * det / gen:.1f}% of all and {100 * det / (gen - unreached):.1f}% "
              f"of those reached")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Descriptive figures of the fourth campaign, as quoted in the write-up.

None of this is a test. The tests the protocol fixes, and the decisions they
lead to, are printed by bin/analyze-campaign4.py, which was committed with the
protocol before the runs. This script was written after the analysis, on 21
November 2026. It adds what a reader needs to follow the result subject by
subject:

- the tests left out at acceptance per project, turns and cost;
- which faults each arm detects, with the class each fix modifies;
- some counts from the transcripts behind the audit's account of what the
  agents tried: the jars of lib/, python, java, direct calls to the compiler,
  calls the harness refused;
- mutation score and line coverage subject by subject. The analysis gives
  them only pooled and as means over suites. Here they are with the share of
  mutants the tests reach, and with the subjects whose fix is in StringUtils
  apart from the rest, since those hold a third of the mutants.

It reads only files already in data/campaign4. It takes the definitions of
bin/analyze-campaign4.py and the transcript reader of bin/audit-campaign4.py
by importing them.

Usage: ./bin/describe-campaign4.py        (from anywhere in the repository)
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
C4 = os.path.join(ROOT, "data", "campaign4")
ARMS = ("m4", "s4")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("analysis4", "analyze-campaign4.py")
AUDIT = load("audit4", "audit-campaign4.py")

HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n\1\b", re.S)
REFUSED = "Permission for this tool use was denied"
# What the transcripts are searched for, in s4 commands with their
# here-documents removed. A program counts where it is called: at the start
# of a command, after a pipe, a separator, `$(` or an assignment, not where
# `which` or `command -v` asks for it.
CALLED = r"(?:^|[;&|\n(`]|\$\(|\bxargs\s|\bexec\s|\b\w+=\S*\s)\s*(?:[\w./-]*/)?"
PATTERNS = (
    ("call unzip, jar, javap or zipinfo on a jar",
     re.compile(CALLED + r"(?:unzip|jar|javap|zipinfo)\s[^|;&\n]*\.jar\b"
                r"|\bfind\s[^|;&\n]*\.jar\S*\s[^|;&\n]*-exec\s+(?:unzip|jar|javap|zipinfo)\b")),
    ("call python", re.compile(CALLED + r"python3?\b")),
    ("ask for java -version", re.compile(CALLED + r"java\s+-version\b")),
    ("run a class with java", re.compile(CALLED + r"java\s+-(?:cp|classpath)\b")),
    ("call javac on a source file or a list of them",
     re.compile(CALLED + r"javac\s[^|;&\n]*(?:\.java\b|\s@\S)")),
)


def project(tag):
    return tag.rsplit("-", 1)[0]


def short(tags):
    tags = sorted(tags)
    return ", ".join(tags) if tags else "none"


def section(title):
    print()
    print(title)
    print("-" * len(title))


def fixed_classes(tag):
    path = os.path.join(C4, "subjects", tag, "classes.txt")
    return [l.strip() for l in open(path) if l.strip()]


def commands(arm, tag):
    """(command without here-document bodies, result) for every shell command."""
    path = os.path.join(C4, f"runs-{arm}", tag + ".stream.jsonl.xz")
    _, cmds, _, _, results, _ = AUDIT.transcript(path)
    return [(HEREDOC.sub(" ", cmd), results.get(cid, "")) for cid, cmd in cmds]


def runs(data):
    section("Runs")
    for arm in ARMS:
        turns, cost, left, total, suites, with_left = [], [], 0, 0, 0, 0
        per = collections.defaultdict(lambda: [0, 0])
        limit = collections.Counter()
        for t in data.tags:
            base = os.path.join(C4, f"runs-{arm}", t)
            r = json.load(open(base + ".json"))
            turns.append(r["num_turns"])
            cost.append(r["total_cost_usd"])
            if r.get("subtype") != "success":
                limit[(r.get("subtype"), os.path.exists(base + ".pruned"))] += 1
            if not os.path.exists(base + ".pruned"):
                continue
            a, b = (int(x) for x in open(base + ".pruned").read().split())
            suites += 1
            left += a
            total += b
            with_left += a > 0
            per[project(t)][0] += a
            per[project(t)][1] += b
        print(f"  {arm}: {suites} suites, {total} tests, {left} left out at acceptance "
              f"({100 * left / total:.1f}%), in {with_left} suites")
        print("      per project: " + "; ".join(
            f"{p} {a} of {b} ({100 * a / b:.1f}%)" for p, (a, b) in sorted(per.items())))
        print(f"      turns a run: mean {sum(turns) / len(turns):.1f}, fewest {min(turns)}, "
              f"most {max(turns)}; ${sum(cost):.2f}, ${sum(cost) / suites:.2f} a suite")
        print("      runs that did not end by the agent's decision: " + (", ".join(
            f"{n} {kind}, {'with' if kept else 'without'} an accepted suite"
            for (kind, kept), n in sorted(limit.items())) or "none"))


def verdicts(data):
    section("Verdicts")
    for arm in ARMS:
        c = collections.Counter(data.verdict(arm, t) or "no suite" for t in data.tags)
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    paired = data.paired(data.tags, data.violations)
    dm = {t for t in paired if data.detected("m4", t)}
    ds = {t for t in paired if data.detected("s4", t)}
    print(f"  paired set: {len(paired)} subjects")
    for label, group in (("both", dm & ds), ("m4 only", dm - ds), ("s4 only", ds - dm)):
        print(f"      {label} ({len(group)}):")
        for t in sorted(group, key=lambda t: (project(t), t)):
            print(f"          {t:<24} {data.info[t]['type']:<15} "
                  + ", ".join(c.rsplit(".", 1)[-1] for c in fixed_classes(t)))


def transcripts(data):
    section("What the s4 agents did (from the transcripts)")
    tried = collections.defaultdict(set)      # any command
    ran = collections.defaultdict(set)        # a command the harness ran
    refused_cmds = collections.Counter()      # commands the harness refused
    refused = collections.Counter()
    for arm in ARMS:
        for t in data.tags:
            path = os.path.join(C4, f"runs-{arm}", t + ".stream.jsonl.xz")
            for obj in AUDIT.read_stream(path):
                if obj.get("type") == "system" and obj.get("subtype") == "permission_denied":
                    refused[arm] += 1
            if arm != "s4":
                continue
            for cmd, res in commands(arm, t):
                for what, pattern in PATTERNS:
                    if pattern.search(cmd):
                        tried[what].add(t)
                        if REFUSED in res[:200]:
                            refused_cmds[what] += 1
                        else:
                            ran[what].add(t)
    for arm in ARMS:
        print(f"  {arm}: calls the harness refused: {refused[arm]}")
    for what, _ in PATTERNS:
        print(f"  s4 runs that {what}: {len(tried[what])}; in a command the harness ran: "
              f"{len(ran[what])}; commands the harness refused: {refused_cmds[what]}")
        print(f"      {short(tried[what])}")


def mutation(data):
    section("Mutation score and line coverage with PIT (bin/mutation-campaign4.sh), subject by subject")
    mut = data.mutation

    def ok(arm, t):
        r = mut.get((arm, t))
        return r and r["status"] == "ok" and int(r["generated"]) > 0 and int(r["lines_total"] or 0) > 0

    def score(arm, t):
        r = mut[(arm, t)]
        return int(r["detected"]) / int(r["generated"])

    def lines(arm, t):
        r = mut[(arm, t)]
        return int(r["lines_covered"]) / int(r["lines_total"])

    complete = [t for t in data.paired(data.tags, data.violations) if all(ok(a, t) for a in ARMS)]
    print(f"  complete set: {len(complete)} subjects")
    print("  subject                  detected     mutants  mutation score    line coverage   fixed class")
    print("                           m4    s4               m4      s4        m4      s4")
    for t in sorted(complete, key=lambda t: (project(t), t)):
        print(f"  {t:<24} {data.verdict('m4', t):<5} {data.verdict('s4', t):<5}"
              f"  {mut[('m4', t)]['generated']:>6}"
              f"  {100 * score('m4', t):5.1f}%  {100 * score('s4', t):5.1f}%"
              f"    {100 * lines('m4', t):5.1f}%  {100 * lines('s4', t):5.1f}%   "
              + ", ".join(c.rsplit(".", 1)[-1] for c in fixed_classes(t)))
    for label, f in (("mutation score", score), ("line coverage", lines)):
        higher = {t for t in complete if f("m4", t) > f("s4", t)}
        lower = {t for t in complete if f("m4", t) < f("s4", t)}
        same = set(complete) - higher - lower
        print(f"  {label}: m4 higher in {len(higher)}, s4 higher in {len(lower)}, "
              f"equal in {len(same)}")

    def pooled(arm, ks):
        gen = sum(int(mut[(arm, t)]["generated"]) for t in ks)
        det = sum(int(mut[(arm, t)]["detected"]) for t in ks)
        unreached = sum(int(mut[(arm, t)]["no_coverage"]) for t in ks)
        return gen, det, unreached

    for arm in ARMS:
        gen, det, unreached = pooled(arm, complete)
        mean = sum(score(arm, t) for t in complete) / len(complete)
        print(f"  {arm}: of the {gen} mutants, {gen - unreached} ({100 * (gen - unreached) / gen:.1f}%) "
              f"reached by a test; detected {det}, {100 * det / gen:.1f}% of all and "
              f"{100 * det / (gen - unreached):.1f}% of those reached; mean over suites {100 * mean:.1f}%")

    strings = [t for t in complete if "org.apache.commons.lang3.StringUtils" in fixed_classes(t)]
    rest = [t for t in complete if t not in strings]
    total = pooled("m4", complete)[0]
    in_strings = pooled("m4", strings)[0]
    print(f"  subjects whose fix is in StringUtils: {len(strings)}, {in_strings} of the {total} mutants "
          f"of each arm ({100 * in_strings / total:.1f}%)")
    print("      " + short(strings))
    for label, ks in (("those subjects", strings), (f"the other {len(rest)}", rest)):
        parts = []
        for arm in ARMS:
            gen, det, unreached = pooled(arm, ks)
            parts.append(f"{arm} {100 * det / gen:.1f}% (reached {100 * (gen - unreached) / gen:.1f}%)")
        det = collections.Counter((data.verdict("m4", t), data.verdict("s4", t)) for t in ks)
        print(f"  {label}: pooled mutation score " + ", ".join(parts)
              + "; verdicts m4/s4 " + ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(det.items())))


def main():
    data = A.Data(C4)
    runs(data)
    verdicts(data)
    transcripts(data)
    mutation(data)


if __name__ == "__main__":
    main()

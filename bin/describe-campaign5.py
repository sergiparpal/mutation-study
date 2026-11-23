#!/usr/bin/env python3
"""
Descriptive figures of the fifth campaign, as quoted in the write-up.

None of this is a test. The estimate and the test that the protocol fixes,
and the decision they lead to, are printed by bin/analyze-campaign5.py, which
was committed with the protocol before the runs. This script was written after
the analysis, on 23 November 2026. It adds what a reader needs to follow the
result subject by subject:

- when the runs were made, before and after the deviation of 22 November;
  their turns and cost; the tests left out at acceptance;
- which faults each arm certifies or detects, and for each b5 suite that
  certifies, the tests that fail on the fix commit and the fix's subject line;
- how many failing tests each Fail rests on;
- the subjects whose verdict differs between m4 and m5, the same condition
  run twice;
- some counts from the transcripts: calls the harness refused, runs that see
  the folders the CLI's sandbox mounts in the working copy (.claude, .vscode);
- mutation score as means over suites, and subject by subject.

It reads only files already in data/campaign5, and the fourth campaign's
verdicts and subject records. It takes the definitions of
bin/analyze-campaign5.py and the transcript reader of bin/audit-campaign5.py
by importing them.

Usage: ./bin/describe-campaign5.py        (from anywhere in the repository)
"""

import collections
import csv
import importlib.util
import json
import lzma
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C5 = os.path.join(ROOT, "data", "campaign5")
RECORDS = os.path.join(ROOT, "data", "campaign4", "subjects")
ARMS = ("b5", "m5")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("analysis5", "analyze-campaign5.py")
AUDIT = load("audit5", "audit-campaign5.py")


def project(tag):
    return tag.rsplit("-", 1)[0]


def section(title):
    print()
    print(title)
    print("-" * len(title))


def meta(tag):
    return dict(l.rstrip("\n").split("=", 1) for l in open(os.path.join(RECORDS, tag, "meta.txt")) if "=" in l)


def fixed_classes(tag):
    return [l.strip().rsplit(".", 1)[-1] for l in open(os.path.join(RECORDS, tag, "classes.txt")) if l.strip()]


def failing_on_other(tag, arm):
    """The keys that fail on the other revision, from the measurement's report."""
    path = os.path.join(C5, "results", f"{tag}.{arm}.other.tsv")
    out = []
    for line in open(path, errors="replace") if os.path.exists(path) else []:
        cols = line.rstrip("\n").split("\t")
        if cols and cols[0] == "FAILED":
            out.append((cols[2], cols[5] if len(cols) > 5 else ""))
    return out


def runs(data):
    section("Runs")
    for arm in ARMS:
        turns, cost, left, total, with_left = [], [], 0, 0, 0
        commits = collections.Counter()
        started, finished = {}, {}
        limit = collections.Counter()
        for t in data.tags:
            base = os.path.join(C5, f"runs-{arm}", t)
            r = json.load(open(base + ".json"))
            m = json.load(open(base + ".meta.json"))
            turns.append(r["num_turns"])
            cost.append(r["total_cost_usd"])
            commits[m["commit"][:7]] += 1
            started[t], finished[t] = m["started"], m["finished"]
            if r.get("subtype") != "success":
                limit[r.get("subtype")] += 1
            a, b = (int(x) for x in open(base + ".pruned").read().split())
            left += a
            total += b
            with_left += a > 0
        print(f"  {arm}: {len(data.tags)} suites, {total} tests, {left} left out at acceptance "
              f"({100 * left / total:.1f}%), in {with_left} suites")
        print(f"      turns a run: mean {sum(turns) / len(turns):.1f}, fewest {min(turns)}, most {max(turns)}; "
              f"${sum(cost):.2f}, ${sum(cost) / len(cost):.2f} a suite")
        print("      runs that did not end by the agent's decision: "
              + (", ".join(f"{n} {k}" for k, n in sorted(limit.items())) or "none"))
        print("      runs by the commit they were made from: "
              + ", ".join(f"{c} {n}" for c, n in sorted(commits.items())))
        print(f"      first start {min(started.values())}, last finish {max(finished.values())}")


def verdicts(data):
    section("Verdicts")
    for arm in ARMS:
        c = collections.Counter(data.verdict(arm, t) or "no suite" for t in data.tags)
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    paired = data.paired(data.tags, data.violations)
    cb = {t for t in paired if data.fail("b5", t)}
    dm = {t for t in paired if data.fail("m5", t)}
    print(f"  paired set: {len(paired)} subjects")
    for label, group in (("b5 certifies and m5 detects", cb & dm), ("b5 alone certifies", cb - dm),
                         ("m5 alone detects", dm - cb)):
        print(f"      {label} ({len(group)}):")
        for t in sorted(group, key=lambda t: (project(t), t)):
            print(f"          {t:<24} {data.info[t]['type']:<15} " + ", ".join(fixed_classes(t)))
    print("  how many failing tests a Fail rests on:")
    for arm in ARMS:
        n = collections.Counter(len(failing_on_other(t, arm)) for t in paired if data.fail(arm, t))
        print(f"      {arm}: " + ", ".join(f"{k} test{'s' if k != 1 else ''}: {v}" for k, v in sorted(n.items())))


def certifying(data):
    section("The b5 suites that certify the fault: what fails on the fix commit")
    for t in sorted(t for t in data.tags if data.fail("b5", t)):
        print(f"  {t}  ({data.info[t]['type']}; m5 {data.verdict('m5', t)})")
        print(f"      fix: {meta(t)['subject']}")
        for key, message in failing_on_other(t, "b5"):
            print(f"      fails: {key.split('.')[-1]}")
            print(f"          {' '.join(message.split())[:160]}")


def repetition(data):
    section("m4 beside m5, the same condition run twice")
    four = A.read_csv(os.path.join(ROOT, "data", "campaign4", "results", "verdicts.csv"))
    m4 = {t: four[("m4", t)]["verdict"] for t in data.tags if ("m4", t) in four}
    changed = [t for t in data.tags if m4.get(t) in ("Pass", "Fail")
               and data.verdict("m5", t) in ("Pass", "Fail") and m4[t] != data.verdict("m5", t)]
    print(f"  subjects with a verdict in both: {sum(1 for t in data.tags if m4.get(t) in ('Pass', 'Fail'))}")
    print(f"  verdict differs: {len(changed)}")
    for t in sorted(changed, key=lambda t: (project(t), t)):
        print(f"      {t:<24} {data.info[t]['type']:<15} m4 {m4[t]:<5} m5 {data.verdict('m5', t)}")


def transcripts(data):
    section("From the transcripts")
    refused = collections.Counter()
    folder = collections.Counter()      # a listing shows the .claude folder
    files = collections.Counter()       # ... with the files the sandbox puts in it
    writes = collections.defaultdict(list)
    for arm in ARMS:
        for t in data.tags:
            path = os.path.join(C5, f"runs-{arm}", t + ".stream.jsonl.xz")
            for obj in AUDIT.read_stream(path):
                if obj.get("type") == "system" and obj.get("subtype") == "permission_denied":
                    refused[arm] += 1
            text = lzma.open(path, "rt", errors="replace").read()
            has_files = ".claude/loop.md" in text or ".claude/skills" in text
            files[arm] += has_files
            folder[arm] += has_files or ".claude/.cc-writes" in text
            if ".cc-writes/" in text:
                writes[arm].append(t)
    for arm in ARMS:
        print(f"  {arm}: calls the harness refused {refused[arm]}")
        print(f"      runs in which a command lists the .claude folder the sandbox mounts in the "
              f"working copy: {folder[arm]}, {files[arm]} of them with the files in it")
        print(f"      runs that name a path inside its .cc-writes area: {', '.join(writes[arm]) or 'none'}")


def mutation(data):
    section("Mutation score (bin/mutation-campaign5.sh), each arm on its own revision")
    keys = [t for t in data.paired(data.tags, data.violations) if all(data.scored(a, t) for a in ARMS)]

    def score(arm, t):
        r = data.mutation[(arm, t)]
        return int(r["detected"]) / int(r["generated"])
    for arm in ARMS:
        s = [score(arm, t) for t in keys]
        print(f"  {arm}: mean over {len(s)} suites {100 * sum(s) / len(s):.1f}%")
    hi_b = sum(score("b5", t) > score("m5", t) for t in keys)
    hi_m = sum(score("m5", t) > score("b5", t) for t in keys)
    print(f"  subject by subject: b5 higher in {hi_b}, m5 higher in {hi_m}, equal in {len(keys) - hi_b - hi_m}")
    for arm, label in (("b5", "certify"), ("m5", "detect")):
        group = [t for t in keys if data.fail(arm, t)]
        rest = [t for t in keys if not data.fail(arm, t)]
        for name, g in ((f"suites that {label}", group), ("the others", rest)):
            if g:
                s = [score(arm, t) for t in g]
                print(f"  {arm} {name}: {len(g)}, mean {100 * sum(s) / len(s):.1f}%")


def main():
    data = A.Data(C5)
    print(f"Fifth campaign, descriptive figures: {len(data.tags)} subjects, arms {', '.join(ARMS)}")
    runs(data)
    verdicts(data)
    certifying(data)
    repetition(data)
    transcripts(data)
    mutation(data)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Descriptive figures of the sixth campaign, as quoted in the write-up.

None of this is a test. The estimate and the test that the protocol fixes,
and the decision they lead to, are printed by bin/analyze-campaign6.py, which
was committed with the protocol before the runs. This script was written after
the analysis, on 27 November 2026. It adds what a reader needs to follow the
result subject by subject:

- when the runs were made; their turns and cost; the runs that reached the
  limit of turns; the tests left out at acceptance;
- which faults each arm detects, with the fault type and the classes the fix
  changes, and how many tests each detection rests on;
- for each f6 suite that detects, the tests that detect, the fix's subject
  line and what the closing message says (closing-f6.txt); for each f6 suite
  that certifies, the tests that fail on the fix commit;
- the f6 findings, by what the run's closing message names;
- f6 beside b5, the same revision under another request, and beside s4;
- m4, m5 and m6, the same condition run three times, subject by subject;
- some counts from the transcripts: calls the harness refused, commands that
  call curl or wget, runs that see the folder the CLI's sandbox mounts in the
  working copy;
- mutation score as means over suites, and subject by subject.

It reads only files already in data/campaign6, the fifth and fourth
campaigns' verdicts, and the fourth campaign's subject records. It takes the
definitions of bin/analyze-campaign6.py and the transcript reader of
bin/audit-campaign6.py by importing them.

Usage: ./bin/describe-campaign6.py        (from anywhere in the repository)
"""

import collections
import importlib.util
import json
import lzma
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C6 = os.path.join(ROOT, "data", "campaign6")
RECORDS = os.path.join(ROOT, "data", "campaign4", "subjects")
ARMS = ("f6", "m6")
NETWORK = re.compile(r"(?<![\w.-])(?:curl|wget)\b")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("analysis6", "analyze-campaign6.py")
AUDIT = load("audit6", "audit-campaign6.py")


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


def method(key):
    """org.x.FooAgentTest#testBar() -> FooAgentTest#testBar"""
    cls, _, name = key.partition("#")
    return cls.rsplit(".", 1)[-1] + ("#" + name.split("(", 1)[0] if name else "")


def keys(field):
    return [k for k in (field or "").split(";") if k]


def failing_on_other(tag, arm):
    """The keys that fail on the other revision, with their messages, from the measurement's report."""
    path = os.path.join(C6, "results", f"{tag}.{arm}.other.tsv")
    out = []
    for line in open(path, errors="replace") if os.path.exists(path) else []:
        cols = line.rstrip("\n").split("\t")
        if cols and cols[0] == "FAILED":
            out.append((cols[2], cols[5] if len(cols) > 5 else ""))
    return out


def closing_words():
    """{subject: the words of its closing-f6.txt line}. A data line is read whole,
    since the words may hold a '#' (an entity such as &#2000000000;)."""
    out = {}
    for line in open(os.path.join(C6, "closing-f6.txt")):
        if line.lstrip().startswith("#"):
            continue
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0] == "f6":
            out[parts[1]] = parts[3].strip()
    return out


def turns_of(base):
    """The run's turns: the sum over the result events of its transcript. The
    run's .json holds the last result only, and in a run with two results (in
    f6, commons-lang-eedd91729) that result counts its own turns, not the run's.
    Its cost, total_cost_usd, is the session's total."""
    turns = [obj.get("num_turns") or 0 for obj in AUDIT.read_stream(base + ".stream.jsonl.xz")
             if obj.get("type") == "result"]
    return sum(turns), len(turns)


def runs(data):
    section("Runs")
    for arm in ARMS:
        turns, cost, started, finished = [], [], [], []
        left = total = with_left = 0
        commits = collections.Counter()
        limit, twice = [], []
        for t in data.tags:
            base = os.path.join(C6, f"runs-{arm}", t)
            r = json.load(open(base + ".json"))
            m = json.load(open(base + ".meta.json"))
            n, results = turns_of(base)
            turns.append(n)
            if results > 1:
                twice.append(f"{t} ({results} results, {n} turns; its .json says {r['num_turns']})")
            cost.append(r["total_cost_usd"])
            commits[m["commit"][:7]] += 1
            started.append(m["started"])
            finished.append(m["finished"])
            if r.get("subtype") != "success":
                limit.append((t, r.get("subtype"), A.status_of(C6, arm, t),
                              bool((r.get("result") or "").strip())))
            if os.path.exists(base + ".pruned"):
                a, b = (int(x) for x in open(base + ".pruned").read().split()[:2])
                left += a
                total += b
                with_left += a > 0
        suites = sum(1 for t in data.tags if A.status_of(C6, arm, t) == "ok")
        print(f"  {arm}: {suites} suites, {total} tests, {left} left out at acceptance "
              f"({100 * left / total:.1f}%), in {with_left} suites")
        print(f"      turns a run: mean {sum(turns) / len(turns):.1f}, fewest {min(turns)}, most {max(turns)}; "
              f"${sum(cost):.2f}, ${sum(cost) / len(cost):.2f} a run")
        print("      runs with more than one result: " + ("; ".join(twice) or "none"))
        print(f"      runs that did not end by the agent's decision: {len(limit)}")
        for t, subtype, status, said in limit:
            print(f"          {t:<24} {subtype}; {'a suite' if status == 'ok' else status}; "
                  f"closing message {'written' if said else 'empty'}")
        print("      runs by the commit they were made from: "
              + ", ".join(f"{c} {n}" for c, n in sorted(commits.items())))
        print(f"      first start {min(started)}, last finish {max(finished)}")


def detection(data):
    section("Detection")
    for arm in ARMS:
        c = collections.Counter(data.detection(arm, t) or "no suite" for t in data.tags)
        print(f"  {arm}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    paired = data.paired(data.tags, data.violations)
    f = {t for t in paired if data.detects("f6", t)}
    m = {t for t in paired if data.detects("m6", t)}
    print(f"  paired set: {len(paired)} subjects")
    for label, group in (("f6 and m6 detect", f & m), ("f6 alone detects", f - m), ("m6 alone detects", m - f)):
        print(f"      {label} ({len(group)}):")
        for t in sorted(group, key=lambda t: (project(t), t)):
            print(f"          {t:<24} {data.info[t]['type']:<15} " + ", ".join(fixed_classes(t)))
    print("  how many tests a detection rests on:")
    n = collections.Counter(len(keys(data.verdicts[("f6", t)]["detecting_keys"])) for t in f)
    print("      f6: " + ", ".join(f"{k} test{'s' if k != 1 else ''}: {v}" for k, v in sorted(n.items())))
    n = collections.Counter("timeout" if data.verdicts[("m6", t)]["detection_note"] == "timeout"
                            else len(failing_on_other(t, "m6")) for t in m)
    print("      m6: " + ", ".join(f"{k} test{'s' if k != 1 else ''}: {v}" if k != "timeout" else f"by timeout: {v}"
                               for k, v in sorted(n.items(), key=lambda kv: str(kv[0]))))


def detecting(data, five, words):
    section("The f6 suites that detect the fault")
    for t in sorted(t for t in data.tags if data.detects("f6", t)):
        v = data.verdicts[("f6", t)]
        b5 = (five.get(("b5", t)) or {}).get("verdict", "none")
        print(f"  {t}  ({data.info[t]['type']}; m6 {data.detection('m6', t)}; b5 {b5}; "
              f"closing message: {data.closing.get(t, 'names no bug')})")
        print(f"      fix: {meta(t)['subject']}")
        for key in keys(v["detecting_keys"]):
            print(f"      detects: {method(key)}")
        print(f"      other findings, false alarms: {v['left_out_false_alarms']}")
        if t in words:
            print(f"      the message: {words[t][:200]}")


def certifying(data, five):
    section("The f6 suites that certify the fault: what fails on the fix commit")
    for t in sorted(t for t in data.tags if data.certification(t) == "Fail"):
        b5 = (five.get(("b5", t)) or {}).get("verdict", "none")
        print(f"  {t}  ({data.info[t]['type']}; f6 detection {data.detection('f6', t)}; m6 {data.detection('m6', t)}; "
              f"b5 {b5}; closing message: {data.closing.get(t, 'names no bug')})")
        print(f"      fix: {meta(t)['subject']}")
        for key, message in failing_on_other(t, "f6"):
            print(f"      fails: {method(key)}")
            print(f"          {' '.join(message.split())[:160]}")


def findings(data):
    section("The f6 findings, by what the closing message names")
    groups = collections.OrderedDict((k, []) for k in ("fault", "other", "names no bug"))
    for t in data.tags:
        if A.status_of(C6, "f6", t) == "ok":
            groups[data.closing.get(t, "names no bug")].append(t)
    for label, ts in groups.items():
        rows = [data.verdicts[("f6", t)] for t in ts]
        with_any = [r for r in rows if r["keys_left_out"] not in ("", "0")]
        found = sum(int(r["keys_left_out"] or 0) for r in rows)
        detect = sum(int(r["left_out_detecting"] or 0) for r in rows)
        alarms = sum(int(r["left_out_false_alarms"] or 0) for r in rows)
        print(f"  {label:<13} {len(ts):>3} suites; {len(with_any):>2} with findings, {found:>2} findings: "
              f"{detect} detect, {alarms} false alarms")
    alarms = collections.Counter(int(data.verdicts[("f6", t)]["left_out_false_alarms"] or 0)
                                 for t in data.tags if ("f6", t) in data.verdicts
                                 and data.verdicts[("f6", t)]["keys_left_out"] not in ("", "0"))
    print("  false alarms in a suite with findings: "
          + ", ".join(f"{k}: {v} suites" for k, v in sorted(alarms.items())))
    nameless = [t for t in groups["names no bug"]
                if data.verdicts[("f6", t)]["keys_left_out"] not in ("", "0")]
    print("  suites with findings whose message names no bug: " + ", ".join(nameless))


def beside(data, four, five):
    section("f6 beside b5, the same revision under another request")
    tags = [t for t in data.tags if ("f6", t) in data.verdicts and ("b5", t) in five]
    b5c = {t for t in tags if five[("b5", t)]["verdict"] == "Fail"}
    f6d = {t for t in tags if data.detects("f6", t)}
    f6c = {t for t in tags if data.certification(t) == "Fail"}
    print(f"  subjects with an f6 suite and a b5 suite: {len(tags)}")
    print(f"  b5 certifies ({len(b5c)}):")
    for t in sorted(b5c):
        print(f"      {t:<24} f6 detection {data.detection('f6', t)}, f6 certification {data.certification(t)}")
    print(f"  f6 detects ({len(f6d)}): " + ", ".join(f"{t} (b5 {five[('b5', t)]['verdict']})" for t in sorted(f6d)))
    print(f"  f6 certifies ({len(f6c)}): " + ", ".join(f"{t} (b5 {five[('b5', t)]['verdict']})" for t in sorted(f6c)))
    section("f6 beside s4, neither shown the repair")
    s4d = {t for t in data.tags if (four.get(("s4", t)) or {}).get("verdict") == "Fail"}
    print("  s4 detects: " + ", ".join(f"{t} (f6 {data.detection('f6', t)}; {data.info[t]['type']})"
                                       for t in sorted(s4d)))


def repetition(data, four, five):
    section("m4, m5 and m6, the same condition run three times")
    three = {}
    for t in data.tags:
        v = ((four.get(("m4", t)) or {}).get("verdict"), (five.get(("m5", t)) or {}).get("verdict"),
             data.detection("m6", t))
        if all(x in ("Pass", "Fail") for x in v):
            three[t] = v
    print(f"  subjects with a verdict in all three: {len(three)}")
    count = collections.Counter(sum(x == "Fail" for x in v) for v in three.values())
    print("  detected in " + ", ".join(f"{k} run{'s' if k != 1 else ''}: {count[k]}" for k in range(4)))
    for k in (1, 2):
        print(f"  detected in {k}:")
        for t in sorted((t for t, v in three.items() if sum(x == "Fail" for x in v) == k),
                        key=lambda t: (project(t), t)):
            print(f"      {t:<24} {data.info[t]['type']:<15} m4 {three[t][0]:<5} m5 {three[t][1]:<5} m6 {three[t][2]}")
    changed = [t for t, v in three.items() if v[1] != v[2]]
    print(f"  m5 and m6 differ on {len(changed)}: "
          + ", ".join(f"{t} (m5 {three[t][1]})" for t in sorted(changed)))


def transcripts(data):
    section("From the transcripts")
    for arm in ARMS:
        refused = with_refusal = folder = files = 0
        network = []
        for t in data.tags:
            path = os.path.join(C6, f"runs-{arm}", t + ".stream.jsonl.xz")
            _, commands, _, _, results, n = AUDIT.transcript(path)
            refused += n
            with_refusal += n > 0
            for tool_id, command in commands:
                if NETWORK.search(command):
                    network.append((t, " ".join(command.split())[:90],
                                    " ".join((results.get(tool_id) or "").split())[:90]))
            text = lzma.open(path, "rt", errors="replace").read()
            has_files = ".claude/loop.md" in text or ".claude/skills" in text
            files += has_files
            folder += has_files or ".claude/.cc-writes" in text
        print(f"  {arm}: calls the harness refused {refused}, in {with_refusal} runs")
        print(f"      commands that call curl or wget: {len(network)}")
        for t, command, result in network:
            print(f"          {t}: {command}")
            print(f"              result: {result}")
        print(f"      runs in which the transcript shows the .claude folder the sandbox mounts in the "
              f"working copy: {folder}, {files} of them with the files in it")


def mutation(data):
    section("Mutation score (bin/mutation-campaign6.sh), each arm on its own revision")
    complete = [t for t in data.paired(data.tags, data.violations) if all(data.scored(a, t) for a in ARMS)]

    def score(arm, t):
        r = data.mutation[(arm, t)]
        return int(r["detected"]) / int(r["generated"])

    def mean(xs):
        return 100 * sum(xs) / len(xs)
    for arm in ARMS:
        print(f"  {arm}: mean over {len(complete)} suites {mean([score(arm, t) for t in complete]):.1f}%")
    hi_f = sum(score("f6", t) > score("m6", t) for t in complete)
    hi_m = sum(score("m6", t) > score("f6", t) for t in complete)
    print(f"  subject by subject: f6 higher in {hi_f}, m6 higher in {hi_m}, equal in {len(complete) - hi_f - hi_m}")
    for arm in ARMS:
        group = [t for t in complete if data.detects(arm, t)]
        rest = [t for t in complete if not data.detects(arm, t)]
        for name, g in (("suites that detect", group), ("the others", rest)):
            if g:
                print(f"  {arm} {name}: {len(g)}, mean {mean([score(arm, t) for t in g]):.1f}%")
    group = [t for t in complete if data.certification(t) == "Fail"]
    if group:
        print(f"  f6 suites that certify: {len(group)}, mean {mean([score('f6', t) for t in group]):.1f}%")


def main():
    data = A.Data(C6)
    four = A.read_csv(os.path.join(ROOT, "data", "campaign4", "results", "verdicts.csv"))
    five = A.read_csv(os.path.join(ROOT, "data", "campaign5", "results", "verdicts.csv"))
    words = closing_words()
    print(f"Sixth campaign, descriptive figures: {len(data.tags)} subjects, arms {', '.join(ARMS)}")
    runs(data)
    detection(data)
    detecting(data, five, words)
    certifying(data, five)
    findings(data)
    beside(data, four, five)
    repetition(data, four, five)
    transcripts(data)
    mutation(data)


if __name__ == "__main__":
    main()

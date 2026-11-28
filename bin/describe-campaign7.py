#!/usr/bin/env python3
"""
Descriptive figures of the seventh campaign, as quoted in the write-up.

None of this is a test. The estimate and the test that the protocol fixes,
and the decision they lead to, are printed by bin/analyze-campaign7.py, which
was committed with the protocol before the runs. This script was written after
the analysis, on 28 November 2026. It adds what a reader needs to follow the
result bug by bug:

- when the runs were made; their turns and cost; the runs that reached the
  limit of turns; the tests left out at acceptance;
- which faults each arm detects, with the fault type and the classes the fix
  modifies, and how many tests each detection rests on;
- for each f7 suite that detects, the tests that detect and what the closing
  message says (closing-f7.txt); for each f7 run whose message names the fault
  and that does not detect, its tests on both versions; for each f7 suite that
  certifies, the tests that fail on the fixed version;
- the f7 findings, by what the run's closing message names;
- f7 beside the second campaign's s2, neither shown the repair;
- m2 and m7, the same condition run twice, bug by bug, with the first
  campaign's M beside them;
- the four bugs the memorisation probe flagged, in every Defects4J arm;
- detection by fault type beside the sixth campaign's;
- some counts from the transcripts: calls the harness refused, commands that
  call curl or wget, runs that see the folder the CLI's sandbox mounts in the
  working copy;
- mutation score as means over suites, and bug by bug.

It reads only files already in data/campaign7, the sixth campaign's verdicts
and subjects, the second campaign's and the first campaign's tables of
verdicts, and data/fault-taxonomy.csv. It takes the definitions of
bin/analyze-campaign7.py and the transcript reader of bin/audit-campaign7.py by
importing them.

Usage: ./bin/describe-campaign7.py        (from anywhere in the repository)
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
C7 = os.path.join(ROOT, "data", "campaign7")
ARMS = ("f7", "m7")
NETWORK = re.compile(r"(?<![\w.-])(?:curl|wget)\b")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "bin", filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("analysis7", "analyze-campaign7.py")
AUDIT = load("audit7", "audit-campaign7.py")


def project(tag):
    return tag.rsplit("-", 1)[0]


def number(tag):
    return int(tag.rsplit("-", 1)[1])


def order(tag):
    return project(tag), number(tag)


def section(title):
    print()
    print(title)
    print("-" * len(title))


def fixed_classes(arm, tag):
    path = os.path.join(C7, f"runs-{arm}", tag + ".classes")
    return [l.strip().rsplit(".", 1)[-1] for l in open(path) if l.strip()]


def method(key):
    """org.x.FooAgentTest#testBar() -> FooAgentTest#testBar"""
    cls, _, name = key.partition("#")
    return cls.rsplit(".", 1)[-1] + ("#" + name.split("(", 1)[0] if name else "")


def keys(field):
    return [k for k in (field or "").split(";") if k]


def report(tag, arm, which):
    """[(status, key, message)] from one of the measurement's reports:
    'other' (the suite as accepted, on the other version), 'leftown' (the tests
    left out, run again on the own version) or 'leftout' (the tests left out, on
    the other version)."""
    path = os.path.join(C7, "results", f"{tag}.{arm}.{which}.tsv")
    out = []
    for line in open(path, errors="replace") if os.path.exists(path) else []:
        cols = line.rstrip("\n").split("\t")
        if len(cols) >= 3 and cols[1] in ("method", "class"):
            out.append((cols[0], cols[2], cols[5] if len(cols) > 5 else ""))
    return out


def failing(tag, arm, which):
    return [(k, m) for s, k, m in report(tag, arm, which) if s == "FAILED"]


def closing_words():
    """{bug: the words of its closing-f7.txt line}"""
    out = {}
    for line in open(os.path.join(C7, "closing-f7.txt")):
        if line.lstrip().startswith("#"):
            continue
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0] == "f7":
            out[parts[1]] = parts[3].strip()
    return out


def turns_of(base):
    """The run's turns: the sum over the result events of its transcript. The
    run's .json holds the last result only. Its cost, total_cost_usd, is the
    session's total."""
    turns = [obj.get("num_turns") or 0 for obj in AUDIT.read_stream(base + ".stream.jsonl.xz")
             if obj.get("type") == "result"]
    return sum(turns), len(turns)


def earlier(data):
    """The earlier Defects4J arms' verdicts: {arm: {bug: verdict}}"""
    second = os.path.join(ROOT, "data", "campaign2", "results", "agent-metrics.csv")
    first = os.path.join(ROOT, "data", "agent-metrics-final.csv")
    return {"m2": A.read_d4j(second, "m2"), "s2": A.read_d4j(second, "s2"),
            "M": A.read_d4j(first, "agent"), "S": A.read_d4j(first, "spec")}


def runs(data):
    section("Runs")
    for arm in ARMS:
        turns, cost, started, finished = [], [], [], []
        left = total = with_left = 0
        commits = collections.Counter()
        limit, twice = [], []
        for t in data.tags:
            base = os.path.join(C7, f"runs-{arm}", t)
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
                limit.append((t, r.get("subtype"), A.status_of(C7, arm, t),
                              bool((r.get("result") or "").strip())))
            if os.path.exists(base + ".pruned"):
                a, b = (int(x) for x in open(base + ".pruned").read().split()[:2])
                left += a
                total += b
                with_left += a > 0
        suites = sum(1 for t in data.tags if A.status_of(C7, arm, t) == "ok")
        print(f"  {arm}: {suites} suites, {total} tests, {left} left out at acceptance "
              f"({100 * left / total:.1f}%), in {with_left} suites")
        print(f"      turns a run: mean {sum(turns) / len(turns):.1f}, fewest {min(turns)}, most {max(turns)}; "
              f"${sum(cost):.2f}, ${sum(cost) / len(cost):.2f} a run, most ${max(cost):.2f}")
        print("      runs with more than one result: " + ("; ".join(twice) or "none"))
        print(f"      runs that did not end by the agent's decision: {len(limit)}")
        for t, subtype, status, said in limit:
            print(f"          {t:<10} {subtype}; {'a suite' if status == 'ok' else status}; "
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
    f = {t for t in paired if data.detects("f7", t)}
    m = {t for t in paired if data.detects("m7", t)}
    print(f"  paired set: {len(paired)} bugs")
    for label, group in (("f7 and m7 detect", f & m), ("f7 alone detects", f - m), ("m7 alone detects", m - f)):
        print(f"      {label} ({len(group)}):")
        for t in sorted(group, key=order):
            print(f"          {t:<10} {data.info[t]['type']:<15} " + ", ".join(fixed_classes("m7", t)))
    print("  how many tests a detection rests on:")
    n = collections.Counter(len(keys(data.verdicts[("f7", t)]["detecting_keys"])) for t in f)
    print("      f7: " + ", ".join(f"{k} test{'s' if k != 1 else ''}: {v}" for k, v in sorted(n.items())))
    n = collections.Counter("timeout" if data.verdicts[("m7", t)]["detection_note"] == "timeout"
                            else len(failing(t, "m7", "other")) for t in m)
    print("      m7: " + ", ".join(f"{k} test{'s' if k != 1 else ''}: {v}" if k != "timeout" else f"by timeout: {v}"
                               for k, v in sorted(n.items(), key=lambda kv: str(kv[0]))))
    one = sum(1 for t in m if len(failing(t, "m7", "other")) == 1)
    print(f"      m7 detections that rest on one failing test: {one} of {len(m)}")


def detecting(data, past, words):
    section("The f7 suites that detect the fault")
    for t in sorted((t for t in data.tags if data.detects("f7", t)), key=order):
        v = data.verdicts[("f7", t)]
        print(f"  {t}  ({data.info[t]['type']}; issue {data.info[t]['issue']}; m7 {data.detection('m7', t)}; "
              f"m2 {past['m2'].get(t, 'none')}; closing message: {data.closing.get(t, 'names no bug')})")
        for key in keys(v["detecting_keys"]):
            print(f"      detects: {method(key)}")
        for key, message in failing(t, "f7", "leftown"):
            if key not in keys(v["detecting_keys"]):
                again = dict(failing(t, "f7", "leftout"))
                print(f"      false alarm: {method(key)}")
                print(f"          buggy: {' '.join(message.split())[:150]}")
                print(f"          fixed: {' '.join(again.get(key, '').split())[:150]}")
        if t in words:
            print(f"      the message: {words[t][:220]}")


def named_not_detecting(data, words):
    section("The f7 runs whose message names the fault and that do not detect it")
    for t in sorted((t for t, k in data.closing.items() if k == "fault" and not data.detects("f7", t)), key=order):
        print(f"  {t}  ({data.info[t]['type']}; m7 {data.detection('m7', t)}): {words.get(t, '')[:200]}")
        own = {k: (s, m) for s, k, m in report(t, "f7", "leftown")}
        other = {k: (s, m) for s, k, m in report(t, "f7", "leftout")}
        for key in sorted(own):
            print(f"      {method(key)}")
            print(f"          buggy: {own[key][0]} {' '.join(own[key][1].split())[:150]}")
            if key in other:
                print(f"          fixed: {other[key][0]} {' '.join(other[key][1].split())[:150]}")


def certifying(data, past):
    section("The f7 suites that certify the fault: what fails on the fixed version")
    for t in sorted((t for t in data.tags if data.certification(t) == "Fail"), key=order):
        print(f"  {t}  ({data.info[t]['type']}; f7 detection {data.detection('f7', t)}; "
              f"m7 {data.detection('m7', t)}; m2 {past['m2'].get(t, 'none')}; "
              f"closing message: {data.closing.get(t, 'names no bug')})")
        for key, message in failing(t, "f7", "other"):
            print(f"      fails: {method(key)}")
            print(f"          {' '.join(message.split())[:160]}")


def findings(data):
    section("The f7 findings, by what the closing message names")
    groups = collections.OrderedDict((k, []) for k in ("fault", "other", "names no bug"))
    for t in data.tags:
        if A.status_of(C7, "f7", t) == "ok":
            groups[data.closing.get(t, "names no bug")].append(t)
    for label, ts in groups.items():
        rows = [data.verdicts[("f7", t)] for t in ts]
        with_any = [r for r in rows if r["keys_left_out"] not in ("", "0")]
        found = sum(int(r["keys_left_out"] or 0) for r in rows)
        detect = sum(int(r["left_out_detecting"] or 0) for r in rows)
        alarms = sum(int(r["left_out_false_alarms"] or 0) for r in rows)
        print(f"  {label:<13} {len(ts):>3} suites; {len(with_any):>2} with findings, {found:>2} findings: "
              f"{detect} detect, {alarms} false alarms")
    alarms = collections.Counter(int(data.verdicts[("f7", t)]["left_out_false_alarms"] or 0)
                                 for t in data.tags if ("f7", t) in data.verdicts
                                 and data.verdicts[("f7", t)]["keys_left_out"] not in ("", "0"))
    print("  false alarms in a suite with findings: "
          + ", ".join(f"{k}: {v} suites" for k, v in sorted(alarms.items())))
    same = [t for t in data.tags if ("f7", t) in data.verdicts
            and int(data.verdicts[("f7", t)]["left_out_false_alarms"] or 0) > 0]
    alike = 0
    for t in same:
        own = dict(failing(t, "f7", "leftown"))
        other = dict(failing(t, "f7", "leftout"))
        for key in own:
            if key in other and " ".join(own[key].split()) == " ".join(other[key].split()):
                alike += 1
    print(f"  false alarms that fail on the fixed version with the message they gave on the buggy one: {alike}")


def beside(data, past):
    section("f7 beside s2, neither shown the repair")
    s2d = sorted((t for t in data.tags if past["s2"].get(t) == "Fail"), key=order)
    print("  s2 detects: " + ", ".join(f"{t} (f7 {data.detection('f7', t)}; {data.info[t]['type']})" for t in s2d))
    f7d = sorted((t for t in data.tags if data.detects("f7", t)), key=order)
    print("  f7 detects: " + ", ".join(f"{t} (s2 {past['s2'].get(t, 'none')})" for t in f7d))


def repetition(data, past):
    section("m2 and m7, the same condition run twice; the first campaign's M beside them")
    both = {t: (past["m2"].get(t), data.detection("m7", t)) for t in data.tags}
    both = {t: v for t, v in both.items() if all(x in ("Pass", "Fail") for x in v)}
    print(f"  bugs with a verdict in m2 and m7: {len(both)}")
    print(f"  detected by m2: {sum(v[0] == 'Fail' for v in both.values())}, "
          f"by m7: {sum(v[1] == 'Fail' for v in both.values())}")
    for label, test in (("only m2", lambda v: v == ("Fail", "Pass")), ("only m7", lambda v: v == ("Pass", "Fail"))):
        ts = sorted((t for t, v in both.items() if test(v)), key=order)
        print(f"  {label} ({len(ts)}): " + ", ".join(f"{t} ({data.info[t]['type']})" for t in ts))
    three = {t: (past["M"].get(t), past["m2"].get(t), data.detection("m7", t)) for t in data.tags}
    three = {t: v for t, v in three.items() if all(x in ("Pass", "Fail") for x in v)}
    count = collections.Counter(sum(x == "Fail" for x in v) for v in three.values())
    print(f"  bugs with a verdict in M, m2 and m7: {len(three)}; detected in "
          + ", ".join(f"{k} run{'s' if k != 1 else ''}: {count[k]}" for k in range(4)))
    ts = sorted((t for t, v in three.items() if v == ("Fail", "Pass", "Pass")), key=order)
    print(f"  detected by M only ({len(ts)}): " + ", ".join(ts))


def probe(data, past):
    section("The four bugs the memorisation probe flagged")
    for t in A.PROBE:
        print(f"  {t:<8} f7 {data.detection('f7', t)}, m7 {data.detection('m7', t)}, "
              f"m2 {past['m2'].get(t, 'none')}, s2 {past['s2'].get(t, 'none')}, M {past['M'].get(t, 'none')}; "
              f"closing message: {data.closing.get(t, 'names no bug')}")


def fault_types(data):
    section("Detection by fault type, beside the sixth campaign's")
    six = A.sixth_campaign()
    paired = data.paired(data.tags, data.violations)
    rows = collections.OrderedDict((ty, [0, 0, 0, 0, 0, 0]) for ty in A.TYPES)
    for t in paired:
        r = rows[data.info[t]["type"]]
        r[0] += 1
        r[1] += data.detects("f7", t)
        r[2] += data.detects("m7", t)
    for _, ty, f, m in six:
        r = rows.setdefault(ty, [0, 0, 0, 0, 0, 0])
        r[3] += 1
        r[4] += f
        r[5] += m
    print(f"  {'':<15} {'seventh':>8} {'f7':>4} {'m7':>4}   {'sixth':>6} {'f6':>4} {'m6':>4}")
    for ty, r in rows.items():
        print(f"  {ty:<15} {r[0]:>8} {r[1]:>4} {r[2]:>4}   {r[3]:>6} {r[4]:>4} {r[5]:>4}")
    om = rows["OMISSION"]
    rest = [sum(r[i] for ty, r in rows.items() if ty != "OMISSION") for i in range(6)]
    print(f"  omissions: f7 {om[1]} of {om[0]}, m7 {om[2]}; f6 {om[4]} of {om[3]}, m6 {om[5]}")
    print(f"  the other types: f7 {rest[1]} of {rest[0]}, m7 {rest[2]}; f6 {rest[4]} of {rest[3]}, m6 {rest[5]}")


def transcripts(data):
    section("From the transcripts")
    for arm in ARMS:
        refused = with_refusal = folder = files = 0
        network = []
        for t in data.tags:
            path = os.path.join(C7, f"runs-{arm}", t + ".stream.jsonl.xz")
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
    section("Mutation score (bin/mutation-campaign7.sh), each arm on its own version")
    complete = [t for t in data.paired(data.tags, data.violations) if all(data.scored(a, t) for a in ARMS)]

    def score(arm, t):
        r = data.mutation[(arm, t)]
        return int(r["mut_killed"]) / int(r["mut_generated"])

    def mean(xs):
        return 100 * sum(xs) / len(xs)
    for arm in ARMS:
        scored = [t for t in data.tags if data.scored(arm, t)]
        s, c = A.pooled(data, arm, scored)
        print(f"  {arm}: {len(scored)} suites with a mutation figure, pooled {100 * s:.1f}%, line coverage of "
              f"the same suites {100 * c:.1f}%; mean over the {len(complete)} of the complete set "
              f"{mean([score(arm, t) for t in complete]):.1f}%")
    hi_f = sum(score("f7", t) > score("m7", t) for t in complete)
    hi_m = sum(score("m7", t) > score("f7", t) for t in complete)
    print(f"  bug by bug: f7 higher in {hi_f}, m7 higher in {hi_m}, equal in {len(complete) - hi_f - hi_m}")
    more = sum(int(data.mutation[("m7", t)]["mut_generated"]) > int(data.mutation[("f7", t)]["mut_generated"])
               for t in complete)
    fewer = sum(int(data.mutation[("m7", t)]["mut_generated"]) < int(data.mutation[("f7", t)]["mut_generated"])
                for t in complete)
    print(f"  mutants of the fixed version against the buggy one: more in {more}, fewer in {fewer}, "
          f"as many in {len(complete) - more - fewer}")
    for arm in ARMS:
        group = [t for t in complete if data.detects(arm, t)]
        rest = [t for t in complete if not data.detects(arm, t)]
        for name, g in (("suites that detect", group), ("the others", rest)):
            if g:
                print(f"  {arm} {name}: {len(g)}, mean {mean([score(arm, t) for t in g]):.1f}%")
    group = [t for t in complete if data.certification(t) == "Fail"]
    if group:
        print(f"  f7 suites that certify: {len(group)}, mean {mean([score('f7', t) for t in group]):.1f}%")


def main():
    data = A.Data(C7)
    past = earlier(data)
    words = closing_words()
    print(f"Seventh campaign, descriptive figures: {len(data.tags)} bugs, arms {', '.join(ARMS)}")
    runs(data)
    detection(data)
    detecting(data, past, words)
    named_not_detecting(data, words)
    certifying(data, past)
    findings(data)
    beside(data, past)
    repetition(data, past)
    probe(data, past)
    fault_types(data)
    transcripts(data)
    mutation(data)


if __name__ == "__main__":
    main()

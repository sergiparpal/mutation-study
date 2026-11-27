#!/usr/bin/env python3
"""
Seventh campaign: the subjects (data/campaign7/PROTOCOL.md, "The subjects").
No model is run.

    ./bin/subjects-campaign7.py
        Write data/campaign7/subjects.txt: the 40 bugs of the sample
        (data/sample.txt), named <project>-<id> as in the second campaign, in
        a new order.
    ./bin/subjects-campaign7.py --check
        Exit 1 if subjects.txt is not what the rule gives, or if a bug fails
        one of the checks below.

The rule: the tags sorted, then random.Random(20261127).shuffle.

The checks, in Defects4J's metadata under D4J_HOME (default ~/defects4j):
  - each bug is an active bug of its project, with an issue;
  - it has classes under test (modified_classes/<id>.src) and trigger tests
    (trigger_tests/<id>);
  - every test file of its test patch (patches/<id>.test.patch) holds one of
    its trigger tests, so that removing the files that hold the trigger tests,
    as the second campaign's generator does, removes every test file the fix
    touches.
That both versions of each bug check out and compile is checked by the
generator, which stages them.
"""

import csv
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "data", "sample.txt")
TAXONOMY = os.path.join(ROOT, "data", "fault-taxonomy.csv")
SUBJECTS = os.path.join(ROOT, "data", "campaign7", "subjects.txt")
D4J = os.path.join(os.environ.get("D4J_HOME", os.path.expanduser("~/defects4j")), "framework", "projects")
SEED = 20261127

HEADER = """\
# Seventh campaign: the subjects, in the order of the runs.
#
# The 40 bugs of the sample (data/sample.txt), named <project>-<id> as in the
# second campaign. The order is random.Random(20261127).shuffle of the tags
# sorted. Both arms of a bug are run before the next: f7 first for the 1st,
# 3rd, 5th ... bug and m7 first for the 2nd, 4th, 6th ... (bin/run-campaign7.sh).
# Each bug's classes under test, trigger tests and issue are Defects4J's, read
# when each version is staged (bin/campaign7-lib.sh).
#
# fault type: data/fault-taxonomy.csv as classified.
# issue: the report Defects4J gives for the bug (active-bugs.csv).
#
# bug       fault type       issue
"""


def tags():
    out = []
    for line in open(SAMPLE):
        if line.strip() and not line.startswith("#"):
            p, b = (x.strip() for x in line.split(",")[:2])
            out.append(f"{p}-{b}")
    return out


def split(tag):
    p, b = tag.rsplit("-", 1)
    return p, b


def issues(project):
    with open(os.path.join(D4J, project, "active-bugs.csv"), newline="") as fh:
        return {r["bug.id"]: r["report.id"] for r in csv.DictReader(fh)}


def fault_types():
    with open(TAXONOMY, newline="") as fh:
        return {r["bug_id"]: r["fault_type"] for r in csv.DictReader(fh) if r["phase"] == "sample"}


def expected():
    ordered = sorted(tags())
    random.Random(SEED).shuffle(ordered)
    types = fault_types()
    rows = []
    for tag in ordered:
        p, b = split(tag)
        rows.append(f"{tag:<10}{types.get(tag, '-'):<17}{issues(p).get(b, '-')}")
    return HEADER + "\n".join(rows) + "\n", ordered


def test_patch_files(project, bug):
    files = set()
    for line in open(os.path.join(D4J, project, "patches", f"{bug}.test.patch"), errors="replace"):
        m = re.match(r"^(?:\+\+\+|---) (?:[ab]/)?(\S+\.java)", line)
        if m:
            files.add(os.path.basename(m.group(1))[:-5])
    return files


def trigger_classes(project, bug):
    out = set()
    path = os.path.join(D4J, project, "trigger_tests", bug)
    for line in open(path, errors="replace"):
        if line.startswith("--- ") and "::" in line:
            out.add(line[4:].split("::")[0].strip())
    return out


def problems(ordered):
    found = []
    for tag in ordered:
        p, b = split(tag)
        if not issues(p).get(b):
            found.append(f"{tag}: not an active bug of {p}, or no issue")
            continue
        mod = os.path.join(D4J, p, "modified_classes", f"{b}.src")
        if not os.path.isfile(mod) or not open(mod).read().split():
            found.append(f"{tag}: no classes under test")
        trig = trigger_classes(p, b)
        if not trig:
            found.append(f"{tag}: no trigger test")
            continue
        holding = {c.split(".")[-1].split("$")[0] for c in trig}
        extra = sorted(test_patch_files(p, b) - holding)
        if extra:
            found.append(f"{tag}: the test patch touches test files without a trigger test: {extra}")
    return found


def main():
    text, ordered = expected()
    if sys.argv[1:] == ["--check"]:
        bad = problems(ordered)
        if not os.path.isfile(SUBJECTS) or open(SUBJECTS).read() != text:
            bad.insert(0, "data/campaign7/subjects.txt is not what the rule gives")
        for b in bad:
            print(b)
        print(f"{len(ordered)} bugs; " + ("every check passed" if not bad else f"{len(bad)} problem(s)"))
        sys.exit(1 if bad else 0)
    if sys.argv[1:]:
        sys.exit(__doc__)
    os.makedirs(os.path.dirname(SUBJECTS), exist_ok=True)
    with open(SUBJECTS, "w") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(SUBJECTS, ROOT)}: {len(ordered)} bugs")


if __name__ == "__main__":
    main()

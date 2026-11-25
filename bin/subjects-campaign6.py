#!/usr/bin/env python3
"""
Sixth campaign: the subjects (data/campaign6/PROTOCOL.md, "The subjects").
No model is run.

    ./bin/subjects-campaign6.py
        Write data/campaign6/subjects.txt: the fourth campaign's 115 subjects
        (data/campaign4/subjects.txt), with the same columns, in a new order.
        Their records stay where they are (data/campaign4/subjects/).
    ./bin/subjects-campaign6.py --check
        Exit 1 if subjects.txt is not what the rule gives, or if a subject
        fails one of the checks below.

The rule: the rows of the fourth campaign's list, sorted by tag, then
random.Random(20261125).shuffle.

The checks, in the clones under MINING (default ~/code/mining-pool), one per
repository:
  - each subject has a record under data/campaign4/subjects/<tag>/;
  - its fix commit has exactly one parent, so <fix>~1, the revision f6 is
    given, is the parent the fourth campaign's measurement used;
  - every class under test (classes.txt) exists at that parent, so the prompt
    names the same classes in both arms.
"""

import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "data", "campaign4", "subjects.txt")
RECORDS = os.path.join(ROOT, "data", "campaign4", "subjects")
SUBJECTS = os.path.join(ROOT, "data", "campaign6", "subjects.txt")
MINING = os.environ.get("MINING", os.path.expanduser("~/code/mining-pool"))
SEED = 20261125
SRC = "src/main/java/"

HEADER = """\
# Sixth campaign: the subjects, in the order of the runs.
#
# The fourth campaign's 115 subjects (data/campaign4/subjects.txt), with its
# columns, and their records under data/campaign4/subjects/, unchanged. The
# order is random.Random(20261125).shuffle of the rows sorted by tag. Both arms
# of a subject are run before the next: f6 first for the 1st, 3rd, 5th ...
# subject and m6 first for the 2nd, 4th, 6th ... (bin/run-campaign6.sh).
#
# fault type: the final type in data/postcutoff-pool/fault-types.tsv.
# strict: whether the subject is eligible under the strict reading of the screen.
#
# subject                  date        fault type       strict
"""


def rows():
    out = []
    for line in open(SOURCE):
        if line.strip() and not line.startswith("#"):
            out.append(line.rstrip("\n"))
    return out


def expected():
    ordered = sorted(rows(), key=lambda r: r.split()[0])
    random.Random(SEED).shuffle(ordered)
    return HEADER + "\n".join(ordered) + "\n"


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)


def meta(tag):
    path = os.path.join(RECORDS, tag, "meta.txt")
    if not os.path.isfile(path):
        return None
    return dict(l.rstrip("\n").split("=", 1) for l in open(path) if "=" in l)


def problems(tags):
    found = []
    for tag in tags:
        m = meta(tag)
        if m is None:
            found.append(f"{tag}: no record under data/campaign4/subjects/")
            continue
        repo = os.path.join(MINING, m["project"])
        listed = git(repo, "rev-list", "--parents", "-n1", m["sha"])
        parents = listed.stdout.split()[1:]
        if listed.returncode != 0:
            found.append(f"{tag}: the fix commit is not in {repo}")
            continue
        if len(parents) != 1:
            found.append(f"{tag}: the fix commit has {len(parents)} parents")
            continue
        for cls in open(os.path.join(RECORDS, tag, "classes.txt")).read().split():
            path = SRC + cls.replace(".", "/") + ".java"
            if git(repo, "cat-file", "-e", f"{m['sha']}~1:{path}").returncode != 0:
                found.append(f"{tag}: {cls} does not exist at the parent")
    return found


def main():
    text = expected()
    tags = [r.split()[0] for r in text.splitlines() if r.strip() and not r.startswith("#")]
    if sys.argv[1:] == ["--check"]:
        bad = problems(tags)
        if not os.path.isfile(SUBJECTS) or open(SUBJECTS).read() != text:
            bad.insert(0, "data/campaign6/subjects.txt is not what the rule gives")
        for b in bad:
            print(b)
        print(f"{len(tags)} subjects; " + ("every check passed" if not bad else f"{len(bad)} problem(s)"))
        sys.exit(1 if bad else 0)
    if sys.argv[1:]:
        sys.exit(__doc__)
    os.makedirs(os.path.dirname(SUBJECTS), exist_ok=True)
    with open(SUBJECTS, "w") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(SUBJECTS, ROOT)}: {len(tags)} subjects")


if __name__ == "__main__":
    main()

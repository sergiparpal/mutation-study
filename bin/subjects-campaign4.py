#!/usr/bin/env python3
"""
Fourth campaign: the subjects and their records (data/campaign4/PROTOCOL.md,
"The subjects"). No model is run.

    ./bin/subjects-campaign4.py
        Write data/campaign4/subjects.txt from the post-cutoff pool, and one
        record per subject under data/campaign4/subjects/<tag>/, in the format
        of bin/mine-postcutoff.sh's records:
          meta.txt         project, sha, short, date and subject line
          classes.txt      the production classes the fix commit changes
          testclasses.txt  the test classes it changes
          triggers.txt     the tests that failed on the parent when the pool
                           was validated (bin/revalidate-postcutoff.sh), as
                           data/postcutoff-pool/eligible.tsv lists them
          status           ok: every eligible candidate meets the subject
                           contract
        The class lists come from the clones under MINING (default
        ~/code/mining-pool), one per repository, at the heads data/README.md
        gives for the pool.
    ./bin/subjects-campaign4.py --check
        Exit 1 if subjects.txt or a record is not what the rule and the clones
        give.

The rule: the eligible candidates no agent has run on (not the third
campaign's subjects, not its two pilot subjects), less the ones the blind
classification flagged and the ones whose commit message credits an AI. Tags
are <repo>-<first 9 characters of the fix commit>; the order is
random.Random(20261120).shuffle of the rows sorted by tag.

Three subjects have no named trigger test: on the parent, their tests ran out
of memory or did not finish. Their triggers.txt is empty and meta.txt says
why, in a line `parent=`.
"""

import os
import random
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, "data", "postcutoff-pool")
DIR = os.path.join(ROOT, "data", "campaign4")
SUBJECTS = os.path.join(DIR, "subjects.txt")
RECORDS = os.path.join(DIR, "subjects")
MINING = os.environ.get("MINING", os.path.expanduser("~/code/mining-pool"))
SEED = 20261120

PILOT = ("6c4269eb8", "ab3d7236")  # the third campaign's pilot, which pilots this one
AI_CREDITED = ("e04b9bc29", "d62646495", "e985f2eec", "6b98966dd", "e871e5b30",
               "98fb6efc5", "e588cc629", "48bf95fb1", "75d71af80")

HEADER = """\
# Fourth campaign: the subjects, in the order of the runs.
#
# The eligible candidates of the post-cutoff pool (data/postcutoff-pool/eligible.tsv)
# that no agent has run on: not the third campaign's subjects, and not its two
# pilot subjects (commons-lang-6c4269eb8, commons-csv-ab3d7236), which pilot this
# campaign too. Of those, left out as PROTOCOL.md says ("The subjects"): the six
# the blind classification flagged (data/postcutoff-pool/fault-types.tsv) and the
# nine whose commit message credits an AI. Tags are <repo>-<first 9 characters
# of the fix commit>. The order is random.Random(20261120).shuffle of the rows
# sorted by tag.
#
# fault type: the final type in fault-types.tsv, classified blind before any run.
# strict: whether the subject is eligible under the strict reading of the screen.
#
# subject                  date        fault type       strict
"""


def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    head = lines[0].split("\t")
    return [dict(zip(head, line.split("\t"))) for line in lines[1:] if line]


def subjects():
    """The subjects in the order of the runs, as dicts with the pool's fields."""
    types = {r["sha"]: r for r in read_tsv(os.path.join(POOL, "fault-types.tsv"))}
    rows = []
    for r in read_tsv(os.path.join(POOL, "eligible.tsv")):
        sha = r["sha"]
        if (r["campaign3"] or sha.startswith(PILOT) or types[sha]["flag"]
                or sha.startswith(AI_CREDITED)):
            continue
        rows.append({**r, "tag": f"{r['repo']}-{sha[:9]}",
                     "fault_type": types[sha]["fault_type"]})
    rows.sort(key=lambda r: r["tag"])
    random.Random(SEED).shuffle(rows)
    return rows


def subjects_text(rows):
    return HEADER + "".join(
        f"{r['tag']:<25}{r['date']:<12}{r['fault_type']:<17}"
        f"{'yes' if r['strict'] == 'yes' else 'no'}\n" for r in rows)


def git(repo, *args):
    return subprocess.run(["git", "-C", os.path.join(MINING, repo), *args],
                          capture_output=True, text=True, check=True).stdout


def fqcn(path):
    return re.sub(r"^.*src/(main|test)/java/", "", path)[:-len(".java")].replace("/", ".")


def record(r):
    """{file name: text} of one subject's record."""
    repo, sha = r["repo"], r["sha"]
    files = [f for f in git(repo, "show", "--name-only", "--format=", sha).split("\n") if f]
    prod = [f for f in files if re.search(r"src/main/java/.*\.java$", f)]
    tests = [f for f in files if re.search(r"src/test/java/.*\.java$", f)]
    meta = [f"project={repo}", f"sha={git(repo, 'rev-parse', sha).strip()}", f"short={sha[:9]}",
            f"date={git(repo, 'log', '-1', '--format=%ad', '--date=short', sha).strip()}",
            f"subject={git(repo, 'log', '-1', '--format=%s', sha).rstrip(chr(10))}"]
    triggers = [t for t in r["triggers"].split("; ") if t]
    named = [t for t in triggers if not t.startswith("(")]
    notes = [t.strip("()") for t in triggers if t.startswith("(")]
    if notes:
        meta.append("parent=" + "; ".join(notes))
    return {
        "meta.txt": "\n".join(meta) + "\n",
        "classes.txt": "".join(fqcn(f) + "\n" for f in prod),
        "testclasses.txt": "".join(fqcn(f) + "\n" for f in tests),
        "triggers.txt": "".join(t + "\n" for t in sorted(set(named))),
        "status": "ok\n",
    }


def check():
    problems = []
    rows = subjects()
    with open(SUBJECTS, encoding="utf-8") as f:
        if f.read() != subjects_text(rows):
            problems.append("subjects.txt: not what the rule gives")
    tags = {r["tag"] for r in rows}
    present = set(os.listdir(RECORDS)) if os.path.isdir(RECORDS) else set()
    for extra in sorted(present - tags):
        problems.append(f"subjects/{extra}: not a subject")
    for r in rows:
        for name, text in record(r).items():
            path = os.path.join(RECORDS, r["tag"], name)
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() != text:
                        problems.append(f"subjects/{r['tag']}/{name}: differs")
            except OSError:
                problems.append(f"subjects/{r['tag']}/{name}: missing")
    return problems


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        problems = check()
        print("\n".join(problems) if problems else
              "subjects.txt and the subjects' records are what the rule and the clones give")
        sys.exit(1 if problems else 0)
    if args:
        sys.exit(__doc__)
    rows = subjects()
    with open(SUBJECTS, "w", encoding="utf-8") as f:
        f.write(subjects_text(rows))
    for r in rows:
        os.makedirs(os.path.join(RECORDS, r["tag"]), exist_ok=True)
        for name, text in record(r).items():
            with open(os.path.join(RECORDS, r["tag"], name), "w", encoding="utf-8") as f:
                f.write(text)
    no_trigger = [r["tag"] for r in rows if not record(r)["triggers.txt"]]
    print(f"{len(rows)} subjects; records under {os.path.relpath(RECORDS, ROOT)}; "
          f"without a named trigger test: {' '.join(no_trigger) or 'none'}")


if __name__ == "__main__":
    main()

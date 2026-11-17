#!/usr/bin/env python3
"""
Look for signs that a generating agent knew which bug it was working on, or
which developer test exposes it.

WHY
---
The implementation-visible arm deletes .git and the developer test file that
holds each trigger test. That was meant to leave the agent with the code and
nothing that says what is wrong with it. It does not: a Defects4J checkout
also contains defects4j.build.properties, which names the bug and lists its
trigger tests in full, and the working directory name carries the bug id
(see the header of run-agent-suites.sh for the other channels).

There are no transcripts, only each run's final message and the suite it
wrote, so what the agent read cannot be observed directly. This script reports
what those two artifacts give away:

  name     a generated test method has exactly the name of a developer
           trigger test
  issue    the issue number embedded in a trigger test's name
           (testEscapedQuote_LANG_477 -> LANG-477) appears in the suite or in
           the agent's final message
  trigger  the final message mentions a trigger test by name
  bug id   the final message names its own Defects4J bug ("the Lang-13
           regression")

A hit is evidence of knowledge, not of its source: a trigger test's name or
body can also be recalled from training data. Its absence proves nothing.

Reads the packaged suites, the .triggers files and the run records. Needs no
Defects4J installation.

Usage: ./bin/audit-trigger-leaks.py        (from the repository root)
"""

import csv
import glob
import io
import json
import os
import re
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = (("agent", "data/agent-runs", "M, Sonnet"),
        ("agentopus", "data/agent-runs-opus", "M, Opus"),
        ("spec", "data/spec-runs", "S, Sonnet"))
SUITE_DIRS = ("data/agent-suites", "data/agent-suites-broken")
ISSUE_IN_NAME = re.compile(r"(lang|csv|cli|gson)[_-]?(\d{2,4})", re.I)
HYPHENS = r"\-‐‑‒–"                # the agent sometimes types U+2011


def suite_sources(project, bug, arm):
    """Concatenated .java sources of one packaged suite, or None."""
    for d in SUITE_DIRS:
        path = os.path.join(d, f"{project}-{bug}f-{arm}.1.tar.bz2")
        if os.path.exists(path):
            parts = []
            with tarfile.open(path, "r:bz2") as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith(".java"):
                        data = tar.extractfile(member).read()
                        parts.append(io.TextIOWrapper(
                            io.BytesIO(data), errors="replace").read())
            return "\n".join(parts)
    return None


def final_message(runs_dir, tag):
    try:
        with open(os.path.join(runs_dir, tag + ".json")) as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return ""
    return record.get("result") or "" if isinstance(record, dict) else ""


def main():
    os.chdir(ROOT)
    outcome = {}
    with open("data/agent-metrics-final.csv") as fh:
        for r in csv.DictReader(fh):
            outcome[(r["project_id"], r["version_id"].rstrip("f"),
                     r["test_suite_source"])] = r["test_classification"]

    totals = {}
    for arm, runs_dir, label in ARMS:
        hits = []
        examined = 0
        for path in sorted(glob.glob("data/agent-runs/*.triggers")):
            tag = os.path.basename(path)[:-len(".triggers")]
            project, bug = tag.split("-")
            src = suite_sources(project, bug, arm)
            if src is None:
                continue
            examined += 1
            msg = final_message(runs_dir, tag)
            with open(path) as fh:
                triggers = sorted({line.strip().split("::")[1]
                                   for line in fh if "::" in line})
            methods = set(re.findall(r"\bvoid\s+(\w+)\s*\(", src))

            found = []
            same = [t for t in triggers if t in methods]
            if same:
                found.append("name: " + ", ".join(same))
            issues = sorted({f"{m.group(1).upper()}-{m.group(2)}"
                             for t in triggers
                             for m in ISSUE_IN_NAME.finditer(t)})
            for issue in issues:
                key, number = issue.split("-")
                pattern = re.compile(rf"\b{key}[\s_{HYPHENS}]?{number}\b", re.I)
                where = [w for w, text in (("suite", src), ("message", msg))
                         if pattern.search(text)]
                if where:
                    found.append(f"issue: {issue} in {' and '.join(where)}")
            named = [t for t in triggers
                     if len(t) > 8 and re.search(rf"\b{re.escape(t)}\b", msg)]
            if named:
                found.append("trigger: message names " + ", ".join(named))
            if re.search(rf"\b{project}[{HYPHENS}]{bug}\b", msg):
                found.append(f"bug id: message names {tag}")

            if found:
                verdict = outcome.get((project, bug, arm), "not measured")
                hits.append((tag, verdict, found))

        totals[label] = (len(hits), examined)
        detected = sum(1 for _, v, _ in hits if v == "Fail")
        print(f"{label}: {len(hits)} of {examined} suites, "
              f"{detected} of them detecting the fault")
        for tag, verdict, found in hits:
            print(f"  {tag:<8} {verdict:<12} {found[0]}")
            for extra in found[1:]:
                print(f"  {'':<8} {'':<12} {extra}")
        print()

    print("An issue number alone is the weakest of these: a project's sources "
          "and remaining tests\ncan cite it. The other three have no source in "
          "the working copy but Defects4J's own files.")


if __name__ == "__main__":
    main()

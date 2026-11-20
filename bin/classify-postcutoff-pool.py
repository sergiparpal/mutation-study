#!/usr/bin/env python3
"""
Classify the post-cutoff pool by fault type, blind (data/README.md, "Fault
types of the post-cutoff pool"). The raters' requests, inputs and outputs are
in data/postcutoff-pool/classification/. This script runs no model.

    ./bin/classify-postcutoff-pool.py --prepare MIRRORS
        Write the raters' inputs from data/postcutoff-pool/eligible.tsv: one
        production diff per eligible candidate under an anonymous id
        (blind/), the key from ids to commits (key.tsv) and the batches
        (batches.tsv). MIRRORS holds a bare clone <repo>.git of each
        repository at or after the heads data/README.md gives for the pool.
    ./bin/classify-postcutoff-pool.py
        Merge the raters' outputs (out/) with the adjudications, rewrite
        data/postcutoff-pool/fault-types.tsv, and print the agreement, the
        counts by fault type, the largest corpus whose composition matches
        the Defects4J sample, and the power of a campaign of that size.
    ./bin/classify-postcutoff-pool.py --check [MIRRORS]
        Exit 1 if key.tsv, batches.tsv, the diffs' header lines, the raters'
        outputs or fault-types.tsv are not what the seeds, the diffs and the
        recorded outputs give. With MIRRORS, also if a diff is not what git
        gives. The recorded diffs were made with git 2.43.0; another version
        may draw some hunk headers differently.

The final type of a candidate is its rater's, unless adjudications.tsv decides
it. The quotas of a corpus of N subjects split N by the shares of the Defects4J
sample, by largest remainder, ties going to the type with more bugs in the
sample. The sample is counted as data/fault-taxonomy.csv classifies it, except
Csv-16, whose fault is object identity: it is counted as STATE, not API.
"""

import collections
import csv
import glob
import math
import os
import random
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, "data", "postcutoff-pool")
ELIGIBLE = os.path.join(POOL, "eligible.tsv")
FAULT_TYPES = os.path.join(POOL, "fault-types.tsv")
DIR = os.path.join(POOL, "classification")
BLIND = os.path.join(DIR, "blind")
OUT = os.path.join(DIR, "out")
KEY = os.path.join(DIR, "key.tsv")
BATCHES = os.path.join(DIR, "batches.tsv")
ADJUDICATIONS = os.path.join(DIR, "adjudications.tsv")
TAXONOMY = os.path.join(ROOT, "data", "fault-taxonomy.csv")
MATCHED = os.path.join(ROOT, "data", "matched-candidates.csv")

SEED = 20261120  # shuffles the eligible candidates into ids; SEED + 1 draws the second rating
N_BATCHES = 5
N_SECOND = 32
TYPES = ["OMISSION", "ALGORITHM", "SUBSTITUTION", "STATE", "MISSING_CLAUSE", "API"]
LABELS = TYPES + ["UNCLEAR"]
FLAGS = {"NOT_A_FIX", "BUNDLE"}
RATING_COLUMNS = ["id", "fault_type", "alt", "code_lines", "preserved", "flag", "note"]
COLUMNS = ["repo", "sha", "id", "fault_type", "decided_by", "rater", "second_rater",
           "matched_corpus", "alt", "code_lines", "preserved", "flag", "note"]
KEY_COLUMNS = ["id", "repo", "sha", "files", "add", "rem", "code_add", "code_rem"]

# The third campaign: 28 subjects gave 23 pairs with a verdict in both arms, of
# which 3 were detected by M3 only and none by S3 only.
PAIRS_PER_SUBJECT = 23 / 28
SCENARIOS = [("3 and 0.5 in 23", 3 / 23, 0.5 / 23), ("3 and 0 in 23", 3 / 23, 0.0)]
ALPHA = 0.05

# New eligible candidates whose commit message credits an AI (data/README.md,
# "Post-cutoff pool"): Claude, ChatGPT, Codex, and six Copilot Autofix.
AI_CREDITED = ("e04b9bc29", "d62646495", "e985f2eec", "6b98966dd", "e871e5b30",
               "98fb6efc5", "e588cc629", "48bf95fb1", "75d71af80")

# git's defaults, set so that a user's configuration cannot change the diffs.
GIT_CONFIG = {"diff.algorithm": "default", "diff.indentHeuristic": "true",
              "diff.renames": "true", "diff.noprefix": "false",
              "diff.mnemonicPrefix": "false", "diff.relative": "false",
              "diff.interHunkContext": "0", "diff.suppressBlankEmpty": "false"}


def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    head = lines[0].split("\t")
    rows = []
    for n, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != len(head):
            sys.exit(f"{os.path.relpath(path, ROOT)}:{n}: {len(fields)} fields, {len(head)} expected")
        rows.append(dict(zip(head, fields)))
    return rows


def tsv_text(rows, columns):
    return "".join("\t".join(r) + "\n" for r in
                   [columns] + [[str(row[c]) for c in columns] for row in rows])


# --- the raters' inputs -----------------------------------------------------

def line_counts(diff):
    """Lines added and removed: all, and code only, with comments and blank
    lines recognised by their prefix, as each diff's header gives them."""
    n = {"add": 0, "rem": 0, "code_add": 0, "code_rem": 0}
    for line in diff.splitlines():
        if line.startswith(("+++", "---")) or line[:1] not in ("+", "-"):
            continue
        kind = "add" if line[0] == "+" else "rem"
        n[kind] += 1
        s = line[1:].strip()
        if s and not s.startswith(("//", "/*", "*")):
            n["code_" + kind] += 1
    return n


def header(pid, files, n):
    return (f"# {pid}: production diff (src/main/java) of one commit against its parent; "
            "whitespace-only changes ignored\n"
            f"# files: {files}   lines, all: +{n['add']}/-{n['rem']}   "
            "lines, code only (comments and blank lines left out, by line prefix): "
            f"+{n['code_add']}/-{n['code_rem']}\n")


def files_in(diff):
    return sum(1 for line in diff.splitlines() if line.startswith("diff --git"))


def ids_in_order(eligible):
    order = list(range(len(eligible)))
    random.Random(SEED).shuffle(order)
    return [(f"P{i:03d}", eligible[j]) for i, j in enumerate(order, 1)]


def batches_text(ids):
    size = -(-len(ids) // N_BATCHES)
    second = sorted(random.Random(SEED + 1).sample(ids, N_SECOND))
    lines = ["batch\tids"]
    lines += [f"{b + 1}\t{' '.join(ids[b * size:(b + 1) * size])}" for b in range(N_BATCHES)]
    lines.append(f"second\t{' '.join(second)}")
    return "\n".join(lines) + "\n"


def read_batches():
    return {r["batch"]: r["ids"].split() for r in read_tsv(BATCHES)}


class Git:
    def __init__(self, mirrors):
        self.mirrors = mirrors
        self.tmp = tempfile.TemporaryDirectory()
        self.attributes = os.path.join(self.tmp.name, "gitattributes")
        with open(self.attributes, "w") as f:
            f.write("*.java diff=java\n")

    def diff(self, repo, sha, context):
        cmd = ["git", "-c", "core.attributesFile=" + self.attributes]
        for k, v in GIT_CONFIG.items():
            cmd += ["-c", f"{k}={v}"]
        cmd += ["-C", os.path.join(self.mirrors, repo + ".git"), "diff", "--no-ext-diff",
                "--no-color", "-w", f"-U{context}", sha + "^", sha, "--", "src/main/java"]
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              check=True).stdout

    def blind(self, pid, repo, sha):
        """The diff a rater saw, and its counts from the diff without context."""
        bare = self.diff(repo, sha, 0)
        n = line_counts(bare)
        full = self.diff(repo, sha, 6)
        full = "\n".join(line for line in full.splitlines() if not line.startswith("index ")) + "\n"
        return header(pid, files_in(bare), n) + full, files_in(bare), n


def prepare(mirrors):
    git = Git(mirrors)
    os.makedirs(BLIND, exist_ok=True)
    for old in glob.glob(os.path.join(BLIND, "P*.diff")):
        os.remove(old)
    key = []
    for pid, r in ids_in_order(read_tsv(ELIGIBLE)):
        text, files, n = git.blind(pid, r["repo"], r["sha"])
        with open(os.path.join(BLIND, pid + ".diff"), "w", encoding="utf-8") as f:
            f.write(text)
        key.append({"id": pid, "repo": r["repo"], "sha": r["sha"], "files": files, **n})
    with open(KEY, "w", encoding="utf-8") as f:
        f.write(tsv_text(key, KEY_COLUMNS))
    with open(BATCHES, "w", encoding="utf-8") as f:
        f.write(batches_text([k["id"] for k in key]))
    print(f"{len(key)} diffs written to {os.path.relpath(BLIND, ROOT)}")


# --- merging the outputs ----------------------------------------------------

def read_ratings():
    """The raters' outputs, checked against the batches: {id: row} for the
    first rating, {id: row} for the second."""
    batches = read_batches()
    first, second, problems = {}, {}, []
    for name, ids in batches.items():
        path = os.path.join(OUT, ("second" if name == "second" else f"batch-{name}") + ".tsv")
        rows = read_tsv(path)
        where = os.path.relpath(path, ROOT)
        if [r["id"] for r in rows] != ids:
            problems.append(f"{where}: its ids are not those of batch {name}, in order")
        for r in rows:
            if list(r) != RATING_COLUMNS:
                problems.append(f"{where}: columns {list(r)}")
                break
            if r["fault_type"] not in LABELS or r["alt"] not in LABELS + [""]:
                problems.append(f"{where}: {r['id']}: {r['fault_type']} / {r['alt']}")
            if not set(filter(None, r["flag"].split(","))) <= FLAGS:
                problems.append(f"{where}: {r['id']}: flag {r['flag']}")
            (second if name == "second" else first)[r["id"]] = r
    return first, second, problems


def matched_labels():
    labels = collections.defaultdict(list)
    with open(MATCHED, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["fault_type"]:
                labels[r["repo"]].append((r["sha"], r["fault_type"]))
    return labels


def merge():
    first, second, problems = read_ratings()
    if problems:
        sys.exit("\n".join(problems))
    adjudicated = {r["id"]: r for r in read_tsv(ADJUDICATIONS)}
    for pid, a in adjudicated.items():
        if a["final"] not in LABELS:
            sys.exit(f"adjudications.tsv: {pid}: {a['final']}")
    ids = {(k["repo"], k["sha"]): k["id"] for k in read_tsv(KEY)}
    matched = matched_labels()
    rows = []
    for e in read_tsv(ELIGIBLE):
        pid = ids[(e["repo"], e["sha"])]
        r = first[pid]
        labels = [t for s, t in matched[e["repo"]] if e["sha"].startswith(s)]
        if len(labels) > 1:
            sys.exit(f"{e['repo']} {e['sha']}: {len(labels)} rows in matched-candidates.csv")
        rows.append({
            "repo": e["repo"], "sha": e["sha"], "id": pid,
            "fault_type": adjudicated[pid]["final"] if pid in adjudicated else r["fault_type"],
            "decided_by": "adjudication" if pid in adjudicated else "rater",
            "rater": r["fault_type"],
            "second_rater": second[pid]["fault_type"] if pid in second else "",
            "matched_corpus": labels[0] if labels else "",
            **{c: r[c] for c in ("alt", "code_lines", "preserved", "flag", "note")},
        })
    return rows


# --- figures ----------------------------------------------------------------

def defects4j():
    counts = collections.Counter()
    with open(TAXONOMY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["phase"] == "pilot":
                continue
            counts["STATE" if r["bug_id"] == "Csv-16" else r["fault_type"]] += 1
    return counts


def sample_lines():
    """OMISSION fixes of the Defects4J sample that remove lines, and all of them."""
    removing = total = 0
    with open(TAXONOMY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["phase"] != "pilot" and r["fault_type"] == "OMISSION":
                total += 1
                removing += not r["lines"].endswith("/-0")
    return removing, total


def quotas(n, sample):
    size = sum(sample.values())
    raw = {t: n * sample[t] / size for t in TYPES}
    q = {t: math.floor(v) for t, v in raw.items()}
    rank = sorted(TYPES, key=lambda t: (-(raw[t] - q[t]), -sample[t], TYPES.index(t)))
    for t in rank[:n - sum(q.values())]:
        q[t] += 1
    return q


def largest(counts, sample):
    """The largest N whose quotas all fit the counts, and the types that stop
    N + 1."""
    best = 0
    for n in range(1, sum(counts.values()) + 1):
        if all(quotas(n, sample)[t] <= counts.get(t, 0) for t in TYPES):
            best = n
    q = quotas(best + 1, sample)
    return best, [t for t in TYPES if q[t] > counts.get(t, 0)]


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return po, (po - pe) / (1 - pe)


def mcnemar_p(b, c):
    d = b + c
    if d == 0:
        return 1.0
    tail = sum(math.comb(d, i) for i in range(min(b, c) + 1)) / 2 ** d
    return min(1.0, 2 * tail)


def power(n, p10, p01):
    """Probability that the exact two-sided McNemar test rejects at ALPHA with
    n pairs, p10 and p01 being the shares of the two kinds of discordant pair."""
    pd = p10 + p01
    q = p10 / pd
    total = 0.0
    for d in range(n + 1):
        pdisc = math.comb(n, d) * pd ** d * (1 - pd) ** (n - d)
        if pdisc < 1e-15:
            continue
        for b in range(d + 1):
            if mcnemar_p(b, d - b) <= ALPHA:
                total += pdisc * math.comb(d, b) * q ** b * (1 - q) ** (d - b)
    return total


def report(rows):
    sample = defects4j()
    assert sum(sample.values()) == 40, sample
    eligible = {(e["repo"], e["sha"]): e for e in read_tsv(ELIGIBLE)}
    key = {k["id"]: k for k in read_tsv(KEY)}
    for r in rows:
        e = eligible[(r["repo"], r["sha"])]
        r["new"] = not e["campaign3"]
        r["strict"] = e["strict"] == "yes"
        r["removes_code"] = int(key[r["id"]]["code_rem"]) > 0
        r["ai"] = r["sha"].startswith(AI_CREDITED)
    short = lambda r: f"{r['id']}  {r['repo']:<13} {r['sha'][:9]}"
    out = []
    p = out.append

    p(f"rated: {len(rows)} eligible candidates, "
      f"{sum(bool(r['second_rater']) for r in rows)} of them twice")
    pairs = [(r["rater"], r["second_rater"]) for r in rows if r["second_rater"]]
    po, k = kappa(pairs)
    p(f"\nsecond rating: agreement {sum(a == b for a, b in pairs)}/{len(pairs)} ({po:.0%}), "
      f"Cohen's kappa {k:.2f}")
    for r in sorted(rows, key=lambda r: r["id"]):
        if r["second_rater"] and r["second_rater"] != r["rater"]:
            p(f"  {short(r)}  {r['rater']:<14} {r['second_rater']:<14} final {r['fault_type']}")
    pairs = [(r["matched_corpus"], r["rater"]) for r in rows if r["matched_corpus"]]
    po, k = kappa(pairs)
    p(f"\nlabels of the matched corpus, which no rater saw: agreement "
      f"{sum(a == b for a, b in pairs)}/{len(pairs)} ({po:.0%}), Cohen's kappa {k:.2f}")
    for r in sorted(rows, key=lambda r: r["id"]):
        if r["matched_corpus"] and r["matched_corpus"] != r["rater"]:
            p(f"  {short(r)}  matched {r['matched_corpus']:<14} rater {r['rater']}")

    adjudicated = [r for r in rows if r["decided_by"] == "adjudication"]
    p(f"\nadjudicated: {len(adjudicated)}")
    for r in sorted(adjudicated, key=lambda r: r["id"]):
        p(f"  {short(r)}  {r['rater']:<14} -> {r['fault_type']}")
    unmarked = [r for r in rows if r["rater"] == "OMISSION" and r["removes_code"]
                and r["preserved"] != "yes"]
    p(f"OMISSION with removed code lines not marked preserved: {len(unmarked)}")
    flagged = [r for r in rows if r["flag"]]
    p(f"\nflagged: {len(flagged)}")
    for r in sorted(flagged, key=lambda r: (r["flag"], r["id"])):
        p(f"  {short(r)}  {r['fault_type']:<14} {r['flag']}"
          + ("" if r["new"] else ", a third-campaign subject"))

    groups = [
        ("eligible", lambda r: True),
        ("  strict reading", lambda r: r["strict"]),
        ("new", lambda r: r["new"]),
        ("  strict reading", lambda r: r["new"] and r["strict"]),
        ("third-campaign subjects", lambda r: not r["new"]),
    ]
    p("\ncounts by fault type, and the largest corpus matched to the Defects4J sample")
    width = {t: len(t) + 2 for t in TYPES}
    p(f"{'':24}" + "".join(f"{t:>{width[t]}}" for t in TYPES) + f"{'UNCLEAR':>9}{'total':>7}"
      f"{'max N':>7}  binding")
    p(f"{'Defects4J sample':24}" + "".join(f"{sample[t]:>{width[t]}}" for t in TYPES)
      + f"{'':>9}{sum(sample.values()):>7}")
    largest_new = None
    for name, keep in groups:
        c = collections.Counter(r["fault_type"] for r in rows if keep(r))
        n, binding = largest(c, sample)
        if name == "new":
            largest_new = n
        p(f"{name:24}" + "".join(f"{c[t]:>{width[t]}}" for t in TYPES) + f"{c['UNCLEAR']:>9}"
          f"{sum(c.values()):>7}{n:>7}  {', '.join(binding)}")
    q = quotas(largest_new, sample)
    p(f"quotas at {largest_new}: " + ", ".join(f"{t} {q[t]}" for t in TYPES))

    removing, total = sample_lines()
    p("")
    for name, keep in (("eligible", lambda r: True), ("new", lambda r: r["new"])):
        om = [r for r in rows if keep(r) and r["fault_type"] == "OMISSION"]
        p(f"OMISSION with removed code lines, {name}: "
          f"{sum(r['removes_code'] for r in om)} of {len(om)}")
    p(f"OMISSION removing lines in the Defects4J sample: {removing} of {total}")
    added_state = [r for r in rows if r["fault_type"] == "STATE" and not r["removes_code"]]
    p(f"STATE fixes that remove no code line: {len(added_state)} "
      f"({' '.join(sorted(r['id'] for r in added_state))})")

    new = [r for r in rows if r["new"]]
    variants = [
        ("as classified", lambda r: r["fault_type"]),
        ("API moved to the rater's runner-up",
         lambda r: r["alt"] if r["fault_type"] == "API" and r["alt"] in TYPES else r["fault_type"]),
        ("STATE removing no code line counted as OMISSION",
         lambda r: "OMISSION" if r["fault_type"] == "STATE" and not r["removes_code"]
         else r["fault_type"]),
    ]
    p("\nsensitivity, new candidates: largest matched corpus")
    for name, label in variants:
        n, binding = largest(collections.Counter(label(r) for r in new), sample)
        p(f"  {name:<50}{n:>4}  {', '.join(binding)}")
    n, binding = largest(collections.Counter(r["fault_type"] for r in new if not r["flag"]), sample)
    p(f"  {'flagged candidates left out':<50}{n:>4}  {', '.join(binding)}")
    runner_up = collections.Counter(r["alt"] or "none" for r in rows if r["fault_type"] == "API")
    p("  runner-ups of API, eligible: " + ", ".join(f"{t} {c}" for t, c in runner_up.most_common()))

    p(f"\npower of the exact McNemar test at {ALPHA}, at the third campaign's "
      f"23 pairs per 28 subjects;")
    p("discordant pairs per pair detected by M3 only and by S3 only:")
    p(f"{'':58}{'subjects':>9}{'pairs':>7}" + "".join(f"{s:>17}" for s, _, _ in SCENARIOS))
    sizes = [("largest matched corpus, new", largest_new),
             ("largest matched corpus, new, strict reading",
              largest(collections.Counter(r["fault_type"] for r in new if r["strict"]), sample)[0]),
             ("all new candidates, unmatched", len(new)),
             ("  strict reading", sum(r["strict"] for r in new)),
             ("  without the flagged and the AI-credited",
              sum(not r["flag"] and not r["ai"] for r in new))]
    for name, subjects in sizes:
        n = round(subjects * PAIRS_PER_SUBJECT)
        p(f"{name:<58}{subjects:>9}{n:>7}"
          + "".join(f"{power(n, a, b):>17.2f}" for _, a, b in SCENARIOS))
    return "\n".join(out)


# --- checks -----------------------------------------------------------------

def check(mirrors):
    problems = []
    eligible = read_tsv(ELIGIBLE)
    key = read_tsv(KEY)
    expected = [(pid, r["repo"], r["sha"]) for pid, r in ids_in_order(eligible)]
    if [(k["id"], k["repo"], k["sha"]) for k in key] != expected:
        problems.append("key.tsv: the ids are not the seeded order of eligible.tsv")
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(BLIND, "*")))
    if names != sorted(k["id"] + ".diff" for k in key):
        problems.append("blind/: the diffs are not one per id of key.tsv")
    git = Git(mirrors) if mirrors else None
    for k in key:
        path = os.path.join(BLIND, k["id"] + ".diff")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        head, body = "".join(text.splitlines(True)[:2]), "".join(text.splitlines(True)[2:])
        n = line_counts(body)
        if header(k["id"], files_in(body), n) != head:
            problems.append(f"blind/{k['id']}.diff: its header does not count its lines")
        if [str(x) for x in (files_in(body), n["add"], n["rem"], n["code_add"], n["code_rem"])] \
                != [k[c] for c in KEY_COLUMNS[3:]]:
            problems.append(f"key.tsv: {k['id']}: counts differ from its diff")
        if git and git.blind(k["id"], k["repo"], k["sha"])[0] != text:
            problems.append(f"blind/{k['id']}.diff: not what git gives for {k['repo']} {k['sha']}")
    with open(BATCHES, encoding="utf-8") as f:
        if f.read() != batches_text([k["id"] for k in key]):
            problems.append("batches.tsv: not the batches the seeds give")
    problems += read_ratings()[2]
    with open(FAULT_TYPES, encoding="utf-8") as f:
        if f.read() != tsv_text(merge(), COLUMNS):
            problems.append("fault-types.tsv: not what the outputs and adjudications give")
    return problems


def main():
    args = sys.argv[1:]
    if args[:1] == ["--prepare"] and len(args) == 2:
        prepare(args[1])
    elif args[:1] == ["--check"] and len(args) <= 2:
        problems = check(args[1] if len(args) == 2 else None)
        print("\n".join(problems) if problems else
              "key, batches, diffs, outputs and fault-types.tsv are what they should be"
              + ("" if len(args) == 2 else " (diffs not compared with git)"))
        sys.exit(1 if problems else 0)
    elif not args:
        rows = merge()
        with open(FAULT_TYPES, "w", encoding="utf-8") as f:
            f.write(tsv_text(rows, COLUMNS))
        print(report(rows))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

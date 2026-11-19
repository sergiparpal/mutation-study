#!/usr/bin/env python3
"""
Count the post-cutoff subjects available for a larger corpus (data/README.md,
"Post-cutoff pool"). No model is run.

    ./bin/count-postcutoff-pool.py --collect LIST OUT
        Build data/postcutoff-pool/candidates.tsv from the candidate list LIST
        (lines "<repo> <sha> <date> <production files> <subject>", as
        bin/list-candidates.sh prints them) and from OUT, the output directory
        of bin/revalidate-postcutoff.sh; then screen as below.
    ./bin/count-postcutoff-pool.py
        Screen the candidates in candidates.tsv again, rewrite it and
        eligible.tsv, and print the counts.
    ./bin/count-postcutoff-pool.py --check
        Exit 1 if either file is not what the screen gives.

The screen applies the rules of data/matched-quotas.md as
data/matched-candidates.csv applied them. A candidate that meets the subject
contract is excluded if it belongs to an excluded population, if it is not the
fix of a fault, or if the matched corpus already rejected it; same-subject
commits and the clusters below count once. 'eligible' rows count under both
readings; 'lenient only' rows drop out under the strict one, which also folds
three same-author series spread over up to four weeks and drops two fixes that
change only an exception message.
"""

import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "postcutoff-pool")
TSV = os.path.join(DIR, "candidates.tsv")
ELIGIBLE = os.path.join(DIR, "eligible.tsv")
COLUMNS = ["repo", "sha", "date", "prod_files", "test_files", "validation",
           "triggers", "campaign3", "screen", "reason", "subject"]
MATCHED_WINDOW_END = "2026-09-22"

# Validated on purpose: the screen excludes these whatever validation says.
NOT_VALIDATED = {
    "c8dc3121a": "matched log #20: hardening (expansion bounds)",
    "166ceb752": "readObject sweep (Range)",
}
CODEX = ("population: a maintainer's direct commits of 2026-11-15 and 11-18 marked "
         "Assisted-By: OpenAI Codex, an audit sweep like the (fNNN) one")
EXCLUDE = {
    # populations the subject patterns do not catch
    "eb560776a": "population: readObject sweep (Fraction, its first commit)",
    "be3b160d9": "population: readObject sweep (commons-csv); matched log #37",
    "085c2dd9e": "population: fixes a line the supplementary-character sweep wrote (243d3fe49)",
    "ac026ed6e": "population: the fault of audit commit 2e16df626 again (message text read as stack frames)",
    **{s: CODEX for s in ("0bafe758a", "8baa35618", "8ff7ad37f", "a5ff3be60", "d1611cac3",
                          "e2a0789bc", "33a58e56b", "5551df008", "8702a433f", "c44f56692")},
    # decided in data/matched-candidates.csv
    "e1ce120c6": "matched log #11: bundles five independent faults",
    "e213b85ce": "matched log #19: same Fraction.addSub revision as 284be5d6a",
    "d8f4116d4": "matched log #16: reflective-accessibility sweep",
    "55dcbc4bb": "matched log #6: mutable-TimeZone sweep",
    "b401c34a4": "matched log #176: hardening (stale buffer)",
    "ef39bc927": "matched log #154: hardening (stale buffer)",
    # not the fix of a fault
    "67f50236b": "not a fault: reverts a behaviour change",
    "bb675e112": "not a fault: feature (a new architecture name)",
    "68ee18aa5": "not a fault: feature; the parent's javadoc documents the limitation",
    "b368d1035": "not a fault: performance only (the trigger test measures CPU time)",
    "9a33a6173": "not a fault: performance only (the trigger test is a timeout)",
    "18979f30e": "not a fault: hardening, the stale-buffer concern of matched log #176",
    "313d877d5": "not a fault: bundles two independent faults",
    "03960a4d9": "not a fault: hardening (class initialisation side effects)",
}
# One subject per cluster: one fault fixed twice, or one concern worked through
# in a short window. A cluster keeps its third-campaign subject if it has one,
# else its oldest member.
CLUSTERS = {
    "PR #1820 committed twice": ["110683aa6", "99618eb84"],
    "cycle guards, one author, May": ["552d7d07d", "0953617b7", "245d8dffc", "8e2d1bed8"],
    "WordUtils.wrap with wrapOn matches other than one character": ["184c9e832", "9f7d3b5ec"],
    "CSV: clear the buffer before a peek": ["1e3de1274", "110e83061"],
    "CSV: leading comment marker": ["a99f26092", "61aa0555d"],
    "interrupt flag, one author, January-February": ["e1ffb6ea0", "fa3924049"],
    "overflow, one author, 2026-11-15": ["355f24676", "8fb590876"],
}
STRICT_CLUSTERS = {
    "overflow, one author, 2026-06-11 to 06-20": ["2240c1f93", "46d9a80e5", "a0ffef035", "13d25e059"],
    "lenient hex scanning in the unescapers, one author": ["4e1f3eef1", "f015a7ed9"],
    "StringUtils.abbreviate, one author, January-February": ["4a5ef8ed2", "4a6a98432"],
}
STRICT_DROP = {"b62244517": "exception message only", "dda928301": "exception message only"}


def read_tsv(path):
    with open(path) as fh:
        head = fh.readline().rstrip("\n").split("\t")
        return [dict(zip(head, line.rstrip("\n").split("\t"))) for line in fh]


def write_tsv(path, rows, columns):
    with open(path, "w") as fh:
        fh.write("\t".join(columns) + "\n")
        for r in rows:
            fh.write("\t".join(r.get(c, "") for c in columns) + "\n")


def collect(listing, out):
    rows = []
    for line in open(listing):
        if not line.strip():
            continue
        repo, sha, date, nprod, subject = line.rstrip("\n").split(" ", 4)
        r = dict(repo=repo, sha=sha, date=date, prod_files=nprod, test_files="",
                 validation="", triggers="", subject=subject)
        d = os.path.join(out, f"{repo}-{sha[:9]}")
        if repo == "gson":
            r["validation"] = "not validated: Gson's build requires JDK 17"
        elif sha[:9] in NOT_VALIDATED:
            r["validation"] = "not validated: excluded whatever the result"
        elif os.path.exists(os.path.join(d, "status")):
            r["validation"] = open(os.path.join(d, "status")).read().strip()
            meta = dict(l.rstrip("\n").split("=", 1) for l in open(os.path.join(d, "meta.txt")) if "=" in l)
            r["test_files"] = meta.get("ntest", "")
            trig = os.path.join(d, "triggers.txt")
            if r["validation"].startswith("ok") and os.path.exists(trig):
                r["triggers"] = "; ".join(l.strip() for l in open(trig) if l.strip())
        else:
            sys.exit(f"{repo} {sha}: no status under {out}")
        rows.append(r)
    return rows


def screen(rows):
    camp3 = [l.split()[0] for l in open(os.path.join(ROOT, "data/campaign3/subjects.txt"))
             if l.strip() and not l.startswith("#")]
    pool = {l.split()[1] for l in open(os.path.join(ROOT, "data/matched-pool.txt")) if l.strip()}
    for r in rows:
        r["campaign3"] = "yes" if any(t.rsplit("-", 1)[0] == r["repo"] and r["sha"].startswith(t.rsplit("-", 1)[1])
                                      for t in camp3) else ""
        r["screen"], r["reason"] = "", ""
    ok = [r for r in rows if r["validation"].startswith("ok")]

    def population(r):
        s = r["subject"]
        if re.search(r"\(f\d{3}\)\.?$", s):
            return "population: the (fNNN) audit sweep"
        if "readObject" in s or "Range serialization" in s:
            return "population: readObject sweep"
        if re.search(r"surrogate|supplementary", s, re.I):
            return "population: supplementary-character sweep"
        if r["date"] <= MATCHED_WINDOW_END and r["sha"] not in pool:
            return "population: left out of the matched corpus's pool"
        return ""

    for r in rows:
        why = NOT_VALIDATED.get(r["sha"][:9])
        if why:
            r["screen"], r["reason"] = "excluded", why
    for r in ok:
        why = population(r) or EXCLUDE.get(r["sha"][:9], "")
        if why:
            r["screen"], r["reason"] = "excluded", why

    def tag(r):
        return f"{r['repo']}-{r['sha'][:9]}"

    # same subject: one commit counts, a validated one, the oldest of those
    groups = collections.defaultdict(list)
    for r in rows:
        key = re.sub(r"\(#\d+\)|\.$", "", r["subject"].lower()).strip()
        if key not in ("javadoc", "sort members"):
            groups[(r["repo"], key)].append(r)
    for members in groups.values():
        valid = sorted((r for r in members if r["validation"].startswith("ok")), key=lambda r: (r["date"], r["sha"]))
        for r in valid[1:]:
            if not r["screen"]:
                r["screen"], r["reason"] = "counted once", f"same subject as {tag(valid[0])}"

    def fold(clusters, label):
        for name, shas in clusters.items():
            members = [r for r in ok if r["sha"][:9] in shas and r["screen"] in ("", "lenient only")]
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (not r["campaign3"], r["date"], r["sha"]))
            for r in members[1:]:
                if r["screen"] == "":
                    r["screen"], r["reason"] = label, f"with {tag(members[0])}: {name}"

    fold(CLUSTERS, "counted once")
    for r in ok:
        if not r["screen"] and r["sha"][:9] in STRICT_DROP:
            r["screen"], r["reason"] = "lenient only", STRICT_DROP[r["sha"][:9]]
    fold(STRICT_CLUSTERS, "lenient only")
    for r in ok:
        if not r["screen"]:
            r["screen"] = "eligible"
    return rows


def eligible_rows(rows):
    out = []
    for r in rows:
        if r["screen"] in ("eligible", "lenient only"):
            out.append(dict(r, strict="yes" if r["screen"] == "eligible" else ""))
    return out


def counts(rows):
    C = collections.Counter
    commons = [r for r in rows if r["repo"] != "gson"]
    ok = [r for r in rows if r["validation"].startswith("ok")]
    lines = [f"candidates: {len(rows)} ({len(commons)} in Commons Lang, CSV and CLI; "
             f"{len(rows) - len(commons)} in Gson, not validated)",
             f"validation: {dict(C(r['validation'] for r in commons).most_common())}"]
    pop = [r for r in ok if r["reason"].startswith("population")]
    lines.append(f"meet the contract: {len(ok)}; in an excluded population: {len(pop)}")
    for name, strict in (("lenient", False), ("strict", True)):
        e = [r for r in ok if r["screen"] == "eligible" or (not strict and r["screen"] == "lenient only")]
        new = [r for r in e if not r["campaign3"]]
        late = [r for r in e if r["date"] > MATCHED_WINDOW_END]
        lines.append(f"eligible ({name}): {len(e)}; third-campaign subjects {len(e) - len(new)}, new {len(new)}; "
                     f"by repo {dict(C(r['repo'] for r in e))}; to {MATCHED_WINDOW_END} {len(e) - len(late)}, "
                     f"after {len(late)}")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if args[:1] == ["--collect"]:
        rows = collect(args[1], args[2])
    else:
        rows = read_tsv(TSV)
    rows = screen(rows)
    rows.sort(key=lambda r: (r["date"], r["repo"], r["sha"]), reverse=True)
    elig = eligible_rows(rows)
    ecols = ["repo", "sha", "date", "strict", "campaign3", "triggers", "subject"]
    if "--check" in args:
        same = (read_tsv(TSV) == [{c: r.get(c, "") for c in COLUMNS} for r in rows] and
                read_tsv(ELIGIBLE) == [{c: r.get(c, "") for c in ecols} for r in elig])
        print("candidates.tsv and eligible.tsv are what the screen gives" if same
              else "they differ from the screen: run ./bin/count-postcutoff-pool.py")
        sys.exit(0 if same else 1)
    os.makedirs(DIR, exist_ok=True)
    write_tsv(TSV, rows, COLUMNS)
    write_tsv(ELIGIBLE, elig, ecols)
    print(counts(rows))


if __name__ == "__main__":
    main()

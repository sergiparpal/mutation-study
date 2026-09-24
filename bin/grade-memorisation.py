#!/usr/bin/env python3
"""
Grade the memorisation probe.

Two stages, because neither alone is trustworthy:

1. Mechanical screen. An answer counts as a disclaimer if it matches the exact
   phrase the prompt offered ("I do not know this bug" / "I do not recall a
   bug in this class"). Everything else is a claim of knowledge and gets
   scored against the real fix.

2. Overlap score. Identifiers taken from the fix diff — method names, type
   names, string and character literals — are looked for in the answer. A high
   overlap means the model reproduced specifics of a fault it was not shown; a
   low one means it produced plausible-sounding but unspecific text.

The second stage is a screen, not a verdict. Answers flagged as high overlap
must be read by hand before being counted as recall: a model can name
`createNumber` because that is the obvious method in a class called
NumberUtils, without recalling anything about the fault.

Reads:  data/memorisation/<Bug>.{A,B}.json, data/raw/<Bug>/fix.diff
Writes: data/memorisation-grades.csv
"""

import csv
import json
import os
import re
import sys

PROBE_DIR = "data/memorisation"
RAW_DIR = "data/raw"
OUT = "data/memorisation-grades.csv"

DISCLAIMERS = ("i do not know this bug", "i do not recall a bug in this class")

IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")
STRLIT = re.compile(r'"([^"\n]{2,30})"')
CHARLIT = re.compile(r"'(\\?.)'")

# words that appear in almost any Java diff and carry no identifying signal
STOP = {
    "public", "private", "protected", "static", "final", "return", "throw",
    "throws", "class", "void", "this", "null", "true", "false", "else",
    "import", "package", "String", "Object", "value", "length", "size",
    "index", "result", "char", "boolean", "int", "long", "double", "float",
    "new", "case", "break", "continue", "while", "instanceof", "extends",
    "implements", "Override", "param", "return", "java", "org", "com",
}


def fix_identifiers(diff_path):
    """Identifiers, string and char literals introduced or removed by the fix."""
    if not os.path.exists(diff_path):
        return set()
    toks = set()
    with open(diff_path, errors="replace") as fh:
        for line in fh:
            if not line or line[0] not in "+-":
                continue
            if line.startswith(("+++", "---")):
                continue
            body = line[1:]
            toks |= {t for t in IDENT.findall(body) if t not in STOP}
            toks |= {m for m in STRLIT.findall(body)}
            toks |= {m for m in CHARLIT.findall(body)}
    return toks


def read_answer(path):
    if not os.path.exists(path):
        return None, 0.0
    try:
        d = json.load(open(path))
    except Exception:
        return None, 0.0
    return (d.get("result") or "").strip(), (d.get("total_cost_usd") or 0.0)


def main():
    if not os.path.isdir(PROBE_DIR):
        sys.exit(f"{PROBE_DIR} not found — run bin/probe-memorisation.sh first")

    bugs = sorted({f.split(".")[0] for f in os.listdir(PROBE_DIR)
                   if f.endswith(".json")})
    rows, cost = [], 0.0

    for bug in bugs:
        toks = fix_identifiers(os.path.join(RAW_DIR, bug, "fix.diff"))
        row = {"bug_id": bug, "fix_tokens": len(toks)}
        for probe in ("A", "B"):
            ans, c = read_answer(os.path.join(PROBE_DIR, f"{bug}.{probe}.json"))
            cost += c
            if ans is None:
                row[f"{probe}_verdict"] = "missing"
                row[f"{probe}_hits"] = ""
                continue
            low = ans.lower()
            if any(d in low for d in DISCLAIMERS) and len(ans) < 120:
                row[f"{probe}_verdict"] = "disclaimed"
                row[f"{probe}_hits"] = ""
                continue
            hits = sorted(t for t in toks if re.search(
                r"\b" + re.escape(t) + r"\b", ans))
            row[f"{probe}_verdict"] = ("claims_high" if len(hits) >= 3
                                       else "claims_low")
            row[f"{probe}_hits"] = "|".join(hits[:8])
        rows.append(row)

    cols = ["bug_id", "fix_tokens", "A_verdict", "A_hits",
            "B_verdict", "B_hits"]
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"{len(rows)} bugs graded -> {OUT}   (probe cost ${cost:.2f})")
    for probe in ("A", "B"):
        counts = {}
        for r in rows:
            v = r.get(f"{probe}_verdict", "missing")
            counts[v] = counts.get(v, 0) + 1
        total = len(rows)
        line = "  ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        print(f"  probe {probe}: {line}   (n={total})")

    flagged = [r for r in rows
               if r.get("A_verdict") == "claims_high"
               or r.get("B_verdict") == "claims_high"]
    if flagged:
        print(f"\nRead these by hand before counting them as recall "
              f"({len(flagged)}):")
        for r in flagged:
            print(f"  {r['bug_id']:<10} A={r['A_verdict']:<12} "
                  f"B={r['B_verdict']:<12} hits: "
                  f"{r['A_hits'] or r['B_hits']}")
    else:
        print("\nNo answer reproduced three or more identifiers from its fix.")


if __name__ == "__main__":
    main()

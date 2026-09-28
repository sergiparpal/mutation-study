#!/usr/bin/env python3
"""
Disable individual test methods inside a generated test class.

Used by the spec arm: an agent writing tests from the public API alone will get
some expectations wrong, and one wrong expectation must not discard the whole
suite. Failing methods are disabled; the rest are kept and measured.

Disabling rather than deleting, so the file always still compiles:
  - JUnit 4: the @Test annotation above the method is commented out
  - JUnit 3: the method is renamed test<X> -> pruned_<X>, since JUnit 3
    discovers by the `test` prefix

Prints "<pruned> <total>" so the caller can record the rate. That rate is a
result in itself — it measures how often an expectation written from the API
alone turns out to disagree with the implementation.

Usage: prune-failing-tests.py <file.java> <method> [<method> ...]
"""

import re
import sys


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: prune-failing-tests.py <file.java> [methods...]")

    path = sys.argv[1]
    failing = set(sys.argv[2:])

    with open(path) as fh:
        lines = fh.readlines()

    src = "".join(lines)
    junit3 = "extends TestCase" in src or "junit.framework.TestCase" in src

    total = (len(re.findall(r"(?:public\s+)?void\s+test\w*\s*\(", src)) if junit3
        else len(re.findall(r"@Test\b", src)))
    pruned = 0

    for name in failing:
        # locate the declaration of this method
        idx = None
        decl = re.compile(r"(?:public\s+|protected\s+|private\s+)?void\s+"
                          + re.escape(name) + r"\s*\(")
        for i, line in enumerate(lines):
            if decl.search(line):
                idx = i
                break
        if idx is None:
            continue

        if junit3:
            lines[idx] = re.sub(r"\bvoid\s+" + re.escape(name) + r"\s*\(",
                                f"void pruned_{name}(", lines[idx])
            pruned += 1
        else:
            # walk back over annotations and comments to find @Test
            j = idx - 1
            while j >= 0:
                stripped = lines[j].strip()
                if stripped.startswith("@Test"):
                    indent = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
                    lines[j] = (f"{indent}// {stripped}"
                                "  // pruned: failed on the fixed version\n")
                    pruned += 1
                    break
                if stripped == "" or stripped.startswith(("@", "//", "*", "/*")):
                    j -= 1
                    continue
                break                     # hit real code: no annotation found

    with open(path, "w") as fh:
        fh.writelines(lines)

    print(f"{pruned} {total}")


if __name__ == "__main__":
    main()

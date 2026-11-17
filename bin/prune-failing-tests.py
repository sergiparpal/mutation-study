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

COUNTING
--------
The denominator of that rate is counted here and nowhere else. The callers
used to count with `grep -cE "@Test|public void test"`, which counts LINES
matching either pattern: a JUnit 4 method written as

    @Test
    public void testFoo() { ... }

matches twice. Six of the forty specification-only suites were written that
way and had their totals doubled, and one early run recorded a total of zero;
the published prune rate of 59/1806 was really 59/1638.

A test is one `void test...(` method under JUnit 3, and one `@Test` annotation
under JUnit 4 or 5 (`@Test\b` does not match @TestFactory, @TestInstance and
the like; @ParameterizedTest methods are not counted and cannot be pruned).
Methods this script has already disabled still count, so the total is that of
the suite as written whether it is taken before or after pruning.

Usage: prune-failing-tests.py <file.java> <method> [<method> ...]
       prune-failing-tests.py --count <file.java> [<file.java> ...]
"""

import re
import sys

PRUNED_NOTE = "// pruned: failed on the fixed version"


def is_junit3(src):
    return "extends TestCase" in src or "junit.framework.TestCase" in src


def count_tests(src):
    """Number of test methods in the suite as written (active + disabled)."""
    if is_junit3(src):
        active = len(re.findall(r"\bvoid\s+test\w*\s*\(", src))
        disabled = len(re.findall(r"\bvoid\s+pruned_\w+\s*\(", src))
        return active + disabled
    total = 0
    for line in src.splitlines():
        stripped = line.strip()
        if re.match(r"@Test\b", stripped):
            total += 1
        elif stripped.startswith("//") and PRUNED_NOTE in stripped:
            total += 1
    return total


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: prune-failing-tests.py <file.java> [methods...]\n"
                 "       prune-failing-tests.py --count <file.java> [...]")

    if sys.argv[1] == "--count":
        total = 0
        for path in sys.argv[2:]:
            with open(path, errors="replace") as fh:
                total += count_tests(fh.read())
        print(total)
        return

    path = sys.argv[1]
    failing = set(sys.argv[2:])

    with open(path) as fh:
        lines = fh.readlines()

    src = "".join(lines)
    junit3 = is_junit3(src)

    total = count_tests(src)
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
                    lines[j] = f"{indent}// {stripped}  {PRUNED_NOTE}\n"
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

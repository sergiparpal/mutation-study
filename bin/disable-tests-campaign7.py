#!/usr/bin/env python3
"""
Seventh campaign: disable, in the source of one test file, the test methods
acceptance left out, each found by its key (data/campaign7/PROTOCOL.md).

WHY NOT bin/prune-failing-tests.py
----------------------------------
The second campaign disabled the tests that failed at its acceptance with
bin/prune-failing-tests.py, and that script stays as it ran: it disabled no test
there. It finds a method by its name alone, the first declaration of that name
in the file, and under JUnit 4 it looks for @Test on the lines above the
declaration. The seventh campaign's check without the model gave it made-up
exclusions: with `@Test public void b()` on one line it commented out the line
above, the method before it, and left b running; and a method of a nested class
is told from one of the same name in another class only by its key. In f7 the
tests left out are the arm's findings, so many suites have some, and the
archive must leave out those and no others.

WHAT IT DOES
------------
A key is the measurement's: `pkg.Outer$Inner#name()`, its class part read from
the file's top-level class, whose own name may hold a `$` (agents name the test
of Gson's $Gson$Types `$Gson$TypesAgentTest`). The file is read as Java
tokens, comments, strings and characters skipped, and each method declared
`void name()`, with no parameter, directly in the body of a named class is
known by its chain of classes. For each key, that declaration:
  - loses its @Test annotation (`@Test`, `@Test(...)`, `@org.junit.Test`),
    wherever it is among the modifiers, which is put in a comment in its place;
  - and, if its name starts with `test`, is renamed `pruned_<name>`, which is
    how bin/prune-failing-tests.py disables a JUnit 3 test. A JUnit 3 class runs
    the methods named test...; a JUnit 4 class runs those annotated @Test. The
    two are both done, so the class's kind does not have to be known.
A nested class left with no test, when the file still holds tests, is marked
@org.junit.Ignore, since JUnit fails a class with none (a top-level class with
none is left out of the archive by the caller). So is a nested class whose key,
with no method, was left out as a whole: it failed as a class, and its methods
may never have run.

A key it cannot place (a method inherited from another file, a declaration
with parameters) is reported, not guessed at; the caller's check run then finds
that the archive does not run the tests kept.

Usage:  disable-tests-campaign7.py <file.java> <top-level binary name> <key>...
Prints one line per key (`disabled <key>` or `not found <key>`), then
`<disabled> <keys>`. Exits 0 when every key was disabled, 1 otherwise.
"""
import re
import sys


def tokens(src):
    """(kind, start, end, text) for identifiers and symbols, skipping blanks,
    comments, strings, characters and numbers."""
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n\f":
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            i = j + 1
        elif c.isalpha() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            yield ("id", i, j, src[i:j])
            i = j
        elif c.isdigit():
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            i = j
        else:
            yield ("sym", i, i + 1, c)
            i += 1


def declarations(src):
    """Methods `void name()` declared directly in a named class:
    {(chain, name): (start of the member's modifiers, position of the name)},
    and the named classes: {chain: position of the `class` keyword}."""
    toks = list(tokens(src))
    stack = []            # ("class", name) or ("block", None), one per open brace
    pending = None        # a class declared, its body not yet opened
    member_start = 0      # where the current member's modifiers begin
    methods, classes = {}, {}
    k = 0
    while k < len(toks):
        kind, s, e, t = toks[k]
        prev = toks[k - 1][3] if k else ""
        if kind == "id" and t in ("class", "interface", "enum") and prev not in (".", "@") \
                and k + 1 < len(toks) and toks[k + 1][0] == "id":
            pending = (toks[k + 1][3], s)
        elif t == "{":
            if pending:
                stack.append(("class", pending[0]))
                if all(x[0] == "class" for x in stack):
                    classes[tuple(x[1] for x in stack)] = pending[1]
                pending = None
            else:
                stack.append(("block", None))
            member_start = e
        elif t == "}":
            if stack:
                stack.pop()
            member_start = e
        elif t == ";":
            member_start = e
        elif kind == "id" and t == "void" and stack and all(x[0] == "class" for x in stack) \
                and k + 3 < len(toks) and toks[k + 1][0] == "id" \
                and toks[k + 2][3] == "(" and toks[k + 3][3] == ")":
            chain = tuple(x[1] for x in stack)
            methods.setdefault((chain, toks[k + 1][3]), (member_start, toks[k + 1][1]))
        k += 1
    return methods, classes


TEST_ANNOTATION = re.compile(r"@\s*(?:org\s*\.\s*junit\s*\.\s*)?Test\b(?!\s*\.)")


def annotation_span(src, start, end):
    """The span of the @Test annotation among the modifiers in src[start:end],
    with its parenthesised arguments, or None."""
    region = src[start:end]
    # look only outside comments: blank them out, keeping offsets
    masked = re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: " " * len(m.group(0)), region, flags=re.S)
    m = TEST_ANNOTATION.search(masked)
    if not m:
        return None
    a, b = start + m.start(), start + m.end()
    j = b
    while j < len(src) and src[j] in " \t\r\n":
        j += 1
    if j < len(src) and src[j] == "(":
        depth = 0
        while j < len(src):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    b = j + 1
                    break
            j += 1
    return a, b


def key_chain(cls, top):
    """The chain of simple class names a key's class is, from the file's
    top-level class: its binary name is cut after the top-level class's own,
    which may itself hold a `$` (Gson's $Gson$Types), and only there."""
    simple = top.rsplit(".", 1)[-1]
    if cls == top:
        return (simple,)
    if cls.startswith(top + "$"):
        return (simple,) + tuple(cls[len(top) + 1:].split("$"))
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, top = sys.argv[1], sys.argv[2]
    keys = sys.argv[3:]
    src = open(path, encoding="utf-8", errors="surrogateescape").read()
    methods, classes = declarations(src)

    edits = []            # (start, end, replacement)
    done, wanted, whole = [], {}, set()
    for key in keys:
        cls, _, name = key.partition("#")
        chain = key_chain(cls, top)
        if not name:
            # a nested class left out as a whole, which may not have run a test
            if chain and len(chain) > 1 and chain in classes:
                whole.add(chain)
                done.append(key)
                print(f"disabled {key}")
            else:
                print(f"not found {key}")
            continue
        name = name[:-2] if name.endswith("()") else name
        if not chain or (chain, name) not in methods:
            print(f"not found {key}")
            continue
        member_start, at = methods[(chain, name)]
        span = annotation_span(src, member_start, at)
        if span:
            edits.append((span[0], span[1], "/* " + src[span[0]:span[1]].replace("*/", "* /")
                          + " left out at acceptance */"))
        if name.startswith("test"):
            edits.append((at, at + len(name), "pruned_" + name))
        if not span and not name.startswith("test"):
            print(f"not found {key}")
            continue
        done.append(key)
        wanted.setdefault(chain, set()).add(name)
        print(f"disabled {key}")

    # a nested class with no test left is ignored as a whole
    remaining = {}
    for (chain, name), (member_start, at) in methods.items():
        if name in wanted.get(chain, ()):
            continue
        if annotation_span(src, member_start, at) or name.startswith("test"):
            remaining.setdefault(chain, 0)
            remaining[chain] += 1
    for chain in sorted(set(wanted) | whole):
        if len(chain) > 1 and chain in classes and (chain in whole or not remaining.get(chain)):
            edits.append((classes[chain], classes[chain], "@org.junit.Ignore "))
            print(f"ignored the nested class {'$'.join(chain)}: "
                  + ("it was left out as a whole" if chain in whole else "no test of it is left"))

    for s, e, r in sorted(edits, reverse=True):
        src = src[:s] + r + src[e:]
    open(path, "w", encoding="utf-8", errors="surrogateescape").write(src)
    print(f"{len(done)} {len(keys)}")
    sys.exit(0 if len(done) == len(keys) else 1)


if __name__ == "__main__":
    main()

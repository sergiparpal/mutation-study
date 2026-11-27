#!/usr/bin/env python3
"""
Read the transcripts of the seventh campaign and report what each agent did
that the protocol forbids, or tried to.

This is bin/audit-campaign6.py, the sixth campaign's, with the arms and the
paths changed, --closing reading the f7 runs, and `knew` read by the
protocol's rule for Defects4J (data/campaign7/PROTOCOL.md, "Exclusions"). The
sixth campaign's script counted the subject's issue, pull request, fix commit
and trigger tests; the second campaign's (bin/audit-transcripts.py) counted
the benchmark, the issue and the trigger tests. Here `knew` counts what the
agent's own text, or a test it wrote, names of these:

  - the benchmark (`Defects4J`, `d4j`);
  - the bug's identifier in Defects4J, such as `Lang-43`;
  - the issue behind the bug, as Defects4J gives it, when it is a tracker key
    such as LANG-477. Gson's issues are bare numbers, which the second
    campaign's rule did not count either;
  - one of the bug's trigger tests, by a method name longer than eight
    characters.

A name that the search of the working copy found there (the run's .leakscan)
does not count: the agent could have read it. Such a name is printed, marked
`(in the working copy)`, and the run is not counted as naming the bug.

Neither arm of this campaign is specification-only, so the counts that apply
to that arm alone, `inspect` and `javac`, are not made.

It reports, per run:

  commands   how many shell commands the agent ran
  refused    tool calls the harness refused (a file tool outside the working
             copy, anything that needed a permission nobody could grant)
  denied     tool results in which the sandbox refused what a command asked
  network    commands that reach for the network (curl, wget, mvn, git clone, ...)
  vcs        commands that run git
  outside    commands naming a path outside the working copy
  own tmp    commands naming the run's own temporary directory
  other      files the agent created or changed that are not its test classes
  knew       the agent's own text, or a test it wrote, names the bug, as above

A flagged command is one the agent ISSUED. Whether it did anything is in the
tool result printed next to it: the sandbox blocks the network and hides
everything outside the working copy. `knew` is evidence of knowledge, not of
its source: Defects4J is public, and what the agent names may come from
training data, which the protocol counts as part of what is measured.

`outside` includes /tmp, which needs reading with care. Inside the sandbox
/tmp is an empty directory private to each command: a file written there is
gone when the command ends and never reaches the host.

--closing prints, instead, the closing message of every f7 run: the text the
agent ended with, as the run's .json records it, and under it the tests that
acceptance left out, those that failed on the buggy version. The protocol has
them read at the audit, before anything is measured. closing-f7.txt then lists
each run whose message names a test as showing a bug, one line per run:

    f7 <bug> fault|other <the words that say what the bug is>

`fault` when one of the bugs named is the fault, judged against the bug's
source patch by the protocol's rule; `other` when none is.

Usage:
    ./bin/audit-campaign7.py                         # data/campaign7
    ./bin/audit-campaign7.py data/campaign7 -v       # every flagged command
    ./bin/audit-campaign7.py data/campaign7 --closing
"""

import glob
import json
import lzma
import os
import re
import sys

ARMS = ("f7", "m7")
BENCHMARK = re.compile(r"defects4j|\bd4j\b", re.I)
SPEC_ARM = None      # neither arm is specification-only: no `inspect`, no `javac`

NETWORK = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|rsync|ftp|telnet|pip3?\s+install|"
                     r"npm\s+install|mvn|mvnw|gradle|git\s+(clone|fetch|pull|remote))\b")
VCS = re.compile(r"\bgit\b")
PROGRAMS = (r"java|javap|jshell|jar|jdb|jdeps|jrunscript|jjs|jlink|jimage|"
            r"unzip|zipinfo|funzip|bsdtar|7z|strings|xxd|od|hexdump|"
            r"python3?|perl|ruby|node|base64")
# the bare word, as the earlier script had it ...
INSPECT_WORD = re.compile(r"(?<![\w./-])(" + PROGRAMS + r")\b(?!\.sh)")
# ... and the same programs behind any path, where a command begins
INSPECT_PATH = re.compile(r"(?:^|[;&|(`]|\$\(|\bxargs\s+|\bexec\s+|-exec\s+|\benv\s+|\btime\s+)\s*"
                          r"(?:[\w.@%+-]*/)+(" + PROGRAMS + r")(?=\s|$)", re.M)
JAVAC_EXEC = re.compile(r"-processor\b|-processorpath\b|-Xplugin|(?<![\w-])-J\S")
JAVAC = re.compile(r"(?<![\w.-])javac\b")
ABS_PATH = re.compile(r"(?<![\w.$-])(/(?:home|tmp|mnt|opt|root|srv|media|var|etc|proc|sys)\b[^\s'\";|&)]*|~/?[^\s'\";|&)]*)")
SANDBOX_DENIAL = re.compile(r"operation not permitted|permission denied|read-only file system", re.I)


def read_stream(path):
    opener = lzma.open if path.endswith(".xz") else open
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj


def transcript(path):
    """cwd, shell commands, the agent's text, what it wrote, tool results, refusals."""
    cwd = None
    commands, texts, written = [], [], []
    results = {}
    refused = 0
    for obj in read_stream(path):
        kind = obj.get("type")
        message = obj.get("message")
        if not isinstance(message, dict):
            message = {}
        if kind == "system" and obj.get("subtype") == "init":
            cwd = obj.get("cwd")
        elif kind == "system" and obj.get("subtype") == "permission_denied":
            refused += 1
        elif kind == "assistant":
            content = message.get("content")
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    inp = part.get("input") or {}
                    if part.get("name") == "Bash":
                        commands.append((part.get("id"), inp.get("command", "")))
                    elif part.get("name") in ("Write", "Edit"):
                        written.append(inp.get("content") or inp.get("new_string") or "")
        elif kind == "user":
            content = message.get("content")
            for part in content if isinstance(content, list) else []:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    body = part.get("content")
                    if not isinstance(body, str):
                        body = " ".join(x.get("text", "") for x in body or []
                                        if isinstance(x, dict))
                    results[part.get("tool_use_id")] = body
    return cwd, commands, texts, written, results, refused


def in_working_copy(base):
    """What the search of the working copy found there: {kind: [snippets]}."""
    found = {}
    try:
        for line in open(base + ".leakscan", errors="replace"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 3:
                found.setdefault(cols[0], []).append(cols[2])
    except OSError:
        pass
    return found


def knowledge(base, texts, written, counted_only=True):
    """What in the agent's words or tests names the bug. A list of reasons;
    a name the working copy holds is marked, and left out with counted_only."""
    found = []
    names, meta = [], {}
    try:
        names = sorted({l.strip().split("::")[1] for l in open(base + ".triggers") if "::" in l})
        meta = json.load(open(base + ".meta.json"))
    except (OSError, ValueError, IndexError):
        pass
    held = in_working_copy(base)
    said = "\n".join(texts) + "\n" + "\n".join(written)

    def add(reason, kind, name=None):
        there = kind in held and (name is None or any(re.search(rf"\b{re.escape(name)}\b", x) for x in held[kind]))
        if there:
            if not counted_only:
                found.append(reason + " (in the working copy)")
        else:
            found.append(reason)

    if BENCHMARK.search(said):
        add("names the benchmark", "benchmark")
    project, bug = meta.get("project") or "", meta.get("bug_id") or ""
    if project and bug and re.search(rf"\b{re.escape(project)}[-_ ]{re.escape(bug)}\b", said, re.I):
        add(f"names {project}-{bug}", "bug id")
    issue = meta.get("issue") or ""
    m = re.match(r"([A-Za-z]+)-(\d+)$", issue)
    if m and re.search(rf"\b{m.group(1)}[-_ ]?{m.group(2)}\b", said, re.I):
        add(f"names {issue}", "issue id")
    for name in names:
        if len(name) > 8 and re.search(rf"\b{re.escape(name)}\b", said):
            add(f"names the trigger test {name}", "trigger name", name)
    return found


def audit(path, arm, verbose):
    base = path.split(".stream.jsonl")[0]
    tag = os.path.basename(base)
    cwd, commands, texts, written, results, refused = transcript(path)
    flags = []
    try:
        own = json.load(open(base + ".meta.json")).get("tmpdir") or ""
    except (OSError, ValueError):
        own = ""

    def flag(kind, cid, cmd):
        flags.append((kind, cmd, results.get(cid, "")))

    denied = 0
    for cid, cmd in commands:
        if SANDBOX_DENIAL.search(results.get(cid, "")[:400]):
            denied += 1
        if NETWORK.search(cmd):
            flag("network", cid, cmd)
        if VCS.search(cmd):
            flag("vcs", cid, cmd)
        own_tmp = False
        for m in ABS_PATH.finditer(cmd):
            p = m.group(1)
            if cwd and (p == cwd or p.startswith(cwd + "/")):
                continue
            if p in ("/tmp", "/dev/null") or p.startswith("/dev/"):
                continue
            if own and (p == own or p.startswith(own + "/")):
                own_tmp = True
                continue
            flag("outside", cid, cmd)
            break
        if own_tmp:
            flag("own tmp", cid, cmd)
        if arm == SPEC_ARM:
            if INSPECT_WORD.search(cmd) or INSPECT_PATH.search(cmd) \
                    or (re.search(r"\bjavac\b", cmd) and JAVAC_EXEC.search(cmd)):
                flag("inspect", cid, cmd)
            if JAVAC.search(cmd):
                flag("javac", cid, cmd)

    other = []
    try:
        other = [l.strip() for l in open(base + ".touched")
                 if l.strip() and not l.strip().endswith("AgentTest.java")]
    except OSError:
        pass
    knew = knowledge(base, texts, written)
    held = [k for k in knowledge(base, texts, written, counted_only=False) if k.endswith("(in the working copy)")]

    counts = {k: sum(1 for f in flags if f[0] == k)
              for k in ("network", "vcs", "outside", "own tmp", "inspect", "javac")}
    line = (f"{tag:<10} commands={len(commands):<3} refused={refused:<2} denied={denied:<2} "
            + " ".join(f"{k.replace(' ', '_')}={v}" for k, v in counts.items()
                       if k not in ("inspect", "javac") or arm == SPEC_ARM)
            + f" other={len(other)}")
    if knew or held:
        line += "  knew: " + "; ".join(knew + held)
    print("  " + line)
    if verbose:
        for kind, cmd, res in flags:
            print(f"      [{kind}] {' '.join(cmd.split())[:150]}")
            print(f"          -> {' '.join(res.split())[:150]}")
        for f in other:
            print(f"      [other] {f}")
    return counts, refused, denied, knew, len(commands), len(other)


def knew_runs(root):
    """{(arm, bug)} whose transcript names the bug: for the analysis."""
    found = set()
    for arm in ARMS:
        for path in sorted(glob.glob(os.path.join(root, f"runs-{arm}", "*.stream.jsonl*"))):
            base = path.split(".stream.jsonl")[0]
            _, _, texts, written, _, _ = transcript(path)
            if knowledge(base, texts, written):
                found.add((arm, os.path.basename(base)))
    return found


def closing(root):
    """The closing message of every f7 run, with the tests acceptance left out,
    for reading at the audit."""
    paths = sorted(glob.glob(os.path.join(root, "runs-f7", "*.json")))
    paths = [p for p in paths if not p.endswith((".meta.json", ".settings.json"))]
    print(f"f7: {len(paths)} closing messages")
    for p in paths:
        try:
            text = json.load(open(p)).get("result") or ""
        except (OSError, ValueError):
            text = "(unreadable)"
        print(f"\n=== {os.path.basename(p)[:-len('.json')]}")
        print(text.strip() or "(empty)")
        try:
            left = [l.strip() for l in open(p[:-len(".json")] + ".excluded") if l.strip()]
        except OSError:
            left = []
        print(f"--- left out at acceptance: {len(left)}")
        for key in left:
            print(f"    {key}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv[1:]
    root = args[0] if args else "data/campaign7"
    if "--closing" in sys.argv[1:]:
        closing(root)
        return
    found = False
    for arm in ARMS:
        paths = sorted(glob.glob(os.path.join(root, f"runs-{arm}", "*.stream.jsonl*")))
        if not paths:
            continue
        found = True
        print(f"{arm}: {len(paths)} transcripts")
        total = {"network": 0, "vcs": 0, "outside": 0, "own tmp": 0, "inspect": 0, "javac": 0}
        runs_flagged = knew_n = refused_n = denied_n = other_n = 0
        for path in paths:
            counts, refused, denied, knew, _, other = audit(path, arm, verbose)
            for k, v in counts.items():
                total[k] += v
            runs_flagged += any(counts.values())
            knew_n += bool(knew)
            refused_n += refused
            denied_n += denied
            other_n += bool(other)
        print(f"  runs with a flagged command: {runs_flagged} of {len(paths)}; "
              f"calls the harness refused: {refused_n}; "
              f"commands the sandbox denied: {denied_n}; "
              f"runs that touched another file: {other_n}; "
              f"runs that name the bug: {knew_n}")
        print()
    if not found:
        print(f"no transcripts under {root}/runs-f7 or {root}/runs-m7")


if __name__ == "__main__":
    main()

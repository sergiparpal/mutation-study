#!/usr/bin/env python3
"""
Read the transcripts of the second campaign and report what each agent did
that the protocol forbids, or tried to.

WHY
---
In the first campaign the prompts forbade several things (running the tests in
the specification-only arm, inspecting the compiled classes, version control,
the web) and nothing enforced or recorded any of it. The second campaign
enforces most of it with a sandbox (bin/generate-suites.sh) and keeps every
run's messages. This script is the other half: it reads what was kept.

It reports, per run:

  commands   how many shell commands the agent ran
  denied     tool calls the harness refused (file tools outside the working
             copy, anything that needed a permission nobody could grant)
  network    commands that reach for the network (curl, wget, git clone, ...)
  vcs        commands that run git
  outside    commands naming a path outside the working copy
  inspect    s2 only: commands that run, disassemble or unpack compiled code
             (java, javap, jshell, jar, unzip, strings, xxd, od, a scripting
             language pointed at lib/), or pass javac an option that executes
             code (-processor, -Xplugin, -J)
  knew       the agent's own text, or a test it wrote, names the benchmark,
             the issue behind the bug, or one of the bug's trigger tests

A flagged command is one the agent ISSUED. Whether it did anything is in the
tool result printed next to it: the sandbox blocks the network and hides
everything outside the working copy, and in s2 it hides every JDK launcher but
javac. `knew` is evidence of knowledge, not of its source.

`outside` includes /tmp, which needs reading with care. Inside the sandbox
/tmp is an empty directory private to each command: a file written there is
gone when the command ends and never reaches the host (seen in the pilot, where
an agent unpacked a JUnit class into /tmp to read its signatures). Such a
command is flagged all the same; what matters is what it read.

Usage:
    ./bin/audit-transcripts.py                         # data/campaign2
    ./bin/audit-transcripts.py data/campaign2 -v       # every flagged command
"""

import glob
import json
import lzma
import os
import re
import sys

NETWORK = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|rsync|ftp|telnet|pip3?\s+install|"
                     r"npm\s+install|mvn|gradle|git\s+(clone|fetch|pull|remote))\b")
VCS = re.compile(r"\bgit\b")
INSPECT = re.compile(r"(?<![\w./-])(java|javap|jshell|jar|jdb|jdeps|jrunscript|jjs|"
                     r"unzip|zipinfo|funzip|bsdtar|7z|strings|xxd|od|hexdump|"
                     r"python3?|perl|ruby|node|base64)\b(?!\.sh)")
JAVAC_EXEC = re.compile(r"-processor\b|-processorpath\b|-Xplugin|(?<![\w-])-J\S")
ABS_PATH = re.compile(r"(?<![\w.$-])(/(?:home|tmp|mnt|opt|root|srv|media|var|etc|proc|sys)\b[^\s'\";|&)]*|~/?[^\s'\";|&)]*)")
BENCHMARK = re.compile(r"defects4j|\bd4j\b", re.I)


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


def audit(path, arm, verbose):
    base = path.split(".stream.jsonl")[0]
    tag = os.path.basename(base)
    cwd = None
    commands, flags, texts, written = [], [], [], []
    results = {}
    denied = 0

    for obj in read_stream(path):
        kind = obj.get("type")
        if kind == "system" and obj.get("subtype") == "init":
            cwd = obj.get("cwd")
        elif kind == "system" and obj.get("subtype") == "permission_denied":
            denied += 1
        elif kind == "assistant":
            for part in obj.get("message", {}).get("content", []):
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    inp = part.get("input") or {}
                    if part.get("name") == "Bash":
                        commands.append((part.get("id"), inp.get("command", "")))
                    elif part.get("name") in ("Write", "Edit"):
                        written.append(inp.get("content") or inp.get("new_string") or "")
        elif kind == "user":
            content = obj.get("message", {}).get("content")
            for part in content if isinstance(content, list) else []:
                if part.get("type") == "tool_result":
                    body = part.get("content")
                    if not isinstance(body, str):
                        body = " ".join(x.get("text", "") for x in body or []
                                        if isinstance(x, dict))
                    results[part.get("tool_use_id")] = body
                    if "--restricted confines" in body or "permission" in body.lower()[:200]:
                        denied += 1

    def flag(kind, cid, cmd):
        flags.append((kind, cmd, results.get(cid, "")))

    for cid, cmd in commands:
        if NETWORK.search(cmd):
            flag("network", cid, cmd)
        if VCS.search(cmd):
            flag("vcs", cid, cmd)
        for m in ABS_PATH.finditer(cmd):
            p = m.group(1)
            if cwd and (p == cwd or p.startswith(cwd + "/")):
                continue
            if p in ("/tmp", "/dev/null") or p.startswith("/dev/"):
                continue
            flag("outside", cid, cmd)
            break
        if arm == "s2":
            if INSPECT.search(cmd) or (re.search(r"\bjavac\b", cmd) and JAVAC_EXEC.search(cmd)):
                flag("inspect", cid, cmd)

    # did the agent show it knew which bug this is?
    knew = []
    names, issue = [], ""
    try:
        names = sorted({l.strip().split("::")[1] for l in open(base + ".triggers") if "::" in l})
        issue = json.load(open(base + ".meta.json")).get("issue", "")
    except (OSError, ValueError, IndexError):
        pass
    said = "\n".join(texts)
    wrote = "\n".join(written)
    if BENCHMARK.search(said) or BENCHMARK.search(wrote):
        knew.append("names the benchmark")
    m = re.match(r"([A-Za-z]+)-(\d+)$", issue)
    if m and re.search(rf"\b{m.group(1)}[-_ ]?{m.group(2)}\b", said + "\n" + wrote, re.I):
        knew.append(f"names {issue}")
    for name in names:
        if len(name) > 8 and re.search(rf"\b{re.escape(name)}\b", said + "\n" + wrote):
            knew.append(f"names the trigger test {name}")

    counts = {k: sum(1 for f in flags if f[0] == k)
              for k in ("network", "vcs", "outside", "inspect")}
    line = (f"{tag:<9} commands={len(commands):<3} denied={denied:<2} "
            + " ".join(f"{k}={v}" for k, v in counts.items() if v or k != "inspect" or arm == "s2"))
    if knew:
        line += "  knew: " + "; ".join(knew)
    print("  " + line)
    if verbose:
        for kind, cmd, res in flags:
            print(f"      [{kind}] {' '.join(cmd.split())[:150]}")
            print(f"          -> {' '.join(res.split())[:150]}")
    return counts, denied, bool(knew), len(commands)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv[1:]
    root = args[0] if args else "data/campaign2"
    found = False
    for arm in ("m2", "s2"):
        paths = sorted(glob.glob(os.path.join(root, f"runs-{arm}", "*.stream.jsonl*")))
        if not paths:
            continue
        found = True
        print(f"{arm}: {len(paths)} transcripts")
        total = {"network": 0, "vcs": 0, "outside": 0, "inspect": 0}
        runs_flagged = knew_n = denied_n = 0
        for path in paths:
            counts, denied, knew, _ = audit(path, arm, verbose)
            for k, v in counts.items():
                total[k] += v
            runs_flagged += any(counts.values())
            knew_n += knew
            denied_n += denied
        print(f"  runs with a flagged command: {runs_flagged} of {len(paths)}; "
              f"refused tool calls: {denied_n}; "
              f"runs showing knowledge of the bug: {knew_n}")
        print()
    if not found:
        print(f"no transcripts under {root}/runs-m2 or {root}/runs-s2")


if __name__ == "__main__":
    main()

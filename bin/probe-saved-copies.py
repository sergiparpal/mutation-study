#!/usr/bin/env python3
"""
How far the one exception the sandbox leaves reaches: the Read tool on the
copy the CLI saves of a command's long output.

WHY THIS EXISTS
---------------
bin/agent-sandbox.py's probe found that --restricted, which confines the file
tools to the working copy, still lets the Read tool open the copy the CLI saves
under ~/.claude/projects of a command's output when it is longer than the CLI
passes on (data/README.md, "The sandbox after the third campaign"). It tried
the run's own copy only. Whether the same exception opens other files there,
such as the copies of other runs or what other sessions of the same user keep
there, was not tried. This was written on 21 November 2026, after the fourth
campaign, to try it. bin/agent-sandbox.py is part of that campaign's record and
is not changed: this imports its settings, environment, flags and stand-in for
the API, and runs the CLI the way its probe does.

WHAT IT TRIES
-------------
Each file below holds a random word, and the run tries to read it:

  planted while the run goes on, in its own directories under ~/.claude/projects:
    own-results-dir   a file the CLI did not write, beside the saved copy
    own-session-dir   a file in the run's session directory, outside tool-results
    own-project-dir   a file in the directory the CLI keeps for the working copy
    sibling-session   a saved copy of another session of the same working copy
  planted before the run:
    other-saved       a saved copy of a session of another working copy
    other-memory      a memory note of another working copy
    other-transcript  a session transcript of another working copy
    claude-root       a file in ~/.claude, outside projects
    lookalike         a file in a directory named tool-results outside ~/.claude

Then the Glob and Grep tools look under ~/.claude/projects for the word, and a
command tries to print one of the files.

The run's own saved copy and own-results-dir are reported in notes: they are
the exception as found. Each of the other files is a check, which passes when
the run cannot read it; so are Glob, Grep and the command. It prints one line
per check and exits with 1 if any fails, with 2 if a run did not complete.

CHECKING IT
-----------
    ./bin/probe-saved-copies.py            # both arms, bin/agent-sandbox.py's settings
    ./bin/probe-saved-copies.py --as-run   # the settings of the second and third campaigns
    ./bin/probe-saved-copies.py --arm s    # one arm

No model is called and nothing is charged. Everything planted is removed
afterwards, with what the CLI saved for the run. Like bin/agent-sandbox.py's
probe, it is to be run on the machine and with the CLI binary a campaign will
use: what the file tools may open is the CLI's behaviour.
"""

import argparse
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid

DURING = {
    "own-results-dir": "a file the CLI did not write, beside the saved copy",
    "own-session-dir": "a file in the run's session directory, outside tool-results",
    "own-project-dir": "a file in the directory the CLI keeps for the working copy",
    "sibling-session": "a saved copy of another session of the same working copy",
}
BEFORE = {
    "other-saved": "a saved copy of a session of another working copy",
    "other-memory": "a memory note of another working copy",
    "other-transcript": "a session transcript of another working copy",
    "claude-root": "a file in ~/.claude, outside projects",
    "lookalike": "a file in a directory named tool-results outside ~/.claude",
}
EXCEPTION = {"own-results-dir"}


def load_sandbox():
    sys.dont_write_bytecode = True      # no __pycache__ beside the scripts
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-sandbox.py")
    spec = importlib.util.spec_from_file_location("agent_sandbox", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(sb, arm, as_run, claude_bin, jdk_bin):
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")
    projects = os.path.join(claude_dir, "projects")
    shared = f"/tmp/claude-{os.getuid()}"
    word = secrets.token_hex(8)

    work = tempfile.mkdtemp(prefix="w-", dir="/tmp")            # as the generators do
    own = None if as_run else tempfile.mkdtemp(prefix="t-", dir="/tmp")
    slug = re.sub(r"[^A-Za-z0-9]", "-", work)
    other = os.path.join(projects, f"-tmp-w-probecanary{secrets.token_hex(4)}")
    lookalike_top = os.path.join(home, ".cache", f"probe-canary-{word}")
    before = {
        "other-saved": os.path.join(other, str(uuid.uuid4()), "tool-results", f"canary-{word}.txt"),
        "other-memory": os.path.join(other, "memory", f"canary-{word}.md"),
        "other-transcript": os.path.join(other, f"{uuid.uuid4()}.jsonl"),
        "claude-root": os.path.join(claude_dir, f"probe-canary-{word}.txt"),
        "lookalike": os.path.join(lookalike_top, "tool-results", f"canary-{word}.txt"),
    }

    def plant(path, key):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if path.endswith(".jsonl"):
                fh.write(json.dumps({"type": "user", "message": {"content": f"{word}-{key}"}}) + "\n")
            else:
                fh.write(f"{word}-{key}\n")
        return path

    state = {"saved": None, "during": {}}

    def read_saved(result):
        m = re.search(r"(/[^\s'\"]+/tool-results/[^\s'\"]+)", result)
        state["saved"] = m.group(1) if m else None
        return {"file_path": state["saved"] or "/no-saved-copy", "limit": 3}

    def planted_during(key):
        # the run's own directories exist once the CLI has saved a copy
        def step(_result):
            saved = state["saved"]
            if not saved:
                return {"file_path": "/no-saved-copy"}
            results_dir = os.path.dirname(saved)
            session_dir = os.path.dirname(results_dir)
            project_dir = os.path.dirname(session_dir)
            path = {
                "own-results-dir": os.path.join(results_dir, f"canary-{word}.txt"),
                "own-session-dir": os.path.join(session_dir, f"canary-{word}.txt"),
                "own-project-dir": os.path.join(project_dir, f"canary-{word}.txt"),
                "sibling-session": os.path.join(project_dir, str(uuid.uuid4()), "tool-results",
                                                f"canary-{word}.txt"),
            }[key]
            state["during"][key] = plant(path, key)
            return {"file_path": path}
        return step

    # One plain command each, as in bin/agent-sandbox.py's probe.
    steps = [("long", "Bash", "seq 1 60000"), ("read-saved", "Read", read_saved)]
    steps += [(k, "Read", planted_during(k)) for k in DURING]
    steps += [(k, "Read", {"file_path": before[k]}) for k in BEFORE]
    steps += [
        ("glob", "Glob", {"pattern": f"**/*{word}*", "path": projects}),
        ("grep", "Grep", {"pattern": word, "path": projects}),
        ("cat", "Bash", f"cat {before['other-saved']} 2>&1; echo DONE"),
    ]
    steps = [(sid, tool, inp if isinstance(inp, dict) or callable(inp)
              else {"command": inp, "description": "probe"}) for sid, tool, inp in steps]

    server, settings_file, stream, stderr = None, None, "", ""
    try:
        for k in BEFORE:
            plant(before[k], k)
        server = sb.StandIn(steps)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        cfg = os.path.join(home, ".cache", "gen-stage")
        os.makedirs(cfg, exist_ok=True)
        settings_file = os.path.join(cfg, os.path.basename(work) + ".settings.json")
        with open(settings_file, "w") as fh:
            json.dump(sb.settings(work, arm, jdk_bin, as_run=as_run), fh, indent=2)
        env = sb.environment(home, own)
        env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{port}"
        env["ANTHROPIC_API_KEY"] = "stand-in-no-key"
        cmd = [claude_bin, "-p", "probe", "--model", "claude-stand-in-0", "--tools", sb.TOOLS,
               "--settings", settings_file] + sb.FLAGS
        try:
            done = subprocess.run(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=600)
            stream, stderr = done.stdout, done.stderr
        except subprocess.TimeoutExpired as e:
            stream, stderr = (e.stdout or ""), "timed out"
    finally:
        if server:
            server.shutdown()
        # what was planted, and what the CLI saved for this working copy
        shutil.rmtree(os.path.join(projects, slug), ignore_errors=True)
        sibling = state["during"].get("sibling-session")
        if sibling:
            shutil.rmtree(os.path.dirname(os.path.dirname(sibling)), ignore_errors=True)
        for p in state["during"].values():
            if os.path.isfile(p):
                os.remove(p)
        shutil.rmtree(other, ignore_errors=True)
        shutil.rmtree(lookalike_top, ignore_errors=True)
        if os.path.isfile(before["claude-root"]):
            os.remove(before["claude-root"])
        shutil.rmtree(os.path.join(shared, slug), ignore_errors=True)
        if settings_file and os.path.isfile(settings_file):
            os.remove(settings_file)
        shutil.rmtree(work, ignore_errors=True)
        if own:
            shutil.rmtree(own, ignore_errors=True)

    out, refused = {}, {}
    for line in stream.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict) or o.get("type") != "user":
            continue
        content = (o.get("message") or {}).get("content")
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                sid = str(b.get("tool_use_id", "")).replace("toolu_probe_", "")
                out[sid] = sb.text_of(b.get("content"))
                refused[sid] = bool(b.get("is_error"))

    def tidy(text):
        """The first line of a tool result, with the planted file, the working
        copy and the home directory named instead of spelt out."""
        first = (text.strip().splitlines() or [""])[0]
        for p in list(before.values()) + list(state["during"].values()):
            first = first.replace(p, "<the file>")
        first = re.sub(r"[^\s:'\"]*" + word + r"[^\s:'\"]*", "<the file>", first)
        return first.replace(work, "<working copy>").replace(home, "~")[:160]

    label = (f"{'specification-only' if sb.spec_only(arm) else 'implementation-visible'} arm, "
             + ("the settings of the second and third campaigns" if as_run
                else "the settings of bin/agent-sandbox.py"))
    print(f"\n{label}")
    missing = [sid for sid, _t, _i in steps if sid not in out]
    if missing:
        print(f"  the CLI did not run every step (missing: {' '.join(missing)})")
        print("  stderr: " + stderr.strip()[:1500])
        return None
    saved = state["saved"]
    if not saved:
        print("  no copy of the long output was saved: the run's own directories were not tried")
        return None

    project_of_saved = os.path.dirname(os.path.dirname(os.path.dirname(saved)))
    shape = ("~/.claude/projects/<working copy>/<session>/tool-results/<file>"
             if project_of_saved == os.path.join(projects, slug) else tidy(saved))
    read_own = not refused["read-saved"] and "--restricted" not in out["read-saved"]
    print(f"  note  the Read tool on the run's own saved copy: {'read' if read_own else 'refused'}"
          f"  [{shape}]")
    ok = True
    for key, what in list(DURING.items()) + list(BEFORE.items()):
        got = f"{word}-{key}" in out[key]
        if key in EXCEPTION:
            print(f"  note  the Read tool on {key}, {what}: {'read' if got else 'refused'}")
            continue
        ok = ok and not got
        print(f"  {'FAIL' if got else 'ok  '}  the Read tool does not read {key}, {what}"
              + ("" if got else f"  [{tidy(out[key])}]"))
    for sid, tool in (("glob", "Glob"), ("grep", "Grep")):
        found = word in out[sid]
        ok = ok and not found
        print(f"  {'FAIL' if found else 'ok  '}  the {tool} tool finds none of them"
              " under ~/.claude/projects"
              + ("" if found else f"  [{tidy(out[sid]) or 'no output'}]"))
    printed = f"{word}-other-saved" in out["cat"]
    ok = ok and not printed
    print(f"  {'FAIL' if printed else 'ok  '}  a command cannot print other-saved"
          + ("" if printed else f"  [{tidy(out['cat'])}]"))
    api = sum(1 for _m, p in server.requests if p.endswith("/v1/messages"))
    print(f"  note  {api} requests for a model's answer, all of them to the stand-in")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--arm", action="append", help="m or s; default: both")
    ap.add_argument("--as-run", action="store_true",
                    help="the settings and environment of the second and third campaigns")
    ap.add_argument("--claude", help="the CLI binary; default: the one `claude` links to")
    args = ap.parse_args()
    sb = load_sandbox()
    arms = args.arm or ["m", "s"]
    for arm in arms:
        sb.spec_only(arm)
    javac = shutil.which("javac")
    claude = args.claude or shutil.which("claude")
    if not javac or not claude:
        sys.exit("javac and claude must be on PATH")
    jdk_bin = os.path.dirname(os.path.realpath(javac))
    claude = os.path.realpath(claude)
    version = subprocess.run([claude, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"CLI {version}")
    results = [run(sb, arm, args.as_run, claude, jdk_bin) for arm in arms]
    print()
    if any(r is None for r in results):
        print("a run did not complete")
        sys.exit(2)
    print("every check passed" if all(results) else "NOT every check passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

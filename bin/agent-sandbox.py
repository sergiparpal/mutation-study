#!/usr/bin/env python3
"""
The sandbox an agent run is given, and a check of what it encloses.

WHY THIS EXISTS
---------------
The generators of the second and third campaigns (bin/generate-suites.sh and
bin/generate-postcutoff.sh) write the sandbox settings themselves. The third
campaign's transcript audit found that those settings enclose less than the
generators' headers say (data/campaign3/PROTOCOL.md, "Deviations"):

- The temporary directory the CLI gives a sandboxed command, $TMPDIR, is a
  directory of the machine, /tmp/claude-<uid>, which every run and every other
  Claude Code session of the same user share.
- The jars the operating system's packages install under /usr/share/java can
  be read. On the machine the campaigns ran on, two of them are releases of
  projects under study.
- The operating system's Maven is on the agent's PATH and runs.

Those two generators are part of their campaigns' records and stay as they
ran. A generator written after them takes its settings from here.

WHAT IS DIFFERENT FROM THE SETTINGS OF THOSE CAMPAIGNS
------------------------------------------------------
- Each run has a temporary directory of its own. The generator makes an empty
  one and names it to the CLI in CLAUDE_CODE_TMPDIR; the CLI then gives
  sandboxed commands <that directory>/claude-<uid> as $TMPDIR, and the
  directory all sessions share stays behind the denial of /tmp. The name has to
  be short: the CLI falls back to the shared directory when it is not, which
  is why it is under /tmp and not beside the staged revision. The probe below
  fails if the fallback happens.
- /usr/share/java, /usr/share/maven-repo, /usr/share/maven and /usr/share/doc
  cannot be read: the packaged jars, the packaged Maven and its repository,
  and the packages' release notes. Without /usr/share/maven the `mvn` on the
  PATH does not start.

Everything else is as in those campaigns, the arms' differences included.

Not closed: the Read tool, confined to the working copy by --restricted, still
reads the copy the CLI saves under ~/.claude/projects of a command's output
when it is longer than the CLI passes on. That copy holds what the run's own
command printed and nothing else; the probe reports it in a note.

    T=$(mktemp -d /tmp/t-XXXXXXXX)
    ./bin/agent-sandbox.py settings "$W" "$ARM" "$JDK_BIN" > "$SETTINGS"
    (cd "$W" && env -i HOME="$HOME" PATH="$AGENT_PATH" ... CLAUDE_CODE_TMPDIR="$T" \\
        "$CLAUDE_BIN" -p "$PROMPT" --restricted ... --settings "$SETTINGS" ...)
    # then: what the run left under "$T" goes into its record, and "$T" is removed

CHECKING IT
-----------
    ./bin/agent-sandbox.py probe              # both arms, the settings above
    ./bin/agent-sandbox.py probe --as-run     # the settings of the two campaigns
    ./bin/agent-sandbox.py probe --arm s -v   # one arm, with every tool result
    ./bin/agent-sandbox.py probe --tmp-in DIR # the runs' temporary directories
                                              # made in DIR and not in /tmp

The probe runs the CLI the way a generator does, same flags and same
environment, in a working copy under /tmp, but pointed at a server on this
machine that stands in for the API and answers each request with the next of
a fixed list of tool calls. No model is called and nothing is charged. What
the CLI does with a tool call is the real thing: the sandbox it builds around
a command, and what --restricted lets a file tool read.

Before the run it leaves a file with a random word in the shared temporary
directory, in /tmp and in /var/tmp, and searches the part of the file system
the settings of the two campaigns left readable for archives that hold a class
of a project under study. The commands then try to read all of them. It
prints one line per check and exits with 1 if any fails. With --as-run the
failures are the finding.

It is to be run before a campaign, on the machine and with the CLI binary the
campaign will use: both the temporary directory and the file tools' confinement
are the CLI's behaviour, and the jars are the machine's.

What -v prints is not for a public record: under the settings of the two
campaigns it includes the names of every directory in the shared temporary
directory, and in either case the machine's mount table.
"""

import argparse
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile

# what the settings of the second and third campaigns hide
HIDDEN_BEFORE = ["/home", "/mnt", "/tmp", "/var/tmp", "/opt", "/root", "/srv", "/media"]
# what these add
HIDDEN_NOW = ["/usr/share/java", "/usr/share/maven-repo", "/usr/share/maven", "/usr/share/doc"]
UNPACKERS = ["/usr/bin/unzip", "/usr/bin/zipinfo", "/usr/bin/funzip",
             "/usr/bin/zipgrep", "/usr/bin/bsdtar"]

# The packages of the projects under study: the three of the post-cutoff
# corpora and Defects4J's.
PACKAGES = [
    "org/apache/commons/lang3", "org/apache/commons/lang", "org/apache/commons/csv",
    "org/apache/commons/cli", "org/apache/commons/codec", "org/apache/commons/collections4",
    "org/apache/commons/collections", "org/apache/commons/compress", "org/apache/commons/math3",
    "org/apache/commons/math", "org/apache/commons/jxpath", "com/google/gson", "org/jsoup",
    "com/fasterxml/jackson", "org/joda/time", "com/google/javascript", "org/mockito", "org/jfree",
]

TOOLS = "Bash,Read,Write,Edit,Glob,Grep"
FLAGS = ["--restricted", "--strict-mcp-config", "--disable-slash-commands",
         "--permission-mode", "acceptEdits", "--permission-prompts", "none",
         "--no-session-persistence", "--max-turns", "50", "--max-budget-usd", "5",
         "--output-format", "stream-json", "--verbose"]


def spec_only(arm):
    if arm[:1] not in ("m", "s"):
        sys.exit(f"arm must start with m (implementation-visible) or s (specification-only): {arm}")
    return arm[:1] == "s"


def settings(work, arm, jdk_bin, as_run=False, hide=()):
    """The settings file of one run. as_run: those of the two campaigns."""
    deny = list(HIDDEN_BEFORE)
    if not as_run:
        deny += HIDDEN_NOW + [h for h in hide if h not in HIDDEN_NOW]
    allow = [work]
    if spec_only(arm):
        # nothing that runs, disassembles or unpacks what is in lib/
        deny += [jdk_bin] + UNPACKERS
        # a jar is a zip: the scripting languages that could unpack it go too
        for tool in ("python3", "python", "perl"):
            found = shutil.which(tool)
            if found:
                deny += sorted({found, os.path.realpath(found)})
        allow += [os.path.join(jdk_bin, "javac")]
    return {
        "autoMemoryEnabled": False,
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {"denyRead": deny, "allowRead": allow, "allowWrite": [work]},
            "network": {"allowedDomains": [], "strictAllowlist": True},
        },
    }


def environment(home, tmp=None):
    """The environment a generator starts the CLI in. tmp: the run's own
    temporary directory; without it, the environment of the two campaigns."""
    env = {
        "HOME": home,
        "PATH": f"{home}/.local/bin:/usr/local/bin:/usr/bin:/bin",
        "TZ": "America/Los_Angeles",
        "LANG": "C.UTF-8",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP": "1",
        "DISABLE_AUTOUPDATER": "1",
    }
    if tmp:
        env["CLAUDE_CODE_TMPDIR"] = tmp
    return env


def archives_with(packages):
    """Archives, outside what the two campaigns' settings hide, that hold a
    class or a source file of one of the packages."""
    skip = set(HIDDEN_BEFORE) | {"/proc", "/sys", "/dev", "/run"}
    marks = [p.strip("/") + "/" for p in packages]
    hits = []
    for dp, dn, fn in os.walk("/"):
        dn[:] = [d for d in dn
                 if os.path.join(dp, d) not in skip and not os.path.islink(os.path.join(dp, d))]
        for f in fn:
            if not f.lower().endswith((".jar", ".zip", ".war", ".ear", ".jmod", ".aar")):
                continue
            path = os.path.join(dp, f)
            if os.path.islink(path):
                continue
            try:
                with zipfile.ZipFile(path) as z:
                    names = z.namelist()
            except (OSError, zipfile.BadZipFile):
                continue
            if any(m in n for n in names for m in marks):
                hits.append(path)
    return sorted(hits)


# ---- the stand-in for the API -------------------------------------------------

class StandIn(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, steps):
        super().__init__(("127.0.0.1", 0), Handler)
        self.steps = steps          # (id, tool name, tool input or a function giving it)
        self.requests = []          # method and path of every request; no header is kept


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _body(self):
        if self.headers.get("transfer-encoding", "").lower() == "chunked":
            data = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    return data
                data += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("content-length") or 0))

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def do_GET(self):
        self.server.requests.append(("GET", self.path.split("?")[0]))
        self._json({"type": "error", "error": {"type": "not_found_error", "message": "stand-in"}}, 404)

    def do_HEAD(self):
        self.server.requests.append(("HEAD", self.path.split("?")[0]))
        self.send_response(404)
        self.send_header("content-length", "0")
        self.send_header("connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_POST(self):
        path = self.path.split("?")[0]
        self.server.requests.append(("POST", path))
        body = self._body()
        if path.endswith("/count_tokens"):
            return self._json({"input_tokens": 1})
        if not path.endswith("/v1/messages"):
            return self._json({"type": "error",
                               "error": {"type": "not_found_error", "message": "stand-in"}}, 404)
        try:
            req = json.loads(body)
        except ValueError:
            req = {}
        # The agent's own requests carry the tools; anything else the CLI asks
        # on the side gets one word.
        names = [t.get("name") for t in req.get("tools") or [] if isinstance(t, dict)]
        if "Bash" in names:
            results = []
            for m in req.get("messages") or []:
                if m.get("role") == "user" and isinstance(m.get("content"), list):
                    results += [text_of(b.get("content")) for b in m["content"]
                                if isinstance(b, dict) and b.get("type") == "tool_result"]
            done = len(results)
            if done < len(self.server.steps):
                sid, tool, tool_input = self.server.steps[done]
                if callable(tool_input):        # a step that depends on the one before it
                    tool_input = tool_input(results[-1] if results else "")
                block = {"type": "tool_use", "id": f"toolu_probe_{sid}", "name": tool,
                         "input": tool_input}
                stop = "tool_use"
            else:
                block, stop = {"type": "text", "text": "The probe is finished."}, "end_turn"
        else:
            block, stop = {"type": "text", "text": "ok"}, "end_turn"
        message = {"id": "msg_probe_" + secrets.token_hex(6), "type": "message",
                   "role": "assistant", "model": req.get("model", "stand-in"),
                   "content": [block], "stop_reason": stop, "stop_sequence": None,
                   "usage": {"input_tokens": 1, "output_tokens": 1,
                             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
        if not req.get("stream"):
            return self._json(message)

        def event(name, data):
            return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()

        start = dict(message, content=[], stop_reason=None)
        out = event("message_start", {"type": "message_start", "message": start})
        if block["type"] == "tool_use":
            out += event("content_block_start", {
                "type": "content_block_start", "index": 0,
                "content_block": dict(block, input={})})
            out += event("content_block_delta", {
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
        else:
            out += event("content_block_start", {
                "type": "content_block_start", "index": 0,
                "content_block": {"type": "text", "text": ""}})
            out += event("content_block_delta", {
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": block["text"]}})
        out += event("content_block_stop", {"type": "content_block_stop", "index": 0})
        out += event("message_delta", {"type": "message_delta",
                                       "delta": {"stop_reason": stop, "stop_sequence": None},
                                       "usage": {"output_tokens": 1}})
        out += event("message_stop", {"type": "message_stop"})
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("content-length", str(len(out)))
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(out)
        self.close_connection = True


# ---- the probe ----------------------------------------------------------------

HELLO = """public class Hello {
    public static void main(String[] args) {
        System.out.println("hello from the probe");
    }
}
"""


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return "" if content is None else str(content)


def saved_copy(result):
    """The Read call for the file the CLI says it saved a long output in."""
    m = re.search(r"(/[^\s'\"]+/tool-results/[^\s'\"]+)", result)
    return {"file_path": m.group(1) if m else "/no-saved-copy", "limit": 3}


def probe(arm, as_run, claude_bin, jdk_bin, archives, verbose, tmp_parent="/tmp"):
    home = os.path.expanduser("~")
    uid = os.getuid()
    shared = f"/tmp/claude-{uid}"
    made_shared = not os.path.isdir(shared)
    if made_shared:
        os.mkdir(shared, 0o700)
    word = secrets.token_hex(8)

    work = tempfile.mkdtemp(prefix="w-", dir="/tmp")            # as the generators do
    own = None if as_run else tempfile.mkdtemp(prefix="t-", dir=tmp_parent)
    canary = {}
    for name, base in (("shared", shared), ("tmp", "/tmp"), ("vartmp", "/var/tmp")):
        d = tempfile.mkdtemp(prefix="probe-canary-", dir=base)
        with open(os.path.join(d, "secret.txt"), "w") as fh:
            fh.write(f"{word}-{name}\n")
        canary[name] = d
    os.mkdir(os.path.join(work, ".probe"))
    with open(os.path.join(work, ".probe", "Hello.java"), "w") as fh:
        fh.write(HELLO)

    # a text file in what is now hidden, for the Read tool to be tried on
    hidden_file, hidden_mark = None, None
    for top in HIDDEN_NOW:
        for dp, _dn, fn in os.walk(top):
            for f in sorted(fn):
                p = os.path.join(dp, f)
                if f.endswith((".pom", ".xml", ".txt", ".properties")) and not os.path.islink(p):
                    try:
                        text = open(p, encoding="utf-8").read()
                    except (OSError, UnicodeDecodeError):
                        continue
                    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 24]
                    if lines:
                        hidden_file, hidden_mark = p, lines[len(lines) // 2]
                        break
            if hidden_file:
                break
        if hidden_file:
            break

    expected_tmp = shared if as_run else os.path.join(own, f"claude-{uid}")
    dirs = " ".join(HIDDEN_NOW + [home, "/opt"])
    # One plain command each: the CLI refuses, as needing an approval nobody is
    # there to give, commands with a substitution or a loop in them.
    steps = [
        ("env", "Bash", 'echo "TMPDIR=$TMPDIR"; echo "PATH=$PATH"; pwd'),
        ("tmpls", "Bash", 'ls -A "$TMPDIR" 2>&1 | head -500; echo DONE'),
        ("shared-ls", "Bash", f'ls -A {shared} 2>&1 | head -500; echo DONE'),
        ("shared-cat", "Bash", f'cat {canary["shared"]}/secret.txt 2>&1; echo DONE'),
        ("sharedw", "Bash", f'echo x > {canary["shared"]}/written && echo WROTE'),
        ("tmp", "Bash", f'ls -A /tmp 2>&1 | head -50; cat {canary["tmp"]}/secret.txt 2>&1; '
                        f'cat {canary["vartmp"]}/secret.txt 2>&1; echo DONE'),
        ("mktemp", "Bash", 'mktemp 2>&1; echo DONE'),
        ("own", "Bash", 'echo kept > "$TMPDIR/probe-own" && cat "$TMPDIR/probe-own"'),
        ("dirs", "Bash", "; ".join(f'echo "ENTRIES {d}"; ls -A {d} 2>/dev/null | wc -l'
                                   for d in HIDDEN_NOW + [home, "/opt"])),
        ("mvn", "Bash", 'mvn -v 2>&1 | head -3; echo DONE'),
        ("javac", "Bash", 'javac -d .probe/out .probe/Hello.java 2>&1 && echo JAVAC-OK'),
        ("java", "Bash", 'java -cp .probe/out Hello 2>&1; echo DONE'),
        ("mounts", "Bash", "cat /proc/self/mountinfo"),
        ("read-shared", "Read", {"file_path": os.path.join(canary["shared"], "secret.txt")}),
        ("glob-java", "Glob", {"pattern": "*.jar", "path": "/usr/share/java"}),
        ("read-own", "Read", {"file_path": os.path.join(expected_tmp, "probe-own")}),
        # more than the CLI passes on: it saves the whole of it under the home
        ("long", "Bash", "seq 1 60000"),
        ("read-saved", "Read", saved_copy),
    ]
    for k in range(0, len(archives), 20):
        steps.append((f"archives-{k // 20}", "Bash", "; ".join(
            f"head -c 4 {a} > /dev/null 2>&1 && echo 'READABLE {a}'" for a in archives[k:k + 20])
            + "; echo CHECKED"))
    if hidden_file:
        steps.append(("read-hidden", "Read", {"file_path": hidden_file}))
    steps = [(sid, tool, inp if isinstance(inp, dict) or callable(inp)
              else {"command": inp, "description": "probe"}) for sid, tool, inp in steps]

    server = StandIn(steps)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    cfg = os.path.join(home, ".cache", "gen-stage")
    os.makedirs(cfg, exist_ok=True)
    settings_file = os.path.join(cfg, os.path.basename(work) + ".settings.json")
    with open(settings_file, "w") as fh:
        json.dump(settings(work, arm, jdk_bin, as_run=as_run), fh, indent=2)

    env = environment(home, own)
    env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{port}"
    env["ANTHROPIC_API_KEY"] = "stand-in-no-key"
    cmd = [claude_bin, "-p", "probe", "--model", "claude-stand-in-0", "--tools", TOOLS,
           "--settings", settings_file] + FLAGS
    try:
        run = subprocess.run(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=600)
        stream, stderr = run.stdout, run.stderr
    except subprocess.TimeoutExpired as e:
        stream, stderr = (e.stdout or ""), "timed out"
    server.shutdown()

    out, refused, result = {}, {}, {}
    for line in stream.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        if o.get("type") == "result":
            result = o
        content = (o.get("message") or {}).get("content") if o.get("type") == "user" else None
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                sid = str(b.get("tool_use_id", "")).replace("toolu_probe_", "")
                out[sid] = text_of(b.get("content"))
                refused[sid] = bool(b.get("is_error"))

    wrote_shared = os.path.exists(os.path.join(canary["shared"], "written"))
    left = []
    if own:
        for dp, _dn, fn in os.walk(own):
            left += [os.path.relpath(os.path.join(dp, f), own) for f in fn]

    # ---- clean up -------------------------------------------------------------
    for d in canary.values():
        shutil.rmtree(d, ignore_errors=True)
    # with the settings of the two campaigns the run's own files are in the
    # shared directory: the two it made, and the CLI's directory for this
    # working copy
    made = (out.get("mktemp", "").splitlines() or [""])[0].strip()
    for p in (os.path.join(shared, "probe-own"), settings_file,
              made if made.startswith(shared + "/tmp.") else ""):
        if p and os.path.isfile(p):
            os.remove(p)
    slug = re.sub(r"[^A-Za-z0-9]", "-", work)
    shutil.rmtree(os.path.join(shared, slug), ignore_errors=True)
    # and the copy of the long output the CLI saved under the home
    shutil.rmtree(os.path.join(home, ".claude", "projects", slug), ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    if own:
        shutil.rmtree(own, ignore_errors=True)
    if made_shared:
        try:
            os.rmdir(shared)
        except OSError:
            pass

    def val(sid, key):
        for ln in out.get(sid, "").splitlines():
            if ln.startswith(key):
                return ln[len(key):].strip()
        return ""

    def lines(sid):
        return [ln.strip() for ln in out.get(sid, "").splitlines() if ln.strip()]

    def entries(d):
        got = lines("dirs")
        for i, ln in enumerate(got[:-1]):
            if ln == f"ENTRIES {d}" and got[i + 1].isdigit():
                return int(got[i + 1])
        return -1

    label = f"{'specification-only' if spec_only(arm) else 'implementation-visible'} arm, " \
            f"{'the settings of the two campaigns' if as_run else 'the settings of this script'}"
    print(f"\n{label}")
    missing = [sid for sid, _t, _i in steps if sid not in out]
    unasked = [sid for sid, tool, _i in steps
               if tool == "Bash" and "requires approval" in out.get(sid, "")]
    if missing or unasked:
        if missing:
            print(f"  the CLI did not run every step (missing: {' '.join(missing)})")
            print(f"  requests seen by the stand-in: {server.requests[:12]}")
            print("  stderr: " + stderr.strip()[:2000])
            print("  stdout: " + stream.strip()[:2000])
        if unasked:
            print(f"  the CLI refused to run a command of the probe: {' '.join(unasked)}")
        return False

    tmpdir = val("env", "TMPDIR=")
    listed = "\n".join(out[sid] for sid, _t, _i in steps if sid.startswith("archives-"))
    checked = all("CHECKED" in out[sid] for sid, _t, _i in steps if sid.startswith("archives-"))
    readable = [ln for ln in listed.splitlines() if ln.startswith("READABLE ")]
    spec = spec_only(arm)
    ran = "hello from the probe" in out["java"]
    checks = [
        ("a command's $TMPDIR is the run's own directory",
         bool(own) and tmpdir.rstrip("/") == expected_tmp, tmpdir),
        ("nothing of another session is in it",
         "DONE" in out["tmpls"] and os.path.basename(canary["shared"]) not in lines("tmpls")
         and tmpdir.rstrip("/") != shared,
         f'{len(lines("tmpls")) - 1} entries when the run starts'),
        ("the temporary directory all sessions share cannot be listed",
         "DONE" in out["shared-ls"] and os.path.basename(canary["shared"]) not in lines("shared-ls"),
         ""),
        ("a file in it cannot be read",
         "DONE" in out["shared-cat"] and f"{word}-shared" not in out["shared-cat"], ""),
        ("nor written",
         not wrote_shared and "WROTE" not in out["sharedw"], ""),
        ("files in the machine's /tmp and /var/tmp cannot be read",
         "DONE" in out["tmp"] and f"{word}-tmp" not in out["tmp"]
         and f"{word}-vartmp" not in out["tmp"], ""),
        ("a command can make a temporary file and read it back",
         made.startswith(tmpdir.rstrip("/") + "/") and out["own"].strip() == "kept", made),
        ("the packaged jars, Maven and package documents cannot be listed",
         all(entries(d) == 0 for d in HIDDEN_NOW),
         ", ".join(f"{d}: {entries(d)}" for d in HIDDEN_NOW)),
        ("no archive holding a class of a project under study can be read",
         checked and not readable,
         f"{len(readable)} of {len(archives)} found on this machine"
         + ("".join("\n" + " " * 10 + r[9:] for r in readable))),
        ("Maven does not run",
         "DONE" in out["mvn"] and "Apache Maven" not in out["mvn"], ""),
        ("the home directory and /opt cannot be listed",
         entries(home) == 0 and entries("/opt") == 0, ""),
        ("javac compiles" + ("; java is not there" if spec else " and java runs"),
         "JAVAC-OK" in out["javac"] and "DONE" in out["java"] and ran != spec, ""),
        ("the Read tool does not read a file of the shared temporary directory",
         f"{word}-shared" not in out["read-shared"], ""),
        ("the Glob tool does not list /usr/share/java",
         ".jar" not in out["glob-java"] or refused["glob-java"], ""),
    ]
    if hidden_file:
        checks.append(("the Read tool does not read a file of the hidden directories",
                       hidden_mark not in out["read-hidden"], hidden_file))
    ok = True
    for what, passed, note in checks:
        ok = ok and passed
        print(f"  {'ok  ' if passed else 'FAIL'}  {what}" + (f"  [{note}]" if note else ""))
    print(f"  note  the Read tool on a file the run wrote in its $TMPDIR: "
          f"{'refused' if '--restricted' in out['read-own'] or refused['read-own'] else 'read'}")
    saved = re.search(r"(/[^\s'\"]+/tool-results/)", out["long"])
    print("  note  the Read tool on the CLI's saved copy of the run's own long output: "
          + ("no copy was saved" if not saved
             else ("refused" if "--restricted" in out["read-saved"] or refused["read-saved"]
                   else "read") + " [it is under ~/.claude/projects]"))
    if own:
        print(f"  note  left in the run's temporary directory: {len(left)} files")
    api = sum(1 for m, p in server.requests if p.endswith("/v1/messages"))
    print(f"  note  {api} requests for a model's answer, all of them to the stand-in; "
          f"{result.get('num_turns')} turns")
    if verbose:
        for sid, _tool, inp in steps:
            shown = "(from the step before)" if callable(inp) else inp.get("command") or json.dumps(inp)
            print(f"\n  --- {sid}: {shown}")
            print("  " + ("(error) " if refused.get(sid) else "")
                  + out.get(sid, "").strip()[:20000].replace("\n", "\n  "))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    sub = ap.add_subparsers(dest="what", required=True)
    s = sub.add_parser("settings", help="print the settings file of one run")
    s.add_argument("work")
    s.add_argument("arm")
    s.add_argument("jdk_bin")
    s.add_argument("--hide", action="append", default=[],
                   help="one more path to hide; may be repeated")
    p = sub.add_parser("probe", help="check, without a model call, what a run can reach")
    p.add_argument("--arm", action="append", help="m or s; default: both")
    p.add_argument("--as-run", action="store_true",
                   help="the settings and environment of the second and third campaigns")
    p.add_argument("--claude", help="the CLI binary; default: the one `claude` links to")
    p.add_argument("--tmp-in", default="/tmp", metavar="DIR",
                   help="where the run's temporary directory is made (default /tmp)")
    p.add_argument("-v", action="store_true", help="print every tool result")
    args = ap.parse_args()

    if args.what == "settings":
        print(json.dumps(settings(args.work, args.arm, args.jdk_bin, hide=args.hide), indent=2))
        return

    javac = shutil.which("javac")
    claude = args.claude or shutil.which("claude")
    if not javac or not claude:
        sys.exit("javac and claude must be on PATH")
    jdk_bin = os.path.dirname(os.path.realpath(javac))
    claude = os.path.realpath(claude)
    version = subprocess.run([claude, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"CLI {version}; JDK tools in {jdk_bin}")
    print("searching the readable file system for archives of the projects under study ...")
    archives = archives_with(PACKAGES)
    for a in archives:
        print("  " + a)
    if not archives:
        print("  none")
    ok = True
    for arm in args.arm or ["m", "s"]:
        ok = probe(arm, args.as_run, claude, jdk_bin, archives, args.v, args.tmp_in) and ok
    print()
    print("every check passed" if ok else "NOT every check passed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

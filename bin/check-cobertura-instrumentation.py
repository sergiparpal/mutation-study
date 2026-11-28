#!/usr/bin/env python3
"""
Check, without running a test, which methods Cobertura gives a line counter.

WHY
---
Defects4J measures line coverage with Cobertura 2.0.3. For Csv-4, Cobertura
reports the constructor of CSVParser and most of its methods as never
executed, although the tests run them: Major kills mutants on those lines,
and parse(String, CSVFormat), whose last line calls the constructor, is
reported hit thousands of times by the developers' own tests. The class
Cobertura writes has no line counter in those methods. This script measures
where in the sample that happens, and what in Csv-4's source causes it.

WHAT THIS DOES
--------------
By default, for every bug of data/sample.txt and both of its versions, it
checks the version out and compiles it with Defects4J, and instruments the
classes Defects4J's coverage step instruments: classes.modified and their
inner classes (framework/core/Project.pm, coverage_instrument). It uses the
Cobertura jar of Defects4J's defects4j.build.xml through Cobertura's
command-line instrumenter, with the version's compile class path as the
auxiliary class path, as the ant task has. For each method it then compares
the source lines in the method's line number table with the line counters
Cobertura put in its code: a read of __cobertura_counters at a constant
index, which is how Cobertura counts a line (a branch is counted at an index
held in a local variable, and is not counted here). A method with lines and
no line counter is one whose lines Cobertura reports as never executed,
whatever the tests do. Interfaces have no code and Cobertura writes no class
for them.

--variants compiles Csv-4's fixed CSVParser.java in six versions, which differ
only in the last statement of parse(URL, Charset, CSVFormat), instruments each
the same way, and prints the counters of every method. A seventh row,
"defects4j-compiled", is the class Defects4J's own build compiled, to show
that compiling here does not change the result.

Output, tab-separated with a header line:
  default      data/csv4-coverage/instrumentation.tsv
  --variants   data/csv4-coverage/variants.tsv
  bug ids      the given bugs only, on standard output (e.g. Csv,4 Csv,7)

Needs Defects4J v3.0.1-7-g8c16da82 at $D4J_HOME (default ~/defects4j) and
Java 11; no model and no test run. The default takes about 20 minutes.

Usage:
  ./bin/check-cobertura-instrumentation.py
  ./bin/check-cobertura-instrumentation.py --variants
  ./bin/check-cobertura-instrumentation.py Csv,4 Csv,7
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D4J_HOME = os.environ.get("D4J_HOME", os.path.expanduser("~/defects4j"))
D4J = os.path.join(D4J_HOME, "framework", "bin", "defects4j")
LIB = os.path.join(D4J_HOME, "framework", "projects", "lib")
D4J_REVISION = "v3.0.1-7-g8c16da82"
ENV = dict(os.environ, TZ="America/Los_Angeles")

# a method's code in javap's output: its declaration, two spaces in, then "    Code:"
METHOD = re.compile(r"\n(?=  [^ \n][^\n]*\n    Code:)")
LINE_COUNTER = re.compile(r"getstatic\s+#\d+\s+// Field __cobertura_counters:\[I\n"
                          r"\s+\d+: (?:ldc|ldc_w|sipush|bipush|iconst_\w+)\b")

# --variants: the last statement of parse(URL, Charset, CSVFormat) in Csv-4f
AS_IS = ("        return new CSVParser(new InputStreamReader(url.openStream(),\n"
         "                             charset == null ? Charset.forName(\"UTF-8\") : charset), format);\n")
COND = "charset == null ? Charset.forName(\"UTF-8\") : charset"
HELPER = ("    private static java.io.Reader reader(final java.io.InputStream in, final Charset cs) {\n"
          "        return new InputStreamReader(in, cs);\n"
          "    }\n\n")
VARIANTS = [
    ("as-is", "the source as it is: the conditional inside new InputStreamReader(...), "
              "itself inside new CSVParser(...)", AS_IS),
    ("one-line", "the same statement on one line",
     f"        return new CSVParser(new InputStreamReader(url.openStream(), {COND}), format);\n"),
    ("local-variable", "the conditional assigned to a local variable first",
     f"        final Charset cs = {COND};\n"
     "        return new CSVParser(new InputStreamReader(url.openStream(), cs), format);\n"),
    ("one-constructor", "the reader built in a statement of its own: the conditional "
                        "inside one constructor call",
     f"        final java.io.Reader r = new InputStreamReader(url.openStream(), {COND});\n"
     "        return new CSVParser(r, format);\n"),
    ("static-helper", "the reader built by a static method: no constructor call "
                      "around the conditional",
     f"        final java.io.Reader r = reader(url.openStream(), {COND});\n"
     "        return new CSVParser(r, format);\n"),
    ("no-conditional", "charset passed as it is",
     "        return new CSVParser(new InputStreamReader(url.openStream(), charset), format);\n"),
]


def run(cmd, **kw):
    return subprocess.run(cmd, env=ENV, capture_output=True, text=True, **kw)


def cobertura_cp():
    jars = [os.path.join(LIB, "cobertura-2.0.3.jar")]
    d = os.path.join(LIB, "cobertura-2.0.3-lib")
    jars += sorted(os.path.join(d, j) for j in os.listdir(d) if j.endswith(".jar"))
    return ":".join(jars)


def check_environment():
    if not os.access(D4J, os.X_OK):
        sys.exit(f"no Defects4J under {D4J_HOME} (set D4J_HOME)")
    rev = run(["git", "-C", D4J_HOME, "describe", "--tags"]).stdout.strip()
    if rev != D4J_REVISION:
        sys.exit(f"Defects4J {rev or 'unknown'}: the measurements used {D4J_REVISION}")
    if not os.path.exists(os.path.join(LIB, "cobertura-2.0.3.jar")):
        sys.exit("Defects4J's Cobertura jar is missing")


def signature(head):
    """A javap declaration as name(parameter types), <init> and <clinit> for initialisers."""
    if head in ("static {}", "static {};"):
        return "<clinit>()"
    head = declaration(head)
    m = re.search(r"([\w.$]+)\(([^)]*)\)$", head)
    if not m:
        return head
    name, params = m.groups()
    before = head[:m.start()].split()
    if not before or before[-1] in ("public", "private", "protected", "static", "final",
                                    "synchronized", "native", "abstract", "strictfp"):
        name = "<init>"           # a constructor: no return type before the name
    params = ",".join(p.strip().rsplit(".", 1)[-1] for p in params.split(",") if p.strip())
    return f"{name.rsplit('.', 1)[-1]}({params})"


def declaration(head):
    return re.sub(r"\s+throws\s+.*", "", head.rstrip(";"))


def methods(javap_text, count_lines):
    """declaration -> distinct source lines (count_lines) or line counters"""
    out = {}
    for part in METHOD.split(javap_text):
        head = part.split("\n", 1)[0].strip()
        if ("(" not in head and head != "static {};") or "__cobertura" in head:
            continue
        if count_lines:
            m = re.search(r"LineNumberTable:\n((?:\s+line \d+: \d+\n)+)", part + "\n")
            out[declaration(head)] = len(set(re.findall(r"line (\d+):", m.group(1)))) if m else 0
        else:
            out[declaration(head)] = len(LINE_COUNTER.findall(part))
    return out


def instrument(classes_dir, files, aux_cp, work):
    """Instrument files (relative to classes_dir) into work/out; return that directory."""
    out = os.path.join(work, "out")
    shutil.rmtree(out, ignore_errors=True)
    r = run(["java", "-cp", cobertura_cp(), "net.sourceforge.cobertura.instrument.Main",
             "--datafile", os.path.join(work, "cobertura.ser"), "--destination", out,
             "--auxClasspath", aux_cp, "--basedir", classes_dir] + files, cwd=classes_dir)
    if r.returncode:
        sys.exit(f"Cobertura failed on {classes_dir}:\n{r.stdout}{r.stderr}")
    return out


def compare(orig_class, instr_class):
    """Per method: (signature, lines, counters), for methods with lines."""
    lines = methods(run(["javap", "-c", "-l", "-p", orig_class]).stdout, True)
    ctrs = methods(run(["javap", "-c", "-p", instr_class]).stdout, False)
    return [(signature(d), n, ctrs.get(d, 0)) for d, n in lines.items() if n > 0]


def checkout(p, vid, wd):
    r = run([D4J, "checkout", "-p", p, "-v", vid, "-w", wd])
    if r.returncode:
        sys.exit(f"checkout of {p}-{vid} failed:\n{r.stderr[-2000:]}")
    r = run([D4J, "compile", "-w", wd])
    if r.returncode:
        sys.exit(f"compile of {p}-{vid} failed:\n{r.stderr[-2000:]}")
    exp = lambda prop: run([D4J, "export", "-p", prop, "-w", wd]).stdout.strip()
    return exp("classes.modified").split(), os.path.join(wd, exp("dir.bin.classes")), exp("cp.compile")


def class_files(classes, modified):
    """classes.modified and their inner classes, as Project.pm's coverage_instrument names them"""
    files = []
    for c in modified:
        base = c.replace(".", "/")
        d, b = os.path.dirname(base), os.path.basename(base)
        for f in sorted(os.listdir(os.path.join(classes, d))):
            if f == b + ".class" or (f.startswith(b + "$") and f.endswith(".class")):
                files.append(os.path.join(d, f))
    return files


def check_version(p, vid, work):
    wd = os.path.join(work, f"{p}-{vid}")
    modified, classes, cp = checkout(p, vid, wd)
    files = class_files(classes, modified)
    out = instrument(classes, files, cp, os.path.join(work, "cob"))
    rows = []
    for f in files:
        orig, inst = os.path.join(classes, f), os.path.join(out, f)
        if not os.path.exists(inst):
            decl = [l for l in run(["javap", "-p", orig]).stdout.splitlines() if l.rstrip().endswith("{")][:1]
            kind = "interface" if decl and re.search(r"\binterface\b", decl[0]) else "not written"
            rows.append([p, vid, f, kind, "0", "0", "0", "0", "0", ""])
            continue
        res = compare(orig, inst)
        lost = [s for s, n, c in res if c == 0]
        short = [s for s, n, c in res if 0 < c < n]
        rows.append([p, vid, f, "instrumented", str(len(res)), str(sum(n for _, n, _ in res)),
                     str(sum(c for _, _, c in res)), str(len(lost)), str(len(short)), " ".join(lost)])
    shutil.rmtree(wd, ignore_errors=True)
    return rows


def sample():
    bugs = []
    for line in open(os.path.join(ROOT, "data", "sample.txt")):
        if line.strip():
            p, i = line.strip().split(",")
            bugs.append((p, i))
    return bugs


def variants(work):
    wd = os.path.join(work, "Csv-4f")
    modified, classes, cp = checkout("Csv", "4f", wd)
    src = open(os.path.join(wd, "src/main/java/org/apache/commons/csv/CSVParser.java"), encoding="utf-8").read()
    if src.count(AS_IS) != 1:
        sys.exit("parse(URL, Charset, CSVFormat) in Csv-4f is not as this script expects")
    anchor = "    // the following objects are shared to reduce garbage\n"
    if src.count(anchor) != 1:
        sys.exit("cannot place the helper method of the static-helper variant")
    rows = []

    def record(name, desc, classes_dir):
        files = class_files(classes_dir, ["org.apache.commons.csv.CSVParser"])
        aux = classes + (":" + cp if cp else "")
        out = instrument(classes_dir, files, aux, os.path.join(work, "cob-" + name))
        f = "org/apache/commons/csv/CSVParser.class"
        for s, n, c in compare(os.path.join(classes_dir, f), os.path.join(out, f)):
            rows.append([name, desc, s, str(n), str(c)])

    record("defects4j-compiled", "the class Defects4J's build compiled from the source as it is", classes)
    for name, desc, stmt in VARIANTS:
        text = src.replace(AS_IS, stmt)
        if name == "static-helper":
            text = text.replace(anchor, HELPER + anchor)
        d = os.path.join(work, "variant-" + name)
        os.makedirs(os.path.join(d, "classes"))
        path = os.path.join(d, "CSVParser.java")
        open(path, "w", encoding="utf-8").write(text)
        r = run(["javac", "-nowarn", "-source", "1.6", "-target", "1.6", "-g", "-encoding", "UTF-8",
                 "-cp", classes, "-d", os.path.join(d, "classes"), path])
        if r.returncode:
            sys.exit(f"variant {name} does not compile:\n{r.stderr[-2000:]}")
        record(name, desc, os.path.join(d, "classes"))
    return rows


def write(rows, header, path):
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "w") if path else sys.stdout
    fh.write("\t".join(header) + "\n")
    for r in rows:
        fh.write("\t".join(r) + "\n")
    if path:
        fh.close()
        print(f"wrote {os.path.relpath(path, ROOT)}")


def main():
    args = sys.argv[1:]
    check_environment()
    work = tempfile.mkdtemp(prefix="cobertura-check-")
    try:
        if args == ["--variants"]:
            write(variants(work), ["variant", "change", "method", "lines", "line_counters"],
                  os.path.join(ROOT, "data", "csv4-coverage", "variants.tsv"))
            return
        bugs = [tuple(a.split(",")) for a in args] if args else sample()
        rows = []
        for p, i in bugs:
            for v in ("b", "f"):
                rows += check_version(p, i + v, work)
                print(f"{p}-{i}{v}: {sum(1 for r in rows if r[0] == p and r[1] == i + v)} class files",
                      file=sys.stderr)
        header = ["project", "version", "class_file", "status", "methods_with_lines", "lines",
                  "line_counters", "methods_without_counters", "methods_short", "methods_without_counters_names"]
        write(rows, header, None if args else os.path.join(ROOT, "data", "csv4-coverage", "instrumentation.tsv"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

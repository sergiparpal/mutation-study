# Third campaign: protocol

Fixed on 18 November 2026, before any run on the subjects. The commit that
adds this file, with the scripts as they are in it, is the reference. Anything
done differently afterwards is a deviation and is listed at the end, with its
date and reason, before the step it affects.

## Why a third campaign

The Defects4J sample is public and older than the model, so an agent may
recall a fault, its fix or its tests. Two small corpora of fix commits that
postdate the model's training data were mined to bound that
(`../README.md`, "Post-cutoff corpora"). Their runs do not carry the weight
the question needs:

- the implementation-visible agent worked in a git worktree, with the fix
  commit and its message within reach, and only a prompt forbade git;
- nothing the prompts forbade was enforced, no transcript was kept, and the
  model was named by an alias;
- the generated tests were not archived, so no verdict can be recomputed;
- the first corpus's specification-only arm has no valid verdict at all;
- six of the 28 validated subjects were used in neither arm, because the
  harness compiled every developer test and that fails once the file with the
  trigger tests is removed.

The second campaign closed the same gaps for the Defects4J sample
(`../campaign2/PROTOCOL.md`). This campaign makes the comparison of the two
arms on the post-cutoff subjects under that campaign's conditions. Its arms
are separate conditions, never pooled with those of the earlier runs on these
subjects or with those of the Defects4J campaigns.

## What is fixed

| | |
|---|---|
| Subjects | the 28 of `subjects.txt`: every fix commit validated for either post-cutoff corpus, each once |
| Arms | `m3`, implementation-visible; `s3`, specification-only; as built by `bin/generate-postcutoff.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per subject and arm, 56 in all |
| Order | subjects in the order of `subjects.txt`, a seeded shuffle; both arms of a subject before the next subject; `m3` first for the 1st, 3rd, 5th … subject and `s3` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign3.sh`) |
| Prompts | as written in `bin/generate-postcutoff.sh`; the prompt of each run is kept |
| Acceptance | the same for both arms: the suite is compiled on its own in the staged fixed revision, and each test method that fails there is left out by name |
| Measurement | `bin/measure-campaign3.sh`: the suite as written, run on the fix commit and on its parent with `bin/AgentTestRunner.java`; Java 11, Maven 3.9 offline for the production classes |

What the agent is given, what is enforced and what is recorded are in the
header of `bin/generate-postcutoff.sh`.

**The subjects.** 19 from Commons Lang, 8 from Commons CSV and 1 from Commons
CLI; fix commits from January to September 2026. 19 were mined for the matched
corpus, whose composition by fault type was fixed in advance to that of the
Defects4J sample, and 11 for the first corpus; two are in both. The union is
not matched on anything. The six subjects the earlier harness could not use
are in it: this one compiles the generated suite alone, so nothing depends on
the developer tests that are removed.

**A run is final.** It is made again in two cases only. One: a usage limit of
the plan ended it before it produced a result (the generator's `dead` state);
its record is kept under `cut-short/` and its tests are not used. Two: the
harness failed before the agent was started (export, build, javadoc); the fix
is a deviation and is recorded. A run that completes is not repeated, whatever
it produced: no test file, tests that do not compile, a suite that ends on its
turn or cost limit.

**No interim look.** Nothing is measured until every one of the 56 runs has a
status.

## What differs from the second campaign

The conditions are the second campaign's wherever the subjects allow: the same
model, CLI version, tools, limits, sandbox settings, flags and environment,
and the same prompts but for the sentences below. These things differ, because
the subjects are upstream commits built with Maven and tested with JUnit 5,
not Defects4J checkouts:

| | Second campaign | Third campaign |
|---|---|---|
| Code | Defects4J checkout of the fixed revision | `git archive` of the fix commit from an upstream clone; nothing of the repository's history |
| Removed from the tree `m` sees | the developer test files that hold the trigger tests, with a stub where the build needs the class; Defects4J's own files; changelogs | every test file the fix commit touches; changelogs, by the same list of names; what the build leaves except the compiled classes |
| Test framework | JUnit 3 or 4 | JUnit 5 (Jupiter 5.14) |
| How the agent's tests are run | JUnit's own runners, in the agent's script and at acceptance; Defects4J's `run_bug_detection.pl` at measurement | `bin/AgentTestRunner.java` on the JUnit Platform, in all three places |
| Class path of the agent's tests | Defects4J's test class path, the project's compiled developer tests included | the production classes and the project's test libraries; no developer test is compiled |
| A released copy of the project on that class path | not there | left out. Maven resolves one when a test library depends on the project. An older release beside the source would show what changed |
| Compiler level | `-source N -target N`, from the project's build | `--release 8`, from the project's build |
| A test that fails on the fixed revision | disabled by editing the source: `@Test` commented out, or the method renamed | left out by name at every run; the source stays as written. A parameterised method is left out whole |
| `lib/` in `s` | the compiled project and JUnit | the same, and the libraries the production classes refer to (Commons IO and Commons Codec, for Commons CSV) |
| Prompts | | the same, less "Some of these projects ship JUnit 3.8 only, where org.junit.Test and org.junit.Assert do not exist", and with the project's compiler level in place of `-source N` |
| Measured | detection, mutation score, coverage | detection |

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

1. **Generation.** `./bin/run-campaign3.sh`. It stops when the plan's usage
   reaches the generator's threshold and is run again after the limit resets.
2. **Audit.** `./bin/audit-campaign3.py data/campaign3 -v > data/campaign3/audit.txt`.
   Every flagged command is read with its result, and the runs with a
   violation (defined below) are listed in `data/campaign3/violations.txt`, one
   per line: arm, subject, reason. The `s3` runs in which the agent called
   `javac` itself are listed the same way in `data/campaign3/direct-javac.txt`.
   Both files are committed even if they are empty.
3. **Measurement.** `./bin/measure-campaign3.sh`.
4. **Analysis.** `./bin/analyze-campaign3.py > data/campaign3/analysis.txt`.

## Outcomes

- **Primary: real-fault detection.** A suite detects the fault when
  `bin/measure-campaign3.sh` gives it the verdict `Fail`: with the tests that
  failed on the fixed revision at acceptance left out, it passes on the fix
  commit and at least one of its tests fails on the parent commit. A test
  that is aborted because an assumption does not hold has not failed. A class
  whose set-up fails on the parent and not on the fix counts as a failing
  test. A suite that finishes on the fix commit and does not finish on the
  parent within 20 minutes is `Fail`, with the note `timeout`.
- **No verdict** (`Broken`): the suite does not compile against the parent
  commit, or does not pass on the fix commit when it is run again.
- **Secondary.** The share of test methods left out at acceptance; turns and
  list-price cost.

**paired** set: the subjects with a verdict, `Pass` or `Fail`, in both arms.

**Not measured: mutation score and coverage.** The second campaign's second
hypothesis, that detection falls further than mutation score, therefore has
no test here. Every suite is archived as written. If mutation score and line
coverage of these suites are measured later, it will be with PIT and its
default mutators, on the classes the fix modifies, with the suite as accepted;
the statistic and interval of the second campaign's H2 will be computed as
that protocol defines them, on the subjects with every measure in both arms,
and reported as a secondary result whatever they are. This corpus was not
sized for that test.

## Hypothesis, test and decision rule

In `bin/analyze-campaign3.py`, committed with this file.

**H1. The arms differ in detection.** Exact McNemar test, two-sided, on the
paired set, at α = 0.05. The difference in detection rate is reported with a
95% percentile interval from a bootstrap over subjects: 10,000 resamples of
the paired set with replacement, the two arms of a subject kept together,
Python's `random.Random(20261118)`.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 rejected with `m3` above `s3` | On faults that postdate the model's training data, and with the controls of the second campaign, the arms differ in detection in the same direction as on Defects4J. Recall of the benchmark does not account for the direction of the effect |
| H1 not rejected | This corpus does not show the difference. The write-up says so and gives the interval. It does not read this as the absence of an effect, nor as evidence that recall produced the effect on Defects4J |
| H1 rejected with `s3` above `m3` | The direction is reversed on this corpus, and the write-up reports that |

The Defects4J campaigns' figures are reported in every case.

**What this test can and cannot show.** The corpus is what had been mined, not
what a power calculation asked for. With 28 pairs, the test rejects with
probability about 0.9 if the shares of discordant pairs are those of the
second campaign (16 and 1 of 39) or of the earlier matched corpus (4 and 0 of
13), and about 0.35 if the gap is half the second campaign's. It needs 6
discordant pairs against 0, 8 against 1, or 10 against 2. It says nothing
reliable about the size of the effect, and a comparison of sizes with the
second campaign is descriptive.

## Exclusions

Fixed here, and none depends on a result.

- **No verdict.** A subject whose suite in either arm is `Broken`, or which
  has no suite because the run produced none that compiles or none with a
  test that passes on the fixed revision, is outside the paired set. It is
  listed with its reason.
- **Violation.** A run is left out of the primary analysis, as if it had
  produced no suite, when its transcript shows a command that did one of
  these: received data from the network; read a file outside the working copy
  that is not part of the operating system or the JDK; or, in `s3`, ran code
  from `lib/`, printed, unpacked or disassembled what is in it, or gave the
  compiler an option that executes code. A command the sandbox refused is not
  a violation. A command's own private `/tmp` is not outside the working copy
  in this sense. Violations are decided at step 2, before anything is
  measured.

  One case is settled here, because it came up in the second campaign and
  again in the pilot. An `s3` agent that calls `javac` itself, where its
  prompt says to compile through `compile.sh` and nothing else, breaks the
  prompt and commits no violation, unless it gives the compiler an option
  that executes code: the compiler's messages tell it nothing it would not
  learn by compiling its test class through `compile.sh`. Such runs stay in
  the primary analysis, are listed at step 2, and are left out in a
  sensitivity analysis.

A run in which the agent names the fix (the issue or pull request behind it,
the fix commit, or one of the subject's trigger tests by a name longer than
eight characters) is not excluded. On these subjects that is first of all a
coincidence of names. Such runs are counted, and analysed separately below.

## Sensitivity analyses

Reported with the primary analysis; none is confirmatory.

1. Runs with a violation included.
2. Intention to treat: every subject counts, runs with a violation as
   measured, and a subject without a suite or without a verdict counts as not
   detected.
3. Runs that name the fix left out.
4. Verdicts that are `Fail` by timeout read as `Pass`.
5. `s3` runs in which the agent called `javac` itself left out.

## Descriptive comparisons

None is a test of this protocol.

- **The two corpora apart**: the subjects mined for the matched corpus, and
  those mined for the first.
- **By project, and by fault type** for the subjects of the matched corpus.
- **The second campaign beside this one**: the difference in detection rate
  between the arms in each, and the difference between the two differences
  with a bootstrap interval, each campaign's subjects resampled on their own.
  The campaigns differ in more than the date of the faults (the table above,
  and the composition of the subjects), so this is not a measurement of what
  recall contributes.
- **The earlier runs on these subjects beside this campaign**, subject by
  subject, where an earlier verdict is valid.

## What this campaign does not control

- **That the fixes postdate the training data** rests on what was checked
  when the corpora were mined: commits from January 2026 on, and five issue
  identifiers from the earliest part of that window, which the model
  disclaimed. It is not checked again here.
- **Only the fix is new.** These are long-lived classes of libraries the model
  knows well. Their code as it stood before the fix, with the fault in it, may
  be in the training data. What the model cannot have seen is the fix and its
  tests.
- **The composition of the subjects.** The union of two corpora selected by
  different rules, three projects, 19 of 28 from Commons Lang. The fault
  types of the first corpus's subjects were never classified.
- **The implementation's own text.** The source under test and the developer
  tests that stay are not edited.
- **The specification is the fixed revision's.** The javadoc `s3` reads is
  generated from the repaired source and may document the repair.
- **One run per subject and arm.** Variation between runs is not estimated.
- **One measurement per suite.** A suite is run once on each revision. A test
  that draws random input can fail on one run and pass on the next, as two
  of the developers' own do.
- **One model, one agent.**
- **The prompts are not identical.** As in the second campaign, they differ in
  what an arm requires.
- **Enforcement in `s3` is not complete.** The JDK's launchers other than
  `javac`, `unzip`, `python` and `perl` are hidden; other general-purpose
  tools are not. The transcript audit is what covers the rest.
- **A runner of our own.** The projects' build does not run the suites. A test
  that depends on what Maven's test plugin sets up could behave differently;
  it would do so on both revisions.

## Checks made without the model

Before this protocol was fixed, the generator and the measurement were run on
all 28 subjects in both arms with no model call (`DRY=1`). The scripts given
to the agent were tried on a two-test class written by the generator, and the
developers' own test classes for the fix, renamed, stood in for the agent's
suite. Those classes are not self-contained, so in a dry run only, the
project's test sources are on the compiler's source path.

- Both revisions of all 28 subjects are exported and built offline.
- The agent's scripts compile and run the two-test class in every working
  copy.
- The stand-in suites are accepted in all 56 runs. One test of 2,179 is left
  out in each arm: a parameterised test whose arguments come from another
  test class, named in a string, which the compiler therefore never sees.
- Measured, all 56 stand-in suites are `Fail`. The tests that fail on the
  parent commit are exactly the trigger tests recorded when the subject was
  mined, with Maven, in 55 of the 56. The other is one of the two
  measurements of `commons-csv-f9e7d792`: two of its four trigger tests draw
  random input, and that time they passed on the parent.
- No working copy holds the issue's identifier, the pull request's number,
  the fix commit's hash or the words of its subject line. One search finds
  the names of trigger tests: `testEquals` and `testHashCode`, 49 times, in
  the other test classes of Commons Lang.

## Pilot

Four runs were made on 18 November 2026 on two fix commits that are not among
the subjects, on classes no subject has under test (`pilot/subjects.txt`):
`commons-lang-6c4269eb8` (`WordUtils`) and `commons-csv-ab3d7236`
(`CSVPrinter`), each in both arms. Their record is in `pilot/` and is not part
of any result.

- All four ended normally on `claude-sonnet-5` with CLI 2.1.316, in 8 to 24
  turns, for $1.61 at list prices.
- Each agent wrote its test class and nothing else. The implementation-visible
  agents compiled and ran their tests with `_tools/test.sh`, the
  specification-only agents compiled theirs with `compile.sh`. No command
  reaches for the network or for version control, or names a path outside the
  working copy. The harness refused one call. The sandbox denied one: a
  `python3` pointed at a page of the javadoc. One specification-only agent
  also called `javac` itself, with the options of `compile.sh` and
  `-Xlint:deprecation`. No run names the fix.
- Acceptance left out none of the 81 tests of `m3` and 7 of the 99 of `s3`.
  The suites went through the measurement as written, and all four are
  `Pass`. Those verdicts check the pipeline and nothing else; in the dry run,
  the developers' tests for the same two commits are `Fail`.

After the pilot, and before this protocol was fixed, the scripts changed in
these ways: the build log kept for each staged revision no longer holds
Maven's debug output or the banner it opens with, which names the machine's
kernel; each run's record states the Java and Maven versions; the audit lists
the `s3` commands that name `javac`, and the analysis has the sensitivity
analysis that goes with them. None changes what an agent is given. In the
pilot's own build logs the kernel's version is replaced by `[redacted]`. No
run on the subjects had been made.

## Deviations

None in the procedure.

**18 November 2026, at the audit, before any measurement: what was enforced.**
Reading the transcripts showed that the sandbox did less than this protocol
and the header of `bin/generate-postcutoff.sh` say. Nothing was changed for
it: the 56 runs were over, and the scripts stay as they ran. The account is in
`violations.txt`; in short:

- The CLI gives sandboxed commands a temporary directory, `/tmp/claude-1000`
  here. It is not private to a command, as `/tmp` itself is: it is the host's
  directory, readable and writable from inside, shared by every command of
  every run. During the campaign it also held the working files of the session
  that prepared the campaign, among them the generator's dry run, with the
  developers' tests for each fix. It has to be assumed that these were within
  reach of every agent in both arms. No agent reached for them: no command in
  the 56 transcripts lists that directory or names a path in it other than the
  files the same run had put there.
- The operating system's packages include released jars of Commons Lang
  (3.14.0) and Commons CLI (1.6.0) under `/usr/share/java`, which the sandbox
  does not hide. No agent opened one.
- The Read tool, confined to the working copy, also reads the outputs the CLI
  saves under the user's home when a command prints more than it passes on.
- `mvn` is on the agents' `PATH`. One agent ran it; it can do nothing without
  a local repository or the network.

**How the violation rule is applied to it.** As written. Five runs read a file
that is outside their working copy and not in a private `/tmp`: in four, a
file the run had itself written in the shared temporary directory, and in one
the CLI's saved copy of the output of the run's own command. Each of these
files came from what is in the run's own working copy, and no run obtained
anything from outside it. The rule has no exception for that, and none is made
after the fact: the five runs are listed in `violations.txt` and left out of
the primary analysis. They are in it again in the first sensitivity analysis.

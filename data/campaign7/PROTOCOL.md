# Seventh campaign: protocol

Fixed on 28 November 2026, before any run on the subjects, by the merge of the
pull request that adds it (#35), after the checks without the model and the
pilot below. The merge commit, with the scripts as they are in it, is the
reference. Anything done differently afterwards is a deviation and is listed at
the end, with its date and reason, before the step it affects.

## Why a seventh campaign

The sixth campaign showed the agent the faulty revision of 115 post-cutoff
faults and asked it to look for faults (`../../PREPRINT.md`, §3.14). Its suites
detect the fault on 7 of 113 subjects, 6.2%, with an interval from 2.7% to
10.6%. The agent shown the repair detects it on 27 of 113, 23.9%. On those
faults the regression evaluation setting credits an agent with about four
times what it finds when asked.

The write-up names what remains unrun (§4.6). One is the faulty revision on
Defects4J, "where recall could point the agent at the fix". Defects4J is the
benchmark the study's headline figure comes from. In the second campaign the
agent shown the repair detects 22 of 39 faults (§3.10). It is also a corpus the
model may know. A probe finds two of the 40 faults of the sample recalled with
their mechanism, Lang-13 and Gson-16, and two more recognised, Lang-43 and
Lang-8 (§3.7). In the first campaign, with the fixed source and the bug's
identity in front of it, the agent wrote out Lang-13's trigger test verbatim.
Shown the faulty code and asked to look, the agent could be led to the fault
by what it recalls.

This campaign asks the agent to look for faults in Defects4J's buggy versions
of the sample's 40 bugs, with the sixth campaign's request, word for word.
Beside it, the second campaign's implementation-visible arm is run a second
time, on the same bugs and under the same conditions.

Four questions follow:

1. Asked to look for faults in the code as Defects4J gives it, how often does
   the agent detect the fault?
2. Does it detect the fault as often as the agent shown the repair? That
   agent's rate is what the regression evaluation setting reports, here on the
   benchmark on which the setting is usually reported.
3. Is the gap as wide as on the post-cutoff faults? If the agent shown the
   faulty code comes much nearer the agent shown the repair here than in the
   sixth campaign, something about Defects4J narrows the gap: recall of the
   fix, or faults that are easier to find. The corpora differ in more than
   their date, so a description answers this question, not a test.
4. How far do verdicts vary between runs on Defects4J? `m7` is `m2`'s
   condition made again. The two Defects4J campaigns had one run per bug and
   arm, and the variation there was not measured (§5.4).

The other condition §4.6 names, a request that does not name the classes to
look in, is not part of this campaign.

The arms are separate conditions. They are never pooled with those of earlier
campaigns.

## What is fixed

| | |
|---|---|
| Subjects | the 40 bugs of the sample (`../sample.txt`), in a new order (`subjects.txt`) |
| Arms | `f7`: implementation-visible on Defects4J's buggy version of the bug (`<id>b`), asked to look for faults, as `f6` was. `m7`: implementation-visible on Defects4J's fixed version (`<id>f`), the second campaign's `m2` made a second time. Both are built by `bin/generate-campaign7.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per bug and arm, 80 in all |
| Order | bugs in the order of `subjects.txt`, a shuffle with `random.Random(20261127)`; both arms of a bug before the next bug; `f7` first for the 1st, 3rd, 5th … bug and `m7` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign7.sh`) |
| Prompt | `m7`: `m2`'s, word for word. `f7`: `m2`'s with its last sentence replaced by `f6`'s paragraph, word for word. Neither says which version the agent has |
| Working copy | `m2`'s, made from the arm's version as the header of `bin/generate-suites.sh` describes it: Defects4J's checkout without its history, without the developer test files that hold the trigger tests (a stub replaces one where the build needs the class), without Defects4J's own files and backups, and without changelogs, release notes and upgrade guides. `_tools/` is added, with the jars the tests need and `test.sh`. The same files are removed in both arms |
| Sandbox | `bin/agent-sandbox.py settings <work> m <jdk_bin>` in both arms, since both see the implementation. Each run has a temporary directory of its own, named in `CLAUDE_CODE_TMPDIR` |
| Acceptance | the sixth campaign's, on the arm's own version. The suite is compiled on its own in the staged checkout of that version, and each test method that fails there is left out by name. In `f7` the tests left out are its findings, and `f6`'s two rules for a failed run apply |
| Measurement | `bin/measure-campaign7.sh`: the sixth campaign's, on Defects4J's two versions of the bug, each staged as for the agent. Java 11; Defects4J `v3.0.1-7-g8c16da82` checks out and compiles the versions |
| Runner | `bin/AgentTestRunner4.java`, for acceptance and measurement: the report of `bin/AgentTestRunner.java`, on JUnit 4 (below). The agent's `test.sh` is `m2`'s |
| Mutation score and line coverage | `bin/mutation-campaign7.sh`: Major and Cobertura through Defects4J's `run_mutation.pl` and `run_coverage.pl`, as in the second campaign. They measure the classes the fix modifies, with the suite as accepted, on the version it was accepted on. The developers' test classes the suite uses are added to its archive, and the archive is run once before Defects4J runs it, to check that it runs the tests acceptance kept. Mutation score is counted from Major's `kill.csv`, as `bin/merge-agent-metrics.py` counts it. Gson-14 and Gson-16 are kept out of the mutation step. Each step is stopped after two hours on a suite, which then has no figure for it |

**The scripts.** Each is derived from an earlier campaign's script, which
stays as it ran:

- `bin/generate-campaign7.sh` is `bin/generate-campaign6.sh`, with the second
  campaign's staging and working copy (`bin/generate-suites.sh`) in place of
  the export from a mirror and Maven's build. It takes `m2`'s prompt and
  `test.sh`, and `bin/AgentTestRunner4.java` at acceptance;
- `bin/run-campaign7.sh`, `bin/audit-campaign7.py` and
  `bin/analyze-campaign7.py` are the sixth campaign's, with the arms, the seed
  and the paths, the count of runs that name the bug, and the comparisons
  below;
- `bin/subjects-campaign7.py` writes `subjects.txt` by the rule in the table,
  and with `--check` confirms it;
- `bin/measure-campaign7.sh` is `bin/measure-campaign6.sh`, on Defects4J's two
  versions and with `bin/AgentTestRunner4.java`;
- `bin/mutation-campaign7.sh` is the mutation and coverage steps of
  `bin/analyze-agent-suites.sh`, run on the version each suite was accepted
  on, with the additions to the archive and the check run described below;
- `bin/disable-tests-campaign7.py` is new. It disables in the source the tests
  acceptance left out, each found by its key;
- `bin/AgentTestRunner4.java` is new;
- `bin/campaign7-lib.sh` is new. It holds what the generator and the
  measurement share: the staging of a version (`stage_bug`), as
  `bin/generate-suites.sh` staged `m2`'s, and the build of the runner. It also
  holds a check of the environment. The generator, the measurement and the
  mutation step refuse to start unless `java` and `javac` are Java 11 and
  Defects4J is `v3.0.1-7-g8c16da82`, and the generator, outside a dry run,
  unless the CLI is 2.1.316.

`bin/agent-sandbox.py` and `bin/merge-agent-metrics.py` are used unchanged.
So are the helpers of
`bin/campaign3-lib.sh` that do not build with Maven: `c3_env`,
`excluded_from`, `count_methods`, and its limit of 20 minutes on a run.

**Why the second campaign's working copy and prompt.** The sample's bugs are
Defects4J checkouts, not commits in a mirror, and Defects4J's own files name
the bug and its trigger tests. The second campaign's generator removes them,
and `m2` is the arm whose condition `m7` repeats. `m2`'s prompt differs from
`m4`'s in two sentences only:

- it adds "Some of these projects ship JUnit 3.8 only, where org.junit.Test
  and org.junit.Assert do not exist.";
- it gives the compiler's level as `-source <level>`, read from the project's
  properties, where `m4`'s gives Maven's options.

Both prompts end with the sentence that `f6`'s paragraph replaces, "Finish when
all your tests pass.", so `f7`'s request replaces the same words.

**The prompt of `f7`.** `m2`'s prompt ends: "Compile and run your tests with
./_tools/test.sh, which compiles every *AgentTest.java under <tests>/ and runs
it. Finish when all your tests pass." In `f7` its last sentence is replaced by
the paragraph the sixth campaign gave `f6`:

> The classes may contain bugs, and your tests are meant to find them. Write
> each test for the behaviour the class should have, as its documentation and
> the rest of the project describe it, not for whatever the code happens to
> do. When a test fails, decide whether the test or the code is wrong: correct
> a wrong test, and leave a test that fails because the code is wrong as it
> is. Finish when every test that still fails is one you believe shows a bug,
> and name those tests in your final message, with the bug each one shows.

The rest of the prompt is `m2`'s, including "Do not modify or create any file
other than the test classes named above". The request is the same, word for
word, so that the sixth and seventh campaigns differ in the corpus and not in
what the agent is asked. It does not say that there is a bug, where, or which
version the agent has.

**The two versions.** Defects4J makes a bug's buggy version from its fixed
one (`framework/core/Project.pm`, `checkout_vid`). It checks out the fix
commit, removes the tests that fail there, and applies the bug's source patch,
which takes the repair back out. The two versions therefore have the same tests
and differ only in the hunks of that patch. Unlike the parent of a fix commit,
the buggy version is not a revision that stood in the project's history: its
other code is the fixed version's. The two arms' working copies hold the same
files and differ only in those hunks.

**The trigger tests.** The buggy version holds the fixed version's tests,
among them the trigger tests, which fail there. The files that hold them are
removed in both arms, as `m2`'s generator removes them. In the second campaign
six Lang bugs needed a stub in their place: Lang-43, 52, 56, 62, 63 and 65. On
these 40 bugs, those files include every test file of the bug's test patch
(`framework/projects/<P>/patches/<id>.test.patch`, checked on 27 November
2026). The sixth campaign's rule, every test file the fix touches, would
remove no other file. By Defects4J's construction, the tests that fail on the
buggy version are the trigger tests. So none of the developers' tests that
stay fails there, and the agent cannot find the fault by running them.

**The runner.** The sixth campaign's runner, `bin/AgentTestRunner.java`, runs
tests on the JUnit Platform. The sample's class paths have JUnit 4 and no
JUnit Platform: every `m2` run found JUnit 4's `JUnitCore` and used it. The
platform's engine for JUnit 4 is not in the machine's local Maven repository,
so the platform cannot run these tests offline. `bin/AgentTestRunner4.java`
runs each class named on its own with `JUnitCore`. It writes the report
`bin/AgentTestRunner.java` writes and takes the same `--report` and
`--exclude`, with the same exit status. Every parameter set of a parameterised
method belongs to its method. A class that fails as a whole, as when it cannot
be loaded or has no runnable method, is reported as a failed class.

**Acceptance in `f7`.** As in `f6`, the suite is run in the staged version.
Each test method that fails is left out by name, and the rest is run again
until it passes, in at most five rounds. Two of `m4`'s rules for a failed run
do not apply in `f7`, because there a failing test is what the agent was asked
for:

- **A suite in which every test fails on the buggy version is kept.** It has
  no certification verdict and no mutation score. Its tests are measured for
  detection like any other left-out tests.
- **A suite that does not finish on the buggy version** is run again one class
  at a time, with the same limit. A run does not finish when it lasts more than
  20 minutes, or when it ends the runner without its report. A class that does
  not finish is left out as a whole, as a class that fails as a whole is.
  Acceptance then goes on as above. If the rest of the suite, run together
  again, still does not finish, the run has no suite.

In `m7`, acceptance is `m4`'s, as in `m6`. There, a suite that ends the runner
without its report fails with nothing more to leave out, and the run has no
suite. `m2`'s own acceptance compiled the suite with Defects4J's build and disabled
failing tests in the source. It disabled none of the 1,453 tests its suites
held.

**The suite as accepted, for mutation and coverage.** It is packaged as the
second campaign packaged its suites, as an archive of the test classes that
Defects4J's scripts read. The archive is named for the version the suite was
accepted on: `<P>-<id>b-…` in `f7` and `<P>-<id>f-…` in `m7`.

- **The tests left out at acceptance are disabled in the source**, as the
  second campaign disabled them: the `@Test` annotation is put in a comment,
  and a JUnit 3 test is renamed. `bin/disable-tests-campaign7.py` does it,
  finding each test by its key, in its own class, wherever its annotation is
  written. `bin/prune-failing-tests.py`, which the second campaign used, finds
  a method by its name alone and looks for `@Test` on the lines above it.
  Given `@Test public void b()` on one line, it disabled the method before
  `b`, and kept `b`. A test that a class inherits can only be disabled where
  it is declared, which takes it out of every class that inherits it. The
  check run below says whether that is what acceptance left out.
- **A class left out as a whole, or every test of which was left out**, is
  left out of the archive, since JUnit fails a class with no test left. A
  nested class in that case is marked `@Ignore`. An `f7` suite whose every
  test was left out has no figure.
- **The developers' test classes the suite uses are added to the archive.**
  Defects4J compiles an archive on its own, without the developers' tests,
  while acceptance compiled the suite with those that stay in the working
  copy. The suite is compiled again in the staged version, with those tests'
  sources on the compiler's source path. Every file the compiler reads from
  there is added to the archive: the classes the suite uses, and those they
  use in turn. Defects4J runs only the suite's own classes, the `*AgentTest`
  ones.
- **The archive is run once before Defects4J runs it**, with
  `bin/AgentTestRunner4.java`, in the staged version, on the class path
  Defects4J gives it. The test methods it runs must be those acceptance kept,
  by key. If they are not, or the archive does not compile, the suite has no
  figure, and the note says why.
- **A kept test that fails in Defects4J's build** makes `run_coverage.pl` call
  the suite broken. Major would still run it and count what the failing test
  does not cover. Such a suite has no figure from either step, and the note
  gives the failure. One case is fixed in advance, as in the second campaign.
  If a suite cannot be loaded on a Cli version for the reason five EvoSuite
  suites could not (`NoClassDefFoundError: org/hamcrest/SelfDescribing`), it
  is measured through the one-line correction of Defects4J that
  `bin/remeasure-cli-evosuite.sh` makes, and the row is marked.
- **Coverage and mutation are each stopped after two hours on a suite**, which
  then has no figure for that step. Major's compiler rejects the class that
  Gson-14 and Gson-16 modify, so their suites are measured for coverage only,
  as in the second campaign.

**The subjects.** These are the 40 bugs of the sample. Their classes under
test, trigger tests and issue are Defects4J's (`classes.modified`,
`tests.trigger`, `active-bugs.csv`), read when each version is staged, as the
second campaign read them. The first campaign's arms, EvoSuite, `m2` and `s2`
have run on these bugs, and their results are known. That is why `m7` is made
again and not replaced by `m2`.

**A run is final.** A run is made again in two cases only. The first is that a
usage limit of the plan ended it before it produced a result. Its record is
then kept under `cut-short/`, and its tests are not used. The second is that
the harness failed before the agent was started, at checkout, compilation or
staging; the fix is then a deviation and is recorded. A run that completes is
not repeated, whatever it produced.

**No interim look.** Nothing is measured until every one of the 80 runs has a
status.

## What differs from the second and sixth campaigns

| | Second campaign | Sixth campaign | Seventh campaign |
|---|---|---|---|
| Subjects | the sample's 40 Defects4J bugs | 115 post-cutoff faults | the sample's 40 Defects4J bugs |
| Arms | `m2`, the fixed version; `s2`, specification only | `f6`, the parent of the fix commit, asked to look for faults; `m6`, the fix commit | `f7`, Defects4J's buggy version, asked to look for faults; `m7`, the fixed version |
| The faulty code | — | the parent of the fix commit, as it stood in the project | the fixed version with the bug's source patch applied, which takes the repair back out |
| Working copy | Defects4J's checkout, cleaned of the benchmark's files | the exported tree, without the test files the fix touches | `m2`'s, from the arm's version |
| Prompt | `m2`'s and `s2`'s | `m4`'s; in `f6`, its last sentence replaced | `m2`'s; in `f7`, its last sentence replaced by `f6`'s paragraph |
| Sandbox | its own; the temporary directory was the host's | `bin/agent-sandbox.py`; a temporary directory per run | the sixth campaign's |
| Acceptance | on the fixed version; failing tests disabled in the source | on the arm's revision; failing tests left out by name; `f6`'s two rules | the sixth campaign's, on the arm's version |
| Runner at acceptance and measurement | `JUnitCore` at acceptance; Defects4J's scripts measure | `bin/AgentTestRunner.java`, on the JUnit Platform | `bin/AgentTestRunner4.java`, on JUnit 4 |
| Detection measured by | `run_bug_detection.pl` | the runner | the runner |
| Mutation score | Major through Defects4J | PIT | Major through Defects4J |
| Order | the sample's | `random.Random(20261125)` | `random.Random(20261127)` |

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

0. **Before the pilot, and again before the campaign.** Two checks are run
   with the CLI binary of the runs, `./bin/agent-sandbox.py probe` and
   `./bin/probe-saved-copies.py`. Every check of both must pass.
1. **Generation.** `./bin/run-campaign7.sh`. It stops when the plan's usage
   reaches the generator's threshold, and is run again after the limit resets.
2. **Audit.** `./bin/audit-campaign7.py data/campaign7 -v > data/campaign7/audit.txt`.
   Every flagged command is read with its result. The runs with a violation,
   as defined below, are listed in `data/campaign7/violations.txt`. The
   audit's output also lists the runs that name the bug, as defined under
   "Exclusions". The closing message of every `f7` run is read
   (`./bin/audit-campaign7.py data/campaign7 --closing`, which prints under
   each message the tests acceptance left out). Each run whose message names
   a test as showing a bug has a line in `data/campaign7/closing-f7.txt`:
   `f7 <bug> fault|other <words>`, with the words that say what the bug is.
   `fault` means one of the bugs named is the fault, by the rule under
   "Outcomes", and `other` means none is. That is judged against the bug's
   source patch, before anything is measured. Both files are committed even if
   they are empty.
3. **Measurement.** `./bin/measure-campaign7.sh`.
4. **Mutation score and line coverage.** `./bin/mutation-campaign7.sh`.
5. **Analysis.** `./bin/analyze-campaign7.py > data/campaign7/analysis.txt`.

## Outcomes

- **Primary, `f7`: detection.** A test method of an `f7` suite detects the
  fault when all three of these hold:
  - it failed on the buggy version at acceptance;
  - it fails there again, or does not finish there, at measurement;
  - it passes on the fixed version.

  "Passes" means the runner reports it successful. A test aborted because an
  assumption does not hold, or ignored, has not passed. A test does not finish
  when its class, run on its own, lasts more than 20 minutes or ends the runner
  without its report. The methods of a class left out as a whole are counted
  one by one on the fixed version. A suite detects the fault, verdict `Fail`,
  when at least one of its tests does. Otherwise its verdict is `Pass`,
  including when acceptance left nothing out.
- **Primary, `m7`: detection**, as the fourth campaign defines it, on
  Defects4J's two versions. With the tests left out at acceptance left out,
  the suite has at least one test that fails on the buggy version, or it does
  not finish there.
- **No verdict** (`Broken`): the suite does not compile against the other
  version. In `m7` it is also `Broken` when it does not pass on its own version
  when it is run again. In `f7` that leaves its detection verdict as it is, and
  gives it no certification verdict.
- **Secondary.**
  - **Certification in `f7`**, as the fifth campaign defines it for `b5`. With
    the tests left out at acceptance left out, the suite passes on the buggy
    version, and at least one of its tests fails on the fixed version. A suite
    whose every test was left out has no certification verdict.
  - **False alarms in `f7`.** These are the tests that fail on the buggy
    version at acceptance and at measurement, and do not pass on the fixed
    version. They are counted per suite and in all. The share of `f7`'s
    failing tests that detect the fault is reported too.
  - **Closing messages in `f7`.** These are the runs whose message names a
    test as showing a bug, and those whose message names the fault. A message
    names the fault when one of the bugs it names is a behaviour that the
    bug's source patch changes, and what the message says the behaviour should
    be is what the fixed version makes it.
  - **In `m7`, the tests left out at acceptance**, run on the buggy version as
    in `m6`. Those that pass there expected the faulty behaviour.
  - **Mutation score and line coverage.** Mutation score is mutants detected
    (`FAIL`, `TIME` and `EXC` in Major's `kill.csv`) over mutants generated.
    Each is taken on the arm's own version and pooled over the suites of an
    arm.
  - **The rest**: the share of test methods left out at acceptance, the runs
    that name the bug, and turns and list-price cost.

The two detections are the same event, reached from opposite sides. It is a
test that fails on the buggy version and passes on the fixed one. `m7`'s tests
passed on the fixed version at acceptance and are run on the buggy one. `f7`'s
failed on the buggy version at acceptance and are run on the fixed one. Each
side is checked twice:

- `m7`'s tests pass on the fixed version at acceptance and again at
  measurement;
- `f7`'s fail on the buggy version at acceptance and again at measurement.

This is Defects4J's own definition of a test that detects a bug: it fails on
the buggy version and passes on the fixed one.

Sets:

- **paired**: the bugs with a detection verdict, `Pass` or `Fail`, in both
  arms;
- **complete**: the paired bugs that also have a mutation score and a
  line-coverage figure in both arms. Gson-14 and Gson-16 cannot be in it.

## Estimate, hypothesis, test and decision rule

All are in `bin/analyze-campaign7.py`, committed with this file. The order of
the bugs and every interval use Python's `random.Random(20261127)`.

**The detection rate when asked to look for faults.** This is `f7`'s share of
`Fail` among its bugs with a detection verdict. It comes with a 95% percentile
interval from 10,000 bootstrap resamples of those bugs. It is the estimate
question 1 asks for, and it is not a test.

**H1. Detection in `f7` and detection in `m7` differ.** This is tested with an
exact McNemar test, two-sided, on the paired set, at α = 0.05. The difference
between the two rates is reported with a 95% percentile interval from 10,000
bootstrap resamples of the paired set, the two arms of a bug kept together.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 not rejected | On Defects4J, asked to look for faults, the agent shown the faulty code detects the fault about as often as the agent shown the repair, which it did not do on the post-cutoff faults. Something about the benchmark narrows the gap, recall of the fix or faults that are easier to find, and the design cannot tell the two apart. The corpus comparison below says how far the gap narrows. The test cannot show that the two rates are equal; the interval says how far apart they could be |
| H1 rejected, `f7` below `m7` | On the benchmark the study's headline figure comes from too, the agent asked to look for faults detects the fault less often than the regression setting credits. The difference and its interval measure by how much, and the corpus comparison says whether the gap is as wide as on the post-cutoff faults |
| H1 rejected, `f7` above `m7` | Asked to look for faults on Defects4J, the agent detects more than the regression setting credits, and the write-up reports that |

The detection rate and its interval are reported in every case, with the false
alarms that came with it, and beside `f6`'s.

**The corpus (secondary, no decision rule).** `f7`'s detection rate is set
beside `f6`'s, and `m7`'s beside `m6`'s. So is the difference inside each
campaign, `f` − `m`, and the share of `m`'s detections that `f` also makes.
Each difference between the campaigns has a 95% interval from 10,000
bootstrap resamples, in which the subjects of each campaign are resampled on
their own. `f6` and `m6` are also weighted to the sample's fault types, as the
fourth campaign's analysis weighted `m4` and `s4`: `../fault-taxonomy.csv` as
classified, Csv-16 counted as STATE, API weighing nothing. The two corpora
differ in project, kind of fault, build and the way the faulty code is made,
as well as in date. So none of these figures can say how much of a difference
is recall, and none is a test of this protocol.

**Certification under the request (secondary, no decision rule).** `f7`'s
certification rate is given with its interval. No arm on Defects4J was shown
the buggy version without the request, so `b5`'s rate, on the post-cutoff
faults, is the only one it can be set beside, as a description.

**Mutation score (secondary, no decision rule).** For each arm on its own
version, the pooled mutation score and line coverage are reported. The
difference `f7` − `m7` is given with a 95% interval from 10,000 bootstrap
resamples of the complete set. The same figures are given for the suites that
detect in each arm. The suite as accepted leaves out `f7`'s findings, the tests
that fail on the buggy version, so they are not in its mutation score. A
suite's detection of the fault therefore cannot raise its score, and the
write-up says so wherever the two are set side by side.

**What this test can show.** Suppose the paired set has 39 bugs, as in the
second campaign, and that `m7` detects as `m2` did, on 22 of them. Suppose too
that `m7` also detects on 60% of the bugs where `f7` detects, as the fifth and
sixth campaigns assumed. `f7`'s count is `m7`'s times the share in the table,
rounded with Python's `round()`, and the 60% is taken as an expected count. H1
then has these chances of rejection, computed exactly. A simulation of 20,000
draws gives the same to two decimals, and so does a paired set of 40. The same
model gives the tables of the fifth and sixth campaigns.

| Detection in `f7` | Chance of rejection |
|---|---|
| the same as `m7`'s, 22 of 39 | 0.03 (the test's size) |
| three quarters of it, 16 | 0.21 |
| half of it, 11 | 0.65 |
| a quarter of it, 6 | 0.96 |

In the sixth campaign `f6` detected about a quarter as often as `m6`. H1 would
find a gap that wide in nearly every draw, and one where `f7` detects half as
often as `m7` in about two draws of three. When it is not rejected, the
interval is the result.

## Exclusions

These are fixed here, and none depends on a result.

- **No verdict.** A bug is outside the paired set, and is listed with its
  reason, when either arm has no detection verdict. That is the case when the
  arm's suite is `Broken`, or when the arm has no suite: the run produced none
  that compiles, or, in `m7`, none with a test that passes on its own version.
  In the second campaign both suites of Cli-21 were `Broken`: each calls a
  method the fix adds, and does not compile on the buggy version.
- **Violation.** A run is left out of the primary analysis, as if it had
  produced no suite, when its transcript shows a command that did either of
  these:
  - received data from the network;
  - read a file outside the working copy that is not part of the operating
    system or the JDK.

  A command the sandbox refused is not a violation. Three places do not count
  as outside the working copy: a command's own private `/tmp`; the run's own
  temporary directory; and the copy the CLI saves of the output of one of the
  run's own commands. Each holds only what the run itself wrote or printed.
  Violations are decided at step 2, before anything is measured.

A run in which the agent names the bug is not excluded. Naming the bug means
naming the benchmark, the bug's identifier in Defects4J, the issue behind it,
or one of its trigger tests by a name longer than eight characters. Gson's
issues are bare numbers and are not counted, as in the second campaign. A name
the working copy holds does not count; the search of the working copy finds
those.
Knowledge that comes from training data is part of what is measured, as in the
second campaign. Such runs are counted and analysed separately. In the sixth
campaign the working copy predated the fix, so a name of this kind could only
be a coincidence. Here the model may have seen the bug.

A run whose agent changed a file other than its test classes is not excluded
either. The suite is compiled and run against the staged version, which the
agent cannot reach. Such runs are counted at the audit.

## Sensitivity analyses

These are reported with the primary analysis; none is confirmatory.

1. Runs with a violation included.
2. Intention to treat. Every bug counts, runs with a violation as measured. A
   bug without a suite or without a verdict counts as not detecting.
3. Runs that name the bug left out.
4. Detection by timeout read as none. In `m7`, these are the verdicts that are
   `Fail` by timeout. In `f7`, they are the detections that rest only on tests
   whose class lasts more than 20 minutes on the buggy version. A run that
   ends without the runner's report is not a timeout. In `m7` a suite that
   ends that way on the buggy version is `Fail` with no failing test named,
   as in the fourth campaign, and an `f7` detection that rests on such a run
   is read the same way.
5. The four bugs that the memorisation probe found recalled or recognised
   left out: Lang-8, Lang-13, Lang-43 and Gson-16 (§3.7).
6. In `f7`, only the detecting tests that the closing message names: the
   detection the agent itself reports.

## Descriptive comparisons

None is a test of this protocol.

- **`m7` beside `m2`.** This is one condition, run twice on the same bugs,
  under two sandboxes and two acceptance runners. The comparison reports how
  many bugs are detected in neither run, in one and in both, with the
  agreement and Cohen's kappa. It is the variation between runs that §5.4
  says was not measured on Defects4J. The first campaign's M arm is set beside
  both. Its working copy held Defects4J's own files, so it is a different
  condition.
- **`f7` beside `s2`.** Neither arm is shown the repair. `f7` is shown the
  faulty code; `s2` was shown the fixed version's documentation.
- **Recall.** `f7` and `m7` on the four bugs the memorisation probe flagged,
  beside the other 36. The runs that name the bug, by arm. The `f7` closing
  messages that name the fault, and whether they cite an issue.
- **By project and by fault type.** On the post-cutoff faults, the agent
  shown the repair detects ten of the 35 omissions, and the agent shown the
  fault certifies none. Asked to look, the agent shown the faulty code detects
  3 of 34 omissions, and none of the 38 algorithm, API and state faults
  (§4.1). The sample has 22 omissions among its 40 bugs.
- **The conditions of §6's table.** `f7`'s detection is a row for the faulty
  implementation with a request to look for faults, on Defects4J.
- **The first to sixth campaigns**, as earlier campaigns have been set beside
  each other: the campaigns differ in more than the arms.

## What this campaign does not control

- **The request is one wording**, `f6`'s. A different wording could give a
  different rate.
- **The prompt names the classes the fix changes.** This holds in both arms,
  as in every campaign. For an agent looking for faults, it says where to look,
  down to the class.
- **The limits are the same in both arms**, 50 turns and $5. A search for
  faults may need more. The runs that reach the limit are reported.
- **A test can fail for a reason other than the fault**, in both directions. A
  detecting test could pass on the fixed version because of something else the
  source patch changes. A test that found the fault could also fail on the
  fixed version, if the repaired behaviour differs in detail from what the
  agent expected. The closing messages show the second case: a run that names
  the fault and does not detect it.
- **A suite that does not finish is split by class**, not by method, whether
  it ran out of time or ended without the runner's report. A method that would
  have passed on the buggy version can therefore count as detecting, if its
  class finishes on the fixed version.
- **What the closing message names is a claim.** It is read as what the agent
  says, and judged against the source patch by one reader, before anything is
  measured.
- **Training data.** Defects4J is public. The model may recall a bug or its
  fix, and the faulty code may cue that. It is part of what is measured, and
  the design cannot separate it from the kind of fault.
- **The buggy version is Defects4J's.** It is the fixed version with the fault
  put back, not code that stood in the project. The developers' tests that stay
  in the working copy are the fixed version's. None of them fails on the buggy
  version, but they were written with the fix in place.
- **The code's own text.** The source under test is not edited. In Lang-65 the
  buggy version keeps the comments that open and close the repair, "Fix for
  LANG-59", with the repair gone from between them (`patches/65.src.patch`).
- **One run per bug and arm.** `m7` beside `m2` estimates the variation for one
  condition only.
- **One model, one agent, 40 bugs from four projects.** The corpus comparison
  sets 40 bugs beside 113 post-cutoff subjects from three Commons projects.
- **The subjects have been used.** The first campaign's arms, EvoSuite, `m2`
  and `s2` ran on them, and their results are known. That is why `m7` is made
  again.
- **The Read tool** can open what is in the `tool-results` directory of the
  run's own session, and nothing else of the user's home. That is what
  `../sandbox/saved-copies.txt` found.
- **Three runners.** The agent runs its tests with JUnitCore's command line,
  through `test.sh`. Acceptance and the measurement of detection run them with
  `bin/AgentTestRunner4.java`, not with Defects4J's build. Mutation and
  coverage run them with Defects4J's build, as in the second campaign. A test
  whose outcome depends on the tests run before it can pass under one and fail
  under another. JUnit before 4.11 runs the methods of a JUnit 3 class in the
  order the JVM's reflection gives, and on Lang-34 that order differed between
  the runners (checks below).
- **Each suite is measured once.** A mutant can be killed by a timeout in one
  run and survive in another, and a test that reads the clock can cover other
  lines at another hour. In the checks, 4 of 56 suites gave other figures in a
  second run, by at most nine mutants.

## Checks made without the model

Made on 27 November 2026, before the protocol was fixed. The full chain was
run three times. The first run found the first of the three faults described
at the end of this section. A second was stopped when made-up exclusions found
the second, and a check of the new disabling on the second campaign's suites
found the third. The third run used the scripts as they are committed here,
and its record is the one given below. Apart from the sandbox's, the output
of the checks is kept outside the repository, where no agent can read it, and
is deleted before any run.

- **The sandbox.** Both checks of step 0 pass with CLI 2.1.316 and the settings
  both arms use (`probe.txt`, `saved-copies.txt`): `./bin/agent-sandbox.py
  probe` and `./bin/probe-saved-copies.py` each end "every check passed". The
  first gives what it gave for the sixth campaign, apart from the random names
  of the runs' temporary directories, and from one run's own directory holding
  4 entries when it started, where it held 3. The second is the sixth
  campaign's, byte for byte. Every request for a model's answer went to the
  probes' stand-in for the API.
- **The subjects.** `bin/subjects-campaign7.py --check` confirms the list.
  Both versions of every bug check out and compile under Defects4J.
- **The prompts.** `m7`'s prompt is the one `m2` was given, byte for byte, for
  each of the 40 bugs. `f7`'s differs from it in the last sentence only, which
  `f6`'s paragraph replaces word for word. The difference is the same for all
  40 bugs but for the name of the test directory.
- **The working copies.** Each is made from its version as staged, and the two
  staged versions of a bug hold the same files but for compiled classes in two
  bugs. In Gson-3 the fixed version has two anonymous classes more
  (`ConstructorConstructor$13` and `$14`). In Csv-16 the buggy version has an
  anonymous class (`CSVParser$2`) where the fixed one has a named one
  (`CSVParser$CSVRecordIterator`). On all 40 bugs, the files whose content
  differs are those the bug's source patch changes. The search of the working
  copies finds in `m7` what it found for `m2` on all 40 bugs, and in `f7` what
  it finds in `m7` on 39. On Lang-65 it finds the same three lines at other
  line numbers: the comments that open and close the repair and the issue's
  address. The repair between them is shorter in the buggy version.
- **The developers' tests that stay**, run with `defects4j test` on the
  staged buggy version of each bug. None fails on any of the 40.
- **The full chain.** The generator, the measurement, the mutation step and
  the analysis were run on all 40 bugs in both arms with no model call
  (`DRY=1`). The developers' test classes that hold the trigger tests, renamed,
  stood in for the agent's suites: 1,344 test methods in each arm. Every
  stand-in was accepted. In `m7` none of their tests was left out, and every
  stand-in is `Fail`. In `f7` acceptance left out the 93 trigger tests. At
  measurement all 93 failed again on the buggy version and passed on the fixed
  one: 93 detecting tests, no false alarm and no unstable test. So every `f7`
  stand-in detects the fault. None certifies it: 37 are `Pass`, and three have
  no certification verdict, since the stand-ins of Cli-21, Gson-6 and Gson-14
  hold trigger tests only.
- **The pilot's bugs**, Lang-61, Csv-11 and Cli-5, through the same chain.
  Every `m7` stand-in is `Fail`, and every `f7` stand-in detects the fault and
  none certifies it. Cli-5's `f7` stand-in holds trigger tests only.
- **The runner.** On the stand-ins, `bin/AgentTestRunner4.java` and JUnit's
  `JUnitCore`, called through its API, run the same tests and name the same
  failing tests, on both versions of all 40 bugs: the 93 trigger tests on the
  buggy versions, none on the fixed ones. A first comparison read the output
  of `JUnitCore`'s command line. It differed on two bugs, for reasons that are
  not the runner's. In Csv-15 a developer test prints through
  `CSVFormat.MYSQL.printer()`, which writes to `System.out`, and closes it, so
  the command line's report is lost. In Lang-34's fixed version,
  `testSelfInstanceVarReflectionObjectCycle` failed in 9 of 10 runs from the
  command line. It failed in none of 20 under each of the other two, and in
  none of 10 from the command line with JUnit 4.12 ahead of 4.7 on the class
  path. The test checks that `ToStringStyle`'s registry is empty, and whether
  it is depends on the tests run before it. Lang-34's class path has JUnit
  4.7, which runs the methods of a JUnit 3 class in the order the JVM's
  reflection gives. JUnit 4.11 sorts them.
- **Mutation.** Major gives a figure for every stand-in but those of Gson-14
  and Gson-16, which are measured for coverage only, and the three `f7`
  stand-ins whose every test was left out, which have none. That is 38 suites
  in `m7` and 36 in `f7`, and 40 and 37 have a line-coverage figure. The
  developers' test classes that the stand-ins of nine bugs use were added to
  their archives: Csv's `Utils`, `TokenMatchers` and `CSVFormatTest`, and
  Gson's `TestTypes`. On every suite measured, the check run found the tests
  acceptance kept, and none of them failed there. In Lang-8 one of the tests
  left out is inherited: `FastDateFormat_PrinterTest` runs the trigger test
  that `FastDatePrinterTest` declares. Disabled where it is declared, it is
  gone from both classes, as the check run confirmed. Of the pilot's suites,
  all but Cli-5's `f7` one have a figure.

  For the 31 bugs whose stand-ins use none of the developers' classes, the
  first and third runs give the same figures in all but four suites. Three
  moved by one mutant, which survived in one run and was killed in the other,
  twice by a timeout and once by a failing test. In Lang-8's `m7` suite, the
  trigger test formats the current time in the last time zone Java lists,
  `VST`. The first run made it just after midnight there, so it ran the line
  of `FastDatePrinter` that turns hour 0 into 12, and the third did not. The
  first run covered one line more and killed nine mutants more.

  The archive's rule was also tried on made-up suites:
  - **The exclusions the rule handles**, on Lang-13. These are `@Test` on the
    declaration's line and with arguments, a JUnit 3 test, and methods of
    nested classes, two levels down. They also include a nested class left
    out as a whole, one whose every test was left out, a top-level class of
    each kind, and classes with a `$` in their names. The check run found the
    tests kept, and Defects4J measured the suite.
  - **A kept test that the archive does not run.** The suite has no figure, and
    the note names the test.
  - **A kept test that passes in the staged version and fails in Defects4J's
    build.** The suite has no figure, and the note gives the failure.
  - **A Cli-10 suite that uses Hamcrest.** It does not load on Defects4J's own
    build. It was measured through the correction, with 26 of 117 mutants and
    55 of 106 lines.
  - **`bin/disable-tests-campaign7.py` on the second campaign's 80 suites**,
    each compiled and run in its staged fixed version. In each suite about 30%
    of the test methods were disabled, drawn with a fixed seed and at least
    one kept in every class: 816 of 2,852 in all. In all 80, the tests run
    afterwards were those run before, less those disabled.
- **The analysis**, on the output of the full chain, and on made-up verdicts
  that reach each outcome of the decision rule. On the full chain's output it
  gives both arms 40 of 40, and H1 is not rejected. For each of the 77 suites
  with a figure, the tests in the archive for Major are those the measurement
  ran. With `f7` detecting on 10 bugs of 40 and `m7` on 40, H1 is rejected with
  `f7` below `m7` (p = 1.9 × 10⁻⁹). With the two counts swapped, it is rejected
  with `f7` above. With 30 against 32 and discordant pairs both ways, it is not
  rejected (p = 0.82). A further set of made-up data held one bug `Broken`, one
  violation, two closing messages and a detection that rests on a timeout. It
  also held a run that names the bug: the second campaign's record of `m2` on
  Lang-36. Each exclusion and each sensitivity analysis changed the sets as
  this protocol says.

**What the checks changed.**

1. **The developers' test classes a suite uses.** Defects4J compiles an
   archive on its own, without the developers' tests. In the first run Major
   gave no figure in either arm for the 9 bugs whose stand-ins use one. They
   were Csv-3, Csv-4, Csv-7, Csv-10, Csv-14, Csv-15, Csv-16, Gson-3 and
   Gson-7. No suite of the second campaign used one: all 80 have a coverage
   figure. Two suites of the first campaign did, Cli-21's and Csv-3's, and
   were moved to `data/agent-suites-broken/` for it. The sources of those
   classes are now added to the archive, and Defects4J runs the `*AgentTest`
   classes only.
2. **Disabling the tests left out.** `bin/prune-failing-tests.py` was given
   made-up exclusions with `@Test` on the declaration's line. It disabled the
   method above the one named and kept that one. It also finds a method by its
   name alone, in whatever class of the file it comes first. In the second
   campaign it disabled no test. In `f7` every finding is a test it would have
   to disable. It stays as it is, part of the earlier campaigns' records, and
   `bin/disable-tests-campaign7.py` takes its place. The archive is now run
   once before Defects4J runs it. A suite that Defects4J calls broken has no
   figure: before, Major counted its failing test as one that covers nothing.
3. **A `$` in a class's own name.** The second campaign's agents named their
   test of Gson's `$Gson$Types` `$Gson$TypesAgentTest`. The scripts read a
   key's classes by cutting it at each `$`, and for that class they cut in the
   wrong place. They now match a class by its name and the names of the
   classes nested in it, as `bin/AgentTestRunner4.java` does. This applies in
   the disabling, in the archive, in the measurement's count of the tests left
   out, and in the staging's removal of trigger files. No trigger test of the
   40 bugs is in such a class.

Two more things were added while the checks were made, and neither changes a
figure. The generator, the measurement and the mutation step check their
environment: in the fifth campaign an update of the system's Java during the
runs made 111 runs fail. The analysis lists, for each paired bug outside the
complete set, why it is outside.

## Pilot

The pilot was six runs with the model, made on 27 November 2026 with the
user's agreement. It used the second campaign's three pilot bugs, which are
outside the sample: Lang-61 (`StrBuilder`), Csv-11 (`CSVParser`) and Cli-5
(`Util`), each in both arms. The generator was this campaign's, at commit
`13b534b`, after the checks above. Just before it, the output of those checks
was deleted, and both checks of step 0 were made again. Every check of both
passed. `saved-copies.txt` came out the same byte for byte, and the probe
differed from `probe.txt` only in temporary names and in the count of entries
when a run starts, 3 or 4. This campaign's scripts then audited the runs and
measured them and their mutation score. The record is in `pilot/`, with the
audit's output in `pilot/audit.txt`. It is not part of any result.

The three faults are these. In `StrBuilder.indexOf(String, int)`, the search
takes its bound from the buffer's capacity instead of the builder's length, so
it can find characters left beyond the length; the fixed version bounds it by
the length. In `CSVParser`, a header that the null string has made `null`
throws `NullPointerException` when the header map is built; the fixed version
tests for `null` first. `Util.stripLeadingHyphens(null)` throws
`NullPointerException`, where the fixed version returns `null`.

- **Runs.** All six ended normally on `claude-sonnet-5`, CLI 2.1.316. They
  ran from 23:06 to 23:18 UTC and cost $2.18 at list prices, $1.19 in `f7` and
  $0.99 in `m7`. The estimate had been about $3. The runs took 17 turns on
  Lang-61 and on Csv-11 in both arms, and 9 in `f7` and 8 in `m7` on Cli-5.
- **Commands.** Each agent read its working copy and wrote one test class and
  nothing else. It ran the class through `_tools/test.sh`. In `m7` on Lang-61
  the agent also ran JUnit's `JUnitCore` itself, on the jars in `_tools/lib`.
  The transcripts show no network command and no path outside the working
  copy. The sandbox denied nothing. In `f7` on Lang-61, the harness refused
  one call, a shell loop over the test files, because it needed an approval
  that nobody can give.
- **Audit.** It flagged no command. No run names the bug.
- **Closing messages.** The three `f7` messages, read before anything was
  measured:
  - On Lang-61, seven tests were named as showing bugs. One is the fault:
    `indexOf(String, int)` takes its bound from the buffer's capacity instead
    of the builder's length. The other six are about code that the source
    patch does not change. Two are `indexOf(char, int)` and `contains(char)`,
    which the message says search the capacity too. Two are
    `equals(StrBuilder)` and `equalsIgnoreCase(StrBuilder)` given `null`. Two
    are `appendFixedWidthPadLeft` and `appendFixedWidthPadRight` given a
    `null` object when there is no null text. The one line of
    `pilot/closing-f7.txt` reads `fault`.
  - On Csv-11 and Cli-5, no test was named as showing a bug. On Cli-5 the
    agent found that `stripLeadingHyphens(null)` throws
    `NullPointerException`, and wrote its test to expect it.
- **Temporary directory.** No command named the run's own temporary
  directory. At the end it held only the CLI's empty directories
  (`.tmp.tar.xz`).
- **Measurement.** In `f7` on Lang-61, acceptance left out the seven tests
  the agent named, of 160. All seven fail again on the buggy version. One, the
  test of `indexOf(String, int)`, passes on the fixed version and detects the
  fault. The other six fail there in the same way, so they are false alarms.
  Acceptance left out no test in the other five suites: 120 methods in `m7` on
  Lang-61, 35 and 33 on Csv-11, 16 and 15 on Cli-5. On Cli-5 the `f7` suite
  certifies the fault: its test that expects `NullPointerException` fails on
  the fixed version. The `m7` suite there detects the fault, with a test that
  expects `null`. No other suite detects or certifies it, and none is
  `Broken`. So each arm detects the fault once: `f7` on Lang-61 and `m7` on
  Cli-5. The verdicts check the pipeline and nothing else.
- **Mutation.** Major gave every suite a figure on its own version, and
  Cobertura a line coverage. The check run found in each archive the tests
  acceptance kept, and none of them failed there. In `f7` on Lang-61 the
  seven tests left out were disabled. Pooled, `f7` killed 48.2% of its mutants
  and covered 88.2% of the lines, and `m7` 51.8% and 92.3%. Each version has
  its own mutants: the fixed version has 6 more than the buggy one on
  Lang-61, 5 more on Csv-11 and 1 more on Cli-5, from the lines the source
  patch changes.
- **The records** were searched for the machine's name, its time zone, its
  operating system and details of the account, with the transcripts and
  archives unpacked. None of these is in them. The CLI's first event in each
  transcript lists the same built-in plugins and agents as in the sixth
  campaign's pilot, but for the first run, `f7` on Lang-61, whose list lacks
  the `web-fetch` agent. The first runs of the fifth and sixth campaigns lack
  it too. No run can call an agent: its tools are Bash, Read, Write, Edit,
  Glob and Grep.

Csv-11's class is one that three bugs of the sample have under test. The
pilot's record is under the user's home, which no agent can read.

## Deviations

None.

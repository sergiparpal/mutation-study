# Mutation Score Understates Oracle Provenance

### Agent-Generated Test Suites on Defects4J, With and Without the Implementation

*Draft.*

---

## Abstract

Evaluations of automated test generation on Defects4J generate a suite against
the **fixed** revision of a bug and then check it against the buggy one. For a
language-model agent this is not neutral: the agent reads the code it is
writing tests for, and on the fixed revision that code already contains the
repair.

We generate two suites per bug with the same agent and model, in two
conditions. In the implementation-visible arm the agent works in the project's
source tree; in the specification-only arm it works from generated javadoc and
a compiled jar, sees no source, and cannot execute its tests. We ran the
comparison twice over the same forty bugs from four Java projects. The first
campaign used Defects4J checkouts as they come. The second is the controlled
one: its working copies hold nothing of the benchmark's own, a sandbox
enforces what the first campaign only asked for, every message of every run is
kept and audited, and its hypotheses, tests and exclusions were fixed before
its first run.

In the second campaign, over the 39 bugs with a verdict in both arms,
real-fault detection falls from **56% to 18%** (exact McNemar, *p* = 2.8 ×
10⁻⁴). **The metrics ordinarily reported alongside detection move far less.**
On the 36 bugs that also have a mutation score in both arms, mutation score
falls from 54% to 39% and line coverage from 84% to 70%: detection loses 65%
of its value, mutation score 28% and coverage 16%. The gap between the first
two losses is 37 points, with a 95% bootstrap interval of 12 to 59. That is
the pre-specified test of the claim in the title.

Mutation score and coverage measure how much of a program a suite exercises
and how hard it checks what it exercises. Neither measures where the expected
values came from, and between these arms that is what detection follows. This
bears on how agent-written suites are evaluated, and on proposals to improve
them by feeding mutation results back to the generating agent — a loop that
optimises a quantity only loosely tied to the distinction.

The first campaign gave 72% against 14%, and what separates it from the second
is a finding of its own. A Defects4J checkout carries Defects4J's metadata,
which names the bug and its trigger tests. In eleven of that campaign's
twenty-six implementation-visible detections the suite or the agent's closing
report shows it knew one or the other. Without the metadata the arm detects
twenty of the same thirty-six bugs, every one of them among the twenty-six;
the campaigns differ in other respects too, so six is an upper bound on what
the metadata added. Nor did a prompt keep the specification-only agent away
from the compiled classes: in the second campaign 22 of 40 agents tried to
list or unpack a jar, and only the sandbox stopped them.

A third campaign took the second's conditions, under a protocol also fixed
beforehand, to 28 fix commits of three of the projects that postdate the
model's training data. Over the 23 subjects of its paired set the arms detect
**35% and 22%**: three faults are detected by the implementation-visible arm
alone and none by the other, and the test does not reject (*p* = 0.25; the
difference is 13 points, with an interval from 0 to 26). The effect is
therefore established on Defects4J and not on faults the model cannot have
seen. The gap is narrower there than on Defects4J, between corpora that
differ in more than the date of their faults, so the difference cannot be
assigned to recall and recall cannot be excluded as a part of the Defects4J
figure.

Three further observations. An agent writing from javadoc alone is wrong about
the code in one test out of fifteen, and catches seven faults, one of which the
implementation-visible arm misses. An EvoSuite baseline sits between the arms
on detection and on mutation score, 43% against 57% and 20% and 47% against
54% and 39%, and finds five faults the implementation-visible agent does not.
And a direct probe of what the model recalls with no code in context finds
benchmark identifiers unmemorised and at least two of the forty faults
recalled with their mechanism.

---

## 1. Introduction

Evaluations of automated test generation on Defects4J follow a standard
protocol: check out the **fixed** revision of a bug, generate a test suite
against it, then run that suite against the buggy revision and record whether
any test detects the fault. The protocol is natural — the fixed revision is the
one that compiles and passes its own tests — and it is what Defects4J's own
`run_bug_detection.pl` implements.

For search-based generators such as EvoSuite this is unproblematic. For a
language-model agent it is not. The agent *reads* the code it is generating
tests for, and on the fixed revision that code already contains the repair. A
test written to pin down current behaviour therefore detects the fault by
construction, without the agent having reasoned about correctness at all. The
measured detection rate conflates two things: the agent's ability to write
tests, and its ability to transcribe a repair it was shown.

This paper separates them. We generate two test suites per bug with the same
agent and the same model, under two conditions built to differ in one thing:
whether the agent can read the implementation. In the **implementation-visible**
arm it works in the project's source tree at the fixed revision. In the
**specification-only** arm it works in a sandbox containing generated javadoc
and a compiled jar, never sees source, and cannot execute its tests.

We made the comparison twice, on the same forty bugs. The first campaign ran
both arms on Defects4J checkouts as they come. An audit of it (§3.9) found that
such a checkout tells the agent more than the code does — Defects4J's own
files name the bug and the tests that expose it — and that nothing enforced
what the prompts forbade or recorded what the agents did. The second campaign
(§2.10, §3.10) closes those gaps and was run under a protocol committed before
its first run: hypotheses, tests, exclusions, and what the paper would say for
each outcome, including withdrawing its title's claim. The second campaign is
the result this paper rests on. The first is reported in full, as what a
standard Defects4J checkout produces. In both, the arms differ in more than
the one thing intended; §5.1 lists every difference we know of.

In the second campaign, over the 39 bugs with a verdict in both arms,
real-fault detection falls from **56% to 18%**. Sixteen faults are detected by
the implementation-visible arm alone and one by the specification-only arm
alone; an exact McNemar test gives *p* = 2.8 × 10⁻⁴.

**The usual metrics move, but far less.** On the 36 bugs with every
measurement in both arms, mutation score falls from 54% to 39% and line
coverage from 84% to 70%. Detection loses 65% of its value, mutation score 28%
and coverage 16%; the gap between the first two losses is 37 points, with a
95% interval of 12 to 59. The specification-only suites are weaker than the
implementation-visible ones on every count, but by nothing like a factor of
three. What differs most is where their expectations came from.

The first campaign had put the two arms at 72% and 14%. The difference between
the campaigns is itself informative, and §3.10 sets them side by side.

Both campaigns are on Defects4J, which is public and older than the model. A
third campaign (§2.11, §3.11) took the second's conditions to 28 faults fixed
upstream after the model's training data ends, under a protocol likewise
committed before its first run. There the arms detect 35% and 22% over 23
subjects. Every fault the specification-only arm detects the other detects
too, with three more, and the pre-specified test does not reject (*p* =
0.25). We report that as the limit of what this paper establishes: the effect
holds on Defects4J under control, and on faults the model cannot have seen
its direction is the same and its existence is not shown.

Contributions:

1. A controlled measurement of how much of an agent's apparent fault-detection
   ability on Defects4J depends on its reading the repaired implementation, on
   real faults from four real projects, with the conditions enforced and the
   analysis fixed in advance: about two thirds of it. That the regression
   evaluation setting flatters generated suites is not a new observation —
   Dinella et al. state it in 2022 and Huang et al. measure it for prompted
   models (§6) — but to our knowledge it has not been quantified for an agent
   that reads the codebase.
2. The finding, tested as a pre-specified hypothesis, that the metrics reported
   alongside detection register far less of the difference than detection
   does. This bears directly on how agent-written suites are currently
   evaluated and on proposals to use mutation feedback to improve them.
3. A bound on what a standard Defects4J checkout adds on top of the repaired
   code. The checkout ships the fix commit in its git history, with a subject
   line naming the fault, and Defects4J's own metadata: the bug identifier,
   the names of the trigger tests and backup copies of developer test classes.
   In the first campaign the agent used the metadata, and we report the
   evidence (§3.9). With all of it removed, in a campaign that differs from
   the first in other ways as well, the implementation-visible arm detects 20
   of the 36 bugs it had detected 26 of.
4. Evidence that an instruction is not a control. Told not to inspect the
   compiled classes, 22 of 40 specification-only agents tried, in runs where a
   sandbox stopped them and a transcript shows it. Studies that restrict an
   agent by prompt alone, as our first campaign did, cannot know.
5. A characterisation of what specification-only generation does catch: seven
   faults in the second campaign, one of them missed by the agent that reads
   the code, with one test in fifteen wrong about the code it describes.
6. An EvoSuite baseline over the same subjects, which shows the two approaches
   to be complementary rather than ordered: 10 faults are found only by the
   agent of the second campaign and 5 only by EvoSuite.
7. A direct probe of what the model recalls about each fault with no code in
   context, which finds at least two of forty recalled with their mechanism.
8. A replication under the same controls on 28 faults that postdate the
   model's training data, with its analysis fixed in advance and every
   transcript kept. Its test does not reject, and we report it as such: 35%
   against 22% over 23 subjects, a gap narrower than on Defects4J, in a
   corpus too small and too different from Defects4J to say why.

---

## 2. Method

The comparison was run twice on Defects4J. §2.1 to §2.9 describe the first
campaign and the measurements made around it. §2.10 describes the second,
which keeps the subjects, the two arms and the measurements, and changes what
the agent is given, what is enforced and what is recorded. §2.11 describes a
third campaign, which takes the second's conditions to faults that postdate
the model's training data.

### 2.1 Subjects

Defects4J v3.0.1 under Java 11, with `TZ=America/Los_Angeles` as the framework
requires. Each Defects4J bug provides a buggy and a fixed revision of a real
project, isolated from unrelated changes, together with the developer tests
that expose the fault (its *trigger tests*).

Forty bugs were drawn across four projects with deterministic random selection,
fixed before any data was collected and never revised afterwards:

```bash
defects4j bids -p Lang | shuf -n 12 --random-source=<(yes) | sed 's/^/Lang,/'
for p in Csv Gson Cli; do
  n=$([ $p = Cli ] && echo 8 || echo 10)
  defects4j bids -p $p | shuf -n $n --random-source=<(yes) | sed "s/^/$p,/"
done
```

Breakdown: Commons Lang 12, Commons CSV 10, Gson 10, Commons CLI 8. Two further
bugs (Lang-1, Lang-3) were examined during pilot work before the sample was
fixed and are excluded from all figures.

### 2.2 Design

Two arms over the same forty bugs, designed to differ in one variable: whether
the agent can read the implementation under test. §5.1 lists the ways in which
they differ beyond it.

**Implementation-visible arm ("M").** The agent works inside the checked-out
project at the *fixed* revision and reads the source freely. This is the
situation when a developer asks a coding agent for tests on existing code. It
also has everything else a Defects4J checkout contains: the project's other
tests, its build files and changelog, and Defects4J's own metadata (§2.4).

**Specification-only arm ("S").** The agent works in a sandbox containing:

```
api/          javadoc generated for the classes under test
lib/          the compiled project jar and JUnit
tests/        an empty directory to write into
compile.sh    compiles tests/ against lib/ at the project's own -source level
```

It never sees implementation source. It may compile its tests but **not run
them**: executing would let it observe behaviour and reconstruct the oracle
from the implementation by another route, which is the very thing the design
isolates.

The javadoc is generated from the fixed revision with `-package`, so it
documents protected and package-private members as well as public ones: some
classes under test are package-private, and a test in the same package sees
what a developer there would.

The short forms **M** and **S** are used throughout for the two arms of the
first campaign, and **M2** and **S2** for those of the second (§2.10).

Both arms are given the same target classes — those the fix modifies, from
`defects4j export -p classes.modified` — and the same two instructions on what
to assert: "Assert on returned values and on observable state, not merely that
no exception is thrown" and "Cover boundary and error cases, not just the happy
path". The rest of the two prompts differs. The M prompt adds "Test only the
public API" and tells the agent to match the style of the project's existing
tests. The S prompt requires self-contained test classes, states the project's
`-source` level, and adds "Base every expectation on the documented contract in
api/".

Each prompt also changed once during collection, to work round a tooling
failure. The M prompt's instructions for running the tests were rewritten for
JUnit 3 projects before the last seven suites; the `-source` constraint was
added to the S prompt, and to its `compile.sh`, after the first seven. The
scripts carry the final wording.

### 2.3 Agent configuration

| | |
|---|---|
| Harness | Claude Code 2.1.251, native install, linux-x64 |
| Model | `claude-sonnet-5` in both arms (40 bugs each), selected with `--model sonnet` |
| Turn cap | 50 in the S arm; 40, later raised to 50, in the M arm |
| Tools | `Read`, `Write`, `Bash` |
| Permission mode | `acceptEdits` |
| Output | `--output-format json`, one record per run: the closing message, cost and turn count, not a transcript |

The model is passed on the command line rather than inherited from local
configuration. The reasoning-effort level is not: the operator's configuration
set `effortLevel` to `xhigh`, no script overrides it, and the runs can be
assumed to have inherited it.

Six additional M-arm suites were produced with `claude-opus-5` before the run
switched models on exhausting quota. Nine Opus runs were started, on the first
nine bugs of the sample. Two ended in errors as the quota ran out and one,
Lang-52, produced a suite that failed on the fixed revision and was rejected.
The six that remain are six of the first seven bugs, not a random subset, and
are reported separately as an opportunistic observation rather than as a model
comparison. Their turn cap also differs (25).

`--bare`, the documented flag for skipping auto-discovery of project
configuration, could not be used: every run under it failed authentication
despite valid stored credentials. Runs were therefore made without it, from
clean checkouts under `/tmp` containing no project-level configuration.

### 2.4 Contamination controls

**Trigger tests are removed.** The whole developer test *file* containing each
trigger test is deleted, not merely the failing method: the remainder of the
class would reveal what is tested and how. Where deletion breaks compilation —
JUnit 3-era projects use aggregator classes that reference each test class by
name — the file is replaced by a stub carrying the same class name, a `suite()`
and one trivial passing test.

**Version-control history is removed.** A Defects4J checkout ships the
project's full git history, including the fix commit. For Lang-13 the log
subject reads `[LANG-788] SerializationUtils throws ClassNotFoundException when
cloning primitive classes`, and the per-bug `BUGGY_VERSION` / `FIXED_VERSION`
tags make `git diff` yield the patch directly. A pilot run without this control
produced a test citing "LANG-788" in a comment. `.git` is
therefore deleted before the agent starts, and the prompt forbids git and web
search.

*Measured effect of this leak on that pilot bug:* no change in mutation score
or fault detection, +6 covered lines. The history is a real channel but a weak
one when the agent can already read the fixed implementation; it matters far
more for the S arm, where the code is withheld.

We note this control because, as far as we are aware, it is not standard
practice in work that generates tests over Defects4J checkouts.

**What these two controls do not close.** They were meant to leave the agent
with the code and nothing that says what is wrong with it. An audit after the
runs found four things they leave behind in the M arm's working copy:

- `defects4j.build.properties`, written by the checkout, which gives the bug
  identifier and lists the trigger tests by class and method — for Lang-13,
  `d4j.tests.trigger=…SerializationUtilsTest::testPrimitiveTypeClassSerialization`.
  The working directory's name carries the identifier as well, and the
  `defects4j` command the prompt tells the agent to use will print the trigger
  tests on request.
- `<Test>.java.bak`. Defects4J backs up every test class from which it strips a
  flaky method. For five bugs (Lang-34, Lang-56, Lang-63, Csv-7, Csv-16) the
  class backed up is the trigger test's, so the complete developer test,
  trigger included, sits beside the file we deleted.
- The project's changelog, which at the fixed revision can describe the fix.
  For Lang-13, `src/site/changes/changes.xml` carries the same sentence as the
  commit subject quoted above, issue number included.
- The rest of the developer test suite, by design.

The agent used at least the first of these, and in one run the second; §3.9
gives the evidence. None of these files exists in the S arm's sandbox, though
the sandbox's directory name carries the bug identifier too. The second
campaign removes the first three and gives every working directory a random
name (§2.10).

**Training-data contamination is measured rather than eliminated.** Defects4J
has been public for years and may appear in the model's training data. The S
arm is a partial control — a model recalling a fault would plausibly recall it
without the source too — and §2.8 adds a direct probe of what the model
actually remembers. Results in §3.7.

### 2.5 Suite acceptance

**M arm.** A suite is accepted if it exists, compiles inside the project, and
passes in full on the fixed revision. All 40 Sonnet suites passed this filter;
one of the seven completed Opus suites did not (§2.3).

**S arm.** An agent writing from documentation alone gets some expectations
wrong, and discarding a whole suite over one wrong expectation would remove
most of the sample. Failing methods are therefore disabled individually — the
`@Test` annotation is commented out under JUnit 4, the method renamed under
JUnit 3 — and the remainder is kept. All 40 suites yielded a non-empty
remainder.

**Declared bias.** This filter uses the implementation as an oracle, so what
survives is precisely the subset that agrees with the code. It only removes,
never rewrites, and the surviving tests were written blind; but the selection
is biased and the effect is to make the S arm look *better* than it is, not
worse. The M arm reaches the same end state by a different route — its agent
runs the tests and revises them until the whole suite passes — so in both arms
every surviving test agrees with the fixed code. §5.1 returns to that
asymmetry.

### 2.6 Measurements

All three measurements use Defects4J's own analysis scripts, applied to each
packaged suite:

- **Real-fault detection** — `run_bug_detection.pl`. The suite is run against
  the fixed and the buggy revision. A suite is classified `Fail` when it passes
  in full on the fixed revision and at least one of its tests fails on the
  buggy one; that is, it detects the real fault. This is the primary outcome.
- **Mutation score** — `run_mutation.pl`, using the Major framework bundled
  with Defects4J, over the classes the fix modifies. Default operator set:
  AOR, LOR, SOR, COR, ROR, ORU, LVR, STD. The score is mutants killed over
  mutants generated, where killed means detected by an assertion failure, an
  exception or a timeout. It is computed from Major's per-mutant output and
  **not** from the table `run_mutation.pl` writes: that table's `mut_killed`
  column counts every mutant that is not left alive, including the ones no
  test executed at all, so a score read from it is inflated by the suite's
  share of uncovered mutants: here 13.6 points in the M arm and 25.6 in the S
  arm (§3.1).
- **Line and branch coverage** — `run_coverage.pl`.

Mutation score and coverage are pooled: mutants killed, or lines covered,
summed over the suites of an arm and divided by the corresponding total. A
per-suite mean gives different absolute figures, since it weights a
seven-mutant class like a 1,651-mutant one, and is quoted alongside wherever
the two disagree on an ordering.

`run_bug_detection.pl` has a third classification besides `Fail` and `Pass`:
`Broken`, for a suite that does not compile on one of the two revisions or has
a failing test on the revision it was generated for. A `Broken` suite was never
validly run against the buggy revision. It is left out of detection rates, not
counted as a miss (§2.9).

### 2.7 Search-based baseline

EvoSuite 1.1.0, as bundled with Defects4J v3.0.1 and invoked through
`gen_tests.pl` with the branch criterion and a total budget of 120 seconds per
bug, provides a non-agent point of comparison. Defects4J's wrapper halves that
budget between search and assertion generation and divides it among the target
classes, so the search itself ran for 60 seconds per class, and 30 for the one
two-class bug that produced a suite. The invocation was not scripted or logged;
the budget is reconstructed from the timestamps of the generated files, which
for most single-class bugs are 66 to 80 seconds apart.

Five of its suites, all on Commons Cli, could not be loaded by Defects4J's
detection and coverage harness: `NoClassDefFoundError:
org/hamcrest/SelfDescribing`, on both revisions. The fault is Defects4J's. Its
build file for Cli points the harness at a JUnit jar the framework does not
ship, so a generated JUnit 4 test has Hamcrest only where the project supplies
it, and these revisions ship JUnit 3.8. Those five suites were measured with
that one path corrected (`bin/remeasure-cli-evosuite.sh`). As a check, the
sixteen other Cli suites, from all three generators, were measured with the
correction too, and every one came out as it had without it. The mutation
harness ran the five as they were.

It is not a third arm of the manipulation: like the implementation-visible arm
it generates against the fixed revision and works from the repaired code. What
it lacks is any interpretation of that code — it asserts observed behaviour —
and, unlike that arm, anything else in the checkout (§3.9). The comparison
therefore separates, imperfectly, the contribution of the generator from the
contribution of the information available to it.

### 2.8 Memorisation probe

Defects4J has been public for years and may be present in the model's training
data, in which case detection could reflect recall rather than reasoning. The
obvious replication corpus does not settle this: GitBug-Java's 199 bugs come
from 2023 commit histories, selected in early 2024 because that postdated the
training cutoff of models available then. It no longer does.

We probe the model directly instead. For each of the 40 bugs, two questions are
put to the same model in a fresh session with no conversational context,
limited to a single turn so that no tool call can complete:

- **A, identifier cue.** *"What is Defects4J bug Lang-13? Describe the specific
  fault."* Answering requires having seen the benchmark itself.
- **B, location cue.** *"Was there a known bug in the class
  `org.apache.commons.lang3.SerializationUtils`? Describe the specific fault if
  you recall one."* This was meant to match what the implementation-visible
  agent had: project and class, not the bug identifier. It does not, because
  that agent had the identifier too (§2.4, §3.9). Where a fix touches more than
  one class (two bugs), only the first is named.

Each prompt offers an exact disclaimer phrase, so that declining is cheaper
than guessing. Answers are screened mechanically against identifiers taken from
the fix diff, and every answer flagged by that screen is then read against the
actual fault, because domain vocabulary alone produces false hits.

The screen compares an answer only with the diff of the bug the probe was
issued for. Several sampled bugs share a class and so received the same
question, which the screen cannot see. Every answer that did not disclaim was
therefore read afterwards against all the sampled faults in its class (§3.7).

### 2.9 Exclusions

Five bugs are excluded from some or all measurements, and three further suites
lack a detection verdict or a coverage figure. Cli-21 appears three times: it
is affected by three independent problems.

| Bug | Affected | Reason |
|---|---|---|
| Cli-21, Csv-3 | M, all measurements | Suite extended a test helper from the project's test tree, so it compiles in the working copy but not as a standalone archive. The M prompt did not ask for self-contained classes; the S prompt did (§2.2) |
| Gson-14, Gson-16 | all arms, all measurements | Major's mml compiler rejects the class name: `invalid scope: com.google.gson.internal.$Gson$Types`. EvoSuite's generated suite for the same class does not compile either — `illegal start of expression` on the `$` in the identifier. Two independent tools fail on this one class, which is why we treat it as a tooling limitation rather than a property of the bugs |
| Cli-15, Cli-21 | EvoSuite, all measurements | `gen_tests` produced no output and no log; both are `cli2` subjects, whose declared classpath references jars that the checkout never materialises |
| Csv-16 | EvoSuite, detection | `Broken`. The suite references a class the fix introduces and does not compile against the buggy revision |
| Cli-21 | S, detection | `Broken`. The suite calls an interface method the fix adds — the javadoc the agent wrote from is the fixed revision's — and does not compile against the buggy revision |
| Lang-34 | EvoSuite, coverage | A test fails under the coverage harness |

This leaves 36 M-arm suites and 38 S-arm suites with a mutation score and a
coverage figure, 37 of the latter with a detection verdict, and **36 bugs with
all three measurements in both arms**. All paired figures use those 36.
EvoSuite has 36 suites with a mutation score, 35 with a detection verdict and
35 with a coverage figure; §3.5 compares the three generators on the 34 bugs
where each has a detection verdict.

For Gson-14 and Gson-16 the specification-only suites did yield detection and
coverage figures before the two bugs were set aside (both suites were
classified `Pass`). Those figures are in the repository's history, not in its
final tables, and are omitted so that no arm total mixes suites with and
without a mutation score.

### 2.10 The second campaign

The second campaign repeats the comparison of §2.2 on the same forty bugs,
with the same model, measured by the same scripts. It was designed after the
audit of §3.9, to close what that audit found. Its protocol
(`data/campaign2/PROTOCOL.md`) was committed with the generation, audit and
analysis scripts before any run on the sample. Its arms, M2 and S2, are
separate conditions from M and S and are never pooled with them.

**What the agent is given.** The M2 working copy is the Defects4J checkout of
the fixed revision without `.git` and without the trigger tests' files, as
before. It is also without `defects4j.build.properties`, `.defects4j.config`,
Defects4J's `.bak` backups, the project's changelogs, release notes and
upgrade guides, and the marks Defects4J leaves in comments and build files.
The `defects4j` command is not available; a script in the working copy
compiles the agent's test classes and runs them. The S2 sandbox is that of
§2.2. Both sit in a directory with a random name. The source under test and
the developer tests that remain are not edited.

**What is enforced.** Every shell command runs in the harness's sandbox: no
network, a process namespace of its own, and of the machine's user and
temporary directories only the working copy, with one exception that the
settings were not meant to leave and that the third campaign's audit found
(§3.11): the directory the harness gives commands for temporary files is the
host's own and is shared between runs. No command of the second campaign
wrote or read a file there. The file tools are confined to the working copy.
The operator's settings, memory and plugins are not loaded. In S2, of the
JDK's launchers only `javac` can be read, so nothing in `lib/` can be run,
disassembled or unpacked with the JDK's tools, and `unzip`, `python` and
`perl` are hidden as well.

**What is recorded.** Every message of every run: the agent's text, each tool
call and each result. The first campaign kept the closing message only.

| | first campaign | second campaign |
|---|---|---|
| Harness | Claude Code 2.1.251 | Claude Code 2.1.316, run from its versioned binary |
| Model | `--model sonnet`, which resolved to `claude-sonnet-5` | `claude-sonnet-5`, by id; every run reports it |
| Reasoning effort | inherited from the operator's configuration (§2.3) | the harness's default; the operator's configuration is not read |
| Tools | `Read`, `Write`, `Bash` | `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash` |
| Turn cap | 40, later 50, in M; 50 in S | 50 in both |
| Prompts | share two instructions and differ otherwise (§2.2) | one text, apart from what an arm requires: where the classes and tests are, what stands in for the source and, in S2, to work from the documentation and not to run or inspect the compiled classes |
| Self-contained test classes | required of S only | required of both |
| Acceptance | an M suite must pass whole; failing S tests are disabled one by one (§2.5) | failing tests are disabled one by one in both arms |
| Order of runs | the M arm, then the S arm | bug by bug, both arms of a bug before the next, the first arm alternating, one agent at a time |

**The analysis was fixed in advance.** Two hypotheses, tested in sequence.

- *H1, the arms differ in detection.* Exact McNemar test, two-sided, at
  α = 0.05, on the *paired set*: the bugs with a verdict, `Pass` or `Fail`, in
  both arms.
- *H2, detection falls further than mutation score does.* This is the claim of
  the title. It is assessed only if H1 is rejected with M2 above S2. For a
  quantity *X*, fall(*X*) = 1 − *X*(S2) / *X*(M2). The statistic is
  fall(detection) − fall(mutation score), with mutation score pooled, on the
  *complete set*: the paired bugs that also have a mutation score and a
  coverage figure in both arms. H2 is supported if the lower bound of the
  statistic's 95% interval is above zero. The interval is a percentile
  bootstrap over bugs, 10,000 resamples with a fixed seed, the two arms of a
  bug kept together.

The protocol also fixes what this paper says for each outcome. Had H1 held and
H2 not, the title's claim was to be withdrawn; had H1 not held, the paper was
to report that the first campaign's effect did not survive control.

**Exclusions were fixed in advance.** A bug whose suite in either arm is
`Broken`, or absent, has no verdict and is outside the paired set. A run whose
transcript shows a *violation* is left out as if it had produced no suite. A
violation is a command that received data from the network; that read a file
outside the working copy other than the operating system's and the JDK's; or
that, in S2, ran code from `lib/`, printed, unpacked or disassembled what is
in it, or gave the compiler an option that executes code. A command the
sandbox refused is not a violation. Violations are decided from the
transcripts before anything is measured. A run in which the agent shows that
it knows the bug — it names the benchmark, the issue behind the bug or one of
its trigger tests — is not excluded, since recall from training data is part
of what is measured. Such runs are counted, and the analysis is repeated
without them.

**Procedure.** Generation, transcript audit, measurement, analysis, each
committed to the repository before the next began, so that its history shows
the order. A run is final: it is made again only if a usage limit cut it short
or the harness failed before the agent started. Three runs on Defects4J bugs
outside the sample exercised the harness beforehand, so that no result on the
sample was seen before the protocol was fixed.

**What the second campaign does not control.** Training data: Defects4J is
public, and the source itself may cue recall. The implementation's own text:
in one bug, Lang-65, the repaired code delimits its repair with comments that
cite the issue. The specification, which is the fixed revision's and may
document the repair. Variation between runs: there is one per bug and arm.
The prompts are not identical. Enforcement in S2 is not complete, because
general-purpose tools other than those named remain; the transcript audit is
what covers them. And the subjects are the first campaign's forty bugs, so the
campaign tests whether the effect survives control on new runs, not whether it
holds on new faults.

### 2.11 The third campaign

The third campaign makes the comparison on faults the model cannot have seen,
under the second campaign's conditions. Its subjects are the 28 fix commits
validated for the two post-cutoff corpora of §3.8, each once: 19 from Commons
Lang, 8 from Commons CSV and 1 from Commons CLI, fixed upstream between
January and September 2026. Nineteen were mined for the corpus matched on
fault type and eleven for the first corpus; two are in both. The runs of §3.8
on these subjects had the fix commit within the agent's reach, enforced
nothing, kept no transcript and no test, and left one arm of one corpus
without a verdict. The protocol (`data/campaign3/PROTOCOL.md`) was committed
with its scripts before any run on the subjects, after four pilot runs on two
fix commits outside them. Its arms, M3 and S3, are separate conditions, pooled
neither with the runs of §3.8 nor with the Defects4J campaigns.

**What is kept from the second campaign.** The model, the harness version,
the tools, the limits of 50 turns and $5 a run, the sandbox settings, the
order of the runs and the rule of acceptance. The prompts are the same but
for a sentence about JUnit 3 that these projects do not need and the
compiler level. Every message of every run is recorded.

**What differs**, because the subjects are upstream commits built with Maven
and tested with JUnit 5, not Defects4J checkouts:

- *The code.* The working copy is an export of the fix commit with nothing of
  the repository's history. From the tree M3 sees, every test file the fix
  commit touches is removed, and so are the changelogs.
- *How tests are run.* A runner of our own on the JUnit Platform
  (`bin/AgentTestRunner.java`) runs the agent's tests in the M3 agent's
  script, at acceptance and at measurement. The suite is compiled on its own
  against the production classes and the project's test libraries. No
  developer test is compiled, so the six subjects that the harness of §3.8
  could not use are in the sample.
- *A released copy of the project.* Maven puts one on the test class path
  when a test library depends on the project. Beside the source, an older
  release shows what has changed since, and it is dropped from every class
  path.
- *A test that fails on the fixed revision* is left out by name at every run,
  and the source stays as the agent wrote it. The earlier runs edited the
  source, which a parameterised test defeats (§3.8).
- *What is measured.* Detection only: a suite detects the fault when, with
  the tests that failed at acceptance left out, it passes on the fix commit
  and at least one of its tests fails on the parent commit. There is no
  mutation score, so the second hypothesis of §2.10 has no test here.

**The analysis was fixed in advance.** One hypothesis, that the arms differ in
detection: the exact McNemar test, two-sided, at α = 0.05, on the subjects
with a verdict in both arms, and the difference in detection rate with a 95%
percentile bootstrap interval over subjects. The protocol fixes what this
paper says for each outcome. Rejected with M3 above S3: on faults that
postdate the model's training data the arms differ in the direction they do
on Defects4J, and recall of the benchmark does not account for that
direction. Not rejected: this corpus does not show the difference, which is
read neither as the absence of an effect nor as evidence that recall produced
the effect on Defects4J. Rejected with S3 above M3: the direction is
reversed, and the paper reports it.

**What the test can show.** The corpus is what had been mined, not what a
power calculation asked for. With 28 pairs the test rejects with probability
about 0.9 if the shares of discordant pairs are those of the second campaign,
and about 0.35 if the gap is half as wide. It needs six discordant pairs
against none, eight against one, or ten against two. It says nothing reliable
about the size of the effect.

**Exclusions** are those of §2.10, by the same definition of a violation. One
case is settled beforehand, because it came up in the second campaign and in
the pilot: an S3 agent that calls `javac` itself, where its prompt says to
compile through the script it is given, breaks the prompt and commits no
violation unless it gives the compiler an option that executes code. Such
runs are listed at the audit and left out in a sensitivity analysis. A run
that names the fix, its issue or one of its trigger tests is counted and not
excluded; on these subjects that is first of all a coincidence of names.

**What the third campaign does not control.** That the fixes postdate the
training data rests on what was checked when the corpora were mined. Only the
fix is new: these are long-lived classes of libraries the model knows well,
and their code as it stood before the fix, fault included, may be in the
training data. The subjects are the union of two corpora selected by
different rules, 19 of the 28 from one project. The specification is the
fixed revision's. There is one run per subject and arm, and one measurement
per suite. And the suites are run by our runner, not by the projects' build.

---

## 3. Results

§3.1 to §3.8 report the first campaign and the measurements made around it,
and §3.9 what an audit of that campaign found. §3.10 reports the second
campaign, which is the confirmatory result. §3.11 reports the third, on
faults that postdate the model's training data, whose test does not reject.

### 3.1 First campaign: the two arms

Over the 36 bugs measured in both arms of the first campaign:

| | M arm (reads code) | S arm (spec only) |
|---|---|---|
| **Real fault detected** | **26/36 — 72%** | **5/36 — 14%** |
| Mutation score | 58% | 44% |
| Line coverage | 85% | 73% |

Detection differs by a factor of five. Mutation score differs by a factor of
1.3 and coverage by 1.2.

The paired outcomes are strongly asymmetric: of the 36 bugs, 21 were detected
by the M arm alone and **none** by the S arm alone. The S arm's detections are
therefore a strict subset of the M arm's rather than a partially overlapping
set. An exact McNemar test on the 21 discordant pairs gives
*p* = 9.5 × 10⁻⁷.

The mutation-score gap is smaller but just as consistent: the M-arm suite
scores higher in 35 of the 36 bugs (sign test, *p* ≈ 10⁻⁹). It has two parts of
about the same size. The S-arm suites leave more of the program unexecuted —
25.6% of mutants are never covered, against 13.6% — and on the mutants they do
execute they kill fewer, 59% against 67%.

Reported per arm over every suite measured, including the unpaired ones:

| arm | suites | detection | mutation | coverage |
|---|---|---|---|---|
| M arm, Sonnet | 36 | 26/36 (72%) | 58% | 85% |
| S arm, Sonnet | 38 | 6/37 (16%) | 44% | 73% |
| EvoSuite | 36 | 15/35 (43%) | 47% | 85% |
| M arm, Opus † | 6 | 6/6 | 70% | 89% |

Detection is over the suites with a valid verdict: one S-arm suite and one
EvoSuite suite are `Broken` (§2.9). EvoSuite's coverage is over the 35 suites
that have a figure.

† Six of the first seven bugs of the sample rather than a random subset: the
run switched models on exhausting quota (§2.3). The detection figure is
reported as a count rather than a percentage to discourage reading it as a
model comparison. On the same six bugs the Sonnet suites detect five, with a
mutation score of 63% and coverage of 86%.

### 3.2 Consistency across projects

The effect holds in all four subjects, which differ substantially in age,
style and documentation density:

| project | n | M detected | S detected |
|---|---|---|---|
| Commons Lang | 12 | 8 | 1 |
| Commons CSV | 9 | 7 | 2 |
| Gson | 8 | 6 | 1 |
| Commons CLI | 7 | 5 | 1 |

### 3.3 What the specification-only arm does detect

The five faults detected by the S arm are Cli-32, Csv-4, Csv-6, Gson-15 and
Lang-13. We read the javadoc of each modified class **at the buggy revision**,
and the generated test that detects each fault, to ask whether the
documentation states the behaviour the fault violates — whether, in other
words, a reader of the documentation alone could have written the failing
assertion. In all five the fix leaves the javadoc untouched, so the text read
here is also the text the agent was given.

Three of the five are documented-contract violations:

- **Cli-32** — `findWrapPos` is documented as "the last position before
  startPos+width having a whitespace character […] If there is no whitespace
  character before startPos+width, it will return startPos+width." The faulty
  loop scanned past the requested width instead of returning it.
- **Lang-13** — the class javadoc promises deep cloning by serialization for
  any `Serializable` object; cloning one holding primitive `Class` references
  failed.
- **Gson-15** — the javadoc of `setLenient` says what a lenient writer permits
  and a strict one refuses: "Numbers may be NaNs or infinities." The faulty
  `value(double)` rejected them in either mode. The test that detects the
  fault, `testValueDoubleNaNAllowedWhenLenient`, quotes that sentence in a
  comment. The method's own `@param` text says the opposite — "a finite value.
  May not be NaNs or infinities" — and the same suite asserts that too, for the
  strict mode. The documentation contradicts itself and the agent tested both
  halves.

Two are not:

- **Csv-4** — `getHeaderMap` is documented as "Returns a copy of the header map
  that iterates in column order", its keys column names and its values indices.
  Nothing covers the no-header case or a null return.
- **Csv-6** — `putIn` is documented as "Puts all values of this record into the
  given Map." Nothing covers a record holding fewer values than the header map.

**There is no single mechanism.** The count of three depends on reading past
the method the fix changes: for Gson-15 that method's own `@param` text
describes the faulty behaviour, and the contract the fault violates is stated
on `setLenient`. What the specification-only arm detects is heterogeneous:
contract violations, and faults reached by probing boundaries, which both
arms' prompts instruct the agent to do and which require no specification at
all. Cli-32 is both: its faulty loop also reads `text.charAt(pos)` under
`pos <= text.length()`, so a boundary input throws regardless of what the
javadoc says.

We report this as a description, not as a predictor. Three of five fits the
obvious hypothesis, that a specification-only agent catches what the
specification states, but the classification was made knowing which faults
were detected, and the evidence against it is in the same repository: an
incomplete and equally non-blind classification of the twelve Commons Lang bugs
(`data/contract-violation.csv`) marks four as contract violations, of which the
arm detected one. A classification designed to test the hypothesis would have
to be committed before the arms are run; ours was not, and is reported as a
limitation rather than a finding (see `data/contract-violation.md`).

### 3.4 Writing from documentation produces few wrong expectations

Across the S arm, **59 of 1638 tests (3.6%)** were disabled for failing on the
fixed revision. Per project:

| project | pruned / total | rate |
|---|---|---|
| Commons Lang | 4 / 579 | 0.7% |
| Commons CSV | 10 / 467 | 2.1% |
| Commons CLI | 12 / 203 | 5.9% |
| Gson | 33 / 389 | 8.5% |

The rate spans an order of magnitude across subjects. Commons Lang's javadoc is
unusually explicit, and its rate is under one percent; Gson, which documents
reflection and generics code far more sparsely, is at the other end.
Documentation density plausibly explains the spread, though we did not measure
it and cannot separate it from differences in API complexity. The second
campaign does not show the spread (§3.10).

Even at the high end the rate is low. This retires the hypothesis that
specification-only generation would largely be guesswork: agents write tests
from javadoc that are almost always correct about what the code does, and still
fail to catch real faults.

### 3.5 Search-based baseline

EvoSuite, invoked through Defects4J's `gen_tests` with a total budget of 120
seconds per bug (§2.7), produced suites for 38 of the 40 bugs; the two failures
are the `cli2` subjects (§2.9). Like the implementation-visible arm, EvoSuite
generates against the fixed revision and works from the repaired code.

Thirty-five bugs have a suite from all three generators with a mutation score.
One of the EvoSuite suites is `Broken` (§2.9), so the three are compared on the
34 bugs where each has a valid detection verdict:

| | detection | mutation | coverage |
|---|---|---|---|
| M arm (implementation-visible) | 24/34 (71%) | 58% | 85% |
| EvoSuite | 14/34 (41%) | 47% | 85% |
| S arm (specification-only) | 5/34 (15%) | 44% | 73% |

EvoSuite's coverage is over 33 suites (§2.9). Five of its 34 verdicts come
from the corrected harness of §2.7.

EvoSuite falls between the two arms on detection. It works from the same
repaired implementation as the implementation-visible arm, though not from the
tests, changelog and benchmark metadata that arm could also read (§3.9), so the
gap from 71% to 41% mixes a difference in generator with a difference in
information. The gap from 71% to 15% is between the same generator under the
two conditions.

**The two approaches are complementary, not ordered.** Of the 34 bugs, 10 are
detected by both, 14 by the agent alone, 4 by EvoSuite alone, and 6 by neither
— a union of 28 (82%). A search-based generator that asserts observed behaviour
without interpreting it still reaches four faults that the agent misses.

**Neither metric tracks detection across the three populations.** Mutation
score puts the implementation-visible suites first and the other two close
together: 47% for EvoSuite and 44% for the specification-only suites when
pooled, 47% and 48% — the other way round — when averaged per suite. Their
detection rates are 41% and 15%. Coverage does separate those two, 85% against
73%, but then cannot tell EvoSuite from the implementation-visible suites, 85%
for both, whose detection rates are 41% and 71%. On the mutants they execute,
the specification-only suites kill more than EvoSuite's do, 59% against 54%,
and detect about a third as many faults.

### 3.6 Cost

At list prices, the 40 Sonnet suites of the M arm cost $42.61 and the 40 of the
S arm $37.02 — $1.07 and $0.93 per suite. The nine Opus runs cost a further
$12.32, of which $10.13 for the six accepted suites. Both arms were produced
against a subscription quota rather than metered billing, so these figures are
token valuations rather than amounts charged.

They cover the runs whose records survive. A run repeated after an
infrastructure failure overwrote the record of the one it replaced; in the S
arm that is at least Lang-21, whose discarded first run cost $1.48.

### 3.7 Memorisation

Under the identifier cue, the model disclaimed knowledge for **all 40 bugs**:
the benchmark identifiers are not memorised.

Under the location cue, 25 answers disclaimed and one run returned no answer:
the model tried to call a tool, which the single-turn limit cut short. The
other 14 described a fault, and the mechanical screen flagged five of them for
reproducing three or more identifiers from the fix. Reading those five against
the actual faults, **four are confabulations**: the model describes a
plausible, internally coherent, confidently stated bug in the right class that
is not the bug in question.

| bug | actual fault | model's answer |
|---|---|---|
| Lang-8 | reads the construction-time zone instead of the calendar's | mutates the caller's `Calendar` without cloning |
| Lang-63 | hardcoded `days += 31` and a `reduceAndCorrect` correction pass | calendar arithmetic sensitive to DST transitions |
| Lang-65 | an absent truncation block between existing marker comments | missing special case for `Calendar.SEMI_MONTH` |
| Gson-4 | an obsolete restriction on top-level JSON values | missing delimiter check after `true`/`null` literals |

**The fifth is genuinely recalled: Lang-13.** The model reproduces the
mechanism in full — `ClassLoaderAwareObjectInputStream`, `resolveClass()`,
`Class.forName()` failing on primitive type names, and the repair mapping
primitive names to their `TYPE` constants — without being shown any code. It
misattributes the JIRA identifier, which is characteristic of recall of a
mechanism rather than of a record.

The screen missed more than it caught. It scores an answer against the diff of
the bug the probe was issued for, so the nine answers it did not flag were
read by hand as well. Read against every sampled fault in the same class, three
of them recall a *different* bug in the sample:

- The answer to the probe for Gson-14 describes the Gson-16 fault exactly:
  infinite recursion in `$Gson$Types.resolve()` on self-referential type
  variables, repaired by tracking the variables already visited. Both bugs are
  in that class and received the same question. The probe issued for Gson-16
  itself disclaimed.
- The answer for Lang-23 names LANG-477, the issue behind Lang-43, and adds
  that it "was one of the defects captured in the Defects4J benchmark". It
  gives the area of the fault, not its mechanism.
- The answer for Lang-56 gives the symptom of LANG-818, which is Lang-8 —
  `format(Calendar)` ignoring the calendar's own time zone — with a repair that
  is wrong.

Two more describe real faults in the same classes that are not in the sample
(CSV-118 and LANG-480, Defects4J's Csv-9 and Lang-42). The readings are in
`data/memorisation-readings.csv`.

**So the probe finds two of the forty faults recalled with their mechanism,
Lang-13 and Gson-16, and two more recognised by issue number or symptom.** It
is a lower bound, and a soft one: each probe is a single sample, and the same
question drew an exact description once and a disclaimer once.

The probe also understates what the model can reproduce once cued. In the
implementation-visible arm, with the fixed source and the bug's identity in
front of it (§3.9), the same model wrote out the developer's trigger test for
Lang-13 verbatim — name, array of primitive types, loop and assertion — and
reproduced the pattern, argument and expected string of Lang-43's, although
both test files had been deleted from its working copy.

What follows from this is narrow. Spontaneous recall does not account for the
implementation-visible arm's result: it detects 26 faults, and the probe finds
a handful recalled. But recall cued by the source, and by the benchmark's own
metadata, is present in that arm, and the probe cannot bound it. Lang-13 is
detected by both arms, as recall available to both would predict; the other
four faults the specification-only arm detects show no sign of recall in the
probe.

The confabulation rate is itself worth noting alongside §3.4. The same model
that writes tests from javadoc with a 3.6% error rate (6.7% in the second
campaign) invents four confident,
specific and wrong faults when asked about code it cannot see. Correctness here
tracks whether there is something to check against.

### 3.8 Post-cutoff replication, and why it does not settle contamination

The probe in §3.7 bounds spontaneous recall but cannot rule out recall *cued*
by the source, since withholding the source withholds the cue. Faults the model
cannot have seen would settle it. We therefore mined two small corpora from the
same four upstream repositories, taking fix commits recent enough to postdate
the training data, so that the intended difference from the Defects4J sample is
the date.

Only detection is measured in either. Mutation score and coverage are not:
recall bears on detection — the model remembers a fault and writes the test
that catches it — more directly than on what a suite covers or how hard it
checks, and both are already measured over 36 Defects4J bugs.

Two things differ from the Defects4J runs and weaken the comparison. The
implementation-visible agent works in a git worktree, with the repository's
history, fix commit included, within reach; the prompt forbids git and nothing
enforces it. And both arms use the per-method acceptance filter of §2.5, so a
failing test is disabled in either arm rather than an M-arm suite being
rejected whole.

**First corpus.** Candidates were fix commits from June to September 2026 that
change both production and test code, touch at most three production files, and
for which the fix's tests fail on the parent commit and pass on the fix. Eleven
subjects passed that validation. Three could not be used in either arm:
removing the developer test file that holds the trigger tests breaks
compilation, because other test classes call static helpers defined in it —
`FastDateParserJava15BugTest` uses `FastDateParserTest.checkParse` and
`LONG_FORMAT`, and `CSVPrinterTest` likewise depends on `CSVFormatTest`. That
leaves eight subjects.

The implementation-visible arm detected **6 of 8 (75%)**, with none of its 251
tests disabled — close to the 72% measured on Defects4J.

**The specification-only arm has no valid result on this corpus.** Seven of its
suites were accepted (the eighth did not compile against the project), with 11
of 276 tests disabled, 4.0%, a rate close to the 3.6% measured on Defects4J.
But none of the seven was ever run against a buggy revision. The harness ran
the fixed revision with the project's licence audit switched off and the buggy
revision with it on, and counted any failed build as a detection. A test file
written in the sandbox carries no licence header; the audit runs before the
tests; all seven builds stopped there. The generated tests were not archived,
so the arm cannot be re-measured on these subjects. One of them was
regenerated for the second corpus, a fault at `Integer.MIN_VALUE` in fraction
reduction; neither arm detected it.

**Second corpus, matched on fault type.** The second corpus fixes its
composition in advance. Quotas by fault type were scaled from the hand
classification of the Defects4J sample, which is dominated by omissions (22 of
40), and written down before any candidate was examined
(`data/matched-quotas.md`). Candidates from January to September 2026 were
walked newest-first and classified from their production diff before
validation; systematic audit sweeps and performance-only changes were excluded
as populations. One deviation is recorded there: once two quotas had closed,
the remaining candidates were screened by commit subject rather than examined
one by one. A second was found later: the quotas were computed from a tally
that miscounted the classification (21 omissions and 7 algorithm faults where
the file has 22 and 6), which moves no quota by more than one subject.

Nineteen subjects validated: ten omissions, three algorithm rewrites, three
substitutions, two state faults and one missing clause. The fourth algorithm
slot could not be filled. Four of the nineteen could not be used in either arm,
for the same test-compilation reason as above.

| arm | suites accepted | valid verdict | detected |
|---|---|---|---|
| implementation-visible | 15 | 14 | 8/14 (57%) |
| specification-only | 13 | 13 | 4/13 (31%) |

One implementation-visible suite does not compile against the buggy revision.
Of the two specification-only suites lost, one does not compile against the
project and one fails on the fixed revision in parameterised tests, which the
acceptance filter cannot disable.

Over the **13 subjects with a valid verdict in both arms**, the
implementation-visible arm detects 8 (62%) and the specification-only arm 4
(31%). Four subjects are detected by the former alone and none by the latter
alone — the same strict-subset pattern as in the first campaign on Defects4J
— but with four
discordant pairs the exact McNemar test gives *p* = 0.125.

**What this does and does not show.** In these runs the direction of the
effect holds on faults the model cannot have memorised, and so does the
subset relation. Its size is another matter: the gap is 31 points here
against 58 in the first campaign on Defects4J, with the
implementation-visible arm lower and the specification-only arm higher. At
thirteen pairs that difference is well within what chance allows, so this
corpus can neither confirm the Defects4J
effect size nor show that contamination inflated it. It bounds contamination
only in the weak sense that an effect in the same direction survives its
removal. These working copies are not Defects4J checkouts and carry none of
its metadata. The second campaign, which takes that metadata out of the
Defects4J runs, finds a gap of 38 points there (§3.10).

They carry something else: the fix commit, within reach of the
implementation-visible agent, with nothing but a prompt in the way and no
record of what the agent did. The third campaign repeats the comparison on
these subjects, and on the ones this harness could not use, with the fix
commit out of reach, the conditions enforced and every transcript kept
(§3.11). There the implementation-visible arm detects 7 of the 19 subjects on
which it had detected 13 here.

### 3.9 The implementation-visible agent knew which bug it was testing

The controls of §2.4 were meant to give the M-arm agent the repaired code
without telling it what had been repaired. They did not achieve that. No
transcript of the runs was kept, so what the agent read cannot be observed
directly. Each run left its closing message and the suite it wrote, and three
left notes in the agent's persistent memory. Those artifacts show what it knew
(`bin/audit-trigger-leaks.py`, `data/agent-notes/`):

| evidence | bugs |
|---|---|
| A generated test has exactly the developer trigger test's name, and is the test that detects the fault | Cli-12, Cli-17, Csv-4, Csv-6, Lang-13 |
| The closing message names the trigger test | Csv-8, Lang-13, Lang-62 |
| The closing message names its own Defects4J bug: "the Lang-13 regression", "the Lang-52 fix", "the Lang-63 trigger scenario", "the CSV-106 / Csv-5 regression point" | Csv-5, Lang-13, Lang-52, Lang-63; also Csv-14 (not detected) and Cli-21 (excluded) |
| The suite carries the issue number that appears in the trigger test's name, and reproduces that test's input and expected output | Lang-43 |
| The agent's own note gives the trigger test by name with its input and expected output, and the test that detects the fault reproduces them | Lang-63 |

That is 13 of the 40 M-arm suites, and **11 of the arm's 26 detections**. One
of the six Opus suites, Lang-43's, carries the same issue number. None of the
40 S-arm suites or closing messages shows any of it.

Once the trigger tests' files are deleted, their names survive in
`defects4j.build.properties` and, for the five bugs of §2.4, in Defects4J's
backup of the test class. The bug identifier is in the properties file, in
`.defects4j.config` and in the directory name. So for at least these eleven
the agent was not only shown the repair. It was told, by the benchmark's own
bookkeeping, which behaviour the benchmark would test — and "trigger" is
Defects4J's word, not the projects'. Where the agent reproduced a deleted
test's body as well (Lang-13, Lang-43), nothing left in the working copy
contains it; the likeliest source is training data, cued by the name.

Lang-63 is the one case with a first-hand record. The note that run left gives
the trigger test as "`DurationFormatUtilsTest::testJiraLang281` (2005-12-31 ->
2006-10-06, "MM" -> "09")", and says of the developer tests we removed that
they are "sometimes kept as `.java.bak` — useful for known-good expected
values". The one test of that suite that fails on the buggy revision has those
dates, that pattern and that expected string. Their only copy in the working
tree was Defects4J's backup of the trigger test's class. That detection is the
developer's test, copied. The backups of the other four bugs were compared
with their suites by hand, and none is reproduced.

This does not change what was measured: 26 of 36 against 5 of 36 under two
conditions. It changes what the first condition is. The M arm is not "the
agent can read the implementation". It is "the agent has a Defects4J checkout",
which is what a standard evaluation gives it, and which leaks more than the
repair. How much of the 72% the metadata accounts for, as opposed to the code,
the first campaign cannot say. The fifteen detections with no such trace are
not thereby shown to be clean, and the eleven with one might have been made
from the code alone. The second campaign removes the metadata.

### 3.10 Second campaign: the comparison under control

The 80 runs of the second campaign (§2.10) were made in one session on 17 and
18 November 2026, in the order the protocol fixes. Every run reports the same
model and harness version. None was cut short by a usage limit and none was
made twice. Every run left a test class that compiles: 1,453 tests from the M2
agents and 1,500 from the S2 agents. One S2 run, on Csv-3, ended on its turn
limit and not by the agent's decision. Under the protocol it stands, and its
suite is used as it was packaged.

**The audit found no violation.** Before anything was measured, every command
the audit script flags was read in full with its result, together with what
the script does not look at: the paths given to the file tools, every direct
call to the compiler, and every S2 command that names `lib/`, a jar or a class
file. No command in either arm reaches for the network. Nothing outside a
working copy was read except the operating system and the JDK.

What the S2 agents attempted is a finding in itself. The prompt forbids
inspecting `lib/`, and 22 of the 40 agents tried to list or unpack a jar, with
`unzip`, `jar` or a script: 15 the project's jar or every jar, 7 only JUnit's.
None succeeded: the sandbox hides those programs, and the harness refused the
remaining attempts before they ran. One agent wrote a Java program to list a
jar, compiled it, and could not run it. The first campaign's S arm had the
same instruction, the same programs within reach, and no record of what it
did.

One case was decided on the protocol's wording. The S2 agent for Csv-10
compiled a scratch file of its own with `javac`, seven times, to find out
which methods a class has that its javadoc does not cover. That breaks the
prompt. It is not a violation as §2.10 defines one, since nothing in `lib/`
was run, printed, unpacked or disassembled, and the compiler messages it read
are the ones the arm's own script would have shown it. The run stays in the
analysis. The decision was recorded before measurement, with a commitment to
report the analysis without that run as well.

**Measurement.** All 80 suites have a coverage figure. Two have no detection
verdict: the M2 and S2 suites of Cli-21, each of which calls a method the fix
adds to an interface and so does not compile against the buggy revision. That
leaves a paired set of 39 bugs. Three of them lack a mutation score in at
least one arm: Gson-14 and Gson-16, where Major rejects the class (§2.9), and
Gson-8, where the JVM running the analysis of the S2 suite crashes under one
mutant, reproducibly. The complete set has 36 bugs.

| | M2 (reads code) | S2 (spec only) |
|---|---|---|
| **Real fault detected**, paired set, 39 bugs | **22/39 — 56%** | **7/39 — 18%** |
| Real fault detected, complete set, 36 bugs | 20/36 — 56% | 7/36 — 19% |
| Mutation score, complete set | 54% | 39% |
| Line coverage, complete set | 84% | 70% |

**H1: the arms differ in detection.** Of the 39 bugs, six are detected by both
arms, 16 by M2 alone, one by S2 alone and 16 by neither. The exact McNemar
test gives *p* = 2.8 × 10⁻⁴, and H1 is rejected with M2 above S2. The
difference is 38.5 points, with a 95% bootstrap interval of 20.5 to 56.4.

**H2: detection falls further than mutation score.** On the complete set:

| | M2 | S2 | fall |
|---|---|---|---|
| Detection | 55.6% | 19.4% | 65.0% |
| Mutation score, pooled | 54.0% | 39.1% | 27.7% |
| Line coverage, pooled | 83.7% | 70.3% | 16.1% |

The fall in detection exceeds the fall in mutation score by 37.3 points, with
a 95% bootstrap interval of 12.0 to 59.0. The lower bound is above zero and H2
is supported. Against line coverage, a secondary result, the difference is
48.9 points (24.0 to 69.8). By the rule fixed in the protocol, the claim in
the title stands.

**Sensitivity.** None of the following is confirmatory. No run has a
violation, so the analysis with violations included is the primary one.
Counting every bug attempted, and a suite without a verdict as a
non-detection, gives 22/40 against 7/40 and the same *p*. The audit script
marks two runs as showing knowledge of the bug, both on Lang-36: each agent
named a test of `NumberUtils.isNumber` `testIsNumber`, which is also the name
of one of that bug's trigger tests. Without them the figures are 22/38 against
7/38 and the interval of H2 is 11.7 to 58.4. With the mean over suites in
place of the pooled mutation score, the arms are at 64.3% and 45.3%. Without
the S2 run of Csv-10, the check committed to at the audit, the figures are
21/38 against 6/38 and the interval is 15.2 to 62.3.

**Where the gap in mutation score comes from.** The M2 suite has the higher
score in 34 of the 36 bugs (sign test, *p* ≈ 10⁻⁹). A little more than half of
the gap is code the S2 suites never execute, 29.2% of mutants against 15.1%.
The rest is what they kill of what they do execute, 55.2% against 63.7%.
Defects4J's own table, which counts unexecuted mutants as killed (§2.6), would
have put the two arms at 69.1% and 68.3%.

**Per project.**

| project | n | M2 detected | S2 detected |
|---|---|---|---|
| Commons Lang | 12 | 5 | 0 |
| Commons CSV | 10 | 7 | 3 |
| Gson | 10 | 7 | 2 |
| Commons CLI | 7 | 3 | 2 |

The direction is the same in all four. The gap is widest in Commons Lang and
narrowest in Commons CLI, where one of the two S2 detections is a fault M2
misses.

**What S2 detects.** Seven faults: Cli-17, Cli-32, Csv-3, Csv-4, Csv-10,
Gson-6 and Gson-15. Six are also detected by M2. Cli-17 is not. Its fault is
in how `PosixParser` bursts a token such as `-xy` into single-character
options: with `stopAtNonOption` set, an unknown character should end the
bursting, and the faulty loop went on. The javadoc of the bursting method
states the rule: "add the special token `--` followed by the remaining
characters". The S2 suite tests exactly that, with a token of two unknown
characters, and fails on the buggy revision. The M2 suite has a test of the
same rule whose token ends at the unknown character, an input on which the
two revisions agree. So detection by reading the repaired code is not a
superset of detection by reading the contract, which is what the first
campaign's strict subset had suggested (§3.1).

**Wrong expectations.** Acceptance disabled 101 of the 1,500 S2 tests, 6.7%,
in 28 of the 40 suites. It disabled none of the 1,453 M2 tests: every M2
agent ran its tests and left them passing. Per project the S2 rate is 3.7% in
Commons CSV, 7.2% in Commons Lang, 7.9% in Gson and 9.0% in Commons CLI. The
overall rate is nearly twice the first campaign's 3.6% (§3.4), and Commons
Lang, under one percent there, is now level with the others. The campaigns
differ in several respects. One of them is that only the second prevents an
agent from running its tests and correcting them. Whatever the cause, the
spread across projects that §3.4 describes does not recur, and neither does
the support it seemed to give to documentation density as an explanation.

**The first campaign beside the second.** This comparison is descriptive. The
campaigns differ in prompts, tools, reasoning effort, acceptance, isolation,
harness version and date as well as in the benchmark's metadata (§2.10), so
the difference between the two implementation-visible arms is an upper bound
on what the metadata accounts for, not a measurement of it.

| | first campaign | second campaign |
|---|---|---|
| Implementation-visible, 36 bugs with a verdict in both | 26 (72%) | 20 (56%) |
| Specification-only, 37 bugs with a verdict in both | 6 (16%) | 7 (19%) |

Every fault M2 detects on those 36 bugs, M had detected. M detected six more:
Lang-13, Lang-21, Lang-63, Csv-16, Cli-10 and Cli-17. The six do not line up
with the evidence of §3.9. Of the eleven detections that show a trace of the
metadata, M2 keeps eight; of the fifteen that show none, twelve. Two of the
three lost from the first group are the two with the strongest trace: Lang-63,
where the first campaign's detecting test was the developer's own, copied from
Defects4J's backup, and Lang-13, where the agent had written out the trigger
test. Lang-13 is also the fault the memorisation probe found recalled with its
mechanism (§3.7). Both arms of the first campaign detected it, in working
directories whose names carried the bug's identifier. Neither arm of the
second does.

The two specification-only arms detect six and seven faults and have four in
common (Csv-3, Csv-4, Gson-15, Cli-32). With one run per bug and arm, that
overlap is the only indication in this study of how much a single run
decides.

**EvoSuite beside both arms.** On the 35 bugs where M2, S2 and EvoSuite each
have a verdict:

| | detection | mutation | coverage |
|---|---|---|---|
| M2 (implementation-visible) | 20/35 (57%) | 53.7% | 83.3% |
| EvoSuite | 15/35 (43%) | 47.1% | 85.5% |
| S2 (specification-only) | 7/35 (20%) | 39.1% | 69.9% |

EvoSuite falls between the two arms on detection and on mutation score, and is
level with M2 on coverage. M2 and EvoSuite detect ten faults in common, ten
and five alone, and 25 of the 35 between them. The two remain complementary,
and they are closer than in §3.5, where the implementation-visible arm also
had the benchmark's metadata. Mutation score here orders the three populations
as detection does. What it does not reflect is the distances: from EvoSuite to
S2 mutation score falls by a sixth and detection by more than half.

**Cost.** At list prices the 40 M2 runs cost $16.18 and the 40 S2 runs $23.07,
or $0.40 and $0.58 a suite, in 18 and 14 turns a run on average. Like the
first campaign's, they were made against a subscription quota. The first
campaign's suites cost $1.07 and $0.93 (§3.6). The lower figures fit the
difference in reasoning effort between the campaigns, which is one more
reason not to read the distance between them as the effect of the metadata
alone.

### 3.11 Third campaign: the comparison on post-cutoff faults

The 56 runs of the third campaign (§2.11) were made in one session on 18
November 2026, in the order the protocol fixes, with the model and harness
version of the second campaign. None was cut short by a usage limit, none was
made twice, and every run ended by the agent's own decision. Every run left a
test class that compiles: 1,217 tests from the M3 agents and 1,558 from the
S3 agents.

**The audit found the sandbox less tight than §2.10 describes.** Before
anything was measured, every command the audit script flags was read in full
with its result, together with what the script does not look at: the paths
given to the file tools, every absolute path in any command, every program
name, every S3 command that names `lib/`, a jar, a class file or the
compiler, and the code the agents wrote. No command in either arm reaches for
the network. Two things were within reach that should not have been.

- The harness gives sandboxed commands a directory for temporary files.
  Unlike the rest of `/tmp`, which each command sees empty, that directory is
  the host's own, readable and writable from inside and shared by every
  command of every run. During the campaign it also held the working files of
  the session that had prepared the campaign, among them a dry run of the
  generator with the developers' tests for each fix. Nothing in the settings
  hides them, so we assume every agent in both arms could have read them.
- The operating system's packages include released jars of Commons Lang and
  Commons CLI, older than every fix, in a directory the sandbox does not
  hide. Beside the source, an older release shows what has changed since
  (§2.11).

The transcripts show that no agent used either. No command lists the shared
directory or names a path in it other than files the same run had just put
there, and no agent opened one of those jars. Five commands searched the
whole file system by name. One M3 agent searched it for the developers' test
class that had been removed from its tree, "for ideas", and found nothing;
another saw the names of the Commons Lang jars and did nothing with them. The
second campaign ran under the same settings on the same machine. Its
transcripts, searched again, show three agents naming the shared directory
and none writing or reading a file there.

**Five runs are left out by the rule as written.** The rule excludes a run
that read a file outside its working copy other than the operating system's
and the JDK's, and its one exception is a command's private `/tmp`. Four runs
read back files they had themselves written in the shared directory: a class
unpacked from the run's own libraries, scratch programs compiled from sources
in the working copy, and the text of the run's own javadoc pages with the
tags stripped. A fifth read the harness's saved copy of the output of its own
command, which the harness keeps outside the working copy when the output is
long. None obtained anything that did not come from its own working copy. The
rule has no exception for that and we made none after reading the
transcripts: the five runs, two of M3 and three of S3, on five subjects, are
out of the primary analysis and back in the first sensitivity analysis.

Five of the 28 S3 agents tried to list a jar in `lib/`, against 22 of 40 in
the second campaign, and none succeeded. One S3 agent compiled two scratch
classes of its own with the compiler directly, to see whether the methods it
meant to call exist: the case §2.11 settles beforehand. Three runs are marked
as naming a trigger test, each for a test the agent named after the method it
tests (`testEquals`, `testHashCode`, `testIsCreatable`,
`testWithHeaderComments`). Nothing an agent said or wrote names an issue, a
pull request or a fix commit.

**Measurement.** Every suite passes on the fix commit when run again. Two
have no verdict, the M3 and S3 suites of one Commons CSV subject: each reads
a field the fix adds and so does not compile against the parent commit. One
of those two runs is also among the five left out, so the paired set has 23
subjects.

| | M3 (reads code) | S3 (spec only) |
|---|---|---|
| **Real fault detected**, paired set, 23 subjects | **8/23 — 35%** | **5/23 — 22%** |
| With the five runs included, 27 subjects | 9/27 — 33% | 6/27 — 22% |
| Every subject, no verdict counted as not detected | 9/28 — 32% | 6/28 — 21% |

**The hypothesis is not rejected.** Of the 23 subjects, five are detected by
both arms, three by M3 alone, none by S3 alone and fifteen by neither. The
exact McNemar test gives *p* = 0.25. The difference is 13.0 points, with a
95% bootstrap interval of 0.0 to 26.1. By the rule fixed in the protocol,
this corpus does not show the difference between the arms. That is not
evidence that there is none. The test needed six discordant pairs against
none, the corpus produced three, and the interval runs from no difference to
one of 26 points. Nor is it evidence that recall produced the effect on
Defects4J: the campaigns differ in more than the date of their faults.

**Sensitivity.** None of the following is confirmatory, and none reads
differently. With the five runs included the three discordant pairs are the
same and *p* = 0.25; the difference is 11.1 points (0.0 to 22.2). Without the
three runs that name a trigger test, 7/20 against 5/20, *p* = 0.5. Without
the S3 run that called the compiler, 8/22 against 5/22, *p* = 0.25. No
verdict is a timeout.

**Where the detections are.** All of them are in Commons Lang: 8 and 5 of its
16 paired subjects. Neither arm detects any of the six paired subjects of
Commons CSV or the one of Commons CLI. Every fault S3 detects, M3 detects
too. The three M3 detects alone are a wrong answer of `CharRange.contains`
for negated ranges, a number that overflows an `int` in `FastDateParser`, and
the `equals` and `hashCode` that a fix adds to `ImmutableTimeZone`. By the
corpus a subject was mined for, the arms detect 4 and 2 of the 15 from the
matched corpus and 4 and 3 of the 10 from the first.

**Wrong expectations.** Acceptance left out 63 of the 1,558 S3 tests, 4.0%,
in 20 of the 28 suites, and none of the 1,217 M3 tests: every M3 agent ran
its tests and left them passing. The S3 rate is 2.9% in Commons Lang and 5.1%
in Commons CSV, against 7.2% and 3.7% for S2 on Defects4J (§3.10).

**The second campaign beside the third.** This comparison is descriptive. The
gap between the arms is 38.5 points in the second campaign and 13.0 here. The
difference between the two, −25.4 points, has a bootstrap interval of −46.9
to −2.3, each campaign's subjects resampled on their own. What moves is the
implementation-visible arm, from 56% to 35%; the specification-only arm is at
18% and 22%. The campaigns do not differ in the date of the faults alone.
The projects, the kinds of fault, the test framework, how the working copy is
built and how a suite is run all differ, and so does the composition by
project: every detection here is in one library. So the narrower gap is not a
measurement of what recall contributed on Defects4J. Interpreting it needs a
larger corpus, matched to the Defects4J sample in project and kind of fault.

**The earlier runs on these subjects beside this campaign.** Also
descriptive. On the 19 subjects with a valid verdict from both, the
implementation-visible runs of §3.8 detected 13 and M3 detects 7, every one
of them among the 13. In those runs the agent worked in a git worktree, with
the fix commit within reach and nothing enforced, and the runs differ in
other ways too, prompts and tools among them, so six is an upper bound on
what the reach of the fix commit added. It is the same pattern as on
Defects4J, where taking the benchmark's metadata out of the working copy cost
the arm six detections of twenty-six (§3.10). On the 11 subjects with a valid
verdict from both specification-only arms, the earlier runs detected two and
S3 detects one of the two.

**Cost.** At list prices the 28 M3 runs cost $13.75 and the 28 S3 runs
$21.34, or $0.49 and $0.76 a suite, in 18 and 16 turns a run on average.

---

## 4. Discussion

### 4.1 The suite mirrors whatever implementation it reads

The mechanism is simple and its sign depends entirely on which revision the
agent is shown. An agent writing tests against code it can read encodes that
code's behaviour as the expected behaviour. Show it the *repaired* code and its
tests encode the repair, so they detect the fault by construction. Show it
*faulty* code and its tests encode the fault, so they cannot detect it.

The second case is the familiar worry — tests written after the code inherit
the code's mistakes — and it is what makes the first case easy to overlook. Our
arms isolate the first. The implementation-visible arm's figure is not a
measure of testing ability but a product of the evaluation protocol itself: of
the repaired code, with which the arm reaches 56%, and of what a standard
checkout puts beside the code, with which it reached 72% in a campaign that
differed in other ways as well (§3.9, §3.10).

Neither arm establishes what an agent would score against genuinely unknown
code. The specification-only arm's 18% is closer to that question but is not
the answer either, because withholding the implementation removes information a
real developer would have.

How much of this carries over to faults the model cannot have seen is not
settled by our data. On 23 fix commits that postdate its training data, under
the second campaign's controls, the arms are at 35% and 22% (§3.11). Every
fault the specification-only arm detects there the other arm detects too, and
it detects three more, which is the direction of the mechanism and a
difference the pre-specified test does not distinguish from none. The
implementation-visible arm is some twenty points lower there than on
Defects4J and the specification-only arm is about where it was. Reading the
repaired code helped
less on those subjects. Whether that is their projects and kinds of fault, or
recall of Defects4J that the source cues, the comparison cannot say, because
the two corpora differ in all of these at once.

### 4.2 What mutation score does and does not register

Mutation score does register the difference between the arms. In the second
campaign they are at 54% and 39%, and the implementation-visible suite scores
higher in 34 of 36 bugs. The first campaign had them at 58% and 44%, and 35 of
36.

What it does not register is the size of the difference. Between the arms of
the second campaign detection loses 65% of its value and mutation score 28%,
and the gap between those two losses is the quantity the campaign was designed
to test: 37 points, with an interval that excludes zero (§3.10). A little more
than half of the loss in mutation score is coverage — code the
specification-only suites never execute — rather than weaker checking of the
code they do. A reader shown only the two mutation scores would expect the
suites to differ in fault detection. Nothing in the scores would lead them to
expect 56% against 18%.

This is not a failure of mutation analysis on its own terms, and it does not
contradict the established result that mutation score predicts real-fault
detection (Just et al., FSE 2014; see §6): here, too, the population with the
higher score detects more. Mutation score asks whether a suite's assertions are
strong enough to distinguish the program from small syntactic variants of it.
The specification-only suites are moderately worse at that. They assert on
returned values, exact exception messages and persisted state, and on the code
they reach they kill 55% of mutants against 64%.

What the metric cannot see is where the expected values came from, and in this
study that is, we argue, where most of the difference in detection lies. A test
whose expectation was read off the repaired code fails on the buggy revision
whenever it touches the behaviour the repair changed. A test whose expectation
was derived from the documentation fails there only if the documentation
happens to pin that behaviour down. The two can kill exactly the same mutants.

The EvoSuite baseline shows the same looseness between populations that our
manipulation did not create, more sharply against the first campaign's suites
than against the second's. EvoSuite and the first campaign's
specification-only suites cannot be told apart by mutation score — the order
between them depends on how the scores are aggregated — and differ nearly
three-fold in detection (§3.5). Against the second campaign's, EvoSuite is
ahead on mutation score, by 47% to 39% pooled and by one point as a mean over
suites, and detects twice as many faults (§3.10). Coverage separates EvoSuite
from the specification-only suites in both campaigns and from the
implementation-visible suites in neither.

Stated as one sentence: **mutation score tracks the strength of a suite's
assertions, and tracks the provenance of its expectations only as far as the
two happen to move together.** In our arms they moved together a little.

The practical consequence for anyone evaluating agent-written suites: a high
mutation score is evidence that the tests exercise the code and that their
assertions bite. It is not evidence that the expectations are correct, and it
cannot support the claim that a generated suite would have caught the faults a
project actually had.

This bears on proposals to close the loop by feeding mutation results back to
the generating agent. Such a loop optimises a quantity that lost 28% of its
value when fault detection lost 65% — and an agent that can read the
implementation has a cheap way to raise it.

### 4.3 Oracle quality, not oracle presence

Read alongside Konstantinou et al. (§6), our arms extend a single axis: how
usable an oracle the generating agent is given. A natural-language task
description supports 25% detection in their setting; partial API documentation
supports 18% in ours; that description with a faulty implementation added
supports 14% in theirs; the repaired implementation produces 56% in ours, and
a Defects4J checkout of it 72% — figures that measure transcription, and in
the second case some of the benchmark's own leakage, not testing.

The practical reading is not "withhold the implementation". It is that the
detection rate of a generated suite is largely a function of what the agent was
given to reason from, and that a benchmark protocol which hands it the repaired
code is measuring the protocol rather than the agent.

### 4.4 What a specification-only agent can do

The specification-only arm is not incompetent. In the second campaign its
suites compile, cover 70% of lines, kill 39% of mutants, and are wrong about
behaviour in 6.7% of their tests: an agent writing from javadoc alone, unable
to run anything, misstates what the code does about once in fifteen tests. It
catches a much smaller set of faults, seven of thirty-nine, and not only
faults the other arm catches (§3.10). Of the five it caught in the first
campaign, three violate a contract the documentation states and two are
reached by probing boundaries (§3.3). The fault it alone catches in the second
is of the first kind.

We cannot say where specification-grounded generation is worth its cost. A
handful of detections in each Defects4J campaign, four of them the same, read
after the fact, are not a capability we can characterise. On post-cutoff
faults the arm detects 5 of 23 (§3.11), a rate close to its 18% on Defects4J
and from a sample too small to say more than that.

### 4.5 Separating the two, in practice

The only mechanism we demonstrate to distinguish a suite grounded in a contract
from one grounded in the code is the counterfactual itself: generate twice,
with and without the implementation, and compare. Tests that appear only in the
implementation-visible suite are the candidates for having transcribed the code
rather than tested it.

This doubles generation cost — $0.40 to $1 per suite at the prices in §3.6 and
§3.10 — and we have not built or evaluated such a tool. We report it as the
one approach the data supports directly, in contrast to mutation feedback,
which it supports only weakly.

### 4.6 The condition we did not run

The complementary condition — the agent writing tests against the **buggy**
revision — is not covered by our arms, though it is well represented in the
literature: it is TOGA's evaluation setting, TDD-Bench Verified's premise, one
side of the designs of Konstantinou et al. and of Huang et al., and, on
Defects4J itself, one of the two inputs Zhao et al. give their models (§6).

What would be specific to this harness is the *certification* rate: how often a
suite written against the buggy revision passes on it and fails on the fixed
one, locking the defect in place rather than merely missing it. Published work
measures how often such suites fail to detect. Huang et al. come nearest to
the other question: of the tests their models write from an incorrect
solution, 34.8% pass on it, against 26.3% of the tests written from the
correct one. That is a rate per test, on programming tasks, and a test that
never reaches the fault passes on the faulty code too. None that we found
reports, for real faults, how often a suite encodes the fault as expected
behaviour. The harness supports the condition with a one-character change to
the checkout.

## 5. Threats to validity

### 5.1 Internal validity

**The arms differ in more than one respect.** The intended variable is access
to the implementation. In the first campaign the arms also differed in five
other ways, the first three by design and the last two by oversight. The
second campaign removes three of the five and enforces a fourth.

- *Execution.* The S arm cannot run its tests. The restriction is deliberate —
  running tests is an alternative route to reading behaviour off the
  implementation — but it is a second difference and must be declared. In the
  first campaign it was also unenforced: the sandbox held the compiled classes
  and a shell, only the prompt forbade running or disassembling them, and no
  transcript was kept against which compliance could be checked. In the second
  the sandbox enforces it and the transcripts show that it held. They also
  show what it held against: 22 of 40 agents tried to list or unpack a jar
  (§3.10). What the first campaign's S agents did with the same instruction
  and no barrier is not known.
- *The rest of the checkout.* The M arm works in the project and can read its
  other tests and build files, and in the first campaign its changelog. The S
  arm has none of them. This holds in both campaigns.
- *Acceptance.* In the first campaign a failing S-arm test is disabled, while
  an M-arm suite must pass whole, which the agent ensures by running it
  (§2.5). In the second the rule is the same for both arms.
- *Instructions.* The first campaign's prompts share their two instructions on
  assertions and differ otherwise (§2.2). The M prompt restricts tests to the
  public API; the S arm's javadoc documents protected and package-private
  members and its prompt does not restrict them, and its detection of Cli-32
  calls a protected method directly. That difference favours the S arm. The
  second campaign's prompts are one text apart from what an arm requires
  (§2.10), and neither restricts tests to the public API.
- *Benchmark metadata.* The first campaign's M working copy names the bug and
  its trigger tests, and in at least eleven of its twenty-six detections the
  agent shows that it knew one or the other (§3.9). This is the most serious
  of the differences, because it is no part of what "reading the
  implementation" means. The second campaign's working copies carry none of
  it. What a search of them still finds is in the implementation itself: in
  one bug, Lang-65, the repaired code marks its own repair with comments that
  cite the issue.

The likely direction of the execution and acceptance differences is worth
stating. An M-arm agent that sees a test fail can rewrite the assertion to
match observed behaviour; an S-arm test that fails is simply removed by the
acceptance filter. Both arms therefore end in the same state (every surviving
test passes on the fixed revision), but the M arm reaches it by adjusting
expectations to the code, which is precisely the behaviour under study. The
asymmetry does not manufacture the effect; it is part of it. The metadata is a
different matter: it could manufacture part of the effect. The second campaign
bounds that part from above, at six detections in thirty-six (§3.10), and the
effect is there without it.

**The first campaign's runs were not isolated from one another.** The agent
ran under the operator's ordinary profile, which gives it a persistent memory
kept per working directory, and a bug has the same working directory whatever
the model. The Opus pilot and the Sonnet arm therefore shared a memory, as any
repeated run would. Notes survive from three runs (`data/agent-notes/`); each
was written by the run reported here and carries nothing from another, and no
notes were found for any other working directory. The design did not close the
channel, all the same. The second campaign runs each agent without the
operator's profile, with persistent memory off, in a sandbox from which the
other runs cannot be read and in a directory whose name is random.

**The second campaign was designed with the first one's results in view.** Its
hypotheses and its statistic were fixed before its own runs, not before the
study: we wrote them having seen 72% against 14% and 58% against 44% on these
forty bugs. What the protocol rules out is choosing the analysis after seeing
the second campaign's data. It does not make the second campaign an
independent sample of faults.

**Training-data contamination is measured, not bounded.** Defects4J has been
public for years. Structurally, if the implementation-visible arm's detection
rate reflected spontaneous recall rather than test-writing, the
specification-only arm would be expected to recall the same faults and detect
far more than the 14% and 18% it does. Directly, the probe in §2.8 finds two
of the forty faults recalled with their mechanism and two more recognised
(§3.7), against 26 detected by the M arm and 22 by M2; benchmark identifiers
are not memorised.

Neither argument reaches recall that is *cued*. The probe withholds the source,
and so suppresses the cue and not the memory. In the first campaign's M arm
the cue was stronger than the source alone, since the working copy named the
bug and its trigger tests (§3.9), and where the result is visible — the
trigger tests of Lang-13 and Lang-43, reproduced from files the agent did not
have — cued recall did occur. In the second campaign the source is the only
cue left, and it is still one. Its transcripts name no benchmark, no issue
behind a bug and no trigger test beyond one generic method name (§3.10), which
shows that no agent announced a recollection, not that none had one. The probe
is also a single sample per bug, from one model at one point in time.

Replication on faults postdating the model's training cutoff is the stronger
check, and ours does not deliver it. GitBug-Java, the obvious candidate, no
longer serves: its bugs come from 2023 commit histories, selected in early
2024 precisely because that postdated the then-current cutoffs. We mined two
small corpora and ran them twice. The first runs (§3.8) had the fix commit
within the agent's reach and lost one arm of one corpus to a harness error.
The third campaign (§3.11) ran all 28 subjects under the second campaign's
controls and a protocol fixed beforehand. Its hypothesis is not rejected: 35%
against 22% over 23 pairs, three faults detected by the implementation-visible
arm alone and none by the other, *p* = 0.25, with an interval for the
difference from 0 to 26 points. So the effect this paper rests on is
established on Defects4J and not on faults the model cannot have seen. The
gap on the post-cutoff subjects is narrower than on Defects4J by 25 points,
with an interval that excludes zero, and the corpora differ in project, kind
of fault and build as well as in date, so that difference cannot be assigned
to recall. Nor can recall be excluded as a part of the Defects4J effect. A
post-cutoff corpus several times this size, matched to the Defects4J sample,
is what the question needs.

**The sandbox enforced less than its settings were meant to.** The third
campaign's audit found that the directory the harness gives commands for
temporary files is the host's own, shared by every run, and that the operating
system carries old released jars of two of that campaign's three projects where
an agent could read them (§3.11). The second campaign ran under the same
settings on the same machine. During the third campaign the shared directory
also held the developers' tests for each fix, left there by the preparation of
the campaign. The transcripts record every command and every result, and in
neither campaign does one show an agent listing that directory, reading a file
there that it had not just written, or opening one of those jars. That is
evidence about what the agents did, from a complete record. It is not the
isolation the design intended, and a run of ours that had used either would
have been caught by the audit and not prevented by the sandbox. A check made
after the third campaign, with its settings and no model in the loop, confirmed
both: a sandboxed command lists and reads that directory, and reads those jars.
Settings under which it does neither are in the repository with that check
(`bin/agent-sandbox.py`), for any later run. No run reported here used them.

**The tooling produced wrong figures without flagging them.** A table whose
column was named `mut_killed` counted unexecuted mutants; a build that failed
a licence audit was recorded as a detected fault; a line count doubled the
tests of six suites; six suites that never ran were counted as failing to
detect. Each was found by an audit of the artifact rather than by the
pipeline. The figures reported here are the audited ones, but the pattern is a
threat in itself: figures that have not been traced back to raw output should
be read with that in mind. `bin/report-figures.py` regenerates every figure in
§3 so that they can be.

### 5.2 Construct validity

**Fault detection is binary and coarse.** Defects4J classifies a suite as
detecting the fault when it passes on the fixed revision and at least one test
fails on the buggy one. A suite that detects the fault through twelve tests and
one that detects it through a single incidental assertion score identically.
In the second campaign 16 of the 22 M2 detections and 6 of the 7 S2 detections
rest on one failing test. The measure also cannot distinguish detection from
an accidental sensitivity to something the fix happened to change. And a suite
that does not compile against the buggy revision, because it uses something
the fix added, is `Broken` rather than detecting: two Defects4J suites of the
first campaign (§2.9), both Cli-21 suites of the second (§3.10), one
post-cutoff suite of the earlier runs (§3.8) and both suites of one subject
of the third campaign (§3.11) are in that position.

**Javadoc is not an independent specification.** The S arm's oracle is
documentation written by the same developers as the code, and sometimes derived
from it. It is a proxy for "an oracle not read off the implementation", and a
weak one. A genuinely independent specification — a requirements document, a
standard, a second implementation — might behave differently in either
direction.

**Mutation score is measured over the classes the fix modifies**, which is
Defects4J's default scope. A wider scope would change the absolute figures,
though there is no obvious reason it would change the between-arm comparison.

**The mutation and coverage figures are pooled.** Averaged per suite instead,
the two arms of the first campaign are at 67.6% and 48.5% rather than 58% and
44%, and those of the second at 64.3% and 45.3% rather than 54% and 39%: the
direction and the per-bug consistency are the same and the gap is larger. The
near-tie between EvoSuite and the first campaign's specification-only suites
changes sign (§3.5), which is why we call it a tie.

**Line coverage is not reliable for every subject.** For Csv-4 the
implementation-visible and EvoSuite suites are credited with 28% and 21% of the
lines of `CSVParser` while executing 93% and 94% of its mutants. The two
measurements cannot both be right for that class, and we have not found which
is wrong.

### 5.3 External validity

**One model family, one harness.** Claude Sonnet 5 throughout, with six Opus 5
suites reported separately. Nothing here establishes that the effect
generalises to other models or other agent scaffolding.

**One language, and a narrow slice of it.** Java, and four library projects —
three of them Apache Commons, so sharing an ecosystem, a coding style and a
documentation culture. Gson is the only outlier. Application code, which
frequently has neither a public API nor javadoc, is not represented; the S-arm
condition may not even be constructible there.

**Defects4J faults are unrepresentative by construction.** Each is
reproducible, isolated from unrelated changes, minimised, and — critically —
had a test written for it by a developer. Faults that were never caught, or
never cleanly isolated, are absent from the corpus by definition.

**Unit-level only.** Nothing here speaks to integration or system tests, where
an agent's access to the implementation may matter differently.

### 5.4 Conclusion validity

**One run per bug per arm, in each campaign.** LLM output is stochastic and no
variance estimate was collected; the figures carry no confidence interval
attributable to sampling the model, and the bootstrap intervals of §3.10 and
§3.11 resample bugs, not runs. Repeated runs would be the standard remedy and
were not affordable at roughly $1 per suite across 80 suites. The two Defects4J
campaigns are the nearest thing to a repetition, under conditions that differ:
the implementation-visible arms detect 26 and 20 of the same 36 bugs with 20 in
common, and the specification-only arms six and seven of 37 with four in
common. The effect, three-fold in the second campaign and five-fold in the
first, is large relative to any plausible run-to-run variation, but this is an
argument, not a measurement. In the first campaign, where a run was lost to an
infrastructure failure it was repeated (§3.6), so a few suites are a second
draw; that is not a replication, and the first draws were not kept. In the
second and the third no run was repeated.

**The first campaign's comparison had no analysis fixed in advance; the
second's had.** In the first campaign only the first arm had a decision rule.
A threshold was written down before the M arm was run:
detection below 25% with high coverage would confirm the working hypothesis,
above 60% would mean the hypothesis was wrong and the study should be
rethought. The M arm returned 72%, crossing the second threshold, and the study
was in fact redirected — the specification-only arm was designed in response.
The rule is reported here because it functioned as intended, including when it
contradicted the hypothesis that motivated the work. Two limits on what it
shows. It was not committed to the repository before data collection, so it
cannot be verified from the artifact. And it covers the M arm's detection rate
only: the first campaign's contrast between arms was designed after that rate
was known, and its analysis — the pairing, the exact test, the choice of
metrics — was not specified beforehand. The second campaign's hypotheses,
tests, exclusions and decision rule are in a protocol committed before its
first run (§2.10), and the repository's history shows the order: protocol,
runs, audit, measurement, analysis. The same holds for the third campaign
(§2.11).

**The tests describe consistency of direction, not effect size in a
population.** The *p* values of §3.1 and §3.10 say the asymmetry between the
arms is very unlikely under the null; they say nothing about how large the gap
would be in a different corpus. The third campaign is a different corpus, and
there the gap is 13 points, with an interval from 0 to 26 (§3.11). The
interval for H2, 12 to 59 points, is wide. It supports the statement that
detection falls further than mutation score and gives little hold on by how
much. H2 was tested on Defects4J alone: the third campaign measures no
mutation score.

## 6. Related work

All figures below were checked against the bodies of the papers themselves,
not against abstracts or search results.

### The regression evaluation setting was already named

Dinella, Ryan, Mytkowicz and Lahiri, *"TOGA: A Neural Method for Test Oracle
Generation"* (ICSE 2022) state the problem this paper quantifies. Their framing
of the oracle task is that synthesising a functional oracle "must capture the
intended functionality rather than the implemented functionality", and they
explicitly set their evaluation apart from the standard one:

> "It is important to note that our evaluation setting is fundamentally
> different from the regression evaluation setting in which the Defects4J
> benchmark is most often used. In a regression evaluation, tests are generated
> on the fixed program version and evaluated on the buggy version. Regression
> studies of randomized test generation tools report finding larger numbers of
> bugs than in our setting as they use regression assumptions to generate higher
> quality oracles [25]. In our setting where tests are generated on the buggy program
> version, regression test oracles will not find bugs as they assume the
> observed buggy behavior is correct."

**The artifact is therefore not our discovery, and we do not claim it.** What
this paper adds is the magnitude — 56% against 18% on the same bugs with the
same agent under controlled conditions, and 72% against 14% on standard
checkouts — measured in the agentic setting rather than argued for
neural-oracle inference over EvoSuite prefixes, and the demonstration that the
metrics ordinarily reported alongside detection register only a fraction of
it.

Hossain, Filieri, Dwyer, Elbaum and Visser, *"Neural-Based Test Oracle
Generation: A Large-Scale Evaluation and Lessons Learned"* (ESEC/FSE 2023)
replicate and extend TOGA over 25 Java systems, 223.5K test cases and 51K
injected faults. TOGA's reported accuracy does not survive the extension. Where
the original reports 69% for assertion-oracle inference and 86% for exceptional
oracles on its held-out test sets, they measure 52% and 75% on their own,
larger dataset. TOGA declines to emit any assertion in 62% of the cases where
it correctly predicts one is needed, and more than 47% of the assertions it
does emit are false positives. On their mutation-based measure, EvoSuite's
suites kill 30,411 of 51,385 mutants, 20,597 of them with no explicit
assertion, and TOGA's assertions add 105, which they report as 0.3%.

Two points carry over to our setting. The first is the caution: a result that
looks strong on the test set it was developed against need not survive a
broader evaluation, which is the same concern as ours approached from the other
side. The second is that TOGA, in Hossain et al.'s words, "is designed to
leverage natural language specifications (docstrings)" — the same source of
truth as our specification-only arm, four years earlier and with a far smaller
model. TOGA's own paper treats the docstring as optional context.

### Documentation in place of the method's code

Hossain, Taylor and Dwyer, *"Doc2OracLL: Investigating the Impact of
Documentation on LLM-based Test Oracle Generation"* (FSE 2025;
arXiv:2412.09360) put to oracle generation the question nearest to ours: what
a method's Javadoc is worth as the source of an oracle, alone and beside the
method's code. Their reason for asking is the mechanism of §4.1. When the
implementation is in the model's input, "if the implementation contains a bug,
the model may encode that buggy behavior into the oracle, resulting in an
inappropriately passing test case", and more generally "this approach tends to
generate oracles that are primarily useful in a regression context". Their
opening example is a Joda-Time method that returns `null` for a time-zone id
it does not recognise, where its Javadoc promises an
`IllegalArgumentException`: the oracle generated from the code expects what
the code does, and the one generated from the Javadoc expects the exception.

Ten code models of 110 million to 7 billion parameters are fine-tuned to
complete a given test prefix with one oracle, an assertion or an expected
exception. Six prompts form three pairs that differ only in whether the
Javadoc is present: the prefix alone, the prefix with the method's signature,
and the prefix with the method's code. The data are the 55,575 samples, of the
140,514 they draw from the SF110 benchmark, whose method has Javadoc. Accuracy
is exact match with the dataset's oracle. Averaged over the ten models it is
58.0% from the prefix alone, 78.1% with the Javadoc added, 79.9% with the
method's code and no Javadoc, and 80.8% with both. An ablation puts most of
the Javadoc's value in its description and its `@return` tag: with both
removed, accuracy on the prompt with the prefix and the Javadoc falls from
78.4% to 54.1% (their Table 2).

For detection the fine-tuned models are run on Defects4J: 374 input samples,
as in the earlier work they compare with, each a test prefix, a method and its
Javadoc, with one oracle generated per sample and the resulting test run on
the buggy and the fixed version. For the 86 samples whose method has no
Javadoc, GPT-3.5 wrote one from the method's implementation. Three models are
taken through four prompts. From the prefix alone they detect 58 to 62 bugs;
with the Javadoc added, 63 to 68; with the method's code in its place, 62 to
68; with both, 63 to 73. The authors' conclusion is that "Javadoc comments
alone can encode sufficient contextual information to potentially replace the
MUT code".

In our data the documentation does not replace the code: the
specification-only agent detects a third of what the implementation-visible
agent does. The two results are not in conflict, because the code is put to
different uses in the two designs. In theirs a model reads the text of one
method and predicts an assertion. It runs nothing. Read in that way the code
adds little to detection, and so does the documentation: the prefix alone
accounts for 58 to 62 of the bugs, the method's code adds between none and ten
to that, and the Javadoc between five and eight. In ours the
implementation-visible agent runs its tests on the repaired code and is told
to finish when they pass, so its expectations are observed and not predicted.
That is the regression oracle in the strict sense, and it is what our 56%
measures. Their inputs are also fixed, every prompt completing the same
prefix, so that their conditions differ in one assertion. Our agents choose
the inputs as well, for a whole class, and the specification-only agent has to
find from the documentation the input that reaches the fault.

Three things limit how far their comparison can be set beside ours. The paper
does not state which revision the code in its own prompts is taken from; it
says of TOGA that it uses the fixed one, and that its own best figure is
obtained "when the same input information is used". For 86 of the 374 samples
the Javadoc was itself written from the implementation, which is the
dependence §5.2 declares for our javadoc, in a stronger form. And detection is
reported as a count of bugs, without the number of bugs the 374 samples can
reach, so it gives no rate to put in the table below. Nor are coverage and
mutation score measured, so the comparison this paper tests cannot be made on
their data.

What they find about the documentation itself is in line with what our
specification-only arm detects (§3.3, §4.4). Of the 900 cases they read in
which adding the Javadoc produced the dataset's oracle, 65.6% are ones where
it states what the method returns. Of the 144 incorrect oracles it produced
where the prompt without it had been right, 55.6% come with Javadoc they class
as vague or incomplete. Documentation supports an oracle where it states the
contract, in their models as in our agent.

That is a finding about what a method returns. For what it throws, the same
group has since found that the stated contract makes no measurable difference
to models of this kind. Hossain, Dwyer and Tasnim, *"Documentation vs. Code
Patterns: What Drives LLM-Based Exception Oracle Generation?"* (ASE 2026;
arXiv:2608.00884) run three released systems, TOGA, TOGLL and Doc2OracLL with
its 7-billion-parameter model, on a test prefix, the method under test and its
Javadoc, and measure one decision: over the instances whose oracle in the
dataset is an expected exception, the share for which the system predicts an
exception and not an assertion. On OE25, which they cite to the 2023
evaluation above (25 systems, 223,557 samples, EvoSuite's prefixes), TOGLL is
at 99.98%, Doc2OracLL at 99.7% and TOGA at 18.66%. On OE25dev, which the paper
contributes, they are at 100%, 91.55% and 36.36%. It is drawn from the tests
that the developers of the same 25 systems wrote: 77,299 instances, of which
2,899 must throw.

Removing every `@throws` and `@exception` clause from the Javadoc, and nothing
else, lowers accuracy by at most 0.16 points, for any system on any benchmark,
SF110 included. Such a clause was present in 17% to 59% of the exception
samples, according to system and benchmark, and among those alone the largest
fall is 0.54 points. (The falls are computed from baselines that differ in the
second decimal from the ones in the paper's first table, quoted above: 99.75%
where that table has 99.7%, in the case of the largest fall. The paper does
not say why.) The earlier paper's ablation had found the same of the `@throws`
tag on its own measure, a cost of less than one point on average, and
concluded that the tag could be omitted. This one draws the other conclusion:
"High exception-oracle accuracy is insufficient when models remain accurate
after removing `@throws`/`@exception` clauses, the documentation signal that
states when and why an exception should be thrown."

The rest of the paper asks what the predictions do rest on. The tokens of an
input are ranked by gradient-times-input attribution and replaced by a
placeholder, one at a time, until the prediction is no longer an exception.
For TOGLL on OE25, with attribution taken at a middle layer, 96.89% of 19,805
correct predictions change within thirty replacements, and half of those
within four. The token whose replacement changes the prediction is a line
break in 82.42% of the cases, and in 97.81% it is of the kind the paper
classes as structural: layout, punctuation, braces and comment markers. In
0.13% it is a token the paper classes as exception-related. On the developers'
tests the structural share is 93.61%. Doc2OracLL differs. About nine in ten of
its predictions change as well, within a budget of 500 replacements, but only
once about 90% of the replaceable tokens are gone, and three quarters of the
tokens that change them are not structural. The authors do not claim those as
evidence of an exception: "many non-structural tokens are uncategorized
lexical cues rather than clearly exception-triggering evidence".

None of this measures what our arms measure. No test is run and no fault is
involved: the authors list what the measure leaves out as "semantic
equivalence, compilability, oracle style, exact exception type, or bug-finding
usefulness". It is taken on the instances labelled as exceptions alone, so an
exception predicted where the dataset has an assertion does not count against
a system. TOGLL and Doc2OracLL are run on "the test prefix, method under test
(MUT), and documentation", so the experiment has no documentation-only
condition: it shows a clause going unused where the method, which the paper
also calls the focal code, and the prefix are present, not what a generator
does with the documentation alone. And the systems are fine-tuned models of
110 million to 7 billion parameters, run as released. The authors note that
they do not evaluate "proprietary API models or larger instruction-tuned
models, which may rely on different signals"; our agent is built on one of
those.

We cite the paper for two reasons. It qualifies the reading of the result
above: that these models complete an oracle about as accurately from the
Javadoc as from the code does not show, for the oracles that expect an
exception, that they used what the Javadoc says. And it makes for a model's
prediction the argument that §4.2 makes for a suite's scores, that a figure
can be high and stable without registering where the expectation came from.
Their remedy is to verify of a prediction whether it "follows from meaningful
exception evidence rather than shortcut cues"; ours, in §4.5, is to generate
with and without the implementation and compare.

### Error propagation in code-then-test workflows

Konstantinou, Tambon and Papadakis, *"On the risk of coding before testing: An
empirical study on LLM-based test generation workflow"* (arXiv:2607.05139)
study the complementary condition. Their pipeline generates candidate
implementations with an LLM, retains only the faulty ones — "we discard the
cases that the model is generating correct code and keep only those that are
faulty" — and compares test suites generated with that faulty implementation in
view against suites generated from the task description alone. Tests generated
after faulty code detect 14% of faults against 25% for tests generated
independently; adding the implementation to the task description reduces
detection by 9.1% to 18.2% across five models, figures the paper gives without
saying whether they are percentage points. They name the phenomenon *error
propagation*.

Their subjects are HumanEval+, MBPP and BigCodeBench: Python programming tasks
with LLM-generated faults, and their specification is the benchmark's
natural-language task description. They measure fault detection and statement
coverage — finding "no consistent relationship between statement coverage and
fault detection", which independently corroborates part of our result on a
different language, corpus and set of models — but not mutation score.

We also adopt their distinction between **fault triggering**, where the test
provokes behaviour differing from the reference, and **fault detection**, which
additionally requires the assertion to be correct. Our harness reports
detection only.

Huang, Zhang, Harman, Du and Cui, *"Measuring the Influence of Incorrect Code
on Test Generation"* (arXiv:2409.09464) had measured the effect of incorrect
code earlier, and over more conditions. Eleven models write tests for
HumanEval, MBPP and APPS tasks from five prompts: the task description alone,
the description with a correct solution, the description with an incorrect
one, and each solution without the description. The incorrect solutions are
ones the models themselves produced. Counting every generated test that
passes on the correct solution, the tests written from the description and
the correct solution detect 47.4% of the faulty solutions the authors
collect; with the incorrect solution in its place, 38.1%; from the correct
solution without the description, 35.5%. A second experiment uses real code
and no description: 10 tasks from BugsInPy and 31 from SWE-Bench, the ones
among 993 for which a correct test was generated from either version.
Averaged over the models, and counting only suites in which every test passes
on the patched code, tests written from the patched code detect 13.5% of
those bugs and tests written from the pre-patch code 7.1% (35.3% and 31.0%
when each passing test counts). That pair is the regression evaluation
setting beside its alternative: the difference Dinella et al. had stated,
measured for models that are handed the code in a prompt.

Two of their results bear on ours. The first is what a specification is worth
when it is complete. Their description alone detects 40.6% (the mean of the
three datasets in their Table 5), a seventh less than the description with
the correct solution and more than the correct solution alone. Our
specification is the partial documentation of a real library, and withholding
the code there costs two thirds of the detections. Both fit the reading of
§4.3, that what counts is how usable an oracle the generator is given. The
second is the nearest published figure to the certification rate of §4.6, and
is quoted there. They measure test accuracy and line coverage besides
detection, and not mutation score, so the comparison this paper tests cannot
be made on their data.

### Tests written before the fix exists

Ahmed, Hirzel, Pan, Shinnar and Sinha, *"TDD-Bench Verified: Can LLMs Generate
Tests for Issues Before They Get Resolved?"* (arXiv:2412.02883, IBM Research)
build a benchmark of 449 issues mined from GitHub and measure *fail-to-pass*
rate — a test that fails before the issue is resolved and passes after — which
is the same criterion as the `Fail` classification used here. Their Auto-TDD
takes an issue description plus the codebase *prior* to resolution; its best
result is 23.6% with GPT-4o on their benchmark.

The comparison point closest to our setting is one they cite rather than one
they run: LIBRO, prompted with Defects4J issues, reaches **19.9% fail-to-pass
at pass@1** (33% at pass@50, i.e. fifty attempts per issue), and Plein et al.,
also on Defects4J issues, reach 6% with ChatGPT. Same benchmark family as ours,
a single attempt, and the model is given a natural-language description of what
is wrong — which our specification-only arm is not.

### Six conditions side by side

| oracle available to the agent | detection | source |
|---|---|---|
| natural-language task description | 25% | Konstantinou et al. |
| issue description + pre-fix codebase | 19.9% (pass@1) | LIBRO on Defects4J, via TDD-Bench Verified |
| partial API documentation (javadoc) | 18% | this work, second campaign (14% in the first) |
| task description + faulty implementation | 14% | Konstantinou et al. |
| **repaired implementation** | **56%** | this work, second campaign |
| **repaired implementation, in a standard Defects4J checkout** | **72%** | this work, first campaign |

The figures are not directly comparable — different corpora, languages, models
and fault distributions. The ordering is the point, and the last two rows are
the ones that concern evaluation methodology rather than development practice.

### Coverage and mutants as proxies

Inozemtseva and Holmes, *"Coverage Is Not Strongly Correlated with Test Suite
Effectiveness"* (ICSE 2014), generated 31,000 suites over five Java systems and
found only a low to moderate correlation between coverage and effectiveness
once suite size is controlled for, and that stronger coverage criteria add no
insight. Note that they operationalise effectiveness as **mutation score**, not
as real-fault detection; their result therefore concerns the relationship
between two proxies, and is consistent with what we observe across populations,
where EvoSuite and the implementation-visible suites have the same coverage and
mutation scores eleven points apart in the first campaign and seven in the
second.

Just, Jalali, Inozemtseva, Ernst, Holmes and Fraser, *"Are Mutants a Valid
Substitute for Real Faults in Software Testing?"* (FSE 2014), examined 357 real
faults in five applications totalling 321,000 lines. They report that 73% of
real faults are coupled to mutants from commonly used operators, that 17% are
coupled to no mutant at all — mostly faults involving algorithmic changes or
code deletion — and that mutation score correlates positively with real-fault
detection independently of coverage, and more strongly than statement coverage
does (significantly so in four of their five subjects).

**Our result is consistent with theirs, and adds a qualification.** Just et al.
hold the source of the oracle fixed and vary suite *strength*: for a given
fault they compare the automatically generated suites that detect it against
those that do not, within the same program, and the detecting suites have
significantly higher mutation scores (in 182 of 194 faults, summing their
Table 5 with coverage controlled; mean Â₁₂ per subject between 0.66 and 0.81).
Every suite in their study — developer-written, or generated by EvoSuite,
Randoop or JCrasher — derives its expectations from the implementation it is
run against.

In our data the direction is the same: the arm with the higher mutation score
detects more faults. What we vary is the *information available to the
generator*, and along that axis the size of a difference in mutation score says
little about the size of the difference in detection: a loss of 28% against
one of 65% between the arms of the second campaign and, in the first, almost
nothing against a factor of three between EvoSuite and the specification-only
suites. Mutation score is a sound proxy
when strength is what varies between the suites compared, which is the setting
Just et al. establish. When provenance varies as well it is a much looser one,
a setting their design could not surface because no suite in it had an oracle
independent of the code.

Zhao, Zhou and Cohen, *"Do Coverage and Mutation Scores of LLM-Generated Test
Suites Correlate with Their Effectiveness? (Replicability Study)"* (ISSTA
2026; arXiv:2607.22880) repeat two analyses for suites written by language
models on Defects4J: that of Inozemtseva and Holmes, and that of Papadakis,
Shin, Yoo and Bae, *"Are Mutation Scores Correlated with Real Fault
Detection? A Large Scale Empirical Study on the Relationship Between Mutants
and Real Faults"* (ICSE 2018). Thirteen configurations of eleven models are
prompted with a method that a fix changes and the code around it, for 318
methods from all 17 projects, once with the fixed version and once with the
buggy one: 8,268 suites and 101,123 tests. Coverage is measured with
CodeCover and mutation score with PIT, both per method. The unit is a method
and a single prompt, where ours is a class and an agent.

For the suites generated from the fixed version, they find the proxies
informative across models and not within one. Over the thirteen
configurations, the share of bugs detected correlates with raw mutation score
at *r* = 0.86 when scores are averaged over methods and 0.62 when they are
pooled, and with average branch coverage at 0.86; among the suites of a
single model the correlations are weak. Their raw score is the one we report,
and their two aggregations are our per-suite mean and our pooled figure. For
the suites generated from the buggy version, coverage and detection are
weakly correlated in every view, and they hold mutation analysis
inapplicable: it needs a suite that passes on the code under test, which
"would exclude precisely the tests that expose the bug". They conclude that
coverage and mutation score are usable for comparing models when the code
given to the model can be assumed correct and the aim is regression testing,
and not when that code may be faulty.

The two results fit together. Where they find mutation score a good guide,
every generator has read the same repaired method and the generators differ
in how thoroughly they pin it down, which is the axis on which Just et al.
validated the metric. A correlation over such generators orders them. It does
not say what a difference in mutation score is worth in detection once the
generators differ in what they were given to read, and that is what our arms
measure. Their Figure 4 shows the mechanism of §4.1 in one example: for
Lang-14, the same model asserts that a `String` and a `StringBuilder` holding
the same characters are equal when it is shown the fixed method, and that
they are not when it is shown the buggy one.

Both of their conditions keep an implementation in the prompt. The setting
without one they leave to future work — "black-box or specification-based
settings, where models generate tests from natural-language specifications,
docstrings, or other behavioral descriptions without access to the
implementation" — and our specification-only arm is such a setting. Its
suites are still accepted and mutated on the fixed revision, so a mutation
score exists on both sides of the change in where the expectations come from.
Their buggy-input condition could not provide that, and it is the comparison
this paper tests.

## 7. Conclusion

An agent asked to write tests for existing code will encode that code's
behaviour as the expected behaviour. Evaluating it on the repaired revision of
a known fault therefore measures, in large part, how well it transcribes a
repair it was handed. On 39 real faults, with the benchmark's own files out of
the working copy, the conditions enforced and the analysis fixed beforehand,
withholding the implementation and supplying only its documentation drops
detection from 56% to 18%.

The metrics around that number move in the same direction and nowhere near as
far. Mutation score falls from 54% to 39% and coverage from 84% to 70%.
Detection loses two thirds of its value and mutation score a little over a
quarter, and the difference between the two losses is above zero with 95%
confidence, by a test fixed before the runs. A suite's assertions can be
strong while its expectations were copied from the program they are meant to
judge, and the scores reflect the difference only in part.

A first campaign, on Defects4J checkouts as they come, had given 72% against
14%. The benchmark's own files name each bug and the tests that expose it, and
the agent read them; without them it detects six fewer of thirty-six faults.
In that campaign only a prompt kept the specification-only agent from the
compiled classes. In the second, where a sandbox did, more than half of the
agents tried.

A third campaign took the second's conditions to 28 faults fixed after the
model's training data ends. Over the 23 with a verdict in both arms and no
excluded run, the arms detect 35% and 22%. Every fault the specification-only
arm detects, the other detects too, with three more, and the test fixed
beforehand does not reject (*p* = 0.25). The effect is established on
Defects4J and not beyond it. The gap is narrower on the newer faults, in a
corpus that differs from Defects4J in more than their date, and we cannot say
how much of the Defects4J figure is recall that the source cues. That
campaign's audit also found the sandbox leaving a shared directory open,
which only the transcripts show that no agent used: a sandbox's settings are
a claim, and the record of what the agents did is the check on it.

The immediate consequence is for evaluation: figures reported for generated
suites on real-fault benchmarks should state what the generator was allowed to
read — which on Defects4J is more than the source tree suggests — and what
stopped it reading more, and should not be read as capability without both.
The longer consequence is for tooling.
Mutation feedback sees only a fraction of the difference, so closing the
generation loop on it optimises a weak proxy. The only mechanism our data
supports for separating the two cases is the counterfactual — generate twice,
with and without the implementation, and compare — which we have measured but
not built.

## Data availability

Everything is in **https://github.com/sergiparpal/mutation-study**, under MIT
for the code and CC BY 4.0 for the data.

Generation: `bin/run-agent-suites.sh` (implementation-visible arm),
`bin/run-spec-suites.sh` (specification-only arm, including sandbox
construction) and `bin/prune-failing-tests.py` (the per-method acceptance
filter). The search-based baseline was produced with Defects4J's own
`gen_tests.pl`; that invocation was not scripted (§2.7). Measurement:
`bin/analyze-agent-suites.sh`, which wraps `run_bug_detection.pl`,
`run_coverage.pl` and `run_mutation.pl`, and `bin/merge-agent-metrics.py`,
which merges their tables and recomputes the mutation columns from Major's
per-mutant output. `bin/remeasure-cli-evosuite.sh` repeats the measurement of
the five EvoSuite suites of §2.7 with Defects4J's JUnit path corrected; its
output is kept apart from Defects4J's own tables, and the merged file marks
the rows taken from it. The post-cutoff corpora are mined by
`bin/mine-postcutoff.sh`, run by `bin/run-postcutoff.sh` and tallied from their
logs by `bin/tally-postcutoff.py`.

The second campaign has its own scripts, all but the last committed before its
runs: `bin/generate-suites.sh`, which builds both working copies and the
sandbox settings and runs the agent; `bin/run-campaign2.sh`, which fixes the
order of the runs; `bin/audit-transcripts.py`; and `bin/analyze-campaign2.py`,
the analysis. `bin/describe-campaign2.py`, written after the runs, prints the
descriptive figures of §3.10. The protocol is `data/campaign2/PROTOCOL.md`.

The third campaign's scripts were committed with its protocol
(`data/campaign3/PROTOCOL.md`) before its runs: `bin/generate-postcutoff.sh`,
`bin/run-campaign3.sh`, `bin/audit-campaign3.py`, `bin/measure-campaign3.sh`,
`bin/analyze-campaign3.py`, `bin/campaign3-lib.sh` and
`bin/AgentTestRunner.java`, the runner used in the agent's script, at
acceptance and at measurement. `bin/describe-campaign3.py`, written after the
runs, prints the descriptive figures of §3.11. `bin/agent-sandbox.py`, also
written after them, holds sandbox settings that give each run a temporary
directory of its own and hide the operating system's jars, and a check of
what a sandboxed command can reach that calls no model; what it prints under
those settings and under the campaigns' own is in `data/sandbox/`.

Raw artifacts are under `data/`. For the first campaign: one directory per arm
holding, for each bug, the record of the run (its closing message, cost and
turn count, not a transcript) and the intermediate logs; the packaged suites;
and the merged per-suite measurements in `data/agent-metrics-final.csv`. The
notes three runs left in the agent's memory are in `data/agent-notes/`. The
specification-only sandboxes were kept on the generating machine as an audit
trail and are not in the repository. For the second campaign, under
`data/campaign2/`: for every run, the complete transcript, the prompt, the
sandbox settings and, in S2, the javadoc the agent was given; the packaged
suites; the audit's output and the list of violations, with the reason for
each decision; Defects4J's tables and logs; and the analysis as the script
printed it. For the post-cutoff corpora the build logs are archived and the
generated tests are not. For the third campaign, under `data/campaign3/`: the
same record of every run as for the second; the suites as the agents wrote
them, with the list of tests left out at acceptance; the audit's output, the
list of violations and the list of direct compiler calls, with the reason for
each decision; the log of every build, compilation and run of the
measurement, and its table of verdicts; and the analysis as the script
printed it. The method record, including the deviations and tooling failures
encountered, is in `data/README.md`.

**The figures need neither model access nor a Defects4J installation.**
`bin/report-figures.py` recomputes every figure in §3 from the files under
`data/`, and `bin/audit-trigger-leaks.py` the evidence of §3.9. Re-measuring
from the packaged suites in `data/agent-suites/` and `data/campaign2/suites/`
needs Defects4J (`bin/analyze-agent-suites.sh`). Re-measuring those in
`data/campaign3/suites/` needs clones of the three upstream repositories,
Java 11, and Maven with the projects' dependencies in its local repository
(`bin/measure-campaign3.sh`). Regenerating the suites needs the model.

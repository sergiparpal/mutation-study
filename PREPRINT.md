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
conditions. In the implementation-visible arm the agent works inside the
checked-out project; in the specification-only arm it works in a sandbox with
generated javadoc and a compiled jar, sees no source, and may not execute its
tests. Over 36 bugs from four Java projects measured in both arms, real-fault
detection falls from **72% to 14%**. Every fault the specification-only suites
catch is also caught by the implementation-visible suites and none the other
way round (exact McNemar, *p* = 9.5 × 10⁻⁷).

**The metrics ordinarily reported alongside detection move far less.** Mutation
score falls from 58% to 44% and line coverage from 85% to 73%: a quarter and a
seventh, against four fifths for detection. An EvoSuite baseline over the same
subjects shows the same thing from another side. EvoSuite and the
specification-only suites are within a few points of each other on mutation
score, 48% and 44%, while EvoSuite detects three times as many faults, 41%
against 14%; and EvoSuite matches the implementation-visible suites on
coverage, 85% against 84%, while detecting 41% against 69%.

Mutation score and coverage measure how much of a program a suite exercises
and how hard it checks what it exercises. Neither measures where the expected
values came from, and across these populations that is what detection follows.
This bears on how agent-written suites are evaluated, and on proposals to
improve them by feeding mutation results back to the generating agent — a loop
that optimises a quantity only loosely tied to the distinction.

Three further observations. Writing tests from javadoc alone yields wrong
expectations in only 3.6% of tests, so the specification-only arm is not
guesswork: it catches a small set of faults — five of thirty-six — three of
which violate a contract the documentation states. The agent and EvoSuite are
complementary rather than ordered — 12 faults are found only by the agent, 4
only by EvoSuite, 5 by neither. And contamination, which we measured and did
not eliminate. Defects4J checkouts ship the fix commit in their git history,
subject line included, which we remove before generation. They also carry
Defects4J's own metadata, naming the bug and its trigger tests, which we did
not remove: in eleven of the implementation-visible arm's twenty-six detections
the suite or the agent's closing report shows it knew one or the other. A
direct probe of what the model recalls with no code in context finds benchmark
identifiers unmemorised and at least two of the forty faults recalled with
their mechanism.

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
arm it works inside the checked-out project at the fixed revision. In the
**specification-only** arm it works in a sandbox containing generated javadoc
and a compiled jar, never sees source, and may not execute its tests. The
conditions differ in more than that one thing, some of it by design and some by
oversight; §5.1 lists every difference we know of.

Over 36 bugs measured in both arms, real-fault detection falls from **72% to
14%**. Every fault the specification-only suites catch is also caught by the
implementation-visible suites; none is caught only by the former. An exact
McNemar test on the 21 discordant pairs gives *p* = 9.5 × 10⁻⁷.

**The usual metrics move, but far less.** Mutation score falls from 58% to 44%
and line coverage from 85% to 73%, against a five-fold fall in detection. An
EvoSuite baseline over the same subjects shows how loosely either metric tracks
detection once the source of the expectations varies. EvoSuite and the
specification-only suites have nearly the same mutation score (48% and 44%)
and detection rates of 41% and 14%; EvoSuite and the implementation-visible
suites have the same coverage (85% and 84%) and detection rates of 41% and 69%.
The specification-only suites are weaker than the implementation-visible ones
on every count, but not by anything like a factor of five. What differs most is
where their expectations came from.

Contributions:

1. A controlled measurement of how much of an agent's apparent fault-detection
   ability on Defects4J depends on what the standard protocol puts in front of
   it — the repaired implementation above all — on real faults from four real
   projects: roughly four fifths of it. That the regression evaluation setting
   flatters generated suites is not a new observation — Dinella et al. state it
   in 2022 (§6) — but to our knowledge it has not been quantified for an agent
   that reads the codebase.
2. The finding that the metrics reported alongside detection register far less
   of the difference than detection does: mutation score falls from 58% to 44%
   and line coverage from 85% to 73%, against a five-fold gap in detection.
   This bears directly on how agent-written suites are currently evaluated and
   on proposals to use mutation feedback to improve them.
3. A characterisation of what specification-only generation does catch: five
   faults, three of which violate a contract the javadoc states and two of
   which are reached by probing boundaries. The classification was not blind
   and is reported as a description, not as a predictor.
4. An EvoSuite baseline over the same subjects, which shows the two approaches
   to be complementary rather than ordered — 12 faults are found only by the
   agent, 4 only by EvoSuite — and which sits next to the specification-only
   suites on mutation score while detecting three times as many faults.
5. An account of contamination channels in Defects4J checkouts that appear not
   to be routinely controlled. The checkout ships the fix commit in its git
   history, with a subject line naming the fault; we remove it. It also ships
   Defects4J's own metadata — the bug identifier and the names of the trigger
   tests — and backup copies of developer test classes; we did not remove
   those, found that the agent had used them, and report the evidence (§3.9).
   A direct probe of what the model recalls about each fault with no code in
   context finds at least two of forty recalled with their mechanism.

---

## 2. Method

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

The short forms **M** and **S** are used throughout for the two arms.

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

The agent used at least the first of these; §3.9 gives the evidence. None of
these files exists in the S arm's sandbox, though the sandbox's directory name
carries the bug identifier too.

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

Five bugs are excluded from some or all measurements, and eight further suites
lack a detection verdict or a coverage figure. Cli-21 appears three times: it
is affected by three independent problems.

| Bug | Affected | Reason |
|---|---|---|
| Cli-21, Csv-3 | M, all measurements | Suite extended a test helper from the project's test tree, so it compiles in the working copy but not as a standalone archive. The M prompt did not ask for self-contained classes; the S prompt did (§2.2) |
| Gson-14, Gson-16 | all arms, all measurements | Major's mml compiler rejects the class name: `invalid scope: com.google.gson.internal.$Gson$Types`. EvoSuite's generated suite for the same class does not compile either — `illegal start of expression` on the `$` in the identifier. Two independent tools fail on this one class, which is why we treat it as a tooling limitation rather than a property of the bugs |
| Cli-15, Cli-21 | EvoSuite, all measurements | `gen_tests` produced no output and no log; both are `cli2` subjects, whose declared classpath references jars that the checkout never materialises |
| Cli-10, Cli-12, Cli-17, Cli-28, Cli-32 | EvoSuite, detection and coverage | `Broken`. The suite fails to load in Defects4J's detection harness on both revisions, with `NoClassDefFoundError: org/hamcrest/SelfDescribing`. Defects4J's build file for Cli points the harness at a JUnit jar the framework does not ship, so Hamcrest is on the classpath only where the project itself supplies it, and these revisions ship JUnit 3.8. The same suites run under the mutation harness |
| Csv-16 | EvoSuite, detection | `Broken`. The suite references a class the fix introduces and does not compile against the buggy revision |
| Cli-21 | S, detection | `Broken`. The suite calls an interface method the fix adds — the javadoc the agent wrote from is the fixed revision's — and does not compile against the buggy revision |
| Lang-34 | EvoSuite, coverage | A test fails under the coverage harness |

This leaves 36 M-arm suites and 38 S-arm suites with a mutation score and a
coverage figure, 37 of the latter with a detection verdict, and **36 bugs with
all three measurements in both arms**. All paired figures use those 36.
EvoSuite has 36 suites with a mutation score, 30 with a detection verdict and
30 with a coverage figure; §3.5 compares the three generators on the 29 bugs
where each has a detection verdict.

For Gson-14 and Gson-16 the specification-only suites did yield detection and
coverage figures before the two bugs were set aside (both suites were
classified `Pass`). Those figures are in the repository's history, not in its
final tables, and are omitted so that no arm total mixes suites with and
without a mutation score.

---

## 3. Results

### 3.1 Primary result

Over the 36 bugs measured in both arms:

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
| EvoSuite | 36 | 13/30 (43%) | 47% | 85% |
| M arm, Opus † | 6 | 6/6 | 70% | 89% |

Detection is over the suites with a valid verdict: one S-arm suite and six
EvoSuite suites are `Broken` (§2.9). EvoSuite's coverage is over the 30 suites
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
it and cannot separate it from differences in API complexity.

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
Six of the EvoSuite suites are `Broken`, five of them because Defects4J's
harness cannot load them (§2.9), so the three are compared on the 29 bugs where
each has a valid detection verdict:

| | detection | mutation | coverage |
|---|---|---|---|
| M arm (implementation-visible) | 20/29 (69%) | 57% | 84% |
| EvoSuite | 12/29 (41%) | 48% | 85% |
| S arm (specification-only) | 4/29 (14%) | 44% | 72% |

EvoSuite's coverage is over 28 suites (§2.9). Over all 35 bugs the mutation
scores are 58%, 47% and 44%.

EvoSuite falls between the two arms on detection. It works from the same
repaired implementation as the implementation-visible arm, though not from the
tests, changelog and benchmark metadata that arm could also read (§3.9), so the
gap from 69% to 41% mixes a difference in generator with a difference in
information. The gap from 69% to 14% is between the same generator under the
two conditions.

**The two approaches are complementary, not ordered.** Of the 29 bugs, 8 are
detected by both, 12 by the agent alone, 4 by EvoSuite alone, and 5 by neither
— a union of 24 (83%). A search-based generator that asserts observed behaviour
without interpreting it still reaches four faults that the agent misses.

**Neither metric tracks detection across the three populations.** Mutation
score puts the implementation-visible suites first and the other two close
together: 48% for EvoSuite and 44% for the specification-only suites when
pooled, 47% and 49% — the other way round — when averaged per suite. Their
detection rates are 41% and 14%. Coverage does separate those two, 85% against
72%, but then cannot tell EvoSuite from the implementation-visible suites, 85%
against 84%, whose detection rates are 41% and 69%. On the mutants they
execute, the specification-only suites kill more than EvoSuite's do, 59%
against 54%, and detect a third as many faults.

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
that writes tests from javadoc with a 3.6% error rate invents four confident,
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
alone — the same strict-subset pattern as on Defects4J — but with four
discordant pairs the exact McNemar test gives *p* = 0.125.

**What this does and does not show.** The direction of the effect holds on
faults the model cannot have memorised, and so does the subset relation. Its
size is another matter: the gap is 31 points here against 58 on Defects4J, with
the implementation-visible arm lower and the specification-only arm higher. At
thirteen pairs that difference is well within what chance allows, so this
corpus can neither confirm the Defects4J effect size nor show that
contamination inflated it. It bounds contamination only in the weak sense that
an effect in the same direction survives its removal.

### 3.9 The implementation-visible agent knew which bug it was testing

The controls of §2.4 were meant to give the M-arm agent the repaired code
without telling it what had been repaired. They did not achieve that. No
transcript of the runs was kept — only each run's closing message and the suite
it wrote — so what the agent read cannot be observed. But those two artifacts
show what it knew (`bin/audit-trigger-leaks.py`):

| evidence | bugs |
|---|---|
| A generated test has exactly the developer trigger test's name, and is the test that detects the fault | Cli-12, Cli-17, Csv-4, Csv-6, Lang-13 |
| The closing message names the trigger test | Csv-8, Lang-13, Lang-62 |
| The closing message names its own Defects4J bug: "the Lang-13 regression", "the Lang-52 fix", "the Lang-63 trigger scenario", "the CSV-106 / Csv-5 regression point" | Csv-5, Lang-13, Lang-52, Lang-63; also Csv-14 (not detected) and Cli-21 (excluded) |
| The suite carries the issue number that appears in the trigger test's name, and reproduces that test's input and expected output | Lang-43 |

That is 13 of the 40 M-arm suites, and **11 of the arm's 26 detections**. One
of the six Opus suites, Lang-43's, carries the same issue number. None of the
40 S-arm suites or closing messages shows any of it.

Once the trigger tests' files are deleted, their names survive in one place in
the working copy: `defects4j.build.properties`. The bug identifier is in that
file, in `.defects4j.config` and in the directory name. So for at least these
eleven the agent was not only shown the repair. It was told, by the benchmark's
own bookkeeping, which behaviour the benchmark would test — and "trigger" is
Defects4J's word, not the projects'. Where the agent reproduced a deleted
test's body as well (Lang-13, Lang-43), nothing left in the working copy
contains it; the likeliest source is training data, cued by the name.

This does not change what was measured: 26 of 36 against 5 of 36 under two
conditions. It changes what the first condition is. The M arm is not "the
agent can read the implementation". It is "the agent has a Defects4J checkout",
which is what a standard evaluation gives it, and which leaks more than the
repair. How much of the 72% the metadata accounts for, as opposed to the code,
this study cannot say. The fifteen detections with no such trace are not
thereby shown to be clean, and the eleven with one might have been made from
the code alone.

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
arms isolate the first: the 72% figure for the implementation-visible arm is
not a measure of testing ability but an upper bound produced by the evaluation
protocol itself — by the repaired code and, as §3.9 shows, by more of the
benchmark than the code.

Neither arm establishes what an agent would score against genuinely unknown
code. The specification-only arm's 14% is closer to that question but is not
the answer either, because withholding the implementation removes information a
real developer would have.

### 4.2 What mutation score does and does not register

Mutation score does register the difference between the arms. They are at 58%
and 44%, and the implementation-visible suite scores higher in 35 of 36 bugs.

What it does not register is the size of the difference. Detection falls by
four fifths between the arms. Mutation score falls by a quarter, and half of
that quarter is coverage — code the specification-only suites never execute —
rather than weaker checking of the code they do. A reader shown only the two
mutation scores would expect the suites to differ in fault detection. Nothing
in the scores would lead them to expect 72% against 14%.

This is not a failure of mutation analysis on its own terms, and it does not
contradict the established result that mutation score predicts real-fault
detection (Just et al., FSE 2014; see §6): here, too, the population with the
higher score detects more. Mutation score asks whether a suite's assertions are
strong enough to distinguish the program from small syntactic variants of it.
The specification-only suites are moderately worse at that. They assert on
returned values, exact exception messages and persisted state, and on the code
they reach they kill 59% of mutants against 67%.

What the metric cannot see is where the expected values came from, and in this
study that is, we argue, where most of the difference in detection lies. A test
whose expectation was read off the repaired code fails on the buggy revision
whenever it touches the behaviour the repair changed. A test whose expectation
was derived from the documentation fails there only if the documentation
happens to pin that behaviour down. The two can kill exactly the same mutants.

The EvoSuite baseline (§3.5) shows the same looseness between populations that
our manipulation did not create. EvoSuite and the specification-only suites
cannot be told apart by mutation score — the order between them depends on how
the scores are aggregated — and differ three-fold in detection. Coverage, which
does separate those two, cannot separate EvoSuite from the
implementation-visible suites.

Stated as one sentence: **mutation score tracks the strength of a suite's
assertions, and tracks the provenance of its expectations only as far as the
two happen to move together.** In our arms they moved together a little.

The practical consequence for anyone evaluating agent-written suites: a high
mutation score is evidence that the tests exercise the code and that their
assertions bite. It is not evidence that the expectations are correct, and it
cannot support the claim that a generated suite would have caught the faults a
project actually had.

This bears on proposals to close the loop by feeding mutation results back to
the generating agent. Such a loop optimises a quantity that moved by a quarter
when fault detection moved by four fifths — and an agent that can read the
implementation has a cheap way to raise it.

### 4.3 Oracle quality, not oracle presence

Read alongside Konstantinou et al. (§6), our arms extend a single axis: how
usable an oracle the generating agent is given. A natural-language task
description supports 25% detection in their setting; partial API documentation
supports 14% in ours; that description with a faulty implementation added
supports 14% in theirs; a Defects4J checkout of the repaired implementation
produces 72% in ours — and that last figure measures transcription, and some of
the benchmark's own leakage, not testing.

The practical reading is not "withhold the implementation". It is that the
detection rate of a generated suite is largely a function of what the agent was
given to reason from, and that a benchmark protocol which hands it the repaired
code is measuring the protocol rather than the agent.

### 4.4 What a specification-only agent can do

The specification-only arm is not incompetent. Its suites compile, pass, cover
73% of lines, kill 44% of mutants, and are wrong about behaviour in only 3.6%
of tests — an agent writing from javadoc alone rarely misstates what the code
does. It simply catches a much smaller set of faults: three of its five
detections violate a contract the documentation states and two are reached by
probing boundaries (§3.3).

We cannot say where specification-grounded generation is worth its cost. Five
detections out of thirty-six, classified after the fact, are not a capability
we can characterise, and the matched post-cutoff corpus (§3.8), where the arm
detects 4 of 13, is too small to say whether the rate is any different on
recent code.

### 4.5 Separating the two, in practice

The only mechanism we demonstrate to distinguish a suite grounded in a contract
from one grounded in the code is the counterfactual itself: generate twice,
with and without the implementation, and compare. Tests that appear only in the
implementation-visible suite are the candidates for having transcribed the code
rather than tested it.

This doubles generation cost — about $1 per suite at the prices in §3.6 — and
we have not built or evaluated such a tool. We report it as the one approach
the data supports directly, in contrast to mutation feedback, which it supports
only weakly.

### 4.6 The condition we did not run

The complementary condition — the agent writing tests against the **buggy**
revision — is not covered by our arms, though it is well represented in the
literature: it is TOGA's evaluation setting, TDD-Bench Verified's premise, and
half of Konstantinou et al.'s design (§6).

What would be specific to this harness is the *certification* rate: how often a
suite written against the buggy revision passes on it and fails on the fixed
one, locking the defect in place rather than merely missing it. Published work
measures how often such suites fail to detect; none that we found reports how
often they actively encode the fault as expected behaviour. The harness
supports the condition with a one-character change to the checkout.

## 5. Threats to validity

### 5.1 Internal validity

**The arms differ in more than one respect.** The intended variable is access
to the implementation. The arms also differ in the following: the first three
by design, the last two by oversight.

- *Execution.* The S arm cannot run its tests. The restriction is deliberate —
  running tests is an alternative route to reading behaviour off the
  implementation — but it is a second difference and must be declared. It is
  also unenforced: the sandbox contains the compiled classes and a shell, and
  only the prompt forbids running or disassembling them. No transcript was
  kept against which compliance could be checked.
- *The rest of the checkout.* The M arm works in the project and can read its
  other tests, build files and changelog. The S arm has none of them.
- *Acceptance.* A failing S-arm test is disabled; an M-arm suite must pass
  whole, which the agent ensures by running it (§2.5).
- *Instructions.* The prompts share their two instructions on assertions and
  differ otherwise (§2.2). The M prompt restricts tests to the public API; the
  S arm's javadoc documents protected and package-private members and its
  prompt does not restrict them, and its detection of Cli-32 calls a protected
  method directly. That difference favours the S arm.
- *Benchmark metadata.* The M arm's working copy names the bug and its trigger
  tests, and in at least eleven of its twenty-six detections the agent shows
  that it knew one or the other (§3.9). This is the most serious of the
  differences, because it is no part of what "reading the implementation"
  means.

The likely direction of the execution and acceptance differences is worth
stating. An M-arm agent that sees a test fail can rewrite the assertion to
match observed behaviour; an S-arm test that fails is simply removed by the
acceptance filter. Both arms therefore end in the same state (every surviving
test passes on the fixed revision), but the M arm reaches it by adjusting
expectations to the code, which is precisely the behaviour under study. The
asymmetry does not manufacture the effect; it is part of it. The metadata is a
different matter: it could manufacture part of the effect, and we cannot say
how much.

**Training-data contamination is measured, not bounded.** Defects4J has been
public for years. Structurally, if the M arm's detection rate reflected
spontaneous recall rather than test-writing, the S arm would be expected to
recall the same faults and detect far more than 14%. Directly, the probe in
§2.8 finds two of the forty faults recalled with their mechanism and two more
recognised (§3.7), against 26 detected by the M arm; benchmark identifiers are
not memorised.

Neither argument reaches recall that is *cued*. The probe withholds the source,
and so suppresses the cue and not the memory; and in the M arm the cue was
stronger than the source alone, since the working copy named the bug and its
trigger tests (§3.9). Where the result is visible — the trigger tests of
Lang-13 and Lang-43, reproduced from files the agent did not have — cued recall
did occur. The probe is also a single sample per bug, from one model at one
point in time.

Replication on faults postdating the model's training cutoff is the stronger
check, and ours is too small to deliver it (§3.8). GitBug-Java, the obvious
candidate, no longer serves: its bugs come from 2023 commit histories, selected
in early 2024 precisely because that postdated the then-current cutoffs. Of the
two corpora we mined, the first lost its specification-only arm to a harness
error, and the second, matched to the fault composition of the Defects4J
sample, yields thirteen usable pairs. On those the direction of the effect and
the subset relation hold, the gap is about half as large, and its difference
from the Defects4J gap is within chance. A matched corpus several times that
size is what the question needs.

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
The measure also cannot distinguish detection from an accidental sensitivity to
something the fix happened to change. And a suite that does not compile against
the buggy revision, because it uses something the fix added, is `Broken` rather
than detecting: two Defects4J suites (§2.9) and one post-cutoff suite (§3.8)
are in that position.

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
the two arms are at 67.6% and 48.5% rather than 58% and 44%: the direction and
the per-bug consistency are the same and the gap is larger. The near-tie
between EvoSuite and the specification-only suites changes sign (§3.5), which
is why we call it a tie.

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

**One run per bug per arm.** LLM output is stochastic and no variance estimate
was collected; the figures carry no confidence interval attributable to
sampling the model. Repeated runs would be the standard remedy and were not
affordable at roughly $1 per suite across 80 suites. The effect size (5×) is
large relative to any plausible run-to-run variation, but this is an argument,
not a measurement. Where a run was lost to an infrastructure failure it was
repeated (§3.6), so a few suites are a second draw; that is not a replication,
and the first draws were not kept.

**Only the first arm had a decision rule fixed in advance; the comparison
between arms had none.** A threshold was written down before the M arm was run:
detection below 25% with high coverage would confirm the working hypothesis,
above 60% would mean the hypothesis was wrong and the study should be
rethought. The M arm returned 72%, crossing the second threshold, and the study
was in fact redirected — the specification-only arm was designed in response.
The rule is reported here because it functioned as intended, including when it
contradicted the hypothesis that motivated the work. Two limits on what it
shows. It was not committed to the repository before data collection, so it
cannot be verified from the artifact. And it covers the M arm's detection rate
only: the contrast this paper reports as its primary result was designed after
that rate was known, and its analysis — the pairing, the exact test, the choice
of metrics — was not specified beforehand.

**The McNemar result describes consistency of direction, not effect size in a
population.** *p* = 9.5 × 10⁻⁷ says the asymmetry between the arms is very
unlikely under the null; it says nothing about how large the gap would be in a
different corpus.

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
this paper adds is the magnitude — 72% against 14% on the same 36 bugs with the
same agent — measured in the agentic setting rather than argued for
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

### Five conditions side by side

| oracle available to the agent | detection | source |
|---|---|---|
| natural-language task description | 25% | Konstantinou et al. |
| issue description + pre-fix codebase | 19.9% (pass@1) | LIBRO on Defects4J, via TDD-Bench Verified |
| partial API documentation (javadoc) | 14% | this work |
| task description + faulty implementation | 14% | Konstantinou et al. |
| **repaired implementation, in a Defects4J checkout** | **72%** | this work |

The figures are not directly comparable — different corpora, languages, models
and fault distributions — and the two 14% entries agreeing is coincidence. The
ordering is the point, and the last row is the one that concerns evaluation
methodology rather than development practice.

### Coverage and mutants as proxies

Inozemtseva and Holmes, *"Coverage Is Not Strongly Correlated with Test Suite
Effectiveness"* (ICSE 2014), generated 31,000 suites over five Java systems and
found only a low to moderate correlation between coverage and effectiveness
once suite size is controlled for, and that stronger coverage criteria add no
insight. Note that they operationalise effectiveness as **mutation score**, not
as real-fault detection; their result therefore concerns the relationship
between two proxies, and is consistent with what we observe across populations,
where EvoSuite and the implementation-visible suites have the same coverage and
mutation scores nine points apart.

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
little about the size of the difference in detection: a quarter against four
fifths between our arms, and almost nothing against a factor of three between
EvoSuite and the specification-only suites. Mutation score is a sound proxy
when strength is what varies between the suites compared, which is the setting
Just et al. establish. When provenance varies as well it is a much looser one,
a setting their design could not surface because no suite in it had an oracle
independent of the code.

## 7. Conclusion

An agent asked to write tests for existing code will encode that code's
behaviour as the expected behaviour. Evaluating it on the repaired revision of
a known fault therefore measures, in large part, how well it transcribes a
repair it was handed. On 36 real faults, withholding the implementation and
supplying only its documentation drops detection from 72% to 14%, with the
remaining detections a strict subset of the original.

The metrics around that number move in the same direction and nowhere near as
far. Mutation score falls from 58% to 44%, coverage from 85% to 73%. With a
search-based baseline added, mutation score cannot tell apart two populations
whose detection rates differ three-fold, and coverage cannot tell apart two
whose rates are 41% and 69%. A suite's assertions can be strong while its
expectations were copied from the program they are meant to judge, and the
scores reflect the difference only in part.

An audit after the runs found that the implementation-visible arm was told
more than the implementation. The benchmark's own files name each bug and the
tests that expose it, and the agent read them.

The immediate consequence is for evaluation: figures reported for generated
suites on real-fault benchmarks should state what the generator was allowed to
read — which on Defects4J is more than the source tree suggests — and should
not be read as capability without it. The longer consequence is for tooling.
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
per-mutant output. The post-cutoff corpora are mined by
`bin/mine-postcutoff.sh`, run by `bin/run-postcutoff.sh` and tallied from their
logs by `bin/tally-postcutoff.py`.

Raw artifacts are under `data/`: one directory per arm holding, for each bug,
the record of the run (its closing message, cost and turn count, not a
transcript) and the intermediate logs; the packaged suites; and the merged
per-suite measurements in `data/agent-metrics-final.csv`. The
specification-only sandboxes were kept on the generating machine as an audit
trail and are not in the repository. For the post-cutoff corpora the build logs
are archived and the generated tests are not. The method record, including the
deviations and tooling failures encountered, is in `data/README.md`.

**The figures need neither model access nor a Defects4J installation.**
`bin/report-figures.py` recomputes every figure in §3 from the files under
`data/`, and `bin/audit-trigger-leaks.py` the evidence of §3.9. Re-measuring
from the packaged suites in `data/agent-suites/` needs Defects4J
(`bin/analyze-agent-suites.sh`); regenerating the suites needs the model.

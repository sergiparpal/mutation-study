# Oracle Provenance Is Invisible to Mutation Score

### Agent-Generated Test Suites on Defects4J, With and Without the Implementation

*Draft.*

---

## Abstract

Evaluations of automated test generation on Defects4J generate a suite against
the **fixed** revision of a bug and then check it against the buggy one. For a
language-model agent this is not neutral: the agent reads the code it is
writing tests for, and on the fixed revision that code already contains the
repair.

We generate two suites per bug with the same agent, model and instructions,
varying only whether the agent can read the implementation. In the
implementation-visible arm it works inside the checked-out project; in the
specification-only arm it works in a sandbox with generated javadoc and a
compiled jar, sees no source, and may not execute its tests. Over 36 bugs from
four Java projects measured in both arms, real-fault detection falls from **72%
to 14%**. Every fault the specification-only suites catch is also caught by the
implementation-visible suites and none the other way round (exact McNemar,
*p* = 9.5 × 10⁻⁷).

**Mutation score does not register the difference: 72% against 70%.** Adding an
EvoSuite baseline over the same subjects shows the failure is not confined to
our manipulation. Ranked by mutation score the three populations are 72%, 70%
and 59%; ranked by fault detection they are 71%, 14% and 34%. The
specification-only suites score eleven points higher on mutation than EvoSuite
and detect less than half as many faults. Line coverage moves in the right
direction but far too little, from 85% to 73%.

Mutation score measures the strength of a suite's assertions. It does not
measure where those assertions' expected values came from, and provenance
leaves no trace in execution. This bears on how agent-written suites are
evaluated, and on proposals to improve them by feeding mutation results back to
the generating agent — a loop that optimises precisely the quantity that is
blind to the distinction.

Three further observations. Writing tests from javadoc alone yields wrong
expectations in only 3.3% of tests, so the specification-only arm is not
guesswork: it catches a small, coherent class of faults, those where the
implementation contradicts documented contract. The agent and EvoSuite are
complementary rather than ordered — 17 faults are found only by the agent, 4
only by EvoSuite, 6 by neither. And two contamination controls we have not seen
reported elsewhere: Defects4J checkouts ship the fix commit in their git
history, subject line included, which we remove before generation; and a direct
probe of what the model recalls with no code in context, which finds benchmark
identifiers entirely unmemorised and exactly one of the forty faults genuinely
recalled — four of the five answers that a mechanical screen flagged turn out
to be confident, specific confabulations.

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
agent, the same model and the same instructions, differing in one variable:
whether the agent can read the implementation. In the **implementation-visible**
arm it works inside the checked-out project at the fixed revision. In the
**specification-only** arm it works in a sandbox containing generated javadoc
and a compiled jar, never sees source, and may not execute its tests.

Over 36 bugs measured in both arms, real-fault detection falls from **72% to
14%**. Every fault the specification-only suites catch is also caught by the
implementation-visible suites; none is caught only by the former. An exact
McNemar test on the 21 discordant pairs gives *p* = 9.5 × 10⁻⁷.

**Mutation score does not move: 72% against 70%.** Line coverage falls from 85%
to 73%, far less than detection does. Adding an EvoSuite baseline over the same
subjects makes the metric's failure sharper still: ranked by mutation score the
three populations are 72%, 70% and 59%, while their detection rates are 71%,
14% and 34% — the middle two in reverse order. Both sets of suites discriminate
behaviour to essentially the same degree; what differs is where their
expectations came from, and no execution-based metric observes that.

Contributions:

1. A controlled measurement of how much of an agent's apparent fault-detection
   ability on Defects4J is attributable to reading the repaired implementation
   (roughly five sixths of it), on real faults from four real projects. That
   the regression evaluation setting flatters generated suites is not a new
   observation — Dinella et al. state it in 2022 (§6) — but to our knowledge it
   has not been quantified for an agent that reads the codebase.
2. The finding that **mutation score does not register the difference at all**
   (72% against 70%) and that line coverage registers far too little of it
   (85% against 73%) to account for a five-fold gap in detection. This bears
   directly on how agent-written suites are currently evaluated and on
   proposals to use mutation feedback to improve them.
3. A characterisation of what specification-only generation does catch: faults
   where the implementation contradicts a contract the documentation states.
   With an EvoSuite baseline over the same subjects, which shows the two
   approaches to be complementary rather than ordered — 17 faults are found
   only by the agent, 4 only by EvoSuite — and which shows mutation score
   ranking three suite populations in the wrong order.
4. Two contamination controls that appear not to be standard practice:
   Defects4J checkouts ship the fix commit in their git history, including its
   subject line naming the fault, which we remove before generation; and a
   direct probe of what the model recalls about each fault with no code in
   context, which finds one memorised fault in forty.

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

Two arms over the same forty bugs, differing in exactly one variable: whether
the agent can read the implementation under test.

**Implementation-visible arm ("M").** The agent works inside the checked-out
project at the *fixed* revision and reads the source freely. This is the
situation when a developer asks a coding agent for tests on existing code.

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

The short forms **M** and **S** are used throughout for the two arms.

Both arms are given the same target classes — those the fix modifies, from
`defects4j export -p classes.modified` — and the same instructions about
assertion style, boundary cases and self-containment.

### 2.3 Agent configuration

| | |
|---|---|
| Harness | Claude Code 2.1.251, native install, linux-x64 |
| Model | `claude-sonnet` for both arms (40 bugs each) |
| Turn cap | 50 |
| Tools | `Read`, `Write`, `Bash` |
| Permission mode | `acceptEdits` |
| Output | `--output-format json`, one record per run |

The model is passed on the command line rather than inherited from local
configuration, so the experiment is not silently defined by the operator's
settings.

Six additional M-arm suites were produced with `claude-opus` before the run
switched models on exhausting quota. They are the first six bugs of the sample,
not a random subset, and are reported separately as an opportunistic
observation rather than as a model comparison. Their turn cap also differs (25).

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

**Training-data contamination is measured rather than eliminated.** Defects4J
has been public for years and may appear in the model's training data. The S
arm is a partial control — a model recalling a fault would plausibly recall it
without the source too — and §2.8 adds a direct probe of what the model
actually remembers. Results in §3.7.

### 2.5 Suite acceptance

**M arm.** A suite is accepted if it exists, compiles inside the project, and
passes in full on the fixed revision. All 40 suites passed this filter.

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
worse. The M arm is subject to the same filter, so the between-arm comparison
is unaffected.

### 2.6 Measurements

All three measurements use Defects4J's own analysis scripts, applied to each
packaged suite:

- **Real-fault detection** — `run_bug_detection.pl`. The suite is run against
  the fixed and the buggy revision. A suite is classified `Fail` when at least
  one of its tests passes on the fixed revision and fails on the buggy one;
  that is, it detects the real fault. This is the primary outcome.
- **Mutation score** — `run_mutation.pl`, using the Major framework bundled
  with Defects4J, over the classes the fix modifies. Default operator set:
  AOR, LOR, SOR, COR, ROR, ORU, LVR, STD.
- **Line and branch coverage** — `run_coverage.pl`.

### 2.7 Search-based baseline

EvoSuite, as bundled with Defects4J v3.0.1 and invoked through `gen_tests` with
a 120-second search budget per class, provides a non-agent point of comparison.
It is not a third arm of the manipulation: like the implementation-visible arm
it generates against the fixed revision and has the same access to the repaired
code. What it lacks is any interpretation of that code — it asserts observed
behaviour. The comparison therefore separates the contribution of the generator
from the contribution of the information available to it.

### 2.8 Memorisation probe

Defects4J has been public for years and may be present in the model's training
data, in which case detection could reflect recall rather than reasoning. The
obvious replication corpus does not settle this: GitBug-Java's 199 bugs come
from 2023 commit histories, selected in early 2024 because that postdated the
training cutoff of models available then. It no longer does.

We probe the model directly instead. For each of the 40 bugs, two questions are
put to the same model with no tools, no web access, no repository and no
conversational context, one turn each:

- **A, identifier cue.** *"What is Defects4J bug Lang-13? Describe the specific
  fault."* Answering requires having seen the benchmark itself.
- **B, location cue.** *"Was there a known bug in the class
  `org.apache.commons.lang3.SerializationUtils`? Describe the specific fault if
  you recall one."* This matches what the implementation-visible agent actually
  had — project and class, never the bug identifier.

Each prompt offers an exact disclaimer phrase, so that declining is cheaper
than guessing. Answers are screened mechanically against identifiers taken from
the fix diff, and every answer flagged by that screen is then read against the
actual fault, because domain vocabulary alone produces false hits.

### 2.9 Exclusions

Five bugs are excluded from some or all measurements, for reasons unrelated to
the treatment. Cli-21 appears twice: it is affected by two independent
problems.

| Bug | Arms affected | Reason |
|---|---|---|
| Cli-21, Csv-3 | M | Suite extended a test helper from the project's test tree, so it compiles in the working copy but not as a standalone archive |
| Gson-14, Gson-16 | all, mutation and coverage | Major's mml compiler rejects the class name: `invalid scope: com.google.gson.internal.$Gson$Types`. EvoSuite's generated suite for the same class does not compile either — `illegal start of expression` on the `$` in the identifier. Three independent tools fail on this one class, which is why we treat it as a tooling limitation rather than a property of the bugs |
| Cli-15, Cli-21 | EvoSuite | `gen_tests` produced no output and no log; both are `cli2` subjects, whose declared classpath references jars that the checkout never materialises |

This leaves 36 M-arm suites and 38 S-arm suites with all three measurements,
and **36 bugs present in both arms**. All paired figures use those 36. Gson-14
and Gson-16 do have detection and coverage figures; they are omitted from the
tables so that every reported arm total covers the same set of suites in all
three metrics.

---

## 3. Results

### 3.1 Primary result

Over the 36 bugs measured in both arms:

| | M arm (reads code) | S arm (spec only) |
|---|---|---|
| **Real fault detected** | **26/36 — 72%** | **5/36 — 14%** |
| Mutation score | 72% | 70% |
| Line coverage | 85% | 73% |

Detection differs by a factor of five. Mutation score differs by two points.

The paired outcomes are strongly asymmetric: of the 36 bugs, 21 were detected
by the M arm alone and **none** by the S arm alone. The S arm's detections are
therefore a strict subset of the M arm's rather than a partially overlapping
set. An exact McNemar test on the 21 discordant pairs gives
*p* = 9.5 × 10⁻⁷.

Reported per arm over every suite measured, including the unpaired ones:

| arm | n | detection | mutation | coverage |
|---|---|---|---|---|
| M arm, Sonnet | 36 | 26/36 (72%) | 72% | 85% |
| S arm, Sonnet | 38 | 6/38 (16%) | 70% | 73% |
| EvoSuite | 36 | 13/36 (36%) | 59% | 85% |
| M arm, Opus † | 6 | 6/6 | 79% | 89% |

† Six bugs, and the first six of the sample rather than a random subset: the
run switched models on exhausting quota (§2.3). The detection figure is
reported as a count rather than a percentage to discourage reading it as a
model comparison.

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
Lang-13. Four are cases where the implementation contradicts a contract the
javadoc states:

- **Csv-4** — a documented accessor returns `null` in a documented case, and
  the value is used without a guard.
- **Csv-6** — an index derived from the header mapping reaches an array access
  with no bound check.
- **Gson-15** — `NaN` and infinities are rejected regardless of the documented
  lenient mode.
- **Lang-13** — primitive class objects fail a documented deserialization
  contract.

The fifth, **Cli-32**, is detected by a different route. Its faulty loop reads
`text.charAt(pos)` under the condition `pos <= text.length()`, so a boundary
input throws `StringIndexOutOfBoundsException`. No knowledge of the intended
wrapping semantics is needed to expose it: any test that reaches that boundary
does, and a crash needs no oracle at all. It is the only one of the five that
the specification-only arm could have caught without the specification.

The specification-only arm detects faults that are visible from the
specification, and very little else. This is consistent with the mechanism the
design isolates: without the implementation, the agent's only oracle is the
documented contract, so it catches exactly the faults where code and contract
disagree.

### 3.4 Writing from documentation produces few wrong expectations

Across the S arm, **59 of 1806 tests (3.3%)** were disabled for failing on the
fixed revision. Per project:

| project | pruned / total | rate |
|---|---|---|
| Commons Lang | 4 / 541 | 0.7% |
| Commons CSV | 10 / 467 | 2.1% |
| Commons CLI | 12 / 221 | 5.4% |
| Gson | 33 / 577 | 5.7% |

The rate spans an order of magnitude across subjects. Commons Lang's javadoc is
unusually explicit, and its rate is under one percent; Gson documents
reflection and generics code far more sparsely, and Commons CLI's older
`cli2` tree is sparser still. Documentation density plausibly explains the
spread, though we did not measure it and cannot separate it from differences in
API complexity.

Even at the high end the rate is low. This retires the hypothesis that
specification-only generation would largely be guesswork: agents write tests
from javadoc that are almost always correct about what the code does, and still
fail to catch real faults.

### 3.5 Search-based baseline

EvoSuite, invoked through Defects4J's `gen_tests` with a 120-second budget per
class, produced suites for 38 of the 40 bugs; the two failures are the `cli2`
subjects (§2.9). Like the implementation-visible arm, EvoSuite generates
against the fixed revision and has the same access to the repaired code.

Thirty-five bugs are measured for all three generators, one fewer than the 36
paired between the two agent arms, because EvoSuite lost an additional subject
to the exclusions in §2.9. Over those 35:

| | detection | mutation | coverage |
|---|---|---|---|
| M arm (implementation-visible) | 25/35 (71%) | 72% | 85% |
| EvoSuite | 12/35 (34%) | 59% | 85% |
| S arm (specification-only) | 5/35 (14%) | 70% | 73% |

EvoSuite falls between the two arms. Since it has the same access to the
repaired implementation as the implementation-visible arm, the gap from 71% to
34% is attributable to the generator rather than to the information available;
the gap from 71% to 14% is attributable to the information.

**The two approaches are complementary, not ordered.** Of the 35 bugs, 8 are
detected by both, 17 by the agent alone, 4 by EvoSuite alone, and 6 by neither
— a union of 29 (83%). A search-based generator that asserts observed behaviour
without interpreting it still reaches four faults that the agent misses.

**Mutation score does not rank the three populations correctly.** Ordered by
mutation score the prediction would be agent (72%) > specification-only (70%) >
EvoSuite (59%); the observed detection order is agent (71%) > EvoSuite (34%) >
specification-only (14%). The specification-only suites score eleven points
higher on mutation than EvoSuite and detect less than half as many faults. The
metric's failure is therefore not confined to the two arms of our manipulation.

### 3.6 Cost

At list prices, the M arm cost $42.61 for 46 suites and the S arm $37.02 for
40 suites — roughly $0.90 to $1.00 per suite. Both arms were produced against
a subscription quota rather than metered billing, so these figures are token
valuations rather than amounts charged.

### 3.7 Memorisation

Under the identifier cue, the model disclaimed knowledge for **all 40 bugs**:
the benchmark identifiers are not memorised.

Under the location cue, 25 answers disclaimed, 10 made unspecific claims, and 5
reproduced three or more identifiers from the fix. Reading those five against
the actual faults, **four are confabulations**: the model describes a
plausible, internally coherent, confidently stated bug in the right class that
is not the bug in question.

| bug | actual fault | model's answer |
|---|---|---|
| Lang-8 | reads the construction-time zone instead of the calendar's | mutates the caller's `Calendar` without cloning |
| Lang-63 | hardcoded `days += 31` and a `reduceAndCorrect` correction pass | calendar arithmetic sensitive to DST transitions |
| Lang-65 | an absent truncation block between existing marker comments | missing special case for `Calendar.SEMI_MONTH` |
| Gson-4 | an obsolete restriction on top-level JSON values | missing delimiter check after `true`/`null` literals |

**One bug of the forty is genuinely recalled: Lang-13.** The model reproduces
the mechanism in full — `ClassLoaderAwareObjectInputStream`, `resolveClass()`,
`Class.forName()` failing on primitive type names, and the repair mapping
primitive names to their `TYPE` constants — without being shown any code. It
misattributes the JIRA identifier, which is characteristic of recall of a
mechanism rather than of a record.

Two things follow. Recall cannot account for the implementation-visible arm's
result: it detects 26 faults and has memorised one. And Lang-13 is the single
bug detected by *both* arms, which is what recall available to both would
predict — rather than recall explaining the gap between them.

The confabulation rate is itself worth noting alongside §3.4. The same model
that writes tests from javadoc with a 3.3% error rate invents four confident,
specific and wrong faults when asked about code it cannot see. Correctness here
tracks whether there is something to check against.

### 3.8 Post-cutoff replication, and why it does not settle contamination

The probe in §3.7 bounds training-data contamination but cannot rule out recall
*cued* by the source, since withholding the source withholds the cue. Faults the
model cannot have seen would settle it. We therefore mined a small corpus from
the same four upstream repositories, taking fix commits from June to September
2026 — recent enough to postdate the training data, and from the same
codebases, so that the only intended difference from the Defects4J sample is
the date.

Candidates were fix commits that change both production and test code, touch at
most three production files, and for which the fix's tests fail on the parent
commit and pass on the fix. Eleven subjects passed that validation. Three could
not be used: removing the developer test file that contains the trigger tests
breaks compilation, because other test classes call static helpers defined in
it — `FastDateParserJava15BugTest` uses `FastDateParserTest.checkParse` and
`LONG_FORMAT`, and `CSVPrinterTest` likewise depends on `CSVFormatTest`. That
leaves **eight subjects**, measured for detection only (§3.8 rationale below).

| arm | detected | tests pruned |
|---|---|---|
| implementation-visible | 6/8 (75%) | 0 of 267 |
| specification-only | 8/8 (100%) † | 11 of 181 (6.1%) |

† Provisional; see the note on completion in the repository.

The implementation-visible figure reproduces the Defects4J result closely: 75%
against 72%, with no tests pruned in either. **The specification-only figure
does not, and the reason is the corpus, not the date.**

Reading the eight faults, they are overwhelmingly extreme-value faults:
`Integer.MIN_VALUE` in fraction reduction; integer overflow in a wrap-position
calculation; sign extension from `>>` where `>>>` was needed; a `ParsePosition`
index equal to the source length; a negated `CharRange` touching its own
bounds; byte tracking for supplementary characters; an overflow bound in the
wrong direction.

Both arms' prompts instruct the agent to "cover boundary and error cases, not
just the happy path". A fault that manifests only at `Integer.MIN_VALUE`, or on
arithmetic overflow, or at an index equal to a length, is reached by following
that instruction. It requires no specification at all — which is a different
mechanism from the one that produced the five Defects4J detections, four of
which were cases where the implementation contradicts a documented contract
(§3.3).

The selection criteria are the cause. Requiring small, ticket-tracked commits
that fix and test in one change filters toward precisely this class of fault.
The Defects4J sample has a different composition: 21 of its 40 faults are
omissions — absent logic, which documentation cannot reveal because it does not
describe what is not there.

**This replication therefore varies two things at once, date and fault
composition, and composition dominates.** It does not bound contamination,
which was its purpose. We report it because it establishes something else: the
specification-only arm has a second competence beyond contract violations. Told
to probe boundaries, it finds extreme-value faults without needing a
specification, and on a corpus made of them it matches the
implementation-visible arm. Whether that generalises to a corpus sampled
without this bias is untested.

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
protocol itself.

Neither arm establishes what an agent would score against genuinely unknown
code. The specification-only arm's 14% is closer to that question but is not
the answer either, because withholding the implementation removes information a
real developer would have.

### 4.2 Mutation score measures strength, not provenance

The central observation is that the two arms are almost indistinguishable under
mutation analysis — 72% against 70% on the same 36 bugs — while differing
five-fold in fault detection.

This is not a failure of mutation analysis on its own terms, and it does not
contradict the established result that mutation score predicts real-fault
detection (Just et al., FSE 2014; see §6). Mutation score asks whether a
suite's assertions are strong enough to distinguish the program from small
syntactic variants of it. Both arms produce suites that are: the
specification-only suites assert on returned values, exact exception messages
and persisted state, and kill mutants at the same rate as suites written with
the source in view.

What the metric cannot see is where the expected values came from. Just et al.
establish the correlation by varying suite *strength* while holding the
generation process fixed — every suite in their study, developer-written or
search-based, derives its expectations from the same implementation. We hold
strength roughly fixed and vary the *information available to the generator*.
Along that second axis the metric is uninformative.

The EvoSuite baseline (§3.5) sharpens this. Across three populations the metric
does not merely fail to separate the two arms; it ranks them in the wrong
order, and the population it rates second detects less than half as many faults
as the one it rates third.

Stated as one sentence: **mutation score tracks the strength of a suite's
assertions, not the provenance of its expectations.** Provenance leaves no
trace in execution, so no metric defined over program behaviour can recover it.

The practical consequence for anyone evaluating agent-written suites: a high
mutation score is evidence that the tests exercise the code and that their
assertions bite. It is not evidence that the expectations are correct, and it
cannot support the claim that a generated suite would have caught the faults a
project actually had.

This bears directly on proposals to close the loop by feeding mutation results
back to the generating agent. Such a loop optimises precisely the quantity our
measurement shows to be insensitive to the difference that matters — and an
agent that can read the implementation has a cheap way to raise it.

### 4.3 Oracle quality, not oracle presence

Read alongside Konstantinou et al. (§6), our arms extend a single axis: how
usable an oracle the generating agent is given. A complete natural-language
specification supports 25% detection in their setting; partial API
documentation supports 14% in ours; a faulty implementation supports 14% in
theirs; a repaired implementation produces 72% in ours — and that last figure
measures transcription, not testing.

The practical reading is not "withhold the implementation". It is that the
detection rate of a generated suite is largely a function of what the agent was
given to reason from, and that a benchmark protocol which hands it the repaired
code is measuring the protocol rather than the agent.

### 4.4 What a specification-only agent can do

The specification-only arm is not incompetent. Its suites compile, pass, cover
73% of lines, and are wrong about behaviour in only 3.3% of tests — an agent
writing from javadoc alone rarely misstates what the code does. It simply
catches a different, much smaller class of faults: those where the
implementation contradicts documentation. Four of its five detections are of
exactly that shape.

That is a coherent capability rather than a degraded one, and it suggests where
specification-grounded generation is worth its cost: as a check on whether code
and its documented contract agree, not as a general fault-detection method.

### 4.5 Separating the two, in practice

The only mechanism we demonstrate to distinguish a suite grounded in a contract
from one grounded in the code is the counterfactual itself: generate twice,
with and without the implementation, and compare. Tests that appear only in the
implementation-visible suite are the candidates for having transcribed the code
rather than tested it.

This doubles generation cost — about $0.90 per suite at the prices in §3.6 —
and we have not built or evaluated such a tool. We report it as the one
approach the data supports, in contrast to mutation feedback, which the data
does not.

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
to the implementation, but the S arm also cannot execute its tests and works in
a sandbox rather than a project checkout. The execution restriction is
deliberate — running tests is an alternative route to reading behaviour off the
implementation — but it is a second difference and must be declared.

Its likely direction is worth stating. An M-arm agent that sees a test fail can
rewrite the assertion to match observed behaviour; an S-arm test that fails is
simply removed by the acceptance filter. Both arms therefore end in the same
state (every surviving test passes on the fixed revision), but the M arm
reaches it by adjusting expectations to the code, which is precisely the
behaviour under study. The asymmetry does not manufacture the effect; it is
part of it.

**Training-data contamination is bounded, and now measured.** Defects4J has
been public for years. Two lines of evidence bound the threat. Structurally, if
the M arm's detection rate reflected recall rather than test-writing, the S arm
would be expected to recall the same faults and detect far more than 14%.
Directly, the probe in §2.8 finds that the model recalls exactly one of the
forty faults (§3.7), against 26 detected by the M arm; benchmark identifiers
are not memorised at all, and four of the five answers the mechanical screen
flagged turn out to be confabulations.

Two residual limitations. Recall may be *cued* by the source rather than
spontaneous, in which case the probe — which withholds the source — suppresses
the cue and not the memory; the design cannot separate these. And the probe
tests one model at one point in time.

Replication on a corpus postdating the model's training cutoff remains the
stronger check, and our attempt at one does not deliver it (§3.8). GitBug-Java,
the obvious candidate, no longer serves: its bugs come from 2023 commit
histories, selected in early 2024 precisely because that postdated the
then-current cutoffs. Mining our own post-cutoff corpus produced subjects whose
fault composition differs systematically from the Defects4J sample — a
consequence of the selection criteria — so the comparison confounds date with
composition. A corpus matched on fault type would be required, and building one
is harder than building either corpus alone.

## 5.2 Construct validity

**Fault detection is binary and coarse.** Defects4J classifies a suite as
detecting the fault when at least one test passes on the fixed revision and
fails on the buggy one. A suite that detects the fault through twelve tests and
one that detects it through a single incidental assertion score identically.
The measure also cannot distinguish detection from an accidental sensitivity to
something the fix happened to change.

**Javadoc is not an independent specification.** The S arm's oracle is
documentation written by the same developers as the code, and sometimes derived
from it. It is a proxy for "an oracle not read off the implementation", and a
weak one. A genuinely independent specification — a requirements document, a
standard, a second implementation — might behave differently in either
direction.

**Mutation score is measured over the classes the fix modifies**, which is
Defects4J's default scope. A wider scope would change the absolute figures,
though there is no obvious reason it would change the between-arm comparison.

### 5.3 External validity

**One model family, one harness.** Claude Sonnet throughout, with six Opus
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
not a measurement.

**The primary outcome and its decision rule were fixed before data
collection.** A threshold was written down in advance: detection below 25% with
high coverage would confirm the working hypothesis, above 60% would mean the
hypothesis was wrong and the study should be rethought. The M arm returned 72%,
crossing the second threshold, and the study was in fact redirected — the
specification-only arm was designed in response. The pre-registered rule is
reported here because it functioned as intended, including when it contradicted
the hypothesis that motivated the work.

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
> quality oracles. In our setting where tests are generated on the buggy program
> version, regression test oracles will not find bugs as they assume the
> observed buggy behavior is correct."

**The artifact is therefore not our discovery, and we do not claim it.** What
this paper adds is the magnitude — 72% against 14% on the same 36 bugs with the
same agent — measured in the agentic setting rather than argued for
neural-oracle inference over EvoSuite prefixes, and the demonstration that the
metrics ordinarily reported alongside detection are blind to it.

Hossain, Filieri, Dwyer, Elbaum and Visser, *"Neural-Based Test Oracle
Generation: A Large-Scale Evaluation and Lessons Learned"* (ESEC/FSE 2023)
replicate and extend TOGA over 25 Java systems, 223.5K test cases and 51K
injected faults. TOGA's Defects4J result does not survive the extension. Where
the original reports 69% accuracy for assertion-oracle inference and 86% for
exceptional oracles, they measure 52% and 75%. TOGA declines to emit any
assertion in 62% of the cases where it correctly predicts one is needed, and
more than 47% of the assertions it does emit are false positives. On their
mutation-based measure, EvoSuite's own assertions kill 30,411 of 51,385
mutants and TOGA's add 105 — 0.3%.

Two points carry over to our setting. The first is the caution: a benchmark
result that looks strong on Defects4J need not survive a broader evaluation,
which is the same concern as ours approached from the other side. The second is
that TOGA is explicitly designed "to leverage natural language specifications
(docstrings)" — the same source of truth as our specification-only arm, seven
years earlier and with a far smaller model.

### Error propagation in code-then-test workflows

Konstantinou, Tambon and Papadakis, *"On the risk of coding before testing: An
empirical study on LLM-based test generation workflow"* (arXiv:2607.05139)
study the complementary condition. Their pipeline generates candidate
implementations with an LLM, retains only the faulty ones — "we discard the
cases that the model is generating correct code and keep only those that are
faulty" — and compares test suites generated from that faulty implementation
against suites generated from the task description alone. Tests generated after
faulty code detect 14% of faults against 25% for tests generated from the
description; exposing the implementation reduces detection by 9 to 18 points
across five models. They name the phenomenon *error propagation*.

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
at pass@1** (33% at pass@50, i.e. fifty attempts per issue), and Plein et al.
reach 6% with ChatGPT on the same corpus. Same benchmark family as ours, a
single attempt, and the model is given a natural-language description of what
is wrong — which our specification-only arm is not.

### The four conditions

| oracle available to the agent | detection | source |
|---|---|---|
| complete natural-language specification | 25% | Konstantinou et al. |
| issue description + pre-fix codebase | 19.9% (pass@1) | LIBRO on Defects4J, via TDD-Bench Verified |
| partial API documentation (javadoc) | 14% | this work |
| faulty implementation | 14% | Konstantinou et al. |
| **repaired implementation** | **72%** | this work |

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
between two proxies, and is consistent with the pattern we observe, where
coverage falls from 85% to 73% while mutation score barely moves.

Just, Jalali, Inozemtseva, Ernst, Holmes and Fraser, *"Are Mutants a Valid
Substitute for Real Faults in Software Testing?"* (FSE 2014), examined 357 real
faults in five applications totalling 321,000 lines. They report that 73% of
real faults are coupled to mutants from commonly used operators, that 17% are
coupled to no mutant at all — mostly faults involving algorithmic changes or
code deletion — and that mutation score correlates positively with real-fault
detection, significantly more strongly than statement coverage does, when
controlling for coverage.

**Our result is not in tension with theirs, because the two vary different
things.** Just et al. hold the generation process roughly constant and vary
suite *strength*: for a given fault they compare the suites that detect it
against those that do not, within the same program, and the detecting suites
have significantly higher mutation scores (in 182 of 194 faults across their
five subjects, Â₁₂ between 0.66 and 0.81). Every suite in their study —
developer-written and search-based alike — derives its expectations from the
same implementation.

We hold suite strength roughly constant, at 72% and 70%, and vary the
*information available to the generator*. Along that axis the metric predicts
nothing. The two compose into one statement: **mutation score tracks the
strength of a suite's assertions, not the provenance of its expectations.** It
is a sound proxy when strength is what varies between the suites compared,
which is the setting Just et al. establish; it is uninformative when provenance
varies, a setting their design could not surface because no suite in it had an
oracle independent of the code.

## 7. Conclusion

An agent asked to write tests for existing code will encode that code's
behaviour as the expected behaviour. Evaluating it on the repaired revision of
a known fault therefore measures, in large part, how well it transcribes a
repair it was handed. On 36 real faults, withholding the implementation and
supplying only the public documentation drops detection from 72% to 14%, with
every remaining detection a strict subset of the original.

The measurement that matters is not that number but what happens to the metrics
around it. Mutation score does not move. With a search-based baseline added it
ranks three suite populations in the wrong order. Coverage moves in the right
direction by nowhere near enough. A suite's assertions can be strong,
discriminating and well-targeted while its expectations were copied from the
program they are meant to judge, and nothing observable at execution time
distinguishes the two cases.

The immediate consequence is for evaluation: figures reported for generated
suites on real-fault benchmarks should state what the generator was allowed to
read, and should not be read as capability without it. The longer consequence
is for tooling. If mutation feedback cannot see the difference, closing the
generation loop on it optimises the wrong quantity. The only mechanism our data
supports is the counterfactual — generate twice, with and without the
implementation, and compare — which we have measured but not built.

## Data availability

All scripts, raw artifacts and per-bug measurements are in the repository.
Generation: `bin/run-agent-suites.sh` (implementation-visible arm),
`bin/run-spec-suites.sh` (specification-only arm, including sandbox
construction) and `bin/prune-failing-tests.py` (the per-method acceptance
filter). The search-based baseline is produced with Defects4J's own
`gen_tests.pl`. Measurement: `bin/analyze-agent-suites.sh`, which wraps
`run_bug_detection.pl`, `run_coverage.pl` and `run_mutation.pl`.

Raw artifacts are under `data/`: one directory per bug per arm with the agent
transcript, cost record and intermediate logs; the packaged suites; the
specification-only sandboxes, retained as an audit trail; and the merged
per-suite measurements in `data/agent-metrics-final.csv`. The full method
record, including every deviation and tooling failure encountered, is in
`data/README.md`.

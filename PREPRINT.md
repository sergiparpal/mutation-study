# Reading the Repaired Code: An Evaluation Artifact in Agent-Based Test Generation

*Draft. Method, results and threats to validity are written. Related work is a
stub pending a read of the primary sources.*

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
to 73%, far less than detection does. Both sets of suites discriminate
behaviour to essentially the same degree; what differs is where their
expectations came from, and no execution-based metric observes that.

Contributions:

1. A controlled measurement of how much of an agent's apparent fault-detection
   ability on Defects4J is attributable to reading the repaired implementation
   (roughly five sixths of it), on real faults from four real projects.
2. The finding that **mutation score and coverage are near-blind to this
   difference**, which bears directly on how agent-written suites are currently
   evaluated and on proposals to use mutation feedback to improve them.
3. A characterisation of what specification-only generation does catch: faults
   where the implementation contradicts a contract the documentation states.
4. A contamination control that appears not to be standard practice — Defects4J
   checkouts ship the fix commit in their git history, including its subject
   line naming the fault.

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

**M arm (implementation-visible).** The agent works inside the checked-out
project at the *fixed* revision and reads the source freely. This is the
situation when a developer asks a coding agent for tests on existing code.

**S arm (specification-only).** The agent works in a sandbox containing:

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
cloning primitive classes`, and the `D4J_<P>_<n>_BUGGY_VERSION` /
`_FIXED_VERSION` tags make `git diff` yield the patch directly. A pilot run
without this control produced a test citing "LANG-788" in a comment. `.git` is
therefore deleted before the agent starts, and the prompt forbids git and web
search.

*Measured effect of this leak on that pilot bug:* no change in mutation score
or fault detection, +6 covered lines. The history is a real channel but a weak
one when the agent can already read the fixed implementation; it matters far
more for the S arm, where the code is withheld.

We note this control because, as far as we are aware, it is not standard
practice in work that generates tests over Defects4J checkouts.

**Training-data contamination is not controlled.** Defects4J has been public
for years and may appear in the model's training data. The S arm is a partial
control — a model recalling the fault would plausibly recall it without the
source too — but not a conclusive one. Replication on a post-cutoff corpus
(GitBug-Java) is pending.

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

### 2.7 Exclusions

Four bugs are excluded from some or all measurements, for reasons unrelated to
the treatment:

| Bug | Arms affected | Reason |
|---|---|---|
| Cli-21, Csv-3 | M | Suite extended a test helper from the project's test tree, so it compiles in the working copy but not as a standalone archive |
| Gson-14, Gson-16 | both, mutation only | Major's mml compiler rejects the class name: `invalid scope: com.google.gson.internal.$Gson$Types` |

This leaves 36 M-arm suites and 38 S-arm suites fully measured, with **36 bugs
present in both arms**. All paired figures use those 36.

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
by the M arm alone and **none** by the S arm alone — every fault the
specification-only suites caught was also caught by the implementation-visible
suites — the S arm's detections are a strict subset of the M arm's, not a
partially overlapping set. An exact McNemar test on the 21 discordant pairs
gives *p* = 9.5 × 10⁻⁷.

Reported per arm over every suite measured, including the unpaired ones:

| arm | n | detection | mutation | coverage |
|---|---|---|---|---|
| Sonnet, implementation-visible | 36 | 26/36 (72%) | 72% | 85% |
| Sonnet, specification-only | 38 | 6/38 (16%) | 70% | 73% |
| Opus, implementation-visible † | 6 | 6/6 (100%) | 80% | 89% |

† Not a designed comparison; see §2.3.

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
Lang-13. Four of the five are cases where the implementation contradicts a
contract the javadoc states:

- **Csv-4** — a documented accessor returns `null` in a documented case, and
  the value is used without a guard.
- **Csv-6** — an index derived from the header mapping reaches an array access
  with no bound check.
- **Gson-15** — `NaN` and infinities are rejected regardless of the documented
  lenient mode.
- **Lang-13** — primitive class objects fail a documented deserialization
  contract.

The specification-only arm detects faults that are visible from the
specification, and very little else. This is consistent with the mechanism the
design isolates: without the implementation, the agent's only oracle is the
documented contract, so it catches exactly the faults where code and contract
disagree.

### 3.4 Writing from documentation produces few wrong expectations

Across the S arm, **59 of 1806 tests (3%)** were disabled for failing on the
fixed revision. The rate varies by project in the expected direction:

| project | prune rate |
|---|---|
| Commons Lang | ~0% |
| Commons CSV | ~2% |
| Gson | ~6% |

Commons Lang's javadoc is unusually explicit; Gson's reflection and generics
code is documented more sparsely. The overall figure retires the hypothesis
that specification-only generation would largely be guesswork: agents write
tests from javadoc that are almost always correct about behaviour, and still
fail to catch real faults.

### 3.5 Baselines

Defects4J ships EvoSuite and Randoop via `gen_tests`. On Lang-13, an EvoSuite
suite generated for the same class is classified `Pass` — it does not detect
the fault — where both agent arms detect it. On the same bug, the developer
test suite scores 70% mutation against 77% for the M-arm agent suite.

These are single-bug observations and are reported as context, not as a
systematic comparison.

### 3.6 Cost

At list prices, the M arm cost $42.61 for 46 suites and the S arm $37.02 for
40 suites — roughly $0.90 to $1.00 per suite. Both arms were produced against
a subscription quota rather than metered billing, so these figures are token
valuations rather than amounts charged.

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

### 4.2 Mutation score measures discrimination, not provenance

The central observation is that the two arms are almost indistinguishable under
mutation analysis — 72% against 70% on the same 36 bugs — while differing
five-fold in fault detection.

This is not a failure of mutation analysis on its own terms. Mutation score
asks whether a suite's assertions are strong enough to distinguish the program
from small variants of it. Both arms produce suites that do: the
specification-only suites assert on returned values, exact exception messages
and persisted state, and kill mutants at the same rate. What differs between
the arms is the **provenance of the expected values** — read off the
implementation, or derived from documentation — and provenance leaves no trace
in execution. No metric defined over program behaviour can see it.

The practical consequence for anyone evaluating agent-written suites: a high
mutation score is evidence that the tests exercise the code and that their
assertions bite. It is not evidence that the expectations are correct, and it
cannot be used to argue that a generated suite would have caught the bugs the
project actually had.

This also bears on proposals to close the loop by feeding mutation results back
to the generating agent. Such a loop optimises exactly the quantity that our
measurement shows to be insensitive to the difference that matters.

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
73% of lines, and are wrong about behaviour in only 3% of tests — an agent
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

### 4.6 An untested variant

The complementary condition — the agent writing tests against the **buggy**
revision — is not covered here. A faithful mirror would then certify the fault:
the suite would pass on the buggy revision and fail on the fixed one. The
harness supports this with a one-character change, and it would give a direct
measure of how often agent-written tests lock a defect in place rather than
merely failing to find it.

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

**Training-data contamination is bounded but not eliminated.** Defects4J has
been public for years. If the M arm's detection rate reflected recall of known
faults rather than test-writing skill, the S arm would be expected to recall
them too and detect more than 14%. That it does not is evidence against pure
recall — but recall may be *cued* by the source rather than spontaneous, in
which case withholding the source suppresses the cue and not the memory. The
design cannot separate these. Replication on GitBug-Java, whose faults postdate
the model's training cutoff, is pending and is the single most important open
check.

**The acceptance filter uses the implementation as an oracle.** Tests that
disagree with the fixed code are removed, so what survives in the S arm is the
subset agreeing with the implementation. This favours the S arm, not the
finding: an unfiltered S arm would score no better. The M arm is subject to the
same filter.

**The sandbox contains compiled classes.** A decompiler or `javap -c` would
recover the logic. The prompt forbids it and the sandboxes are retained for
audit, but this is an honour-system control rather than a technical one.
Withholding the jar would leave the agent unable to compile, which was judged
the larger cost.

**The turn cap changed during the M-arm run** (25, then 40, then 50) as bugs in
older projects proved to need more iterations. Six M-arm suites ran under the
lowest cap. This works against the M arm, so against the reported effect.

**Six Lang bugs required stub test classes** to keep the build compiling after
deleting the developer tests. Those bugs ran in a slightly different
environment from the other 34, in both arms equally.

**Only one side of the mirror is tested.** The implementation-visible arm reads
the *repaired* revision. The complementary condition — an agent reading the
*faulty* revision, where a mirror would certify the defect rather than expose
it — is not covered here and is reported by Konstantinou et al. (see §6). Our
72% therefore characterises an evaluation protocol, not agent behaviour during
development.

### 5.2 Construct validity

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

> **Partially verified.** The Konstantinou et al. subsection below has been
> checked against the paper itself. The remaining entries are still assembled
> from abstracts and must be read before publication.

### Error propagation in code-then-test workflows

Konstantinou, Tambon and Papadakis, *"On the risk of coding before testing: An
empirical study on LLM-based test generation workflow"* (arXiv:2607.05139)
study the complementary condition to ours. Their pipeline generates candidate
implementations with an LLM, retains only the faulty ones — "we discard the
cases that the model is generating correct code and keep only those that are
faulty" — and compares test suites generated from that faulty implementation
against suites generated from the task description alone. Tests generated after
faulty code detect 14% of faults against 25% for tests generated from the
description; exposing the implementation reduces detection by 9 to 18 points
across five models. They name the phenomenon *error propagation*.

Their subjects are HumanEval+, MBPP and BigCodeBench: Python programming tasks
with LLM-generated faulty implementations. Their specification is the
benchmark's natural-language task description.

Taken together, the two studies cover four conditions along one axis — the
quality of the oracle available to the generating agent:

| oracle available to the agent | detection | source |
|---|---|---|
| complete natural-language specification | 25% | Konstantinou et al. |
| partial documentation (javadoc) | 14% | this work |
| faulty implementation | 14% | Konstantinou et al. |
| **repaired implementation** | **72%** | this work |

The two middle rows agreeing at 14% is coincidence; the figures come from
different corpora, languages and models, and are not directly comparable. The
ordering is the point. A complete specification is a usable independent
oracle. Partial documentation is a weak one. A faulty implementation is an
actively misleading one. And a *repaired* implementation is not an oracle at
all in the relevant sense: it hands the agent the answer.

Three differences position this work against theirs:

- **Subjects.** Real faults from four real projects, with the fault
  distribution that comes with them, rather than LLM-generated faults on
  benchmark tasks.
- **Metrics.** They measure fault detection and statement coverage. They do not
  measure mutation score in this contrast, and the insensitivity of mutation
  score to the manipulation is our central observation. Their coverage result
  — "no consistent relationship between statement coverage and fault
  detection" — independently corroborates half of ours, on a different
  language, corpus and set of models.
- **Framing.** Their threat to validity concerns coupled generation pipelines
  in which one model produces both code and tests. Ours concerns the
  evaluation protocol of real-fault benchmarks, where the suite is generated
  against the repaired revision. The two are adjacent and distinct: theirs is
  about development workflows, ours about measurement.

We also adopt their distinction between **fault triggering** — the test
provokes behaviour differing from the reference — and **fault detection**,
which additionally requires the assertion to be correct. The gap between the
two measures wrongly expressed assertions. Our harness reports detection only;
reporting triggering as well is straightforward and left for future work.

### Other threads to check

*(Not yet verified against sources.)*

- **Just, Jalali, Inozemtseva, Ernst, Holmes and Fraser, "Are Mutants a Valid
  Substitute for Real Faults in Software Testing?"** (FSE 2014). The
  foundational study on mutant–real-fault coupling, by the authors of
  Defects4J, over 357 real faults, reported to find a significant correlation
  between mutant detection and real-fault detection, independent of coverage.
  Our result does not contradict it: within each arm the suites may couple
  normally. What we observe is that the metric does not separate two
  *populations* of suites. This needs stating carefully.
- **Inozemtseva and Holmes** on coverage as a poor proxy for suite
  effectiveness, and recent replication work questioning those correlations for
  LLM-generated suites specifically.
- **Oracle-generation work** (TOGA, TOGLL and successors), reported to note
  that models are "prone to asserting the current (potentially buggy)
  implementation" — the mirror hypothesis already stated in the literature,
  and to be cited as such rather than presented as new.
- **TDD-Bench Verified** (Ahmed et al.) for tests written before a fix exists,
  the closest published framing to our specification-only arm.

## Data availability

All scripts, raw artifacts and per-bug measurements are in the repository:
`bin/run-agent-suites.sh`, `bin/run-spec-suites.sh`,
`bin/analyze-agent-suites.sh`, with raw output under `data/` and the full
method record in `data/README.md`.

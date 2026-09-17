# What Does an Agent-Written Test Suite Owe to Reading the Code?

*Draft — method and results. Introduction, related work, discussion and threats
to validity are pending.*

---

## 1. Introduction

*(Pending. The claim to lead with, subject to revision after the related-work
review: **mutation score does not distinguish a test suite whose oracle comes
from an independent specification from one whose oracle was read off the
implementation**, even though the two differ five-fold in their ability to
catch real faults.)*

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

*(Pending.)*

Points to develop:

- Mutation score and coverage measure whether a suite *discriminates
  behaviour*. Both arms do. What differs is the **provenance of the oracle**,
  and no execution-based metric observes provenance.
- The practical consequence for anyone evaluating agent-written tests: a high
  mutation score is evidence that the tests exercise the code, not that they
  encode correct expectations.
- The only mechanism demonstrated here to separate the two is the
  counterfactual itself — generate the suite twice, with and without the
  implementation, and compare. It doubles the cost.
- The M arm's 72% is an upper bound, not a capability measure: the agent reads
  the *fixed* code, which already contains the repair, so a test written for
  current behaviour catches the fault by construction. An untested variant
  worth running is the agent writing against the *buggy* revision, where a
  faithful mirror would certify the fault instead.

## 5. Threats to validity

*(Pending.)*

Points to develop: training-data contamination and the pending GitBug-Java
replication; the acceptance filter's use of the implementation as an oracle;
one model, one language, four projects from two ecosystems; the Opus arm's
non-random selection; `Fail` as a binary outcome ignores how many tests detect
the fault.

## 6. Related work

*(Pending.)*

## Data availability

All scripts, raw artifacts and per-bug measurements are in the repository:
`bin/run-agent-suites.sh`, `bin/run-spec-suites.sh`,
`bin/analyze-agent-suites.sh`, with raw output under `data/` and the full
method record in `data/README.md`.

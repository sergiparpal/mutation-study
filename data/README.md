# Study data

## Source

Defects4J v3.0.1, Java 11, `TZ=America/Los_Angeles`.

## Sample (`sample.txt`)

40 bugs across 4 projects, drawn with deterministic random selection:

```bash
defects4j bids -p Lang | shuf -n 12 --random-source=<(yes) | sed 's/^/Lang,/'
for p in Csv Gson Cli; do
  n=$([ $p = Cli ] && echo 8 || echo 10)
  defects4j bids -p $p | shuf -n $n --random-source=<(yes) | sed "s/^/$p,/"
done
```

Breakdown: Lang 12, Csv 10, Gson 10, Cli 8.

**The sample was fixed before classification began.** No bugs are added or
removed afterwards.

### Representativeness caveats

For Lang, this is a random sample of 61 active bugs. For Csv and Gson, the
total bug count per project is small, so 10 approaches a census — results for
those projects describe the project itself, not a wider population.

Observations within a project are also not fully independent. Three of the
twelve Lang bugs fall in `NumberUtils`; three of the ten Csv bugs fall in
`CSVFormat`/`CSVParser`, and two of those (Csv-7, Csv-8) address the same
requirement — duplicate header names must be rejected — failing by different
routes. Treat per-project counts as weaker evidence than the raw n suggests.

## Pilot

Lang-1 and Lang-3 were examined **before** the sample was fixed, and generated
the working hypothesis (predominance of omission faults). They are marked
`phase=pilot` and **excluded from analysis**, even if they were to reappear in
the sample by chance.

---

# Study A — fault taxonomy and mutation coupling

## Taxonomy (`fault-taxonomy.csv`)

Hand classification of all 40 diffs. Complete.

### `fault_type`

| Value | Definition |
|---|---|
| `SUBSTITUTION` | wrong operator, value or variable |
| `OMISSION` | missing logic: a condition, a branch, a loop |
| `MISSING_CLAUSE` | the condition existed but was missing a clause |
| `ALGORITHM` | the whole approach is wrong; the fix rewrites it |
| `STATE` | ordering, lifecycle, concurrency |
| `API` | incorrect use of another API, or wrong exception |
| `UNCLEAR` | to be reviewed at the end |

Final distribution: OMISSION 22, ALGORITHM 6, SUBSTITUTION 5, STATE 3,
MISSING_CLAUSE 3, API 1.

*(This line used to read 21, 7, 5, 4, 3, 1, which sums to 41. The CSV has
always held the figures above. The wrong tally is the one the quotas in
`matched-quotas.md` were scaled from, and the "21 of 40 omissions" of the first
write-up.)*

#### Rule: `OMISSION` requires an addition-only fix

`OMISSION` applies only when the fix **adds** lines without modifying existing
ones — a diff of `+n/-0`, or where the removed lines are pure context
(unchanged code re-indented or re-wrapped around the addition).

If the fix both adds and rewrites existing logic, it is not `OMISSION`. Use
`MISSING_CLAUSE` when an existing condition gained a clause, or `ALGORITHM`
when the approach itself was replaced.

Rationale: with one category likely to dominate this sample, `OMISSION` is at
risk of becoming the default bucket for anything that roughly fits. The
`+n/-0` test is mechanical and leaves no room for drift.

*(Note: Lang-1 is recorded as `OMISSION` at `+9/-2` and would not satisfy this
rule. It is pilot data and excluded from analysis, so it was left as-is.)*

*(Limitation: the `+n/-0` test is sensitive to how the guard is written. An
`if` wrapper leaves the original line untouched (`+n/-0`); a ternary rewrites
it (`+1/-1`), despite being the same kind of fault. Csv-4 and Gson-10 are such
cases, classified `OMISSION` with the original expression preserved verbatim
inside the new ternary. Flagged for final review.)*

#### Rule: one row per Defects4J bug, even when it bundles several faults

Some Defects4J bugs contain more than one distinct fault, because the fix
commit addressed several at once. One row is still recorded, classified by the
dominant category, with the individual faults enumerated in `note`.

Known cases:

- **Lang-62** — three faults in one fix: a missing `0xFFFF` range guard
  (appearing twice), a missing `break` causing switch fall-through, and an
  empty `catch` leaving a stale value. All three are omissions, so the
  category is unambiguous.
- **Lang-36** — a condition gained a clause (`&& lastChar != '.'`) and a
  separate validation block was added in `isNumber`. Same root cause, so
  classified `MISSING_CLAUSE` on the dominant fault.
- **Lang-65** — a 30-line truncation block absent between existing marker
  comments, plus two minor missing guards. Classified on the dominant fault.

### `nearby_mutant_RETIRED` — withdrawn, do not use

**Status: retired 2026-09-09.** The column remains in the CSV for provenance
and is renamed so it cannot be mistaken for a live variable. **No figure
derived from it appears in any result.**

Original definition: `YES` when at least one arithmetic, relational or logical
operator, or one literal constant, appears in the lines the fix modifies or in
lines immediately adjacent. Intended to capture whether a classical mutation
operator would have anywhere to anchor within the faulty region.

Two independent reasons for withdrawal:

1. **Miscalibrated.** It was judged by reading diffs, never measured. The first
   measurement refuted it: Major generates mutants in Lang-13's faulty region
   (two LVR on the `false` argument of `Class.forName`), which the definition
   missed because it counted only arithmetic, relational and logical operators
   and numeric literals — overlooking boolean, null and string literals, which
   are pervasive in object-oriented code. The 17/40 "sterile region" figure it
   produced is void.

2. **Superseded by measurement.** The question it was reaching for is answered
   directly, and mechanically, by `mutation-metrics.csv`:
   `n_mutants_in_fix_methods`, `n_coupled_in_fix_methods`,
   `n_coupled_on_touch_lines` and `ops_coupled_in_fix_methods`. Those are tool
   output over 36 bugs; this was one person's reading of 40 diffs.

Remeasuring it with a corrected definition was considered and rejected: the
corrected number would duplicate what the measured columns already report,
at the cost of re-reading all 40 diffs by hand.

`fault_type` is unaffected and remains in use. It was expected to explain which
faults the spec-only arm of Study B detects, and turned out not to (see
`contract-violation.md`).

## Classification protocol

1. Only the diff over `dir.src.classes` between buggy and fixed versions is
   examined.
2. **Trigger tests are not consulted** during classification: they reveal where
   the fault lies and bias the judgement on `nearby_mutant_RETIRED`.
3. `UNCLEAR` entries are reviewed as a batch at the end.
4. **Re-read performed.** Once finished, the first 10 entries were re-read
   under the final criteria, since criteria drift over the course of
   classification. All ten were sustained: the six `OMISSION` entries satisfy
   the mechanical `+n/-0` test, and the four others (Lang-56 `STATE`, Lang-8
   and Lang-21 `SUBSTITUTION`, Lang-63 `ALGORITHM`) were confirmed to remove
   real logic rather than re-indented context. The criteria were fixed early
   enough — around the third and fifth bug — that no drift accumulated.

## Mutation measurement (`mutation-metrics.csv`)

Produced by `bin/run-mutation.sh` (collection, ~34 min for the sample) and
`bin/analyze-mutation.py` (analysis). Raw artifacts under `data/raw/`, one
directory per bug, so the analysis can be rerun without repeating any
defects4j work.

### Protocol

For each bug, on the **fixed** version:

- `defects4j mutation -r` — the relevant developer test suite.
- `defects4j mutation -t` with a single trigger test — once per trigger test, in isolation.
- `diff -ru` between buggy and fixed `dir.src.classes` — to know which lines
  the fix touches.

Mutants killed by a trigger test running alone are called **coupled**.

### Tooling facts worth recording

- Major's default operator set is **AOR, LOR, SOR, COR, ROR, ORU, LVR, STD**.
  Statement deletion is enabled by default.
- By default only the classes modified by the fix are mutated, so no filtering
  by file is needed.
- Kill statuses are `FAIL` (assertion), `TIME` (timeout), `EXC` (exception),
  `LIVE`, `UNCOV`.

### Deviations and exclusions

- **`-r` instead of the full suite.** The unrestricted run aborts on unrelated
  flaky tests — Lang-56 failed on `StopWatchTest::testStopWatchSplit`, a
  wall-clock test with no bearing on `FastDateFormat`. "Full suite" in this
  study therefore means *relevant tests*. Defensible, since irrelevant tests
  cannot kill mutants in these classes, but it is a deviation.
- **Gson-14 and Gson-16 excluded.** Major's mml compiler rejects the class
  name: `invalid scope: com.google.gson.internal.$Gson$Types`. A tool
  limitation with the `$` in the file name, not a property of the bugs.
  **38 of 40 bugs analysed.**

### Method attribution

Major reports a method signature and line per mutant but nothing about method
boundaries, so spans are inferred as min..max over each method's own mutants,
then widened into the gaps between neighbouring methods (capped at 30 lines).

The widening is not cosmetic. Without it, Lang-8 reported zero mutants in the
fix's methods: the line the fix adds (`TimeZone zone = calendar.getTimeZone();`)
contains no operators or literals, generates no mutant, and therefore fell one
line below the method's first mutant. That failure mode is systematic, since
lines with nothing mutable are exactly the ones of interest.

The `attribution` column flags bugs where the fix touches a class but no method
matched, so a zero is never silently mistaken for a real result.

### Dilution by multiple triggers

Some fixes break many tests: Lang-34 has 27 trigger tests, Csv-14 has 6. The
union of what 27 tests kill is not "the test that catches the fault". Those
bugs are flagged in `attribution` and reported separately; the headline figures
use the 36 bugs with 5 triggers or fewer.

### Headline results (36 clean bugs)

- Coupled mutants: 2150 anywhere in the mutated classes, **919 inside the
  methods the fix touches** (43%), 185 on the fix's exact lines. An unrestricted
  coupling measure overestimates by ~2.3x.
- Operators generating coupled mutants: ROR 234, LVR 208, COR 205, STD 137,
  AOR 135. **Spread across the classical catalogue; STD does not dominate.**
- Kill kinds among coupled mutants: FAIL 520, EXC 377, TIME 22 — **56% die by
  assertion.**

Both figures contradict hypotheses formed earlier from two or three bugs. See
`IDEAS.md` for what was refuted and when.

---

# Study B — what does an agent-written suite owe to reading the code?

Complete. Two arms over the same 40 bugs, designed to differ in one variable:
whether the agent can read the implementation. The comparison was made twice.
The first campaign, on standard Defects4J checkouts, is what the sections
before "Second campaign" describe. An audit found that its
implementation-visible arm was told more than the implementation ("What those
controls do not close"). The second campaign closes that and is the controlled
comparison. Its section holds its results.

- **M arm (implementation-visible)** — `bin/run-agent-suites.sh`. The agent
  works inside the checked-out project and reads the fixed source. This is
  what happens when anyone asks a coding agent for tests on existing code.
- **S arm (spec-only)** — `bin/run-spec-suites.sh`. The agent works in a
  sandbox holding generated javadoc, the compiled jar and JUnit. It never sees
  implementation source and may not execute its tests.

Suites are analysed by `bin/analyze-agent-suites.sh`, which wraps Defects4J's
own `run_bug_detection.pl`, `run_coverage.pl` and `run_mutation.pl`, and merged
by `bin/merge-agent-metrics.py`. `bin/report-figures.py` prints every figure
below, and every figure in the write-up, from the files in this directory.

## Results

Of the first campaign. Per arm, over every suite measured:

| arm | suites | real fault detected | mutation score | line coverage |
|---|---|---|---|---|
| `agent` (Sonnet, M) | 36 | **26/36 — 72%** | 58% | 85% |
| `agentopus` (Opus, M) | 6 | 6/6 | 70% | 89% |
| `spec` (Sonnet, S) | 38 | 6/37 — 16% | 44% | 73% |
| `evosuite` | 36 | 15/35 — 43% | 47% | 85% |

Detection is over suites classified `Pass` or `Fail`; one `spec` suite and one
`evosuite` suite are `Broken`. EvoSuite's coverage is over 35 suites. Five of
the `evosuite` rows were measured a second time under a corrected harness
(below).

Paired over the 36 bugs present in both Sonnet arms:

```
detection   M 26/36 (72%)   vs   S 5/36 (14%)
mutation    M 58%           vs   S 44%
coverage    M 85%           vs   S 73%

Cli    n=7    M=5   S=1
Csv    n=9    M=7   S=2
Gson   n=8    M=6   S=1
Lang   n=12   M=8   S=1
```

**Two things follow.**

Roughly four fifths of the M arm's real-fault detection is gone when the
implementation is withheld. The effect holds in all four projects.

And the standard metrics show only a fraction of it. Mutation score falls from
58% to 44%, with the M-arm suite higher in 35 of the 36 bugs, and line coverage
from 85% to 73% — factors of 1.3 and 1.2 against a factor of five in detection.
About half of the mutation gap is coverage (25.6% of mutants are never executed
by the S-arm suites, against 13.6%) and half is kill rate on the mutants each
arm does execute (59% against 67%).

### Mutation score: do not use Defects4J's `mut_killed`

**This is the error that produced this study's first, wrong, headline.**
`run_mutation.pl` writes a table whose `mut_killed` column is every mutant
that is not `LIVE` in Major's `kill.csv`, and whose `mut_covered` column is
every mutant in that file (`framework/core/Mutation.pm`, `_build_data_hash`).
Major lists each mutant as `FAIL`, `TIME`, `EXC`, `LIVE` or `UNCOV`, so the
table counts the mutants no test executes as killed, and `mut_covered` always
equals `mut_generated`. A suite that executes less scores higher. The EvoSuite
suite for Gson-3 covers 0 of 94 lines and is credited with 34 of 34.

Until November 2026 this file and the write-up reported
`mut_killed / mut_generated` from that table: 72% for the M arm and 70% (71% in an earlier
analysis run) for the S arm, "statistically indistinguishable". Those figures
are each arm's real score plus its share of uncovered mutants, 13.6 and 25.6
points.

`bin/merge-agent-metrics.py` recomputes the columns from the `kill.csv` files
under `agent-results/mutation_log/`. In `agent-metrics-final.csv` and
`agent-results/agent-metrics.csv`:

| column | meaning |
|---|---|
| `mut_generated` | as reported by Defects4J |
| `mut_covered` | mutants with a status other than `UNCOV` |
| `mut_killed` | `FAIL` + `TIME` + `EXC` |
| `mut_killed_d4j` | what the Defects4J table calls `mut_killed`, kept so the earlier figures can be traced |
| `harness` | `stock` when the row's detection and coverage figures are Defects4J's as first measured; otherwise the name of the directory under `agent-results/remeasured/` they come from |

`agent-results/mutation` is Defects4J's table, left as it was written. Study A
was never affected: `bin/analyze-mutation.py` has always read `kill.csv`
directly and counted `FAIL`, `TIME` and `EXC`.

Figures are pooled (mutants killed over mutants generated, summed across the
suites of an arm). Averaged per suite the arms are at 67.6% and 48.5%.

### `Broken` is not a missed detection

`run_bug_detection.pl` classifies a suite as `Broken` when it does not compile
on one of the two revisions or has a failing test on the revision it was
generated for. Seven suites came out `Broken`, and were counted as failures to
detect until November 2026. Two still are:

- `evosuite` Csv-16 — references `CSVParser.CSVRecordIterator`, a class the fix
  introduces, and does not compile against the buggy revision.
- `spec` Cli-21 — calls `WriteableCommandLine.setCurrentOption`, an interface
  method the fix adds, and does not compile against the buggy revision. The
  javadoc the agent wrote from is the fixed revision's.

The other five were never broken. `evosuite` Cli-10, Cli-12, Cli-17, Cli-28 and
Cli-32 failed to load on both revisions with `NoClassDefFoundError:
org/hamcrest/SelfDescribing`. The cause is one line of Defects4J (v3.0.1). Its
build file for the project, `framework/projects/Cli/Cli.build.xml`, redefines
`junit.jar` as `file://${d4j.home}/framework/projects/lib/junit-4.12.jar`, a
file the framework does not ship (it ships `junit-4.12-hamcrest-1.3.jar`). The
harness therefore has Hamcrest only where the project supplies it, and these
revisions ship JUnit 3.8. Cli-38, a later revision, is unaffected. The same
suites ran under the mutation harness as they were.

### The five Cli EvoSuite suites, measured again (`agent-results/remeasured/cli-junit-fix/`)

`bin/remeasure-cli-evosuite.sh` runs `run_bug_detection.pl` and
`run_coverage.pl` with that one path pointed at the jar that exists. It does
not touch the Defects4J installation: Defects4J reads its per-project files
from `$PROJECTS_DIR` when that is set, so the script builds a directory of
links to the installation's `projects/` in which `Cli.build.xml` alone is a
corrected copy. `Cli.build.xml.patch` in the output directory is the
difference, one line.

Run on 17 November 2026, in the environment of the original measurements
(Defects4J `v3.0.1-7-g8c16da82`, Java 11):

| suite | stock harness | junit path corrected | coverage, lines |
|---|---|---|---|
| Cli-10 | `Broken` | `Pass` | 95/106 |
| Cli-12 | `Broken` | `Pass` | 26/28 |
| Cli-17 | `Broken` | `Fail`, 1 test | 63/68 |
| Cli-28 | `Broken` | `Pass` | 89/101 |
| Cli-32 | `Broken` | `Fail`, 6 tests | 200/201 |
| Cli-38 | `Fail`, 1 test | `Fail`, 1 test | 159/193, as before |

Cli-32's six failing tests all end in `StringIndexOutOfBoundsException`, the
exception of the developer's own trigger test. The run was made three times
(twice by hand, once by the script) with identical tables.

**Control.** The script also measures every Cli suite of every generator with
the correction, 21 in all, into `control/`. The sixteen that are not among the
five came out exactly as in the stock tables, detection and coverage: the
correction changes nothing for a suite that could already load.

**How it enters the figures.** `agent-results/bug_detection` and
`agent-results/coverage` are Defects4J's tables as first written, and still say
`Broken` for the five. `bin/merge-agent-metrics.py` replaces a stock row with
the re-measured one where they differ and writes `cli-junit-fix` in the
`harness` column of the merged file. EvoSuite is therefore at 15/35, not 13/30,
and its coverage is over 35 suites, not 30. Lang-34, where a test fails under
the coverage harness, still has no coverage figure.

A first attempt, made earlier the same day inside a command sandbox, left
Cli-32 `Broken`: one test that depends on the environment failed on the fixed
revision there. It passes outside the sandbox, which is where every other
measurement in this directory was made.

### Which faults the spec arm does catch

Cli-32, Csv-4, Csv-6, Gson-15, Lang-13 — five of thirty-six. Three are cases
where the code contradicts a contract the javadoc states:

- **Cli-32** — `findWrapPos` is documented to return `startPos+width` when no
  whitespace precedes it; the faulty loop scanned past it.
- **Lang-13** — the class javadoc promises deep cloning by serialization;
  cloning primitive `Class` objects failed.
- **Gson-15** — `setLenient`'s javadoc says a lenient writer permits NaNs and
  infinities; `value(double)` rejected them in either mode. The detecting test
  quotes that sentence.

Csv-4 and Csv-6 are not: nothing in the javadoc covers a parser with no header
or a record shorter than its header. Both are reached by probing boundaries.

This count has been wrong twice. It was first given as four of five, inferred
from the fault descriptions without reading any javadoc; then as two of five,
from the javadoc of the modified *method* alone, which for Gson-15 says the
opposite of `setLenient`. The classification is not blind either way: see
`contract-violation.md`.

## M arm — configuration

| | |
|---|---|
| Claude Code | 2.1.251 (native install, linux-x64) |
| Models | `--model opus` → `claude-opus-5` (9 runs, 6 suites kept), `--model sonnet` → `claude-sonnet-5` (40 bugs) |
| Turn cap | 25 for the Opus runs, 40 then 50 for Sonnet |
| Tools | `Read,Write,Bash` |
| Permissions | `--permission-mode acceptEdits` |
| Output | `--output-format json`, one file per run: the closing message, cost and turn count. Not a transcript |
| Cost | $42.61 for the 40 Sonnet suites ($1.07 each); the nine Opus runs cost a further $12.32, of which $10.13 for the six suites kept. List price against subscription quota |

The model is passed on the command line rather than left to
`~/.claude/settings.json`, which held `"model": "opus"` and
`"effortLevel": "xhigh"`. Local configuration must not silently define the
experiment. **The effort level was not overridden**, so the runs can be assumed
to have inherited `xhigh`.

**`--bare` cannot be used.** It is the documented way to skip auto-discovery of
CLAUDE.md, hooks, skills, plugins and MCP servers, which is exactly what
reproducibility wants — but with `--bare` every run fails with
`Not logged in · Please run /login` despite valid credentials in
`~/.claude/.credentials.json`. Runs are therefore made **without** `--bare`
from a clean checkout under `/tmp`, which contains no project-level
configuration.

### Model arms are not comparable as a designed contrast

Nine Opus runs were started, on the first nine bugs of the sample, before the
quota ran out and the run switched to Sonnet. Two ended in errors, and one
(Lang-52) produced a suite that failed on the fixed revision and was rejected.
The six suites kept are therefore six of the first seven bugs, not a random
subset and not the first six. They are reported separately as an opportunistic
indication, never as a model comparison. The turn cap also differs between
them (25 vs 40/50).

### Loop per bug

```
checkout _f
export metadata                          BEFORE removing .git
rm -rf .git                              contamination control, below
delete the developer test files holding the trigger tests
  → if that breaks the build, replace them with stubs
[agent writes tests]
verify: file exists, compiles, passes on _f
package as <Project>-<bid>f-agent.1.tar.bz2
```

### The prompt changed once

Verification originally told the agent to run its tests with
`org.junit.runner.JUnitCore`. When that broke on Cli's JUnit 3.8 the wording
was changed to name both runners and warn about JUnit 3. The seven Cli suites
generated afterwards (all but Cli-38; they are the ones with a `.runner` file)
got the new wording; the other 33 got the old.

The M prompt has never asked for self-contained test classes. An earlier
version of this file said it "now" did; no suite was regenerated and the script
carries no such requirement. The S prompt does ask for it.

## S arm — configuration

Same model and flags as the M Sonnet arm, `MAX_TURNS=50`. Cost: $37.02 for 40
suites ($0.93 each). The sandbox given to the agent:

```
api/          javadoc for the classes under test — the spec
lib/          the compiled project jar and JUnit — so tests can be COMPILED
tests/        where the agent writes
compile.sh    compiles tests/ against lib/ at the project's own -source level
```

The prompt forbids running the tests, decompiling or disassembling `lib/`,
inspecting version control and searching the web. Nothing enforces any of it.
Sandboxes were kept under `/tmp/specW_*` on the generating machine as an audit
trail; they are not in this repository and no transcript of any run exists, so
compliance cannot be checked from the artifact.

The M and S prompts share two instructions — assert on returned values and
observable state, cover boundary and error cases — and differ otherwise. The M
prompt says "Test only the public API"; the S prompt does not, and its javadoc
is generated with `-package` (below), so the S arm may test protected and
package-private members. Its detection of Cli-32 does.

### Javadoc invocation — four details that had to line up

- Pass **file paths**, not fully-qualified class names. Given a qualified name
  without `.java`, javadoc treats it as a package (found on Lang-43).
- Keep `-sourcepath` anyway, so sibling classes referenced by the source
  resolve, otherwise "cannot find symbol: class Validate".
- Use `-package`, not `-public`: some classes under test are package-private
  and `-public` documents nothing (Lang-62). `-package` gives the agent what a
  developer in the same package would see, which is the situation modelled.
- Judge success by the existence of `api/index.html`, never by exit status:
  this vintage of source produces warnings javadoc reports as non-zero.

The javadoc is generated from the **fixed** revision. Where a fix changes the
public surface, the documentation the agent reads describes the repaired API
(Cli-21, above).

### Source level

The sandbox compiles with the project's own `-source` level, read from
`default.properties`. Lang-65 was initially lost because the agent wrote
`1_017_320_701_000L`, valid under the sandbox's default javac but not under the
project's `-source 1.6`. The level is passed to `compile.sh` and stated in the
prompt. **The first seven suites predate this** (Lang-13, -23, -43, -52, -56,
-63, -8: the ones with no `.srclevel` file) and were generated without the
constraint.

### Per-method filter, and its bias

An agent writing from the API alone gets some expectations wrong. Discarding a
whole suite over one wrong expectation would throw away most of the sample, so
failing methods are disabled individually by `bin/prune-failing-tests.py` — the
`@Test` annotation is commented out (JUnit 4) or the method renamed
(JUnit 3) — and the rest are kept.

**Measured prune rate: 59 of 1638 tests (3.6%)**, with a clear gradient:

```
Lang    4 / 579   0.7%    Commons javadoc is unusually explicit
Csv    10 / 467   2.1%
Cli    12 / 203   5.9%
Gson   33 / 389   8.5%    reflection and generics, sparser documentation
```

This retires the hypothesis that the spec arm would mostly guess: writing from
javadoc produces few wrong expectations.

*(Counting error, corrected November 2026. The total was counted with
`grep -cE "@Test|public void test"`, which counts lines: a JUnit 4 method with
both the annotation and a `test`-prefixed public signature was counted twice.
Six suites had their totals doubled — Cli-38, Gson-6, Gson-7, Gson-10, Gson-14,
Gson-16 — and Lang-43, run before any counting existed, was recorded as
`0 0`. The published rate was 59 of 1806 (3.3%), with Gson at 5.7%. The seven
`.pruned` files have been corrected from the packaged suites and the JUnit
logs: Cli-38 `0 18`, Gson-6 `1 11`, Gson-7 `7 50`, Gson-10 `5 22`, Gson-14
`2 56`, Gson-16 `4 49`, Lang-43 `0 38`. For all forty suites the corrected total
equals the tests the JUnit log reports plus the tests pruned. Counting is now
done by `prune-failing-tests.py --count`.)*

**Declared bias.** That filter uses the implementation as an oracle, so what
survives is precisely the subset agreeing with the code. It only removes, never
rewrites, and the survivors were written blind — but the selection is biased
and is reported as such. The M arm reaches the same end state by another route:
its agent runs the tests and revises them until the whole suite passes.

*(Stale class files: disabling a method changes the `.java` by a few bytes
within the same second, and ant's one-second timestamp granularity then skips
the recompile, so the next run executes the pre-prune bytecode and the loop
never converges (Lang-21). `touch` does not help. The compiled test classes are
deleted before recompiling, inner classes included.)*

*(Runs repeated after such failures overwrote the record of the run they
replaced. Lang-21's S-arm suite is a second generation; the first cost $1.48
and is not in the total above.)*

## Contamination controls

- **Git history is removed before the agent starts.** A Defects4J checkout
  ships the project's full history including the fix commit: for Lang-13 the
  log subject reads `[LANG-788] SerializationUtils throws ClassNotFoundException
  when cloning primitive classes`, and the `D4J_Lang_13_BUGGY_VERSION` /
  `_FIXED_VERSION` tags make `git diff` yield the patch. The first pilot run
  produced a test citing "LANG-788" in a comment.

  *Measured effect on that pilot:* none on mutation score or fault detection
  (identical), +6 covered lines. A real leak but a weak one when the agent can
  already read the fixed implementation — it matters far more for the S arm,
  where the code is withheld.

- **The trigger test file is deleted, not just the failing method.** Leaving
  the rest of the class would show the agent what is tested and how.

- **Training-data contamination cannot be eliminated.** Defects4J has been
  public for years. It is measured by a direct probe and by two post-cutoff
  corpora, below.

### What those controls do not close

Found in November 2026, after all the runs. A Defects4J checkout, with `.git`
and the trigger test's `.java` file gone, still hands the M-arm agent:

- `defects4j.build.properties` and `.defects4j.config`. The first names the bug
  (`d4j.bug.id`, `d4j.project.id`) and lists its trigger tests in full
  (`d4j.tests.trigger=<Class>::<method>`). The working directory name
  (`/tmp/agentB_<Project>_<bid>_f`) carries the bug id too, and the `defects4j`
  command the prompt tells the agent to use answers `export -p tests.trigger`.
- `<Test>.java.bak` — Defects4J's backup of every test class it removes a
  flaky method from. Where that class is the trigger test's, the backup is the
  whole developer test, trigger included: Lang-34, Lang-56, Lang-63, Csv-7,
  Csv-16.
- the project's changelog. For Lang-13, `src/site/changes/changes.xml` has the
  LANG-788 sentence quoted above, so the pilot's "LANG-788" need not have come
  from git at all.

The agent used at least the first, and in one run the second (see the notes
below). `bin/audit-trigger-leaks.py` reports, for 13
of the 40 M-arm suites and 11 of the arm's 26 detections, one or more of: a
generated test with exactly the developer trigger test's name (Cli-12, Cli-17,
Csv-4, Csv-6, Lang-13 — in each case the test that detects the fault); a
closing message that names the trigger test (Csv-8, Lang-13, Lang-62) or its
own bug ("the Lang-13 regression", "the Lang-52 fix", "the Lang-63 trigger
scenario", "the CSV-106 / Csv-5 regression point"); or the issue number from
the trigger test's name, with that test's input and expected output reproduced
(Lang-43). None of the 40 S-arm suites or messages shows any of it. For Lang-13
and Lang-43 the body of the deleted trigger test is reproduced as well, which
no file in the working copy contains.

So the M arm is not "the agent can read the implementation". It is "the agent
has a Defects4J checkout". How much of its 72% the metadata accounts for cannot
be told from this data. The script is left as it ran; its header says what a
rerun should change.

### Notes three of the agents left behind (`agent-notes/`)

The runs used the operator's ordinary Claude Code profile, with its persistent
memory switched on. Memory is kept per working directory, outside it, under
`~/.claude/projects/`. Three runs wrote notes there. The notes were still on the
generating machine on 17 November 2026 and are archived here as they were, but
for one redaction: the generating machine's own time zone, in the Lang-63 note,
is replaced by `[redacted]`.

| run | directory | what the notes are about |
|---|---|---|
| M arm, Lang-52 | `agent-notes/M-Lang-52/` | conventions for the task; the behaviour of `StringEscapeUtils` in the fixed tree |
| M arm, Lang-63 | `agent-notes/M-Lang-63/` | conventions for the task; the bug and its trigger test |
| S arm, Csv-3 | `agent-notes/S-Csv-3/` | the API of the jar, found by trial compilation |

Each note's `originSessionId` is the `session_id` of the run recorded in
`agent-runs/` or `spec-runs/`, so each was written by the run whose suite is
published. No notes of any other run were found. They are the only first-hand
record of what an agent read.

- **Lang-63.** The note names the trigger test and gives its input and
  expected output: "d4j trigger `DurationFormatUtilsTest::testJiraLang281`
  (2005-12-31 -> 2006-10-06, "MM" -> "09")". It cites `.defects4j.config`. Of
  the developer tests the script removed it says: "sometimes kept as
  `.java.bak` — useful for known-good expected values". The one test of the
  suite that fails on the buggy revision,
  `testFormatPeriodMonthsAcrossYearBoundary`, has those dates, that pattern and
  that expected string. Their only copy in the working tree was
  `DurationFormatUtilsTest.java.bak`: the live file had been replaced by a
  stub. So this detection is the developer's trigger test, copied from
  Defects4J's backup of it. The agent used the second leak above as well as the
  first.
- **Lang-52.** The note identifies the repair: "`escapeJava` AND
  `escapeJavaScript` both escape the forward slash … (this is the Lang-52
  fix …)".
- **Csv-3, S arm.** The note describes the task as the prompt set it, "against
  `api/` javadoc only, compile with `./compile.sh` (never run)", and says the
  API of the jar was "discovered by trial compilation (bytecode inspection was
  disallowed)". That is the agent's own account of complying, for one run. It
  also shows how little that sandbox documented: "Only
  `api/org/apache/commons/csv/Lexer.html` + package docs exist as spec; nothing
  for `CSVFormat`".

The other four bugs whose trigger class has a `.bak` were checked against the
backup by hand. None of their suites reproduces the trigger test: Lang-34
shares only the literal `<null>` with it; Lang-56 shares the date pattern
`yyyy/MM/dd`, which other developer tests left in the tree use too, and its
closing message derives the serialization test from the repaired `readObject`;
Csv-7 and Csv-16 share nothing.

**The runs were not isolated from one another.** A bug gets the same working
directory whatever the model (`/tmp/agentB_<Project>_<bid>_f`, unchanged since
the pilot), so the Opus pilot and the Sonnet arm shared a memory directory, as
would any repeated run. Nothing in the three notes comes from another run: all
were created by the recorded Sonnet sessions. The channel was open all the
same. A rerun should give each run an empty profile and keep its transcript.

## Baseline: EvoSuite

Generated with Defects4J's `gen_tests.pl` (EvoSuite 1.1.0, branch criterion,
test id 1). **The invocation was not scripted or logged.** From the timestamps
inside the archives — the suites were generated in sample order, 66 to 80
seconds apart for most single-class bugs — the total budget was 120 seconds per
bug (`-b 120`). Defects4J's `evosuite.sh` halves that between search and
assertion generation and divides it by the number of target classes: 60 seconds
of search per class, 30 for Gson-4's two. `evosuite-report/statistics.csv` is
EvoSuite's own branch-coverage report from those runs.

Suites were produced for 38 of the 40 bugs. `gen_tests` produced nothing for
Cli-15 and Cli-21, the `cli2` subjects. The Gson-14 and Gson-16 suites do not
compile (`illegal start of expression` on `$Gson$Types`) and were moved to
`agent-suites-broken/`. Of the 36 analysed, one is `Broken` for detection, and
five have their verdict from the corrected harness (above).

On the 34 bugs where M, S and EvoSuite all have a detection verdict:

```
            detection      mutation   coverage
M           24/34 (71%)    58%        85%
EvoSuite    14/34 (41%)    47%        85%   (33 suites)
S            5/34 (15%)    44%        73%

M and EvoSuite: both 10, M only 14, EvoSuite only 4, neither 6
```

EvoSuite and the S arm are nearly tied on mutation score — 47% and 44% pooled,
47% and 48% averaged per suite — and differ nearly three-fold in detection.

## Memorisation probe

`bin/probe-memorisation.sh` asks the model two questions per bug in a fresh
single-turn session: one naming the Defects4J bug id (A), one naming the first
modified class (B). `bin/grade-memorisation.py` screens the answers against
identifiers from the fix diff and writes `memorisation-grades.csv`.

- A: all 40 disclaimed.
- B: 25 disclaimed, 14 described a fault (5 flagged by the screen), and 1 gave
  no answer — the model tried a tool call, which a single turn cannot complete.

The screen compares an answer only with the diff of the bug the probe was
issued for, and at first only the flagged answers were read. All 14 have now
been read against every sampled fault in the same class;
`memorisation-readings.csv` records the result. Lang-13 is recalled with its
mechanism. So is Gson-16, in the answer to the probe for Gson-14: both are in
`$Gson$Types` and got the same question, and the Gson-16 probe itself
disclaimed. The answer for Lang-23 names LANG-477, the issue behind Lang-43;
the answer for Lang-56 gives the symptom of Lang-8. Four flagged answers are
confabulations. "Exactly one of forty", as first published, was wrong.

The probe says nothing about recall cued by the source, and the M arm had more
than the source to cue it (above).

## Post-cutoff corpora

Fix commits from the same four upstream repositories, recent enough to postdate
the model's training data. Mined by `bin/mine-postcutoff.sh`, run by
`bin/run-postcutoff.sh` (detection only), tallied by `bin/tally-postcutoff.py`.

| | subjects | runs |
|---|---|---|
| first corpus | `postcutoff-first/`, plus e992a498d and e0dba35f9 in `postcutoff/` | `postcutoff-first-runs/` |
| matched corpus | `postcutoff/`, selected per `matched-quotas.md` and `matched-candidates.csv` | `postcutoff-runs/` |

**First corpus.** 14 candidates (`postcutoff-candidates.txt`), 11 validated
fail-to-pass, 3 unusable in either arm because deleting the trigger test file
breaks other test classes. M arm: 6 of 8 detected. **The S arm has no valid
verdict.** The harness ran the buggy revision without `-Drat.skip=true` and
recorded any non-zero Maven exit as `Fail`. A test written in the sandbox has
no licence header, so all seven S-arm builds stopped at the RAT audit before a
test ran, and were published as 7/7 detected. The seven `.spec.detection` files
now read `build_failed_not_detection`, the verdict the corrected script gives
their logs. The generated tests were not archived, so the arm cannot be
re-measured.

The two subjects shared with the matched corpus were rerun for it, which
overwrote their first-corpus records. Those records were restored into
`postcutoff-first-runs/` from commit `5242c2e`.

**Matched corpus.** 20 candidates classified to pre-registered quotas, 19
validated, 4 unusable in either arm for the same compilation reason.

```
M   15 suites accepted, 14 with a verdict    8/14 detected (57%)
S   13 suites accepted, 13 with a verdict    4/13 detected (31%)

paired, 13 subjects:   M 8/13 (62%)   S 4/13 (31%)
detected by M only 4, by S only 0     exact McNemar p = 0.125
```

`commons-lang-e4380908b` has no valid S-arm verdict. Its latest run ended in
`failing methods could not be disabled` (parameterised tests failing on the
fixed revision, which the filter cannot disable). The `.spec.detection`,
`.spec.pruned` and `.spec.buggy.log` beside that status belong to an earlier
attempt, made under the old rule, whose build also died at the RAT audit. An
earlier summary counted it as a detection by the S arm alone and reported 14
pairs, a 21-point gap and *p* = 0.375.

Both arms use the per-method filter here. Recorded `.pruned` totals in these
two directories are doubled in nine files by the counting error described
above; the generated tests are not archived, so they have been left as written
and `tally-postcutoff.py` takes the number of tests from the surefire log
instead.

In these runs the M-arm agent works in a `git worktree`, with the repository's
history reachable. The Defects4J runs delete `.git`; here only the prompt
forbids git.

**Rejections recorded with the wrong reason (found 2026-11-19).** All five
rejections recorded under `postcutoff/` and `postcutoff-first/` give a reason
their logs do not support. They came to light when every 2026 fix commit of
Commons Lang, CSV and CLI was validated again, in clean clones and under the
same contract, to count the subjects available for a larger corpus
(`bin/revalidate-postcutoff.sh`). The `status` files are left as written; the
new runs of the three Commons Lang candidates, and a replay of their
checkouts, are in `postcutoff-revalidation/`.

- **`gson-698ba9eb` and `gson-e4f54f78`, matched corpus: never validated.**
  Both `buggy.log` files stop at the Maven enforcer: Gson requires JDK 17 and
  the machine had only JDK 11, so nothing was compiled or run. Their `status`
  files say the tests pass on the parent, and `matched-quotas.md` and
  `matched-candidates.csv` say they failed fail-to-pass validation. Neither is
  what happened. The fourth ALGORITHM slot stayed empty, and gson-e4f54f78's
  OMISSION slot went to `commons-lang-68c333308`, because of the build
  environment, not the candidates. Neither has been tried under JDK 17.
- **`commons-lang-581ce79c4` and `commons-lang-13d93944f`, first corpus:
  `cannot check out parent commit`.** Both parents check out in a clean clone.
  The checkouts failed on a file the previous candidate left behind. When
  `bin/mine-postcutoff.sh` rejects a candidate at the parent it runs
  `git checkout -- .`, which restores the working tree from the index, so the
  test file it had taken from the fix stays staged. After
  `commons-lang-ae85262f0` that file was `StringUtilsTest.java`, and both
  checkouts would have overwritten it. The mining clone's reflog shows HEAD at
  ae85262f0's parent until the next checkout that succeeded, to 9288e2c95's
  parent, which has the staged version of that file; replaying the script's
  commands gives both failures and that success
  (`postcutoff-revalidation/checkout-replay.txt`). Validated again, both are
  rejected anyway: with the fix's `StringsTest.java`, the parent's test sources
  do not compile. The outcome stands; the reason does not.
- **`commons-lang-ae85262f0`, first corpus: `tests pass on the parent`.** They
  did not pass: the forked test JVM died with `Java heap space` (`buggy.log`,
  from line 887). The script takes the trigger tests from the per-test failure
  lines of Maven's summary, found none, and read that as a pass. Its
  `classes.txt` and `testclasses.txt` are also empty, so `-Dtest` named no
  class and the whole suite ran; the committed script lists one class of each
  for this commit, and the record does not show why the lists are empty.
  Validated again with the fix's `StringUtilsTest` alone, the test JVM runs out
  of memory on the parent, and the fix passes it (173 tests, one skipped). The
  candidate meets the contract: twelve of the first corpus's fourteen
  candidates do, not eleven, and the third campaign, whose subjects are the
  validated commits of both corpora, would have had 29. Its protocol and
  results stand as run.

The trigger pattern also misses a failure inside a lambda (reported as
`Class.lambda$name$N:line`), an error with no line in the test class
(`Class.method » …`), and every line of a log in which a test wrote NUL bytes,
which `grep` then reads as binary. None of these changed a recorded status.

## Second campaign

The comparison of the two arms, made again on the same 40 bugs with the leaks
of the first campaign closed, under a protocol fixed before any run on the
sample. It is the controlled comparison and the study's primary result. The
first campaign's arms are separate conditions and are never pooled with it.

```
detection, 39 bugs with a verdict in both arms    m2 22/39 (56.4%)   s2 7/39 (17.9%)
exact McNemar, two-sided                           p = 0.000275  (16 bugs m2 only, 1 s2 only)
on the 36 bugs with every measurement in both:
  detection         55.6% -> 19.4%    falls by 65.0%
  mutation score    54.0% -> 39.1%    falls by 27.7%
  line coverage     83.7% -> 70.3%    falls by 16.1%
  fall(detection) - fall(mutation score)    +37.3 points, 95% interval [+12.0, +59.0]
```

Both hypotheses of the protocol hold: the arms differ in detection, and
detection falls further than mutation score does. `campaign2/analysis.txt` is
the analysis as the script printed it; the sections below record how the runs,
the audit and the measurement went.

`bin/generate-suites.sh` is the rerun that "What those controls do not close"
asks for, for both arms. Its header is the specification. The campaign's
protocol is `campaign2/PROTOCOL.md`: the design, the two hypotheses and their
tests, the exclusions and what follows from each outcome, fixed before any run
on the sample. `bin/run-campaign2.sh` makes the runs in the order it fixes and
`bin/analyze-campaign2.py` is the analysis it fixes. What changes:

| | first campaign | second |
|---|---|---|
| M working copy | the Defects4J checkout without `.git` and the trigger test files | also without `defects4j.build.properties`, `.defects4j.config`, every `.bak`, changelogs, release notes and upgrade guides, and Defects4J's marker comments and paths; in a directory with a random name |
| Compiling and running, M | the `defects4j` command | `_tools/test.sh`, with the jars it needs copied in |
| What Bash can reach | whatever the operator can | the working copy; no network; its own process namespace |
| File tools | unrestricted | confined to the working copy |
| Operator's profile | in force: settings, memory, plugins | ignored; memory off |
| S arm, running or unpacking `lib/` | forbidden by the prompt | forbidden by the prompt, and of the JDK's launchers only `javac` can be read; `unzip`, `python` and `perl` are hidden |
| Model | the alias `sonnet`, which resolved to `claude-sonnet-5` | `claude-sonnet-5`, by id |
| Reasoning effort | inherited from the operator's configuration, `xhigh` | the CLI's default: no flag is passed and the operator's configuration is not read |
| Tools | `Read`, `Write`, `Bash` | `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash` |
| Record of a run | the closing message | every message |
| Prompts | share two instructions | differ only in what the arm requires |
| Acceptance | an M suite must pass whole; S tests are disabled one by one | tests are disabled one by one in both |
| Turn cap | 25 to 50 (M), 50 (S) | 50 |

The source under test and the developer tests that stay are not edited, apart
from Defects4J's own marks.

Checks made on 17 November 2026, before any run on the sample:

- **Self-tests**, four single calls to the model (list price $0.18 in all).
  `claude-sonnet-5` is still served and is what answered. From the sandbox,
  listing the Defects4J installation finds nothing, `curl` fails at the proxy,
  `ps -e` shows four processes where the host has 107, and the Read tool
  refuses a path outside the working copy. In the S sandbox `./compile.sh`
  works and `java`, `javap`, `jar` and `unzip` do not. `python3` could still
  open the jar in that test; it has been hidden since.
- **Dry run, no model.** For each of the 40 bugs and each arm the working copy
  was built and the first campaign's packaged suite put where the agent's
  would be. All 36 M stand-ins compiled and passed under `_tools/test.sh`, all
  38 S stand-ins compiled under `compile.sh`, and acceptance in the real
  checkout disabled none of their 1518 and 1533 tests. Four M bugs and two S
  bugs have no packaged suite to stand in; their working copies built.
- **What a search of the 40 M working copies still finds.** Nothing that names
  Defects4J. No trigger test's name, except in two other test classes that
  happen to have a method of the same name (Csv-10, Lang-34). One real residue:
  in Lang-65 the repaired source delimits its own repair, `// Fix for LANG-59
  … START` and `END`. That is the implementation, and it is left as it is. One
  coincidence of numbering, which this list left out until 18 November 2026
  although the scan had reported it: in the Lang-13 working copy a developer
  test of another class, `DateUtilsTest`, cites JIRA issue LANG-13, which is
  not the issue behind Defects4J's Lang-13 (LANG-788). Each run's `.leakscan`
  records what its search found.
- **Pilot, three runs with the model** (`campaign2/pilot/`), on Defects4J bugs
  outside the sample, so that no result on the sample is seen before the
  protocol is fixed: Lang-61 and Csv-11 in the M arm, Cli-5 in the S arm. All
  three ended normally on `claude-sonnet-5`, in 19, 19 and 8 turns, for $1.19
  at list prices. Each agent created its test class and nothing else. The M
  agents compiled and ran their tests with `_tools/test.sh`; each had one
  failing test on its first run and none on its second. Acceptance disabled
  none of the 174 M tests and 3 of the 18 S tests.
  `bin/audit-transcripts.py` flags no network or version-control command and
  no sign that an agent knew its bug. It flags one M run for a path outside
  the working copy: the agent unpacked a JUnit class into `/tmp` to read its
  signatures. Inside the sandbox `/tmp` is private to each command, and the
  file never reached the host. The three suites then went through the
  measurement scripts unchanged (`campaign2/pilot/results/`). Their verdicts,
  Cli-5 detected and the other two not, check the pipeline and nothing else:
  three bugs, chosen to exercise the harness.

### The runs

`bin/run-campaign2.sh` made the 80 runs in one session, from 22:13 UTC on 17
November 2026 to 02:41 on the 18th, from commit `2f56801`: the bugs in the
order of the sample, both arms of a bug before the next, the first arm
alternating, one agent at a time. Every run reports `claude-sonnet-5` and
Claude Code 2.1.316. No run was cut short by a usage limit and none was made
twice.

| | `m2` | `s2` |
|---|---|---|
| runs that left an accepted suite | 40 | 40 |
| tests written | 1453 | 1500 |
| tests disabled at acceptance | 0 | 101 (6.7%), in 28 suites |
| turns a run, mean and most | 18.1, 47 | 14.3, 51 |
| list price | $16.18, $0.40 a suite | $23.07, $0.58 a suite |

The `s2` tests disabled, per project: Lang 43 of 600 (7.2%), Csv 14 of 374
(3.7%), Gson 25 of 316 (7.9%), Cli 19 of 210 (9.0%). The first campaign's S
arm had 59 of 1638 (3.6%), and 4 of 579 in Lang. The campaigns differ in
several ways (table above). One of them is that only the second enforces the
ban on running the tests.

One run did not end by itself: Csv-3 in `s2` reached its turn limit, at 51
turns. Under the protocol a run that completes is final. Its test class
compiled and was packaged as it stood, 29 tests and none disabled.

Every `m2` agent ran its tests with `_tools/test.sh`, 103 executions in all,
and in every run the last one passed. Every `s2` agent compiled with
`compile.sh`, 67 times in all, and in every run the last compilation
succeeded.

The search of the 40 `m2` working copies found what the dry run had found
(above): the two methods that share a trigger test's name, Lang-65's comments
and the LANG-13 coincidence. The transcript of the Lang-13 run never shows
that line.

### The audit

`campaign2/audit.txt` is the output of `bin/audit-transcripts.py -v` on the 80
transcripts. `campaign2/violations.txt` is the list the protocol asks for,
committed before anything was measured. It lists no run, and its notes give
each decision. In short:

- **What was read.** Every command the script flags, in 6 `m2` runs and 32
  `s2` runs, whole and with its whole result. Also what the script does not
  look at: the paths given to the file tools, every direct call to `javac`,
  every `s2` command that names `lib/`, a jar or a class file, and every
  program name in either arm.
- **Network.** No command in either arm reaches for it.
- **Outside the working copy.** Nothing was read there but the operating
  system and the JDK. One `m2` run (Gson-7) unpacked a JUnit class from its
  own `_tools/lib` into `/tmp`, which inside the sandbox is private to the
  command. The file tools refused four writes addressed to `/tmp`, and the
  permission layer refused seven shell commands that would have written a
  scratch program there.
- **`lib/` in `s2`.** The prompt forbids inspecting it, and 22 of the 40
  agents tried to list or unpack a jar: 15 the project's or every jar, 7 only
  JUnit's.
  None succeeded. The sandbox hides `unzip`, `jar`, `java` and `python`, and
  the rest was refused before it ran. Under the first campaign's conditions,
  where only the prompt stood in the way and no transcript was kept, the same
  commands would have worked and left no trace.
- **One case decided on the protocol's wording.** The `s2` run of Csv-10
  compiled a scratch file of its own with `javac`, seven times, to find out
  which methods `CSVFormat` has; its `api/` documents only the class under
  test. That breaks the prompt and is not a violation as the protocol defines
  one: nothing in `lib/` was run, printed, unpacked or disassembled, and the
  compiler was given no option that executes code. `violations.txt` declared,
  before measurement, that the analysis would also be reported without that
  run (`campaign2/analysis-without-s2-Csv-10.txt`).
- **Knowledge of the bug.** The script's rule marks Lang-36 in both arms:
  each agent named a test of `NumberUtils.isNumber` `testIsNumber`, which is
  also the name of a trigger test. Nothing else an agent said or wrote names
  the benchmark, the issue behind a bug or a trigger test. Two `m2` agents
  cite CLI-71. They read it in a comment of the source under test, and it is
  the issue behind neither bug.

Two things the script gets wrong, found by this reading and left as they are
because the script is fixed. Its pattern for programs that inspect compiled
code misses one called by its full path (`s2`, Gson-14; the call failed). And
its count of refused calls, 32 and 46, counts each refusal by the harness
twice and adds the sandbox's denials. The transcripts have 16 calls refused by
the harness in `m2` and 8 in `s2` (`bin/describe-campaign2.py`).

### Measurement

Run once, on 18 November 2026, after the audit was committed:

```
OUT=data/campaign2/results NO_MUTATION="Gson-14 Gson-16" \
    ./bin/analyze-agent-suites.sh data/campaign2/suites
```

Defects4J `v3.0.1-7-g8c16da82`, Java 11.0.33. Per arm, over every suite:

| arm | suites | real fault detected | mutation score | line coverage |
|---|---|---|---|---|
| `m2` | 40 | **22/39 — 56%** | 54% | 83% |
| `s2` | 40 | **7/39 — 18%** | 39% | 69% |

- **Cli-21 has no verdict in either arm.** Both suites are `Broken`. Each
  calls a method the fix adds to `WriteableCommandLine` (`setCurrentOption` in
  `m2`, `getCurrentOption` in `s2`) and does not compile on the buggy
  revision. The first campaign's S suite failed the same way.
- **The `s2` suite of Gson-8 has no mutation score.** Under one of
  `UnsafeAllocator`'s mutants the JVM that runs the analysis dies with
  `SIGSEGV`, and Major writes no `kill.csv`. A second attempt, in a scratch
  directory, ended the same way. The suite has its verdict (`Pass`) and its
  coverage figure, so Gson-8 is in the paired set and not in the complete one.
- Gson-14 and Gson-16 are kept out of the mutation step, as the protocol
  fixes. Their four suites have a verdict and a coverage figure.
- The failure the protocol provides for, a Cli suite that cannot load for
  want of Hamcrest, did not occur. Nothing was measured a second time.
- One edit to the logs: in `results/run_mutation_Gson.log` the JVM's crash
  message names the machine's core-dump handler, and that name is replaced by
  `[redacted]`.

### Analysis

`./bin/analyze-campaign2.py > data/campaign2/analysis.txt`, run once with the
script as it was fixed. The paired set has 39 bugs and the complete set 36.

- **H1, the arms differ in detection: rejected.** 22/39 against 7/39. Six
  bugs are detected by both arms, 16 by `m2` alone and one, Cli-17, by `s2`
  alone. Exact McNemar, two-sided, *p* = 0.000275.
- **H2, detection falls further than mutation score: supported.** On the
  complete set detection falls from 55.6% to 19.4%, by 65.0% of its value;
  pooled mutation score from 54.0% to 39.1%, by 27.7%; line coverage from
  83.7% to 70.3%, by 16.1%. The difference between the falls in detection and
  in mutation score is +37.3 points, with a 95% bootstrap interval of [+12.0,
  +59.0]. Against coverage it is +48.9 points, [+24.0, +69.8].
- **Sensitivity.** No run has a violation, so the first sensitivity analysis
  is the primary one. Intention to treat: 22/40 against 7/40, *p* = 0.000275.
  Without the two Lang-36 runs: 22/38 against 7/38, and the interval of H2 is
  [+11.7, +58.4]. Mutation score as the mean over suites: 64.3% and 45.3%.
- **The check declared at the audit**, without the `s2` run of Csv-10: 21/38
  against 6/38, *p* = 0.000275, and an interval of [+15.2, +62.3].

Per project, on the paired set, `m2` and `s2` detect 5 and 0 of 12 in Lang, 7
and 3 of 10 in Csv, 7 and 2 of 10 in Gson, 3 and 2 of 7 in Cli.

`bin/describe-campaign2.py` was written after the runs and prints what the
analysis script does not. None of it is a test.

- The gap in mutation score is there in 34 of the 36 bugs. The two others are
  Lang-13, where `s2` is three points higher, and Gson-6, where both suites
  kill every mutant. A little more than half of the gap is code the `s2`
  suites never execute, 29.2% of mutants against 15.1%. The rest is what they
  kill of what they execute, 55.2% against 63.7%. Defects4J's own table would
  have put the arms at 69.1% and 68.3%.
- Sixteen of the 22 `m2` detections and six of the seven `s2` detections rest
  on a single failing test.

### Beside the first campaign

Descriptive, as the protocol says: the campaigns differ in more than the
benchmark's metadata, so the difference between the M arms is an upper bound
on what the metadata accounts for. Reasoning effort is among the differences
(table above), and the second campaign's suites cost less than half of what
the first's did at list prices: $0.40 and $0.58 against $1.07 and $0.93.

- **M arms**, on the 36 bugs with a verdict in both. The first campaign's
  detected 26 and `m2` detects 20, all 20 among the 26. The six lost are
  Lang-13, Lang-21, Lang-63, Csv-16, Cli-10 and Cli-17. Of the eleven
  first-campaign detections that show a trace of the metadata, `m2` keeps
  eight; of the fifteen that show none, twelve. Lang-63, whose first-campaign
  detection was the developer's test copied from Defects4J's backup, is not
  detected. Csv-3 and Gson-14, which had no M verdict in the first campaign,
  are detected by `m2`.
- **S arms**, on 37 bugs. Six and seven detections, four in common (Csv-3,
  Csv-4, Gson-15, Cli-32). The first campaign's also had Lang-13 and Csv-6;
  `s2` has Csv-10, Gson-6 and Cli-17.
- **Lang-13** is the fault the memorisation probe found recalled with its
  mechanism. Both arms of the first campaign detected it, in working
  directories whose names carried the bug's identifier. Neither arm of the
  second campaign detects it.
- **EvoSuite**, on the 35 bugs with a verdict from all three. `m2` detects 20,
  EvoSuite 15, `s2` 7. Mutation score 53.7%, 47.1% and 39.1%; line coverage
  83.3%, 85.5% and 69.9%. `m2` and EvoSuite detect ten faults in common, ten
  and five alone, 25 between them.

### Deviations from the protocol

None. Three things were done that the protocol does not provide for. None
changes a script it fixes or a figure of the primary analysis: the check
without the `s2` run of Csv-10, declared before measurement; the one
redaction in a log; and `bin/describe-campaign2.py`, written after the runs.

## Third campaign

The comparison of the two arms on the post-cutoff subjects, under the second
campaign's conditions and a protocol fixed before any run on them
(`campaign3/PROTOCOL.md`). It was run on 18 November 2026: 56 runs, audited,
measured and analysed in that order, each step committed before the next.
**Its hypothesis is not rejected**: over the 23 subjects of the paired set
`m3` detects 8 and `s3` 5, three faults by `m3` alone and none by `s3` alone,
*p* = 0.25. The record is under `campaign3/`: every run's transcript, prompt
and settings (`runs-m3/`, `runs-s3/`), the suites as written (`suites/`),
`audit.txt`, `violations.txt`, `direct-javac.txt`, the logs and verdicts of
the measurement (`results/`) and `analysis.txt`. Mutation score and line
coverage were measured afterwards, as the protocol provides: `mutation/` and
`mutation-analysis.txt`.

The runs of "Post-cutoff corpora" above stay as they are. They had the fix
commit within the agent's reach, enforced nothing, kept no transcript and no
test, and left one arm of one corpus without a verdict. This campaign's arms,
`m3` and `s3`, are separate conditions, pooled neither with those runs nor
with the Defects4J campaigns.

**Subjects** (`campaign3/subjects.txt`): the 28 fix commits validated for
either corpus, each once: 19 from Commons Lang, 8 from Commons CSV, 1 from
Commons CLI; 17 mined for the matched corpus only, 9 for the first only, 2 for
both. Six of them were used in neither arm before, because the harness
compiled every developer test and that fails once the file with the trigger
tests is gone. Here the generated suite is compiled alone, so they are in.

**Scripts.**

| | |
|---|---|
| `bin/generate-postcutoff.sh` | builds both working copies, runs the agent, accepts the suite. Its header is the specification |
| `bin/run-campaign3.sh` | the runs, in the order the protocol fixes |
| `bin/audit-campaign3.py` | reads the transcripts |
| `bin/measure-campaign3.sh` | detection: the suite on the fix commit and on its parent |
| `bin/analyze-campaign3.py` | the analysis the protocol fixes |
| `bin/campaign3-lib.sh` | what the generator and the measurement share: a revision exported with `git archive`, built with Maven offline |
| `bin/AgentTestRunner.java` | runs a suite on the JUnit Platform and reports per test method. The same runner in the agent's script, at acceptance and at measurement |

**What differs from the second campaign** is in the protocol, as a table. In
short: the code is an export of the upstream fix commit, not a Defects4J
checkout; the tests are JUnit 5 and are run by a runner of ours, not by the
project's build; the generated suite is compiled without the developers'
tests on its class path; a test that fails on the fixed revision is left out
by name instead of being edited out of the source, which also covers
parameterised tests; and only detection is measured in the campaign itself.
Mutation score and line coverage were measured afterwards, as the protocol
provides ("Mutation score and line coverage, measured afterwards", below).

Two things about the class path are worth recording, since both would have
leaked or broken silently:

- **A released copy of the project on its own test class path.** Commons
  Text is a test library of Commons Lang and depends on a released
  `commons-lang3`, so Maven puts that jar on the test class path, behind the
  tree's own classes. Beside the source, an older release shows what has
  changed since. It is dropped from every class path
  (`bin/campaign3-lib.sh`).
- **What `s3` gets besides the project and JUnit.** Commons Lang declares
  Mockito and Byte Buddy at compile scope, though no production class uses
  them. `lib/` holds only the libraries the compiled production classes refer
  to, by `jdeps`: Commons IO and Commons Codec for Commons CSV, nothing for
  the other two.

### Checks made without the model

`DRY=1` runs the generator and the measurement with no model call. The
scripts given to the agent are tried on a two-test class the generator writes,
and the developers' own test classes for the fix, renamed, stand in for the
agent's suite. They are not self-contained, so in a dry run only, the
project's test sources are on the compiler's source path.

On all 28 subjects and both arms: both revisions build offline, the agent's
scripts work in every working copy, every stand-in suite is accepted and,
measured, is `Fail`. In 55 of the 56 measurements the tests that fail on the
parent commit are exactly the trigger tests the mining recorded with Maven,
which is the check that the runner judges a suite as the project's own build
does. The other is one measurement of `commons-csv-f9e7d792`, two of whose
four trigger tests draw random input and passed on the parent that time.

### Pilot (`campaign3/pilot/`)

Four runs with the model, on 18 November 2026, on two fix commits that are
not among the subjects and whose classes no subject has under test:
`commons-lang-6c4269eb8` (`WordUtils`) and `commons-csv-ab3d7236`
(`CSVPrinter`), each in both arms. Not part of any result.

- All four ended normally on `claude-sonnet-5`, CLI 2.1.316, for $1.61 at list
  prices.
- Each agent wrote its test class and nothing else, and used the script it
  was given. The transcripts show no network or version-control command and
  no path outside the working copy. The harness refused one call and the
  sandbox denied one. One specification-only agent called `javac` itself,
  which the protocol now settles in advance.
- The suites went through acceptance (0 of 81 tests left out in `m3`, 7 of 99
  in `s3`) and measurement. Their verdicts, all `Pass`, check the pipeline and
  nothing else.

One redaction: Maven's banner in the pilot's eight build logs named the
generating machine's kernel, and that version is replaced by `[redacted]`.
The scripts no longer keep the banner.

### The runs

`bin/run-campaign3.sh` made the 56 runs in one session on 18 November 2026,
from 13:29 to 16:55 UTC, from commit `41d1ffc`: the subjects in the order of
`subjects.txt`, both arms of a subject before the next, the first arm
alternating, one agent at a time. Every run reports `claude-sonnet-5` and
Claude Code 2.1.316, and every revision was built with Java 11.0.33 and Maven
3.9.16 at `--release 8`. No run was cut short by a usage limit, none was made
twice, and every run ended by the agent's own decision.

| | `m3` | `s3` |
|---|---|---|
| runs that left an accepted suite | 28 | 28 |
| tests written | 1217 | 1558 |
| tests left out at acceptance | 0 | 63 (4.0%), in 20 suites |
| turns a run, mean and most | 18.2, 36 | 16.2, 42 |
| list price | $13.75, $0.49 a suite | $21.34, $0.76 a suite |

The `s3` tests left out, per project: Lang 29 of 993 (2.9%), CSV 27 of 526
(5.1%), CLI 7 of 39. Every `m3` agent ran its tests with `_tools/test.sh` and
in every run the last execution passed. Every `s3` agent compiled with
`compile.sh` and in every run the last compilation succeeded.

The search of the working copies found nothing in 55 of the 56. In the `m3`
copy of `commons-lang-963c337d7` it found what the dry run had: `testEquals`
and `testHashCode`, the names of that subject's trigger tests, 49 times in the
other test classes of Commons Lang.

### The audit

`campaign3/audit.txt` is the output of `bin/audit-campaign3.py -v` on the 56
transcripts. `campaign3/violations.txt` and `campaign3/direct-javac.txt` are
the lists the protocol asks for, committed before anything was measured, with
the reasons for each decision. In short:

- **What was read.** Every command the script flags, in 9 `m3` runs and 21
  `s3` runs, whole and with its whole result. Also what the script does not
  look at: the paths given to the file tools, every absolute path in any
  command (its pattern leaves out `/usr`), every program name in either arm,
  every `s3` command that names `lib/`, a jar, a class file or `javac`, and
  the code the agents wrote, for anything that opens a file or a connection
  outside the working copy.
- **Network.** No command in either arm reaches for it.
- **The sandbox did less than the protocol says**, in four ways.
  1. The CLI gives sandboxed commands a temporary directory, `$TMPDIR`,
     `/tmp/claude-1000` on this machine. `/tmp` itself is, to each command, an
     empty directory of its own, as the generator's header says. That
     directory inside it is not: it is the host's, readable and writable from
     inside and shared by every command of every run. Files that four runs
     wrote there were on the host when the campaign ended. During the campaign
     it also held the working files of the session that prepared the
     campaign, among them the generator's dry run: the developers' test
     classes for each fix, renamed, in archives, and each subject's trigger
     tests by name. Whether an agent could list those subdirectories was not
     tried; nothing in the settings hides them, so it is assumed they were
     within reach of every agent in both arms. (Tried after the analysis,
     without a model: they were. See "The sandbox after the third campaign".)
     **No agent reached for them.**
     No command in the 56 transcripts lists that directory or names a path in
     it other than the files the same run had just put there. Five commands
     searched the whole file system by name. One of them, by the `m3` agent of
     `commons-lang-824837751`, was for `ConstructorUtilsTest.java`, the
     developers' test class that had been removed from its tree; it printed
     nothing.
  2. The operating system's packages include released jars of Commons Lang
     (3.14.0) and Commons CLI (1.6.0) under `/usr/share/java`, older than
     every fix, and the sandbox does not hide `/usr`. One `m3` agent
     (`commons-lang-de0184561`) saw their names in a search and did nothing
     with them. No agent opened one.
  3. The Read tool, confined to the working copy by `--restricted`, also
     reads the files in which the CLI saves a command's output when it is
     longer than the CLI passes on. They are under the user's home.
  4. `mvn` is on the agents' `PATH`, where the generator's header says Maven
     is not available. One `m3` agent ran `mvn -q -o compile`, which stopped
     at the parent POM: offline, no local repository, no network.
- **Five runs are listed as violations, by the wording of the rule and by
  nothing else.** The rule leaves out a run when a command read a file outside
  the working copy that is not part of the operating system or the JDK, and
  excepts a command's own private `/tmp`. Four runs read back a file they had
  themselves written in the shared temporary directory: a class unpacked from
  the run's own `_tools/lib` (`m3`, `commons-csv-1d89cd5f`), scratch classes
  compiled from sources in the working copy (`m3`, `commons-lang-df1e91895`),
  and the text of pages of the run's own `api/` (`s3`, `commons-csv-f9e7d792`
  and `commons-lang-623235ebc`). The fifth read the CLI's saved copy of the
  output of its own `cat` of an `api/` page (`s3`, `commons-lang-824837751`).
  None obtained anything that did not come from its own working copy. The
  rule has no exception for that and none was made after the fact; the
  protocol's first sensitivity analysis has the five runs included.
- **`lib/` in `s3`.** Five of the 28 agents tried to list a jar, two the
  project's and three JUnit's alone, with `unzip` or `jar`. None succeeded.
  Seventeen called `python`, sixteen of them on a page of their `api/` to
  strip its tags; it is hidden and never ran.
- **Direct calls to `javac` in `s3`.** One run, `commons-csv-4a28ba82`,
  compiled two scratch classes of its own with the options of `compile.sh`, to
  see whether the methods it meant to call exist. Under the protocol that is
  not a violation; the run is listed in `direct-javac.txt` and left out in the
  fifth sensitivity analysis.
- **Knowledge of the fix.** The script's rule marks three runs, each for a
  test the agent named after the method it tests, which is also the name of a
  trigger test: `testEquals` and `testHashCode` (`m3`,
  `commons-lang-963c337d7`), `testIsCreatable` (`m3`,
  `commons-lang-9a92df9fa`) and `testWithHeaderComments` (`s3`,
  `commons-csv-10220941`). Nothing an agent said or wrote names an issue, a
  pull request or a fix commit.
- **Refused calls.** The harness refused 9 calls in `m3` and 8 in `s3`, and
  the sandbox denied 16 `s3` commands a hidden program. The script's counts
  agree with the transcripts.

**What this means for the second campaign's record.** Its runs used the same
sandbox settings, on the same machine, so the first, second and fourth points
hold for it too, whatever its protocol and the header of
`bin/generate-suites.sh` say about `/tmp`. Its 80 transcripts were searched
again on 18 November 2026 for the temporary directory, for `/usr/share`, for
the CLI's saved outputs and for searches of the whole file system. Three `m2`
agents named the temporary directory (Gson-3, Lang-21, Lang-43); every command
or file-tool call that would have written there was refused, and none read a
file there. No command names `/usr/share`. Two commands searched the file
system by name, both already in that campaign's `violations.txt`, and printed
nothing. Its audit's conclusion stands: nothing outside a working copy was
read but the operating system and the JDK.

### Measurement

`./bin/measure-campaign3.sh`, run once, on 18 November 2026, after the audit
was committed. Each suite is compiled on its own against the fix commit and
against its parent and run on both, the tests left out at acceptance left out
again.

| arm | suites | `Fail` | `Pass` | `Broken` |
|---|---|---|---|---|
| `m3` | 28 | 9 | 18 | 1 |
| `s3` | 28 | 6 | 21 | 1 |

- **`commons-csv-f9e7d792` has no verdict in either arm.** Both suites read
  `Token.isEscaped`, a field the fix adds, and do not compile against the
  parent commit.
- Every suite passes on the fix commit when run again, and no verdict is a
  timeout. Nothing was measured a second time.

### Analysis

`./bin/analyze-campaign3.py > data/campaign3/analysis.txt`, run once with the
script as it was fixed. The paired set has 23 subjects: the 28, less the five
with a run listed as a violation, one of which is also the subject without a
verdict.

- **H1, the arms differ in detection: not rejected.** 8/23 (34.8%) against
  5/23 (21.7%). Five faults are detected by both arms, three by `m3` alone,
  none by `s3` alone. Exact McNemar, two-sided, *p* = 0.25. The difference is
  +13.0 points, with a 95% bootstrap interval of [+0.0, +26.1]. By the rule
  fixed in the protocol, this corpus does not show the difference; that is
  read neither as the absence of an effect nor as evidence that recall
  produced the effect on Defects4J.
- **Sensitivity.** With the five runs included: 9/27 against 6/27, six faults
  by both, the same three by `m3` alone, *p* = 0.25, +11.1 points [+0.0,
  +22.2]. Intention to treat: 9/28 against 6/28, +10.7 points [+0.0, +21.4].
  Without the three runs that name a trigger test: 7/20 against 5/20, *p* =
  0.5. Without the `s3` run that called `javac`: 8/22 against 5/22, *p* =
  0.25.
- **The three faults `m3` alone detects**: `commons-lang-1d6ef29ce`
  (`CharRange.contains` for negated ranges), `commons-lang-d4b4d8c35`
  (`FastDateParser` on a number that overflows an `int`) and
  `commons-lang-963c337d7` (`equals` and `hashCode` of `ImmutableTimeZone`).

Descriptive, and no test of the protocol. The analysis script prints the
comparisons below. `bin/describe-campaign3.py`, written after the runs,
prints what it does not: the faults each arm detects, the tests left out per
project, and the counts in "The runs" and "The audit" above.

- **By project**, on the paired set: Commons Lang 8 and 5 of 16; Commons CSV 0
  and 0 of 6; Commons CLI 0 and 0 of 1. Every detection in either arm is in
  Commons Lang.
- **By corpus**: the subjects mined for the matched corpus, 4 and 2 of 15;
  those mined for the first, 4 and 3 of 10.
- **By fault type**, for the subjects of the matched corpus: omissions 3 and 1
  of 8, state faults 1 and 1 of 2, substitutions 0 of 3, algorithm faults 0 of
  2.
- **The second campaign beside this one.** Its difference is +38.5 points
  (22/39 against 7/39) and this one's +13.0. The difference between the two
  differences is −25.4 points, with a bootstrap interval of [−46.9, −2.3],
  each campaign's subjects resampled on their own. The campaigns differ in
  more than the date of the faults: the projects, the fault types, the test
  framework, how the working copy is built and how a suite is run. It is not
  a measurement of what recall contributes.
- **The earlier runs on these subjects beside this campaign.** On the 19
  subjects with a valid verdict from both, the earlier implementation-visible
  runs detected 13 and `m3` detects 7, all 7 among the 13. The six lost are
  `commons-lang-0edbb4ae0`, `commons-lang-677e57f56`,
  `commons-lang-623235ebc`, `commons-lang-284be5d6a`, `commons-cli-dc69e842`
  and `commons-csv-10220941`. On the 11 subjects with a valid verdict from
  both specification-only arms, the earlier runs detected 2 and `s3` detects
  1, `commons-lang-963c337d7` being the one lost. The earlier
  implementation-visible agent worked in a git worktree with the fix commit
  within reach and nothing enforced, and the runs differ in other ways too,
  prompts and tools among them, so six is an upper bound on what the reach of
  the fix commit added, not a measurement of it.

### Mutation score and line coverage, measured afterwards

The protocol left both unmeasured and said how they would be measured later:
with PIT and its default mutators, on the classes the fix modifies, with the
suite as accepted, and the second campaign's H2 computed as that campaign's
protocol defines it and reported as a secondary result, whatever it is ("Not
measured: mutation score and coverage"). That was done on 19 November 2026,
after the analysis above. The protocol and its seven scripts are unchanged,
and no figure above changes.

**Scripts**, written that day and committed before they were run on any
subject (`aff1ff0`):

| | |
|---|---|
| `bin/mutation-campaign3.sh` | stages the fix commit as the measurement does, compiles each archived suite on its own, and runs PIT. Its header is the specification |
| `bin/ExcludedTestsFilter.java` | leaves out, on the JUnit Platform PIT drives, the test methods that failed at acceptance, by the keys and the rule of `bin/AgentTestRunner.java`, and records the methods kept |
| `bin/analyze-mutation-campaign3.py` | the H2 statistic and interval, with the second campaign's own functions (`bin/analyze-campaign2.py`). On that campaign's data it gives that campaign's figures |

**How.** PIT 1.30.2 with its JUnit 5 plugin 1.2.3, on the JDK of the
measurement and in its environment. The classes mutated are those of the
subject's `classes.txt` with the classes nested in them, which are in the
same source file. PIT's options are its defaults but for eight threads, a
heap of 1 GB for each process that runs tests, an XML report only, and its
own class path kept off the tests': PIT's command line adds it unless told
not to, and PIT's dependencies include a released Commons Lang (3.18.0). The
mutation score is PIT's: the mutants it counts as detected (killed, timed out,
out of memory, run error, not viable) over every mutant made in those
classes, the ones no test reaches included. Line coverage is PIT's too, over
the same classes. A suite gets no figure if it does not compile, if PIT stops
because a test fails on the unmutated code (PIT is not allowed to skip such a
test, since the suite would then not be the suite as accepted), or if PIT
does not finish within two hours.

- **PIT's jars** are fetched once from Maven Central by Maven, and each is
  checked against the SHA-256 written in the script before every run.
- **Java's `assert` statements.** PIT turns them on in the processes that run
  tests, and the measurement's runs leave them off. No test of the 56 suites
  uses one. One mutated method holds one, `Conversion.shortToBinary` in
  `commons-lang-0edbb4ae0`, right after a check that makes it hold on the
  unmutated code.
- **Major and PIT.** The Defects4J campaigns' mutation scores are Major's,
  with its operators, on Defects4J's build; these are PIT's, with its default
  mutators. The absolute figures are not comparable between the campaigns;
  the falls between the arms are what H2 compares.
- **Tried first.** Before the scripts were written, PIT was run by hand on one
  suite of the campaign, the `s3` suite of `commons-lang-677e57f56`, to see
  how it runs with the JUnit 5 plugin, and its figures were seen. Then the
  script was run on the pilot's two subjects (`pilot/mutation/`): in all four
  suites, the test methods PIT ran and those it left out are the ones the
  pilot's measurement ran and left out.

**Measurement** (`campaign3/mutation/`). `./bin/mutation-campaign3.sh`, run
once, on 19 November 2026, with the scripts as committed (`aff1ff0`); its
output was committed before the analysis was run (`7722330`). Every one of the
56 suites has a figure: each compiles against the fix commit, PIT found each
green on the unmutated code, and none ran out of time. In all 56, the test
methods PIT ran are the ones the detection measurement ran on the fix commit,
and the ones it left out are those left out at acceptance. The arms are
mutated in the same classes, 7,834 mutants each. Of the 15,668, PIT counts
6,990 as detected: 6,895 killed, 62 timed out, 33 out of memory. None is a run
error, not viable or equivalent. Per suite, `mutation/` holds PIT's log, its
XML record of every mutant, the test methods the filter kept and left out,
the compiler's output and the row of `mutation.csv`.

**Analysis** (`campaign3/mutation-analysis.txt`).
`./bin/analyze-mutation-campaign3.py`, run once, as committed, after the
measurement had been committed (`2fd53ab`). Every subject of the paired set
has every measure in both arms, so the complete set is the paired set: 23
subjects.

| | `m3` | `s3` | fall |
|---|---|---|---|
| detection | 8/23 — 34.8% | 5/23 — 21.7% | 37.5% |
| mutation score, pooled | 56.7% | 51.9% | 8.6% |
| line coverage, pooled | 77.8% | 71.9% | 7.5% |

- **The second campaign's H2 statistic**, fall(detection) − fall(mutation
  score), is +28.9 points, with a 95% bootstrap interval of [−7.2, +66.6].
  The interval includes zero: on this corpus the fall in detection is not
  shown to exceed the fall in mutation score. The protocol fixes no decision
  for it and says the corpus was not sized for it. In the second campaign's
  sequence it would not have been assessed at all, since H1 is not rejected.
  Against line coverage: +30.0 points [−6.7, +67.0].
- **Sensitivity**, as in the second campaign. With the five runs with a
  violation included, 27 subjects: +24.5 points [−7.5, +59.4]. Without the
  three runs that name a trigger test, 20 subjects: +17.7 points [−13.9,
  +56.4]. As means over suites, the mutation scores are 67.7% and 57.9%.
- **The second campaign beside it**, as its analysis computes it: detection
  falls 65.0%, mutation score 27.7%, coverage 16.1%, and the statistic is
  +37.3 points [+12.0, +59.0]. Descriptive: the campaigns differ in the
  mutation tool as well as in everything "Analysis" above lists.

Descriptive, printed by `bin/describe-campaign3.py` subject by subject, and
by the analysis script:

- `m3` has the higher mutation score in 18 of the 23 subjects and `s3` in 3,
  all three on `CSVFormat` in Commons CSV (`commons-csv-10220941`,
  `commons-csv-4a28ba82`, `commons-csv-a6ee67ec`); the two are equal in 2.
  Line coverage: `m3` higher in 18, `s3` in 2, equal in 3.
- Of the mutants their tests reach, `m3` detects 73.3% and `s3` 71.7%. What
  separates the arms on this measure is mostly what their tests reach.
- By project: Commons Lang, 16 subjects, 58.8% and 51.5%; Commons CSV, 6
  subjects, 51.7% and 53.4%; Commons CLI, 1 subject, 73.4% and 35.1%.
- Over every suite, the five runs with a violation included: 46.9% and 42.4%
  pooled, 66.3% and 55.3% as means, line coverage 66.5% and 61.6%. The pooled
  figures are lower than on the complete set because one subject outside it,
  `commons-lang-623235ebc`, puts the 1,880 mutants of `ArrayUtils` in each
  arm, at 14.3% and 17.0%.

### Deviations from the protocol

None in the procedure. Two entries are recorded in the protocol, both dated 18
November 2026. The first, before the measurement: what the audit found the
sandbox not to enforce, and that the violation rule was applied to it as
written. The second, after the analysis: that what the first assumes about the
shared temporary directory was tried and holds ("The sandbox after the third
campaign", below). One thing was done that the protocol does not provide for
and that changes no script it fixes and no figure of its analysis:
`bin/describe-campaign3.py`, written after the runs. The measurement of
mutation score and coverage afterwards is one the protocol provides for, in
the way it states (above).

## The sandbox after the third campaign

The third campaign's audit found the sandbox of both campaigns doing less than
their protocols say ("The audit", above). Part of that was read off the
settings and not tried. On 18 November 2026, after the campaign was analysed,
it was tried, and settings that close it were written for any later run. The
generators of the two campaigns are not changed: they are the record of how
those runs were made, and no run has been made with the new settings.

**`bin/agent-sandbox.py`** holds the settings and a probe of them. The probe
runs the CLI as the generators do, with their flags and environment, in a
working copy under `/tmp`, but pointed at a server on the same machine that
stands in for the API and answers each request with the next of a fixed list of
tool calls. No model is called. What the CLI does with a tool call is the real
thing: the sandbox it builds around a command, and what `--restricted` lets a
file tool read. Before the run the probe leaves a file with a random word in
the shared temporary directory, in `/tmp` and in `/var/tmp`, and searches the
part of the file system the campaigns' settings left readable for archives that
hold a class of any project under study, the Defects4J projects included. The
commands then try to read all of it.

**Under the settings of the two campaigns** (`sandbox/probe-as-run.txt`), in
both arms, with CLI 2.1.316:

- A command's `$TMPDIR` is `/tmp/claude-1000`. The command lists it, the
  directories of every other session on the machine included, reads the file
  left in a subdirectory of it, and writes beside that file. What the audit
  assumed therefore holds: the dry run left there during the third campaign,
  with the developers' tests for each fix, was within reach of every agent.
  That no agent reached for it rests on the transcripts, as before.
- `/usr/share/java` is listed and both jars are read:
  `commons-lang3-3.14.0.jar` and `commons-cli-1.6.0.jar`. They are the only
  archives on the machine, outside what the settings hide, that hold a class of
  a project under study.
- The `mvn` on the `PATH` is the operating system's Maven 3.8.7, under
  `/usr/share/maven`. It starts in the implementation-visible arm. In the other
  it does not, `java` being hidden.
- What the settings were written to hide is hidden: files in the machine's
  `/tmp` and `/var/tmp`, the home directory and `/opt`. The file tools refuse
  every path outside the working copy, the run's own temporary files among
  them, with the one exception the audit found: the Read tool reads the copy
  the CLI saves, under the home, of a command's output when it is longer than
  the CLI passes on.

**Under the new settings** (`sandbox/probe.txt`) every check passes in both
arms. Two things differ from the campaigns' settings:

- Each run has a temporary directory of its own. The generator is to make an
  empty one and name it to the CLI in `CLAUDE_CODE_TMPDIR`; sandboxed commands
  then get a directory inside it as `$TMPDIR`, which starts with nothing of any
  other session in it, and `/tmp/claude-1000` does not exist for them. The name
  has to be short. With a directory under the home's cache, which is where the
  staged revision is, the CLI gave commands the shared directory again; that
  was tried too, and the probe fails when it happens.
- `/usr/share/java`, `/usr/share/maven-repo`, `/usr/share/maven` and
  `/usr/share/doc` are hidden: the packaged jars, the packaged Maven with its
  repository, and the packages' release notes. `mvn` is then not found in
  either arm. `javac` compiles, and `java` runs where the arm allows it.

**Not closed.** The Read tool still reads the CLI's saved copy of a long
output. It holds what the run's own command printed and nothing else. The
violation rules of both protocols count reading it, as they are written.

**To be done again** before any campaign, on the machine and with the CLI
binary that campaign will use: the temporary directory and the confinement of
the file tools are the CLI's behaviour and may change with its version, and the
jars are the machine's. Neither file under `sandbox/` is the verbose output,
which lists the other sessions' directories and the machine's mount table.

## Infrastructure failures and exclusions

Each project contributed its own, all recorded here because they are easy to
mistake for results:

- **JUnit 3 vs 4.** Verification originally hard-coded
  `org.junit.runner.JUnitCore`, which does not exist in Cli's JUnit 3.8.1. Six
  Cli suites were recorded as failing when they had never been run. Verification
  now falls back to `junit.textui.TestRunner`.
- **cli2 declares jars it never materialises.** `cp.test` lists
  `target/lib/junit/jars/junit-3.8.1.jar`, which is absent; the jars Defects4J
  keeps under the per-project `lib` directory under `framework/projects` are appended to the classpath.
- **Suites that do not compile in isolation.** Cli-21 and Csv-3 extended test
  helpers from the project's test tree (`CLITestCase`, `TokenMatchers`), which
  compile in the working copy but not inside the packaged archive. Both were
  moved to `data/agent-suites-broken/`. The M prompt did not, and does not,
  require self-contained classes.
- **Gson-14 and Gson-16 break `run_mutation.pl`** for the same `$Gson$Types`
  reason as in Study A, and the script aborts the whole project at the first
  failure — which silently cost six other Gson bugs their mutation figures
  until the two were moved aside. Their S-arm suites had been measured for
  detection and coverage before that (both `Pass`, commit `2dfdc0d`); those
  rows are not in the final tables.
- **Post-cutoff mining.** Every rejection recorded for the two post-cutoff
  corpora gives the wrong reason: two builds stopped by a JDK too old for Gson
  and one test JVM out of memory, all three read as passing tests, and a test
  file one candidate left staged, which broke the next two checkouts.
  Described under Post-cutoff corpora. One of the five,
  `commons-lang-ae85262f0`, meets the contract and is in neither corpus nor
  the third campaign.
- **Figures that were wrong and went unnoticed**, because nothing in the
  pipeline failed: `mut_killed` counting uncovered mutants, `Broken` suites
  counted as missed detections, the doubled test totals, and the RAT audit
  recorded as detection. All four are described above. None was caught by a
  script; all four were caught by reading raw output.

---

## Status

- [x] Sample fixed
- [x] Classification, 40/40
- [x] No `UNCLEAR` entries to review (the category was never used)
- [x] First 10 classifications re-read under the final rules — all sustained
- [x] Mutation measurement, 38/40 (Gson-14, Gson-16 excluded — tool limitation)
- [x] `nearby_mutant` retired (column renamed, no figure derived from it)
- [x] Study B, M arm: 40/40 suites (Sonnet), 6 extra (Opus)
- [x] Study B, S arm: 40/40 suites
- [x] Study B analysed: 72% vs 14% detection; mutation score 58% vs 44%
- [x] EvoSuite baseline: 36 suites analysed, 35 with a detection verdict
- [x] Memorisation probe, with hand readings of every non-disclaiming answer
- [x] Post-cutoff corpora: first (S arm void), matched (13 pairs)
- [x] Write-up, revised after the November 2026 audit
- [x] The five Cli EvoSuite suites re-measured with Defects4J's JUnit path corrected
- [x] Generator for the rerun (`bin/generate-suites.sh`): written, dry-run on the 40 bugs, piloted on three bugs outside the sample
- [x] Protocol of the second campaign fixed (`campaign2/PROTOCOL.md`), with its analysis script
- [x] Second campaign: both arms regenerated, without Defects4J's metadata in the working copy, under that protocol: 80 runs, audited, measured and analysed (56% vs 18% detection; both hypotheses hold)
- [x] Third campaign prepared: protocol, scripts, checks without the model and a pilot (`campaign3/`)
- [x] Third campaign run: the 28 post-cutoff subjects in both arms, under the second campaign's conditions: 56 runs, audited, measured and analysed (35% vs 22% detection over 23 pairs; its hypothesis is not rejected)
- [x] Sandbox settings for any further run, with a temporary directory of its own for each run and the operating system's jars of the projects hidden, and a probe of them that calls no model (`bin/agent-sandbox.py`, `sandbox/`). No run has been made with them
- [x] Third campaign, afterwards: mutation score and line coverage of its 56 suites with PIT, as its protocol provides, and the second campaign's H2 on them as a secondary result (+28.9 points, interval −7.2 to +66.6; `campaign3/mutation/`, `campaign3/mutation-analysis.txt`)
- [ ] A matched post-cutoff corpus large enough to test the effect size

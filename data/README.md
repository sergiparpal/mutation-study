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

Final distribution: OMISSION 21, ALGORITHM 7, SUBSTITUTION 5, STATE 4,
MISSING_CLAUSE 3, API 1.

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

`fault_type` is unaffected and remains in use — it is the variable that
explains which faults the spec-only arm of Study B detects.

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

Complete. Two arms over the same 40 bugs, differing in one variable: whether
the agent can read the implementation.

- **M arm (implementation-visible)** — `bin/run-agent-suites.sh`. The agent
  works inside the checked-out project and reads the fixed source. This is
  what happens when anyone asks a coding agent for tests on existing code.
- **S arm (spec-only)** — `bin/run-spec-suites.sh`. The agent works in a
  sandbox holding generated javadoc, the compiled jar and JUnit. It never sees
  implementation source and may not execute its tests.

Suites are analysed by `bin/analyze-agent-suites.sh`, which wraps Defects4J's
own `run_bug_detection.pl`, `run_coverage.pl` and `run_mutation.pl`.

## Results

Per arm, over every suite that produced all three measurements:

| arm | n | real fault detected | mutation score | line coverage |
|---|---|---|---|---|
| `agent` (Sonnet, M) | 36 | **26/36 — 72%** | 72% | 85% |
| `agentopus` (Opus, M) | 6 | 6/6 — 100% | 80% | 89% |
| `spec` (Sonnet, S) | 38 | 6/38 — 16% | 70% | 73% |

Paired over the 36 bugs present in both Sonnet arms:

```
detection   M 26/36 (72%)   vs   S 5/36 (14%)
mutation    M 72%           vs   S 70%
coverage    M 85%           vs   S 73%

Cli    n=7    M=5   S=1
Csv    n=9    M=7   S=2
Gson   n=8    M=6   S=1
Lang   n=12   M=8   S=1
```

**Two things follow.**

Roughly five sixths of an agent's real-fault detection comes from having read
the implementation, not from knowing how to test. The effect holds in all four
projects.

And **no standard metric separates the two cases**: mutation score is 72% vs
71%, statistically indistinguishable, while detection differs five-fold. Line
coverage drops from 85% to 72% — far less than detection does. A suite that
catches three faults in four and a suite that catches one in seven look
identical under mutation analysis.

### Which faults the spec arm does catch

Cli-32, Csv-4, Csv-6, Gson-15, Lang-13 — five of thirty-six, and four of them
are cases where the code contradicts a contract the javadoc states: a missing
null guard on a documented return, an unchecked index, `NaN` rejected
regardless of the documented lenient mode, primitive classes failing a
documented deserialization contract. The spec arm catches faults that are
visible from the specification, and essentially nothing else.

## M arm — configuration

| | |
|---|---|
| Claude Code | 2.1.251 (native install, linux-x64) |
| Models | `--model opus` (6 bugs), `--model sonnet` (40 bugs) |
| Turn cap | 25 for the Opus runs, 40 then 50 for Sonnet |
| Tools | `Read,Write,Bash` |
| Permissions | `--permission-mode acceptEdits` |
| Output | `--output-format json`, one file per run |
| Cost | $42.61 for 46 suites (list price against subscription quota) |

The model is passed on the command line rather than left to
`~/.claude/settings.json`, which held `"model": "opus"` and
`"effortLevel": "xhigh"`. Local configuration must not silently define the
experiment.

**`--bare` cannot be used.** It is the documented way to skip auto-discovery of
CLAUDE.md, hooks, skills, plugins and MCP servers, which is exactly what
reproducibility wants — but with `--bare` every run fails with
`Not logged in · Please run /login` despite valid credentials in
`~/.claude/.credentials.json`. Runs are therefore made **without** `--bare`
from a clean checkout under `/tmp`, which contains no project-level
configuration.

### Model arms are not comparable as a designed contrast

The six Opus suites are the first six bugs of the sample, not a random subset:
the run switched to Sonnet after exhausting quota. They are reported separately
as an opportunistic indication, never as a model comparison. The turn cap also
differs between them (25 vs 40/50).

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

## S arm — configuration

Same model and flags as the M Sonnet arm, `MAX_TURNS=50`. Cost: $37.02 for 40
suites. The sandbox given to the agent:

```
api/          javadoc for the classes under test — the spec
lib/          the compiled project jar and JUnit — so tests can be COMPILED
tests/        where the agent writes
compile.sh    compiles tests/ against lib/ at the project's own -source level
```

The prompt forbids running the tests, decompiling or disassembling `lib/`,
inspecting version control and searching the web. Sandboxes are kept under
`/tmp/specW_*` as an audit trail.

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

### Source level

The sandbox compiles with the project's own `-source` level, read from
`default.properties`. Lang-65 was initially lost because the agent wrote
`1_017_320_701_000L`, valid under the sandbox's default javac but not under the
project's `-source 1.6`. The level is passed to `compile.sh` and stated in the
prompt.

### Per-method filter, and its bias

An agent writing from the API alone gets some expectations wrong. Discarding a
whole suite over one wrong expectation would throw away most of the sample, so
failing methods are disabled individually by `bin/prune-failing-tests.py` — the
`@Test` annotation is commented out (JUnit 4) or the method renamed
(JUnit 3) — and the rest are kept.

**Measured prune rate: 59 of 1806 tests (3%)**, with a clear gradient:

```
Lang   ~0%    Commons javadoc is unusually explicit
Csv    ~2%
Gson   ~6%    reflection and generics, sparser documentation
```

This retires the hypothesis that the spec arm would mostly guess: writing from
javadoc produces almost no wrong expectations.

**Declared bias.** That filter uses the implementation as an oracle, so what
survives is precisely the subset agreeing with the code. It only removes, never
rewrites, and the survivors were written blind — but the selection is biased
and is reported as such. The M arm carries the same bias, so the comparison
between arms stays clean.

*(Stale class files: disabling a method changes the `.java` by a few bytes
within the same second, and ant's one-second timestamp granularity then skips
the recompile, so the next run executes the pre-prune bytecode and the loop
never converges (Lang-21). `touch` does not help. The compiled test classes are
deleted before recompiling, inner classes included.)*

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
  public for years. Planned mitigation is a later comparison against
  GitBug-Java, whose bugs postdate the cutoff.

## Baselines

`gen_tests` ships with EvoSuite and Randoop. On Lang-13, EvoSuite's suite is
classified `Pass` — it does not detect the fault — against `Fail` for both
agent arms. The developer suite is the upper bound: 70% mutation score on
Lang-13 against 77% for the M-arm agent suite.

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
  compile in the working copy but not inside the packaged archive. The M-arm
  prompt now requires self-contained test classes. Both were moved to
  `data/agent-suites-broken/`.
- **Gson-14 and Gson-16 break `run_mutation.pl`** for the same `$Gson$Types`
  reason as in Study A, and the script aborts the whole project at the first
  failure — which silently cost six other Gson bugs their mutation figures
  until the two were moved aside.

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
- [x] Study B analysed: 72% vs 14% detection at equal mutation score
- [ ] Write-up
- [ ] Replication on post-cutoff bugs (GitBug-Java)

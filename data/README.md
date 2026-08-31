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

### `nearby_mutant` — SUPERSEDED

> **⚠ This variable was judged by reading diffs, not measured, and the first
> measurement refuted it (2026-08-29).** Major generates mutants in Lang-13's
> faulty region — two LVR on the `false` argument of `Class.forName` — which the
> definition missed because it counted only arithmetic, relational and logical
> operators and numeric literals, overlooking boolean, null and string literals.
> Those are pervasive in object-oriented code.
>
> The column is kept for provenance. **Do not use the 17/40 sterile figure.**
> It is replaced by the measured columns in `mutation-metrics.csv`.

Original definition: `YES` when at least one arithmetic, relational or logical
operator, or one literal constant, appears in the lines the fix modifies or in
lines immediately adjacent.

## Classification protocol

1. Only the diff over `dir.src.classes` between buggy and fixed versions is
   examined.
2. **Trigger tests are not consulted** during classification: they reveal where
   the fault lies and bias the judgement on `nearby_mutant`.
3. `UNCLEAR` entries are reviewed as a batch at the end.
4. Once finished, the first 10 entries are re-read under the final criteria,
   since criteria drift over the course of classification.

## Mutation measurement (`mutation-metrics.csv`)

Produced by `bin/run-mutation.sh` (collection, ~34 min for the sample) and
`bin/analyze-mutation.py` (analysis). Raw artifacts under `data/raw/`, one
directory per bug, so the analysis can be rerun without repeating any
defects4j work.

### Protocol

For each bug, on the **fixed** version:

- `defects4j mutation -r` — the relevant developer test suite.
- `defects4j mutation -t <trigger>` — once per trigger test, in isolation.
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

# Study B — do agent-written suites catch real bugs?

Not started. Setup notes recorded here as they are established.

## Agent configuration

| | |
|---|---|
| Claude Code | 2.1.251 (native install, linux-x64) |
| Model | `--model opus`, passed explicitly |
| Turn cap | `--max-turns 15` |
| Tools | `Read,Write,Bash` |
| Permissions | `--permission-mode acceptEdits` |
| Output | `--output-format json`, one file per run |

The model is passed on the command line rather than left to
`~/.claude/settings.json`, which currently holds `"model": "opus"` and
`"effortLevel": "xhigh"`. Local configuration must not silently define the
experiment.

**`--bare` cannot be used.** It is the documented way to skip auto-discovery of
CLAUDE.md, hooks, skills, plugins and MCP servers, which is exactly what
reproducibility wants — but with `--bare` every run fails with
`Not logged in · Please run /login` despite valid credentials in
`~/.claude/.credentials.json`. Runs are therefore made **without** `--bare`
from a clean checkout under `/tmp`, which contains no project-level
configuration. User-level settings still apply; their contents at the time of
the runs were:

```json
{"model": "opus", "effortLevel": "xhigh", "tui": "fullscreen",
 "skipDangerousModePermissionPrompt": true, "skipWorkflowUsageWarning": true,
 "agentPushNotifEnabled": true}
```

## Measurement loop, per bug

```
checkout _f
defects4j export -p classes.modified     which classes to test
delete the trigger tests' file           or the agent copies the answer
[agent writes tests]
verify they compile and pass on _f       discard the rest
defects4j coverage -t <agent test class>
defects4j mutation -t <agent test class>
copy the tests to _b, defects4j test     any failure = real fault detected
```

Test classes are named `<Class>AgentTest` so they never collide with developer
tests and can always be measured in isolation with `-t`.

### Contamination controls

- The trigger test **file** is deleted, not just the failing method: leaving the
  rest of the class in place would show the agent what is tested and how.
- Defects4J has been public for years and may be in the model's training data.
  This cannot be eliminated. Planned mitigation is a later comparison against
  GitBug-Java, whose bugs postdate the cutoff.

### Baselines available at no cost

`gen_tests` ships with EvoSuite and Randoop, and the developer suite itself is
an upper bound. The agent is measured against three references, not against
nothing.

---

## Status

- [x] Sample fixed
- [x] Classification, 40/40
- [ ] Review of unclear entries and of the first 10
- [x] Mutation measurement, 38/40 (Gson-14, Gson-16 excluded — tool limitation)
- [ ] `nearby_mutant` remeasured, or formally retired
- [ ] Study B: agent prompt validated on one bug
- [ ] Study B: full run

# Fourth campaign: protocol

**Draft of 20 November 2026, not fixed.** The checks without the model and the
pilot below have been made. The protocol is fixed by the merge of the pull
request that adds it, with its scripts as they are in that commit. From then
on, anything done differently is a deviation and is listed at the end, with its
date and reason, before the step it affects.

## Why a fourth campaign

The third campaign made the comparison of the two arms on 28 fix commits that
postdate the model's training data, under the second campaign's conditions
(`../campaign3/PROTOCOL.md`). Its hypothesis was not rejected: 8 of 23 against
5 of 23, three discordant pairs against none, p = 0.25. Its corpus was what had
been mined, not what a power calculation asked for: it needed six discordant
pairs against none, and said nothing reliable about the size of the effect.

Since then the post-cutoff subjects available have been counted and classified
(`../README.md`, "Post-cutoff pool" and "Fault types of the post-cutoff
pool"). A corpus matched by fault type to the Defects4J sample, as the matched
corpus was, could take at most 69 of the new ones, because omissions are 29%
of them and 55% of the sample; that is about 57 pairs. This campaign takes
instead every eligible candidate no agent has run on, less the exclusions
below, and deals with the difference in composition in a secondary analysis
that weights each fault type by its share in the Defects4J sample.

The arms are separate conditions, never pooled with those of the third
campaign, of the earlier runs on post-cutoff subjects, or of the Defects4J
campaigns.

## What is fixed

| | |
|---|---|
| Subjects | the 115 of `subjects.txt` |
| Arms | `m4`, implementation-visible; `s4`, specification-only; as built by `bin/generate-campaign4.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per subject and arm, 230 in all |
| Order | subjects in the order of `subjects.txt`, a seeded shuffle; both arms of a subject before the next subject; `m4` first for the 1st, 3rd, 5th … subject and `s4` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign4.sh`) |
| Prompts | the third campaign's: `bin/generate-campaign4.sh` writes them as `bin/generate-postcutoff.sh` does, word for word; the prompt of each run is kept |
| Acceptance | the third campaign's, the same for both arms: the suite is compiled on its own in the staged fixed revision, and each test method that fails there is left out by name |
| Detection | `bin/measure-campaign4.sh`, the third campaign's measurement: the suite as written, run on the fix commit and on its parent with `bin/AgentTestRunner.java`; Java 11, Maven 3.9 offline for the production classes |
| Mutation score and line coverage | `bin/mutation-campaign4.sh`, as the third campaign measured them afterwards: PIT 1.30.2 and its default mutators, on the classes the fix modifies, with the suite as accepted; PIT is stopped after two hours on a suite, which then has no figure |

What the agent is given, what is enforced and what is recorded are in the
header of `bin/generate-campaign4.sh`. The staging, compiling and running of a
suite that the generator and both measurements share is the third campaign's
`bin/campaign3-lib.sh`, unchanged, and so are `bin/AgentTestRunner.java` and
`bin/ExcludedTestsFilter.java`.

**The subjects.** The eligible candidates of the post-cutoff pool, as
`../postcutoff-pool/eligible.tsv` lists them, that no agent has run on: not
the third campaign's 27 subjects in the pool, and not the two subjects of its
pilot, `commons-lang-6c4269eb8` and `commons-csv-ab3d7236`, which pilot this
campaign too. That leaves 129. Two exclusions are decided here, before any
run, and neither depends on a result:

- **The six the blind classification flagged**
  (`../postcutoff-pool/fault-types.tsv`): four that fix several distinct
  faults (`110683aa6`, `9b95001e9`, `48bf95fb1`, `86ed42da5`) and two that do
  not look like the fix of a fault (`8089a0c2d`, `2c0b84836`). The pool's
  screen excludes both kinds; these came to light only when the diffs were
  classified.
- **The nine whose commit message credits an AI**: six Copilot Autofix
  (`6b98966dd`, `e871e5b30`, `98fb6efc5`, `e588cc629`, `48bf95fb1`,
  `75d71af80`), one Claude (`e04b9bc29`), one ChatGPT (`d62646495`) and one
  Codex (`e985f2eec`). The screen already excludes, as a population, a
  maintainer's commits marked as assisted by Codex. These nine were fixed
  with an AI's help, unlike the faults of the Defects4J sample, and the agent
  under study is itself a model.

`48bf95fb1` is in both lists, so 14 are left out and 115 remain: 93 from
Commons Lang, 16 from Commons CSV and 6 from Commons CLI, fix commits from 17
January to 19 November 2026, 29 of them after 22 September. By fault type, as
classified blind before any run: 35 `OMISSION`, 23 `SUBSTITUTION`, 19
`MISSING_CLAUSE`, 17 `ALGORITHM`, 12 `STATE` and 9 `API`. 108 are eligible
under the strict reading of the screen.

Each subject's record (`subjects/<tag>/`) comes from the validation that made
the pool (`bin/revalidate-postcutoff.sh`): the fix commit, the production and
test classes it changes, and its trigger tests. Three subjects have no named
trigger test, because on the parent their tests ran out of memory
(`commons-lang-19b59ffdd`, `commons-lang-ae85262f0`) or did not finish
(`commons-lang-5d46a39e4`); their `meta.txt` says so.
`bin/subjects-campaign4.py` writes `subjects.txt` and the records by the rule
above, and checks them. The code is exported with `git archive` from clones of
the upstream repositories at the heads that `../README.md` gives for the pool.

**A run is final.** It is made again in two cases only. One: a usage limit of
the plan ended it before it produced a result (the generator's `dead` state);
its record is kept under `cut-short/` and its tests are not used. Two: the
harness failed before the agent was started (export, build, javadoc); the fix
is a deviation and is recorded. A run that completes is not repeated, whatever
it produced: no test file, tests that do not compile, a suite that ends on its
turn or cost limit.

**No interim look.** Nothing is measured until every one of the 230 runs has a
status.

## What differs from the third campaign

The conditions are the third campaign's: the same model, CLI version, tools,
limits, flags, environment and prompts, the same acceptance and the same
measurement of detection. These things differ:

| | Third campaign | Fourth campaign |
|---|---|---|
| Subjects | the 28 fix commits validated for the two mined corpora | 115 of the pool's eligible candidates |
| Temporary directory of a sandboxed command | `/tmp/claude-1000`, the machine's, shared by every run and every other session | a short, empty directory of the run's own, named to the CLI in `CLAUDE_CODE_TMPDIR` and removed after the run, its contents kept in the run's record |
| The operating system's jars, Maven and package notes (`/usr/share/java`, `maven-repo`, `maven`, `doc`) | readable; the `mvn` on the `PATH` starts in `m3` | not readable; `mvn` does not start |
| Sandbox settings | written by `bin/generate-postcutoff.sh` | `bin/agent-sandbox.py settings` |
| Mutation score and line coverage | measured afterwards, not part of the protocol | measured before the analysis; the second campaign's H2 is a hypothesis of this protocol |
| A run that reads files of its own outside the working copy | a violation, as the rule was written | not a violation when the files are in its own temporary directory, or are the CLI's saved copy of its own command's output (Exclusions) |
| The run's record | | also what the run left in its temporary directory (`.tmp.tar.xz`), and that directory's path (`.meta.json`), which the audit counts apart (`own tmp`) |

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

1. **Generation.** `./bin/run-campaign4.sh`. It stops when the plan's usage
   reaches the generator's threshold and is run again after the limit resets.
2. **Audit.** `./bin/audit-campaign4.py data/campaign4 -v > data/campaign4/audit.txt`.
   Every flagged command is read with its result, and the runs with a
   violation (defined below) are listed in `data/campaign4/violations.txt`, one
   per line: arm, subject, reason. The `s4` runs in which the agent called
   `javac` itself are listed the same way in `data/campaign4/direct-javac.txt`.
   Both files are committed even if they are empty.
3. **Detection.** `./bin/measure-campaign4.sh`.
4. **Mutation score and line coverage.** `./bin/mutation-campaign4.sh`.
5. **Analysis.** `./bin/analyze-campaign4.py > data/campaign4/analysis.txt`.

## Outcomes

- **Primary: real-fault detection.** A suite detects the fault when
  `bin/measure-campaign4.sh` gives it the verdict `Fail`: with the tests that
  failed on the fixed revision at acceptance left out, it passes on the fix
  commit and at least one of its tests fails on the parent commit. A test that
  is aborted because an assumption does not hold has not failed. A class whose
  set-up fails on the parent and not on the fix counts as a failing test. A
  suite that finishes on the fix commit and does not finish on the parent
  within 20 minutes is `Fail`, with the note `timeout`.
- **No verdict** (`Broken`): the suite does not compile against the parent
  commit, or does not pass on the fix commit when it is run again.
- **Secondary.** Mutation score, as mutants detected over mutants generated
  (`bin/mutation-campaign4.sh` lists the PIT statuses that count as
  detected), and line coverage, each pooled over the suites of an arm; the
  share of test methods left out at acceptance; turns and list-price cost.

Sets:

- **paired**: the subjects with a verdict, `Pass` or `Fail`, in both arms;
- **complete**: the paired subjects that also have a mutation score and a
  line-coverage figure in both arms.

## Hypotheses, tests and decision rule

All in `bin/analyze-campaign4.py`, committed with this file. The order of the
subjects, H1's interval and the composition analysis use Python's
`random.Random(20261120)`. H2's interval is the second campaign's, computed by
that campaign's own function with its seed, 20261117, as the third campaign's
mutation analysis computed it.

**H1. The arms differ in detection.** Exact McNemar test, two-sided, on the
paired set, at α = 0.05. The difference in detection rate is reported with a
95% percentile interval from a bootstrap over subjects: 10,000 resamples of
the paired set with replacement, the two arms of a subject kept together.

**H2. Detection falls further than mutation score does.** The second
campaign's H2, as `../campaign2/PROTOCOL.md` defines it, on this campaign's
complete set. It is assessed only if H1 is rejected with `m4` above `s4`; the
sequence is fixed, so no correction is applied. For detection rate *D*, pooled
mutation score *M* and pooled line coverage *C*:

    fall(X) = 1 − X(s4) / X(m4)

The statistic is fall(*D*) − fall(*M*). Its 95% interval is a percentile
bootstrap over subjects: 10,000 resamples of the complete set with
replacement, the two arms of a subject kept together, `random.Random(20261117)`,
bounds at the 250th and 9,750th of the sorted values. A resample in which `m4`
detects nothing has no fall(*D*); such resamples are left out, counted, and the
bounds taken at the same quantiles of the rest. H2 is supported if the lower
bound is above zero. The same interval for fall(*D*) − fall(*C*) is reported
as a secondary result.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 rejected with `m4` above `s4`, H2's lower bound above zero | On faults that postdate the model's training data, the arms differ in detection in the direction they do on Defects4J, and detection falls further than mutation score: the claim of the paper's title holds on these faults. Recall of the benchmark does not account for it |
| H1 rejected with `m4` above `s4`, H2's interval includes zero | The arms differ in detection on these faults in the direction they do on Defects4J. That detection falls further than mutation score is not shown on them |
| H1 not rejected | This corpus does not show the difference. The write-up says so and gives the interval. It does not read this as the absence of an effect, nor as evidence that recall produced the effect on Defects4J |
| H1 rejected with `s4` above `m4` | The direction is reversed on these faults, and the write-up reports that |

The figures of the Defects4J campaigns and of the third campaign are reported
in every case.

**Composition (secondary, no decision rule).** The subjects are not matched to
the Defects4J sample by fault type. The difference in detection rate is also
reported with each fault type weighted by its share in the sample: 22, 6, 5, 4
and 3 of 40 for `OMISSION`, `ALGORITHM`, `SUBSTITUTION`, `STATE` and
`MISSING_CLAUSE`, the sample as `../fault-taxonomy.csv` classifies it except
Csv-16, counted as `STATE`. `API`, 0 of 40, weighs nothing. Each subject's type
is the final type in `../postcutoff-pool/fault-types.tsv`. For each arm, the
detection rate of each type on the paired set is weighted and summed; the 95%
interval of the difference is a percentile bootstrap that resamples each
type's paired subjects within the type, 10,000 times. A type with no paired
subject is reported as such, and the weights of the others are scaled to sum to
one.

**What these tests can show.** If 23 of every 28 subjects end in the paired
set, as in the third campaign, there will be about 94 pairs. H1 then rejects
with probability about 1.0 if the shares of discordant pairs are the second
campaign's (16 and 1 of 39), 0.97 if the gap is half that (8 and 1 of 39), and
0.99 if they are the third campaign's (3 and 0 of 23); with one pair in 46 the
other way (3 and 0.5 of 23), 0.75. It still needs six discordant pairs against
none, eight against one, or ten against two. H2 was not sized: the second
campaign's interval on 39 bugs and the third's on 23 subjects are the only
guides.

## Exclusions

Fixed here, and none depends on a result.

- **No verdict.** A subject whose suite in either arm is `Broken`, or which
  has no suite because the run produced none that compiles or none with a test
  that passes on the fixed revision, is outside the paired set. It is listed
  with its reason.
- **Violation.** A run is left out of the primary analysis, as if it had
  produced no suite, when its transcript shows a command that did one of
  these: received data from the network; read a file outside the working copy
  that is not part of the operating system or the JDK; or, in `s4`, ran code
  from `lib/`, printed, unpacked or disassembled what is in it, or gave the
  compiler an option that executes code. A command the sandbox refused is not
  a violation. Not outside the working copy in this sense: a command's own
  private `/tmp`; the run's own temporary directory; and the copy the CLI saves
  of the output of one of the run's own commands, which the Read tool can open.
  Each holds only what the run itself wrote or printed. Violations are decided
  at step 2, before anything is measured.

  An `s4` agent that calls `javac` itself, where its prompt says to compile
  through `compile.sh` and nothing else, breaks the prompt and commits no
  violation, unless it gives the compiler an option that executes code. Such
  runs stay in the primary analysis, are listed at step 2, and are left out in
  a sensitivity analysis.

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
5. `s4` runs in which the agent called `javac` itself left out.
6. Only the subjects eligible under the strict reading of the screen (108).

## Descriptive comparisons

None is a test of this protocol.

- **By project, by fault type and by date of the fix**: up to 22 September
  2026, the end of the window mined for the matched corpus, and after it.
- **The third campaign beside this one**: the difference in detection rate
  between the arms in each, and the difference between the two differences
  with a bootstrap interval, each campaign's subjects resampled on their own.
  The two campaigns' subjects were selected by different rules and run in
  different sandboxes.
- **The second campaign beside this one**, in the same way. The campaigns
  differ in more than the date of the faults, so this is not a measurement of
  what recall contributes.

## What this campaign does not control

- **That the fixes postdate the training data** rests on one check: five issue
  identifiers from January 2026, the earliest part of the matched corpus's
  window, which the model disclaimed. Every subject is from 17 January 2026 or
  later. No subject is probed on its own, and the check is not made again.
- **Only the fix is new.** These are long-lived classes of libraries the model
  knows well. Their code as it stood before the fix, with the fault in it, may
  be in the training data. What the model cannot have seen is the fix and its
  tests.
- **The composition of the subjects.** Not matched: 30% omissions against the
  Defects4J sample's 55%, three projects, 93 of 115 from Commons Lang. The
  weighted analysis rests on fault types that a model classified from the diffs
  alone and that nobody has checked by hand.
- **The pool's screen** was applied knowing which candidates meet the subject
  contract, though not knowing anything about a run.
- **The implementation's own text.** The source under test and the developer
  tests that stay are not edited.
- **The specification is the fixed revision's.** The javadoc `s4` reads is
  generated from the repaired source and may document the repair.
- **One run per subject and arm.** Variation between runs is not estimated.
- **One measurement per suite.** A suite is run once on each revision. A test
  that draws random input can fail on one run and pass on the next.
- **One model, one agent.**
- **The prompts are not identical.** As in the second and third campaigns,
  they differ in what an arm requires.
- **Enforcement in `s4` is not complete.** The JDK's launchers other than
  `javac`, `unzip`, `python` and `perl` are hidden; other general-purpose
  tools are not. The transcript audit is what covers the rest.
- **The Read tool** can open the CLI's saved copies of a run's own long
  outputs, under the user's home; the sandbox does not close that. Those copies
  hold nothing the run did not print.
- **A runner of our own.** The projects' build does not run the suites. A test
  that depends on what Maven's test plugin sets up could behave differently;
  it would do so on both revisions.

## Checks made without the model

**The sandbox.** On 20 November 2026, `./bin/agent-sandbox.py probe` on this
machine, with CLI 2.1.316, the binary of the runs: every check passed in both
arms (`probe.txt`). A command's `$TMPDIR` is the run's own directory; neither
the directory all sessions share nor the machine's `/tmp` can be read; the
packaged jars, Maven and package notes cannot be listed, and Maven does not
start. What the CLI leaves in the run's temporary directory is only what the
run's own commands wrote there. The Read tool can still open the CLI's saved
copy of a run's own long output.

**The subjects, with no model call.** On 20 November 2026, the generator and
detection were run on all 115 subjects in both arms (`DRY=1`), and the mutation
measurement on the `m4` suites. The developers' own test classes for the fix,
renamed, stood in for the agent's suite. The output was kept outside the
repository, where no agent can read it, and was deleted before any run.

- **Generation.** Both revisions of every subject were exported and built
  offline. The agent's scripts compiled and ran a two-test class in all 230
  working copies. Every stand-in suite was accepted with no test left out:
  8,190 test methods in each arm. With no agent, nothing is left in a run's
  temporary directory; that part is the probe's.
- **The search of the working copies** found no issue identifier, pull-request
  number, fix-commit hash or subject line in any of them. It found a trigger
  test's name in the `m4` working copies of four subjects. Each time it was a
  method of the same name in another test class:
  - `testBigDecimal` and `testBigInteger` in `EqualsBuilderTest`
    (`commons-lang-1418a770b`);
  - `testLastIndexOf_String` in `StringUtilsEqualsIndexOfTest`
    (`commons-lang-b1aba6833`);
  - `testEqualsIgnoreCase`, also in `StringUtilsEqualsIndexOfTest`
    (`commons-lang-7c91ce989`);
  - `testConstants` in `NumberUtilsTest` and `FractionTest`
    (`commons-lang-c07bc828f`).
- **Detection.** All 230 stand-in suites are `Fail`. On 110 subjects the tests
  that fail on the parent are the trigger tests the validation recorded; for
  two of these it recorded the frame of a lambda inside the test. The other
  five:
  - `commons-lang-05fffe85e`: the three trigger tests fail, and so do five
    more tests of the same class. Those five fail in the check the project's
    tests make after each test (`AbstractLangTest.after`), because the trigger
    tests' failure leaves an object in `ToStringStyle`'s registry.
  - `commons-lang-184c9e832`: does not finish on the parent within 20 minutes
    (`timeout`). Its trigger test waits for a call that does not return there,
    under a JUnit timeout that does not interrupt it.
  - `commons-lang-5d46a39e4`: does not finish on the parent within 20 minutes
    either, as in the validation.
  - `commons-lang-19b59ffdd`: in the validation its tests ran out of memory on
    the parent; here seven of them fail.
  - `commons-lang-ae85262f0`: runs out of memory on the parent, as in the
    validation. The runner ends with status 1 without writing its report,
    which the measurement reads as `Fail` with no failing test named.
- **Mutation, `m4`.** PIT gave a figure for 107 suites. It gave none for these:
  - The four subjects whose fix is in `FastDateParser`
    (`commons-lang-f4442b1c9`, `dda928301`, `f4bdd4e1d`, `edcc0ff2c`). PIT did
    not finish within the 30 minutes this check allowed; the campaign allows
    two hours.
  - `commons-lang-c07bc828f`. Its developers' test `testGetJavaAwtHeadless`
    asserts that `java.awt.headless` is not set, and PIT sets it in the JVMs it
    runs the tests in. PIT does not run on a suite that fails without mutation.
  - The three `commons-cli` subjects whose fix is in `Converter`
    (`commons-cli-f3ba9c951`, `8010193ee`, `7d77ecce8`). `Converter` is an
    interface whose code is all in lambdas assigned to its constants. PIT made
    no mutant there and counted no line, so these three subjects have no
    mutation score whatever the suites, and are outside the complete set.
- **Analysis.** It ran on this output. It also ran on a copy of the output in
  which the `s4` verdicts and mutation figures were made up, so that H1 is
  rejected and H2 computed; there the complete set was 107 subjects.
- **Durations.** Generation took 55 minutes. Detection took 2 hours 9 minutes,
  80 of them in the four runs that end by timeout. The mutation measurement of
  one arm took 3 hours 41 minutes, 2 hours of them in the four runs that did
  not finish.

The check found two faults in the scripts, both corrected before this protocol
was fixed:

- `bin/measure-campaign4.sh` and `bin/mutation-campaign4.sh` ended with status
  1 when the last subject had no record in `s4`.
- `bin/analyze-campaign4.py` counted the three `Converter` suites among those
  with a mutation figure.

## Pilot

Four runs with the model, on 20 November 2026, with the user's agreement: the
third campaign's two pilot subjects, `commons-lang-6c4269eb8` (`WordUtils`) and
`commons-csv-ab3d7236` (`CSVPrinter`), each in both arms. The generator was
this campaign's, at the commit that adds this protocol (`8a2e729`). The
subjects' records were the third campaign's (`../campaign3/pilot/subjects/`).
This campaign's scripts then audited the runs and measured detection and
mutation. The record is in `pilot/`, with the audit's output in
`pilot/audit.txt`. It is not part of any result.

- **Runs.** All four ended normally on `claude-sonnet-5`, CLI 2.1.316. They
  took 15 minutes and cost $2.07 at list prices. In `m4` they took 13 turns
  (`commons-lang`) and 20 (`commons-csv`); in `s4`, 7 and 13.
- **Commands.** Each agent wrote its test class and nothing else. The
  transcripts show no network or version-control command. The harness refused
  nothing and the sandbox denied nothing. The first request of the first run
  was refused once for authentication; the CLI retried it and the run went on.
- **Audit.** It flagged two commands of one `s4` run (`commons-csv-ab3d7236`).
  The agent called `javac` itself, writing the classes to `/tmp/out2`, and then
  removed that directory. Inside the sandbox `/tmp` is private to each command,
  so neither command reached outside the working copy. The `javac` call is one
  that step 2 lists and the primary analysis keeps.
- **Temporary directory.** No command named the run's own temporary directory.
  At the end it held only the CLI's empty directories (`.tmp.tar.xz`).
- **Measurement.** Acceptance left out 0 of 102 tests in `m4` and 7 of 96 in
  `s4`. All four suites are `Pass`, as in the third campaign's pilot; the
  verdicts check the pipeline and nothing else. PIT gave each suite a figure.

The third campaign chose its pilot on classes no subject had under test. Here
two subjects do: `commons-lang-184c9e832` (`WordUtils`) and
`commons-csv-09e27ffdb` (`CSVPrinter`). The pilot's record is under the user's
home, which no agent can read.

## Deviations

None.

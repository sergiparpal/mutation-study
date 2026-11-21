# Fifth campaign: protocol (draft)

**Draft of 21 November 2026, not fixed.** No run has been made with the model
for this campaign. The scripts this file names are written, and have been
tried without the model on two subjects ("Checks to be made without the
model", below). The full checks and the pilot have not been made. It will be
fixed as the fourth campaign's was: by the merge of the pull request that adds
it, after those checks and the pilot. Until then it can change.

## Why a fifth campaign

The write-up explains the effect by a mechanism. An agent writing tests
against code it can read encodes that code's behaviour as the expected
behaviour. Shown the repaired code, its tests encode the repair, and so they
detect the fault. Shown faulty code, its tests encode the fault, and so they
cannot detect it (`../../PREPRINT.md`, §4.1). Every campaign so far has shown
the implementation-visible agent the repaired revision, which is the first
case. The second case is asserted in §4.1 and not measured (§4.6).

This campaign measures it. The agent is shown the faulty revision, and its
suite is accepted there and then run on the repair. A suite that passes on the
faulty revision and fails on the repaired one encodes the fault as expected
behaviour: it *certifies* the fault, and would report the repair as a
regression. Two questions follow:

1. How often does a suite written against the faulty revision certify the
   fault? Published work measures how often such suites miss a fault. None
   that §6 found reports how often they lock one in on real faults.
2. Does that happen as often as the agent shown the repair detects the fault?
   §4.1 says the sign of the effect "depends entirely on which revision the
   agent is shown". If so, the two rates should be close. If certification is
   much rarer, the repaired code does more than get copied: it may also show
   the agent which inputs to try.

So that the second question is answered by a comparison made inside one
campaign, the fourth campaign's implementation-visible arm is run again
beside the new one, on the same subjects and under the same conditions.

The arms are separate conditions. They are never pooled with those of earlier
campaigns.

## What is fixed

| | |
|---|---|
| Subjects | the fourth campaign's 115 (`../campaign4/subjects.txt`), in a new order (`subjects.txt`) |
| Arms | `b5`: implementation-visible on the faulty revision, the parent of the fix commit (`<fix>~1`, the revision the fourth campaign's measurement calls buggy). `m5`: implementation-visible on the fix commit, which is the fourth campaign's `m4` made again. Both are built by `bin/generate-campaign5.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per subject and arm, 230 in all |
| Order | subjects in the order of `subjects.txt`, a shuffle with `random.Random(20261122)`; both arms of a subject before the next subject; `b5` first for the 1st, 3rd, 5th … subject and `m5` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign5.sh`) |
| Prompt | `m4`'s, word for word, in both arms. Nothing in either says which revision the agent has, or that the code has a fault |
| Working copy | `m4`'s, made from the arm's revision: the tree exported without its history. The test files the fix commit touches are removed in both arms, as are changelogs, release notes and upgrade guides and what the build leaves under `target/` except the compiled classes. `_tools/` is added, with the test libraries, the runner and `test.sh` |
| Sandbox | `bin/agent-sandbox.py settings <work> m <jdk_bin>` in both arms, since both see the implementation. Each run has a temporary directory of its own, named in `CLAUDE_CODE_TMPDIR` |
| Acceptance | `m4`'s, on the arm's own revision. The suite is compiled on its own in the staged revision the agent was given, and each test method that fails there is left out by name |
| Measurement | `bin/measure-campaign5.sh`: the fourth campaign's measurement, with each arm's revisions in its own order. The suite is run on the revision it was accepted on and on the other one, with the tests that failed at acceptance left out. Java 11, Maven 3.9 offline for the production classes |
| Mutation score and line coverage | `bin/mutation-campaign5.sh`: the fourth campaign's, PIT 1.30.2 and its default mutators, on the classes the fix modifies, with the suite as accepted, on the revision it was accepted on. PIT is stopped after two hours on a suite, which then has no figure |

The scripts are the fourth campaign's, with these changes and no other. What
the generator, the measurements and the runner share is unchanged:
`bin/campaign3-lib.sh`, `bin/AgentTestRunner.java`,
`bin/ExcludedTestsFilter.java` and `bin/agent-sandbox.py`. The change that
makes `b5` is the one §4.6 has in mind. The revision staged for the agent and
for acceptance becomes `$SHA~1`, the parent the measurement already uses, in
place of `$SHA`.

**The subjects.** These are the fourth campaign's 115, with their records
(`../campaign4/subjects/`) as they are. On 21 November 2026, in the pool's
clones, every one of the 115 fix commits was found to have a single parent.
Every class under test was also found to exist at that parent, so the prompt
names the same classes in both arms. `bin/subjects-campaign5.py` writes
`subjects.txt` by the rule in the table; with `--check`, it confirms the list
and makes both checks again. The fourth campaign's arms have run on these
subjects, and their results are known. That is why `m5` is run again
and not replaced by `m4`. `b5` has no earlier counterpart.

**A run is final.** A run is made again in two cases only. The first is that a
usage limit of the plan ended it before it produced a result. Its record is
then kept under `cut-short/`, and its tests are not used. The second is that
the harness failed before the agent was started; the fix is then a deviation
and is recorded. A run that completes is not repeated, whatever it produced.

**No interim look.** Nothing is measured until every one of the 230 runs has a
status.

## What differs from the fourth campaign

| | Fourth campaign | Fifth campaign |
|---|---|---|
| Arms | `m4`, the fix commit; `s4`, specification-only | `b5`, the parent of the fix commit; `m5`, the fix commit |
| Revision of acceptance and of PIT | the fix commit, in both arms | the arm's own revision |
| Outcome of the new arm | detection, in both arms | certification in `b5`, detection in `m5` |
| Order | `random.Random(20261120)` | `random.Random(20261122)` |
| Tests left out at acceptance | not run again | also run on the other revision, as a secondary outcome |
| Closing messages | not read | `b5`'s read for a statement that the code under test is wrong, at the audit, before anything is measured |

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

0. **Before the pilot, and again before the campaign.** Two checks are run
   with the CLI binary of the runs, `./bin/agent-sandbox.py probe` and
   `./bin/probe-saved-copies.py`. Every check of both must pass.
1. **Generation.** `./bin/run-campaign5.sh`. It stops when the plan's usage
   reaches the generator's threshold, and is run again after the limit resets.
2. **Audit.** `./bin/audit-campaign5.py data/campaign5 -v > data/campaign5/audit.txt`.
   Every flagged command is read with its result. The runs with a violation,
   as defined below, are listed in `data/campaign5/violations.txt`. The
   closing message of every `b5` run is read
   (`./bin/audit-campaign5.py data/campaign5 --closing`). Those that say the
   code under test is wrong are listed in `data/campaign5/closing-b5.txt`,
   with the words that say it. Both files are committed even if they are
   empty.
3. **Measurement.** `./bin/measure-campaign5.sh`.
4. **Mutation score and line coverage.** `./bin/mutation-campaign5.sh`.
5. **Analysis.** `./bin/analyze-campaign5.py > data/campaign5/analysis.txt`.

## Outcomes

- **Primary, `b5`: certification.** A suite certifies the fault when
  `bin/measure-campaign5.sh` gives it the verdict `Fail`. That is: with the
  tests that failed on the parent at acceptance left out, it passes on the
  parent, and at least one of its tests fails on the fix commit. The fourth
  campaign's rules apply, with the revisions swapped:
  - a test aborted because an assumption does not hold has not failed;
  - a class whose set-up fails on the fix commit and not on the parent counts
    as a failing test;
  - a suite that finishes on the parent and does not finish on the fix commit
    within 20 minutes is `Fail`, with the note `timeout`.
- **Primary, `m5`: detection**, as the fourth campaign defines it.
- **No verdict** (`Broken`): the suite does not compile against the other
  revision, or does not pass on its own revision when it is run again.
- **Secondary.**
  - Mutation score, as mutants detected over mutants generated, and line
    coverage, each on the arm's own revision and pooled over the suites of an
    arm.
  - The tests left out at acceptance, run on the other revision. In `b5`,
    those that pass on the fix commit are tests that expected the repaired
    behaviour, which acceptance discarded. In `m5`, those that pass on the
    parent expected the faulty behaviour.
  - The `b5` runs whose closing message says the code under test is wrong.
  - The share of test methods left out at acceptance, and turns and
    list-price cost.

Sets:

- **paired**: the subjects with a verdict, `Pass` or `Fail`, in both arms;
- **complete**: the paired subjects that also have a mutation score and a
  line-coverage figure in both arms.

## Estimate, hypothesis, test and decision rule

All are in `bin/analyze-campaign5.py`, committed with this file. The order of
the subjects and every interval use Python's `random.Random(20261122)`.

**The certification rate.** This is `b5`'s share of `Fail` among its subjects
with a verdict, with a 95% percentile interval from 10,000 bootstrap resamples
of those subjects. It is the estimate §4.6 asks for, and it is not a test.

**H1. Certification in `b5` and detection in `m5` differ.** This is tested
with an exact McNemar test, two-sided, on the paired set, at α = 0.05. The
difference between the two rates is reported with a 95% percentile interval
from 10,000 bootstrap resamples of the paired set, the two arms of a subject
kept together.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 not rejected | Shown the faulty code, the agent's suites lock the fault in about as often as, shown the repaired code, they detect it. The difference is given with its interval. That agrees with §4.1. The test cannot show that the two rates are equal; the interval says how far apart they could be |
| H1 rejected, `b5` below `m5` | The sign of the effect follows the revision the agent reads, but its size does not: the repaired code does more than get copied. §4.1 is qualified to say so |
| H1 rejected, `b5` above `m5` | The fault is locked in more often than the repair is detected, and the write-up reports that |

The certification rate and its interval are reported in every case, with the
fourth campaign's figures.

**Mutation score (secondary, no decision rule).** For each arm on its own
revision, the pooled mutation score and line coverage are reported. The
difference `b5` − `m5` is given with a 95% interval from 10,000 bootstrap
resamples of the complete set. The same figures are given for the suites that
certify and for those that detect. They show whether mutation score registers
which revision a suite was written against.

**What this test can show.** Suppose the paired set has 112 subjects, as in
the fourth campaign, and `m5` detects as `m4` did, on 21 of them. Suppose too
that where the rarer outcome occurs, the other arm's also occurs on 60% of
those subjects. A simulation of 20,000 draws then gives H1 these chances of
rejection:

| Certification in `b5` | Chance of rejection |
|---|---|
| the same as detection, 21 of 112 | 0.03 (the test's size) |
| three quarters of it, 16 | 0.16 |
| half of it, 10 | 0.67 |
| a quarter of it, 5 | 0.97 |

H1 therefore finds a large asymmetry and not a small one. When it is not
rejected, the interval is the result.

## Exclusions

These are fixed here, and none depends on a result.

- **No verdict.** A subject is outside the paired set, and is listed with its
  reason, when its suite in either arm is `Broken`. It is also outside when
  either arm has no suite, because the run produced none that compiles or
  none with a test that passes on its own revision.
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

A run in which the agent names the fix is not excluded. Naming the fix means
naming the issue or pull request behind it, the fix commit, or one of the
subject's trigger tests by a name longer than eight characters. Such runs are
counted and analysed separately. A `b5` working copy predates the fix, so a
name found there can only be a coincidence.

## Sensitivity analyses

These are reported with the primary analysis; none is confirmatory.

1. Runs with a violation included.
2. Intention to treat. Every subject counts, runs with a violation as
   measured. A subject without a suite or without a verdict counts as neither
   certifying nor detecting.
3. Runs that name the fix left out.
4. Verdicts that are `Fail` by timeout read as `Pass`.
5. Only the subjects eligible under the strict reading of the screen (108).

## Descriptive comparisons

None is a test of this protocol.

- **By project, by fault type and by date of the fix.** Suppose the repaired
  code shows the agent which inputs to try. Then the gap between detection
  and certification should be widest where the fix adds code: `OMISSION` and
  `MISSING_CLAUSE`.
- **`m5` beside `m4`.** This is the same condition, run twice on the same
  subjects. The comparison reports how many subjects change verdict between
  the two runs, the first estimate the study makes of variation between runs.
- **`b5` beside `s4`.** Neither arm is shown the repair.
- **The second, third and fourth campaigns**, as earlier campaigns have been
  set beside each other: the campaigns differ in more than the arms.

## What this campaign does not control

- **The prompt asks for tests that pass.** It ends "Finish when all your tests
  pass", and in `b5` that means tests that pass on the faulty code. The
  campaign measures what the agent does when asked to write tests for code
  that has a fault it is not told of. That is the setting of tests written
  after the code. It does not measure an agent asked to look for faults.
- **That the fixes postdate the training data** rests on the one check the
  fourth campaign describes.
- **The faulty code is older than the fix.** The faulty code stood in the
  library before the fix, so the model may have seen it in training. It
  cannot have seen the fix.
- **A failing test is not always about the fault.** A test can fail on the
  other revision because of something else the fix commit changed, such as a
  message or a refactoring. This holds for detection in `m5` as for
  certification in `b5`.
- **One run per subject and arm.** The comparison of `m5` with `m4` estimates
  the variation for one condition only.
- **One model, one agent.**
- **The composition of the subjects** is the fourth campaign's: 30% omissions,
  three Commons projects, 93 of 115 from Commons Lang.
- **The Read tool** can open what is in the `tool-results` directory of the
  run's own session, and nothing else of the user's home. That is what
  `../sandbox/saved-copies.txt` found.
- **A runner of our own.** The projects' build does not run the suites. A test
  that depends on what Maven's test plugin sets up could behave differently
  from how it would under Maven. It would do so on both revisions.
- **The subjects have been used.** `m4` and `s4` ran on them, and their
  results are known. That is why `m5` is made again.

## Checks to be made without the model

The full checks have not been made yet; a first trial has.

**Tried so far.** On 21 November 2026 the scripts were tried without the
model on two subjects, `commons-csv-b5940a642` and `commons-lang-1418a770b`,
in both arms. The output was kept outside the repository.

- **Generation.** Each revision was exported and built, and the agent's
  scripts compiled and ran a two-test class. The prompt is the same file in
  both arms. The `b5` stand-ins are the parent's versions of the test files:
  122 and 9 test methods, against the fix's 123 and 13.
- **Measurement.** The `m5` stand-ins are `Fail` and the `b5` ones `Pass`. On
  neither subject does a test of the parent fail on the fix.
- **The left-out run.** It was tried by leaving one test out of each suite of
  one subject. In `m5`, a trigger test was left out, and it failed on the
  parent. In `b5`, a test that passes on both revisions was left out, and it
  passed on the fix.
- **Mutation.** PIT gave each suite a figure, on its own revision. The
  methods it kept are those the measurement ran in all four suites.
- **Analysis.** It ran on this output. It also ran on made-up verdicts for 112
  subjects, and reached each of the three outcomes of the decision rule.

**Still to be made:**

- **The sandbox.** Run both checks of step 0.
- **The subjects, with no model call.** Run the generator and the measurement
  on all 115 subjects in both arms (`DRY=1`), and the mutation measurement on
  both arms. The output is kept outside the repository, where no agent can
  read it, and deleted before any run. The stand-ins for the agent's suite are
  as follows:
  - **`m5`:** as in the fourth campaign, the developers' own test classes for
    the fix, renamed. Each should come out `Fail`.
  - **`b5`:** the parent's own versions of the test files the fix commit
    touches, renamed. They pass on the parent by construction. Where the fix
    changed one of their assertions, they fail on the fix commit; elsewhere
    they pass. The `Fail` verdicts should therefore fall on those subjects and
    no others. This checks the verdict in the direction the campaign needs.
    Subjects with no such file have no stand-in in `b5`, and are listed.
- **The search of the working copies** for issue identifiers, pull-request
  numbers, fix-commit hashes, subject lines and trigger-test names, in both
  arms.
- **The analysis.** Run it on that output. Run it again on a copy with made-up
  verdicts, so that H1 is rejected in each direction.

## Pilot

The pilot has not been run. It is four runs with the model, made only with the
user's agreement: the third campaign's two pilot subjects,
`commons-lang-6c4269eb8` (`WordUtils`) and `commons-csv-ab3d7236`
(`CSVPrinter`), each in both arms. At `m4`'s cost, $0.53 a suite at list
prices, that is about $2. The pilot's record goes in `pilot/`. It is not part
of any result.

## Deviations

None. This is a draft, and nothing has been run.

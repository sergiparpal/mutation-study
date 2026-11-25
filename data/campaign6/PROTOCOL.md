# Sixth campaign: protocol

Fixed on 25 November 2026, before any run on the subjects, by the merge of the
pull request that adds it (#33), after the checks without the model and the
pilot below. The merge commit, with the scripts as they are in it, is the
reference. Anything done differently afterwards is a deviation and is listed at
the end, with its date and reason, before the step it affects.

## Why a sixth campaign

The fifth campaign showed the agent the faulty revision of 115 post-cutoff
faults and asked it, in `m4`'s words, for tests that pass. Its suites lock the
fault in on 7 of them (`../../PREPRINT.md`, §3.13). They cannot detect it,
because acceptance leaves out every test that fails on the code the agent
read. Of the 25 tests left out that way, none expected the repaired behaviour.
The write-up names what that campaign does not measure: an agent asked to look
for faults (§4.6, and "What this does not show" in `../../README.md`). It is
also the nearest the study can come to a question §4.1 leaves open: what an
agent would score against code whose fault nobody has found yet.

This campaign asks the agent to look. It is shown the faulty revision, as in
`b5`, and told that the classes may contain bugs and that its tests are meant
to find them. A test that fails on the faulty revision is then a finding,
not a test to drop. A finding that passes on the fix commit expected the
repaired behaviour, so it detects the fault. That is the criterion every
campaign has used: a test that fails on the faulty revision and passes on the
fix.

Three questions follow:

1. Asked to look for faults in the code as it stood, how often does the agent
   detect the fault? Published work measures this when the model is told what
   is wrong, by an issue description (LIBRO; TDD-Bench Verified; §6). Told
   only that the code might be buggy, the one attempt §6 found is one model
   judging one assertion at a time. It was reported without figures
   (Konstantinou, Degiovanni and Papadakis).
2. Does it detect the fault as often as the agent shown the repair? That
   agent's rate is what the regression evaluation setting reports. If the two
   are close, the setting does not overstate what an agent achieves when
   asked. If the first is much lower, the gap measures how much the setting
   overstates fault finding on these faults.
3. Does the request stop the lock-in? The fifth campaign's `b5` gives the rate
   without the request, on the same subjects.

So that the second question is answered by a comparison made inside one
campaign, the fourth campaign's implementation-visible arm is run a third
time, beside the new one, on the same subjects and under the same conditions.

The arms are separate conditions. They are never pooled with those of earlier
campaigns.

## What is fixed

| | |
|---|---|
| Subjects | the fourth campaign's 115 (`../campaign4/subjects.txt`), in a new order (`subjects.txt`) |
| Arms | `f6`: implementation-visible on the faulty revision, the parent of the fix commit (`<fix>~1`), as `b5`, and asked to look for faults. `m6`: implementation-visible on the fix commit, the fourth campaign's `m4` made a third time. Both are built by `bin/generate-campaign6.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per subject and arm, 230 in all |
| Order | subjects in the order of `subjects.txt`, a shuffle with `random.Random(20261125)`; both arms of a subject before the next subject; `f6` first for the 1st, 3rd, 5th … subject and `m6` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign6.sh`) |
| Prompt | `m6`: `m4`'s, word for word. `f6`: `m4`'s with its last sentence replaced by the paragraph below. Neither says which revision the agent has. `f6`'s says the classes may contain bugs, not that they do |
| Working copy | `m4`'s, made from the arm's revision, as in the fifth campaign: the tree exported without its history. The test files the fix commit touches are removed in both arms, as are changelogs, release notes and upgrade guides and what the build leaves under `target/` except the compiled classes. `_tools/` is added, with the test libraries, the runner and `test.sh` |
| Sandbox | `bin/agent-sandbox.py settings <work> m <jdk_bin>` in both arms, since both see the implementation. Each run has a temporary directory of its own, named in `CLAUDE_CODE_TMPDIR` |
| Acceptance | `m4`'s, on the arm's own revision. The suite is compiled on its own in the staged revision the agent was given, and each test method that fails there is left out by name. In `f6` the tests left out are its findings, and two of `m4`'s rules for a failed run do not apply (below) |
| Measurement | `bin/measure-campaign6.sh`: the fifth campaign's. In `f6` the tests left out at acceptance are also run again on the faulty revision, and they are run on the fix commit whatever the verdict of the rest of the suite. Java 11, Maven 3.9 offline for the production classes |
| Mutation score and line coverage | `bin/mutation-campaign6.sh`: the fifth campaign's, PIT 1.30.2 and its default mutators, on the classes the fix modifies, with the suite as accepted, on the revision it was accepted on. In `f6` the tests left out at acceptance are not part of it. PIT is stopped after two hours on a suite, which then has no figure |

The scripts are the fifth campaign's, with these changes and no other:

- the arms, the seed and the paths;
- `f6`'s prompt and its two rules of acceptance;
- in a dry run, the stand-in suite: in both arms the developers' test classes
  for the fix, which in `f6` are staged on the faulty revision (below);
- the measurement of the left-out tests. They are run one class at a time in
  both arms, and in `f6` on both revisions. A class that does not finish
  there, by time or by ending the runner without its report, is recorded as
  such. A class left out as a whole now runs whole there, as the fifth
  campaign's script meant to do. In that campaign every key left out was a
  method's, so none of its figures depends on this;
- in the mutation measurement, an `f6` suite whose every test was left out
  has no figure. When PIT stops, the note no longer quotes a line that names
  a left-out test;
- at acceptance, each run starts with the previous run's report removed, so
  that a run that ends without one is seen as such. In the fifth campaign's
  script a later round that ended that way would have found the earlier
  round's report, and the run would have failed as it does now, with nothing
  more to leave out;
- the reading of `f6`'s closing messages at the audit;
- the analysis of the outcomes below.

What the generator, the measurements and the runner share stays unchanged:
`bin/campaign3-lib.sh`, `bin/AgentTestRunner.java`,
`bin/ExcludedTestsFilter.java` and `bin/agent-sandbox.py`.

**The prompt of `f6`.** `m4`'s prompt ends: "Compile and run your tests with
./_tools/test.sh, which compiles every *AgentTest.java under <tests>/ and runs
it. Finish when all your tests pass." In `f6` its last sentence is replaced by
this paragraph:

> The classes may contain bugs, and your tests are meant to find them. Write
> each test for the behaviour the class should have, as its documentation and
> the rest of the project describe it, not for whatever the code happens to
> do. When a test fails, decide whether the test or the code is wrong: correct
> a wrong test, and leave a test that fails because the code is wrong as it
> is. Finish when every test that still fails is one you believe shows a bug,
> and name those tests in your final message, with the bug each one shows.

The rest of the prompt is `m4`'s, including "Do not modify or create any file
other than the test classes named above". The request is explicit on purpose.
It gives the agent the best case a prompt can, so that a low rate cannot be
put down to a request the agent could read as optional. A shorter one, such as
"The classes may contain bugs. Write tests that find them.", would not say
what to do with a test that fails, and an agent's habit is to make it pass.
A low rate would then not tell a weak request from an agent that cannot find
the fault. The request does not say that there is a bug, where, or which
revision the agent has.

**Acceptance in `f6`.** As in `m4`, the suite is run in the staged revision;
each test method that fails is left out by name, and the rest is run again
until it passes, in at most five rounds. Two of `m4`'s rules for a failed run
do not apply in `f6`, because there a failing test is what the agent was asked
for:

- **A suite in which every test fails on the faulty revision is kept.** It has
  no certification verdict and no mutation score. Its tests are measured for
  detection like any other left-out tests.
- **A suite that does not finish on the faulty revision** is run again one
  class at a time, with the same limit. A run does not finish when it lasts
  more than 20 minutes, or when it ends the runner without its report. The
  runner writes its report whenever it gets to the end, so a run without one
  died on the way, as a JVM does when a test exhausts its heap. A class that
  does not finish is left out as a whole, as a class that fails as a whole
  is. Acceptance then goes on as above. If the rest of the suite, run together
  again, still does not finish, the run has no suite.

In `m6`, acceptance is `m4`'s unchanged. There, a suite that ends the runner
without its report fails with nothing more to leave out, and the run has no
suite.

**The subjects.** These are the fourth campaign's 115, with their records
(`../campaign4/subjects/`) as they are. The fifth campaign found on
21 November 2026 that every fix commit has a single parent, and that every
class under test exists at that parent. `bin/subjects-campaign6.py` writes
`subjects.txt` by the rule in the table. With `--check`, it confirms the list
and makes both checks again. `m4`, `s4`, `m5` and `b5` have run on these
subjects, and their results are known. That is why `m6` is made again and not
replaced by `m5`.

**A run is final.** A run is made again in two cases only. The first is that a
usage limit of the plan ended it before it produced a result. Its record is
then kept under `cut-short/`, and its tests are not used. The second is that
the harness failed before the agent was started; the fix is then a deviation
and is recorded. A run that completes is not repeated, whatever it produced.

**No interim look.** Nothing is measured until every one of the 230 runs has a
status.

## What differs from the fifth campaign

| | Fifth campaign | Sixth campaign |
|---|---|---|
| Arms | `b5`, the parent of the fix commit; `m5`, the fix commit | `f6`, the parent of the fix commit, asked to look for faults; `m6`, the fix commit |
| Prompt | `m4`'s in both arms | `m4`'s in `m6`; in `f6`, `m4`'s with its last sentence replaced |
| Acceptance | `m4`'s in both arms | `m4`'s; in `f6`, a suite whose every test fails is kept, and one that does not finish, by time or by ending without the runner's report, is run a class at a time |
| Outcome of the new arm | certification | detection; certification is secondary |
| Tests left out at acceptance | run on the other revision, as a secondary outcome | in `f6`, run on both revisions: the primary outcome |
| Closing messages | `b5`'s read for a statement that the code under test is wrong | `f6`'s read for the bugs they name, and whether one is the fault |
| Order | `random.Random(20261122)` | `random.Random(20261125)` |

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

0. **Before the pilot, and again before the campaign.** Two checks are run
   with the CLI binary of the runs, `./bin/agent-sandbox.py probe` and
   `./bin/probe-saved-copies.py`. Every check of both must pass.
1. **Generation.** `./bin/run-campaign6.sh`. It stops when the plan's usage
   reaches the generator's threshold, and is run again after the limit resets.
2. **Audit.** `./bin/audit-campaign6.py data/campaign6 -v > data/campaign6/audit.txt`.
   Every flagged command is read with its result. The runs with a violation,
   as defined below, are listed in `data/campaign6/violations.txt`. The
   closing message of every `f6` run is read
   (`./bin/audit-campaign6.py data/campaign6 --closing`, which prints under
   each message the tests acceptance left out). Each run whose message names
   a test as showing a bug has a line in `data/campaign6/closing-f6.txt`:
   `f6 <subject> fault|other <words>`, with the words that say what the bug
   is. `fault` means one of the bugs named is the fault, by the rule under
   "Outcomes", and `other` means none is. That is judged against the fix
   commit's change to the production code, before anything is measured. Both
   files are committed even if they are empty.
3. **Measurement.** `./bin/measure-campaign6.sh`.
4. **Mutation score and line coverage.** `./bin/mutation-campaign6.sh`.
5. **Analysis.** `./bin/analyze-campaign6.py > data/campaign6/analysis.txt`.

## Outcomes

- **Primary, `f6`: detection.** A test method of an `f6` suite detects the
  fault when all three of these hold:
  - it failed on the faulty revision at acceptance;
  - it fails there again, or does not finish there, at measurement;
  - it passes on the fix commit.

  "Passes" means the runner reports it successful. A test aborted because an
  assumption does not hold, or skipped, has not passed. A test does not finish
  when its class, run on its own, lasts more than 20 minutes or ends the
  runner without its report. The methods of a class left out as a whole are
  counted one by one on the fix commit. A suite detects the fault, verdict
  `Fail`, when at least one of its tests does. Otherwise its verdict is
  `Pass`, including when acceptance left nothing out.
- **Primary, `m6`: detection**, as the fourth campaign defines it.
- **No verdict** (`Broken`): the suite does not compile against the other
  revision. In `m6` it is also `Broken` when it does not pass on its own
  revision when it is run again. In `f6` that leaves its detection verdict as
  it is, and gives it no certification verdict.
- **Secondary.**
  - **Certification in `f6`**, as the fifth campaign defines it for `b5`. With
    the tests left out at acceptance left out, the suite passes on the faulty
    revision, and at least one of its tests fails on the fix commit. A suite
    whose every test was left out has no certification verdict.
  - **False alarms in `f6`.** These are the tests that fail on the faulty
    revision at acceptance and at measurement, and do not pass on the fix
    commit. They are counted per suite and in all. The share of `f6`'s failing
    tests that detect the fault is reported too.
  - **Closing messages in `f6`.** These are the runs whose message names a
    test as showing a bug, and those whose message names the fault. A message
    names the fault when one of the bugs it names is a behaviour that the fix
    commit changes in the production code, and what the message says the
    behaviour should be is what the fix makes it.
  - **In `m6`, the tests left out at acceptance**, run on the parent as in
    `m5`. Those that pass there expected the faulty behaviour.
  - **Mutation score and line coverage.** Mutation score is mutants detected
    over mutants generated. Each is taken on the arm's own revision and pooled
    over the suites of an arm.
  - **The rest**: the share of test methods left out at acceptance, and turns
    and list-price cost.

The two detections are the same event, reached from opposite sides. It is a
test that fails on the faulty revision and passes on the fix. `m6`'s tests
passed on the fix at acceptance and are run on the faulty revision. `f6`'s
failed on the faulty revision at acceptance and are run on the fix. Each side
is checked twice:

- `m6`'s tests pass on the fix at acceptance and again at measurement;
- `f6`'s fail on the faulty revision at acceptance and again at measurement.

Sets:

- **paired**: the subjects with a detection verdict, `Pass` or `Fail`, in both
  arms;
- **complete**: the paired subjects that also have a mutation score and a
  line-coverage figure in both arms.

## Estimate, hypothesis, test and decision rule

All are in `bin/analyze-campaign6.py`, committed with this file. The order of
the subjects and every interval use Python's `random.Random(20261125)`.

**The detection rate when asked to look for faults.** This is `f6`'s share of
`Fail` among its subjects with a detection verdict. It comes with a 95%
percentile interval from 10,000 bootstrap resamples of those subjects. It is
the estimate question 1 asks for, and it is not a test.

**H1. Detection in `f6` and detection in `m6` differ.** This is tested with an
exact McNemar test, two-sided, on the paired set, at α = 0.05. The difference
between the two rates is reported with a 95% percentile interval from 10,000
bootstrap resamples of the paired set, the two arms of a subject kept
together.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 not rejected | Asked to look for faults, the agent shown the faulty code detects the fault about as often as the agent shown the repair. On these faults, the figure of the regression evaluation setting then does not overstate what an agent achieves when asked. §4.1 and §7 are qualified to say so. The test cannot show that the two rates are equal; the interval says how far apart they could be |
| H1 rejected, `f6` below `m6` | Even asked to look for faults, the agent shown the faulty code detects the fault less often than the regression setting credits. The difference and its interval measure how much the setting overstates fault finding on these faults |
| H1 rejected, `f6` above `m6` | Asked to look for faults, the agent detects more than the regression setting credits, and the write-up reports that |

The detection rate and its interval are reported in every case, with the false
alarms that came with it.

**Certification under the request (secondary, no decision rule).** `f6`'s
certification rate is given with its interval. It is set beside `b5`'s on the
same subjects: how many subjects certify in both, in one only, and in neither.
An exact McNemar *p* is given as a description. It is not a test of this
protocol, because `b5` ran in another campaign.

**Mutation score (secondary, no decision rule).** For each arm on its own
revision, the pooled mutation score and line coverage are reported. The
difference `f6` − `m6` is given with a 95% interval from 10,000 bootstrap
resamples of the complete set. The same figures are given for the suites that
detect in each arm. PIT needs the suite to pass, so `f6`'s findings, the tests
that fail on the faulty revision, are not in its mutation score. A suite's
detection of the fault therefore cannot raise its score, and the write-up says
so wherever the two are set side by side.

**What this test can show.** Suppose the paired set has 115 subjects, and `m6`
detects as `m5` did, on 26 of them. Suppose too that where the rarer outcome
occurs, the other arm's also occurs on 60% of those subjects, as the fifth
campaign assumed. H1 then has these chances of rejection, computed exactly; a
simulation of 20,000 draws gives the same to two decimals:

| Detection in `f6` | Chance of rejection |
|---|---|
| the same as `m6`'s, 26 of 115 | 0.03 (the test's size) |
| three quarters of it, 20 | 0.18 |
| half of it, 13 | 0.73 |
| a quarter of it, 6 | 0.99 |

H1 therefore finds a large asymmetry and not a small one. When it is not
rejected, the interval is the result.

## Exclusions

These are fixed here, and none depends on a result.

- **No verdict.** A subject is outside the paired set, and is listed with its
  reason, when either arm has no detection verdict. That is the case when the
  arm's suite is `Broken`, or when the arm has no suite: the run produced none
  that compiles, or, in `m6`, none with a test that passes on its own
  revision.
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
counted and analysed separately. An `f6` working copy predates the fix, so a
name found there can only be a coincidence.

A run whose agent changed a file other than its test classes is not excluded
either. The suite is compiled and run against the staged revision, which the
agent cannot reach. Such runs are counted at the audit.

## Sensitivity analyses

These are reported with the primary analysis; none is confirmatory.

1. Runs with a violation included.
2. Intention to treat. Every subject counts, runs with a violation as
   measured. A subject without a suite or without a verdict counts as not
   detecting.
3. Runs that name the fix left out.
4. Detection by timeout read as none. In `m6`, these are the verdicts that are
   `Fail` by timeout. In `f6`, they are the detections that rest only on tests
   whose class lasts more than 20 minutes on the faulty revision. A run that
   ends without the runner's report is not a timeout. In `m6` a suite that
   ends that way on the faulty revision is `Fail` with no failing test named,
   as in the fourth campaign, and an `f6` detection that rests on such a run
   is read the same way.
5. Only the subjects eligible under the strict reading of the screen (108).
6. In `f6`, only the detecting tests that the closing message names: the
   detection the agent itself reports.

## Descriptive comparisons

None is a test of this protocol.

- **By project, by fault type and by date of the fix.** The fifth campaign
  found that the agent shown the repair detects 10 of the 35 omissions, and
  the agent shown the fault certifies none of them (§4.1). If faulty code
  gives the agent nothing to test where a case is missing, `f6` should detect
  fewest there.
- **`m6` beside `m5` and `m4`.** This is the same condition run three times on
  the same subjects. The comparison reports how many subjects are detected in
  none, one, two and all three runs, with the pairwise agreement and Fleiss'
  kappa.
- **`f6` beside `b5`.** These are the same revision under another request.
  Detection, certification and the share of tests left out are compared.
- **`f6` beside `s4`.** Neither arm is shown the repair, and `f6` is shown the
  fault.
- **The conditions of §6's table.** `f6`'s detection is a row the table lacks:
  the faulty implementation with a request to look for faults.
- **The second to fifth campaigns**, as earlier campaigns have been set beside
  each other: the campaigns differ in more than the arms.

## What this campaign does not control

- **The request is one wording.** It is explicit, and a developer's request
  may be vaguer. A different wording could give a different rate. The rate is
  that of this request.
- **The prompt names the classes the fix changes.** This holds in both arms,
  as in every campaign. For an agent looking for faults, it says where to look,
  down to the class. A search of a whole project would not know that much.
- **The limits are the same in both arms**, 50 turns and $5. A search for
  faults may need more. The runs that reach the limit are reported.
- **A test can fail for a reason other than the fault**, in both directions. A
  detecting test could pass on the fix because of something else the fix
  changed. A test that found the fault could also fail on the fix, if the
  repaired behaviour differs in detail from what the agent expected. The
  closing messages show the second case: a run that names the fault and does
  not detect it.
- **A suite that does not finish is split by class**, not by method, whether
  it ran out of time or ended without the runner's report. A class left out
  because it does not finish is counted on the fix method by method. A method
  that would have passed on the faulty revision can therefore count as
  detecting, if the class finishes on the fix.
- **What the closing message names is a claim.** It is read as what the agent
  says, and judged against the fix by one reader, before anything is
  measured.
- **That the fixes postdate the training data** rests on the one check the
  fourth campaign describes.
- **The faulty code is older than the fix.** The faulty code stood in the
  library before the fix, so the model may have seen it in training. It
  cannot have seen the fix.
- **One run per subject and arm.** `m6` beside `m5` and `m4` estimates the
  variation for one condition only.
- **One model, one agent.**
- **The composition of the subjects** is the fourth campaign's: 30% omissions,
  three Commons projects, 93 of 115 from Commons Lang.
- **The Read tool** can open what is in the `tool-results` directory of the
  run's own session, and nothing else of the user's home. That is what
  `../sandbox/saved-copies.txt` found.
- **A runner of our own.** The projects' build does not run the suites. A test
  that depends on what Maven's test plugin sets up could behave differently
  from how it would under Maven. It would do so on both revisions.
- **The subjects have been used.** `m4`, `s4`, `m5` and `b5` ran on them, and
  their results are known. That is why `m6` is made again, and why `f6`'s
  comparison with `b5` is descriptive.

## Checks made without the model

**The sandbox.** On 25 November 2026, with CLI 2.1.316, the binary of the
runs, both checks of step 0 passed every check, with the settings both arms
use (`probe.txt`, `saved-copies.txt`). The first gave what it gave for the
fifth campaign, apart from the random names of the runs' temporary
directories. The second is the fifth campaign's, byte for byte.

**The subjects, with no model call.** From 25 November 2026 at 08:21 UTC to
20:15, the generator, the measurement and the mutation measurement were run
on all 115 subjects in both arms (`DRY=1`), and the analysis on their output.
Developers' tests stood in for the agent's suite:

- in `m6`, as in `m5`, their test classes for the fix, renamed;
- in `f6`, the same classes, staged on the faulty revision.

The trigger tests among the `f6` stand-ins should fail on the faulty revision
at acceptance and be left out, and pass on the fix at measurement. So every
`f6` stand-in that compiles on the faulty revision should detect the fault,
and none should certify it.

The output was kept outside the repository, where no agent can read it, and is
deleted before any run.

- **Generation.** Both revisions of every subject were exported and built
  offline. The agent's scripts compiled and ran a two-test class in all 230
  working copies. Every `m6` stand-in was accepted with no test left out:
  8,190 test methods, as in the fourth and fifth campaigns. Every `f6`
  stand-in compiled on the faulty revision. 114 were accepted, with 201 of
  their 7,971 test methods left out (2.5%). Three of them met the rules that
  are new in `f6`:
  - In `commons-lang-184c9e832` and `5d46a39e4` the suite did not finish
    within 20 minutes, as in the fifth campaign's check. Its one class, run on
    its own, did not finish either, and was left out as a whole.
  - In `commons-lang-daa17b862` the suite's one test fails, so every test was
    left out. The suite was kept.

  The 115th, `commons-lang-ae85262f0`, had no suite. That was the fault this
  check found (below).
- **The search of the working copies** found, in both arms, what it found in
  the fourth and fifth campaigns and nothing else. That is a trigger test's
  name in the working copies of `commons-lang-1418a770b`, `7c91ce989`,
  `b1aba6833` and `c07bc828f`. The files and lines are the same in both arms.
- **Measurement.** All 115 `m6` stand-ins are `Fail`:
  - Two of them are `Fail` by timeout on the parent: `commons-lang-184c9e832`
    and `5d46a39e4`, as in the fourth and fifth campaigns' checks.
  - In `commons-lang-ae85262f0` the runner ran out of memory on the parent and
    wrote no report. That reads as `Fail` with no failing test named, as in the
    fourth campaign.

  All 114 `f6` suites detect the fault, those of `184c9e832` and `5d46a39e4`
  with the note `timeout`. None certifies it: 111 are `Pass`, and the three
  whose every test was left out have no certification verdict.

  Of the tests left out, 258 failed again on the faulty revision. Of these,
  257 pass on the fix. The other is a false alarm, by the rule that a skipped
  test has not passed. It is `testHugeStrings` in `5d46a39e4`: its class did
  not finish on the faulty revision, and on the fix the test is skipped, as it
  is in the `m6` stand-in. No test was unstable.
- **The left-out run of `m6`** had nothing to run, since no `m6` stand-in test
  was left out. Its counting was tried on made-up reports.
- **Mutation.** PIT gave a figure for 107 `m6` suites and 102 `f6` suites. In
  `m6` it gave none for the eight subjects for which it gave none in the fifth
  campaign:
  - the four whose fix is in `FastDateParser`, which did not finish within
    the 30 minutes this check allowed; the campaign allows two hours;
  - `commons-lang-c07bc828f`, whose developers' test of `java.awt.headless`
    fails under PIT;
  - the three `commons-cli` subjects whose fix is in `Converter`, which have no
    mutant.

  In `f6` it gave none for the same eight and for the three suites whose every
  test was left out. It also gave none for `commons-lang-19b59ffdd`, for which
  `b5` had no stand-in. On the faulty revision, the nine tests that suite
  keeps make the code allocate more than the 1 GB heap that PIT gives each
  process that runs tests. PIT's coverage process ended at once. Run by hand
  with the same ceiling, the runner's JVM ran out of heap.

  Run by hand ten times at the JVM's default heap, as the measurement runs
  them, the nine tests passed nine times; once, one of them failed. They
  limit each call to 2 seconds.

  In all 215 suites on which PIT finished, the methods it kept are those the
  measurement ran.
- **Analysis.** It ran on this output. After the fix below, the paired set has
  115 subjects and the complete set 102.
- **Durations.**
  - Generation took 2 hours 22 minutes, 80 of them in the two `f6` runs that
    do not finish.
  - The measurement took 2 hours 14 minutes, 80 of them in the same two
    subjects.
  - The mutation measurement of both arms took 7 hours 18 minutes, 4 hours of
    them in the eight runs that did not finish.

**The fault the check found, and the fix.** On the faulty revision of
`commons-lang-ae85262f0`, the developers' tests exhaust the JVM's heap, as the
fourth campaign recorded. The runner dies without writing its report.
`f6`'s acceptance ran a suite one class at a time only when it ran out of
time. Here it found nothing to leave out, and the run had no suite. In the
campaign, that would lose the kind of test `f6` asks for. On 25 November,
before any run with the model, the scripts were changed:

- In `bin/generate-campaign6.sh`, `f6`'s rule for a suite that does not finish
  also covers a run that ends the runner without its report ("Acceptance in
  `f6`", above). Each run at acceptance starts with the previous run's report
  removed.
- In `bin/measure-campaign6.sh`, a left-out class whose run ends without a
  report is recorded as `NO_REPORT`. It counts as not finishing, but it does
  not give the note `timeout`, since `m6`'s verdict on the same event has
  none (sensitivity analysis 4). The new counting was tried on made-up reports.
- In `bin/mutation-campaign6.sh`, the note of a suite on which PIT stops no
  longer quotes a line that names a left-out test. In `19b59ffdd`, the name
  of such a test holds the word "Exception", and that line had been taken for
  PIT's error.

The same commands were then run again with the changed scripts. Each skips
what already has a status, a verdict or a mutation row. So they made only
`f6`'s run of `ae85262f0`, and, after its row was removed, `f6`'s mutation
measurement of `19b59ffdd`:

- The `ae85262f0` suite ended without a report. So did its one class, run on
  its own, which was left out as a whole.
- Its 162 methods fail again on the faulty revision, where the class does not
  finish. On the fix 161 pass. One, `testLang1593`, is skipped, as in the
  `m6` stand-in, and is a false alarm by the rule above.
- `ae85262f0`'s detection is `Fail` with no note. It has no certification
  verdict and no mutation score.
- The note for `19b59ffdd` now names PIT's error.

Nothing else changed in the verdicts or the mutation figures. No other run of
the check had ended without the runner's report, at acceptance or among the
left-out runs, so no other result depends on the change.

**The first trial**, on 25 November 2026, ran the scripts on two subjects in
both arms:

- `commons-csv-b5940a642`: `f6` detects through the trigger test, and `m6`
  through the same test.
- `commons-lang-184c9e832`, with each run limited to 5 minutes: `f6`'s split
  left its class out as a whole. Its detection is `Fail` with the note
  `timeout`, through 17 methods. It has no certification verdict and no
  mutation score.

It also tried what the full check could not:

- **A suite whose every test fails**, written by a stand-in for the CLI. It was
  kept with both of its tests left out. Its detection is `Pass` with two false
  alarms, and it has no certification verdict and no mutation score.
- **The analysis on made-up verdicts**, which reached each of the three
  outcomes of the decision rule. Sensitivity analysis 6 was tried both with a
  detecting test named and with none.
- **The audit**, on the fifth campaign's pilot transcripts. Its output is that
  of the fifth campaign's script.
- **`m6`'s prompt**, which is `m5`'s, byte for byte.

## Pilot

The pilot was four runs with the model, made on 25 November 2026 with the
user's agreement. It used the third campaign's two pilot subjects,
`commons-lang-6c4269eb8` (`WordUtils`) and `commons-csv-ab3d7236`
(`CSVPrinter`), each in both arms. The generator was this campaign's, at
commit `13ce63a`, after the checks above and their fix. The subjects' records
were the third campaign's (`../campaign3/pilot/subjects/`). This campaign's
scripts then audited the runs and measured them and their mutation score. The
record is in `pilot/`, with the audit's output in `pilot/audit.txt`. It is not
part of any result.

The two faults are these. In `WordUtils.containsAllWords`, the pattern that
looks for each word does not match across a line break; the fix adds
`Pattern.DOTALL`. In `CSVPrinter.printComment`, each comment line ends with
`println()`, which also writes the format's trailing delimiter; the fix ends
it with the record separator alone.

- **Runs.** All four ended normally on `claude-sonnet-5`, CLI 2.1.316. They
  ran from 20:41 to 20:51 UTC and cost $1.56 at list prices; the fifth
  campaign's pilot cost $1.43. In `f6` they took 21 turns (`commons-lang`) and
  15 (`commons-csv`); in `m6`, 15 and 18.
- **Commands.** Each agent read its working copy and wrote its test class and
  nothing else. It ran the class through `_tools/test.sh`. The transcripts
  show no network command and no path outside the working copy. The sandbox
  denied nothing.
  - In `f6` on `commons-lang`, the harness refused two calls, each because it
    needed an approval that nobody can give. One was a `python3 -c` and the
    other a shell computation. Both worked out lengths and positions in a
    string for a test of `wrap`.
  - In `f6` on `commons-csv`, the agent ran `git status`, which found no
    repository: the working copy has no history.
- **Audit.** It flagged that one `git status`, which received nothing and is
  not a violation. No run names the fix.
- **Closing messages.** The two `f6` messages, read before anything was
  measured:
  - On `commons-lang`, no test was named as showing a bug. The agent wrote
    that four of its tests had failed along the way, and that in each case it
    had found the test, not the code, to be wrong. It tested
    `containsAllWords`, but not across a line break.
  - On `commons-csv`, two tests were named as showing bugs. One was that
    `getRecordCount()` counts the header that the constructor prints. The
    other was that `printRecords(Iterable)` prints simple objects one record
    each. Neither is the fault, so the one line of `pilot/closing-f6.txt`
    reads `other`.
- **Temporary directory.** No command named the run's own temporary
  directory. At the end it held only the CLI's empty directories
  (`.tmp.tar.xz`).
- **Measurement.** Acceptance left out no test in three suites: 56 and 53
  methods on `commons-lang` in `f6` and `m6`, and 38 on `commons-csv` in `m6`.
  In `f6` on `commons-csv` it left out the two tests the agent named, of 35.
  Both fail again on the faulty revision, and both fail on the fix commit as
  well, so they are false alarms. No suite detects the fault and none
  certifies it: all four are `Pass`, as in the earlier campaigns' pilots. The
  verdicts check the pipeline and nothing else.
- **Mutation.** PIT gave each suite a figure on its own revision. It kept the
  methods the measurement ran, and left out the two that acceptance left out.
- **The records** were searched for the machine's name, its time zone, its
  operating system and details of the account, with the transcripts and
  archives unpacked. None of these is in them. The CLI's first event in each
  transcript lists the same built-in plugins and agents as in the fifth
  campaign's pilot.

The third campaign chose its pilot on classes that no subject had under test.
Here, as in the fourth and fifth campaigns, two subjects do:
`commons-lang-184c9e832` (`WordUtils`) and `commons-csv-09e27ffdb`
(`CSVPrinter`). The pilot's record is under the user's home, which no agent
can read.

## Deviations

None.

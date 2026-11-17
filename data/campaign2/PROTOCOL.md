# Second campaign: protocol

Fixed on 17 November 2026, before any run on the sample. The commit that adds
this file, with the scripts as they are in it, is the reference. Anything done
differently afterwards is a deviation and is listed at the end, with its date
and reason, before the step it affects.

## Why a second campaign

The first campaign compared two arms on 40 Defects4J bugs and found real-fault
detection at 72% with the implementation visible and 14% without it. An audit
of that campaign found that its implementation-visible arm was told more than
the implementation: the working copy carried Defects4J's own files, which name
the bug and its trigger tests, and in at least 11 of the arm's 26 detections
the agent shows it knew one or the other (`../README.md`, "What those controls
do not close"). Nothing the prompts forbade was enforced, no transcript was
kept, the runs shared the operator's profile, the model was named by an alias,
and the two arms differed in their instructions and in how a suite was
accepted.

This campaign repeats the comparison with those closed. It is the primary
result. The first campaign's arms are kept as separate conditions and are
never pooled with it.

## What is fixed

| | |
|---|---|
| Subjects | the 40 bugs of `data/sample.txt`, unchanged |
| Arms | `m2`, implementation-visible; `s2`, specification-only; as built by `bin/generate-suites.sh` |
| Model | `claude-sonnet-5`, named by id |
| Agent | Claude Code 2.1.316, run from its versioned binary with self-update off; no effort flag, so the CLI's default |
| Limits per run | 50 turns, $5 at list prices |
| Runs | one per bug and arm, 80 in all |
| Order | bugs in the order of the sample; both arms of a bug before the next bug; `m2` first for the 1st, 3rd, 5th … bug and `s2` first for the 2nd, 4th, 6th …; one agent at a time (`bin/run-campaign2.sh`) |
| Prompts | as written in `bin/generate-suites.sh`; the prompt of each run is kept |
| Acceptance | the same for both arms: the suite is compiled in the real checkout and each test that fails on the fixed revision is disabled |
| Measurement | Defects4J `v3.0.1-7-g8c16da82`, Java 11, `bin/analyze-agent-suites.sh` and `bin/merge-agent-metrics.py`, as in the first campaign |

What the agent is given, what is enforced and what is recorded are in the
header of `bin/generate-suites.sh`.

**A run is final.** It is made again in two cases only. One: a usage limit of
the plan ended it before it produced a result (the generator's `dead` state);
its record is kept under `cut-short/` and its tests are not used. Two: the
harness failed before the agent was started (checkout, compilation,
javadoc); the fix is a deviation and is recorded. A run that completes is not
repeated, whatever it produced: no test file, tests that do not compile, a
suite that ends on its turn or cost limit.

**No interim look.** Nothing is measured until every one of the 80 runs has a
status.

## Procedure

Each step is committed before the next begins, so that the history shows the
order.

1. **Generation.** `./bin/run-campaign2.sh`. It stops when the plan's usage
   reaches the generator's threshold and is run again after the limit resets.
2. **Audit.** `./bin/audit-transcripts.py data/campaign2 -v > data/campaign2/audit.txt`.
   Every flagged command is read with its result, and the runs with a
   violation (defined below) are listed in `data/campaign2/violations.txt`, one
   per line: arm, bug, reason. The file is committed even if it is empty.
3. **Measurement.**
   `OUT=data/campaign2/results NO_MUTATION="Gson-14 Gson-16" ./bin/analyze-agent-suites.sh data/campaign2/suites`.
   The two Gson bugs are measured for detection and coverage and kept out of
   the mutation step: Major rejects the class they modify, as it did in the
   first campaign.
4. **Analysis.** `./bin/analyze-campaign2.py > data/campaign2/analysis.txt`.

One contingency is fixed in advance. If a suite of this campaign cannot be
loaded on a Cli revision for the reason five EvoSuite suites could not
(`NoClassDefFoundError: org/hamcrest/SelfDescribing`), it is measured through
the same one-line correction of Defects4J (`bin/remeasure-cli-evosuite.sh`),
and the merged file marks the row.

## Outcomes

- **Primary: real-fault detection.** A suite detects the fault when
  `run_bug_detection.pl` classifies it `Fail`: it passes on the fixed revision
  and at least one of its tests fails on the buggy one.
- **Secondary.** Mutation score, as mutants killed (`FAIL`, `TIME`, `EXC` in
  Major's `kill.csv`) over mutants generated, pooled over the suites of an
  arm; line coverage, pooled; the share of tests disabled at acceptance;
  turns and list-price cost.

Sets:

- **paired**: bugs with a verdict, `Pass` or `Fail`, in both arms;
- **complete**: paired bugs that also have a mutation score and a
  line-coverage figure in both arms. Gson-14 and Gson-16 cannot be in it.

## Hypotheses, tests and decision rule

All in `bin/analyze-campaign2.py`, committed with this file.

**H1. The arms differ in detection.** Exact McNemar test, two-sided, on the
paired set, at α = 0.05.

**H2. Detection falls further than mutation score does.** This is the claim of
the paper's title. It is assessed only if H1 is rejected with `m2` above `s2`;
the sequence is fixed, so no correction is applied. On the complete set, for
detection rate *D*, pooled mutation score *M* and pooled line coverage *C*:

    fall(X) = 1 − X(s2) / X(m2)

The statistic is fall(*D*) − fall(*M*). Its 95% interval is a percentile
bootstrap over bugs: 10,000 resamples of the complete set with replacement,
the two arms of a bug kept together, Python's `random.Random(20261117)`,
bounds at the 250th and 9,750th of the sorted values. A resample in which `m2`
detects nothing has no fall(*D*); such resamples are left out, counted, and
the bounds taken at the same quantiles of the rest. H2 is supported if the
lower bound is above zero. The same interval for fall(*D*) − fall(*C*) is
reported as a secondary result.

**What follows from each outcome:**

| Outcome | What the write-up says |
|---|---|
| H1 rejected with `m2` above `s2`, and H2's lower bound above zero | Detection falls further than mutation score: the title's claim stands, on a comparison without the leaks |
| H1 rejected with `m2` above `s2`, H2's interval includes zero | The arms differ in detection, but the fall is not shown to exceed that of mutation score: the title's claim is withdrawn |
| H1 not rejected, or rejected with `s2` above `m2` | The effect of the first campaign is not supported once the leaks are closed, and the write-up reports that |

The first campaign's figures are reported in every case, as what a standard
Defects4J checkout produces.

## Exclusions

Fixed here, and none depends on a result.

- **No verdict.** A bug whose suite in either arm is `Broken`, or which has no
  suite because the run produced none that compiles, is outside the paired
  set. It is listed with its reason.
- **Violation.** A run is left out of the primary analysis, as if it had
  produced no suite, when its transcript shows a command that did one of
  these: received data from the network; read a file outside the working copy
  that is not part of the operating system or the JDK; or, in `s2`, ran code
  from `lib/`, printed, unpacked or disassembled what is in it, or gave the
  compiler an option that executes code. A command the sandbox refused is not
  a violation. A command's own private `/tmp` is not outside the working copy
  in this sense. Violations are decided at step 2, before anything is
  measured.

A run in which the agent shows it knows the bug, by naming the benchmark, the
issue behind the bug or one of its trigger tests, is not excluded. Knowledge
that comes from training data is part of what is being measured. Such runs are
counted, and analysed separately below.

## Sensitivity analyses

Reported with the primary analysis; none is confirmatory.

1. Runs with a violation included.
2. Intention to treat: every bug attempted in both arms counts, runs with a
   violation as measured, and a bug without a suite or without a verdict
   counts as not detected.
3. Runs that show knowledge of the bug left out.
4. Mutation score as the mean over suites, next to the pooled figure.

## Descriptive comparisons

None is a test of this protocol.

- **The first campaign's arms beside the second's**, bug by bug: its M arm
  against `m2`, its S arm against `s2`. The campaigns differ in more than the
  benchmark's metadata (prompts, acceptance, isolation, CLI version, date), so
  the difference between the M arms is an upper bound on what the metadata
  accounts for, not a measurement of it.
- **EvoSuite beside both arms**, on the bugs where all three have a verdict.
- Figures per project.

## What this campaign does not control

- **Training data.** Defects4J is public. The agent may recall a bug or its
  tests without being told which bug it has, and the source may cue that.
- **The implementation's own text.** The source under test and the developer
  tests that stay are not edited. In Lang-65 the repaired code delimits its
  own repair with comments that cite the issue.
- **The specification is the fixed revision's.** The javadoc `s2` reads is
  generated from the repaired source and may document the repair.
- **One run per bug and arm.** Variation between runs is not estimated.
- **One model, one agent, 40 bugs from four projects.**
- **The prompts are not identical.** They differ in what an arm requires:
  where the classes and tests are, what there is in place of the source, and,
  in `s2`, to work from the documentation and not to run or inspect the
  compiled classes.
- **Enforcement in `s2` is not complete.** The JDK's launchers other than
  `javac`, `unzip`, `python` and `perl` are hidden; other general-purpose
  tools are not. The transcript audit is what covers the rest.

## Pilot

Three runs were made on 17 November 2026 on Defects4J bugs outside the sample
(Lang-61, Csv-11, Cli-5), to exercise the harness without seeing a result on
the sample. Their record is in `pilot/` and is not part of any result.

After the pilot, and before this protocol was fixed, the scripts changed in
these ways: the CLI's usage-limit events are dropped from the kept
transcripts; the generator stops before a run a usage limit would cut short,
and keeps the record of one that was; the CLI is run from its versioned binary
with self-update off; each run records the commit it was made from, and the
generator refuses to run from scripts that differ from it; and the measurement
script can keep named bugs out of the mutation step. None changes what an
agent is given, apart from one more variable in its shell's environment
(`DISABLE_AUTOUPDATER`). No run on the sample had been made.

## Deviations

None.

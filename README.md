# Mutation Score Understates Oracle Provenance

Agent-generated test suites on Defects4J and on post-cutoff faults, with and
without the implementation.

Evaluations of automated test generation on Defects4J generate a suite against
the **fixed** revision of a bug and then check it against the buggy one. For a
language-model agent that is not neutral: the agent reads the code it is
writing tests for, and on the fixed revision that code already contains the
repair.

This repository holds the data and scripts for measuring how much of an
agent's apparent fault-detection ability that accounts for, and what the
metrics usually reported alongside it can see.

## Result

Two suites per bug from the same agent and model, under two conditions: the
agent either works in the project's source tree or sees only its javadoc. The
comparison was run twice on the same 40 Defects4J bugs, and twice more on
faults fixed after the model's training data ends: 28 in a third campaign and
115 in a fourth. A fifth campaign showed the agent the faulty revision of the
fourth campaign's 115 faults.

**The second campaign is the controlled one.** Its working copies hold nothing
of the benchmark's own, a sandbox enforces the conditions, every run's
transcript is kept and audited, and the hypotheses, tests and exclusions were
fixed before the first run (`data/campaign2/PROTOCOL.md`).

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | **22/39 — 56%** | 54% | 84% |
| specification-only | **7/39 — 18%** | 39% | 70% |

Detection is over the 39 bugs with a verdict in both arms: 16 faults are
detected by the first arm alone and one by the second alone (exact McNemar,
*p* = 2.7 × 10⁻⁴). Mutation score and coverage are over the 36 of those bugs
that have every measurement in both arms. On those 36, **detection loses 65%
of its value, mutation score 28% and line coverage 16%.** The gap between the
first two losses is 37 points, with a 95% bootstrap interval of 12 to 59. That
is the pre-specified test of the claim in the title.

**The first campaign used Defects4J checkouts as they come.**

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | 26/36 — 72% | 58% | 85% |
| specification-only | 5/36 — 14% | 44% | 73% |
| EvoSuite (baseline) | 15/35 — 43% | 47% | 85% |

Such a checkout tells the agent more than the code does: Defects4J's own files
name the bug and the tests that expose it. Without them the
implementation-visible arm detects 20 of the 36 bugs it had detected 26 of.
And where the first campaign only told the specification-only agent not to
inspect the compiled classes, the second stopped it: 22 of 40 agents tried.

EvoSuite's row is over the suites that have each measurement: 36 for mutation,
35 for detection and 35 for coverage. Beside the second campaign's arms, on
the 35 bugs where all three have a detection verdict, the rates are 57%, 43%
and 20% and the mutation scores 54%, 47% and 39%.

**The third campaign is on faults the model cannot have seen.** The second
campaign's conditions, on 28 fix commits of Commons Lang, Commons CSV and
Commons CLI from January to September 2026, with its test and exclusions also
fixed before the first run (`data/campaign3/PROTOCOL.md`). Mutation score and
coverage were measured afterwards with PIT, as that protocol provides.

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | 8/23 — 35% | 57% | 78% |
| specification-only | 5/23 — 22% | 52% | 72% |

Over the 23 subjects with a verdict in both arms and no excluded run, three
faults are detected by the first arm alone and none by the second alone (exact
McNemar, *p* = 0.25). **The pre-specified test does not reject.** The
difference is 13 points, with a 95% bootstrap interval of 0 to 26: the
direction of the Defects4J campaigns, in a corpus too small to show more.
There detection loses 37.5% of its value and mutation score 8.6%. The gap
between the two losses is 29 points, with an interval of −7 to 67 that
includes zero, a secondary result on a corpus not sized for it.

**The fourth campaign is on 115 more of them.** It uses the same conditions,
on fix commits from a pool counted afterwards from the three projects' 2026
histories. They are not matched by fault type, and the sandbox was tightened
after the third campaign's audit. Its protocol (`data/campaign4/PROTOCOL.md`)
makes the claim in the title one of its hypotheses.

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | **21/112 — 19%** | 44% | 62% |
| specification-only | **3/112 — 3%** | 50% | 68% |

Detection is over the 112 subjects with a verdict in both arms. Nineteen
faults are detected by the first arm alone and one by the second alone (exact
McNemar, *p* = 4.0 × 10⁻⁵). The difference is 16 points, with an interval of 9
to 23. Mutation score and coverage are over the 109 of those subjects in
whose fixed classes PIT makes a mutant.

**There detection loses 84% of its value, and mutation score none: pooled,
it is higher in the arm that detects less.** The gap between the two losses is
99 points, with an interval of 74 to 121, so by the test the protocol fixed
the claim in the title holds on these faults.

The pooled figure leans on eight subjects whose fix is in `StringUtils`.
They hold a third of the mutants, and the specification-only suites cover
them more widely. As means over suites the scores are 62% and 56%, in the
usual order. Both arms detect far less than on Defects4J.

**The fifth campaign shows the agent the faulty code.** It runs on the fourth
campaign's 115 subjects, with two arms:

- one implementation-visible arm works on the parent of the fix commit, and
  its suite is accepted there;
- the fourth campaign's implementation-visible arm is run again beside it, on
  the fix.

A suite written against the faulty revision that fails on the fix *certifies*
the fault. The protocol is `data/campaign5/PROTOCOL.md`.

| arm | fault certified or detected | mutation score | line coverage |
|---|---|---|---|
| reads the faulty code | **7/115 — 6% certified** | 42% | 60% |
| reads the repaired code | **26/115 — 23% detected** | 41% | 59% |

The two arms split the 115 subjects like this:

- four are certified by the first arm and detected by the second;
- three are certified only;
- 22 are detected only.

The exact McNemar test gives *p* = 1.6 × 10⁻⁴, and the difference is −16.5
points, with an interval of −24.3 to −8.7. **The sign of the effect follows
the revision the agent reads, but its size does not.** Shown the faulty code,
the agent locks the fault in about a quarter as often as it detects the fault
from the repair. Of the 35 omissions, it certifies none, where the other arm
detects ten.

Mutation score cannot tell the arms apart: pooled over the 112 subjects with a
figure, it is 42% and 41%. Run twice on the same subjects, the arm that reads
the repaired code changes its verdict on 15 of the 115.

During the runs, a package installation changed the machine's Java. The 111
runs still to come failed before their agent started, and were made again, as
the protocol provides for such failures. Its Deviations section records what
happened.

Mutation score and coverage measure how much of a program a suite exercises
and how hard it checks what it exercises. Neither measures where the expected
values came from.

## What is here

| path | what |
|---|---|
| `PREPRINT.md` | the write-up: method, results, threats, related work |
| `data/README.md` | the method record, including deviations, tooling failures and corrections |
| `CITATION.cff` | how to cite the work. `.zenodo.json`, which Zenodo reads when it archives a release, is written from it by `bin/zenodo-metadata.py` |
| `data/agent-metrics-final.csv` | per-suite detection, mutation and coverage of the first campaign and of EvoSuite; the second campaign's are in `data/campaign2/results/agent-metrics.csv` |
| `data/fault-taxonomy.csv` | hand classification of the 40 Defects4J faults |
| `data/memorisation-grades.csv`, `data/memorisation-readings.csv` | what the model recalls about each fault with no code in context: the mechanical screen and the hand readings |
| `data/agent-notes/` | the notes three generation runs of the first campaign wrote to the agent's persistent memory, that campaign's only first-hand record of what an agent read |
| `bin/run-agent-suites.sh` | generation, first campaign, implementation-visible arm |
| `bin/run-spec-suites.sh` | generation, first campaign, specification-only arm (sandbox construction included) |
| `data/campaign2/PROTOCOL.md` | the protocol of the second campaign, fixed before any run on the sample: design, hypotheses, tests, exclusions |
| `data/campaign2/` | that campaign's record: every run's transcript, prompt and settings, the packaged suites, the audit and the list of violations, Defects4J's tables and logs, and the analysis as printed |
| `bin/generate-suites.sh`, `bin/run-campaign2.sh` | generation for that campaign, both arms, with the agent isolated from the benchmark, the network and the operator's profile |
| `bin/audit-transcripts.py` | reads that campaign's transcripts for anything the protocol forbids |
| `bin/analyze-campaign2.py` | the analysis the protocol fixes |
| `bin/describe-campaign2.py` | descriptive figures of that campaign, written after the runs |
| `bin/analyze-agent-suites.sh` | measurement, wrapping Defects4J's own scripts |
| `bin/merge-agent-metrics.py` | merges Defects4J's tables and recomputes the mutation columns from Major's output |
| `bin/remeasure-cli-evosuite.sh` | measures five EvoSuite suites again with one path in Defects4J corrected |
| `bin/report-figures.py` | recomputes most of the figures of §3 of the write-up from `data/` |
| `bin/audit-trigger-leaks.py` | what the generated suites and run records give away about what the agent knew |

Post-cutoff replication corpora, their mining scripts and their results are
under `data/postcutoff*`, `data/matched-*`, `bin/mine-postcutoff.sh`,
`bin/run-postcutoff.sh`, `bin/tally-postcutoff.py`,
`bin/revalidate-postcutoff.sh`, `bin/count-postcutoff-pool.py` and
`bin/classify-postcutoff-pool.py`.

The third campaign, which makes the comparison on those post-cutoff subjects
under the second campaign's conditions, is under `data/campaign3/`: its
protocol (`PROTOCOL.md`), its pilot (`pilot/`), every run's transcript, prompt
and settings, the suites as written, the audit with the lists of violations
and of direct compiler calls, the measurement's logs and verdicts, and the
analysis as printed. Its scripts are `bin/generate-postcutoff.sh`,
`bin/run-campaign3.sh`, `bin/audit-campaign3.py`, `bin/measure-campaign3.sh`,
`bin/analyze-campaign3.py`, `bin/campaign3-lib.sh` and
`bin/AgentTestRunner.java`, all committed before its runs, and
`bin/describe-campaign3.py`, written after them. Its suites' mutation score
and coverage were measured afterwards, as its protocol provides, by
`bin/mutation-campaign3.sh` with `bin/ExcludedTestsFilter.java`, and analysed
by `bin/analyze-mutation-campaign3.py`; their output is in
`data/campaign3/mutation/` and `data/campaign3/mutation-analysis.txt`.

`bin/agent-sandbox.py`, written after the third campaign, holds sandbox
settings for any later run, which give each run a temporary directory of its
own and hide the operating system's jars, and a check of them that calls no
model. Its output under those settings and under the two campaigns' is in
`data/sandbox/`. `bin/probe-saved-copies.py`, written after the fourth
campaign, checks in the same way how far the one exception those settings leave
reaches: the Read tool on the copy the CLI saves of a run's long output. It
reaches no further than the run's own session; the output is in
`data/sandbox/` too.

The fourth campaign is under `data/campaign4/`. It makes the comparison on 115
of the pool's post-cutoff subjects, not matched by fault type, under those
settings. The directory holds its protocol (`PROTOCOL.md`), fixed before any
run on the subjects, the subjects and their records, the sandbox probe, the
pilot (`pilot/`), the records of its 230 runs (`runs-m4/`, `runs-s4/`,
`suites/`), their audit (`audit.txt`, `violations.txt`, `direct-javac.txt`),
the measurement of detection (`results/`), that of mutation score and line
coverage (`mutation/`), and the analysis (`analysis.txt`). Its scripts are
`bin/subjects-campaign4.py`, `bin/generate-campaign4.sh`,
`bin/run-campaign4.sh`, `bin/audit-campaign4.py`, `bin/measure-campaign4.sh`,
`bin/mutation-campaign4.sh` and `bin/analyze-campaign4.py`, all committed with
its protocol, and `bin/describe-campaign4.py`, written after the analysis.
They use the third campaign's `bin/campaign3-lib.sh`,
`bin/AgentTestRunner.java` and `bin/ExcludedTestsFilter.java` unchanged.

The fifth campaign is under `data/campaign5/`. It uses the fourth campaign's
115 subjects. One implementation-visible arm is shown the faulty revision, the
parent of the fix commit. The fourth campaign's implementation-visible arm is
run again beside it, on the fix commit. A suite written against the faulty
revision that fails on the fix certifies the fault. The campaign measures how
often that happens, and whether it happens as often as the other arm detects
the fault. The directory holds:

- its protocol (`PROTOCOL.md`), fixed before any run on the subjects, with the
  deviation recorded during the runs;
- the subject list;
- the output of the two sandbox checks, before the pilot and before the runs;
- the pilot (`pilot/`);
- the records of its 230 runs (`runs-b5/`, `runs-m5/`, `suites/`), with the
  first attempts the harness failed (`harness-failed/`);
- their audit (`audit.txt`, `violations.txt`, `closing-b5.txt`);
- the measurement (`results/`), mutation score and line coverage
  (`mutation/`), and the analysis (`analysis.txt`).

Its scripts are `bin/subjects-campaign5.py`, `bin/generate-campaign5.sh`,
`bin/run-campaign5.sh`, `bin/audit-campaign5.py`, `bin/measure-campaign5.sh`,
`bin/mutation-campaign5.sh` and `bin/analyze-campaign5.py`, all committed with
its protocol, and `bin/describe-campaign5.py`, written after the analysis.
They use `bin/campaign3-lib.sh`, `bin/AgentTestRunner.java`,
`bin/ExcludedTestsFilter.java` and `bin/agent-sandbox.py` unchanged.

## What this does not show

Several things, recorded here because they are easy to over-read from the
table above:

- **The implementation-visible figure is an upper bound, not a capability.**
  The agent reads the repaired code, so a test written for current behaviour
  catches the fault by construction. That the regression evaluation setting
  flatters generated suites is not a new observation — Dinella et al. state it
  in 2022; what is measured here is the magnitude, and how little of it the
  usual metrics show.
- **In the first campaign the implementation-visible arm was told more than
  the implementation.** A Defects4J checkout carries Defects4J's own metadata,
  which names the bug and its trigger tests, and that was not removed. In 11
  of the arm's 26 detections the suite or the agent's closing message shows it
  knew one or the other, and one of the eleven is the developer's own test,
  copied from a backup the checkout leaves in the tree. The second campaign
  removes all of it and the arm detects six fewer of 36 bugs. The campaigns
  differ in other ways too, reasoning effort and prompts among them, so six
  is an upper bound on what the metadata added, not a measurement of it.
- **The second campaign is the same forty bugs.** Its analysis was fixed
  before its runs, with the first campaign's results already known. It shows
  that the effect survives control on new runs. It does not show that it holds
  on new faults. There is one run per bug and arm in each campaign.
- **On new faults the effect rests on one campaign.** The third campaign's
  test does not reject: 8/23 against 5/23, *p* = 0.25, three discordant pairs
  where the test needed six. The fourth's does, on 112 subjects.
  - Its difference, 16 points, is close to the third's 13.
  - It is 22 points narrower than the second campaign's, with an interval that
    excludes zero. The corpora differ in project, kind of fault and build as
    well as in date, so the narrower gap cannot be put down to recall, and
    recall cannot be excluded as a part of the Defects4J figure.
  - That the fixes postdate the training data rests on one check, of five
    issue identifiers. And only the fix is new: the code around it may be in
    the training data.
- **The fourth campaign's H2 depends on how mutants are pooled.** Pooled,
  mutation score rises from the implementation-visible arm to the
  specification-only one. As means over suites it falls by a tenth, and the
  implementation-visible arm is ahead in 80 of 109 subjects. Either way it
  falls far less than detection does. But the size of the pre-specified
  statistic, 99 points, comes from the pooling.
- **The fourth campaign's subjects are not matched to the Defects4J sample by
  fault type.** Weighted to it, detection is 16.0% against 3.6%.
- **The faulty-revision condition measures tests written to pass.** The fifth
  campaign's agent is asked to make its tests pass on the code it reads, and
  acceptance drops any that fail there. So it measures how often tests written
  after faulty code lock the fault in. It does not measure how well an agent
  finds faults when asked to. One of its seven certifications rests on
  behaviours the fix changed besides the fault.
- **Verdicts vary between runs.** Each campaign has one run per subject and
  arm. The fifth campaign ran the fourth's implementation-visible arm again on
  the same 115 subjects, and 15 verdicts changed (agreement 87%, κ 0.60). The
  between-arm differences the tests rest on are larger than that. But no
  single verdict should be read as a property of its subject.
- **The sandbox was less tight than its settings were meant to make it.** The
  third campaign's audit found that the directory the harness gives commands
  for temporary files is the host's own and shared by every run, in that
  campaign and in the second, and that during the third it also held the
  developers' tests for each fix. The transcripts, which record every command
  and result, show no agent in either campaign listing that directory or
  reading anything there that it had not just written. Five runs of the third
  campaign did read back their own files there, or the harness's saved copy of
  their own output; the exclusion rule as written leaves them out, and the
  result is the same with them in (9/27 against 6/27, *p* = 0.25). A check made
  after the campaign, with its settings and no model, confirmed that a command
  could list and read that directory. Settings that close it are in
  `bin/agent-sandbox.py`, and the fourth and fifth campaigns ran under them.
  Neither campaign's audit found a violation.
- **Contamination is measured, not bounded.** A direct probe finds two of the
  forty faults recalled with their mechanism and two more recognised, and
  benchmark identifiers not memorised. But recall may be cued by the source
  rather than spontaneous, and the probe withholds the source. The second
  campaign's transcripts show no agent naming a bug, which is not the same as
  no agent recalling one.
- **The earlier runs on the post-cutoff corpora were not controlled.** Two
  corpora were mined. In their first runs the first has no valid
  specification-only result: a harness error recorded seven failed licence
  audits as seven detections. The second, matched on fault type, gave 8/13
  against 4/13, *p* = 0.125. Those runs had the fix commit within the agent's
  reach and kept no transcript. On the 19 subjects where both have a verdict,
  their implementation-visible arm detected 13 and the third campaign's
  detects 7.
- **What the specification-only arm detects is only described.** Of its five
  detections in the first campaign, three are documented-contract violations
  and two are not, a classification made knowing the outcome. In the second
  campaign it detects seven faults, one of which the other arm misses.

## Reproducing

`./bin/report-figures.py` recomputes most of the figures of §3 of the write-up
from `data/`. The evidence of §3.9 is printed by `./bin/audit-trigger-leaks.py`,
the classification of §3.3 is recorded in `data/contract-violation.md`, and
some other figures are quoted from records under `data/`, as the script's
header describes. What the transcript audits found is in the `audit.txt` and
`violations.txt` of `data/campaign2/` to `data/campaign5/`. None of it needs
Defects4J or model access. `./bin/analyze-campaign2.py` to
`./bin/analyze-campaign5.py` print the second to fifth campaigns' analyses on
their own, and
`./bin/analyze-mutation-campaign3.py` the third campaign's mutation figures.
No Python script under `bin/` needs a package outside the standard library
except `bin/zenodo-metadata.py`, which reads `CITATION.cff` with PyYAML.

Re-measuring from the packaged suites in `data/agent-suites/` and
`data/campaign2/suites/` needs Defects4J v3.0.1 under Java 11 with
`TZ=America/Los_Angeles` (`bin/analyze-agent-suites.sh`). The post-cutoff
corpora and the third to fifth campaigns' suites (`bin/measure-campaign3.sh`
to `bin/measure-campaign5.sh`) need clones of the upstream repositories, Java
11 and Maven 3.9+. Their mutation score (`bin/mutation-campaign3.sh` to
`bin/mutation-campaign5.sh`) also needs PIT, which each script fetches from
Maven Central once and checks against the hashes written in it.
Regenerating the suites needs the model and costs between $0.40 and $1 per
suite at list prices.

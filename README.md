# Mutation Score Understates Oracle Provenance

Agent-generated test suites on Defects4J, with and without the implementation.

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
comparison was run twice on the same 40 Defects4J bugs.

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
*p* = 2.8 × 10⁻⁴). Mutation score and coverage are over the 36 of those bugs
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

Mutation score and coverage measure how much of a program a suite exercises
and how hard it checks what it exercises. Neither measures where the expected
values came from.

## What is here

| path | what |
|---|---|
| `PREPRINT.md` | the write-up: method, results, threats, related work |
| `data/README.md` | the method record, including deviations, tooling failures and corrections |
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
| `bin/report-figures.py` | recomputes every figure in §3 of the write-up from `data/` |
| `bin/audit-trigger-leaks.py` | what the generated suites and run records give away about what the agent knew |

Post-cutoff replication corpora, their mining scripts and their results are
under `data/postcutoff*`, `data/matched-*`, `bin/mine-postcutoff.sh`,
`bin/run-postcutoff.sh` and `bin/tally-postcutoff.py`.

A third campaign, which will make the comparison on those post-cutoff
subjects under the second campaign's conditions, is prepared and has not been
run: its protocol is `data/campaign3/PROTOCOL.md`, its pilot is under
`data/campaign3/pilot/`, and its scripts are `bin/generate-postcutoff.sh`,
`bin/run-campaign3.sh`, `bin/audit-campaign3.py`, `bin/measure-campaign3.sh`,
`bin/analyze-campaign3.py`, `bin/campaign3-lib.sh` and
`bin/AgentTestRunner.java`.

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
- **Contamination is measured, not bounded.** A direct probe finds two of the
  forty faults recalled with their mechanism and two more recognised, and
  benchmark identifiers not memorised. But recall may be cued by the source
  rather than spontaneous, and the probe withholds the source. The second
  campaign's transcripts show no agent naming a bug, which is not the same as
  no agent recalling one.
- **The replication did not settle it.** Two post-cutoff corpora were mined.
  The first has no valid specification-only result: a harness error recorded
  seven failed licence audits as seven detections. The second, matched on fault
  type, gives 8/13 against 4/13 — the same direction, a gap of 31 points
  against 38 in the second campaign and 58 in the first, and *p* = 0.125 on 13
  pairs: too few to distinguish a smaller effect from no power.
- **What the specification-only arm detects is only described.** Of its five
  detections in the first campaign, three are documented-contract violations
  and two are not, a classification made knowing the outcome. In the second
  campaign it detects seven faults, one of which the other arm misses.

## Reproducing

`./bin/report-figures.py` recomputes every figure in the write-up from `data/`
and needs neither Defects4J nor model access. `./bin/analyze-campaign2.py`
prints the second campaign's analysis on its own.

Re-measuring from the packaged suites in `data/agent-suites/` and
`data/campaign2/suites/` needs Defects4J v3.0.1 under Java 11 with
`TZ=America/Los_Angeles` (`bin/analyze-agent-suites.sh`); the post-cutoff
corpora need Maven 3.9+. Regenerating the suites needs the model and costs
between $0.40 and $1 per suite at list prices.

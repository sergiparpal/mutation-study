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
agent either works inside the checked-out project or sees only its javadoc.
Over the 36 Defects4J bugs measured in both arms:

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | **26/36 — 72%** | 58% | 85% |
| specification-only | **5/36 — 14%** | 44% | 73% |
| EvoSuite (baseline) | 15/35 — 43% | 47% | 85% |

Detection differs five-fold. The S arm's detections are a strict subset of the
M arm's — 21 discordant pairs in one direction, none in the other (exact
McNemar, *p* = 9.5 × 10⁻⁷). **Mutation score and coverage move the same way,
but by factors of 1.3 and 1.2.**

EvoSuite's row is over the suites that have each measurement: 36 for mutation,
35 for detection and 35 for coverage. On the 34 bugs where all three generators
have a detection verdict the rates are 71%, 15% and 41%, and the mutation
scores 58%, 44% and 47%. EvoSuite and the specification-only suites are nearly
tied on mutation score and differ nearly three-fold in detection.

Mutation score and coverage measure how much of a program a suite exercises
and how hard it checks what it exercises. Neither measures where the expected
values came from.

## What is here

| path | what |
|---|---|
| `PREPRINT.md` | the write-up: method, results, threats, related work |
| `data/README.md` | the method record, including deviations, tooling failures and corrections |
| `data/agent-metrics-final.csv` | per-suite detection, mutation and coverage |
| `data/fault-taxonomy.csv` | hand classification of the 40 Defects4J faults |
| `data/memorisation-grades.csv`, `data/memorisation-readings.csv` | what the model recalls about each fault with no code in context: the mechanical screen and the hand readings |
| `data/agent-notes/` | the notes three generation runs wrote to the agent's persistent memory, the only first-hand record of what an agent read |
| `bin/run-agent-suites.sh` | generation, implementation-visible arm |
| `bin/run-spec-suites.sh` | generation, specification-only arm (sandbox construction included) |
| `bin/generate-suites.sh` | generation for a second campaign, both arms, with the agent isolated from the benchmark, the network and the operator's profile; not yet run on the sample |
| `bin/audit-transcripts.py` | reads that campaign's transcripts for anything the protocol forbids |
| `bin/analyze-agent-suites.sh` | measurement, wrapping Defects4J's own scripts |
| `bin/merge-agent-metrics.py` | merges Defects4J's tables and recomputes the mutation columns from Major's output |
| `bin/remeasure-cli-evosuite.sh` | measures five EvoSuite suites again with one path in Defects4J corrected |
| `bin/report-figures.py` | recomputes every figure in §3 of the write-up from `data/` |
| `bin/audit-trigger-leaks.py` | what the generated suites and run records give away about what the agent knew |

Post-cutoff replication corpora, their mining scripts and their results are
under `data/postcutoff*`, `data/matched-*`, `bin/mine-postcutoff.sh`,
`bin/run-postcutoff.sh` and `bin/tally-postcutoff.py`.

## What this does not show

Several things, recorded here because they are easy to over-read from the
table above:

- **The 72% is an upper bound, not a capability.** The agent reads the repaired
  code, so a test written for current behaviour catches the fault by
  construction. That the regression evaluation setting flatters generated
  suites is not a new observation — Dinella et al. state it in 2022; what is
  measured here is the magnitude, and how little of it the usual metrics show.
- **The implementation-visible arm was told more than the implementation.** A
  Defects4J checkout carries Defects4J's own metadata, which names the bug and
  its trigger tests, and that was not removed. In 11 of the arm's 26 detections
  the suite or the agent's closing message shows it knew one or the other, and
  one of the eleven is the developer's own test, copied from a backup the
  checkout leaves in the tree. How much of the 72% that accounts for cannot be
  said.
- **Contamination is measured, not bounded.** A direct probe finds two of the
  forty faults recalled with their mechanism and two more recognised, and
  benchmark identifiers not memorised. But recall may be cued by the source
  rather than spontaneous, the probe withholds the source, and in the
  implementation-visible arm the cue was stronger than the source alone.
- **The replication did not settle it.** Two post-cutoff corpora were mined.
  The first has no valid specification-only result: a harness error recorded
  seven failed licence audits as seven detections. The second, matched on fault
  type, gives 8/13 against 4/13 — the same direction and the same subset
  relation, a gap of 31 points rather than 58, and *p* = 0.125 on 13 pairs: too
  few to distinguish a smaller effect from no power.
- **What the specification-only arm detects is only described.** Of its five
  detections, three are documented-contract violations and two are not. The
  classification was made knowing the outcome.

## Reproducing

`./bin/report-figures.py` recomputes every figure in the write-up from `data/`
and needs neither Defects4J nor model access.

Re-measuring from the packaged suites in `data/agent-suites/` needs Defects4J
v3.0.1 under Java 11 with `TZ=America/Los_Angeles`
(`bin/analyze-agent-suites.sh`); the post-cutoff corpora need Maven 3.9+.
Regenerating the suites needs the model and costs roughly $1 per suite.

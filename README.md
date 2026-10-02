# Oracle Provenance Is Invisible to Mutation Score

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

Two suites per bug from the same agent, model and instructions, varying only
whether the agent could read the implementation. Over the 36 Defects4J bugs
measured in both arms:

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | **26/36 — 72%** | 72% | 85% |
| specification-only | **5/36 — 14%** | 70% | 73% |
| EvoSuite (baseline) | 12/35 — 34% | 59% | 85% |

Detection differs five-fold. **Mutation score does not register it.** The S
arm's detections are a strict subset of the M arm's — 21 discordant pairs in
one direction, none in the other (exact McNemar, *p* = 9.5 × 10⁻⁷).

Ranked by mutation score the three populations are 72%, 70%, 59%; ranked by
fault detection they are 72%, 14%, 34%. The middle two swap, and the
population with the higher mutation score detects less than half as many
faults.

Mutation score measures the strength of a suite's assertions. It does not
measure where those assertions' expected values came from, and provenance
leaves no trace in execution.

## What is here

| path | what |
|---|---|
| `PREPRINT.md` | the write-up: method, results, threats, related work |
| `data/README.md` | the full method record, including every deviation and tooling failure |
| `data/agent-metrics-final.csv` | per-suite detection, mutation and coverage |
| `data/fault-taxonomy.csv` | hand classification of the 40 Defects4J faults |
| `data/memorisation-grades.csv` | what the model recalls about each fault with no code in context |
| `bin/run-agent-suites.sh` | generation, implementation-visible arm |
| `bin/run-spec-suites.sh` | generation, specification-only arm (sandbox construction included) |
| `bin/analyze-agent-suites.sh` | measurement, wrapping Defects4J's own scripts |

Post-cutoff replication corpora, their mining scripts and their results are
under `data/postcutoff*`, `data/matched-*` and `bin/mine-postcutoff.sh`.

## What this does not show

Several things, recorded here because they are easy to over-read from the
table above:

- **The 72% is an upper bound, not a capability.** The agent reads the repaired
  code, so a test written for current behaviour catches the fault by
  construction. That the regression evaluation setting flatters generated
  suites is not a new observation — Dinella et al. state it in 2022; what is
  measured here is the magnitude, and that the usual metrics are blind to it.
- **Contamination is bounded, not eliminated.** A direct probe finds one of the
  forty faults genuinely recalled, and benchmark identifiers not memorised at
  all. But recall may be cued by the source rather than spontaneous, and the
  probe withholds the source.
- **The replication did not settle it.** Two post-cutoff corpora were mined.
  The first was dominated by extreme-value faults, an artefact of the selection
  criteria. The second, matched on fault type, narrowed the gap to 21 points
  and lost significance (*p* = 0.375) on 14 pairs — too few to distinguish a
  smaller effect from no power.
- **What the specification-only arm detects is uncharacterised.** Its five
  detections do not share a property we could identify; two are
  documented-contract violations and three are not.

## Reproducing

Defects4J v3.0.1 under Java 11, `TZ=America/Los_Angeles`, Maven 3.9+ for the
post-cutoff corpora. Generation costs roughly $0.90 per suite. Measurement
needs no model access: `bin/analyze-agent-suites.sh` runs over the packaged
suites in `data/agent-suites/`.

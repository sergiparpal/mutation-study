# Matched post-cutoff corpus — pre-registered quotas

Written before any candidate was examined. **The quotas below are fixed.**
A category that fills is closed: later candidates of that type are discarded
even if they look like better subjects.

## Why

The first post-cutoff corpus (§3.8) was selected with criteria — small,
ticket-tracked, fix-and-test in one commit — that filtered toward
extreme-value faults, the class the specification-only arm catches without
needing a specification. The result confounded date with fault composition.

This corpus fixes composition to match the Defects4J sample, so that date is
the only thing that varies.

## Target distribution

Scaled from the 40-bug Defects4J sample (21 OMISSION, 7 ALGORITHM,
5 SUBSTITUTION, 4 STATE, 3 MISSING_CLAUSE, 1 API) to 20 subjects:

| fault_type | Defects4J | share | quota |
|---|---|---|---|
| OMISSION | 21 | 52.5% | 10 |
| ALGORITHM | 7 | 17.5% | 4 |
| SUBSTITUTION | 5 | 12.5% | 3 |
| STATE | 4 | 10.0% | 2 |
| MISSING_CLAUSE | 3 | 7.5% | 1 |
| API | 1 | 2.5% | 0 |
| **total** | **40** | | **20** |

API rounds to zero at this sample size. Recorded so the omission is visible
rather than silent.

## Window and exclusions (added before classification began)

**Window: 2026-01-01 to 2026-09-22.** Verified post-cutoff by probing the model
with five issue identifiers from the earliest part of the window
(LANG-1806, 1811, 1814, 1817, 1818); all five were disclaimed. Note this
probes the identifier cue only; the location cue (§2.8, probe B) was not
run for this corpus.

**Excluded: systematic audit campaigns.** Two are visible in the candidate
pool and are excluded as a population, not case by case:

- Commits suffixed `(fNNN)` — 23 of them, a maintainer's own audit sweep.
  Many are performance or resource-exhaustion hardening rather than
  correctness faults ("O(width^2) padding", "cache grows without bound"),
  and several are explicitly documented-contract violations, the class the
  specification-only arm catches. Neither resembles a user-reported defect.
- A `readObject` invariant-validation sweep across six classes (CharRange,
  EventListenerSupport, FluentBitSet, FastDateParser, Fraction, Range), and
  a supplementary-character sweep. Both are one fault repeated; filling the
  OMISSION quota from them would yield ten copies of a single case rather
  than ten faults.

The residual pool after both exclusions is 259 candidates.

**Also excluded: performance-only changes.** A commit that leaves observable
behaviour unchanged and improves only time or space complexity is not a fault
subject, since no test can distinguish the two revisions by result. Defects4J
contains no such subjects.

**Thematic sweeps count once.** Where a maintainer works through one concern
across several classes in a short window — mutable TimeZone defensive copies,
reflective accessibility on non-public classes — the first candidate is taken
and the rest are rejected. The faults are not independent observations even
when the code differs.

## Protocol

1. **Mine without the biasing filters.** No size cap, no ticket requirement.
   The only structural requirement is that the commit changes both
   `src/main/java` and `src/test/java`, since a subject needs a trigger test.
2. **Classify blind.** Label each candidate from its production diff under the
   Study A rules, *before* knowing whether it validates fail-to-pass. Knowing
   that a subject works must not influence what it is called.
3. **Fill in order of appearance.** Walk candidates newest-first and assign
   each to its category until that category's quota is met. Discard the rest.
4. **Validate afterwards.** Run fail-to-pass on the selected 20. A subject that
   fails validation is replaced by the next candidate of the same category, not
   by whatever is convenient.

## Classification rules

Identical to the Defects4J sample, reproduced here so there is no drift:

- `OMISSION` — the fix **adds** lines without modifying existing ones: a diff
  of `+n/-0`, or where removed lines are pure context (code re-indented or
  re-wrapped around the addition). A guard prepended with a ternary, leaving
  the original expression verbatim inside it, also counts.
- `MISSING_CLAUSE` — an existing condition gained a clause.
- `SUBSTITUTION` — wrong operator, value or variable.
- `ALGORITHM` — the approach itself is replaced; the fix rewrites rather than
  extends.
- `STATE` — ordering, lifecycle, concurrency, object identity or ownership.
- `API` — incorrect use of another API, or the wrong exception.

## Expected difficulty

`OMISSION` is the binding constraint. Addition-only fixes tend to be larger,
and larger test changes are more likely to hit the compilation problem that
cost three subjects in the first corpus: removing a developer test file breaks
other test classes that call its static helpers. Expect to examine many
candidates per accepted `OMISSION` subject.

## Log

Candidates examined, in order, with their assigned category and the reason for
acceptance or rejection, go in `data/matched-candidates.csv`. The log is the
evidence that quotas were filled by appearance order and not by convenience.

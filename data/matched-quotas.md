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

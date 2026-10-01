## Deviation: this classification is not blind

**Recorded 2026-10-01, before classification was completed.**

The protocol above requires classifying `contract_violated` without seeing
which subjects the specification-only arm detected. That requirement was not
met and cannot now be met.

The hypothesis was formed by examining the five Defects4J faults the
specification-only arm caught and noticing what they had in common. Both the
author and the assistant used throughout this work had those five subjects in
mind while reading the javadoc. There is no version of this classification,
performed by either of us on this sample, that is blind to the outcome.

### What this costs

A variable fitted to an outcome cannot then be used to explain that outcome.
The following claim is therefore **not** supported by this classification:

> The specification-only arm's detection rate is a function of how much of the
> fault's behaviour is documented, and the matched post-cutoff corpus narrowed
> the gap because Commons in 2026 documents more of its contracts.

That is the claim the classification was designed to test, and it remains
untested.

### What survives

The classification is **descriptive**, not predictive. It can support:

> Of the faults the specification-only arm detected, N of M are cases where the
> javadoc of the modified method states the behaviour the fault violates. Of
> those it missed, K of L are not.

stated as an observation about this sample, with the non-blindness declared
alongside it. It characterises a pattern. It does not establish that the
pattern is the cause.

### What would test it

A corpus classified for `contract_violated` **before** either arm is run, by
someone who has not seen any detection results. The classification is cheap —
it needs only the buggy revision's javadoc and the fix diff — so the cost is
not the labour but the discipline: the subjects must be classified and the
judgements committed before generation begins.

This is left for future work and is reported as a limitation, not as a result.

### A separate error this exposed

Section 3.3 of the paper states that four of the five faults detected by the
specification-only arm are cases where the implementation contradicts a
documented contract, and names Csv-4, Csv-6, Gson-15 and Lang-13.

**That claim was written without reading any javadoc.** It was inferred from
the fault descriptions. On reading the actual documentation at the buggy
revision, at least two of the four do not support it:

- `CSVRecord.putIn` — "Puts all values of this record into the given Map."
  Nothing about a record holding fewer values than the header map.
- `CSVParser.getHeaderMap` — "Returns a copy of the header map that iterates in
  column order." Nothing about the no-header case or a null return.

Section 3.3 must be corrected regardless of what happens with this
classification.

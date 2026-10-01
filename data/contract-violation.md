# Contract violation: a second classification of the Defects4J sample

Written after the matched post-cutoff corpus narrowed the arms' gap from 58 to
21 percentage points, to test an explanation for that narrowing.

## The question

`fault_type` classifies the *shape of the fix* — what the diff adds, removes or
rewrites. It turned out not to predict what the specification-only arm detects.

Within OMISSION alone:

| | Defects4J (19) | matched post-cutoff (8) |
|---|---|---|
| implementation-visible | 16/19 (84%) | 6/8 (75%) |
| specification-only | 3/19 (16%) | 4/8 (50%) |
| gap | 68 pp | 25 pp |

The implementation-visible arm holds steady. The specification-only arm triples
inside the same fault category. So the narrowing is not explained by having
lost the discriminating categories to compilation failures — something else
separates these omissions from those ones.

The candidate, from §3.3 of the paper: the specification-only arm detects
faults where the implementation **contradicts a documented contract**, and
little else. Four of its five Defects4J detections were of that shape, and the
post-cutoff omissions it catches read the same way — a javadoc promising `null`
for out-of-range input where the code threw; a documented accessibility
guarantee that was not checked.

## The variable

`contract_violated` — **yes** when the public documentation of the class or
method under test states, or directly implies, the behaviour the fault
violates, such that a reader of the javadoc alone could write an assertion that
fails on the buggy revision. **No** otherwise.

Judged from the javadoc of the *buggy* revision, not the fixed one. A fix that
also updates the documentation is common, and reading the updated text would
make every fault look documented.

Borderline guidance, fixed before classifying:

- A class-level statement counts ("null inputs are no-ops", "this class is
  immutable"). The contract need not be on the method itself.
- An `@throws` or `@return` clause that the code does not honour is a yes.
- "The method is named `isNumber`, so obviously it should…" is a **no**. The
  name is not documentation.
- Absent logic with no corresponding promise is a no, even when the omission
  is obvious in hindsight — Lang-65's missing truncation block, where only a
  marker comment in the source hinted at it, is a no: source comments are not
  public documentation and the specification-only arm never saw them.
- Where the javadoc is silent but the method overrides an interface with a
  documented contract (`equals`/`hashCode`, `Iterator`, `Comparable`), that
  inherited contract counts as a yes.

## Protocol

1. For each of the 36 Defects4J subjects measured in both arms, read the
   javadoc of the modified class and method **at the buggy revision**.
2. Record `yes` or `no` with the specific sentence relied on, so the judgement
   is auditable.
3. Classify **blind to the detection outcome.** Do not look at
   `agent-metrics-final.csv` while classifying. This is the whole point: the
   variable must not be fitted to the result it is meant to predict.
4. Only then cross with detection.

The third rule matters more here than anywhere else in this project. The
hypothesis was formed by looking at which faults the specification-only arm
caught, so classifying with the outcomes visible would confirm it by
construction.

## What the result would mean

If the specification-only arm's detection tracks `contract_violated` and the
implementation-visible arm's does not, then the gap between the arms is a
function of how much of a codebase's behaviour is documented — not of the date,
the fault's syntactic shape, or the model's training data. The matched corpus
narrowed because Commons in 2026 documents more of its contracts than Commons
in 2008 did.

If it does not track, the narrowing is unexplained and the candidate
explanations left are contamination and something not yet identified.

## Log

`data/contract-violation.csv`: `bug_id,contract_violated,evidence`
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

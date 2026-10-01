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

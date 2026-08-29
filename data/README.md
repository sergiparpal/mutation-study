# Study data

## Source

Defects4J v3.0.1, Java 11, `TZ=America/Los_Angeles`.

## Sample (`sample.txt`)

40 bugs across 4 projects, drawn with deterministic random selection:

```bash
defects4j bids -p Lang | shuf -n 12 --random-source=<(yes) | sed 's/^/Lang,/'
for p in Csv Gson Cli; do
  n=$([ $p = Cli ] && echo 8 || echo 10)
  defects4j bids -p $p | shuf -n $n --random-source=<(yes) | sed "s/^/$p,/"
done
```

Breakdown: Lang 12, Csv 10, Gson 10, Cli 8.

**The sample was fixed before classification began.** No bugs are added or
removed afterwards.

### Representativeness caveats

For Lang, this is a random sample of 61 active bugs. For Csv and Gson, the
total bug count per project is small, so 10 approaches a census — results for
those projects describe the project itself, not a wider population.

Observations within a project are also not fully independent. Three of the
twelve Lang bugs fall in `NumberUtils`; three of the ten Csv bugs fall in
`CSVFormat`/`CSVParser`, and two of those (Csv-7, Csv-8) address the same
requirement — duplicate header names must be rejected — failing by different
routes. Treat per-project counts as weaker evidence than the raw n suggests.

## Pilot

Lang-1 and Lang-3 were examined **before** the sample was fixed, and generated
the working hypothesis (predominance of omission faults). They are marked
`phase=pilot` and **excluded from analysis**, even if they were to reappear in
the sample by chance.

## Taxonomy (`fault-taxonomy.csv`)

### `fault_type`

| Value | Definition |
|---|---|
| `SUBSTITUTION` | wrong operator, value or variable |
| `OMISSION` | missing logic: a condition, a branch, a loop |
| `MISSING_CLAUSE` | the condition existed but was missing a clause |
| `ALGORITHM` | the whole approach is wrong; the fix rewrites it |
| `STATE` | ordering, lifecycle, concurrency |
| `API` | incorrect use of another API, or wrong exception |
| `UNCLEAR` | to be reviewed at the end |

#### Rule: `OMISSION` requires an addition-only fix

`OMISSION` applies only when the fix **adds** lines without modifying existing
ones — a diff of `+n/-0`, or where the removed lines are pure context
(unchanged code re-indented or re-wrapped around the addition).

If the fix both adds and rewrites existing logic, it is not `OMISSION`. Use
`MISSING_CLAUSE` when an existing condition gained a clause, or `ALGORITHM`
when the approach itself was replaced.

Rationale: with one category likely to dominate this sample, `OMISSION` is at
risk of becoming the default bucket for anything that roughly fits. The
`+n/-0` test is mechanical and leaves no room for drift.

*(Note: Lang-1 is recorded as `OMISSION` at `+9/-2` and would not satisfy this
rule. It is pilot data and excluded from analysis, so it was left as-is.)*

*(Limitation: the `+n/-0` test is sensitive to how the guard is written. An
`if` wrapper leaves the original line untouched (`+n/-0`); a ternary rewrites
it (`+1/-1`), despite being the same kind of fault. Csv-4 is such a case,
classified `OMISSION` with the original expression preserved verbatim inside
the new ternary. Flagged for final review.)*

#### Rule: one row per Defects4J bug, even when it bundles several faults

Some Defects4J bugs contain more than one distinct fault, because the fix
commit addressed several at once. One row is still recorded, classified by the
dominant category, with the individual faults enumerated in `note`.

Known cases:

- **Lang-62** — three faults in one fix: a missing `0xFFFF` range guard
  (appearing twice), a missing `break` causing switch fall-through, and an
  empty `catch` leaving a stale value. All three are omissions, so the
  category is unambiguous.
- **Lang-36** — a condition gained a clause (`&& lastChar != '.'`) and a
  separate validation block was added in `isNumber`. Same root cause, so
  classified `MISSING_CLAUSE` on the dominant fault.
- **Lang-65** — a 30-line truncation block absent between existing marker
  comments, plus two minor missing guards. Classified on the dominant fault.

If bundled bugs become frequent, a `sub_faults` count column may be worth
adding. Not added on the strength of three cases.

### `nearby_mutant`

`YES` when at least one arithmetic, relational or logical operator, or one
literal constant, appears in the lines the fix modifies or in lines immediately
adjacent. In other words: would a classical mutation operator have somewhere to
anchor within the faulty region?

Not to be confused with "does a mutant reproduce the bug?" — that is a stricter
question and is almost always `NO`.

Bugs classified `NO` are the mutation-sterile regions tracked in `IDEAS.md`;
the running count is maintained there, not here.

*(Limitation: `nearby_mutant` presupposes the classical operator catalogue —
arithmetic, relational, logical, literals. A region judged sterile may not be
sterile under a wider catalogue: Cli-28 (`break` where `continue` belonged) has
no anchor under this definition, but a control-flow operator would find one.
The definition is kept unchanged for the whole sample; the dependency on the
assumed catalogue belongs in the conclusions.)*

## Classification protocol

1. Only the diff over `dir.src.classes` between buggy and fixed versions is
   examined.
2. **Trigger tests are not consulted** during classification: they reveal where
   the fault lies and bias the judgement on `nearby_mutant`.
3. `UNCLEAR` entries are reviewed as a batch at the end.
4. Once finished, the first 10 entries are re-read under the final criteria,
   since criteria drift over the course of classification.

## Status

- [x] Sample fixed
- [ ] Classification (19/40)
- [ ] Review of unclear entries and of the first 10

# Ideas and open questions

Parking lot for detector ideas and hypotheses that surface while classifying
faults. **Nothing here is a finding.** Entries are recorded with the bug that
prompted them so their provenance stays visible.

Two kinds of content live here and must not be confused:

- **Measured** — tool output, reproducible by re-running a script.
- **Judged** — read off diffs by hand. Everything below the measured section.

The distinction earned its keep repeatedly. Every hypothesis in this file that
was formed from two or three bugs and later measured across the sample turned
out to be wrong: the sterile-region count, the dominance of statement deletion,
and the EXC/FAIL kill split were all refuted by their own measurement.

## Bias warning

These ideas are generated *from* the 40-bug sample. They cannot be validated on
that same sample — doing so confirms a hypothesis with the data that produced
it, the same problem the pilot exclusion exists to avoid. Anything promoted from
this file needs a fresh set of bugs (another project, or GitBug-Java).

---

## The headline refutation: mutation score does not detect the mirror

**This is the result of Study B and it undercuts the premise most entries below
are built on.** Two arms, same 40 bugs, same model, one variable — whether the
agent could read the implementation:

| arm | real fault detected | mutation score | line coverage |
|---|---|---|---|
| implementation-visible | **26/36 (72%)** | 72% | 85% |
| spec-only (javadoc) | **5/36 (14%)** | **71%** | 72% |

Detection differs five-fold. **Mutation score is indistinguishable.** Coverage
drops far less than detection does.

A suite that catches three real faults in four and a suite that catches one in
seven look the same under mutation analysis, and nearly the same under
coverage. Whatever separates a test grounded in the contract from one grounded
in the current code, mutation testing does not measure it — because both suites
genuinely discriminate behaviour. What differs is the *origin of the oracle*,
and no execution-based metric sees that.

Consequence for every detector idea below: if the idea's mechanism is "run
mutants and see what survives", it inherits this blind spot. The ideas that
look at *documented intent* (announced-but-absent code, comment–code
divergence) are unaffected, because they never relied on execution.

The only mechanism shown to separate the two is the contrafactual itself:
generate the suite twice, with and without the implementation, and compare.
Expensive — it doubles the cost — but measured to work.

---

## Measured with Major

Tool output, not judgement. Produced by `bin/run-mutation.sh` and
`bin/analyze-mutation.py`; raw artifacts in `data/raw/`.

### Answered: statement deletion is enabled by default

`defects4j mutation -h` lists the default operator set: **AOR, LOR, SOR, COR,
ROR, ORU, LVR, STD**. Statement deletion is on by default, and by default only
the classes modified by the fix are mutated.

### Refuted: STD does not dominate coupled mutants

> **⚠ An earlier version of this entry claimed the opposite.** On Lang-13,
> 9 of the 14 coupled mutants were STD deletions of lines the fix adds, which
> suggested that *mutation catches omission faults by deleting the repair* — a
> mechanism only available once the missing code exists.
>
> Measured across 36 bugs, that does not hold. Operators generating coupled
> mutants: **ROR 234, LVR 208, COR 205, STD 137, AOR 135.** STD is the least
> frequent, not the dominant one. Lang-13 and Lang-56 were small cases that
> suggested a pattern that is not there.

### Refuted: coupled mutants mostly die by assertion, not by crashing

> **⚠ An earlier version of this entry claimed the opposite.** Measured on the
> first two bugs, only 5 of 80 coupled mutants died by assertion; the rest died
> by exception or timeout. That suggested a high mutation score demonstrates
> code fragility rather than test strength, and that an agent given mutation
> feedback would learn to provoke exceptions.
>
> Across 36 bugs with `-r`: **FAIL 520, EXC 377, TIME 22 — 56% die by
> assertion.** The early figure came from two bugs measured before the flaky-
> test workaround, and did not survive the sample.

The FAIL/EXC/TIME split is still worth reporting alongside any mutation score —
it is nearly free and no existing tool does it — but it is not the indictment
it first appeared to be.

### Measurement caveats that did hold

- **"Coupled" is a superset unless restricted by method.** It means "killed by
  a trigger test run in isolation". That test also kills mutants unrelated to
  the fault: Lang-43's single-line fix yields 85 coupled mutants, of which 1 is
  on a fix line. Restricting to the methods the fix touches cuts 2150 down to
  919 — **an unrestricted coupling measure overestimates by ~2.3x.** Worth
  reporting on its own as a methodological point.
- **Flaky tests abort the full run.** Lang-56 failed on
  `StopWatchTest::testStopWatchSplit`, a wall-clock test unrelated to the bug.
  `defects4j mutation -r` is the workaround, at the cost of redefining "full
  suite" as "relevant tests".

---

## Structural blind spot: mutation-sterile regions

> **⚠ Refuted as stated (2026-08-29).** `nearby_mutant` was judged by reading
> diffs, not measured. Major generates mutants in Lang-13's faulty region (two
> LVR on the `false` argument of `Class.forName`), so at least one listed case
> is not sterile. The definition missed boolean, null and string literals,
> which are pervasive in object-oriented code.
>
> The counts below — and the 17/40 in the final tally — cannot be used until
> remeasured with `bin/run-mutation.sh`. Kept for provenance only.

### Sterile faulty regions — from Lang-13, Csv-3, Csv-4, Csv-5, Csv-6 and others

Judged sterile: regions containing no arithmetic, relational or logical
operators and no literal constants. Classical mutation was thought to have
nothing to anchor to, not merely nothing that reproduces the fault.

Shapes observed:

- **Call-chain code** (Lang-13, Csv-4, Csv-5, Csv-6, Gson-6) — only method
  calls, assignments and field accesses.
- **Unconditioned branches** (Csv-3, Gson-16) — a bare `switch` default or a
  `while (true)`, with no condition to mutate.
- **Object construction** (Gson-14, Gson-3) — dispatch on `instanceof` and
  `isAssignableFrom`, no values compared.
- **Reference identity** (Csv-16, Cli-10) — the fault is in what object is
  returned or shared, not in any expression.

The underlying intuition may survive remeasurement in weakened form: the
project gradient (Lang 25%, Csv 40%, Gson 60%, Cli 50%) tracked how much
arithmetic each codebase contains, which is at least a coherent story. But it
is a story about a variable that turned out to be miscalibrated.

### Mutation score can reward incorrect logic — from Csv-14/Csv-15, Gson-4, Gson-15, Cli-32

Csv-14 replaced alphanumeric character ranges with RFC 4180 hex ranges in
`printAndQuote`. Csv-15 removed that condition entirely: it turned out to be
over-aggressive, quoting values that needed no quoting.

The intermediate state — the one Csv-14 produced — is the most densely mutable
expression in the sample: four `<`, four `>`, three `&&`, two `||`, six
literals. Killing those mutants requires tests that pin the behaviour of a
condition that was itself wrong, and those tests would then have blocked the
Csv-15 fix.

Gson-4 is the same shape in another project. Gson forbade top-level JSON values
outside lenient mode — a rule from an obsolete version of the specification,
since RFC 7159 permits any value as a document root. The fix deletes the
restriction from reader and writer, removing a parameter from `beforeValue` and
touching eight call sites. The removed guard (`!lenient && !root`) is mutable;
killing its mutants requires tests enforcing the wrong specification.

Gson-15 is the same root cause as Gson-4: `NaN`/`Infinity` rejected regardless
of lenient mode. Cli-32 removed a loop that scanned past the requested width.

**Four of the forty bugs are fixes that delete incorrect logic.** In all four,
mutation would have raised the score while defending the fault. This is the
Goodhart risk observed in the corpus, not argued from theory — and it points
the same way as the Study B result at the top of this file.

### A mutant that fixes the bug — from Cli-32

Cli-32's removed loop had `pos <= text.length()` with `text.charAt(pos)` inside
— an off-by-one throwing `StringIndexOutOfBoundsException`. The ROR mutant
`<=` → `<` **repairs** it.

Such a mutant can never be killed by a test that passes on the original: the
original is the one that fails. It is not equivalent, and it is not a test gap.
It is a fault reported inside out.

Any witness-based design has to handle this case explicitly: a distinguishing
input exists, but it exonerates the mutant and indicts the original.

---

## Measured in Study B: what the spec arm can and cannot see

### The five faults a spec-only suite does catch

Of 36 paired bugs, the spec arm detected Cli-32, Csv-4, Csv-6, Gson-15 and
Lang-13. Four of the five are cases where the code contradicts a contract the
javadoc states:

- **Csv-4** — missing null guard on a documented return value.
- **Csv-6** — unchecked index into an array.
- **Gson-15** — `NaN`/`Infinity` rejected regardless of the documented lenient
  mode.
- **Lang-13** — primitive classes failing a documented deserialization
  contract.

The spec arm catches faults visible from the specification and essentially
nothing else. This is the positive version of the announced-but-absent and
comment–code-divergence ideas below: those faults really are findable from
documented intent alone, and an agent finds them without being told to look.

### Javadoc quality is enough, and measurably varies

Prune rate — tests written blind that turned out to disagree with the
implementation — was **59 of 1806 (3%)**, with a gradient:

```
Lang   ~0%    Commons javadoc is unusually explicit
Csv    ~2%
Gson   ~6%    reflection and generics, sparser documentation
```

This retires the hypothesis that writing from the API alone would mostly be
guesswork. It also suggests javadoc density is measurable and matters, which
may be worth a variable of its own if this is replicated.

---

## Mutation operators worth adding

### Related-constant substitution — from Lang-21

Swap a library constant for a semantically adjacent one from the same family:
`Calendar.HOUR` ↔ `HOUR_OF_DAY`, `DAY_OF_MONTH` ↔ `DAY_OF_YEAR`,
`TimeUnit.SECONDS` ↔ `MILLISECONDS`, `RoundingMode.HALF_UP` ↔ `HALF_EVEN`.

Classical operators mutate syntax and cannot know these are interchangeable in
form but different in meaning. An LLM knows the families trivially, and the
resulting mutants would reproduce this bug exactly rather than merely anchoring
near it.

Cheap to build, and the candidate families can be mined from the JDK itself.

### Control-flow keyword substitution — from Cli-28, Cli-17

Swap `break` ↔ `continue`, `return` ↔ `break`; insert or delete a `break`.

Cli-28 is a `break` where `continue` belonged: a non-affirmative property value
aborted the whole loop instead of skipping one entry, silently dropping every
later option. Cli-17 is the mirror case — a missing `break` let a loop continue
over characters already consumed.

Unlike the absent-branch cases, this is not a conceptual limitation of
mutation: the transformation is as syntactically trivial as `<` → `<=` and
would reproduce both faults exactly. The operator is simply absent from the
standard catalogue — a catalogue gap, not a conceptual one.

Both regions were judged sterile under the operators-and-literals definition of
`nearby_mutant`. A control-flow operator would anchor in both, which is a
second reason that variable needs remeasuring.

---

## Detector ideas (non-mutation)

These do not inherit the blind spot at the top of this file: none of them
depends on execution, so none of them is fooled by a suite that discriminates
behaviour it learned from the code.

### Structural contract checks — from Lang-23

`equals`/`hashCode` never overridden despite the class carrying its own state.
Orphan javadoc present with no method beneath it.

No mutation operator can generate a missing method. A structural lint over the
AST can flag it trivially. Suggests the eventual tool should not be
mutation-only.

Same approach extends beyond `equals`/`hashCode`: for any type implementing a
known interface (`Iterable`, `Comparator`, `Comparable`), the documented
contract properties can be checked directly.

### Reference identity and ownership — from Csv-16, Cli-10

The fault lies in whether an object is shared or copied, not in any
expression. Csv-16 returned a fresh anonymous iterator on every call while all
instances shared one consumable stream, so multiple iterators silently
interfered; Cli-10 stored a reference to the caller's required-options list
and then mutated it during parsing, corrupting the caller's object.

No mutation operator has a notion of "same instance vs new instance" or
"shared vs defensively copied", which puts this class structurally out of
reach.

Possible probe, metamorphic in shape: run the same operation twice with the
same input object and check the results are identical. Aliasing bugs surface
on the second run, which is exactly what a single-invocation test never does.
Two iterators over the same source should likewise yield the same sequence.

### Announced-but-absent code — from Lang-23, Lang-65, Csv-10, Gson-8, Gson-16, Gson-5, Cli-38, Cli-15, Cli-21

Javadoc with no method beneath it; paired region markers (`START`/`END`)
enclosing nothing; a `TODO` describing work that was never done; a comment
describing an operation the code does not perform.

- **Lang-23** — orphan javadoc where `equals`/`hashCode` should have been.
- **Lang-65** — a `LANG-59 START/END` marker pair around an empty gap where 30
  lines of truncation logic belonged.
- **Csv-10** — a `TODO` debating *where* to print the header, above code that
  never printed it at all.
- **Gson-8** — complete javadoc for an `assertInstantiable` method that did not
  exist, describing the exception it was supposed to throw.
- **Gson-16** — `// cannot reduce due to infinite recursion` with no guard
  beneath it.
- **Gson-5** — a comment describing timezone padding that was never applied.
- **Cli-38** — `// check for several concatenated short options` sitting below
  an unconditional `return` that made it unreachable.
- **Cli-15** — three consecutive comments describing operations that did not
  exist.
- **Cli-21** — javadoc for two interface accessors that were not declared, plus
  `// this is a reentrant call` with no reentrancy guard.

Detectable by AST lint. Invisible to mutation, since there is no code in the
faulty region to mutate.

With comment–code divergence below, **11 of the 40 bugs (27.5%) have documented
intent diverging from implementation**, across all four projects. The most
recurrent shape in the sample, and unlike `nearby_mutant` this variable is
objective: the comment is either there or it is not.

Study B corroborates the mechanism from the other direction: the faults the
spec-only arm detected are precisely the ones where the documented contract
and the code disagree.

### Comment–code divergence — from Csv-14, Cli-12

The code exists; it contradicts the specification sitting next to it. Harder
than the announced-but-absent case.

Csv-14's comment cited the correct RFC 4180 ranges (`%x20-21 / %x23-2B /
%x2D-7E`) while the code used alphanumeric ranges. Cli-12's comment described
the `--foo=value` format above a branch that split by fixed position instead.

Not detectable by AST lint, but an LLM comparing a comment against the
statement it documents does this naturally.

### Absent branch in an exhaustive dispatch — from Lang-52, Gson-3, Gson-7

Three shapes of the same hole: a missing `case` in a `switch` (Lang-52, the `/`
escape), a missing branch in an `if/else if` type-dispatch chain (Gson-3,
`ConcurrentMap` and `ConcurrentNavigableMap`), and a constant missing from an
accepted-token condition (Gson-7, `PEEKED_UNQUOTED`).

Mutating neighbouring branches drives tests toward the cases that already
exist. Mutation is structurally incapable of pointing at the absent one — and
Gson-7 shows this is independent of whether anchors are present: its region is
dense with operators and none of them names the missing constant.

The type-dispatch variant has an external source of truth a classical operator
cannot reach but an LLM has: the `java.util` hierarchy. Knowing that
`ConcurrentNavigableMap` exists, extends `ConcurrentMap`, and must therefore
precede it in the chain is library knowledge, not syntax.

Possible probe: for each dispatch over a known type hierarchy or enumerated
domain, list what the chain does *not* handle. Requires knowing the intent, so
probably needs an LLM proposing candidate cases from the domain — escape
tables, enum coverage, character classes.

### Over-permissive default branch — from Csv-3

The mirror image of the absent case: the `default` existed and accepted
anything. `Lexer.readEscape` returned any character following a backslash as a
valid escape; the fix restricts it to meta-characters.

Both shapes are invisible to mutation, for opposite reasons — nothing to delete
in the absent case, nothing to constrain in the permissive one. Possible probe:
for each `default` branch, is the accepted input set wider than the enumerated
cases suggest it should be?

### Missing fallback in a catch block — from Lang-13

Possible probe: force each catch path to execute and check whether any test
asserts on the *result*, not merely that no exception escaped.

### Serialization round-trip — from Lang-56

Fault was invalid object state after deserialization. This is a metamorphic
relation rather than a mutant: `deserialize(serialize(x))` should be
indistinguishable from `x` at the observation boundary.

Cheap, general, and applies to any `Serializable` type without needing a spec.
Same shape applies to other round-trips (parse/format, encode/decode,
compress/decompress).

### Unchecked index into array — from Csv-6

An index derived from external data (a header mapping, a parsed field) reaches
an array access with no bound established by a comparison against `length`.

Detectable by dataflow analysis, and a natural probe for an LLM: "which array
accesses here could exceed bounds, and does any test exercise that?"

Note that the spec arm caught this one unaided: the missing bound contradicts
the documented behaviour of the accessor.

### Missing null guard on a returned value — from Csv-4, Csv-5, Gson-6

A value obtained from a getter, from a factory, or from external data is used
without checking for `null`. Three of the forty bugs. Csv-6 (unchecked array
index) is the same mechanism with a different missing check.

All three were judged mutation-sterile, and the association looked structural:
the check is what is absent, and code surrounding an unchecked `null` is
typically pure call-chain code. **That judgement is now in doubt** — see the
refutation note above.

Failure modes differ in severity: Csv-4 and Gson-6 throw NPE (a crash oracle
catches them); Csv-5 appends the literal string `"null"`, so the failure is
silent and corrupts output. The silent variant needs a test comparing full
output, which no crash oracle and no partial assertion will give you.

### Misplaced guard — from Lang-34, Csv-8

The validation exists and is correct; it runs at the wrong point. Lang-34 had a
null-guard inside the accessor instead of at the call site; Csv-8 validated
duplicate headers in `validate()` instead of in the constructor.

Operators are present in both faulty regions, but no classical operator
relocates code — mutation drives tests toward "is the guard correct?", never
toward "does the guard run early enough?".

Possible probe: for each validation, is there a reachable state where the
object is used before that validation runs?

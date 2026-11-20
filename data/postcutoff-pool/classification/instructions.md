# Fault-type classification of post-cutoff fix commits — instructions to each rater

## Task

Each file you are given holds the production-code diff (`src/main/java`) of
one commit to an Apache Commons library (Lang, CSV or CLI) against its parent.
Every commit is believed to fix one fault. Say what kind of fault, under the
rules below, which are the rules the study used for its Defects4J sample and
for its earlier post-cutoff corpus.

You see the diff only, on purpose. The protocol classifies from the production
diff alone: no commit message, no tests, no issue, no outcome. So:

- Open only this file and the diff files listed in your request.
- Do not use git, the network, a search, or any other file to identify a
  commit or to learn anything about it. Do not open the other files in the
  directory, or other raters' output.
- Judge each diff on its own. Do not try to balance the categories.

## Categories

| fault_type | definition |
|---|---|
| `SUBSTITUTION` | wrong operator, value or variable |
| `OMISSION` | missing logic: a condition, a branch, a loop |
| `MISSING_CLAUSE` | the condition existed but was missing a clause |
| `ALGORITHM` | the whole approach is wrong; the fix rewrites it rather than extends it |
| `STATE` | ordering, lifecycle, concurrency, object identity or ownership |
| `API` | incorrect use of another API, or the wrong exception |
| `UNCLEAR` | two categories fit equally after the rules below are applied; name both |

## Rules

1. **`OMISSION` requires an addition-only fix.** It applies only when the fix
   adds lines without modifying existing ones: a diff of `+n/-0`, or one whose
   removed lines are pure context (unchanged code re-indented or re-wrapped
   around the addition, such as `}` becoming `} else {`, or an `if` re-chained
   to `else if`). If the fix both adds and rewrites existing logic, it is not
   `OMISSION`: use `MISSING_CLAUSE` when an existing condition gained a clause,
   or `ALGORITHM` when the approach itself was replaced. The test is
   mechanical so that `OMISSION` does not become the default bucket.
2. **A removed line whose original expression survives verbatim inside a new
   guard counts as preserved.** A guard is a condition that chooses between
   the original behaviour and new behaviour: a ternary, an `if`/`else`, a
   `try`/`catch` around the original call. Example: `return a.b();` becomes
   `return a == null ? null : a.b();`. If every removed code line is preserved
   in this sense and the rest is addition, the fix is `OMISSION`. A line whose
   original expression is always transformed (`f(x)` becoming `f(g(x))` with
   no condition) is modified, not preserved.
3. **Count code lines only.** Whole commits carry documentation changes that
   the Defects4J sample's minimised patches do not. Javadoc, comments and
   blank lines are not counted and do not decide the category. Each file's
   header gives a mechanical count for both, with comments recognised by line
   prefix; check it against the diff and give your own count.
4. **One fault per commit.** If a commit fixes the same missing check in
   several places (overloads, two accessors, reader and writer), it is one
   fault, classified on the root cause, even if the check is written
   differently in each place. If it fixes several distinct faults, classify the
   dominant one, list the others in the note, and set the flag `BUNDLE`.
5. **Changes that are not the fix do not decide the category.** Renames,
   javadoc, refactoring, new constants or helper methods introduced for the fix
   are read as part of the fix only in so far as they carry its logic. A new
   helper method that holds the added logic counts as addition; the call site
   changed to use it is judged by rules 1 and 2.
6. **`STATE`** covers, among others: a mutable object stored or returned by
   reference where a defensive copy was needed (ownership); a derived field
   not refreshed when its input changes; operations in the wrong order;
   initialisation, serialisation and lifecycle faults; thread safety; an object
   shared where a new one was needed, or the reverse (identity).
7. **Flags**, independent of the category:
   - `NOT_A_FIX` — the diff does not look like the fix of a fault: a feature,
     a refactoring, a performance-only change with the same results, a
     documentation-only change. Still give the category the change would have
     as a fix, if any, or `UNCLEAR`.
   - `BUNDLE` — two or more independent faults (rule 4).
   Leave the flag empty otherwise. Whether a commit stays in the pool is not
   yours to decide; the flag only reports what the diff shows.
8. Use `UNCLEAR` sparingly: only when two categories fit equally after rules 1
   to 6. Give the other category in `alt`. When you choose a category but
   hesitate, also give the runner-up in `alt`.

## Reference: the Defects4J sample as classified

The forty bugs of the study's Defects4J sample, with the counts and notes
recorded for them. They were classified from Defects4J's minimised patches.
Ignore the remarks about mutants ("sterile region", "anchor"); they belong to a
retired variable. One difference with the rules above: Csv-16 is recorded as
`API`, although its fault is one of object identity, which rule 6 puts under
`STATE`. Follow the rules.

| bug | fault_type | lines | method | note |
|---|---|---|---|---|
| Lang-43 | OMISSION | +1/-0 | ExtendedMessageFormat.appendQuotedString | missing next(pos) call; parser fails to advance past escaped quote |
| Lang-13 | OMISSION | +19/-0 | SerializationUtils.ClassLoaderAwareObjectInputStream.resolveClass | no fallback for primitive type names; region has no operators or literals for a classical mutant to anchor to |
| Lang-56 | STATE | +6/-2 | FastDateFormat | non-serializable state serialized; fix marks fields transient and adds readObject to re-init after deserialization |
| Lang-23 | OMISSION | +32/-0 | ExtendedMessageFormat | equals and hashCode never overridden; orphan javadoc present without methods; nothing in the faulty region for any mutant to anchor to |
| Lang-52 | OMISSION | +4/-0 | StringEscapeUtils.escapeJavaScript | missing case for '/' in escape switch; mutation on neighbouring cases drives tests toward covered branches, never toward the absent one |
| Lang-8 | SUBSTITUTION | +1/-2 | FastDatePrinter.TimeZoneNameRule.appendTo | used construction-time zone field instead of calendar's zone; adjacent condition has operators for a mutant to anchor to |
| Lang-62 | OMISSION | +11/-0 | Entities.unescape | three omissions: missing 0xFFFF range guard (x2), missing break causing switch fall-through, empty catch leaving stale entityValue; region has literals and radix args to anchor mutants |
| Lang-65 | OMISSION | +35/-0 | DateUtils.modify | entire manual truncation block absent between existing LANG-59 marker comments; also missing MILLISECOND early return and offset!=0 guard; main faulty region is an empty gap with no code to mutate |
| Lang-63 | ALGORITHM | +3/-21 | DurationFormatUtils.formatPeriod | hardcoded days+=31 plus a reduceAndCorrect post-correction method; fix replaces both with getActualMaximum and deletes the method; literal 31 is directly mutable |
| Lang-21 | SUBSTITUTION | +1/-1 | DateUtils.isSameLocalTime | Calendar.HOUR (12h) used instead of HOUR_OF_DAY (24h); dense operators for anchoring, though classical operators do not swap related library constants |
| Lang-34 | SUBSTITUTION | +2/-2 | ToStringStyle.getRegistry | defensive emptyMap() masked null registry; fix returns null and moves the guard to isRegistered; operators present but no operator relocates a guard |
| Lang-36 | MISSING_CLAUSE | +10/-1 | NumberUtils.createNumber | condition gained && lastChar != '.'; isNumber also gained decimal-point validation block; same root cause, dense operators nearby |
| Csv-14 | SUBSTITUTION | +1/-1 | CSVFormat.printAndQuote | alphanumeric char ranges instead of RFC 4180 hex ranges; adjacent comment already stated the correct ranges; densest anchoring region in the sample |
| Csv-6 | OMISSION | +2/-0 | CSVRecord.putIn | unchecked values[col] access when record has fewer columns than header; faulty region has no operators or literals to anchor a mutant |
| Csv-8 | STATE | +6/-7 | CSVFormat.CSVFormat | duplicate-header validation moved from validate() to the constructor; object could exist in an invalid state; operators present but no operator relocates a guard |
| Csv-4 | OMISSION | +1/-1 | CSVParser.getHeaderMap | no null guard before copying headerMap; original expression preserved verbatim inside new ternary — see README note on +n/-0 limitation; region has no operators or literals |
| Csv-7 | OMISSION | +4/-0 | CSVParser.initializeHeader | duplicate header names silently overwrote earlier entries; loop bounds nearby give anchors but mutants there drive tests toward traversal, not duplicate detection; same requirement as Csv-8 |
| Csv-5 | OMISSION | +2/-0 | CSVPrinter.println | no null guard on recordSeparator; append(null) writes the literal string "null" so the failure is silent; fourth mutation-sterile region |
| Csv-3 | OMISSION | +3/-0 | Lexer.readEscape | default branch accepted any character as a valid escape; fix restricts to meta-characters and returns END_OF_STREAM otherwise; sterile region (fifth) |
| Csv-16 | API | +9/-3 | CSVParser.iterator | returned a new anonymous iterator per call over a shared consumable stream; fix returns a single named instance; fault lies in object identity, not in any expression; sterile region |
| Csv-10 | OMISSION | +3/-0 | CSVPrinter.CSVPrinter | header row never printed despite format defining one; a TODO above debated where to print it; sterile region |
| Csv-15 | ALGORITHM | +1/-3 | CSVFormat.printAndQuote | removes the RFC 4180 range condition introduced by Csv-14 as over-aggressive; densely mutable expression whose mutants would have pinned incorrect behaviour |
| Gson-14 | OMISSION | +8/-0 | $Gson$Types.subtypeOf/supertypeOf | no instanceof check before wrapping bound, producing nested wildcards; same omission in both methods; sterile region — object construction with no operators or literals |
| Gson-3 | OMISSION | +16/-1 | ConstructorConstructor.newDefaultImplementationConstructor | type-dispatch chain missing ConcurrentMap and ConcurrentNavigableMap branches; -1 line is the SortedMap condition rechained to else-if; sterile region — dispatch on isAssignableFrom, no operators or literals |
| Gson-4 | ALGORITHM | +9/-13 | JsonWriter.beforeValue/JsonReader.doPeek | removes obsolete restriction on top-level JSON values (pre-RFC 7159); drops the root parameter, touching eight call sites; mutants on the removed guard would have pinned the wrong spec |
| Gson-6 | OMISSION | +2/-0 | JsonAdapterAnnotationTypeAdapterFactory.getTypeAdapter | nullSafe() called on a possibly-null adapter from the factory; sterile region — call-chain code with no operators or literals |
| Gson-10 | OMISSION | +2/-2 | ReflectiveTypeAdapterFactory.BoundField.write | explicit @JsonAdapter overridden by unconditional runtime-type wrapper; original expression preserved verbatim as ternary else-branch — same +n/-0 limitation as Csv-4, flagged for review; sterile region |
| Gson-8 | OMISSION | +13/-0 | UnsafeAllocator.newInstance | no instantiability check before unsafe allocation of interfaces/abstract classes; javadoc for assertInstantiable already present with no method beneath; sterile region |
| Gson-16 | OMISSION | +5/-0 | $Gson$Types.resolve | no visited-set to break recursive type variable resolution; comment about infinite recursion already present with no guard beneath; sterile region — while(true) has no condition to mutate |
| Gson-5 | OMISSION | +1/-0 | ISO8601Utils.parse | abbreviated timezone offsets like +00 not padded to +0000; comment above already described the missing operation; adjacent offset += length() gives an anchor |
| Gson-7 | MISSING_CLAUSE | +10/-2 | JsonReader.nextLong/nextInt | PEEKED_UNQUOTED missing from the accepted-token condition in both methods; dense operators nearby but no mutant names a constant absent from the expression |
| Gson-15 | MISSING_CLAUSE | +1/-1 | JsonWriter.value(double) | NaN/Infinite rejected regardless of lenient mode; same root cause as Gson-4 (partial lenient implementation); mutants here would pin the over-restrictive behaviour |
| Cli-12 | OMISSION | +7/-2 | GnuParser.flatten | no branch for --foo=value; long options split by fixed position as if they were -Dprop=value; comment describing the missing format already present above the wrong branch; literal 2 anchors the faulty assumption |
| Cli-28 | SUBSTITUTION | +1/-1 | Parser.processProperties | break instead of continue aborted the whole loop, silently dropping later properties; sterile under current definition, but a control-flow operator would anchor here — see IDEAS.md |
| Cli-38 | OMISSION | +6/-1 | DefaultParser.isShortOption | concatenated short options (-abc) not recognised; comment describing the missing check sat below an unconditional return; pos == -1 and substring literals anchor nearby |
| Cli-10 | STATE | +2/-1 | Parser.setOptions | stored reference to caller's required-options list and mutated it during parsing; missing defensive copy; fault is in reference ownership, not in any expression; sterile region |
| Cli-17 | OMISSION | +1/-0 | PosixParser.burstToken | missing break after processing the remainder as a non-option; loop continued over already-consumed characters; sterile under current definition, control-flow operator would anchor — see IDEAS.md |
| Cli-32 | ALGORITHM | +1/-5 | HelpFormatter.findWrapPos | loop scanned past the requested width looking for a space, ignoring the width; also had pos <= length() with charAt(pos), an off-by-one throwing SIOOBE; densely mutable region where one mutant would have FIXED the bug |
| Cli-15 | ALGORITHM | +13/-6 | WriteableCommandLineImpl.getValues | default resolution was all-or-nothing instead of augmenting a partial list; precedence between parameter and map defaults also reworked; three orphan comments described the missing operations |
| Cli-21 | ALGORITHM | +38/-2 | WriteableCommandLineImpl.looksLikeOption | prefix match alone decided if a token was an option; fix consults the current option, adding two interface methods, a state field, a reentrancy guard and save/restore in GroupImpl; javadoc for both accessors and the reentrancy comment already present with no code beneath; sterile region |

## Output

Write a tab-separated file, with this header and one row per diff, in the order
of your list:

```
id	fault_type	alt	code_lines	preserved	flag	note
```

- `id` — the diff's id, e.g. `P001`.
- `fault_type` — one of the seven values above.
- `alt` — the runner-up category, or empty.
- `code_lines` — your count of code lines, `+a/-r`.
- `preserved` — for `OMISSION` with removed code lines: `yes` if every one is
  preserved under rules 1 and 2. Otherwise `-`.
- `flag` — `NOT_A_FIX`, `BUNDLE`, both separated by a comma, or empty.
- `note` — one sentence, at most 35 words, in English, saying what the fault
  is and why the category, in the style of the reference notes. No tabs.

Read every diff in full before classifying it, the large ones included.

# Adjudication rule — written 2026-11-19 23:15 UTC, before any rater output was read

The final fault type of a candidate is its primary rater's, except in three
cases, which the adjudicator decides by reading the same blind diff under the
same instructions:

1. the primary rater said UNCLEAR;
2. the candidate was double-rated and the two raters disagree;
3. the primary label breaks rule 1 mechanically: OMISSION with removed code
   lines that the rater did not mark as preserved.

Labels from the matched corpus (data/matched-candidates.csv) neither override
nor are overridden: they stay as recorded there, and agreement with them is
reported. Flags (NOT_A_FIX, BUNDLE) do not change eligibility; they are
reported for a decision on the screen.

# The raters' requests

Each rater was a subagent of an interactive Claude Code session (agent type
`general-purpose`, model `claude-opus-5-5`). A new agent, it did not see the
session's conversation, only the request below. All six were started on
2026-11-19 at 23:14 UTC and wrote their outputs between 23:27 and 23:37 UTC.
The requests are verbatim, except that `$S` stands
for the session's scratchpad directory,
`/tmp/claude-1000/-home-sergi-code-mutation-study/<session id>/scratchpad`.
`$S/ft/` held `instructions.md`, `blind/` and `out/` as they are in this
directory. The key, the batches and the adjudication rule were kept outside it,
in `$S/ft-key/`.

## Blind fault-type rater, batch 1

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are the 32 files P001.diff to P032.diff in $S/ft/blind/ (that is, P001, P002, ..., P032). Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/batch-1.tsv

Constraints, which are part of the method: open no file other than the instructions and your 32 diffs (nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

## Blind fault-type rater, batch 2

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are the 32 files P033.diff to P064.diff in $S/ft/blind/ (that is, P033, P034, ..., P064). Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/batch-2.tsv

Constraints, which are part of the method: open no file other than the instructions and your 32 diffs (nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

## Blind fault-type rater, batch 3

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are the 32 files P065.diff to P096.diff in $S/ft/blind/ (that is, P065, P066, ..., P096). Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/batch-3.tsv

Constraints, which are part of the method: open no file other than the instructions and your 32 diffs (nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

## Blind fault-type rater, batch 4

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are the 32 files P097.diff to P128.diff in $S/ft/blind/ (that is, P097, P098, ..., P128). Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/batch-4.tsv

Constraints, which are part of the method: open no file other than the instructions and your 32 diffs (nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

## Blind fault-type rater, batch 5

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are the 30 files P129.diff to P158.diff in $S/ft/blind/ (that is, P129, P130, ..., P158). Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/batch-5.tsv

Constraints, which are part of the method: open no file other than the instructions and your 30 diffs (nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

## Blind fault-type second rater

```
You are one of several independent raters in a blind classification of fault-fixing commits by fault type. Nobody will tell you what other raters decided, and you must not try to find out.

1. Read $S/ft/instructions.md in full. It is your whole brief: the categories, the rules, a reference table and the output format. Follow it exactly.
2. Your diffs are these 32 files in $S/ft/blind/ (each is <id>.diff): P001 P002 P019 P020 P021 P022 P024 P030 P039 P042 P043 P044 P045 P047 P054 P060 P063 P072 P084 P087 P089 P090 P093 P094 P095 P101 P105 P117 P121 P135 P147 P155. Read each one in full and classify it.
3. Write your output, the tab-separated file the instructions describe, to $S/ft/out/second.tsv

Constraints, which are part of the method: open no file other than the instructions and your 32 diffs (no other diff, nothing else under that scratchpad directory, nothing in /home/sergi/code or its data/ directories); do not run git; do not use the network or any search to identify a commit; do not read anything under ft/out/ other than the file you write. Do not change any file other than your output.

When done, reply with only: the path written, the number of rows, and the counts per fault_type and per flag.
```

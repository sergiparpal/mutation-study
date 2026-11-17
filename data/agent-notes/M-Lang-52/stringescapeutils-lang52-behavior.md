---
name: stringescapeutils-lang52-behavior
description: Actual behavior of org.apache.commons.lang.StringEscapeUtils in the Lang-52 fixed tree
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0a0259b2-1ece-47af-88f2-7c30b07145e7
  modified: 2026-09-02T08:34:48.600Z
---

Observed behavior of `StringEscapeUtils` in `/tmp/agentB_Lang_52_f` (Defects4J Lang 52, fixed):

- `escapeJava` AND `escapeJavaScript` both escape the forward slash: `/` -> `\/`
  (this is the Lang-52 fix; `</a>` -> `<\/a>`). They differ ONLY on the single quote:
  `escapeJava("'") == "'"`, `escapeJavaScript("'") == "\\'"`.
- `escapeJava` char rules: `< 0x20` -> `\b \n \t \f \r` or `\u000X`/`\u00XX`;
  `0x20..0x7F` pass through (0x7F is NOT escaped); `> 0x7F` -> `\uXXXX` with UPPER-CASE hex
  (from `Integer.toHexString(ch).toUpperCase()`), width keyed off `>0xff`/`>0xfff`.
- `unescapeJava`: unknown `\x` -> `x`; trailing lone `\` -> emitted; a `\u` escape with fewer
  than 4 trailing hex digits before EOF -> silently dropped; invalid hex in `\uXXXX` ->
  throws `org.apache.commons.lang.exception.NestableRuntimeException`
  ("Unable to parse unicode value: ...").
- `escapeHtml` uses `Entities.HTML40` (no `apos`); unnamed char `> 0x7F` -> `&#DECIMAL;`.
  `unescapeHtml` supports `&#d;`, `&#xH;`/`&#XH;`; value `> 0xFFFF` -> left verbatim;
  missing `;` or `&..&..;` -> left verbatim; unknown name -> left verbatim.
- `escapeXml`/`unescapeXml` use `Entities.XML` = only the 5 (`lt gt amp quot apos`);
  `escapeXml` escapes `'` as `&apos;` (unlike HTML); non-ASCII -> `&#DECIMAL;`.
- `escapeSql(str)` = `StringUtils.replace(str, "'", "''")` only; `"` `%` `_` untouched.
- All string methods return `null` for `null` in, `""` for `""`. All `Writer` overloads throw
  `IllegalArgumentException` on null Writer (checked before the null-string no-op).

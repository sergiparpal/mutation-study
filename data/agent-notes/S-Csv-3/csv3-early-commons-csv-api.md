---
name: csv3-early-commons-csv-api
description: specW_Csv_3 test task — this is a pre-1.0 commons-csv with the CSVFormatBuilder API
metadata: 
  node_type: memory
  type: project
  originSessionId: ea683d80-15a3-495c-bcfd-92e997b06aea
  modified: 2026-09-10T13:47:54.552Z
---

Task at `/tmp/specW_Csv_3`: write `<Class>AgentTest` JUnit tests against `api/` javadoc only, compile with `./compile.sh` (never run). `lib/` has JUnit 3.8.1 (also 4.x jars, but match 3.8 → extend `junit.framework.TestCase`, no `org.junit.*`). `-source 8`.

`lib/project.jar` is an **early (pre-1.0) Apache Commons CSV**. Key API facts discovered by trial compilation (bytecode inspection was disallowed):
- `CSVFormat` has **no** fluent `withDelimiter/withEscape/...` methods and **no** `newFormat(char)`.
- Custom formats go through the builder: `CSVFormat.newBuilder(CSVFormat.DEFAULT).withDelimiter(';').withEscape('\\').withCommentStart('#').withIgnoreEmptyLines(false).withIgnoreSurroundingSpaces(true).withQuoteChar('"').build()`.
- Nested builder type is `CSVFormat.CSVFormatBuilder`; `CSVFormat.newBuilder()`, `newBuilder(char)`, `newBuilder(CSVFormat)` all exist. `build()` returns `CSVFormat`.
- Note names: `withCommentStart` (not `withCommentMarker`), `withQuoteChar` (not `withQuote`). `Quote` enum class (not `QuoteMode`).
- Package-private classes in `org.apache.commons.csv`: `Lexer` (abstract), `ExtendedBufferedReader` (ctor `(Reader)`, has `read()`, `getLastChar()`, line counter starts at 0), `Token`, `Token.Type`, `Constants`, `CSVLexer`.
- Only `api/org/apache/commons/csv/Lexer.html` + package docs exist as spec; nothing for `CSVFormat`.

Done so far: `LexerAgentTest` (33 tests) compiles OK. Uses a local `ConcreteLexer extends Lexer` stub for the abstract `nextToken(Token)`.

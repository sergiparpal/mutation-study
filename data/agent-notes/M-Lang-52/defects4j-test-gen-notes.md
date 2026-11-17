---
name: defects4j-test-gen-notes
description: Practical notes for writing JUnit tests for Defects4J projects (Lang/Csv/Gson/Cli) in this environment
metadata: 
  node_type: memory
  type: project
  originSessionId: 0a0259b2-1ece-47af-88f2-7c30b07145e7
  modified: 2026-09-02T08:34:39.054Z
---

Task family: write `<ClassName>AgentTest` JUnit classes for Defects4J bugs, verified with
`defects4j compile` + `java -cp "$(defects4j export -p cp.test)" org.junit.runner.JUnitCore <TestClass>`.

**Commons Lang (2.x) specifics**
- JUnit **3.8.1** style: `extends junit.framework.TestCase`, `public void testXxx()`, provide
  `public static Test suite()` + `(String name)` constructor. No `org.junit` imports, no annotations
  (JUnit 4 is on `cp.test` at runtime via junit-4.12, but NOT guaranteed on the ant compile classpath).
- Dominant assertion idiom: `assertEquals(expected, actual)`, `assertEquals(null, x)` for nulls,
  `assertEquals(true, boolExpr)`. Constructor test pattern (see `StringUtilsTest.testConstructor`):
  `assertNotNull(new X()); getDeclaredConstructors().length == 1; Modifier.isPublic(...)`.
- `build.xml` `<javac>` sets **no `encoding`** attribute -> source must be **strict ASCII**.

**Write-tool gotcha (this harness)**
- The Write/Edit content path does NOT reliably preserve `\uXXXX` escapes inside Java string
  literals (single backslash-u gets eaten -> string becomes empty) and preserves literal non-ASCII
  bytes as-is (which then break the no-encoding javac).
- Fix: build non-ASCII / control chars at runtime, e.g. a private `static String chr(int c){return
  String.valueOf((char)c);}` helper, and only ever write `\\u` (escaped backslash, for text that
  must literally contain a backslash-u, e.g. `unescapeJava` inputs). Verify after writing with
  `grep -nP '[^\x00-\x7F]'` and `grep -nP '(?<!\\)\\u'` — both must be empty.

Done: Lang-52 `StringEscapeUtilsAgentTest` (76 tests, all green). See [[stringescapeutils-lang52-behavior]].

---
name: d4j-agent-test-generation
description: Conventions for the Defects4J agent test-generation experiment (Lang/Csv/Gson/Cli bugs)
metadata: 
  node_type: memory
  type: project
  originSessionId: e4904f81-d8a9-4ae6-9333-6cd210d8f899
  modified: 2026-09-02T20:49:15.438Z
---

Recurring task: write `<ClassName>AgentTest` JUnit classes for Defects4J checkouts
(dirs like `/tmp/agentB_<Project>_<bug>_f`, a FIXED version per `.defects4j.config` `vid=<n>f`).

**Why:** The user supplies a long list of `Project,bug` pairs; each is the same shaped task.

**How to apply:**
- Place tests in `src/test/<pkg>/`, package-matched, named exactly `<ClassName>AgentTest`.
- Match existing test style. commons-lang uses **JUnit 3** (`extends TestCase`,
  `junit.framework.*`, `assertEquals`/`fail`/try-catch), with `main()` + `suite()` boilerplate.
- A stub `<ClassName>Test.java` is present (original dev tests removed, sometimes kept as
  `.java.bak` — useful for known-good expected values). Do NOT modify the stub.
- Verify: `defects4j compile` then
  `java -cp "$(defects4j export -p cp.test)" org.junit.runner.JUnitCore <pkg>.<ClassName>AgentTest`
  (cp.test bundles junit-4.12; JUnitCore runs JUnit 3 TestCases fine).
- Env gotcha: shell `TZ=America/Los_Angeles` but `/etc/timezone`=[redacted]; JVM used LA.
  For time/period tests build epoch millis via `Calendar.getInstance(TimeZone.getTimeZone("GMT"))`
  or pick dates where both endpoints share the same UTC offset (e.g. Jan 1) to avoid DST flakiness.
- Lang 63: bug in `DurationFormatUtils.formatPeriod` day/month borrow; d4j trigger
  `DurationFormatUtilsTest::testJiraLang281` (2005-12-31 -> 2006-10-06, "MM" -> "09").

Done so far: Lang 63 -> `DurationFormatUtilsAgentTest` (23 tests, passing).

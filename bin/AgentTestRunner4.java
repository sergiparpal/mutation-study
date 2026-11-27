/*
 * Seventh campaign: the report of bin/AgentTestRunner.java, on JUnit 4.
 *
 * The sample's Defects4J bugs have JUnit 4 on their test class path and no
 * JUnit Platform, and the platform's engine for JUnit 4 is not in the
 * machine's local Maven repository, so bin/AgentTestRunner.java cannot run
 * their tests offline. This runner runs each class named on the command line
 * on its own, with JUnit 4's own runners (those JUnitCore uses), and says,
 * method by method, what happened, in the format of bin/AgentTestRunner.java.
 * Acceptance (bin/generate-campaign7.sh) and the measurement
 * (bin/measure-campaign7.sh) use it. The agent's own script, _tools/test.sh,
 * runs JUnitCore, as in the second campaign.
 *
 * The unit is the test METHOD. A method is `class#name()`, the class being
 * the binary name, so a method of a nested class is told from one of the same
 * name in another. Every parameter set of a parameterised method belongs to
 * its method: JUnit 4 names them `name[0]`, `name[1]` and so on. A method
 * FAILED if any of its invocations failed; ABORTED (an assumption did not
 * hold) and SKIPPED (@Ignore) are not failures. A class that fails as a whole
 * is reported as a failed CLASS, and its methods do not run. That is the case
 * when it cannot be loaded, when JUnit rejects its declarations, when a
 * @BeforeClass method or a static initialiser throws, or when JUnit 3's
 * TestSuite reports a warning in its place.
 *
 *   --report FILE    one line per method or failed class, tab-separated:
 *                    status, kind, key, invocations, failed invocations, first message
 *   --exclude FILE   keys, one per line, left out before anything runs: a
 *                    method's key, or a class's binary name for the whole
 *                    class and the classes nested in it
 *
 * Exit status: 0 nothing failed; 1 something failed; 2 the classes named hold
 * no test method at all.
 *
 * Java 8 source. Needs JUnit 4.7 or later on the class path.
 */

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.runner.Description;
import org.junit.runner.Request;
import org.junit.runner.Runner;
import org.junit.runner.manipulation.Filter;
import org.junit.runner.manipulation.NoTestsRemainException;
import org.junit.runner.notification.Failure;
import org.junit.runner.notification.RunListener;
import org.junit.runner.notification.RunNotifier;

public final class AgentTestRunner4 {

    private static final int MAX_FRAMES = 40;

    /** What is known about one method, or about one class that failed as a whole. */
    private static final class Entry {
        final String kind;
        int invocations;
        int failed;
        int aborted;
        int skipped;
        String message = "";
        Entry(String kind) { this.kind = kind; }
        String status() {
            if (failed > 0) return "FAILED";
            if (invocations == 0) return "NOT_RUN";
            if (invocations > aborted + skipped) return "SUCCESSFUL";
            if (aborted > 0) return "ABORTED";
            return "SKIPPED";
        }
    }

    private static final Map<String, Entry> ENTRIES = new LinkedHashMap<String, Entry>();
    private static final List<String> FAILURES = new ArrayList<String>();
    private static final int[] COUNTS = new int[4];            // run, failed, aborted, skipped

    private static boolean belongsTo(String className, String cls) {
        return className != null && (className.equals(cls) || className.startsWith(cls + "$"));
    }

    /**
     * The key of the method a description stands for, or null when it stands
     * for a class as a whole: JUnit's placeholder for a class it rejects, or a
     * test that is not one of the class's own, as JUnit 3's TestSuite puts a
     * warning in place of a class it cannot use.
     */
    private static String methodKey(Description d, String cls) {
        String m = d.getMethodName();
        String c = d.getClassName();
        if (m == null || !belongsTo(c, cls)) return null;
        int b = m.indexOf('[');
        if (b > 0) m = m.substring(0, b);
        if (m.isEmpty() || "initializationError".equals(m)) return null;
        return c + "#" + m + "()";
    }

    /** The class a failure as a whole is reported for. */
    private static String classKey(Description d, String cls) {
        return belongsTo(d.getClassName(), cls) ? d.getClassName() : cls;
    }

    /** Whether a class, or a class it is nested in, is left out as a whole. */
    private static boolean classLeftOut(String className, Set<String> excluded) {
        if (className == null) return false;
        String[] parts = className.split("\\$");
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) sb.append('$');
            sb.append(parts[i]);
            if (excluded.contains(sb.toString())) return true;
        }
        return false;
    }

    private static boolean leftOut(Description d, String cls, Set<String> excluded) {
        String key = methodKey(d, cls);
        if (key != null && excluded.contains(key)) return true;
        return classLeftOut(belongsTo(d.getClassName(), cls) ? d.getClassName() : cls, excluded);
    }

    private static Entry entry(String key, String kind) {
        Entry e = ENTRIES.get(key);
        if (e == null) { e = new Entry(kind); ENTRIES.put(key, e); }
        return e;
    }

    private static String oneLine(String s) {
        return s.replace('\t', ' ').replace('\r', ' ').replace('\n', ' ');
    }

    private static void fail(String key, String shown, Throwable t, String text) {
        Entry e = entry(key, key.indexOf('#') >= 0 ? "method" : "class");
        e.failed++;
        COUNTS[1]++;
        if (e.message.isEmpty()) e.message = oneLine(t != null ? String.valueOf(t) : text);
        StringBuilder sb = new StringBuilder();
        sb.append(FAILURES.size() + 1).append(") ").append(key);
        if (shown != null && !key.contains("#" + shown) && !key.endsWith(shown)) sb.append("  [").append(shown).append("]");
        sb.append('\n');
        if (t == null) {
            sb.append(text).append('\n');
        } else {
            sb.append(t).append('\n');
            int shownFrames = 0;
            for (StackTraceElement f : t.getStackTrace()) {
                String c = f.getClassName();
                if (c.startsWith("org.junit.") || c.startsWith("junit.framework.") || c.startsWith("jdk.internal.")
                        || c.startsWith("java.lang.reflect.") || c.startsWith("sun.reflect.")
                        || (c.startsWith("java.util.") && shownFrames > 0)) continue;
                sb.append("    at ").append(f).append('\n');
                if (++shownFrames >= MAX_FRAMES) { sb.append("    ...\n"); break; }
            }
            Throwable cause = t.getCause();
            if (cause != null && cause != t) sb.append("Caused by: ").append(cause).append('\n');
        }
        FAILURES.add(sb.toString());
    }

    private static boolean hasLeftOutKey(String cls, Set<String> excluded) {
        for (String e : excluded) {
            if (e.equals(cls) || e.startsWith(cls + "#") || e.startsWith(cls + "$")) return true;
        }
        return false;
    }

    /** Run one class. Returns false if it holds no test method at all. */
    private static boolean runClass(final String cls, final Set<String> excluded) {
        if (excluded.contains(cls)) return true;       // left out as a whole
        final Class<?> c;
        try {
            c = Class.forName(cls, false, Thread.currentThread().getContextClassLoader());
        } catch (Throwable t) {
            entry(cls, "class").invocations++;
            fail(cls, null, null, "the class cannot be loaded: " + t);
            return true;
        }
        // JUnit 4 would run a static initialiser when it makes the first test
        // instance and blame that test; here it fails the class, as on the
        // JUnit Platform
        try {
            Class.forName(cls, true, Thread.currentThread().getContextClassLoader());
        } catch (Throwable t) {
            entry(cls, "class").invocations++;
            fail(cls, null, t instanceof ExceptionInInitializerError && t.getCause() != null ? t.getCause() : t,
                    "(no exception reported)");
            return true;
        }

        final Runner runner;
        try {
            runner = Request.aClass(c).getRunner();
        } catch (Throwable t) {
            entry(cls, "class").invocations++;
            fail(cls, null, null, "JUnit could not make a runner for this class:\n" + t);
            return true;
        }
        if (!excluded.isEmpty()) {
            try {
                new Filter() {
                    @Override
                    public boolean shouldRun(Description d) {
                        if (d.isTest()) return !leftOut(d, cls, excluded);
                        for (Description child : d.getChildren()) {
                            if (shouldRun(child)) return true;
                        }
                        return false;
                    }

                    @Override
                    public String describe() { return "the tests not left out"; }
                }.apply(runner);
            } catch (NoTestsRemainException e) {
                return hasLeftOutKey(cls, excluded);
            }
        }

        // what the class holds, before anything runs. A runner that cannot be
        // filtered still holds what was left out; the listener ignores it.
        int found = 0, wholeClass = 0;
        Deque<Description> todo = new ArrayDeque<Description>();
        todo.add(runner.getDescription());
        while (!todo.isEmpty()) {
            Description d = todo.poll();
            if (!d.isTest()) { todo.addAll(d.getChildren()); continue; }
            if (leftOut(d, cls, excluded)) continue;
            String key = methodKey(d, cls);
            if (key != null) { entry(key, "method"); found++; } else { wholeClass++; }
        }
        if (found == 0 && wholeClass == 0) return hasLeftOutKey(cls, excluded);

        RunNotifier notifier = new RunNotifier();
        notifier.addListener(new RunListener() {
            @Override
            public void testFinished(Description d) {
                String key = methodKey(d, cls);
                if (key == null || leftOut(d, cls, excluded)) return;
                entry(key, "method").invocations++;
                COUNTS[0]++;
            }

            @Override
            public void testFailure(Failure f) {
                Description d = f.getDescription();
                if (leftOut(d, cls, excluded)) return;
                String key = methodKey(d, cls);
                if (key != null) {
                    fail(key, d.getMethodName(), f.getException(), "(no exception reported)");
                } else {
                    // a class that failed as such: in its set-up, or rejected by JUnit
                    String own = classKey(d, cls);
                    entry(own, "class").invocations++;
                    fail(own, d.getDisplayName(), f.getException(), "(no exception reported)");
                }
            }

            @Override
            public void testAssumptionFailure(Failure f) {
                Description d = f.getDescription();
                String key = methodKey(d, cls);
                if (key == null || leftOut(d, cls, excluded)) return;
                entry(key, "method").aborted++;
                COUNTS[2]++;
            }

            @Override
            public void testIgnored(Description d) {
                String key = methodKey(d, cls);
                if (key == null || leftOut(d, cls, excluded)) return;
                Entry e = entry(key, "method");
                e.invocations++;
                e.skipped++;
                COUNTS[3]++;
            }
        });
        try {
            runner.run(notifier);
        } catch (Throwable t) {
            entry(cls, "class").invocations++;
            fail(cls, null, t, "(no exception reported)");
        }
        return true;
    }

    public static void main(String[] args) throws IOException {
        String report = null;
        Set<String> excluded = new HashSet<String>();
        List<String> classes = new ArrayList<String>();
        for (int i = 0; i < args.length; i++) {
            if ("--report".equals(args[i]) && i + 1 < args.length) {
                report = args[++i];
            } else if ("--exclude".equals(args[i]) && i + 1 < args.length) {
                for (String line : Files.readAllLines(Paths.get(args[++i]), StandardCharsets.UTF_8)) {
                    if (!line.trim().isEmpty()) excluded.add(line.trim());
                }
            } else {
                classes.add(args[i]);
            }
        }
        if (classes.isEmpty()) {
            System.err.println("usage: AgentTestRunner4 [--report FILE] [--exclude FILE] <test class> ...");
            System.exit(2);
        }

        for (String cls : classes) {
            if (!runClass(cls, excluded)) {
                System.out.println("no test method found in " + cls);
            }
        }

        for (String f : FAILURES) System.out.println(f);
        int methods = 0, failedMethods = 0, failedClasses = 0;
        for (Entry e : ENTRIES.values()) {
            if ("method".equals(e.kind)) {
                methods++;
                if (e.failed > 0) failedMethods++;
            } else if (e.failed > 0) {
                failedClasses++;
            }
        }
        System.out.println("Tests run: " + COUNTS[0] + ", Failures: " + COUNTS[1]
                + ", Aborted: " + COUNTS[2] + ", Skipped: " + COUNTS[3]);
        System.out.println("Test methods: " + methods + ", failed: " + failedMethods
                + (failedClasses > 0 ? ", classes that failed as a whole: " + failedClasses : "")
                + (excluded.isEmpty() ? "" : ", left out beforehand: " + excluded.size()));
        // nothing to run at all is not a pass
        boolean empty = methods == 0 && failedClasses == 0 && excluded.isEmpty();
        System.out.println(COUNTS[1] > 0 ? "FAILURES!!!" : (empty ? "NO TESTS" : "OK"));

        if (report != null) {
            PrintWriter out = new PrintWriter(Files.newBufferedWriter(Paths.get(report), StandardCharsets.UTF_8));
            try {
                for (Map.Entry<String, Entry> en : ENTRIES.entrySet()) {
                    Entry e = en.getValue();
                    out.println(e.status() + "\t" + e.kind + "\t" + en.getKey() + "\t" + e.invocations
                            + "\t" + e.failed + "\t" + e.message);
                }
            } finally {
                out.close();
            }
        }
        System.out.flush();
        // tests may leave non-daemon threads behind
        System.exit(COUNTS[1] > 0 ? 1 : (empty ? 2 : 0));
    }
}

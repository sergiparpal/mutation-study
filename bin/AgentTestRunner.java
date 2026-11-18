/*
 * Third campaign: runs the test classes named on the command line on the
 * JUnit Platform and says, method by method, what happened.
 *
 * One runner for every place a generated suite is run: the script the
 * implementation-visible agent is given (_tools/test.sh), the acceptance of a
 * suite on the fixed revision and the measurement on both revisions
 * (bin/generate-postcutoff.sh, bin/measure-campaign3.sh). The projects' own
 * build is not used to run them: Maven needs the network or a local
 * repository, which the agent's sandbox has neither of, and it compiles every
 * developer test first, which fails once the files that hold the trigger
 * tests are gone.
 *
 * The unit is the test METHOD. A method is `class#name(parameter types)`, the
 * class being the binary name, so a method of a @Nested class is told from one
 * of the same name in another. Every invocation of a parameterised or repeated
 * test and every dynamic test of a factory belongs to its method. A method
 * FAILED if any of its invocations failed; ABORTED (an assumption did not
 * hold) and SKIPPED are not failures. A class that fails as a whole (it cannot
 * be loaded, JUnit rejects its declarations, @BeforeAll or a static
 * initialiser throws) is reported as a failed CLASS, and its methods do not
 * run.
 *
 * Each class is discovered and run on its own, so that one the platform
 * rejects does not take the others with it.
 *
 *   --report FILE    one line per method or failed class, tab-separated:
 *                    status, kind, key, invocations, failed invocations, first message
 *   --exclude FILE   keys, one per line, left out before anything runs: the
 *                    methods (or classes) that failed on the fixed revision
 *
 * Exit status: 0 nothing failed; 1 something failed; 2 the classes named hold
 * no test method at all.
 *
 * Java 8 source. Needs junit-platform-launcher 1.8 or later on the class path.
 */

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.platform.engine.FilterResult;
import org.junit.platform.engine.TestDescriptor;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.TestSource;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.engine.support.descriptor.ClassSource;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.PostDiscoveryFilter;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.TestPlan;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;

public final class AgentTestRunner {

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

    private static String keyOf(Optional<TestSource> source) {
        if (!source.isPresent()) return null;
        TestSource s = source.get();
        if (s instanceof MethodSource) {
            MethodSource m = (MethodSource) s;
            String params = m.getMethodParameterTypes();
            return m.getClassName() + "#" + m.getMethodName() + "(" + (params == null ? "" : params) + ")";
        }
        if (s instanceof ClassSource) return ((ClassSource) s).getClassName();
        return null;
    }

    private static boolean isMethod(String key) { return key != null && key.indexOf('#') >= 0; }

    /** The method an identifier belongs to: its own, or that of its nearest ancestor. */
    private static String methodKey(TestPlan plan, TestIdentifier id) {
        TestIdentifier at = id;
        while (at != null) {
            String key = keyOf(at.getSource());
            if (isMethod(key)) return key;
            Optional<TestIdentifier> parent = plan.getParent(at);
            at = parent.isPresent() ? parent.get() : null;
        }
        return null;
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
        Entry e = entry(key, isMethod(key) ? "method" : "class");
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
                if (c.startsWith("org.junit.") || c.startsWith("jdk.internal.") || c.startsWith("java.lang.reflect.")
                        || c.startsWith("sun.reflect.") || (c.startsWith("java.util.") && shownFrames > 0)) continue;
                sb.append("    at ").append(f).append('\n');
                if (++shownFrames >= MAX_FRAMES) { sb.append("    ...\n"); break; }
            }
            Throwable cause = t.getCause();
            if (cause != null && cause != t) sb.append("Caused by: ").append(cause).append('\n');
        }
        FAILURES.add(sb.toString());
    }

    /** Discover and run one class. Returns false if it holds no test method at all. */
    private static boolean runClass(Launcher launcher, final String cls, final Set<String> excluded) {
        if (excluded.contains(cls)) return true;       // left out as a whole
        try {
            Class.forName(cls, false, Thread.currentThread().getContextClassLoader());
        } catch (Throwable t) {
            entry(cls, "class").invocations++;
            fail(cls, null, null, "the class cannot be loaded: " + t);
            return true;
        }

        LauncherDiscoveryRequestBuilder builder = LauncherDiscoveryRequestBuilder.request()
                .selectors(DiscoverySelectors.selectClass(cls));
        if (!excluded.isEmpty()) {
            // the platform asks about leaves only, so a class left out as a whole
            // is found by walking up from each of its methods
            builder.filters(new PostDiscoveryFilter() {
                @Override
                public FilterResult apply(TestDescriptor d) {
                    TestDescriptor at = d;
                    while (at != null) {
                        String key = keyOf(at.getSource());
                        if (key != null && excluded.contains(key)) {
                            return FilterResult.excluded("failed on the fixed revision");
                        }
                        at = at.getParent().isPresent() ? at.getParent().get() : null;
                    }
                    return FilterResult.included("kept");
                }
            });
        }

        final TestPlan plan;
        try {
            plan = launcher.discover(builder.build());
        } catch (Throwable t) {
            // JUnit refuses the class as declared
            entry(cls, "class").invocations++;
            String text = String.valueOf(t.getMessage());
            fail(cls, null, null, "JUnit could not discover the tests of this class:\n" + text);
            return true;
        }

        int found = 0;
        for (TestIdentifier root : plan.getRoots()) {
            for (TestIdentifier id : plan.getDescendants(root)) {
                String key = keyOf(id.getSource());
                if (isMethod(key)) { entry(key, "method"); found++; }
            }
        }
        if (found == 0) {
            for (String e : excluded) {
                if (e.equals(cls) || e.startsWith(cls + "#") || e.startsWith(cls + "$")) return true;
            }
            return false;
        }

        launcher.execute(plan, new TestExecutionListener() {
            @Override
            public void executionSkipped(TestIdentifier id, String reason) {
                String key = methodKey(plan, id);
                if (key == null) return;
                Entry e = entry(key, "method");
                e.invocations++;
                e.skipped++;
                COUNTS[3]++;
            }

            @Override
            public void executionFinished(TestIdentifier id, TestExecutionResult result) {
                TestExecutionResult.Status status = result.getStatus();
                Throwable t = result.getThrowable().isPresent() ? result.getThrowable().get() : null;
                String key = methodKey(plan, id);
                if (id.isTest()) {
                    if (key == null) key = id.getUniqueId();
                    Entry e = entry(key, "method");
                    e.invocations++;
                    COUNTS[0]++;
                    if (status == TestExecutionResult.Status.FAILED) {
                        fail(key, id.getDisplayName(), t, "(no exception reported)");
                    } else if (status == TestExecutionResult.Status.ABORTED) {
                        e.aborted++;
                        COUNTS[2]++;
                    }
                } else if (status == TestExecutionResult.Status.FAILED) {
                    // a container that failed as such: a class in its set-up, or a
                    // parameterised method that could not produce its invocations
                    String own = keyOf(id.getSource());
                    if (own == null) own = key != null ? key : id.getUniqueId();
                    entry(own, isMethod(own) ? "method" : "class").invocations++;
                    fail(own, id.getDisplayName(), t, "(no exception reported)");
                }
            }
        });
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
            System.err.println("usage: AgentTestRunner [--report FILE] [--exclude FILE] <test class> ...");
            System.exit(2);
        }

        Launcher launcher = LauncherFactory.create();
        for (String cls : classes) {
            if (!runClass(launcher, cls, excluded)) {
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

/*
 * Third campaign, mutation measurement (bin/mutation-campaign3.sh): leaves
 * out of a run on the JUnit Platform the test methods that acceptance left
 * out, by the same keys and the same rule as bin/AgentTestRunner.java.
 *
 * Written on 19 November 2026, after the campaign had been measured and
 * analysed. It is not one of the scripts the protocol fixes.
 *
 * PIT runs the tests itself, so the runner's --exclude cannot be used. This
 * filter is registered through java.util.ServiceLoader
 * (META-INF/services/org.junit.platform.launcher.PostDiscoveryFilter), which
 * the platform reads for every launcher it creates, PIT's included.
 *
 *   -Dc3.exclude=FILE   the keys to leave out, one per line:
 *                       `class#name(parameter types)` for a method, the
 *                       class's binary name for a class. A test is left out
 *                       when its own key, or that of any of its ancestors, is
 *                       in the file. Without it nothing is left out; a file
 *                       that cannot be read stops the run.
 *   -Dc3.report=FILE    where to append, once per key and process, `kept` or
 *                       `left out`, a tab and the key of each test the
 *                       platform asks about: the record of what the run
 *                       contained. Several processes may append to it.
 *
 * Every left-out key is also printed once on standard error.
 *
 * Java 8 source. Needs junit-platform-launcher 1.7 or later on the class path.
 */

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.Optional;
import java.util.Set;

import org.junit.platform.engine.FilterResult;
import org.junit.platform.engine.TestDescriptor;
import org.junit.platform.engine.TestSource;
import org.junit.platform.engine.support.descriptor.ClassSource;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.PostDiscoveryFilter;

public final class ExcludedTestsFilter implements PostDiscoveryFilter {

    private final Set<String> excluded = new HashSet<String>();
    private final Set<String> seen = new HashSet<String>();
    private final String report = System.getProperty("c3.report");

    public ExcludedTestsFilter() {
        String path = System.getProperty("c3.exclude");
        if (path == null || path.isEmpty()) return;
        try {
            for (String line : Files.readAllLines(Paths.get(path), StandardCharsets.UTF_8)) {
                if (!line.trim().isEmpty()) excluded.add(line.trim());
            }
        } catch (IOException e) {
            throw new IllegalStateException("c3.exclude: cannot read " + path, e);
        }
    }

    /** The key of a descriptor, as bin/AgentTestRunner.java forms it. */
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

    private void record(String status, String key, boolean toStderr) {
        if (key == null) return;
        synchronized (seen) {
            if (!seen.add(status + "\t" + key)) return;
            if (toStderr) System.err.println("c3.exclude: left out " + key);
            if (report == null || report.isEmpty()) return;
            try {
                Files.write(Paths.get(report), (status + "\t" + key + "\n").getBytes(StandardCharsets.UTF_8),
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException e) {
                throw new IllegalStateException("c3.report: cannot write " + report, e);
            }
        }
    }

    @Override
    public FilterResult apply(TestDescriptor d) {
        String own = keyOf(d.getSource());
        TestDescriptor at = d;
        while (at != null) {
            String key = keyOf(at.getSource());
            if (key != null && excluded.contains(key)) {
                record("left out", key, true);
                return FilterResult.excluded("failed on the fixed revision");
            }
            at = at.getParent().isPresent() ? at.getParent().get() : null;
        }
        record("kept", own, false);
        return FilterResult.included("kept");
    }
}

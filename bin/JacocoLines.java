/*
 * JaCoCo's record of which lines ran, for bin/remeasure-csv4-coverage.sh.
 *
 * Defects4J measures line coverage with Cobertura. In one class of the sample,
 * Csv-4's CSVParser, Cobertura leaves most methods without a line counter
 * (bin/check-cobertura-instrumentation.py), so the lines of those methods read
 * as never executed. The re-measurement runs Defects4J's coverage step again
 * with JaCoCo attached, and this program reads what JaCoCo recorded.
 *
 *   JacocoLines lines EXEC CLASSES...
 *       EXEC is a JaCoCo execution data file; each of CLASSES is a class file
 *       or a directory of them, holding the bytes the run executed. For each
 *       class, sorted by name, prints one line per source line that has code:
 *           LINE <tab> class <tab> line <tab> 1 if any of its instructions ran, else 0
 *       and then
 *           CLASS <tab> class <tab> lines with code <tab> lines with an instruction that ran
 *       A class whose bytes are not those the run recorded is printed as
 *           NO-MATCH <tab> class
 *       and the exit status is 1.
 *
 *   JacocoLines instrument SOURCE=TARGET...
 *       Writes TARGET, the class file SOURCE instrumented offline. That is for
 *       classes JaCoCo's agent does not see: EvoSuite's runtime defines the
 *       class under test in a class loader of its own. Such a class reports
 *       to the agent's runtime, which must be on the class path of the run,
 *       and its execution data are read against SOURCE, not TARGET.
 *
 * Java 8 source. Needs org.jacoco.core and ASM (asm, asm-commons, asm-tree)
 * on the class path.
 */

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IClassCoverage;
import org.jacoco.core.analysis.ICounter;
import org.jacoco.core.instr.Instrumenter;
import org.jacoco.core.runtime.OfflineInstrumentationAccessGenerator;
import org.jacoco.core.tools.ExecFileLoader;

public class JacocoLines {

    public static void main(String[] args) throws Exception {
        if (args.length >= 3 && args[0].equals("lines")) {
            System.exit(lines(args));
        } else if (args.length >= 2 && args[0].equals("instrument")) {
            instrument(args);
        } else {
            System.err.println("usage: JacocoLines lines EXEC CLASSES... | JacocoLines instrument SOURCE=TARGET...");
            System.exit(2);
        }
    }

    private static int lines(String[] args) throws Exception {
        ExecFileLoader loader = new ExecFileLoader();
        loader.load(new File(args[1]));
        CoverageBuilder builder = new CoverageBuilder();
        Analyzer analyzer = new Analyzer(loader.getExecutionDataStore(), builder);
        for (int i = 2; i < args.length; i++) {
            analyzer.analyzeAll(new File(args[i]));
        }
        List<IClassCoverage> classes = new ArrayList<>(builder.getClasses());
        classes.sort(Comparator.comparing(IClassCoverage::getName));
        int status = 0;
        for (IClassCoverage c : classes) {
            if (c.isNoMatch()) {
                System.out.println("NO-MATCH\t" + c.getName());
                status = 1;
                continue;
            }
            for (int n = c.getFirstLine(); n > 0 && n <= c.getLastLine(); n++) {
                int s = c.getLine(n).getStatus();
                if (s != ICounter.EMPTY) {
                    System.out.println("LINE\t" + c.getName() + "\t" + n + "\t" + (s == ICounter.NOT_COVERED ? 0 : 1));
                }
            }
            ICounter lc = c.getLineCounter();
            System.out.println("CLASS\t" + c.getName() + "\t" + lc.getTotalCount() + "\t" + lc.getCoveredCount());
        }
        return status;
    }

    private static void instrument(String[] args) throws Exception {
        Instrumenter instrumenter = new Instrumenter(new OfflineInstrumentationAccessGenerator());
        for (int i = 1; i < args.length; i++) {
            String[] pair = args[i].split("=", 2);
            if (pair.length != 2) {
                throw new IllegalArgumentException("not SOURCE=TARGET: " + args[i]);
            }
            byte[] out;
            try (InputStream in = new FileInputStream(pair[0])) {
                out = instrumenter.instrument(in, pair[0]);
            }
            try (OutputStream o = new FileOutputStream(pair[1])) {
                o.write(out);
            }
        }
    }
}

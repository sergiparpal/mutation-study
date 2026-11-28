/*
 * The behaviours that the find-faults runs of the sixth and seventh campaigns
 * named in more than one run, tried on the projects' releases, for
 * bin/check-recurring-findings.sh.
 *
 * None of them is the fault of a subject, so the campaigns count the tests
 * that show them as false alarms. Whether each is a bug is a separate
 * question. This program shows what each one does in the releases on the
 * class path. What the javadoc promises is read in the sources
 * (data/README.md, "The recurring findings, checked against the projects").
 *
 *   1. StopWatch.split() called twice without unsplit()      (f6: three runs)
 *   2. equalsIgnoreCase(null) on the string builders         (f6: two runs)
 *   3. a registered format name followed by a space,
 *      in ExtendedMessageFormat                              (f6: two runs; f7: Lang-23)
 *   4. CSVFormat.withRecordSeparator with a separator that is
 *      none of CR, LF or CRLF                                (f7: Csv-14, Csv-15)
 *
 * The program also checks two other claims made by those runs: Csv-15's,
 * that CSVFormat.equals() ignores trim and allowMissingColumnNames, and
 * Lang-23's, that toPattern() throws for "'{0}' {1,upper}".
 *
 * Every line printed is "what is tried -> what happens". An exception is
 * printed as its class name and its message, in quotes. Java 8 source; needs
 * commons-lang3, commons-text and commons-csv, with commons-io and
 * commons-codec, on the class path.
 */

import java.text.FieldPosition;
import java.text.Format;
import java.text.MessageFormat;
import java.text.ParsePosition;
import java.util.Collections;
import java.util.Locale;
import java.util.Map;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.lang3.time.StopWatch;

@SuppressWarnings("deprecation")
public class RecurringFindings {

    /** The format the runs registered: the argument in upper case. */
    static final class Upper extends Format {
        private static final long serialVersionUID = 1L;

        @Override
        public StringBuffer format(final Object obj, final StringBuffer to, final FieldPosition pos) {
            return to.append(String.valueOf(obj).toUpperCase(Locale.ROOT));
        }

        @Override
        public Object parseObject(final String source, final ParsePosition pos) {
            throw new UnsupportedOperationException();
        }
    }

    interface Call {
        Object run() throws Exception;
    }

    static void show(final String what, final Call call) {
        String result;
        try {
            result = String.valueOf(call.run());
        } catch (final Exception e) {
            result = e.getClass().getSimpleName() + (e.getMessage() == null ? "" : ": \"" + e.getMessage() + "\"");
        }
        System.out.println(what + " -> " + result);
    }

    static String version(final Class<?> c) {
        return c.getPackage().getImplementationVersion();
    }

    public static void main(final String[] args) {
        System.out.println("commons-lang3 " + version(StopWatch.class)
                + ", commons-text " + version(org.apache.commons.text.TextStringBuilder.class)
                + ", commons-csv " + version(CSVFormat.class));

        System.out.println();
        System.out.println("1. StopWatch: the class's javadoc says split(), suspend() and stop() cannot be invoked twice");
        show("split(), split()", () -> {
            final StopWatch sw = StopWatch.createStarted();
            sw.split();
            sw.split();
            return "accepted; getSplits().size() = " + sw.getSplits().size();
        });
        show("suspend(), suspend()", () -> {
            final StopWatch sw = StopWatch.createStarted();
            sw.suspend();
            sw.suspend();
            return "accepted";
        });
        show("stop(), stop()", () -> {
            final StopWatch sw = StopWatch.createStarted();
            sw.stop();
            sw.stop();
            return "accepted";
        });

        System.out.println();
        System.out.println("2. equalsIgnoreCase(null): the javadoc of each says \"null returns false\"");
        show("commons-lang3 StrBuilder.equals((StrBuilder) null)",
                () -> new org.apache.commons.lang3.text.StrBuilder("a").equals((org.apache.commons.lang3.text.StrBuilder) null));
        show("commons-lang3 StrBuilder.equalsIgnoreCase(null)",
                () -> new org.apache.commons.lang3.text.StrBuilder("a").equalsIgnoreCase(null));
        show("commons-text StrBuilder.equalsIgnoreCase(null)",
                () -> new org.apache.commons.text.StrBuilder("a").equalsIgnoreCase(null));
        show("commons-text TextStringBuilder.equals((TextStringBuilder) null)",
                () -> new org.apache.commons.text.TextStringBuilder("a").equals((org.apache.commons.text.TextStringBuilder) null));
        show("commons-text TextStringBuilder.equalsIgnoreCase(null)",
                () -> new org.apache.commons.text.TextStringBuilder("a").equalsIgnoreCase(null));

        System.out.println();
        System.out.println("3. ExtendedMessageFormat with a format registered as \"upper\", formatting \"ab\"");
        final Map<String, org.apache.commons.lang3.text.FormatFactory> langRegistry =
                Collections.singletonMap("upper", (name, arguments, locale) -> new Upper());
        final Map<String, org.apache.commons.text.FormatFactory> textRegistry =
                Collections.singletonMap("upper", (name, arguments, locale) -> new Upper());
        for (final String p : new String[] {"{0,upper}", "{0, upper}", "{0,upper }", "{ 0 , upper }", "{0,upper ,x}"}) {
            show("commons-lang3 \"" + p + "\"",
                    () -> new org.apache.commons.lang3.text.ExtendedMessageFormat(p, Locale.ROOT, langRegistry).format(new Object[] {"ab"}));
            show("commons-text  \"" + p + "\"",
                    () -> new org.apache.commons.text.ExtendedMessageFormat(p, Locale.ROOT, textRegistry).format(new Object[] {"ab"}));
        }
        show("java.text.MessageFormat \"{0,number }\", formatting 1.5",
                () -> new MessageFormat("{0,number }", Locale.ROOT).format(new Object[] {1.5}));

        System.out.println();
        System.out.println("4. CSVFormat.withRecordSeparator: the javadoc of the String overload says it throws"
                + " IllegalArgumentException if the separator is none of CR, LF or CRLF");
        show("CSVFormat.DEFAULT.withRecordSeparator(\"abc\")",
                () -> "accepted; record separator \"" + CSVFormat.DEFAULT.withRecordSeparator("abc").getRecordSeparator() + "\"");
        show("CSVFormat.DEFAULT.withRecordSeparator('x')",
                () -> "accepted; record separator \"" + CSVFormat.DEFAULT.withRecordSeparator('x').getRecordSeparator() + "\"");

        System.out.println();
        System.out.println("Other claims of the same runs");
        show("Csv-15: CSVFormat.DEFAULT.withTrim().equals(CSVFormat.DEFAULT)",
                () -> CSVFormat.DEFAULT.withTrim().equals(CSVFormat.DEFAULT));
        show("Csv-15: CSVFormat.DEFAULT.withAllowMissingColumnNames().equals(CSVFormat.DEFAULT)",
                () -> CSVFormat.DEFAULT.withAllowMissingColumnNames().equals(CSVFormat.DEFAULT));
        show("Lang-23: commons-lang3 ExtendedMessageFormat(\"'{0}' {1,upper}\").toPattern()",
                () -> new org.apache.commons.lang3.text.ExtendedMessageFormat("'{0}' {1,upper}", Locale.ROOT, langRegistry).toPattern());
    }
}

/* @hwut {
 *     title      = "HOCON parser: subset (A), annotated tree"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         comments  { features = ["java-hocon"] }
 *         faults    { features = ["java-hocon"] }
 *         fuzz      { features = ["java-hocon"] }
 *         numbers   { features = ["java-hocon"] }
 *         oneline   { features = ["java-hocon"] }
 *         positions { features = ["java-hocon"] }
 *         quoting   { features = ["java-hocon"] }
 *         refused   { features = ["java-hocon"] }
 *         scalars   { features = ["java-hocon"] }
 *         structure { features = ["java-hocon"] }
 *         triple    { features = ["java-hocon"] }
 *         unclosed  { features = ["java-hocon"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-hwut_hocon.py', choice for
 *          choice, held against its GOOD files by '.link'. 'fuzz' draws its
 *          3000 mutations from the same seed as Python, draw for draw, and
 *          bounds every parse by 0.5 s on a thread of its own.
 * _____________________________________________________________________________
 */
import hwut.DeterministicStream;
import hwut.Hocon;
import hwut.HwutRunner;
import hwut.PyText;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

final class TestHwutHocon {
    /** RETURN: nothing; the section heading is printed. */
    static void banner(String label) {
        System.out.println();
        System.out.println("--- " + label + " ---");
    }

    /** RETURN: List of SourceLine, 'text' split at '\n', offsets applied
     *          uniformly. */
    static List<Hocon.SourceLine> lines(String text, int lineOffset, int columnOffset) {
        List<Hocon.SourceLine> result = new ArrayList<>();
        String[] part = text.split("\n", -1);
        for (int i = 0; i < part.length; ++i) result.add(new Hocon.SourceLine(part[i], i + 1 + lineOffset, columnOffset));
        return result;
    }

    /** RETURN: nothing; the annotated tree printed, positions included. */
    static void show(Hocon.Node node, int indent) {
        String pad = "    ".repeat(indent);
        if (node instanceof Hocon.ObjectNode object) {
            System.out.println(pad + "{ at " + object.position());
            for (Hocon.Entry entry : object.entryList()) {
                System.out.println(pad + "  key '" + entry.key() + "' at " + entry.keyPosition() + " ->");
                show(entry.node(), indent + 1);
            }
            System.out.println(pad + "}");
        } else if (node instanceof Hocon.ListNode list) {
            System.out.println(pad + "[ at " + list.position());
            for (Hocon.Node item : list.itemList()) show(item, indent + 1);
            System.out.println(pad + "]");
        } else if (node instanceof Hocon.ScalarNode scalar) {
            System.out.println(pad + PyText.repr(scalar.value()) + " (" + PyText.typeName(scalar.value()) + ") at "
                               + scalar.position());
        }
    }

    /** RETURN: nothing; 'text' parsed, tree and faults printed. */
    static void run(String label, String text) { run(label, text, 0, 0); }

    /** RETURN: nothing; 'text' parsed with the offsets, tree and faults printed. */
    static void run(String label, String text, int lineOffset, int columnOffset) {
        banner(label);
        Hocon.Result result = Hocon.parse(lines(text, lineOffset, columnOffset), "f.hocon");
        show(result.document(), 0);
        for (Hocon.ParseFault fault : result.faultList()) System.out.println("FAULT " + fault);
    }

    /** RETURN: nothing; every scalar shape. */
    static void testScalars() {
        run("scalars",
            "a = bare\n"
            + "b = \"quoted \\\"x\\\" and \\n\"\n"
            + "c = 42\n"
            + "d = -3.14\n"
            + "e = 1e-6\n"
            + "f = true\n"
            + "g = no\n"
            + "h = make %.exe\n"
            + "i: \"colon-bound\"\n"
            + "j = null\n"
            + "k = nihil\n"
            + "l =\n");
    }

    /** RETURN: nothing; every radix, the helper, and the split sign. */
    static void testNumbers() {
        run("decimal, with sign and exponent",
            "a = 42\n" + "b = -0.12\n" + "c = +7e212\n" + "d = 6.02e23\n" + "e = .5\n");
        run("the visual helper enters no value",
            "a = 1_000\n" + "b = 7_000.5_5\n");
        run("hexadecimal, binary, octal",
            "a = 0xDEAD_BEEF\n" + "b = 0b0111_11_01\n" + "c = 0o3124\n" + "d = 0XFF\n" + "e = -0b1010\n");
        run("roman",
            "a = 0rIV\n" + "b = 0rMCMLXXXIV\n" + "c = -0rX\n");
        run("a sign standing apart from its digits",
            "a = - 0.12\n" + "b = + 7\n" + "c = - 0xFF\n" + "d = - -1.5e3\n");
        run("what spells no number is a string, and carries quotes",
            "a = 1.2.3\n" + "b = 0x\n" + "c = 0b012\n" + "d = 1__0\n" + "e = 0rIIII\n" + "f = 0rVX\n");
        run("no arithmetic: this language computes nothing",
            "a = 5 - 1\n");
    }

    /** RETURN: nothing; the quoted string, and the unquoted word. */
    static void testQuoting() {
        run("quoted: blanks, comment markers and binders are content",
            "a = \"make %.exe\"\n" + "b = \"not # a comment\"\n" + "c = \"x = y\"\n" + "d = \"yes\"\n");
        run("unquoted: refused, and shown in the quotes it wants",
            "a = make\n" + "b = strip.pype\n" + "c = [one, two]\n" + "d = 1\n");
    }

    /** RETURN: nothing; objects, lists, nesting. */
    static void testStructure() {
        run("nesting and key-brace",
            "outer {\n" + "    inner = { deep = 1 }\n" + "    braced { x = 2 }\n" + "}\n");
        run("lists",
            "commas   = [one, two, three]\n"
            + "newlines = [\n" + "    1\n" + "    2\n" + "]\n"
            + "objects  = [ { a = 1 }, { a = 2 } ]\n"
            + "empty    = []\n");
    }

    /** RETURN: nothing; entries sharing a line, without commas. */
    static void testOneline() {
        run("two entries, one line, no comma",
            "caps { timeout_sec = 30  network = false }\n");
        run("a quoted value with blanks, beside a following key",
            "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
        run("three entries, one line",
            "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
    }

    /** RETURN: nothing; both comment forms, whole-line and trailing. */
    static void testComments() {
        run("comments",
            "# whole line\n" + "a = 1   # trailing\n" + "// slashes too\n" + "b = 2   // trailing slashes\n"
            + "c = bare value # comment cut\n");
    }

    /** RETURN: nothing; the three constructs that do not exist here. */
    static void testRefused() {
        run("refused, each by name",
            "include \"other.conf\"\n" + "a = ${outside.value}\n" + "b += appended\n" + "d = survives\n");
    }

    /** RETURN: nothing; the text of several lines. */
    static void testTriple() {
        String q = "\"\"\"";
        run("several lines: indentation and blank ends go",
            "doc = " + q + "\n" + "    First line.\n" + "\n" + "      indented more\n" + "    last line\n"
            + "    " + q + "\n" + "after = 1\n");
        run("on one line; beside another entry; in a list",
            "a = " + q + "one line" + q + "  b = 2\n" + "c = [" + q + "x" + q + ", \"y\"]\n");
        run("as written: a quote, a backslash-n, a comment marker",
            "a = " + q + "says \"no\" \\n # not a comment" + q + "\n");
        run("never closed: a fault, at its beginning",
            "a = 1\n" + "b = " + q + "open\n" + "c = 2\n");
    }

    /** RETURN: nothing; faults accumulate, the parse completes. */
    static void testFaults() {
        run("faults accumulate",
            "a = 1\n" + "a = 2\n" + "b = \"unterminated\n" + "}\n" + "c {\n" + "    d = 3\n");
    }

    /** RETURN: nothing; a list whose ']' was forgotten ENDS: the brace closes
     *          the object, the fault is said once. */
    static void testUnclosed() {
        run("a list closed by the object's brace",
            "@hwut { title = \"B\" choices = [ }\n" + "after = 1\n");
        run("a stray character in a list",
            "a = [1, ; 2]\n");
    }

    static final List<String> FUZZ_SEED_TUPLE = List.of(
        "@hwut {\n"
        + "    title    = \"T\"\n"
        + "    choices  = [\"a\", \"b\"]\n"
        + "    tolerance { eq_pattern = [\"x.*\"] }\n"
        + "    n        = -1.5e3\n"
        + "    f        = true\n"
        + "}\n",
        "hwut {\n"
        + "    target     { clean = \"./c.sh\" }\n"
        + "    dependency { \"a.py\" = [\"b.py one\"] }\n"
        + "    ignore     = [\"x\"]   // comment\n"
        + "    # comment\n"
        + "}\n");
    //  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
    //  that it refuses by name, and some ordinary ones.
    static final List<String> FUZZ_ALPHABET = fuzzAlphabet();
    static final int          FUZZ_INPUT_N  = 3000;
    static final long         FUZZ_BOUND_MS = 500;      // one parse takes well under a millisecond

    /** RETURN: List of String, every character of Python's alphabet, then
     *          its four pieces of several. */
    static List<String> fuzzAlphabet() {
        List<String> result = new ArrayList<>();
        for (char c : "{}[]\",=:#/\\$ \n\t-+.eE0a".toCharArray()) result.add(String.valueOf(c));
        result.addAll(List.of("\"\"\"", "${", "//", "+="));
        return result;
    }

    /** RETURN: String, 'text' edited by one to four random insertions,
     *          deletions and duplications of a short stretch. */
    static String mutated(DeterministicStream stream, String text) {
        int editN = stream.nextInt(1, 4);
        for (int k = 0; k < editN; ++k) {
            int i = stream.nextInt(0, text.length());
            switch (stream.nextInt(0, 2)) {
                case 0  -> text = text.substring(0, i) + stream.select(FUZZ_ALPHABET) + text.substring(i);
                case 1  -> text = text.substring(0, i) + text.substring(Math.min(i + 1, text.length()));
                default -> {
                    int j = stream.nextInt(0, text.length());
                    text = text.substring(0, i) + text.substring(j, Math.min(j + 5, text.length())) + text.substring(i);
                }
            }
        }
        return text;
    }

    /** RETURN: ExecutorService, one daemon thread a parse runs on. */
    static ExecutorService parser() {
        return Executors.newSingleThreadExecutor(runnable -> {
            Thread thread = new Thread(runnable, "fuzz-parse");
            thread.setDaemon(true);
            return thread;
        });
    }

    /** RETURN: nothing; every mutated header ends and answers faults. */
    static void testFuzz() {
        DeterministicStream  stream  = new DeterministicStream(4711);
        Map<String, Integer> tally   = new LinkedHashMap<>();
        Map<String, String>  example = new LinkedHashMap<>();
        for (String key : List.of("clean", "with faults", "hang", "exception")) tally.put(key, 0);
        ExecutorService executor = parser();
        for (int k = 0; k < FUZZ_INPUT_N; ++k) {
            String text = mutated(stream, stream.select(FUZZ_SEED_TUPLE));
            Future<Hocon.Result> future = executor.submit(() -> Hocon.parse(lines(text, 0, 0), "f.hocon"));
            try {
                Hocon.Result result = future.get(FUZZ_BOUND_MS, TimeUnit.MILLISECONDS);
                tally.merge(result.faultList().isEmpty() ? "clean" : "with faults", 1, Integer::sum);
            } catch (TimeoutException hang) {
                future.cancel(true);
                executor.shutdownNow();
                executor = parser();                      // the hung one is left behind
                tally.merge("hang", 1, Integer::sum);
                example.putIfAbsent("hang", text);
            } catch (ExecutionException error) {
                Throwable cause = error.getCause();
                tally.merge("exception", 1, Integer::sum);
                example.putIfAbsent("exception", cause.getClass().getSimpleName() + ": " + cause.getMessage() + "\n" + text);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        executor.shutdownNow();
        banner(FUZZ_INPUT_N + " mutated headers");
        for (Map.Entry<String, Integer> e : tally.entrySet())
            System.out.println("    " + PyText.ljust(e.getKey(), 12) + " " + e.getValue());
        for (Map.Entry<String, String> e : example.entrySet())
            System.out.println("FIRST " + e.getKey().toUpperCase() + ":\n" + e.getValue());
    }

    /** RETURN: nothing; offsets carried: the same text reported at its place
     *          in a larger file, as an unwrapped header would be. */
    static void testPositions() {
        String text = "@hwut {\n" + "    title = \"T\"\n" + "}";
        run("plain: as its own file", text);
        run("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
    }

    public static void main(String[] args) {
        new HwutRunner(args, "HOCON parser: subset (A), annotated tree;")
            .choice("scalars",   TestHwutHocon::testScalars)
            .choice("numbers",   TestHwutHocon::testNumbers)
            .choice("quoting",   TestHwutHocon::testQuoting)
            .choice("structure", TestHwutHocon::testStructure)
            .choice("oneline",   TestHwutHocon::testOneline)
            .choice("comments",  TestHwutHocon::testComments)
            .choice("refused",   TestHwutHocon::testRefused)
            .choice("triple",    TestHwutHocon::testTriple)
            .choice("unclosed",  TestHwutHocon::testUnclosed)
            .choice("fuzz",      TestHwutHocon::testFuzz)
            .choice("faults",    TestHwutHocon::testFaults)
            .choice("positions", TestHwutHocon::testPositions)
            .run();
    }
}

/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN JAVA -- the port of
 *          'python/hwut_runner.py': the same modes, the same words.
 *
 *     app --hwut-info      the info block; exit 0.
 *     app <choice>         one choice; test output on stdout and stderr,
 *                          '<hwut-end>' after it. '-' runs a choice-less test.
 *     app --interactive    choices started over stdin, output into two named
 *                          sink files per choice, 'done' on the original stdout.
 *     app                  the choice-less test; where the application has
 *                          choices, refused, naming them.
 *
 * USAGE:
 *
 *     final class TestX {
 *         static void plain()  { ... }
 *         static void tricky() { ... }
 *         public static void main(String[] args) {
 *             new HwutRunner(args, "What this tests")
 *                 .choice("plain",  TestX::plain)
 *                 .choice("tricky", TestX::tricky)
 *                 .run();
 *         }
 *     }
 *
 * A choice-less test gives its one function under the name null. Before
 * 'run' a test may set 'happy(...)', 'same(true)' and 'parallel(true)'
 * (interactive: choices run concurrently). 'args' is 'main's own: the
 * program's name is not in it, as it is in Python's 'sys.argv'.
 *
 * THE INTERACTIVE PROTOCOL is Python's, line for line:
 *     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
 *     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
 * EVERY CHOICE RUNS IN A JVM OF ITS OWN -- the command line this one was
 * started with, its arguments replaced by '--hwut-child <choice>' (Java
 * cannot fork): a choice that calls 'System.exit' or crashes ends that
 * choice, not the session, and no choice inherits another's state. Between
 * choices 'System.out' and 'System.err' point at a stray sink, so a stray
 * print never reaches the UP channel.
 *
 * TEXT IS UTF-8 on 'System.out' and 'System.err' whatever the locale says:
 * Python writes UTF-8, and the GOOD files are its.
 * _____________________________________________________________________________
 */
package hwut;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;

public final class HwutRunner {
    /** THE ARGUMENT a session gives the JVM it starts for one choice. */
    public static final String CHILD_FLAG = "--hwut-child";

    private final String[]              args;
    private final String                title;
    private final Map<String, Runnable> choiceMap = new LinkedHashMap<>();
    private final List<String>          happyList = new ArrayList<>();
    private boolean                     sameF;
    private boolean                     parallelF;

    private PrintStream                 control;          // UP channel
    private final AtomicInteger         pendingN = new AtomicInteger();

    /** RETURN: HwutRunner, with no choice yet; 'choice' adds them, 'run'
     *          starts. 'args' is the command line as 'main' receives it,
     *          'title' the info block's title line. */
    public HwutRunner(String[] args, String title) {
        this.args  = args;
        this.title = title;
        installUtf8();
    }

    /** RETURN: HwutRunner, the one choice-less test 'function'. */
    public HwutRunner(String[] args, String title, Runnable function) {
        this(args, title);
        choice(null, function);
    }

    /** RETURN: HwutRunner, the choices of 'choiceMap' (name -> test
     *          function; the key null stands for the choice-less test and
     *          is then the only one). */
    public HwutRunner(String[] args, String title, Map<String, Runnable> choiceMap) {
        this(args, title);
        choiceMap.forEach(this::choice);
    }

    /** RETURN: this; the choice 'name' runs 'function' -- null names the
     *          single choice-less test, which then is the only one. */
    public HwutRunner choice(String name, Runnable function) {
        if (choiceMap.containsKey(null) || (name == null && !choiceMap.isEmpty()))
            throw new IllegalArgumentException("a choice-less test has one function and no choices");
        choiceMap.put(name, function);
        return this;
    }

    /** RETURN: this; 'pattern' adds the info block's 'HAPPY:' lines. */
    public HwutRunner happy(String... pattern) { happyList.addAll(Arrays.asList(pattern)); return this; }

    /** RETURN: this; 'flag' true => the info block carries 'SAME;'. */
    public HwutRunner same(boolean flag) { sameF = flag; return this; }

    /** RETURN: this; 'flag' true => interactive choices run concurrently,
     *          each in its JVM; false (default) => one after the other. */
    public HwutRunner parallel(boolean flag) { parallelF = flag; return this; }

    /** RETURN: never; exits with the status of the mode the command line
     *          selects: 0 after the info block, a choice run, a session
     *          ended; 1 where a choice is missing, unknown, or (alone in
     *          its JVM) threw -- its stack trace on stderr. */
    public void run() {
        String word = args.length > 0 ? args[0] : null;
        int    status;
        if (word != null && List.of("-h", "--hi", "--hwut-info", "--sos", "--wtf").contains(word)) {
            for (String line : infoBlockLines()) System.out.println(line);
            status = 0;
        } else if ("--interactive".equals(word)) {
            status = modeInteractive();
        } else if (CHILD_FLAG.equals(word) && args.length == 2) {
            String name = "-".equals(args[1]) ? null : args[1];
            status = runChoice(name, System.getenv("HWUT_NO_TERMINAL") == null);
        } else if (word == null) {
            if (noneF()) status = runChoice(null, true);
            else {
                System.out.println("error: a choice is required: " + String.join(", ", printableChoiceList())
                                   + " -- name one, or let 'hwut.play' ask.");
                status = 1;
            }
        } else {
            String choice = choiceOfWord(word);
            if (choice != null && choiceMap.containsKey(choice) || choice == null && noneF())
                status = runChoice(choice, true);
            else status = choiceDoesNotExist(word);
        }
        System.out.flush(); System.err.flush();
        System.exit(status);
    }

    // ------------------------------------------------------------- the modes
    /** RETURN: int, 0 where the test function of 'choice' returned -- after
     *          it '<hwut-end>' where 'endF' (R-70); 1 where it threw, its
     *          stack trace on stderr. */
    private int runChoice(String choice, boolean endF) {
        try {
            choiceMap.get(choice).run();
            System.out.flush();
            if (endF) System.out.println("<hwut-end>");
            return 0;
        } catch (Throwable error) {
            System.out.flush();
            error.printStackTrace();
            return 1;
        } finally {
            System.out.flush(); System.err.flush();
        }
    }

    /** RETURN: String, the choice the command-line 'word' names -- the word
     *          itself; null for '-' where the application is choice-less;
     *          'word' unchanged, else. */
    private String choiceOfWord(String word) {
        if (choiceMap.containsKey(word))   return word;
        if (word.equals("-") && noneF())   return null;
        return word;
    }

    /** RETURN: int, 1; the unavailable choice, the available ones and the
     *          closest by Levenshtein distance are said. */
    private int choiceDoesNotExist(String word) {
        if (noneF()) {
            System.out.println("error: '" + word + "': this application has no choices -- call it without one.");
            return 1;
        }
        System.out.println("error: choice '" + word + "' not available.");
        System.out.println("error: available: " + String.join(", ", printableChoiceList()) + ".");
        String suggestion = levenshteinBestMatch(word, sortedChoiceList());
        if (suggestion != null) System.out.println("error: did you mean '" + suggestion + "'?");
        return 1;
    }

    /** RETURN: int, 0 once the session ended ('quit' or end of input) and
     *          every choice it started is reported. The original stdout is
     *          the UP channel; System.out and System.err point at a stray
     *          sink until then. */
    private int modeInteractive() {
        System.out.flush(); System.err.flush();
        control = new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8);
        try {
            Path stray = Files.createTempFile("hwut_stray_", ".txt");
            stray.toFile().deleteOnExit();
            PrintStream sink = new PrintStream(new FileOutputStream(stray.toFile()), true, StandardCharsets.UTF_8);
            System.setOut(sink);
            System.setErr(sink);
        } catch (IOException noTemporaryFile) {
            //  NO STRAY SINK: stray output is dropped -- never into the UP channel.
            PrintStream sink = new PrintStream(java.io.OutputStream.nullOutputStream());
            System.setOut(sink);
            System.setErr(sink);
        }
        try (BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = in.readLine()) != null) {
                line = line.strip();
                if (line.isEmpty()) continue;
                if (!interprete(line)) break;
            }
        } catch (IOException ignored) {
            // end of input
        }
        synchronized (pendingN) {
            while (pendingN.get() > 0) {
                try { pendingN.wait(); } catch (InterruptedException ignored) { break; }
            }
        }
        up("bye");
        return 0;
    }

    /** RETURN: boolean, true where the session goes on; false where it ends.
     *          One DOWN command is interpreted; replies go UP; never throws. */
    private boolean interprete(String line) {
        String[] field = line.split("\\s+");
        if (field.length == 1 && List.of("quit", "q", "exit").contains(field[0])) return false;
        if (field.length == 1 && field[0].equals("info")) {
            for (String infoLine : infoBlockLines()) up("info: " + infoLine);
            up("done - 0");
        } else if (field.length == 4 && field[0].equals("run")) {
            String token = field[1];
            Object[] found = findChoice(token);
            if (found == null) up("fail " + token + " unknown-choice");
            else               runChild(token, (String) found[0], field[2], field[3]);
        } else {
            up("fail - bad-command");
        }
        return true;
    }

    /** RETURN: Object[], { choice } -- the choice 'token' names (by name, by
     *          decimal index into the sorted list, '-' for the choice-less
     *          test; the choice null for that one); null where none. */
    private Object[] findChoice(String token) {
        if (token.equals("-"))            return noneF() ? new Object[] { null } : null;
        if (choiceMap.containsKey(token)) return new Object[] { token };
        if (!token.isEmpty() && token.chars().allMatch(Character::isDigit)) {
            List<String> sorted = sortedChoiceList();
            try {
                int i = Integer.parseInt(token);
                if (i < sorted.size()) return new Object[] { sorted.get(i) };
            } catch (NumberFormatException ignored) { /* too large: no choice */ }
        }
        return null;
    }

    /** RETURN: nothing; the choice runs in a JVM of its own, stdout into
     *          'sinkOut', stderr into 'sinkErr', and 'done <token> <status>'
     *          goes UP when it ended -- before this returns where sequential,
     *          from the JVM's exit handler where parallel. A JVM that cannot
     *          be started is 'done <token> 1', its reason in 'sinkErr'. */
    private void runChild(String token, String choice, String sinkOut, String sinkErr) {
        ProcessBuilder builder = new ProcessBuilder(childCommand(choice == null ? "-" : choice));
        builder.redirectInput(new File("/dev/null"));
        builder.redirectOutput(new File(sinkOut));
        builder.redirectError(new File(sinkErr));
        //  THE JVM'S OWN NOTE ('Picked up JAVA_TOOL_OPTIONS ...') would stand
        //  in the error sink of every choice: the options are kept, the note
        //  is not -- they are handed over on the command line instead.
        String options = builder.environment().remove("JAVA_TOOL_OPTIONS");
        if (options != null && !options.isBlank()) {
            List<String> command = builder.command();
            command.addAll(1, Arrays.asList(options.trim().split("\\s+")));
        }
        Process process;
        try {
            process = builder.start();
        } catch (IOException error) {
            try { Files.writeString(Path.of(sinkErr), error.toString() + "\n"); } catch (IOException ignored) { }
            up("done " + token + " 1");
            return;
        }
        if (parallelF) {
            pendingN.incrementAndGet();
            process.onExit().thenAccept(ended -> {
                up("done " + token + " " + ended.exitValue());
                synchronized (pendingN) { pendingN.decrementAndGet(); pendingN.notifyAll(); }
            });
            return;
        }
        int status;
        while (true) {
            try { status = process.waitFor(); break; } catch (InterruptedException ignored) { }
        }
        up("done " + token + " " + status);
    }

    /** RETURN: List of String, the command line this JVM was started with,
     *          its program arguments replaced by '--hwut-child <choice>'. */
    private List<String> childCommand(String choice) {
        ProcessHandle.Info info = ProcessHandle.current().info();
        List<String> command = new ArrayList<>();
        command.add(info.command().orElse("java"));
        String[] all = info.arguments().orElse(new String[0]);
        command.addAll(Arrays.asList(all).subList(0, Math.max(0, all.length - args.length)));
        command.add(CHILD_FLAG);
        command.add(choice);
        return command;
    }

    /** RETURN: nothing; 'message' and a newline are written and flushed on
     *          the UP channel, whole, whatever thread writes. */
    private void up(String message) {
        synchronized (this) { control.print(message + "\n"); control.flush(); }
    }

    // --------------------------------------------------------------- helpers
    /** RETURN: boolean, true where the application is choice-less. */
    private boolean noneF() { return choiceMap.containsKey(null); }

    /** RETURN: List of String, the choices sorted; for a choice-less
     *          application one null. */
    private List<String> sortedChoiceList() {
        List<String> result = new ArrayList<>();
        if (noneF()) { result.add(null); return result; }
        result.addAll(new TreeMap<>(choiceMap).keySet());
        return result;
    }

    /** RETURN: List of String, the sorted choices; the choice-less one as '-'. */
    private List<String> printableChoiceList() {
        List<String> result = new ArrayList<>();
        for (String c : sortedChoiceList()) result.add(c == null ? "-" : c);
        return result;
    }

    /** RETURN: List of String, the lines of the info block: title, CHOICES,
     *          HAPPY patterns, SAME, INTERACTIVE. */
    private List<String> infoBlockLines() {
        List<String> result = new ArrayList<>();
        result.add(title.endsWith(";") ? title : title + ";");
        if (!noneF()) result.add("CHOICES: " + String.join(", ", sortedChoiceList()) + ";");
        for (String pattern : happyList) result.add("HAPPY: " + pattern + ";");
        if (sameF) result.add("SAME;");
        result.add("INTERACTIVE;");
        return result;
    }

    /** RETURN: nothing; System.out and System.err write UTF-8 to file
     *          descriptors 1 and 2, '\n' ending a line. */
    private static void installUtf8() {
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8));
        System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err), true, StandardCharsets.UTF_8));
    }

    /** RETURN: String, the element of 'haystack' least distant from 'needle'
     *          (the first of equally distant ones; 'needle' itself where it
     *          stands there); null where 'needle' is null or 'haystack' is
     *          empty. */
    public static String levenshteinBestMatch(String needle, List<String> haystack) {
        if (needle == null || haystack.isEmpty()) return null;
        if (haystack.contains(needle))           return needle;
        String best = null;
        int    bestDistance = -1;
        for (String key : haystack) {
            if (key == null) continue;
            int distance = levenshteinDistance(needle, key);
            if (bestDistance < 0 || distance < bestDistance) { bestDistance = distance; best = key; }
        }
        return best;
    }

    /** RETURN: int >= 0, the Levenshtein distance between 'a' and 'b'. */
    public static int levenshteinDistance(String a, String b) {
        if (a.equals(b)) return 0;
        if (a.isEmpty()) return b.length();
        if (b.isEmpty()) return a.length();
        if (a.length() < b.length()) { String t = a; a = b; b = t; }
        int[] previous = new int[b.length() + 1];
        for (int j = 0; j <= b.length(); ++j) previous[j] = j;
        for (int i = 1; i <= a.length(); ++i) {
            int[] current = new int[b.length() + 1];
            current[0] = i;
            for (int j = 1; j <= b.length(); ++j) {
                int insert = current[j - 1] + 1, delete = previous[j] + 1;
                int substitute = previous[j - 1] + (a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1);
                current[j] = Math.min(Math.min(insert, delete), substitute);
            }
            previous = current;
        }
        return previous[b.length()];
    }
}

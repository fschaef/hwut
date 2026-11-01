/* @hwut {
 *     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
 *     build   { framework = "make", executable = "%.exe" }
 *     pype    = "build.pypes"
 *     same    = true
 *     choices = ["serial", "parallel"]
 *     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
 *                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
 *                 "pype-quantity", "pype-anchors-globs-flush"]
 *     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
 * }
 * ______________________________________________________________________________
 * SUBJECT  the log of a recursive build -- configure, then the directories
 *          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
 *          a pype system makes of it.
 * REQUIREMENT  A parallel build builds what the serial build builds: the same
 *              sources, the same warnings, the same archives and the same
 *              program, linked from the same parts.
 *
 * The application only REPORTS the build as it happens, as 'make -w' would.
 * (The build of THIS application -- 'make build.exe' -- is hwut's, before
 * the run; what it prints is no part of the output.) The header's 'pype =
 * "build.pypes"' puts a SYSTEM of two pype scripts between the application
 * and the comparison (hwut runs it; the application prints no '<hwut-end>'):
 *
 *     build.pypes       --> normalise.pype         stdin to the first
 *                       normalise.pype --> build.pype
 *     normalise.pype    a parallel build tags each line with its job,
 *                       'job2: cc -c ...'; the tag goes, every other line
 *                       passes unchanged ('flush')
 *     build.pype        the summary, sorted -- see its own comments: modes
 *                       pushed on 'Entering directory' and popped on
 *                       'Leaving' (nested: 'app/plugins' inside 'app'),
 *                       '<entry>'/'<exit>' around each, a vocabulary
 *                       imported from 'compiler.pype', a repeat group over
 *                       the parts of a link, durations read as quantities
 *
 * 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.java.txt'. Serial
 * or parallel, the summary must be the same -- that is the requirement, and
 * the header says it once. 'choices' is a list: no choice states anything
 * of its own.
 *
 * The laws: the compile times sum to under 5 s ('((compile: ...))', in
 * s, whatever unit the log used), and nothing in the log broke the build's
 * grammar ('((breaches: 0))').
 *
 * A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
 * Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
 * build here; a pype that judges time is fed live ('protocol.sh slow').
 * ______________________________________________________________________________
 */
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

final class Build {
    /** What one directory does: its sources, warnings and product. */
    record Directory(List<String> sourceList, Map<String, String> warningDb, String product) {}

    static final Random RANDOM = new Random(System.nanoTime());
    static final Map<String, Directory> DIRECTORY_DB = Map.of(
        "lib",         new Directory(List.of("lib/str.c", "lib/num.c", "lib/map.c"),
                                     Map.of("lib/num.c", "lib/num.c:14:9: warning: unused variable 'n'"),
                                     "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"),
        "app/plugins", new Directory(List.of("app/plugins/png.c", "app/plugins/svg.c"),
                                     Map.of("app/plugins/svg.c", "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"),
                                     "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"),
        "app",         new Directory(List.of("app/main.c", "app/cli.c"),
                                     Map.of(),
                                     "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a"));

    /** RETURN: List of String, what building directory 'name' prints, its
     *          sources compiled in the time each takes. */
    static List<String> compileLines(String name) {
        Directory spec = DIRECTORY_DB.get(name);
        List<String> lineList = new ArrayList<>();
        for (String source : spec.sourceList()) {
            double took = 0.04 + 0.08 * RANDOM.nextDouble();
            try { Thread.sleep((long) (took * 1000.0)); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
            String spent = took < 0.1 ? (int) (took * 1000) + " ms" : String.format(Locale.ROOT, "%.2f s", took);
            String object = source.substring(0, source.length() - 2) + ".o";
            lineList.add("cc -c " + source + " -o " + object + " (took " + spent + ")");
            if (spec.warningDb().containsKey(source)) lineList.add(spec.warningDb().get(source));
        }
        return lineList;
    }

    /** RETURN: List of String, the block 'make -w' prints for 'name' at
     *          'level', the block of 'inner' (null: none) nested before the
     *          product. */
    static List<String> directoryBlock(String name, int level, String inner) {
        List<String> lineList = new ArrayList<>();
        lineList.add("make[" + level + "]: Entering directory '" + name + "'");
        lineList.addAll(compileLines(name));
        if (inner != null) lineList.addAll(directoryBlock(inner, level + 1, null));
        lineList.add(DIRECTORY_DB.get(name).product());
        lineList.add("make[" + level + "]: Leaving directory '" + name + "'");
        return lineList;
    }

    /** RETURN: nothing; what 'configure' prints, and that make enters the
     *          top directory, is printed. */
    static void configure() {
        System.out.println("configure: checking for cc... cc");
        System.out.println("configure: checking for ar... ar");
        System.out.println("make: Entering directory 'demo'");
    }

    /** RETURN: nothing; one directory was built after the other. */
    static void serial() {
        configure();
        List<String> lineList = new ArrayList<>(directoryBlock("lib", 1, null));
        lineList.addAll(directoryBlock("app", 1, "app/plugins"));
        for (String line : lineList) { System.out.println(line); System.out.flush(); }
        System.out.println("make: Leaving directory 'demo'");
    }

    /** RETURN: nothing; 'lib' and 'app' were built at once. Each job printed
     *          its block whole when done ('make -O'), every line tagged with
     *          the job; which job finishes first is the scheduler's. */
    static void parallel() {
        configure();
        Object lock = new Object();
        List<Thread> pool = new ArrayList<>();
        String[][] jobList = { { "1", "lib", null }, { "2", "app", "app/plugins" } };
        for (String[] job : jobList) {
            pool.add(new Thread(() -> {
                List<String> block = directoryBlock(job[1], 1, job[2]);
                synchronized (lock) {
                    for (String line : block) { System.out.println("job" + job[0] + ": " + line); System.out.flush(); }
                }
            }));
        }
        for (Thread t : pool) t.start();
        for (Thread t : pool) {
            try { t.join(); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        }
        System.out.println("make: Leaving directory 'demo'");
    }

    public static void main(String[] args) {
        Map<String, Runnable> choiceDb = new LinkedHashMap<>();
        choiceDb.put("serial",   Build::serial);
        choiceDb.put("parallel", Build::parallel);
        String choice = args.length > 0 ? args[0] : "";
        if (!choiceDb.containsKey(choice)) {
            System.out.println("choices: " + String.join(", ", choiceDb.keySet()));
            System.exit(1);
        }
        choiceDb.get(choice).run();
    }
}

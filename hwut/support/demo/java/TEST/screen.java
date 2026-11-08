/* @hwut {
 *     title     = "Demo: a terminal program's screen, as a person sees it"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { regions    = false
 *                 comment    = false
 *                 whitespace = false }
 *     choices {
 *         open   { features = ["terminal-screen", "screen-as-seen"] }
 *         scroll { features = ["terminal-screen", "screen-as-seen"] }
 *     }
 * }
 * ______________________________________________________________________________
 * SUBJECT  the screen of 'viewer.java', a full-screen file viewer, run in a
 *          terminal of 9 rows and 40 columns and driven by its keys.
 * REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
 *              as they fit, and a status line -- the keys flush left, the lines
 *              shown flush right; 'j' and the down key go one line further,
 *              'k' one back.
 *
 * 'VtermTerminal' runs the viewer ('viewer.exe', which the Makefile builds
 * with this test) on a pseudo-terminal: the viewer cannot tell it from a
 * real one. The test PRESSES KEYS and is told what CHANGED: three regions
 * are declared -- title, body, status -- and after every key, once the
 * viewer has gone quiet, each region whose text changed is printed. A
 * redraw that changes nothing is not told: the title is told once.
 *
 * THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
 * off, in the header:
 *
 *     regions = false     the file shown is a GOOD file of hwut, with a
 *                         '##! potpourri' ... '####' block. On this screen
 *                         those are characters, not a region to open.
 *     comment = false     '## ...' lines are characters too, not notes.
 *     whitespace = false  the status line's two halves stand flush left and
 *                         flush right: every blank between them counts. A
 *                         half moved by one column is red. (A line's leading
 *                         and trailing blanks are stripped all the same.)
 *
 * libvterm must be installed ('apt install libvterm0'); where it is not, the
 * test prints why and probes nothing -- its output differs from GOOD and the
 * reason stands in the difference.
 *
 * CHOICES  open    the viewer opened, then quit.
 *          scroll  down, down, 'j', then 'k': three lines on, one back.
 * ______________________________________________________________________________
 */
import hwut.LibraryMissing;
import hwut.VtermCell;
import hwut.VtermTerminal;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class Screen {
    static final Path   HERE   = here();
    static final String SAMPLE = String.join("\n",
        "## demo.py race -- three workers",
        "start",
        "##! potpourri",
        "worker B done: 5 jobs",
        "worker A done: 3 jobs",
        "worker C done: 2 jobs",
        "####",
        "all joined",
        "## the order between the markers is",
        "## free; the lines are not.") + "\n";

    /** RETURN: Path, the directory this test stands in -- the parent of the
     *          classes directory it runs from. */
    static Path here() {
        try { return Path.of(Screen.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParent(); }
        catch (URISyntaxException error) { throw new IllegalStateException(error); }
    }

    /** RETURN: nothing; one region that changed is printed, its rows as they
     *          stand on the screen, from the first column. */
    static void show(String name, List<String> lineList) {
        System.out.println("-- " + name);
        for (String line : lineList) System.out.println(line);
    }

    /** RETURN: nothing; the viewer ran on the sample, 'keyList' was pressed,
     *          the viewer quit, and what changed after each step is printed. */
    static void view(List<String> keyList) throws IOException {
        Path path = HERE.resolve("TMP").resolve("race.txt");
        Files.createDirectories(path.getParent());
        Files.writeString(path, SAMPLE, StandardCharsets.UTF_8);
        try (VtermTerminal terminal = new VtermTerminal(9, 40)) {
            terminal.region("title",  0);
            terminal.region("body",   1, 7);
            terminal.region("status", -1);
            terminal.onChange(Screen::show);
            System.out.println("> viewer.exe race.txt");
            terminal.run(List.of(HERE.resolve("viewer.exe").toString(), path.toString()));
            VtermCell cell = terminal.cell(0, 1);
            String attribute = cell.attributeText();
            System.out.println("title bar: " + (attribute.isEmpty() ? "plain" : attribute));
            for (String key : keyList) {
                System.out.println("> " + key);
                if (key.length() == 1) terminal.send(key);
                else                   terminal.press(key);
            }
            terminal.send("q");
            System.out.println("> q -- exit status " + terminal.waitFor());
        }
    }

    public static void main(String[] args) throws IOException {
        Map<String, List<String>> choiceDb = new LinkedHashMap<>();
        choiceDb.put("open",   List.of());
        choiceDb.put("scroll", List.of("down", "down", "j", "k"));
        String choice = args.length > 0 ? args[0] : "";
        if (!choiceDb.containsKey(choice)) {
            System.out.println("choices: " + String.join(", ", choiceDb.keySet()));
            System.exit(1);
        }
        try {
            view(choiceDb.get(choice));
        } catch (LibraryMissing error) {
            System.out.println(error.getMessage());
            System.exit(1);
        }
        System.out.println("<hwut-end>");
    }
}

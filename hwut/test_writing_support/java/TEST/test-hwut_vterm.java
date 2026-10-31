/* @hwut {
 *     title      = "A terminal's screen read by a test: libvterm through the Foreign Function & Memory API."
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         attributes { features = ["java-vterm"] }
 *         colours    { features = ["java-vterm"] }
 *         events     { features = ["java-vterm"] }
 *         keys       { features = ["java-vterm"] }
 *         missing    { features = ["java-vterm"] }
 *         regions    { features = ["java-vterm"] }
 *         screen     { features = ["java-vterm"] }
 *         text       { features = ["java-vterm"] }
 *         unnoticed  { features = ["java-vterm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-hwut_vterm.py', choice for
 *          choice, held against its GOOD files by '.link'. WANTS libvterm --
 *          found at run time, no header needed to build. The two APPLICATIONS
 *          a terminal runs here are the Python test's, unchanged, run by
 *          'python3 -c': they are the system under test, and what they print
 *          is in the shared GOOD files.
 * _____________________________________________________________________________
 */
import hwut.HwutRunner;
import hwut.LibraryMissing;
import hwut.PyText;
import hwut.Vterm;
import hwut.VtermCell;
import hwut.VtermScreen;
import hwut.VtermTerminal;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

final class TestHwutVterm {
    static final String ESC = "\u001b";

    /** RETURN: nothing; every row that holds something, framed, then the
     *          cursor. */
    static void shown(VtermScreen screen) {
        List<String> lineList = screen.lineList();
        for (int row = 0; row < lineList.size(); ++row)
            if (!lineList.get(row).isEmpty()) System.out.println("    " + row + " |" + lineList.get(row) + "|");
        System.out.println("    cursor " + screen.cursor());
    }

    /** RETURN: Runnable, 'function' run on a library that is there; one line
     *          where it is not. */
    static Runnable probe(Runnable function) {
        return () -> {
            try {
                function.run();
            } catch (LibraryMissing error) {
                System.out.println("NOT PROBED: " + error.getMessage());
            }
        };
    }

    static void runText() {
        try (VtermScreen screen = new VtermScreen(4, 12)) {
            System.out.println("-- plain, then carriage return and line feed");
            screen.feed("hello\r\nworld");
            shown(screen);
        }
        try (VtermScreen screen = new VtermScreen(4, 12)) {
            System.out.println("-- UTF-8: two bytes, one cell; a wide character, two");
            screen.feed("ä日x");
            shown(screen);
            for (int column = 0; column < 4; ++column) {
                VtermCell cell = screen.cell(0, column);
                System.out.println("    column " + column + ": " + PyText.ljust(PyText.strRepr(cell.text()), 6)
                                   + " width " + cell.width());
            }
        }
        try (VtermScreen screen = new VtermScreen(3, 5)) {
            System.out.println("-- seven characters on five columns: the line wraps");
            screen.feed("abcdefg");
            shown(screen);
        }
        try (VtermScreen screen = new VtermScreen(2, 4)) {
            System.out.println("-- a str is sent as UTF-8; the bytes taken are counted");
            System.out.println("    taken: " + screen.feed("aä"));
            System.out.println("-- a place off the screen");
            try {
                screen.cell(2, 0);
            } catch (IndexOutOfBoundsException error) {
                System.out.println("    IndexError: " + error.getMessage());
            }
        }
    }

    static void runScreen() {
        try (VtermScreen screen = new VtermScreen(5, 20)) {
            System.out.println("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'");
            screen.feed("first line\r\nsecond line\r\nthird line");
            screen.feed(ESC + "[2;4H" + "X");
            shown(screen);
            System.out.println("-- erase to the end of that line");
            screen.feed(ESC + "[K");
            shown(screen);
            System.out.println("-- clear the screen, home, one word");
            screen.feed(ESC + "[2J" + ESC + "[H" + "clean");
            shown(screen);
        }
    }

    static void runAttributes() {
        try (VtermScreen screen = new VtermScreen(3, 20)) {
            for (Map.Entry<String, String> e : Vterm.ATTRIBUTE_SGR_DB.entrySet())
                screen.feed(ESC + "[" + e.getValue() + "m" + e.getKey().charAt(0) + ESC + "[0m");
            System.out.println("-- one cell per attribute, set by its own code");
            int column = 0;
            for (String name : Vterm.ATTRIBUTE_SGR_DB.keySet()) {
                VtermCell cell = screen.cell(0, column++);
                //  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
                String said = cell.attributeText().isEmpty() ? "(none)" : cell.attributeText();
                if (name.equals("conceal")) said = "conceal, or (none) on libvterm 0.1";
                System.out.println("    " + PyText.strRepr(cell.text()) + "  " + said);
            }
            System.out.println("-- bold, underline and reverse at once; then reset");
            screen.feed("\r\n" + ESC + "[1;4;7mA" + ESC + "[0mB");
            for (int at = 0; at < 2; ++at) {
                VtermCell cell = screen.cell(1, at);
                System.out.println("    " + PyText.strRepr(cell.text()) + "  "
                                   + (cell.attributeText().isEmpty() ? "(none)" : cell.attributeText()));
            }
            System.out.println("-- double underline (SGR 21) is underlined");
            screen.feed(ESC + "[21mD");
            System.out.println("    " + PyText.strRepr("D") + "  " + screen.cell(1, 2).attributeText());
        }
    }

    static void runColours() {
        try (VtermScreen screen = new VtermScreen(2, 20)) {
            screen.feed("d" + ESC + "[31mr" + ESC + "[0m" + ESC + "[38;5;196mp" + ESC + "[0m" + ESC + "[38;2;10;20;30mt" + ESC + "[0m");
            screen.feed(ESC + "[48;2;1;2;3mb" + ESC + "[0m");
            String[] what = { "default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3" };
            for (int column = 0; column < what.length; ++column) {
                VtermCell cell = screen.cell(0, column);
                String said;
                //  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
                //  is a colour and mostly red is the claim, not its shade.
                if (what[column].equals("indexed 31")) {
                    VtermCell.Rgb fg = cell.foreground();
                    said = "fg mostly red: " + PyText.bool(fg.red() > 2 * Math.max(fg.green(), fg.blue()));
                } else {
                    said = "fg " + PyText.repr(cell.foreground()) + "  bg " + PyText.repr(cell.background());
                }
                System.out.println("    " + PyText.ljust(what[column], 18) + " " + PyText.strRepr(cell.text()) + "  " + said);
            }
        }
    }

    //  THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for
    //  word: the system under test is the same, so the GOOD files can be.
    static final String SEEING_APP = ""
        + "\n"
        + "import os, sys, tty, termios\n"
        + "print(\"streams are terminals: %s %s %s\"\n"
        + "      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))\n"
        + "try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")\n"
        + "except OSError: print(\"controlling terminal: no\")\n"
        + "print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))\n"
        + "print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))\n"
        + "old = termios.tcgetattr(0); tty.setraw(0)\n"
        + "sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()\n"
        + "reply = b\"\"\n"
        + "while not reply.endswith(b\"R\"): reply += os.read(0, 1)\n"
        + "sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()\n"
        + "while True:\n"
        + "    key = os.read(0, 32)\n"
        + "    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()\n"
        + "    if key == b\"q\": break\n"
        + "termios.tcsetattr(0, termios.TCSADRAIN, old)\n"
        + "print(\"\\r\\nleaving\"); sys.exit(3)\n";

    static final String DRAWING_APP = ""
        + "\n"
        + "import os, sys, tty, termios\n"
        + "old = termios.tcgetattr(0); tty.setraw(0)\n"
        + "count, foot = 0, \"q=quit\"\n"
        + "def draw():\n"
        + "    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\"\n"
        + "    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count\n"
        + "    out += \"\\x1b[8;1H%s\" % foot\n"
        + "    sys.stdout.write(out); sys.stdout.flush()\n"
        + "draw()\n"
        + "while True:\n"
        + "    key = os.read(0, 1)\n"
        + "    if   key == b\"n\": count += 1\n"
        + "    elif key == b\"f\": foot = \"q=quit  f=pressed\"\n"
        + "    elif key == b\"q\": break\n"
        + "    draw()\n"
        + "termios.tcsetattr(0, termios.TCSADRAIN, old)\n";

    static List<String> python(String program) { return List.of("python3", "-c", program); }

    static void runUnnoticed() {
        Map<String, String> environment = new HashMap<>(System.getenv());
        environment.put("COLUMNS", "300");
        try (VtermTerminal terminal = new VtermTerminal(10, 44)) {
            boolean running = terminal.run(python(SEEING_APP), environment, null, 10.0);
            System.out.println("-- still running after its first screen: " + PyText.bool(running));
            shown(terminal);
            terminal.send("q");
            System.out.println("-- after 'q': exit status " + terminal.waitFor());
            shown(terminal);
        }
    }

    static void runKeys() {
        try (VtermTerminal terminal = new VtermTerminal(10, 44)) {
            String[] pressed = { "(start)" };
            terminal.region("read", 8);
            terminal.onChange((name, lineList) -> System.out.println("    " + PyText.ljust(pressed[0], 22) + " " + lineList.get(0)));
            terminal.run(python(SEEING_APP));
            String[][] keyList = { { "up" }, { "enter" }, { "tab" }, { "escape" }, { "f5" }, { "delete" },
                                   { "c", "ctrl" }, { "x", "alt" }, { "up", "shift" } };
            for (String[] key : keyList) {
                List<String> word = new ArrayList<>();
                for (int i = 1; i < key.length; ++i) word.add(key[i]);
                word.add(key[0]);
                pressed[0] = String.join(" ", word);
                terminal.press(key[0], java.util.Arrays.copyOfRange(key, 1, key.length));
            }
            pressed[0] = "send 'ä'";
            terminal.send("ä");
            pressed[0] = "send 'q'";
            terminal.send("q");
            terminal.waitFor();
        }
    }

    static void runRegions() {
        //  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
        //  ONE report on a loaded machine too.
        try (VtermTerminal terminal = new VtermTerminal(8, 30, 0.3)) {
            terminal.region("head", 0);
            terminal.region("body", 2, 2);
            terminal.region("foot", -1);
            terminal.onChange((name, lineList) -> System.out.println("    changed  " + PyText.ljust(name, 5) + " " + PyText.repr(lineList)));
            System.out.println("-- run");
            terminal.run(python(DRAWING_APP));
            String[][] act = { { "'n'", "n" }, { "'n'", "n" }, { "'r': a redraw, nothing new", "r" }, { "'f'", "f" },
                               { "'nnn', typed at once", "nnn" }, { "'q'", "q" } };
            for (String[] a : act) {
                System.out.println("-- " + a[0]);
                terminal.send(a[1]);
            }
            Integer status = terminal.waitFor();
            System.out.println("-- exit status " + status + "; a region asked by name: " + PyText.repr(terminal.regionText("body")));
            try {
                terminal.regionText("nosuch");
            } catch (NoSuchElementException error) {
                System.out.println("-- no such region: KeyError " + error.getMessage());
            }
        }
    }

    static void runEvents() {
        try (VtermTerminal terminal = new VtermTerminal(4, 20)) {
            terminal.onEvent(event -> System.out.println("    " + event));
            String[][] fed = { { "'ab'", "ab" }, { "a line feed and 'c'", "\r\nc" },
                               { "the cursor to row 4, hidden", ESC + "[4;1H" + ESC + "[?25l" },
                               { "the alternate screen", ESC + "[?1049h" }, { "the bell", "\u0007" },
                               { "nothing that draws: a reset of attributes", ESC + "[0m" } };
            for (String[] f : fed) {
                System.out.println("-- fed: " + f[0]);
                terminal.feed(f[1]);
            }
            System.out.println("-- asked where the cursor is, nobody running: the answer waits");
            terminal.feed(ESC + "[2;5H" + ESC + "[6n");
            System.out.println("    answer() = " + PyText.bytesRepr(terminal.answer()));
            System.out.println("-- a key pressed with nobody running");
            terminal.press(0, "f1");
            System.out.println("    answer() = " + PyText.bytesRepr(terminal.answer()));
        }
    }

    static void runMissing() {
        Vterm.resetLibrary("/nowhere/libvterm.so");
        try (VtermScreen screen = new VtermScreen()) {
            System.out.println("a Screen stands on a library that is not there");
        } catch (LibraryMissing error) {
            //  THE SYSTEM'S OWN WORDS for the failed load are left out; what
            //  this module says -- the line, and the way to install -- stands.
            String[] lineList = error.getMessage().split("\n", -1);
            System.out.println("LibraryMissing: " + lineList[0].split(" -- ", -1)[0]);
            for (int i = 1; i < lineList.length; ++i) System.out.println(lineList[i]);
        }
    }

    public static void main(String[] args) {
        new HwutRunner(args, "A terminal's screen read by a test: libvterm through the Foreign Function & Memory API.")
            .choice("text",       probe(TestHwutVterm::runText))
            .choice("screen",     probe(TestHwutVterm::runScreen))
            .choice("attributes", probe(TestHwutVterm::runAttributes))
            .choice("colours",    probe(TestHwutVterm::runColours))
            .choice("unnoticed",  probe(TestHwutVterm::runUnnoticed))
            .choice("keys",       probe(TestHwutVterm::runKeys))
            .choice("regions",    probe(TestHwutVterm::runRegions))
            .choice("events",     probe(TestHwutVterm::runEvents))
            .choice("missing",    TestHwutVterm::runMissing)
            .run();
    }
}

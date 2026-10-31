/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: libvterm, FOUND AND MEASURED -- the module part of
 *          'python/hwut_vterm.py' (README-hwut_vterm.txt): the library loaded
 *          once at run time through the Foreign Function & Memory API, the
 *          layout of its cell measured once, and the tables a test presses
 *          keys and reads attributes by. The classes a test uses are
 *          'VtermScreen' and 'VtermTerminal'.
 *
 * THE LIBRARY IS FOUND, NOT SHIPPED: the file HWUT_LIBVTERM names, else the
 * system's 'libvterm.so.0' (Debian: 'libvterm0'). Where neither loads, a
 * VtermScreen throws 'LibraryMissing', whose text says how to install it.
 * NO HEADER IS NEEDED: the few structures are declared here, as the Python
 * binding declares them for 'ctypes'.
 *
 * THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED: libvterm's 'VTermScreenCell'
 * changed between versions ('strike' is bit 0x40 in 0.1 and 0x80 from 0.2
 * on). Once per library a scratch terminal is fed one attribute at a time and
 * the bit or the bytes that changed are where that attribute stands.
 *
 *     java ... hwut.Vterm         says whether the library is there (exit 0/1)
 * _____________________________________________________________________________
 */
package hwut;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.StructLayout;
import java.lang.foreign.SymbolLookup;
import java.lang.invoke.MethodHandle;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;

public final class Vterm {
    /** THE ENVIRONMENT VARIABLE that names the library's file. */
    public static final String LIBRARY_VARIABLE = "HWUT_LIBVTERM";

    //  WHAT IS THE SAME IN EVERY VERSION: six code points of four bytes, then
    //  the width; everything behind them is measured.
    static final int CHARS_PER_CELL_N = 6;
    static final int CHARS_BYTE_N     = 4 * CHARS_PER_CELL_N;
    static final int CELL_BYTE_N      = 128;                 // room beyond any version's cell

    /** THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets
     *  it -- in this order everywhere. */
    public static final Map<String, String> ATTRIBUTE_SGR_DB = ordered(
        "bold", "1", "italic", "3", "underline", "4", "blink", "5", "reverse", "7", "conceal", "8", "strike", "9");

    /** WHAT A PERSON IS TOLD where the library is not found. */
    public static final String INSTALL_HINT = String.join("\n",
        "HINT: install the library, or name its file:",
        "    Debian, Ubuntu   apt install libvterm0",
        "    Fedora           dnf install libvterm",
        "    Arch             pacman -S libvterm",
        "    macOS            brew install libvterm",
        "    elsewhere        export " + LIBRARY_VARIABLE + "=<path>/libvterm.so",
        "    or work inside   hwut.dev.podman.enter   (the image holds it)");

    /** THE PROPERTIES A TERMINAL REPORTS, by libvterm's number: name, and
     *  whether the value is a flag or a number (a title's text is not
     *  carried). */
    static final Map<Integer, Object[]> PROPERTY_DB = Map.of(
        1, new Object[] { "cursor-visible", true },  2, new Object[] { "cursor-blink", true },
        3, new Object[] { "alternate-screen", true }, 4, new Object[] { "title", false },
        5, new Object[] { "icon-name", false },       6, new Object[] { "reverse-video", true },
        7, new Object[] { "cursor-shape", true },     8, new Object[] { "mouse", true },
        9, new Object[] { "focus-report", true });

    /** THE KEYS THAT ARE NOT A CHARACTER, by the name a test presses them
     *  under ('VTermKey'; function keys 'f1'..'f12' stand at 256 + n). */
    public static final Map<String, Integer> KEY_DB = keyDb();
    /** THE MODIFIERS, by name. */
    public static final Map<String, Integer> MODIFIER_DB = Map.of("shift", 1, "alt", 2, "ctrl", 4);

    //  'VTERM_DAMAGE_ROW': damage is told per row, once the terminal is
    //  flushed -- not per cell as it happens.
    static final int DAMAGE_MERGE_ROW = 1;

    /** 'VTermPos', passed by value: a row and a column. */
    static final StructLayout POSITION = MemoryLayout.structLayout(JAVA_INT.withName("row"), JAVA_INT.withName("col"));
    /** 'VTermRect', passed by value: rows and columns, the ends EXCLUDED. */
    static final StructLayout RECTANGLE = MemoryLayout.structLayout(
        JAVA_INT.withName("start_row"), JAVA_INT.withName("end_row"),
        JAVA_INT.withName("start_col"), JAVA_INT.withName("end_col"));

    /** THE LOADED LIBRARY: its name and its functions. */
    static final class Library {
        final String       name;
        final MethodHandle vtermNew, vtermFree, setUtf8, inputWrite, obtainScreen, obtainState, screenReset,
                           enableAltscreen, getCell, getCursorpos, outputSetCallback, keyboardUnichar,
                           keyboardKey, setCallbacks, setDamageMerge, flushDamage, convertColorToRgb;

        /** RETURN: Library, every function of 'lookup' declared, if success;
         *          throws LibraryMissing naming the function missing, else. */
        Library(String name, SymbolLookup lookup) {
            this.name = name;
            vtermNew          = down(lookup, "vterm_new",                     FunctionDescriptor.of(ADDRESS, JAVA_INT, JAVA_INT));
            vtermFree         = down(lookup, "vterm_free",                    FunctionDescriptor.ofVoid(ADDRESS));
            setUtf8           = down(lookup, "vterm_set_utf8",                FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT));
            inputWrite        = down(lookup, "vterm_input_write",             FunctionDescriptor.of(JAVA_LONG, ADDRESS, ADDRESS, JAVA_LONG));
            obtainScreen      = down(lookup, "vterm_obtain_screen",           FunctionDescriptor.of(ADDRESS, ADDRESS));
            obtainState       = down(lookup, "vterm_obtain_state",            FunctionDescriptor.of(ADDRESS, ADDRESS));
            screenReset       = down(lookup, "vterm_screen_reset",            FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT));
            enableAltscreen   = down(lookup, "vterm_screen_enable_altscreen", FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT));
            getCell           = down(lookup, "vterm_screen_get_cell",         FunctionDescriptor.of(JAVA_INT, ADDRESS, POSITION, ADDRESS));
            getCursorpos      = down(lookup, "vterm_state_get_cursorpos",     FunctionDescriptor.ofVoid(ADDRESS, ADDRESS));
            outputSetCallback = down(lookup, "vterm_output_set_callback",     FunctionDescriptor.ofVoid(ADDRESS, ADDRESS, ADDRESS));
            keyboardUnichar   = down(lookup, "vterm_keyboard_unichar",        FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT, JAVA_INT));
            keyboardKey       = down(lookup, "vterm_keyboard_key",            FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT, JAVA_INT));
            setCallbacks      = down(lookup, "vterm_screen_set_callbacks",    FunctionDescriptor.ofVoid(ADDRESS, ADDRESS, ADDRESS));
            setDamageMerge    = down(lookup, "vterm_screen_set_damage_merge", FunctionDescriptor.ofVoid(ADDRESS, JAVA_INT));
            flushDamage       = down(lookup, "vterm_screen_flush_damage",     FunctionDescriptor.ofVoid(ADDRESS));
            //  ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
            convertColorToRgb = lookup.find("vterm_screen_convert_color_to_rgb")
                                      .map(a -> Linker.nativeLinker().downcallHandle(a, FunctionDescriptor.ofVoid(ADDRESS, ADDRESS)))
                                      .orElse(null);
        }

        /** RETURN: MethodHandle, the library's 'function' as 'descriptor'
         *          says; throws LibraryMissing where the library has none. */
        private MethodHandle down(SymbolLookup lookup, String function, FunctionDescriptor descriptor) {
            MemorySegment address = lookup.find(function).orElseThrow(() -> new LibraryMissing(
                "libvterm cannot be loaded from '" + name + "' -- no function '" + function + "'\n" + INSTALL_HINT));
            return Linker.nativeLinker().downcallHandle(address, descriptor);
        }

        /** RETURN: Object, what the library's 'function' returned for
         *          'argument'; a failure of the call itself is a defect of
         *          this binding and thrown as an Error. */
        Object call(MethodHandle function, Object... argument) {
            try {
                return function.invokeWithArguments(argument);
            } catch (RuntimeException | Error error) {
                throw error;
            } catch (Throwable error) {
                throw new AssertionError("libvterm call failed: " + error, error);
            }
        }
    }

    /** WHERE A CELL'S FIELDS STAND in this library's 'VTermScreenCell'. */
    record Layout(Map<String, int[]> maskDb,        // attribute -> { byte offset, bit mask }
                  int foregroundI, int backgroundI, // offsets of the colours' red bytes
                  boolean convertF,                 // colours pass 'convert_color_to_rgb' first
                  byte[] defaultFg, byte[] defaultBg) {}

    private static Library library;               // the loaded library, once
    private static Layout  layout;                // its measured layout, once
    private static String  fileOverride;          // 'resetLibrary's word over HWUT_LIBVTERM

    private Vterm() {}

    /** RETURN: String, 'libvterm found: <name>' where the library loads; the
     *          text of 'LibraryMissing' -- what is wrong and how to install
     *          it -- else. */
    public static String detectionText() {
        try {
            return "libvterm found: " + library().name;
        } catch (LibraryMissing error) {
            return error.getMessage();
        }
    }

    /** RETURN: nothing; the loaded library (and its measured layout) is
     *  forgotten; the next one is loaded from 'file' -- as though
     *  HWUT_LIBVTERM named it (Java cannot set its own environment); null:
     *  as HWUT_LIBVTERM and the system say. */
    public static synchronized void resetLibrary(String file) {
        library      = null;
        layout       = null;
        fileOverride = file;
    }

    /** RETURN: Library, libvterm loaded once and its functions declared;
     *          throws LibraryMissing, where no such library is found. */
    static synchronized Library library() {
        if (library != null) return library;
        String file = fileOverride != null ? fileOverride : System.getenv(LIBRARY_VARIABLE);
        if (file != null && !file.isEmpty()) {
            SymbolLookup lookup;
            try {
                lookup = SymbolLookup.libraryLookup(file, Arena.global());
            } catch (IllegalArgumentException error) {
                throw new LibraryMissing("libvterm cannot be loaded from '" + file + "' -- " + error.getMessage()
                                         + "\n" + INSTALL_HINT);
            }
            library = new Library(file, lookup);
            return library;
        }
        for (String candidate : List.of("libvterm.so.0", "libvterm.so", "libvterm.0.dylib", "libvterm.dylib")) {
            try {
                SymbolLookup lookup = SymbolLookup.libraryLookup(candidate, Arena.global());
                library = new Library(candidate, lookup);
                return library;
            } catch (IllegalArgumentException notThere) {
                // the next name
            }
        }
        throw new LibraryMissing("libvterm is not installed, and '" + LIBRARY_VARIABLE + "' names no file\n" + INSTALL_HINT);
    }

    /** RETURN: Layout, the measured one; null while it is being measured. */
    static synchronized Layout layoutOrNull() { return layout; }

    /** RETURN: Layout, where this library's cell keeps each attribute and
     *          each colour -- measured once on a scratch terminal, then
     *          remembered; throws LibraryMissing where there is no library. */
    static synchronized Layout measured() {
        if (layout != null) return layout;
        byte[] plain = cellAfter("");
        Map<String, int[]> maskDb = new LinkedHashMap<>();
        for (Map.Entry<String, String> e : ATTRIBUTE_SGR_DB.entrySet()) {
            List<int[]> found = changed(plain, cellAfter(e.getValue()));
            //  NOTHING MOVED: this library does not know the attribute.
            maskDb.put(e.getKey(), found.isEmpty() ? new int[] { CHARS_BYTE_N + 1, 0 } : found.get(0));
        }
        //  UNDERLINE IS A NUMBER OF TWO BITS (single, double, curly): any of
        //  them is 'underlined', so the double's bit joins the mask.
        for (int[] change : changed(plain, cellAfter("21"))) {
            int[] underline = maskDb.get("underline");
            if (change[0] == underline[0]) maskDb.put("underline", new int[] { underline[0], underline[1] | change[1] });
        }
        int foregroundI = colourAt("38"), backgroundI = colourAt("48");
        boolean convertF = library().convertColorToRgb != null;
        //  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be
        //  read from now on.
        layout = new Layout(maskDb, foregroundI, backgroundI, convertF, new byte[0], new byte[0]);
        byte[] raw;
        try (VtermScreen scratch = new VtermScreen(2, 4)) {
            scratch.feed("X");
            raw = scratch.raw(0, 0);
        }
        layout = new Layout(Collections.unmodifiableMap(maskDb), foregroundI, backgroundI, convertF,
                            Arrays.copyOfRange(raw, foregroundI, foregroundI + 3),
                            Arrays.copyOfRange(raw, backgroundI, backgroundI + 3));
        return layout;
    }

    /** RETURN: byte[], the raw cell (0, 0) of a fresh terminal after
     *          '<esc>[<sequence>m' (nothing for "") and one 'X' -- unconverted. */
    private static byte[] cellAfter(String sequence) {
        try (VtermScreen scratch = new VtermScreen(2, 4)) {
            scratch.feed(sequence.isEmpty() ? "" : "\u001b[" + sequence + "m");
            scratch.feed("X");
            return scratch.raw(0, 0);
        }
    }

    /** RETURN: List of { offset, bits }, every byte behind the width in which
     *          'raw' differs from 'plain'. */
    private static List<int[]> changed(byte[] plain, byte[] raw) {
        List<int[]> result = new java.util.ArrayList<>();
        for (int i = CHARS_BYTE_N + 1; i < Math.min(plain.length, raw.length); ++i)
            if (plain[i] != raw[i]) result.add(new int[] { i, (plain[i] ^ raw[i]) & 0xFF });
        return result;
    }

    /** RETURN: int, the offset of the red byte of the colour '<code>;2;1;2;3'
     *          sets; throws IllegalStateException where it stands nowhere. */
    private static int colourAt(String code) {
        byte[] raw = cellAfter(code + ";2;1;2;3");
        for (int i = CHARS_BYTE_N + 1; i + 2 < raw.length; ++i)
            if (raw[i] == 1 && raw[i + 1] == 2 && raw[i + 2] == 3) return i;
        throw new IllegalStateException("libvterm keeps the colour " + code + " nowhere this binding can see");
    }

    /** RETURN: Map, the pairs 'keyValue' (key, value, key, value ...) in
     *          their order, unmodifiable. */
    private static Map<String, String> ordered(String... keyValue) {
        Map<String, String> result = new LinkedHashMap<>();
        for (int i = 0; i + 1 < keyValue.length; i += 2) result.put(keyValue[i], keyValue[i + 1]);
        return Collections.unmodifiableMap(result);
    }

    /** RETURN: Map, KEY_DB: the named keys and 'f1'..'f12'. */
    private static Map<String, Integer> keyDb() {
        Map<String, Integer> result = new LinkedHashMap<>();
        String[] name = { "enter", "tab", "backspace", "escape", "up", "down", "left", "right",
                          "insert", "delete", "home", "end", "pageup", "pagedown" };
        for (int i = 0; i < name.length; ++i) result.put(name[i], i + 1);
        for (int n = 1; n <= 12; ++n) result.put("f" + n, 256 + n);
        return Collections.unmodifiableMap(result);
    }

    /** THE DETECTION, asked by hand: is the library there? Exits 0 if so, 1
     *  else. */
    public static void main(String[] args) {
        System.out.println(detectionText());
        System.exit(library != null ? 0 : 1);
    }
}

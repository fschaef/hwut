/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- 'Screen' of
 *          'python/hwut_vterm.py': bytes go in, the grid of cells --
 *          characters, attributes, colours, the cursor -- is read back as
 *          plain values a test prints. No process (see 'VtermTerminal').
 *
 *     try (VtermScreen screen = new VtermScreen(24, 80)) {
 *         screen.feed("\u001b[1mbold\u001b[0m plain");
 *         screen.line(0);                 // "bold plain"
 *         screen.cell(0, 0).boldF();      // true
 *         screen.cursor();                // (0, 10)
 *     }
 *
 * The terminal is the library's memory, not Java's: 'close' it -- a
 * try-with-resources is Python's 'with'. Throws LibraryMissing where libvterm
 * is not found (see 'Vterm').
 * _____________________________________________________________________________
 */
package hwut;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static java.lang.foreign.ValueLayout.JAVA_BYTE;
import static java.lang.foreign.ValueLayout.JAVA_INT;

public class VtermScreen implements AutoCloseable {
    /** A place on the screen; printed as Python prints the tuple. */
    public record Place(int row, int column) {
        /** RETURN: String, '(row, column)'. */
        @Override public String toString() { return "(" + row + ", " + column + ")"; }
    }

    public final int        rowN, columnN;
    final Vterm.Library     lib;
    final Arena             arena = Arena.ofShared();
    MemorySegment           terminal, screen, state;
    private final MemorySegment cellBuffer, position;

    /** RETURN: VtermScreen of 24 rows and 80 columns; see the full one. */
    public VtermScreen() { this(24, 80); }

    /** RETURN: VtermScreen of 'rowN' rows and 'columnN' columns, blank, the
     *          cursor at (0, 0), the alternate screen enabled (a full-screen
     *          application draws on it); throws LibraryMissing where libvterm
     *          is not found. */
    public VtermScreen(int rowN, int columnN) {
        this.rowN    = rowN;
        this.columnN = columnN;
        try {
            lib = Vterm.library();
        } catch (LibraryMissing missing) {
            arena.close();
            throw missing;
        }
        cellBuffer = arena.allocate(Vterm.CELL_BYTE_N);
        position   = arena.allocate(Vterm.POSITION);
        terminal   = (MemorySegment) lib.call(lib.vtermNew, rowN, columnN);
        lib.call(lib.setUtf8, terminal, 1);
        screen     = (MemorySegment) lib.call(lib.obtainScreen, terminal);
        state      = (MemorySegment) lib.call(lib.obtainState, terminal);
        //  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR, and a
        //  full-screen application draws on it.
        lib.call(lib.enableAltscreen, screen, 1);
        lib.call(lib.screenReset, screen, 1);
    }

    /** RETURN: nothing; the terminal's memory is freed; a second call does
     *          nothing. */
    @Override public void close() {
        if (terminal == null) return;
        lib.call(lib.vtermFree, terminal);
        terminal = screen = state = null;
        arena.close();
    }

    /** RETURN: long, the number of bytes the terminal took of 'data' -- all
     *          of them, where it works as documented. */
    public long feed(byte[] data) {
        try (Arena call = Arena.ofConfined()) {
            MemorySegment bytes = call.allocate(Math.max(1, data.length));
            MemorySegment.copy(data, 0, bytes, JAVA_BYTE, 0, data.length);
            return (long) lib.call(lib.inputWrite, terminal, bytes, (long) data.length);
        }
    }

    /** RETURN: long, 'feed' of 'text' sent as UTF-8. */
    public long feed(String text) { return feed(text.getBytes(StandardCharsets.UTF_8)); }

    /** RETURN: Place, the cursor's row and column, from 0. */
    public Place cursor() {
        lib.call(lib.getCursorpos, state, position);
        return new Place(position.get(JAVA_INT, 0), position.get(JAVA_INT, 4));
    }

    /** RETURN: byte[], the library's own cell at that place, CELL_BYTE_N
     *          bytes, its colours resolved to red, green, blue where the
     *          library keeps them otherwise (once the layout is measured). */
    byte[] raw(int row, int column) {
        cellBuffer.fill((byte) 0);
        position.set(JAVA_INT, 0, row);
        position.set(JAVA_INT, 4, column);
        lib.call(lib.getCell, screen, position, cellBuffer);
        Vterm.Layout layout = Vterm.layoutOrNull();
        if (layout != null && layout.convertF()) {
            //  THE COLOUR'S STRUCTURE begins one byte before its red: the type
            //  byte the conversion reads and rewrites.
            for (int start : new int[] { layout.foregroundI(), layout.backgroundI() })
                lib.call(lib.convertColorToRgb, screen, cellBuffer.asSlice(start - 1));
        }
        return cellBuffer.toArray(JAVA_BYTE);
    }

    /** RETURN: VtermCell, what stands at that place, if it is on the screen;
     *          throws IndexOutOfBoundsException (Python's IndexError, its
     *          text) else. */
    public VtermCell cell(int row, int column) {
        if (!(0 <= row && row < rowN && 0 <= column && column < columnN))
            throw new IndexOutOfBoundsException("(" + row + ", " + column + ") is not on a screen of "
                                                + rowN + " x " + columnN);
        Vterm.Layout layout = Vterm.measured();
        byte[] raw = raw(row, column);
        StringBuilder text = new StringBuilder();
        for (int i = 0; i < Vterm.CHARS_BYTE_N; i += 4) {
            int code = (raw[i] & 0xFF) | (raw[i + 1] & 0xFF) << 8 | (raw[i + 2] & 0xFF) << 16 | (raw[i + 3] & 0xFF) << 24;
            if (code != 0 && code != 0xFFFFFFFF) text.appendCodePoint(code);
        }
        int width = raw[Vterm.CHARS_BYTE_N] & 0xFF;
        Map<String, int[]> mask = layout.maskDb();
        return new VtermCell(text.toString(), width == 0 ? 1 : width,
                             flag(raw, mask.get("bold")), flag(raw, mask.get("italic")),
                             flag(raw, mask.get("underline")), flag(raw, mask.get("blink")),
                             flag(raw, mask.get("reverse")), flag(raw, mask.get("conceal")),
                             flag(raw, mask.get("strike")),
                             colour(raw, layout.foregroundI(), layout.defaultFg()),
                             colour(raw, layout.backgroundI(), layout.defaultBg()));
    }

    /** RETURN: boolean, true where the bit 'where[1]' of byte 'where[0]' is set. */
    private static boolean flag(byte[] raw, int[] where) { return (raw[where[0]] & where[1]) != 0; }

    /** RETURN: VtermCell.Rgb, the three bytes at 'i'; null where they are
     *          'fallback' -- the default colour. */
    private static VtermCell.Rgb colour(byte[] raw, int i, byte[] fallback) {
        if (fallback.length == 3 && raw[i] == fallback[0] && raw[i + 1] == fallback[1] && raw[i + 2] == fallback[2])
            return null;
        return new VtermCell.Rgb(raw[i] & 0xFF, raw[i + 1] & 0xFF, raw[i + 2] & 0xFF);
    }

    /** RETURN: String, the row's characters, blanks at its end dropped; a
     *          cell nothing was written to reads as a blank. */
    public String line(int row) { return text(row, 0, columnN); }

    /** RETURN: List of String, every row as 'line' gives it, top first. */
    public List<String> lineList() {
        List<String> result = new ArrayList<>();
        for (int row = 0; row < rowN; ++row) result.add(line(row));
        return result;
    }

    /** RETURN: String, the cells of 'row' from 'column' for 'columnN'
     *          columns -- a wide character's right half skipped, an unwritten
     *          cell a blank -- trailing blanks dropped. */
    String text(int row, int column, int columnN) {
        StringBuilder text = new StringBuilder();
        int at = column;
        while (at < column + columnN) {
            VtermCell cell = cell(row, at);
            text.append(cell.text().isEmpty() ? " " : cell.text());
            at += Math.max(cell.width(), 1);
        }
        return text.toString().stripTrailing();
    }
}

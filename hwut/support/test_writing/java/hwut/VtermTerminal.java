/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A TERMINAL AN APPLICATION RUNS IN, OBSERVED BY CALLBACKS --
 *          'Terminal' of 'python/hwut_vterm.py'. Set up first, then run: the
 *          application is started on a pseudo-terminal of this size and
 *          cannot tell this from a terminal a person sits at -- its three
 *          streams are a terminal, its controlling one, the size and TERM
 *          answer, and what it ASKS the terminal is answered by libvterm.
 *
 *     try (VtermTerminal terminal = new VtermTerminal(24, 80)) {
 *         terminal.region("foot", -1);
 *         terminal.onChange((name, lineList) -> System.out.println(name + " " + lineList));
 *         terminal.run(List.of("my-app"));
 *         terminal.press("down");
 *         terminal.send("q");
 *         System.out.println(terminal.waitFor());
 *     }
 *
 * TWO LAYERS OF OBSERVATION:
 *     onEvent    RAW: every VtermEvent -- damage, cursor, property, bell -- as
 *                it happens; print them only where the test feeds the bytes.
 *     onChange   REGIONS: a named rectangle's text, told once it has CHANGED
 *                and the application has gone QUIET ('settleS' without a
 *                byte), in the order the regions were declared.
 *
 * THE PSEUDO-TERMINAL is opened and the application spawned through libc
 * ('Posix': posix_openpt, posix_spawnp with POSIX_SPAWN_SETSID) -- Java has
 * neither 'openpty' nor 'fork'. Python's 'wait' is 'waitFor' here (Object's
 * 'wait' is taken); 'TimeoutError' is 'VtermTerminal.TimeoutError'.
 * _____________________________________________________________________________
 */
package hwut;

import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.function.BiConsumer;
import java.util.function.Consumer;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_BYTE;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;

public class VtermTerminal extends VtermScreen {
    /** WHAT DID NOT HAPPEN IN TIME -- Python's TimeoutError, its text. */
    public static class TimeoutError extends RuntimeException {
        /** RETURN: TimeoutError carrying 'message'. */
        public TimeoutError(String message) { super(message); }
    }

    public final double settleS;
    private final List<Consumer<VtermEvent>>               eventFList  = new ArrayList<>();
    private final List<BiConsumer<String, List<String>>>   changeFList = new ArrayList<>();
    private final Map<String, int[]>                       regionDb    = new LinkedHashMap<>();
    private final Map<String, List<String>>                toldDb      = new HashMap<>();
    private ByteArrayOutputStream answer = new ByteArrayOutputStream();
    private int                   master = -1;                 // -1: nothing runs
    private int                   process;                     // 0: never started
    private Integer               status;                      // the exit status, once reaped
    private boolean               endedF;
    private RuntimeException      callbackError;               // thrown in a callback, rethrown after

    /** RETURN: VtermTerminal of 24 x 80, settling after 0.1 s. */
    public VtermTerminal() { this(24, 80, 0.1); }

    /** RETURN: VtermTerminal of 'rowN' x 'columnN', settling after 0.1 s. */
    public VtermTerminal(int rowN, int columnN) { this(rowN, columnN, 0.1); }

    /** RETURN: VtermTerminal, blank, nothing running in it; throws
     *          LibraryMissing where libvterm is not found. 'settleS' is how
     *          long the application must write nothing before its screen is
     *          taken as drawn. */
    public VtermTerminal(int rowN, int columnN, double settleS) {
        super(rowN, columnN);
        this.settleS = settleS;
        //  THE CALLBACKS LIVE AS LONG AS THE TERMINAL: libvterm keeps their
        //  addresses; they live in this terminal's arena.
        Linker linker = Linker.nativeLinker();
        MemorySegment output = linker.upcallStub(handle("onOutput", MethodType.methodType(void.class, MemorySegment.class, long.class, MemorySegment.class)),
                                                 FunctionDescriptor.ofVoid(ADDRESS, JAVA_LONG, ADDRESS), arena);
        MemorySegment callbacks = arena.allocate(ADDRESS.byteSize() * 16);   // 8 slots, 8 spare: null
        callbacks.setAtIndex(ADDRESS, 0, linker.upcallStub(
            handle("onDamage", MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class)),
            FunctionDescriptor.of(JAVA_INT, Vterm.RECTANGLE, ADDRESS), arena));
        callbacks.setAtIndex(ADDRESS, 2, linker.upcallStub(
            handle("onCursor", MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class, MemorySegment.class)),
            FunctionDescriptor.of(JAVA_INT, Vterm.POSITION, Vterm.POSITION, JAVA_INT, ADDRESS), arena));
        callbacks.setAtIndex(ADDRESS, 3, linker.upcallStub(
            handle("onProperty", MethodType.methodType(int.class, int.class, MemorySegment.class, MemorySegment.class)),
            FunctionDescriptor.of(JAVA_INT, JAVA_INT, ADDRESS, ADDRESS), arena));
        callbacks.setAtIndex(ADDRESS, 4, linker.upcallStub(
            handle("onBell", MethodType.methodType(int.class, MemorySegment.class)),
            FunctionDescriptor.of(JAVA_INT, ADDRESS), arena));
        lib.call(lib.outputSetCallback, terminal, output, MemorySegment.NULL);
        lib.call(lib.setCallbacks, screen, callbacks, MemorySegment.NULL);
        lib.call(lib.setDamageMerge, screen, Vterm.DAMAGE_MERGE_ROW);
    }

    /** RETURN: MethodHandle, this terminal's method 'name' of 'type'. */
    private MethodHandle handle(String name, MethodType type) {
        try {
            return MethodHandles.lookup().findVirtual(VtermTerminal.class, name, type).bindTo(this);
        } catch (ReflectiveOperationException error) {
            throw new AssertionError(error);
        }
    }

    //  ------------------------------------------------------- observation
    /** RETURN: nothing; 'callback' is called with every raw VtermEvent from
     *          now on. */
    public void onEvent(Consumer<VtermEvent> callback) { eventFList.add(callback); }

    /** RETURN: nothing; 'callback(name, lineList)' is called for every region
     *          whose text changed, once the screen is quiet. */
    public void onChange(BiConsumer<String, List<String>> callback) { changeFList.add(callback); }

    /** RETURN: nothing; 'region(name, row, 1, 0, null)': one row, all columns. */
    public void region(String name, int row) { region(name, row, 1, 0, null); }

    /** RETURN: nothing; 'region(name, row, rowN, 0, null)'. */
    public void region(String name, int row, int rowN) { region(name, row, rowN, 0, null); }

    /** RETURN: nothing; the rectangle 'name' is observed from now on: 'rowN'
     *          rows from 'row', 'columnN' columns from 'column' (to the right
     *          edge where null). A NEGATIVE 'row' counts from the bottom: -1
     *          is the last row. What stands there now is known, not news. */
    public void region(String name, int row, int rowN, int column, Integer columnN) {
        if (row < 0) row += this.rowN;
        int width = columnN == null ? this.columnN - column : columnN;
        regionDb.put(name, new int[] { row, rowN, column, width });
        toldDb.put(name, regionText(name));
    }

    /** RETURN: List of String, the region's rows as they stand now, blanks at
     *          each row's end dropped, if it was declared; throws
     *          NoSuchElementException, else -- its message the name quoted,
     *          as Python's KeyError says it. */
    public List<String> regionText(String name) {
        int[] r = regionDb.get(name);
        if (r == null) throw new NoSuchElementException(PyText.strRepr(name));
        List<String> result = new ArrayList<>();
        for (int each = r[0]; each < r[0] + r[1]; ++each) result.add(text(each, r[2], r[3]));
        return result;
    }

    /** RETURN: List of String, the names of the regions whose text differs
     *          from what was last told -- each told to every 'onChange'
     *          callback, in the order of declaration. */
    public List<String> report() {
        List<String> changedList = new ArrayList<>();
        for (String name : regionDb.keySet()) {
            List<String> lineList = regionText(name);
            if (lineList.equals(toldDb.get(name))) continue;
            toldDb.put(name, lineList);
            changedList.add(name);
            for (BiConsumer<String, List<String>> callback : changeFList) callback.accept(name, lineList);
        }
        return changedList;
    }

    /** RETURN: int, 1 -- libvterm's 'handled'. The event reached every raw
     *          callback; what a callback throws is kept and rethrown once the
     *          library call that reported the event returned (an exception
     *          must not cross into C). */
    private int emit(VtermEvent event) {
        try {
            for (Consumer<VtermEvent> callback : eventFList) callback.accept(event);
        } catch (RuntimeException error) {
            if (callbackError == null) callbackError = error;
        }
        return 1;
    }

    /** RETURN: int, 1 (handled); 'damage' told: the rectangle that changed. */
    private int onDamage(MemorySegment rectangle, MemorySegment user) {
        return emit(new VtermEvent("damage", rectangle.get(JAVA_INT, 0), rectangle.get(JAVA_INT, 8),
                                   rectangle.get(JAVA_INT, 4), rectangle.get(JAVA_INT, 12), null, null));
    }

    /** RETURN: int, 1 (handled); 'cursor' told: where it stands, visible or not. */
    private int onCursor(MemorySegment position, MemorySegment old, int visible, MemorySegment user) {
        return emit(new VtermEvent("cursor", position.get(JAVA_INT, 0), position.get(JAVA_INT, 4),
                                   null, null, null, visible != 0));
    }

    /** RETURN: int, 1 (handled); 'property' told: its name, its value where plain. */
    private int onProperty(int number, MemorySegment value, MemorySegment user) {
        Object[] entry = Vterm.PROPERTY_DB.getOrDefault(number, new Object[] { "property-" + number, false });
        Object   said  = (Boolean) entry[1] ? (Object) value.reinterpret(4).get(JAVA_INT, 0) : null;
        return emit(new VtermEvent("property", null, null, null, null, (String) entry[0], said));
    }

    /** RETURN: int, 1 (handled); 'bell' told. */
    private int onBell(MemorySegment user) {
        return emit(new VtermEvent("bell", null, null, null, null, null, null));
    }

    /** RETURN: nothing; what the TERMINAL says -- a key's sequence, the
     *          answer to a question -- is collected for the application. */
    private void onOutput(MemorySegment data, long length, MemorySegment user) {
        byte[] bytes = data.reinterpret(length).toArray(JAVA_BYTE);
        answer.write(bytes, 0, bytes.length);
    }

    /** RETURN: nothing; an error a callback threw is thrown now, once. */
    private void rethrow() {
        RuntimeException error = callbackError;
        callbackError = null;
        if (error != null) throw error;
    }

    //  --------------------------------------------------- bytes in and out
    /** RETURN: long, the number of bytes the terminal took. The raw events
     *          of what was fed fire before this returns; what the terminal
     *          answered goes to the application, where one runs. */
    @Override public long feed(byte[] data) {
        long takenN = super.feed(data);
        lib.call(lib.flushDamage, screen);
        forward();
        rethrow();
        return takenN;
    }

    /** RETURN: byte[], what the terminal said since the last call and no
     *          application took -- the reply to a question fed by hand, the
     *          sequence of a key pressed with nothing running. */
    public byte[] answer() {
        byte[] data = answer.toByteArray();
        answer = new ByteArrayOutputStream();
        return data;
    }

    /** RETURN: nothing; the terminal's words reach the application, if one
     *          runs; they wait in 'answer()' otherwise. */
    private void forward() {
        if (master < 0 || answer.size() == 0) return;
        if (!Posix.write(master, answer.toByteArray())) endedF = true;
        answer = new ByteArrayOutputStream();
    }

    /** RETURN: boolean, 'send(text, 1.0)'. */
    public boolean send(String text) { return send(text, 1.0); }

    /** RETURN: boolean, true if the application still runs after it. 'text'
     *          is typed, character by character, as a keyboard sends it; then
     *          the screen is given 'reactS' to begin answering and is read
     *          until quiet. */
    public boolean send(String text, double reactS) {
        text.codePoints().forEach(c -> lib.call(lib.keyboardUnichar, terminal, c, 0));
        forward();
        return pump(reactS);
    }

    /** RETURN: boolean, 'press(1.0, key, modifier...)'. */
    public boolean press(String key, String... modifier) { return press(1.0, key, modifier); }

    /** RETURN: boolean, true if the application still runs after it, if
     *          'key' and the modifiers have names here; throws
     *          NoSuchElementException (Python's KeyError) else. 'key' is a
     *          name of Vterm.KEY_DB ('enter', 'up', 'f5', ...) or one
     *          character; the modifiers 'shift', 'alt', 'ctrl' --
     *          'press("c", "ctrl")' is Ctrl-C. Then as 'send'. */
    public boolean press(double reactS, String key, String... modifier) {
        int mask = 0;
        for (String name : modifier) {
            Integer bit = Vterm.MODIFIER_DB.get(name);
            if (bit == null) throw new NoSuchElementException(PyText.strRepr(name));
            mask |= bit;
        }
        if (key.codePointCount(0, key.length()) == 1) {
            lib.call(lib.keyboardUnichar, terminal, key.codePointAt(0), mask);
        } else {
            Integer code = Vterm.KEY_DB.get(key);
            if (code == null) throw new NoSuchElementException(PyText.strRepr(key));
            lib.call(lib.keyboardKey, terminal, code, mask);
        }
        forward();
        return pump(reactS);
    }

    //  ------------------------------------------------------ the application
    /** RETURN: boolean, 'run(argv, null, null, 10.0)'. */
    public boolean run(List<String> argv) { return run(argv, null, null, 10.0); }

    /** RETURN: boolean, true if the application still runs once its first
     *          screen stands; throws IllegalStateException (Python's
     *          RuntimeError) where one was run here already, or where the
     *          pseudo-terminal or the process cannot be made.
     *
     *  'argv' is started (searched on PATH) on a pseudo-terminal of this
     *  terminal's size: stdin, stdout and stderr are that terminal, and it is
     *  the application's controlling one. 'env' is its environment (null:
     *  this process's); TERM is 'xterm-256color', LINES and COLUMNS are taken
     *  OUT, since they would overrule the size the terminal answers. 'cwd'
     *  null: this directory. 'startS' is how long its first screen may take. */
    public boolean run(List<String> argv, Map<String, String> env, String cwd, double startS) {
        if (process != 0) throw new IllegalStateException("an application already runs in this terminal");
        Map<String, String> environment = new LinkedHashMap<>(env == null ? System.getenv() : env);
        environment.put("TERM", "xterm-256color");
        environment.remove("LINES");
        environment.remove("COLUMNS");
        Posix.Pair pair = Posix.openpty(rowN, columnN);
        master = pair.master();
        try {
            process = Posix.spawn(argv, environment, pair.slaveName(), cwd);
        } finally {
            if (pair.slave() >= 0) Posix.close(pair.slave());
        }
        endedF = false;
        return pump(startS);
    }

    /** RETURN: Integer, the application's exit status (minus the signal that
     *          ended it) where it has ended; null while it runs or where none
     *          was run. */
    private Integer poll() {
        if (process == 0) return null;
        if (status == null) status = Posix.waitpid(process, false);
        return status;
    }

    /** RETURN: boolean, 'pump(1.0)'. */
    public boolean pump() { return pump(1.0); }

    /** RETURN: boolean, true if the application still runs. READ UNTIL
     *          QUIET: wait up to 'firstS' for the application to write at
     *          all, then go on reading until it has written nothing for
     *          'settleS'. Then the changed regions are reported. */
    public boolean pump(double firstS) {
        double waitS = firstS;
        while (master >= 0 && !endedF) {
            if (!Posix.readable(master, (int) Math.round(waitS * 1000))) break;
            byte[] data = Posix.read(master, 65536);
            if (data.length == 0) {                       // the last writer closed: it ended
                endedF = true;
                break;
            }
            feed(data);
            waitS = settleS;
        }
        report();
        return process != 0 && poll() == null && !endedF;
    }

    /** RETURN: Place, 'expect(text, 10.0)'. */
    public Place expect(String text) { return expect(text, 10.0); }

    /** RETURN: Place, the row and column (in characters) where 'text' stands
     *          on the screen, once it does; throws TimeoutError carrying the
     *          screen where it does not within 'timeoutS'. */
    public Place expect(String text, double timeoutS) {
        long deadline = System.nanoTime() + (long) (timeoutS * 1e9);
        while (true) {
            List<String> lineList = lineList();
            for (int row = 0; row < lineList.size(); ++row) {
                int at = lineList.get(row).indexOf(text);
                if (at >= 0) return new Place(row, lineList.get(row).codePointCount(0, at));
            }
            if (System.nanoTime() >= deadline || endedF || master < 0)
                throw new TimeoutError("'" + text + "' did not appear; the screen:\n" + String.join("\n", lineList));
            pump(settleS);
        }
    }

    /** RETURN: Integer, 'waitFor(10.0)'. */
    public Integer waitFor() { return waitFor(10.0); }

    /** RETURN: Integer, the application's exit status, once it has ended and
     *          its last words are on the screen; null where none was run;
     *          throws TimeoutError where it still runs after 'timeoutS' -- it
     *          is killed first. Python's 'wait'. */
    public Integer waitFor(double timeoutS) {
        if (process == 0) return null;
        long deadline = System.nanoTime() + (long) (timeoutS * 1e9);
        while (pump(settleS)) {
            if (System.nanoTime() >= deadline) {
                kill();
                throw new TimeoutError(String.format("the application still ran after %.1f s", timeoutS));
            }
        }
        long last = Math.max(deadline, System.nanoTime() + 100_000_000L);
        while (poll() == null) {
            if (System.nanoTime() >= last) {
                kill();
                throw new TimeoutError("the application closed its terminal and did not end");
            }
            try { Thread.sleep(5); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
        }
        return status;
    }

    /** RETURN: nothing; the application, where it still runs, is killed and
     *          reaped. */
    private void kill() {
        if (poll() != null || process == 0) return;
        Posix.kill(process);
        status = Posix.waitpid(process, true);
    }

    /** RETURN: nothing; an application still running is killed, the
     *          pseudo-terminal closed, the terminal's memory freed. */
    @Override public void close() {
        kill();
        if (master >= 0) {
            Posix.close(master);
            master = -1;
        }
        super.close();
    }
}

/* ______________________________________________________________________________
 * SQLITE FOR THE SHOP AND ITS FIXTURE -- no test, a helper 'shop.java' and
 * 'fixture.java' compile with them (the Makefile: each into its own classes).
 *
 *     try (Sqlite db = Sqlite.open(path, 10000, line -> System.err.println(line))) {
 *         db.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", -1, "apple");
 *         for (List<Object> row : db.query("SELECT item, qty FROM stock")) ...
 *     }
 *
 * Java has no SQLite of its own, and the JDK no JDBC driver for it; Python
 * has 'sqlite3' in its library. So the library itself, 'libsqlite3.so.0', is
 * called through the Foreign Function & Memory API (a preview in JDK 21) --
 * the way the port's 'Vterm' calls libvterm: no jar, no header. What Python's
 * 'sqlite3' gives the Python shop is given here: a connection in autocommit
 * ('isolation_level=None'), a busy timeout ('timeout='), every statement
 * told to a trace ('set_trace_callback'), parameters bound by '?', an error
 * thrown with SQLite's own message.
 * ______________________________________________________________________________
 */
import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.invoke.MethodHandle;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;

final class Sqlite implements AutoCloseable {
    /** A statement SQLite refused, or a database it could not open. */
    static final class Error extends RuntimeException {
        /** RETURN: Error carrying SQLite's own 'message'. */
        Error(String message) { super(message); }
    }

    static final int SQLITE_OK = 0, SQLITE_ROW = 100, SQLITE_DONE = 101;
    static final int SQLITE_INTEGER = 1, SQLITE_NULL = 5;
    static final int OPEN_READWRITE = 0x2, OPEN_CREATE = 0x4, OPEN_FULLMUTEX = 0x10000;
    //  SQLITE_TRANSIENT: SQLite copies a bound text before the call returns.
    static final MemorySegment TRANSIENT = MemorySegment.ofAddress(-1L);

    static final Linker       LINKER = Linker.nativeLinker();
    static final SymbolLookup LIB    = SymbolLookup.libraryLookup("libsqlite3.so.0", Arena.global());

    /** RETURN: MethodHandle, the library's function 'name' as 'descriptor' says. */
    static MethodHandle function(String name, FunctionDescriptor descriptor) {
        return LINKER.downcallHandle(LIB.find(name).orElseThrow(), descriptor);
    }

    static final MethodHandle OPEN_V2      = function("sqlite3_open_v2",      FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS, JAVA_INT, ADDRESS));
    static final MethodHandle CLOSE_V2     = function("sqlite3_close_v2",     FunctionDescriptor.of(JAVA_INT, ADDRESS));
    static final MethodHandle BUSY_TIMEOUT = function("sqlite3_busy_timeout", FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT));
    static final MethodHandle ERRMSG       = function("sqlite3_errmsg",       FunctionDescriptor.of(ADDRESS, ADDRESS));
    static final MethodHandle PREPARE_V2   = function("sqlite3_prepare_v2",   FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS, JAVA_INT, ADDRESS, ADDRESS));
    static final MethodHandle BIND_INT64   = function("sqlite3_bind_int64",   FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT, JAVA_LONG));
    static final MethodHandle BIND_TEXT    = function("sqlite3_bind_text",    FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT, ADDRESS, JAVA_INT, ADDRESS));
    static final MethodHandle STEP         = function("sqlite3_step",         FunctionDescriptor.of(JAVA_INT, ADDRESS));
    static final MethodHandle COLUMN_COUNT = function("sqlite3_column_count", FunctionDescriptor.of(JAVA_INT, ADDRESS));
    static final MethodHandle COLUMN_TYPE  = function("sqlite3_column_type",  FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT));
    static final MethodHandle COLUMN_INT64 = function("sqlite3_column_int64", FunctionDescriptor.of(JAVA_LONG, ADDRESS, JAVA_INT));
    static final MethodHandle COLUMN_TEXT  = function("sqlite3_column_text",  FunctionDescriptor.of(ADDRESS, ADDRESS, JAVA_INT));
    static final MethodHandle FINALIZE     = function("sqlite3_finalize",     FunctionDescriptor.of(JAVA_INT, ADDRESS));

    private final MemorySegment    handle;
    private final Consumer<String> trace;

    private Sqlite(MemorySegment handle, Consumer<String> trace) { this.handle = handle; this.trace = trace; }

    /** RETURN: Object, what the library call 'function' returned for 'args';
     *          the Throwable a method handle may throw is unchecked here. */
    static Object call(MethodHandle function, Object... args) {
        try { return function.invokeWithArguments(args); }
        catch (RuntimeException error) { throw error; }
        catch (Throwable error) { throw new IllegalStateException(error); }
    }

    /** RETURN: String, the C string at 'pointer'; "" where it is NULL. */
    static String text(MemorySegment pointer) {
        return pointer.address() == 0 ? "" : pointer.reinterpret(Long.MAX_VALUE).getUtf8String(0);
    }

    /** RETURN: Sqlite, a connection to the database 'path', created where it
     *          does not stand, waiting up to 'busyMs' for a lock, every
     *          statement told to 'trace' (null: none) before it runs;
     *          throws Error where SQLite cannot open it. */
    static Sqlite open(String path, int busyMs, Consumer<String> trace) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment slot = arena.allocate(ADDRESS);
            int rc = (int) call(OPEN_V2, arena.allocateUtf8String(path), slot,
                                OPEN_READWRITE | OPEN_CREATE | OPEN_FULLMUTEX, MemorySegment.NULL);
            MemorySegment handle = slot.get(ADDRESS, 0);
            if (rc != SQLITE_OK) {
                String message = text((MemorySegment) call(ERRMSG, handle));
                call(CLOSE_V2, handle);
                throw new Error(message);
            }
            call(BUSY_TIMEOUT, handle, busyMs);
            return new Sqlite(handle, trace);
        }
    }

    /** RETURN: List of rows, each a List of Object (Long, String or null),
     *          the rows 'sql' yields with 'args' bound to its '?' in order
     *          (Integer, Long or String) -- empty for a statement that yields
     *          none; throws Error with SQLite's message where it fails. */
    List<List<Object>> query(String sql, Object... args) {
        if (trace != null) trace.accept(sql);
        List<List<Object>> rowList = new ArrayList<>();
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment slot = arena.allocate(ADDRESS);
            check((int) call(PREPARE_V2, handle, arena.allocateUtf8String(sql), -1, slot, MemorySegment.NULL));
            MemorySegment statement = slot.get(ADDRESS, 0);
            try {
                for (int i = 0; i < args.length; ++i) {
                    if (args[i] instanceof String s)
                        check((int) call(BIND_TEXT, statement, i + 1, arena.allocateUtf8String(s), -1, TRANSIENT));
                    else
                        check((int) call(BIND_INT64, statement, i + 1, ((Number) args[i]).longValue()));
                }
                while (true) {
                    int rc = (int) call(STEP, statement);
                    if (rc == SQLITE_DONE) break;
                    if (rc != SQLITE_ROW) check(rc);
                    int columnN = (int) call(COLUMN_COUNT, statement);
                    List<Object> row = new ArrayList<>();
                    for (int c = 0; c < columnN; ++c) {
                        int type = (int) call(COLUMN_TYPE, statement, c);
                        if      (type == SQLITE_NULL)    row.add(null);
                        else if (type == SQLITE_INTEGER) row.add((Long) call(COLUMN_INT64, statement, c));
                        else                             row.add(text((MemorySegment) call(COLUMN_TEXT, statement, c)));
                    }
                    rowList.add(row);
                }
            } finally {
                call(FINALIZE, statement);
            }
        }
        return rowList;
    }

    /** RETURN: nothing; 'sql' ran with 'args' bound, its rows (if any)
     *          dropped; throws Error with SQLite's message where it fails. */
    void execute(String sql, Object... args) { query(sql, args); }

    /** RETURN: nothing, where 'rc' is SQLITE_OK; throws Error with the
     *          connection's last message, else. */
    private void check(int rc) {
        if (rc != SQLITE_OK) throw new Error(text((MemorySegment) call(ERRMSG, handle)));
    }

    /** RETURN: nothing; the connection is closed. */
    @Override public void close() { call(CLOSE_V2, handle); }
}

/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE FEW libc CALLS A PSEUDO-TERMINAL NEEDS, through the Foreign
 *          Function & Memory API -- for 'VtermTerminal', which runs an
 *          application on one. Java opens no pseudo-terminal and cannot fork;
 *          Python's 'os.openpty' and 'subprocess.Popen(preexec_fn=...)' are
 *          met here by
 *
 *              posix_openpt, grantpt, unlockpt, ptsname_r   the pair
 *              ioctl(TIOCSWINSZ)                            its size
 *              posix_spawnp  + POSIX_SPAWN_SETSID           the child leads a
 *                + open(slave) as its fd 0, dup2 to 1, 2    session; the slave,
 *                                                           opened first in it,
 *                                                           is its controlling
 *                                                           terminal
 *              poll, read, write, close, waitpid, kill     the conversation
 *
 * THE NUMBERS ARE LINUX'S (glibc, x86-64 and aarch64 alike): O_RDWR 2,
 * O_NOCTTY 0400, O_CLOEXEC 02000000, TIOCSWINSZ 0x5414, POSIX_SPAWN_SETSID
 * 0x80 (glibc 2.26 on); the opaque spawn structures are given room beyond
 * glibc's (80 and 336 bytes).
 * _____________________________________________________________________________
 */
package hwut;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.invoke.MethodHandle;
import java.util.List;
import java.util.Map;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_BYTE;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;
import static java.lang.foreign.ValueLayout.JAVA_SHORT;

final class Posix {
    static final int O_RDWR             = 2;
    static final int O_NOCTTY           = 0400;
    static final int O_CLOEXEC          = 02000000;
    static final long TIOCSWINSZ        = 0x5414L;
    static final short POSIX_SPAWN_SETSIGMASK = 0x08;
    static final short POSIX_SPAWN_SETSIGDEF  = 0x04;
    static final short POSIX_SPAWN_SETSID     = 0x80;
    static final short POLLIN           = 1;
    static final int WNOHANG            = 1;
    static final int SIGKILL            = 9;
    private static final int OPAQUE_BYTE_N = 512;              // room for spawn's structures

    private static final Linker       LINKER = Linker.nativeLinker();
    private static final SymbolLookup LIBC   = LINKER.defaultLookup();

    private static final MethodHandle POSIX_OPENPT = down("posix_openpt", FunctionDescriptor.of(JAVA_INT, JAVA_INT));
    private static final MethodHandle GRANTPT      = down("grantpt",      FunctionDescriptor.of(JAVA_INT, JAVA_INT));
    private static final MethodHandle UNLOCKPT     = down("unlockpt",     FunctionDescriptor.of(JAVA_INT, JAVA_INT));
    private static final MethodHandle PTSNAME_R    = down("ptsname_r",    FunctionDescriptor.of(JAVA_INT, JAVA_INT, ADDRESS, JAVA_LONG));
    private static final MethodHandle OPEN         = down("open",         FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT, JAVA_INT),
                                                          Linker.Option.firstVariadicArg(2));
    private static final MethodHandle IOCTL        = down("ioctl",        FunctionDescriptor.of(JAVA_INT, JAVA_INT, JAVA_LONG, ADDRESS),
                                                          Linker.Option.firstVariadicArg(2));
    private static final MethodHandle CLOSE        = down("close",        FunctionDescriptor.of(JAVA_INT, JAVA_INT));
    private static final MethodHandle READ         = down("read",         FunctionDescriptor.of(JAVA_LONG, JAVA_INT, ADDRESS, JAVA_LONG));
    private static final MethodHandle WRITE        = down("write",        FunctionDescriptor.of(JAVA_LONG, JAVA_INT, ADDRESS, JAVA_LONG));
    private static final MethodHandle POLL         = down("poll",         FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_LONG, JAVA_INT));
    private static final MethodHandle WAITPID      = down("waitpid",      FunctionDescriptor.of(JAVA_INT, JAVA_INT, ADDRESS, JAVA_INT));
    private static final MethodHandle KILL         = down("kill",         FunctionDescriptor.of(JAVA_INT, JAVA_INT, JAVA_INT));
    private static final MethodHandle SIGEMPTYSET  = down("sigemptyset",  FunctionDescriptor.of(JAVA_INT, ADDRESS));
    private static final MethodHandle SIGADDSET    = down("sigaddset",    FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT));
    private static final MethodHandle SPAWNP       = down("posix_spawnp", FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS, ADDRESS, ADDRESS, ADDRESS, ADDRESS));
    private static final MethodHandle FA_INIT      = down("posix_spawn_file_actions_init",    FunctionDescriptor.of(JAVA_INT, ADDRESS));
    private static final MethodHandle FA_DESTROY   = down("posix_spawn_file_actions_destroy", FunctionDescriptor.of(JAVA_INT, ADDRESS));
    private static final MethodHandle FA_ADDOPEN   = down("posix_spawn_file_actions_addopen", FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT, ADDRESS, JAVA_INT, JAVA_INT));
    private static final MethodHandle FA_ADDDUP2   = down("posix_spawn_file_actions_adddup2", FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_INT, JAVA_INT));
    private static final MethodHandle FA_ADDCHDIR  = downOptional("posix_spawn_file_actions_addchdir_np", FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS));
    private static final MethodHandle AT_INIT      = down("posix_spawnattr_init",       FunctionDescriptor.of(JAVA_INT, ADDRESS));
    private static final MethodHandle AT_DESTROY   = down("posix_spawnattr_destroy",    FunctionDescriptor.of(JAVA_INT, ADDRESS));
    private static final MethodHandle AT_SETFLAGS  = down("posix_spawnattr_setflags",   FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_SHORT));
    private static final MethodHandle AT_SETMASK   = down("posix_spawnattr_setsigmask", FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS));
    private static final MethodHandle AT_SETDEF    = down("posix_spawnattr_setsigdefault", FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS));

    private Posix() {}

    /** RETURN: MethodHandle, libc's 'name' with the C type 'descriptor';
     *          throws UnsatisfiedLinkError where libc has no such function. */
    private static MethodHandle down(String name, FunctionDescriptor descriptor, Linker.Option... option) {
        MemorySegment address = LIBC.find(name).orElseThrow(() -> new UnsatisfiedLinkError("libc has no '" + name + "'"));
        return LINKER.downcallHandle(address, descriptor, option);
    }

    /** RETURN: MethodHandle, libc's 'name'; null where libc has none. */
    private static MethodHandle downOptional(String name, FunctionDescriptor descriptor) {
        return LIBC.find(name).map(a -> LINKER.downcallHandle(a, descriptor)).orElse(null);
    }

    /** RETURN: Object, what 'handle' returned for 'argument' -- a C call
     *          that cannot throw; any Throwable of the call is rethrown as an
     *          Error (it is a defect of this binding). */
    private static Object call(MethodHandle handle, Object... argument) {
        try {
            return handle.invokeWithArguments(argument);
        } catch (Throwable error) {
            throw new AssertionError("libc call failed: " + error, error);
        }
    }

    /** One pseudo-terminal: the master's descriptor, the slave's -- open
     *  until the application has opened it itself -- and the slave's name. */
    record Pair(int master, int slave, String slaveName) {}

    /** RETURN: Pair, a new pseudo-terminal of 'rowN' x 'columnN', its size
     *          set, master and slave open (close-on-exec; the slave not this
     *          process's controlling terminal), if success;
     *          throws IllegalStateException naming the call that failed, else. */
    static Pair openpty(int rowN, int columnN) {
        int master = (int) call(POSIX_OPENPT, O_RDWR | O_NOCTTY | O_CLOEXEC);
        if (master < 0) throw new IllegalStateException("posix_openpt failed");
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment name = arena.allocate(256);
            if ((int) call(GRANTPT, master) != 0 || (int) call(UNLOCKPT, master) != 0
                || (int) call(PTSNAME_R, master, name, 256L) != 0) {
                close(master);
                throw new IllegalStateException("grantpt/unlockpt/ptsname_r failed");
            }
            String slaveName = name.getUtf8String(0);
            //  THE SIZE IS SET ON THE SLAVE, as Python sets it; the slave stays
            //  open here until the application holds it (the caller closes it).
            int slave = (int) call(OPEN, arena.allocateUtf8String(slaveName), O_RDWR | O_NOCTTY | O_CLOEXEC, 0);
            if (slave < 0) { close(master); throw new IllegalStateException("cannot open " + slaveName); }
            MemorySegment size = arena.allocate(8);
            size.set(JAVA_SHORT, 0, (short) rowN);
            size.set(JAVA_SHORT, 2, (short) columnN);
            call(IOCTL, slave, TIOCSWINSZ, size);
            return new Pair(master, slave, slaveName);
        }
    }

    /** RETURN: int, the process id of 'argv' started (searched on PATH) with
     *          the environment 'environment' -- in a session of its own, the
     *          slave 'slaveName' its stdin, stdout, stderr and controlling
     *          terminal, in 'cwd' (null: this one), its signal mask empty and
     *          the usual signals at their default, if success;
     *          throws IllegalStateException carrying the errno, else. */
    static int spawn(List<String> argv, Map<String, String> environment, String slaveName, String cwd) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment actions = arena.allocate(OPAQUE_BYTE_N);
            MemorySegment attr    = arena.allocate(OPAQUE_BYTE_N);
            MemorySegment none    = arena.allocate(128), standard = arena.allocate(128);
            call(FA_INIT, actions);
            call(AT_INIT, attr);
            try {
                call(FA_ADDOPEN, actions, 0, arena.allocateUtf8String(slaveName), O_RDWR, 0);
                call(FA_ADDDUP2, actions, 0, 1);
                call(FA_ADDDUP2, actions, 0, 2);
                if (cwd != null) {
                    if (FA_ADDCHDIR == null) throw new IllegalStateException("this libc cannot spawn into a directory");
                    call(FA_ADDCHDIR, actions, arena.allocateUtf8String(cwd));
                }
                call(SIGEMPTYSET, none);
                call(SIGEMPTYSET, standard);
                for (int signal : new int[] { 1, 2, 3, 13, 15, 25 })   // HUP INT QUIT PIPE TERM XFSZ
                    call(SIGADDSET, standard, signal);
                call(AT_SETMASK, attr, none);
                call(AT_SETDEF, attr, standard);
                call(AT_SETFLAGS, attr, (short) (POSIX_SPAWN_SETSID | POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETSIGDEF));
                MemorySegment pid = arena.allocate(JAVA_INT);
                int error = (int) call(SPAWNP, pid, arena.allocateUtf8String(argv.get(0)), actions, attr,
                                       stringArray(arena, argv), stringArray(arena, environmentList(environment)));
                if (error != 0) throw new IllegalStateException("posix_spawnp '" + argv.get(0) + "' failed, errno " + error);
                return pid.get(JAVA_INT, 0);
            } finally {
                call(FA_DESTROY, actions);
                call(AT_DESTROY, attr);
            }
        }
    }

    /** RETURN: List of String, 'environment' as 'NAME=value' entries. */
    private static List<String> environmentList(Map<String, String> environment) {
        return environment.entrySet().stream().map(e -> e.getKey() + "=" + e.getValue()).toList();
    }

    /** RETURN: MemorySegment, a NULL-terminated 'char*[]' of 'text', in 'arena'. */
    private static MemorySegment stringArray(Arena arena, List<String> text) {
        MemorySegment array = arena.allocateArray(ADDRESS, text.size() + 1L);
        for (int i = 0; i < text.size(); ++i) array.setAtIndex(ADDRESS, i, arena.allocateUtf8String(text.get(i)));
        array.setAtIndex(ADDRESS, text.size(), MemorySegment.NULL);
        return array;
    }

    /** RETURN: boolean, true where 'fd' has something to read -- or its
     *          writer is gone -- within 'timeoutMs' (negative: no bound). */
    static boolean readable(int fd, int timeoutMs) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment entry = arena.allocate(8);
            entry.set(JAVA_INT, 0, fd);
            entry.set(JAVA_SHORT, 4, POLLIN);
            int n;
            do { n = (int) call(POLL, entry, 1L, timeoutMs); } while (n < 0);   // EINTR: again
            return n > 0;
        }
    }

    /** RETURN: byte[], what one 'read' of 'fd' gave, up to 'size' bytes;
     *          empty at the end of the stream or on an error (EIO: the last
     *          writer of a pseudo-terminal closed it). */
    static byte[] read(int fd, int size) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment buffer = arena.allocate(size);
            long n = (long) call(READ, fd, buffer, (long) size);
            if (n <= 0) return new byte[0];
            return buffer.asSlice(0, n).toArray(JAVA_BYTE);
        }
    }

    /** RETURN: boolean, true where all of 'data' was written to 'fd'; false
     *          where a write failed. */
    static boolean write(int fd, byte[] data) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment buffer = arena.allocate(Math.max(1, data.length));
            MemorySegment.copy(data, 0, buffer, JAVA_BYTE, 0, data.length);
            long at = 0;
            while (at < data.length) {
                long n = (long) call(WRITE, fd, buffer.asSlice(at), (long) data.length - at);
                if (n <= 0) return false;
                at += n;
            }
            return true;
        }
    }

    /** RETURN: nothing; 'fd' is closed. */
    static void close(int fd) { call(CLOSE, fd); }

    /** RETURN: Integer, the exit code of the ended child 'pid' -- minus the
     *          signal that ended it -- once reaped; null where it still runs
     *          ('block' false) or is no child of this process. 'block' true
     *          waits for its end. */
    static Integer waitpid(int pid, boolean block) {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment status = arena.allocate(JAVA_INT);
            int got = (int) call(WAITPID, pid, status, block ? 0 : WNOHANG);
            if (got != pid) return null;
            int s = status.get(JAVA_INT, 0);
            if ((s & 0x7f) == 0) return (s >> 8) & 0xff;               // WIFEXITED: WEXITSTATUS
            return -(s & 0x7f);                                          // WTERMSIG, negated
        }
    }

    /** RETURN: nothing; SIGKILL was sent to 'pid'. */
    static void kill(int pid) { call(KILL, pid, SIGKILL); }
}

// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: THE NATIVE EDGE OF 'hwut_vterm.psm1' -- what PowerShell cannot say
//          itself: the C functions of libvterm and libc declared for P/Invoke,
//          the two structures passed by value, the callback signatures, and
//          the marshalling of 'char*[]'. Compiled at run time by 'Add-Type'
//          (once per process, on the first Screen), nothing built beforehand.
//
//     HwutVterm.Lib       libvterm's functions; the library is the handle
//                         'Lib.Use(handle)' names (loaded by the PowerShell
//                         side with NativeLibrary, from HWUT_LIBVTERM or the
//                         system's search) -- a resolver binds the name.
//     HwutVterm.Recorder  libvterm's screen and output callbacks: what they
//                         report is QUEUED, in the order reported, and
//                         drained by PowerShell after each call into the
//                         library -- no script runs inside a native callback.
//     HwutVterm.Posix     the pseudo-terminal: posix_openpt, grantpt,
//                         unlockpt, ptsname_r, ioctl(TIOCSWINSZ),
//                         posix_spawnp (a new session, the slave opened as
//                         fd 0, dup'ed to 1 and 2, every signal at its
//                         default), poll, read, write, close, waitpid, kill
//                         -- as 'java/hwut/Posix.java' does; no helper
//                         process, no fork of the runtime.
//
// THE NUMBERS ARE LINUX'S (glibc, x86-64 and aarch64 alike): O_RDWR 2,
// O_NOCTTY 0400, O_CLOEXEC 02000000, TIOCSWINSZ 0x5414, POSIX_SPAWN_SETSID
// 0x80 (glibc 2.26 on); the opaque spawn structures are given room beyond
// glibc's.
//_____________________________________________________________________________
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

namespace HwutVterm
{
    [StructLayout(LayoutKind.Sequential)]
    public struct VTermPos  { public int row; public int col; }

    [StructLayout(LayoutKind.Sequential)]
    public struct VTermRect { public int start_row; public int end_row; public int start_col; public int end_col; }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void OutputCallback(IntPtr data, UIntPtr length, IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int  DamageCallback(VTermRect rectangle, IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int  MoveCursorCallback(VTermPos position, VTermPos old, int visible, IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int  PropertyCallback(int number, IntPtr value, IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int  BellCallback(IntPtr user);

    public static class Lib
    {
        public const string NAME = "hwut-libvterm";
        static IntPtr handle = IntPtr.Zero;
        static bool   resolverSet;

        /// RETURN: nothing; from now on the functions below are the library
        ///         'h' holds (a handle of NativeLibrary.Load). The binding of
        ///         a function, once made, stays: a later handle must be the
        ///         same library.
        public static void Use(IntPtr h)
        {
            handle = h;
            if (resolverSet) return;
            NativeLibrary.SetDllImportResolver(typeof(Lib).Assembly,
                (name, assembly, path) => name == NAME ? handle : IntPtr.Zero);
            resolverSet = true;
        }

        /// RETURN: bool, true where the library 'h' exports 'name'; false else.
        public static bool Has(IntPtr h, string name)
        {
            IntPtr address;
            return NativeLibrary.TryGetExport(h, name, out address);
        }

        [DllImport(NAME)] public static extern IntPtr  vterm_new(int rows, int cols);
        [DllImport(NAME)] public static extern void    vterm_free(IntPtr vt);
        [DllImport(NAME)] public static extern void    vterm_set_utf8(IntPtr vt, int is_utf8);
        [DllImport(NAME)] public static extern UIntPtr vterm_input_write(IntPtr vt, byte[] bytes, UIntPtr len);
        [DllImport(NAME)] public static extern IntPtr  vterm_obtain_screen(IntPtr vt);
        [DllImport(NAME)] public static extern IntPtr  vterm_obtain_state(IntPtr vt);
        [DllImport(NAME)] public static extern void    vterm_screen_reset(IntPtr screen, int hard);
        [DllImport(NAME)] public static extern void    vterm_screen_enable_altscreen(IntPtr screen, int altscreen);
        [DllImport(NAME)] public static extern int     vterm_screen_get_cell(IntPtr screen, VTermPos pos, byte[] cell);
        [DllImport(NAME)] public static extern void    vterm_state_get_cursorpos(IntPtr state, out VTermPos cursorpos);
        [DllImport(NAME)] public static extern void    vterm_output_set_callback(IntPtr vt, IntPtr func, IntPtr user);
        [DllImport(NAME)] public static extern void    vterm_keyboard_unichar(IntPtr vt, uint c, int mod);
        [DllImport(NAME)] public static extern void    vterm_keyboard_key(IntPtr vt, int key, int mod);
        [DllImport(NAME)] public static extern void    vterm_screen_set_callbacks(IntPtr screen, IntPtr callbacks, IntPtr user);
        [DllImport(NAME)] public static extern void    vterm_screen_set_damage_merge(IntPtr screen, int size);
        [DllImport(NAME)] public static extern void    vterm_screen_flush_damage(IntPtr screen);
        [DllImport(NAME)] static extern void vterm_screen_convert_color_to_rgb(IntPtr screen, IntPtr colour);

        /// RETURN: int, what 'vterm_screen_get_cell' returns; the library's
        ///         own cell at (row, column) is copied into 'cell' (room
        ///         beyond any version's cell).
        public static int GetCell(IntPtr screen, int row, int column, byte[] cell)
        {
            VTermPos pos; pos.row = row; pos.col = column;
            return vterm_screen_get_cell(screen, pos, cell);
        }

        /// RETURN: int[] { row, column }, the cursor of the state 'state', from 0.
        public static int[] CursorPos(IntPtr state)
        {
            VTermPos pos;
            vterm_state_get_cursorpos(state, out pos);
            return new int[] { pos.row, pos.col };
        }

        /// RETURN: long, the number of bytes the terminal 'vt' took of 'bytes'.
        public static long InputWrite(IntPtr vt, byte[] bytes)
        {
            return (long)vterm_input_write(vt, bytes, (UIntPtr)bytes.Length);
        }

        /// RETURN: nothing; the colour structures that begin at the byte
        ///         offsets 'starts' of 'cell' are resolved to red, green,
        ///         blue by the library (0.2 and later; the caller asks only
        ///         where 'Has' found the function).
        public static void ConvertColours(IntPtr screen, byte[] cell, int[] starts)
        {
            GCHandle pin = GCHandle.Alloc(cell, GCHandleType.Pinned);
            try
            {
                IntPtr at = pin.AddrOfPinnedObject();
                foreach (int start in starts) vterm_screen_convert_color_to_rgb(screen, at + start);
            }
            finally { pin.Free(); }
        }
    }

    /// WHAT libvterm REPORTS, QUEUED: each entry an object[] -- { "damage",
    /// start_row, end_row, start_col, end_col }, { "cursor", row, col,
    /// visible }, { "property", number, int value or null }, { "bell" } --
    /// and the bytes the terminal says ('answer').
    public sealed class Recorder : IDisposable
    {
        public readonly List<object[]> EventList  = new List<object[]>();
        public readonly List<byte>     AnswerList = new List<byte>();
        readonly OutputCallback     output;
        readonly DamageCallback     damage;
        readonly MoveCursorCallback movecursor;
        readonly PropertyCallback   property;
        readonly BellCallback       bell;
        IntPtr callbacks;                       // VTermScreenCallbacks, in C memory
        readonly HashSet<int> plainSet;         // property numbers whose value is an int or bool

        const int CALLBACK_SLOT_N = 16;         // 8 callbacks, spare slots beyond any version's

        /// RETURN: Recorder registered on the terminal 'vt' and its screen
        ///         'screen'; its delegates live as long as it does (libvterm
        ///         keeps their addresses). 'plain' are the property numbers
        ///         whose value is a number (the others report null).
        public Recorder(IntPtr vt, IntPtr screen, int[] plain)
        {
            plainSet   = new HashSet<int>(plain);
            output     = (data, length, user) => {
                int n = (int)length;
                if (n <= 0) return;
                byte[] chunk = new byte[n];
                Marshal.Copy(data, chunk, 0, n);
                AnswerList.AddRange(chunk);
            };
            damage     = (r, user) => { EventList.Add(new object[] { "damage", r.start_row, r.end_row, r.start_col, r.end_col }); return 1; };
            movecursor = (p, old, visible, user) => { EventList.Add(new object[] { "cursor", p.row, p.col, visible != 0 }); return 1; };
            property   = (number, value, user) => {
                object v = plainSet.Contains(number) ? (object)Marshal.ReadInt32(value) : null;
                EventList.Add(new object[] { "property", number, v });
                return 1;
            };
            bell       = (user) => { EventList.Add(new object[] { "bell" }); return 1; };
            callbacks  = Marshal.AllocHGlobal(IntPtr.Size * CALLBACK_SLOT_N);
            for (int i = 0; i < CALLBACK_SLOT_N; ++i) Marshal.WriteIntPtr(callbacks, i * IntPtr.Size, IntPtr.Zero);
            //  damage, moverect, movecursor, settermprop, bell, resize, sb_pushline, sb_popline
            Marshal.WriteIntPtr(callbacks, 0 * IntPtr.Size, Marshal.GetFunctionPointerForDelegate(damage));
            Marshal.WriteIntPtr(callbacks, 2 * IntPtr.Size, Marshal.GetFunctionPointerForDelegate(movecursor));
            Marshal.WriteIntPtr(callbacks, 3 * IntPtr.Size, Marshal.GetFunctionPointerForDelegate(property));
            Marshal.WriteIntPtr(callbacks, 4 * IntPtr.Size, Marshal.GetFunctionPointerForDelegate(bell));
            Lib.vterm_output_set_callback(vt, Marshal.GetFunctionPointerForDelegate(output), IntPtr.Zero);
            Lib.vterm_screen_set_callbacks(screen, callbacks, IntPtr.Zero);
        }

        /// RETURN: object[][], every event queued since the last call, in
        ///         the order reported; the queue is empty after it.
        public object[][] TakeEvents()  { object[][] r = EventList.ToArray(); EventList.Clear(); return r; }

        /// RETURN: byte[], the bytes the terminal said since the last call;
        ///         empty after it.
        public byte[] TakeAnswer() { byte[] r = AnswerList.ToArray(); AnswerList.Clear(); return r; }

        /// RETURN: nothing; the callbacks' structure is freed. The terminal
        ///         must be freed before (or not be called again).
        public void Dispose()
        {
            if (callbacks != IntPtr.Zero) { Marshal.FreeHGlobal(callbacks); callbacks = IntPtr.Zero; }
        }
    }

    public static class Posix
    {
        public const int   O_RDWR = 2, O_NOCTTY = 0x100, O_CLOEXEC = 0x80000;
        public const ulong TIOCSWINSZ = 0x5414;
        public const short POSIX_SPAWN_SETSIGDEF = 0x04, POSIX_SPAWN_SETSIGMASK = 0x08, POSIX_SPAWN_SETSID = 0x80;
        public const short POLLIN = 1;
        public const int   WNOHANG = 1, SIGKILL = 9, EINTR = 4;
        const int OPAQUE_BYTE_N = 1024;

        [DllImport("libc.so.6", SetLastError = true)] static extern int  posix_openpt(int flags);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  grantpt(int fd);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  unlockpt(int fd);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  ptsname_r(int fd, byte[] buf, UIntPtr buflen);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  open(string path, int flags, int mode);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  ioctl(int fd, ulong request, byte[] argument);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  close(int fd);
        [DllImport("libc.so.6", SetLastError = true)] static extern IntPtr read(int fd, byte[] buf, UIntPtr count);
        [DllImport("libc.so.6", SetLastError = true)] static extern IntPtr write(int fd, byte[] buf, UIntPtr count);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  poll(byte[] fds, UIntPtr nfds, int timeout);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  waitpid(int pid, out int status, int options);
        [DllImport("libc.so.6", SetLastError = true)] static extern int  kill(int pid, int sig);
        [DllImport("libc.so.6")] static extern int sigfillset(byte[] set);
        [DllImport("libc.so.6")] static extern int sigemptyset(byte[] set);
        [DllImport("libc.so.6")] static extern int posix_spawn_file_actions_init(byte[] actions);
        [DllImport("libc.so.6")] static extern int posix_spawn_file_actions_destroy(byte[] actions);
        [DllImport("libc.so.6")] static extern int posix_spawn_file_actions_addopen(byte[] actions, int fd, string path, int oflag, int mode);
        [DllImport("libc.so.6")] static extern int posix_spawn_file_actions_adddup2(byte[] actions, int fd, int newfd);
        [DllImport("libc.so.6")] static extern int posix_spawn_file_actions_addchdir_np(byte[] actions, string path);
        [DllImport("libc.so.6")] static extern int posix_spawnattr_init(byte[] attr);
        [DllImport("libc.so.6")] static extern int posix_spawnattr_destroy(byte[] attr);
        [DllImport("libc.so.6")] static extern int posix_spawnattr_setflags(byte[] attr, short flags);
        [DllImport("libc.so.6")] static extern int posix_spawnattr_setsigmask(byte[] attr, byte[] mask);
        [DllImport("libc.so.6")] static extern int posix_spawnattr_setsigdefault(byte[] attr, byte[] mask);
        [DllImport("libc.so.6")] static extern int posix_spawnp(out int pid, string file, byte[] actions, byte[] attr, IntPtr[] argv, IntPtr[] envp);

        /// RETURN: object[] { master, slave_path }, a new pseudo-terminal of
        ///         'row_n' x 'column_n' -- the master open (close-on-exec,
        ///         not this process's controlling terminal), its size set on
        ///         the slave -- if success; throws InvalidOperationException
        ///         naming the call that failed, else.
        public static object[] OpenPty(int row_n, int column_n)
        {
            int master = posix_openpt(O_RDWR | O_NOCTTY | O_CLOEXEC);
            if (master < 0) throw new InvalidOperationException("no pseudo-terminal: posix_openpt/grantpt/unlockpt failed");
            byte[] name = new byte[256];
            if (grantpt(master) != 0 || unlockpt(master) != 0 || ptsname_r(master, name, (UIntPtr)name.Length) != 0)
            {
                close(master);
                throw new InvalidOperationException("no pseudo-terminal: posix_openpt/grantpt/unlockpt failed");
            }
            string slavePath = Encoding.UTF8.GetString(name, 0, Array.IndexOf(name, (byte)0));
            //  THE SIZE IS SET ON THE SLAVE, as Python sets it.
            int slave = open(slavePath, O_RDWR | O_NOCTTY | O_CLOEXEC, 0);
            if (slave < 0) { close(master); throw new InvalidOperationException("cannot open " + slavePath); }
            byte[] size = new byte[8];
            BitConverter.GetBytes((ushort)row_n).CopyTo(size, 0);
            BitConverter.GetBytes((ushort)column_n).CopyTo(size, 2);
            ioctl(slave, TIOCSWINSZ, size);
            close(slave);
            return new object[] { master, slavePath };
        }

        /// RETURN: int, the process id of 'argv' started (searched on PATH)
        ///         with the environment 'envp' ('NAME=value' entries) -- in a
        ///         session of its own, the slave 'slavePath' opened as its fd 0
        ///         (so its controlling terminal) and dup'ed to 1 and 2, in
        ///         'cwd' (null or empty: this one), its signal mask empty and every
        ///         signal at its default -- if success; throws
        ///         InvalidOperationException carrying the errno, else.
        public static int Spawn(string[] argv, string[] envp, string slavePath, string cwd)
        {
            byte[] actions = new byte[OPAQUE_BYTE_N], attr = new byte[OPAQUE_BYTE_N];
            byte[] all = new byte[256], none = new byte[256];
            List<IntPtr> allocated = new List<IntPtr>();
            posix_spawn_file_actions_init(actions);
            posix_spawnattr_init(attr);
            try
            {
                posix_spawn_file_actions_addopen(actions, 0, slavePath, O_RDWR, 0);
                posix_spawn_file_actions_adddup2(actions, 0, 1);
                posix_spawn_file_actions_adddup2(actions, 0, 2);
                if (!string.IsNullOrEmpty(cwd))         // PowerShell hands $null as ""
                {
                    try { posix_spawn_file_actions_addchdir_np(actions, cwd); }
                    catch (EntryPointNotFoundException) { throw new InvalidOperationException("no 'posix_spawn_file_actions_addchdir_np': 'cwd' cannot be set"); }
                }
                sigfillset(all);
                sigemptyset(none);
                posix_spawnattr_setsigdefault(attr, all);
                posix_spawnattr_setsigmask(attr, none);
                posix_spawnattr_setflags(attr, (short)(POSIX_SPAWN_SETSID | POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK));
                IntPtr[] cArgv = StringArray(argv, allocated);
                IntPtr[] cEnvp = StringArray(envp, allocated);
                int pid;
                int error = posix_spawnp(out pid, argv[0], actions, attr, cArgv, cEnvp);
                if (error != 0) throw new InvalidOperationException("posix_spawnp '" + argv[0] + "': errno " + error);
                return pid;
            }
            finally
            {
                posix_spawn_file_actions_destroy(actions);
                posix_spawnattr_destroy(attr);
                foreach (IntPtr p in allocated) Marshal.FreeHGlobal(p);
            }
        }

        /// RETURN: IntPtr[], 'text' as NUL-terminated UTF-8 strings in C
        ///         memory (recorded in 'allocated' for the caller to free),
        ///         a null pointer last -- a 'char*[]'.
        static IntPtr[] StringArray(string[] text, List<IntPtr> allocated)
        {
            IntPtr[] array = new IntPtr[text.Length + 1];
            for (int i = 0; i < text.Length; ++i)
            {
                byte[] bytes = Encoding.UTF8.GetBytes(text[i] + "\0");
                IntPtr p = Marshal.AllocHGlobal(bytes.Length);
                Marshal.Copy(bytes, 0, p, bytes.Length);
                allocated.Add(p);
                array[i] = p;
            }
            array[text.Length] = IntPtr.Zero;
            return array;
        }

        /// RETURN: int, what 'poll' says of 'fd' for reading within
        ///         'timeoutMs' (negative: no bound): 1 readable (or its writer
        ///         gone), 0 not within the time; an interrupted call is made
        ///         again.
        public static int Readable(int fd, int timeoutMs)
        {
            byte[] entry = new byte[8];
            BitConverter.GetBytes(fd).CopyTo(entry, 0);
            BitConverter.GetBytes(POLLIN).CopyTo(entry, 4);
            while (true)
            {
                int n = poll(entry, (UIntPtr)1, timeoutMs);
                if (n < 0 && Marshal.GetLastWin32Error() == EINTR) continue;
                return n < 0 ? -1 : n;
            }
        }

        /// RETURN: byte[], what one 'read' of 'fd' gave, up to 'size' bytes;
        ///         empty at the end of the stream or on an error (EIO: the
        ///         last writer of a pseudo-terminal closed it).
        public static byte[] Read(int fd, int size)
        {
            byte[] buffer = new byte[size];
            long n = (long)read(fd, buffer, (UIntPtr)size);
            if (n <= 0) return new byte[0];
            byte[] result = new byte[n];
            Array.Copy(buffer, result, n);
            return result;
        }

        /// RETURN: bool, true where all of 'data' was written to 'fd'; false
        ///         where a write failed.
        public static bool Write(int fd, byte[] data)
        {
            int at = 0;
            while (at < data.Length)
            {
                byte[] rest = new byte[data.Length - at];
                Array.Copy(data, at, rest, 0, rest.Length);
                long n = (long)write(fd, rest, (UIntPtr)rest.Length);
                if (n <= 0) return false;
                at += (int)n;
            }
            return true;
        }

        /// RETURN: nothing; 'fd' is closed.
        public static void Close(int fd) { close(fd); }

        /// RETURN: object, the exit code of the ended child 'pid' -- minus
        ///         the signal that ended it -- once reaped; null where it
        ///         still runs ('block' false) or is no child of this process.
        ///         'block' true waits for its end.
        public static object WaitPid(int pid, bool block)
        {
            int status;
            int got = waitpid(pid, out status, block ? 0 : WNOHANG);
            if (got != pid) return null;
            if ((status & 0x7f) == 0) return (status >> 8) & 0xff;      // WIFEXITED: WEXITSTATUS
            return -(status & 0x7f);                                     // WTERMSIG, negated
        }

        /// RETURN: nothing; SIGKILL was sent to 'pid'.
        public static void Kill(int pid) { kill(pid, SIGKILL); }
    }
}

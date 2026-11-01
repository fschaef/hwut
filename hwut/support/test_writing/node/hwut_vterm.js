// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
//          'python/hwut_vterm.py' (read '../python/README-hwut_vterm.txt'):
//          'libvterm' through 'koffi', node's foreign function interface.
//
//     const { Screen, Terminal } = require(path.join(__dirname, '..', 'hwut_vterm.js'));
//     new Screen(24, 80).use(screen => {
//         screen.feed('\x1b[1mbold\x1b[0m plain');
//         screen.line(0);               // 'bold plain'
//         screen.cell(0, 0).bold_f;     // true
//         screen.cursor();              // [0, 10]
//     });
//
// THE LIBRARY IS FOUND, NOT SHIPPED: 'libvterm.so.0' as the system knows it
//     (Debian: 'libvterm0'), or the file HWUT_LIBVTERM names. Where neither
//     stands, 'new Screen()' throws 'LibraryMissing', whose text says how to
//     install it. 'node hwut_vterm.js' asks the same by hand.
//
// THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED -- as the Python binding does:
//     a scratch terminal is fed one attribute at a time and the bit or the
//     bytes that changed are where that attribute stands; no header of
//     libvterm is read.
//
// TWO CLASSES:
//     Screen      the grid alone: bytes in, cells out. No process.
//     Terminal    a Screen an APPLICATION RUNS IN, on a pseudo-terminal it
//                 cannot tell from a person's; keys go in as a keyboard
//                 sends them; observation by callback, raw ('on_event') or
//                 by named region ('on_change').
//
// WHERE NODE DIFFERS FROM PYTHON:
//     no 'ctypes'      'koffi' (npm; prebuilt, no compiler) -- the one
//                      package this port wants; 'npm install' in '..'.
//     no 'with'        'screen.use(block)': 'block(screen)' runs, then
//                      'close()' -- whatever way it ends. Or 'close()'.
//     no fork          a forked node is unsafe (threads). The application
//                      is started by libc's 'posix_spawnp': a new session
//                      (POSIX_SPAWN_SETSID), then the pseudo-terminal's
//                      slave OPENED as fd 0 -- a session leader opening a
//                      terminal makes it its controlling one, as Python's
//                      'setsid' and 'TIOCSCTTY' do -- and dup'ed to 1, 2;
//                      every signal back to its default, as Python's
//                      'subprocess' restores them. The child is waited for
//                      by 'waitpid' directly (node's loop never knew it).
//     synchronous      'run', 'pump', 'send', 'press', 'wait', 'expect'
//                      block, as in Python -- 'poll' and 'read' on the
//                      master through libc.
//     keyword args     positional in Python's order: 'region(name, row,
//                      row_n, column, column_n)', 'press(key, modifier_list,
//                      react_s)', 'run(argv, env, cwd, start_s)'.
//     tuples           arrays: 'cursor()' is [row, column], a colour
//                      [red, green, blue].
//     exceptions       named as Python's: LibraryMissing, IndexError,
//                      KeyError, TimeoutError, RuntimeError (this module's
//                      own classes, 'name' set, 'message' Python's text).
//_____________________________________________________________________________
'use strict';

const fs = require('fs');

//  THE ENVIRONMENT VARIABLE that names the library's file.
const LIBRARY_VARIABLE = 'HWUT_LIBVTERM';
//  THE NAMES the system's search is asked for, in this order.
const LIBRARY_NAME_LIST = ['libvterm.so.0', 'libvterm.so', 'libvterm.dylib', 'libvterm.0.dylib'];

const CHARS_PER_CELL_N = 6;
const CHARS_BYTE_N     = 4 * CHARS_PER_CELL_N;
const CELL_BYTE_N      = 128;          // room beyond any version's cell

//  THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets it.
const ATTRIBUTE_SGR_DB = Object.freeze({
    bold: '1', italic: '3', underline: '4', blink: '5', reverse: '7', conceal: '8', strike: '9',
});

const INSTALL_HINT = [
    'HINT: install the library, or name its file:',
    '    Debian, Ubuntu   apt install libvterm0',
    '    Fedora           dnf install libvterm',
    '    Arch             pacman -S libvterm',
    '    macOS            brew install libvterm',
    `    elsewhere        export ${LIBRARY_VARIABLE}=<path>/libvterm.so`,
    '    or work inside   hwut.dev.podman.enter   (the image holds it)',
].join('\n');

const DAMAGE_MERGE_ROW = 1;

const PROPERTY_DB = {
    1: ['cursor-visible', true],   2: ['cursor-blink', true],  3: ['alternate-screen', true],
    4: ['title', false],           5: ['icon-name', false],    6: ['reverse-video', true],
    7: ['cursor-shape', true],     8: ['mouse', true],         9: ['focus-report', true],
};

const KEY_DB = {
    enter: 1, tab: 2, backspace: 3, escape: 4, up: 5, down: 6, left: 7, right: 8,
    insert: 9, delete: 10, home: 11, end: 12, pageup: 13, pagedown: 14,
};
for (let n = 1; n <= 12; n += 1) KEY_DB[`f${n}`] = 256 + n;
const MODIFIER_DB = { shift: 1, alt: 2, ctrl: 4 };

class LibraryMissing extends Error {
    /* RETURN: LibraryMissing: 'libvterm' was not found. */
    constructor(message) { super(message); this.name = 'LibraryMissing'; }
}
class IndexError extends Error {
    /* RETURN: IndexError, as Python's: a place not on the screen. */
    constructor(message) { super(message); this.name = 'IndexError'; }
}
class KeyError extends Error {
    /* RETURN: KeyError, as Python's: 'message' is the key's repr ("'nosuch'"). */
    constructor(message) { super(message); this.name = 'KeyError'; }
}
class TimeoutError extends Error {
    /* RETURN: TimeoutError, as Python's. */
    constructor(message) { super(message); this.name = 'TimeoutError'; }
}
class RuntimeError extends Error {
    /* RETURN: RuntimeError, as Python's. */
    constructor(message) { super(message); this.name = 'RuntimeError'; }
}

class Event {
    /* RETURN: Event, ONE THING THE TERMINAL DID (the RAW layer):
     *     kind 'damage'    rows 'row'..'row_end', columns 'column'..'column_end'
     *                      changed, ends EXCLUDED
     *          'cursor'    the cursor stands at (row, column); 'value': visible
     *          'property'  the property 'name' is now 'value' (null for a text)
     *          'bell'      the bell rang */
    constructor(kind, { row = null, column = null, row_end = null, column_end = null,
                        name = null, value = null } = {}) {
        Object.assign(this, { kind, row, column, row_end, column_end, name, value });
        Object.freeze(this);
    }

    /* RETURN: string, the event on one line, as the Python test prints it. */
    toString() {
        if (this.kind === 'damage')
            return `damage    rows ${this.row}..${this.row_end}  columns ${this.column}..${this.column_end}`;
        if (this.kind === 'cursor')
            return `cursor    (${this.row}, ${this.column})${this.value ? '' : '  hidden'}`;
        if (this.kind === 'property')
            return `property  ${this.name} = ${this.value === null ? 'None' : this.value}`;
        return this.kind;
    }
}

class Cell {
    /* RETURN: Cell, ONE CELL OF THE SCREEN as plain values: 'text' ('' for a
     *         cell nothing was written to, and for the right half of a wide
     *         character), 'width', the attribute flags '<name>_f', and
     *         'foreground'/'background' as [red, green, blue] -- null where
     *         the cell wears the terminal's default. */
    constructor(fields = {}) {
        Object.assign(this, {
            text: '', width: 1, bold_f: false, italic_f: false, underline_f: false, blink_f: false,
            reverse_f: false, conceal_f: false, strike_f: false, foreground: null, background: null,
        }, fields);
        Object.freeze(this);
    }

    /* RETURN: string, the attributes that are set, by name, in the fixed
     *         order of ATTRIBUTE_SGR_DB, separated by blanks ('bold
     *         reverse'); '' where none is set. */
    attribute_text() {
        return Object.keys(ATTRIBUTE_SGR_DB).filter(name => this[`${name}_f`]).join(' ');
    }
}

let koffi    = null;        // the package, required once
let _library = null;        // the loaded library and its functions, once
let _layout  = null;        // its measured layout, once
let _libc    = null;        // libc's functions for the pseudo-terminal, once

/* RETURN: the 'koffi' module; throws LibraryMissing (with the way to install
 *         it) where the package is not installed beside this file. */
function ffi() {
    if (koffi !== null) return koffi;
    try {
        koffi = require('koffi');
    } catch (error) {
        throw new LibraryMissing("the npm package 'koffi' is not installed -- run 'npm install' in "
                                 + `'${__dirname}'\n${INSTALL_HINT}`);
    }
    return koffi;
}

/* RETURN: object, 'libvterm' loaded once -- its functions declared, 'name'
 *         the file it was loaded as; throws LibraryMissing, if no such
 *         library is found or it cannot be loaded. */
function library() {
    if (_library !== null) return _library;
    const k = ffi();
    const given = process.env[LIBRARY_VARIABLE];
    let lib = null, name = null;
    if (given) {
        try { lib = k.load(given); name = given; }
        catch (error) {
            throw new LibraryMissing(`libvterm cannot be loaded from '${given}' -- ${error.message}\n${INSTALL_HINT}`);
        }
    } else {
        for (const candidate of LIBRARY_NAME_LIST) {
            try { lib = k.load(candidate); name = candidate; break; } catch (error) { /* the next */ }
        }
        if (lib === null)
            throw new LibraryMissing(`libvterm is not installed, and '${LIBRARY_VARIABLE}' names no file\n${INSTALL_HINT}`);
    }
    const t = typeOnce(k);
    const f = proto => lib.func(proto);
    const result = {
        name,
        vterm_new:                     f('void *vterm_new(int, int)'),
        vterm_free:                    f('void vterm_free(void *)'),
        vterm_set_utf8:                f('void vterm_set_utf8(void *, int)'),
        vterm_input_write:             f('size_t vterm_input_write(void *, const uint8_t *, size_t)'),
        vterm_obtain_screen:           f('void *vterm_obtain_screen(void *)'),
        vterm_obtain_state:            f('void *vterm_obtain_state(void *)'),
        vterm_screen_reset:            f('void vterm_screen_reset(void *, int)'),
        vterm_screen_enable_altscreen: f('void vterm_screen_enable_altscreen(void *, int)'),
        vterm_screen_get_cell:         f('int vterm_screen_get_cell(void *, HwutVTermPos, void *)'),
        vterm_state_get_cursorpos:     f('void vterm_state_get_cursorpos(void *, void *)'),
        vterm_output_set_callback:     f('void vterm_output_set_callback(void *, HwutVTermOutput *, void *)'),
        vterm_keyboard_unichar:        f('void vterm_keyboard_unichar(void *, uint32_t, int)'),
        vterm_keyboard_key:            f('void vterm_keyboard_key(void *, int, int)'),
        vterm_screen_set_callbacks:    f('void vterm_screen_set_callbacks(void *, void *, void *)'),
        vterm_screen_set_damage_merge: f('void vterm_screen_set_damage_merge(void *, int)'),
        vterm_screen_flush_damage:     f('void vterm_screen_flush_damage(void *)'),
        vterm_screen_convert_color_to_rgb: null,
        type: t,
    };
    //  ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
    try { result.vterm_screen_convert_color_to_rgb = f('void vterm_screen_convert_color_to_rgb(void *, void *)'); }
    catch (error) { result.vterm_screen_convert_color_to_rgb = null; }
    _library = result;
    return result;
}

let _type = null;
/* RETURN: object, the koffi types of libvterm's structures and callbacks --
 *         declared once per process (koffi's names are global). The
 *         callback shapes are the same in every version measured; the
 *         callbacks structure ends in spare null slots. */
function typeOnce(k) {
    if (_type !== null) return _type;
    k.struct('HwutVTermPos',  { row: 'int', col: 'int' });
    k.struct('HwutVTermRect', { start_row: 'int', end_row: 'int', start_col: 'int', end_col: 'int' });
    const output     = k.proto('void HwutVTermOutput(const uint8_t *data, size_t length, void *user)');
    const damage     = k.proto('int HwutVTermDamage(HwutVTermRect rectangle, void *user)');
    const movecursor = k.proto('int HwutVTermMoveCursor(HwutVTermPos position, HwutVTermPos old, int visible, void *user)');
    const property   = k.proto('int HwutVTermProperty(int number, int *value, void *user)');
    const bell       = k.proto('int HwutVTermBell(void *user)');
    const callbacks  = k.struct('HwutVTermScreenCallbacks', {
        damage: 'HwutVTermDamage *', moverect: 'void *', movecursor: 'HwutVTermMoveCursor *',
        settermprop: 'HwutVTermProperty *', bell: 'HwutVTermBell *', resize: 'void *',
        sb_pushline: 'void *', sb_popline: 'void *', spare: k.array('void *', 8),
    });
    _type = { output, damage, movecursor, property, bell, callbacks };
    return _type;
}

/* RETURN: undefined; the loaded library (and its measured layout) are
 *         forgotten, so the next Screen looks for it again under
 *         HWUT_LIBVTERM -- what Python's test does by 'hwut_vterm._library =
 *         None'. */
function _forget_library() { _library = null; _layout = null; }

/* RETURN: string, 'libvterm found: <name>', if the library loads; the text
 *         of LibraryMissing -- what is wrong and how to install it -- else. */
function detection_text() {
    try {
        return `libvterm found: ${library().name}`;
    } catch (error) {
        if (error instanceof LibraryMissing) return error.message;
        throw error;
    }
}

class Screen {
    /* RETURN: Screen, a terminal of 'row_n' rows and 'column_n' columns,
     *         blank, the cursor at (0, 0); throws LibraryMissing, if
     *         'libvterm' is not found. Call 'close()' (or 'use(block)'): the
     *         terminal is the library's memory, not JS's. */
    constructor(row_n = 24, column_n = 80) {
        this.row_n = row_n; this.column_n = column_n;
        this._lib      = library();
        this._terminal = this._lib.vterm_new(row_n, column_n);
        this._lib.vterm_set_utf8(this._terminal, 1);
        this._screen   = this._lib.vterm_obtain_screen(this._terminal);
        this._state    = this._lib.vterm_obtain_state(this._terminal);
        //  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR.
        this._lib.vterm_screen_enable_altscreen(this._screen, 1);
        this._lib.vterm_screen_reset(this._screen, 1);
    }

    /* RETURN: what 'block(this)' returns; the screen is closed after it,
     *         whatever way it ends -- Python's 'with'. */
    use(block) {
        try { return block(this); }
        finally { this.close(); }
    }

    /* RETURN: undefined. The terminal's memory is freed; a second call does
     *         nothing. */
    close() {
        if (this._terminal !== null) {
            this._lib.vterm_free(this._terminal);
            this._terminal = this._screen = this._state = null;
        }
    }

    /* RETURN: integer, the number of bytes the terminal took -- all of them,
     *         where it works as documented. 'data' is what a program wrote: a
     *         Buffer, or a string sent as UTF-8. */
    feed(data) {
        const bytes = typeof data === 'string' ? Buffer.from(data, 'utf8') : Buffer.from(data);
        return Number(this._lib.vterm_input_write(this._terminal, bytes, bytes.length));
    }

    /* RETURN: [integer, integer], the cursor's row and column, from 0. */
    cursor() {
        const position = Buffer.alloc(8);
        this._lib.vterm_state_get_cursorpos(this._state, position);
        return [position.readInt32LE(0), position.readInt32LE(4)];
    }

    /* RETURN: Buffer (CELL_BYTE_N), the library's own cell at that place,
     *         its colours resolved to red, green, blue where the library
     *         keeps them otherwise (once the layout is measured). */
    _raw(row, column) {
        const buffer = Buffer.alloc(CELL_BYTE_N);
        this._lib.vterm_screen_get_cell(this._screen, { row, col: column }, buffer);
        if (_layout !== null && _layout.convert_f) {
            //  THE COLOUR'S STRUCTURE begins one byte before its red.
            for (const start of [_layout.foreground_i, _layout.background_i])
                this._lib.vterm_screen_convert_color_to_rgb(this._screen, buffer.subarray(start - 1));
        }
        return buffer;
    }

    /* RETURN: Cell, what stands at that place; throws IndexError, if the
     *         place is not on the screen. */
    cell(row, column) {
        if (!(row >= 0 && row < this.row_n && column >= 0 && column < this.column_n))
            throw new IndexError(`(${row}, ${column}) is not on a screen of ${this.row_n} x ${this.column_n}`);
        const layout = measured();
        const raw    = this._raw(row, column);
        let text = '';
        for (let i = 0; i < CHARS_BYTE_N; i += 4) {
            const code = raw.readUInt32LE(i);
            if (code !== 0 && code !== 0xFFFFFFFF) text += String.fromCodePoint(code);
        }
        const colour = (i, deflt) => {
            const rgb = [raw[i], raw[i + 1], raw[i + 2]];
            return rgb.every((v, j) => v === deflt[j]) && deflt.length === 3 ? null : rgb;
        };
        const fields = {
            text, width: raw[CHARS_BYTE_N] || 1,
            foreground: colour(layout.foreground_i, layout.default_fg),
            background: colour(layout.background_i, layout.default_bg),
        };
        for (const [name, [offset, mask]] of Object.entries(layout.mask_db))
            fields[`${name}_f`] = !!(raw[offset] & mask);
        return new Cell(fields);
    }

    /* RETURN: string, the row's characters, blanks at its end dropped; a
     *         cell nothing was written to reads as a blank. */
    line(row) {
        return this._text_of(row, 0, this.column_n);
    }

    /* RETURN: string, the characters of 'row' from 'column' for 'column_n'
     *         columns -- a wide character's right half skipped, an empty
     *         cell a blank -- blanks at the end dropped. */
    _text_of(row, column, column_n) {
        let text = '', at = column;
        while (at < column + column_n) {
            const cell = this.cell(row, at);
            text += cell.text || ' ';
            at += Math.max(cell.width, 1);
        }
        return text.replace(/\s+$/u, '');
    }

    /* RETURN: array of strings, every row as 'line()' gives it, top first. */
    line_list() {
        return Array.from({ length: this.row_n }, (_, row) => this.line(row));
    }
}

/* RETURN: number, a monotonic clock in seconds. */
function monotonic() { return Number(process.hrtime.bigint()) / 1e9; }

const SLEEPER = new Int32Array(new SharedArrayBuffer(4));
/* RETURN: undefined, after 'seconds' -- blocking, as Python's 'time.sleep'. */
function sleepSync(seconds) { Atomics.wait(SLEEPER, 0, 0, Math.max(0, seconds * 1000)); }

/* RETURN: object, the libc functions and constants the pseudo-terminal
 *         takes, loaded once. */
function libc() {
    if (_libc !== null) return _libc;
    const k = ffi();
    const c = k.load(process.platform === 'darwin' ? 'libc.dylib' : 'libc.so.6');
    const f = proto => c.func(proto);
    const optional = proto => { try { return f(proto); } catch (error) { return null; } };
    _libc = {
        posix_openpt:  f('int posix_openpt(int)'),
        grantpt:       f('int grantpt(int)'),
        unlockpt:      f('int unlockpt(int)'),
        ptsname_r:     f('int ptsname_r(int, _Out_ uint8_t *buffer, size_t)'),
        ioctl:         f('int ioctl(int, unsigned long, ...)'),
        close:         f('int close(int)'),
        read:          f('long read(int, void *, size_t)'),
        write:         f('long write(int, const void *, size_t)'),
        poll:          f('int poll(void *, unsigned long, int)'),
        waitpid:       f('int waitpid(int, _Out_ int *status, int)'),
        kill:          f('int kill(int, int)'),
        sigfillset:    f('int sigfillset(void *)'),
        sigemptyset:   f('int sigemptyset(void *)'),
        fa_init:       f('int posix_spawn_file_actions_init(void *)'),
        fa_destroy:    f('int posix_spawn_file_actions_destroy(void *)'),
        fa_addopen:    f('int posix_spawn_file_actions_addopen(void *, int, const char *, int, unsigned int)'),
        fa_adddup2:    f('int posix_spawn_file_actions_adddup2(void *, int, int)'),
        fa_addchdir:   optional('int posix_spawn_file_actions_addchdir_np(void *, const char *)'),
        attr_init:     f('int posix_spawnattr_init(void *)'),
        attr_destroy:  f('int posix_spawnattr_destroy(void *)'),
        attr_setflags: f('int posix_spawnattr_setflags(void *, short)'),
        attr_sigdef:   f('int posix_spawnattr_setsigdefault(void *, const void *)'),
        attr_sigmask:  f('int posix_spawnattr_setsigmask(void *, const void *)'),
        posix_spawnp:  f('int posix_spawnp(_Out_ int *pid, const char *file, void *actions, void *attr, const char **argv, const char **envp)'),
        //  Linux's numbers (glibc): the flags of 'open', the window-size
        //  request, the spawn attributes, 'poll' and 'waitpid'.
        O_RDWR: fs.constants.O_RDWR, O_NOCTTY: fs.constants.O_NOCTTY, O_CLOEXEC: 0o2000000,
        TIOCSWINSZ: 0x5414, POSIX_SPAWN_SETSIGDEF: 0x04, POSIX_SPAWN_SETSIGMASK: 0x08,
        POSIX_SPAWN_SETSID: 0x80, POLLIN: 0x1, WNOHANG: 1, SIGKILL: 9, EINTR: 4,
    };
    return _libc;
}

class Process {
    /* RETURN: Process, the application 'argv' started on the pseudo-terminal
     *         whose slave is the file 'slave_path': a new session, the slave
     *         its controlling terminal and its fd 0, 1, 2; every signal at
     *         its default; 'environment' (an object) as its environment;
     *         'cwd' (or null) its directory. Throws Error (with errno's
     *         number) where it cannot be started. */
    constructor(argv, environment, cwd, slave_path) {
        const c = libc();
        const actions = Buffer.alloc(512), attr = Buffer.alloc(1024);
        const sigdef = Buffer.alloc(256), sigmask = Buffer.alloc(256);
        c.fa_init(actions);
        c.attr_init(attr);
        try {
            c.fa_addopen(actions, 0, slave_path, c.O_RDWR, 0);
            c.fa_adddup2(actions, 0, 1);
            c.fa_adddup2(actions, 0, 2);
            if (cwd !== null && cwd !== undefined) {
                if (c.fa_addchdir === null) throw new Error("no 'posix_spawn_file_actions_addchdir_np': 'cwd' cannot be set");
                c.fa_addchdir(actions, String(cwd));
            }
            c.sigfillset(sigdef); c.sigemptyset(sigmask);
            c.attr_sigdef(attr, sigdef); c.attr_sigmask(attr, sigmask);
            c.attr_setflags(attr, c.POSIX_SPAWN_SETSID | c.POSIX_SPAWN_SETSIGDEF | c.POSIX_SPAWN_SETSIGMASK);
            const envp = Object.entries(environment).map(([k, v]) => `${k}=${v}`);
            const pid  = [0];
            const error = c.posix_spawnp(pid, String(argv[0]), actions, attr, [...argv.map(String), null], [...envp, null]);
            if (error !== 0) throw new Error(`posix_spawnp '${argv[0]}': errno ${error}`);
            this.pid = pid[0];
        } finally {
            c.fa_destroy(actions);
            c.attr_destroy(attr);
        }
        this.returncode = null;
    }

    /* RETURN: integer, the exit status -- minus the signal's number where a
     *         signal ended it -- where the application has ended; null where
     *         it still runs. */
    poll() {
        if (this.returncode !== null) return this.returncode;
        const status = [0];
        const pid = libc().waitpid(this.pid, status, libc().WNOHANG);
        if (pid === this.pid) {
            const s = status[0];
            this.returncode = (s & 0x7f) === 0 ? (s >> 8) & 0xff : -(s & 0x7f);
        }
        return this.returncode;
    }

    /* RETURN: integer, the exit status (see 'poll') once the application has
     *         ended; throws TimeoutError where it still runs after
     *         'timeout_s' seconds (null: wait for ever). */
    wait(timeout_s = null) {
        const deadline = timeout_s === null ? Infinity : monotonic() + timeout_s;
        while (this.poll() === null) {
            if (monotonic() >= deadline) throw new TimeoutError('TimeoutExpired');
            sleepSync(0.005);
        }
        return this.returncode;
    }

    /* RETURN: undefined. SIGKILL is sent, where the application still runs. */
    kill() { if (this.poll() === null) libc().kill(this.pid, libc().SIGKILL); }
}

class Terminal extends Screen {
    /* RETURN: Terminal, blank, nothing running in it; throws LibraryMissing,
     *         if 'libvterm' is not found. 'settle_s' is how long the
     *         application must write nothing before its screen is taken as
     *         drawn.
     *
     * TWO LAYERS OF OBSERVATION:
     *     on_event    RAW: every Event libvterm reports, as it happens.
     *     on_change   REGIONS: a named rectangle's text, told once it has
     *                 CHANGED and the application has gone QUIET; one call
     *                 per changed region and pause, in declaration order. */
    constructor(row_n = 24, column_n = 80, settle_s = 0.1) {
        super(row_n, column_n);
        this.settle_s        = settle_s;
        this._event_f_list   = [];
        this._change_f_list  = [];
        this._region_db      = new Map();   // name -> [row, row_n, column, column_n]
        this._told_db        = new Map();   // name -> the lines last told
        this._answer         = [];          // Buffers the terminal said
        this._master         = null;
        this._process        = null;
        this._ended_f        = false;
        const k = ffi(), t = this._lib.type;
        //  THE CALLBACKS LIVE AS LONG AS THE TERMINAL: libvterm keeps their
        //  addresses -- registered, and their structure in C memory.
        this._registered = [
            k.register((data, length) => { this._on_output(data, length); }, k.pointer(t.output)),
            k.register(rectangle => this._on_damage(rectangle), k.pointer(t.damage)),
            k.register((position, old, visible) => this._on_cursor(position, visible), k.pointer(t.movecursor)),
            k.register((number, value) => this._on_property(number, value), k.pointer(t.property)),
            k.register(() => this._on_bell(), k.pointer(t.bell)),
        ];
        const [output, damage, movecursor, settermprop, bell] = this._registered;
        this._callbacks = k.alloc(t.callbacks, 1);
        k.encode(this._callbacks, t.callbacks, {
            damage, moverect: null, movecursor, settermprop, bell, resize: null,
            sb_pushline: null, sb_popline: null, spare: new Array(8).fill(null),
        });
        this._lib.vterm_output_set_callback(this._terminal, output, null);
        this._lib.vterm_screen_set_callbacks(this._screen, this._callbacks, null);
        this._lib.vterm_screen_set_damage_merge(this._screen, DAMAGE_MERGE_ROW);
    }

    //  ------------------------------------------------------- observation
    /* RETURN: undefined. 'callback(event)' is called with every raw Event
     *         from now on. */
    on_event(callback) { this._event_f_list.push(callback); }

    /* RETURN: undefined. 'callback(name, line_list)' is called for every
     *         region whose text changed, once the screen is quiet. */
    on_change(callback) { this._change_f_list.push(callback); }

    /* RETURN: undefined. The rectangle 'name' is observed from now on:
     *         'row_n' rows from 'row', 'column_n' columns from 'column' (to
     *         the right edge where null). A NEGATIVE 'row' counts from the
     *         bottom: -1 is the last row. What stands there now is known,
     *         not news: only a change is told. */
    region(name, row, row_n = 1, column = 0, column_n = null) {
        if (row < 0) row += this.row_n;
        if (column_n === null || column_n === undefined) column_n = this.column_n - column;
        this._region_db.set(name, [row, row_n, column, column_n]);
        this._told_db.set(name, this.region_text(name));
    }

    /* RETURN: array of strings, the region's rows as they stand now, blanks
     *         at each row's end dropped; throws KeyError, if no such region
     *         was declared. */
    region_text(name) {
        if (!this._region_db.has(name)) throw new KeyError(`'${name}'`);
        const [row, row_n, column, column_n] = this._region_db.get(name);
        const result = [];
        for (let each = row; each < row + row_n; each += 1) result.push(this._text_of(each, column, column_n));
        return result;
    }

    /* RETURN: array of strings, the names of the regions whose text differs
     *         from what was last told -- each told to every 'on_change'
     *         callback, in the order of declaration. */
    report() {
        const changed = [];
        for (const name of this._region_db.keys()) {
            const lineList = this.region_text(name);
            const told     = this._told_db.get(name);
            if (told && told.length === lineList.length && told.every((l, i) => l === lineList[i])) continue;
            this._told_db.set(name, lineList);
            changed.push(name);
            for (const callback of this._change_f_list) callback(name, lineList);
        }
        return changed;
    }

    /* RETURN: 1, libvterm's 'handled'. The event reaches every raw callback. */
    _emit(event) {
        for (const callback of this._event_f_list) callback(event);
        return 1;
    }

    _on_damage(r) {
        return this._emit(new Event('damage', { row: r.start_row, column: r.start_col,
                                                row_end: r.end_row, column_end: r.end_col }));
    }

    _on_cursor(p, visible) {
        return this._emit(new Event('cursor', { row: p.row, column: p.col, value: !!visible }));
    }

    _on_property(number, value) {
        const [name, plainF] = PROPERTY_DB[number] || [`property-${number}`, false];
        return this._emit(new Event('property', { name, value: plainF ? ffi().decode(value, 'int') : null }));
    }

    _on_bell() { return this._emit(new Event('bell')); }

    /* RETURN: undefined. What the TERMINAL says -- a key's sequence, the
     *         answer to a question -- is collected for the application. */
    _on_output(data, length) {
        const n = Number(length);
        if (n > 0) this._answer.push(Buffer.from(ffi().decode(data, ffi().array('uint8_t', n))));
    }

    //  --------------------------------------------------- bytes in and out
    /* RETURN: integer, the number of bytes the terminal took. The raw events
     *         of what was fed fire before this returns; what the terminal
     *         answered goes to the application, where one runs. */
    feed(data) {
        const taken = super.feed(data);
        this._lib.vterm_screen_flush_damage(this._screen);
        this._forward();
        return taken;
    }

    /* RETURN: Buffer, what the terminal said since the last call and no
     *         application took. */
    answer() {
        const data = Buffer.concat(this._answer);
        this._answer = [];
        return data;
    }

    /* RETURN: undefined. The terminal's words reach the application, if one
     *         runs; they wait in 'answer()' otherwise. */
    _forward() {
        if (this._master === null || this._answer.length === 0) return;
        const data = Buffer.concat(this._answer);
        if (libc().write(this._master, data, data.length) < 0) this._ended_f = true;
        this._answer = [];
    }

    /* RETURN: boolean, true if the application still runs after it. 'text'
     *         is typed, character by character, as a keyboard sends it; then
     *         the screen is given 'react_s' to begin answering and is read
     *         until quiet. */
    send(text, react_s = 1.0) {
        for (const character of text)
            this._lib.vterm_keyboard_unichar(this._terminal, character.codePointAt(0), 0);
        this._forward();
        return this.pump(react_s);
    }

    /* RETURN: boolean, true if the application still runs after it; throws
     *         KeyError, if 'key' or a modifier has no name here. 'key' is a
     *         name of KEY_DB ('enter', 'up', 'f5', ...) or one character;
     *         'modifier_list' holds 'shift', 'alt', 'ctrl' --
     *         'press("c", ["ctrl"])' is Ctrl-C. */
    press(key, modifier_list = [], react_s = 1.0) {
        let modifier = 0;
        for (const name of modifier_list) {
            if (!(name in MODIFIER_DB)) throw new KeyError(`'${name}'`);
            modifier |= MODIFIER_DB[name];
        }
        if ([...key].length === 1) {
            this._lib.vterm_keyboard_unichar(this._terminal, key.codePointAt(0), modifier);
        } else {
            if (!(key in KEY_DB)) throw new KeyError(`'${key}'`);
            this._lib.vterm_keyboard_key(this._terminal, KEY_DB[key], modifier);
        }
        this._forward();
        return this.pump(react_s);
    }

    //  ------------------------------------------------------ the application
    /* RETURN: boolean, true if the application still runs once its first
     *         screen stands; throws RuntimeError, if one already runs here.
     *
     * 'argv' is started on a pseudo-terminal of this terminal's size: stdin,
     * stdout and stderr are that terminal, and it is the application's
     * controlling one. TERM is 'xterm-256color'; LINES and COLUMNS are taken
     * OUT of the environment ('env', default 'process.env'). */
    run(argv, env = null, cwd = null, start_s = 10.0) {
        if (this._process !== null) throw new RuntimeError('an application already runs in this terminal');
        const c = libc();
        const master = c.posix_openpt(c.O_RDWR | c.O_NOCTTY | c.O_CLOEXEC);
        if (master < 0 || c.grantpt(master) !== 0 || c.unlockpt(master) !== 0)
            throw new RuntimeError('no pseudo-terminal: posix_openpt/grantpt/unlockpt failed');
        const name = Buffer.alloc(256);
        c.ptsname_r(master, name, name.length);
        const slavePath = name.toString('latin1', 0, name.indexOf(0));
        const size = Buffer.alloc(8);
        size.writeUInt16LE(this.row_n, 0); size.writeUInt16LE(this.column_n, 2);
        c.ioctl(master, c.TIOCSWINSZ, 'void *', size);
        const environment = { ...(env === null || env === undefined ? process.env : env) };
        environment.TERM = 'xterm-256color';
        delete environment.LINES; delete environment.COLUMNS;
        this._master  = master;
        try {
            this._process = new Process(argv, environment, cwd, slavePath);
        } catch (error) {
            c.close(master); this._master = null;
            throw error;
        }
        this._ended_f = false;
        return this.pump(start_s);
    }

    /* RETURN: boolean, true if the application still runs. READ UNTIL QUIET:
     *         wait up to 'first_s' for the application to write at all, then
     *         go on reading until it has written nothing for 'settle_s'. Then
     *         the changed regions are reported. */
    pump(first_s = 1.0) {
        let waitS = first_s;
        if (this._master !== null && !this._ended_f) {
            const c = libc();
            const pollfd = Buffer.alloc(8), data = Buffer.alloc(65536);
            while (this._master !== null && !this._ended_f) {
                pollfd.writeInt32LE(this._master, 0); pollfd.writeInt16LE(c.POLLIN, 4); pollfd.writeInt16LE(0, 6);
                const ready = c.poll(pollfd, 1, Math.round(waitS * 1000));
                if (ready < 0 && ffi().errno() === c.EINTR) continue;
                if (ready <= 0) break;
                const n = Number(c.read(this._master, data, data.length));
                if (n <= 0) { this._ended_f = true; break; }   // the last writer closed: it ended
                this.feed(Buffer.from(data.subarray(0, n)));
                waitS = this.settle_s;
            }
        }
        this.report();
        return this._process !== null && this._process.poll() === null && !this._ended_f;
    }

    /* RETURN: [integer, integer], the row and column where 'text' stands on
     *         the screen, once it does; throws TimeoutError, carrying the
     *         screen, if it does not within 'timeout_s'. */
    expect(text, timeout_s = 10.0) {
        const deadline = monotonic() + timeout_s;
        while (true) {
            const lineList = this.line_list();
            for (let row = 0; row < lineList.length; row += 1) {
                const at = lineList[row].indexOf(text);
                if (at >= 0) return [row, [...lineList[row].slice(0, at)].length];
            }
            if (monotonic() >= deadline || this._ended_f || this._master === null)
                throw new TimeoutError(`'${text}' did not appear; the screen:\n${lineList.join('\n')}`);
            this.pump(this.settle_s);
        }
    }

    /* RETURN: integer, the application's exit status, once it has ended and
     *         its last words are on the screen; null, if no application was
     *         run; throws TimeoutError, if it still runs after 'timeout_s'
     *         -- it is killed first. */
    wait(timeout_s = 10.0) {
        if (this._process === null) return null;
        const deadline = monotonic() + timeout_s;
        while (this.pump(this.settle_s)) {
            if (monotonic() >= deadline) {
                this._process.kill(); this._process.wait();
                throw new TimeoutError(`the application still ran after ${timeout_s.toFixed(1)} s`);
            }
        }
        try {
            return this._process.wait(Math.max(deadline - monotonic(), 0.1));
        } catch (error) {
            if (!(error instanceof TimeoutError)) throw error;
            this._process.kill(); this._process.wait();
            throw new TimeoutError('the application closed its terminal and did not end');
        }
    }

    /* RETURN: undefined. An application still running is killed (and
     *         reaped), the pseudo-terminal closed, the callbacks released,
     *         the terminal's memory freed; a second call does nothing. */
    close() {
        if (this._process !== null && this._process.poll() === null) {
            this._process.kill(); this._process.wait();
        }
        if (this._master !== null) { libc().close(this._master); this._master = null; }
        const wasOpen = this._terminal !== null;
        super.close();
        if (wasOpen) {
            const k = ffi();
            for (const callback of this._registered) k.unregister(callback);
            this._registered = [];
            k.free(this._callbacks);
            this._callbacks = null;
        }
    }
}

/* RETURN: object, where this library's cell keeps each attribute and each
 *         colour -- { mask_db: name -> [offset, bits], foreground_i,
 *         background_i, convert_f, default_fg, default_bg } -- measured once
 *         on scratch terminals, then remembered. */
function measured() {
    if (_layout !== null) return _layout;

    const cellAfter = sequence => new Screen(2, 4).use(scratch => {
        scratch.feed(sequence ? `\x1b[${sequence}m` : '');
        scratch.feed('X');
        return scratch._raw(0, 0);
    });
    const plain = cellAfter('');
    const changed = raw => {
        const found = [];
        for (let i = CHARS_BYTE_N + 1; i < CELL_BYTE_N; i += 1)
            if (plain[i] !== raw[i]) found.push([i, plain[i] ^ raw[i]]);
        return found;
    };
    const mask_db = {};
    for (const [name, code] of Object.entries(ATTRIBUTE_SGR_DB)) {
        const found = changed(cellAfter(code));
        //  NOTHING MOVED: this library does not know the attribute.
        mask_db[name] = found.length ? found[0] : [CHARS_BYTE_N + 1, 0];
    }
    //  UNDERLINE IS A NUMBER OF TWO BITS: any of them is 'underlined'.
    for (const [offset, bits] of changed(cellAfter('21')))
        if (offset === mask_db.underline[0]) mask_db.underline = [offset, mask_db.underline[1] | bits];

    const colourAt = code => cellAfter(`${code};2;1;2;3`).indexOf(Buffer.from([1, 2, 3]), CHARS_BYTE_N + 1);
    const foreground_i = colourAt('38');
    const background_i = colourAt('48');
    const convert_f    = library().vterm_screen_convert_color_to_rgb !== null;
    //  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be
    //  read from now on.
    _layout = { mask_db, foreground_i, background_i, convert_f, default_fg: [], default_bg: [] };
    const raw = new Screen(2, 4).use(scratch => { scratch.feed('X'); return scratch._raw(0, 0); });
    _layout = { mask_db, foreground_i, background_i, convert_f,
                default_fg: [...raw.subarray(foreground_i, foreground_i + 3)],
                default_bg: [...raw.subarray(background_i, background_i + 3)] };
    return _layout;
}

module.exports = {
    Screen, Terminal, Cell, Event, LibraryMissing, IndexError, KeyError, TimeoutError, RuntimeError,
    ATTRIBUTE_SGR_DB, KEY_DB, MODIFIER_DB, PROPERTY_DB, LIBRARY_VARIABLE, INSTALL_HINT,
    library, detection_text, _forget_library,
};

if (require.main === module) {
    //  THE DETECTION, asked by hand: is the library there?
    console.log(detection_text());
    process.exitCode = _library !== null ? 0 : 1;
}

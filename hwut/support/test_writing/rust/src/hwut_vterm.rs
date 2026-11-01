// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
//          'python/hwut_vterm.py' (README-hwut_vterm.txt): 'libvterm',
//          loaded at run time by 'dlopen', as Python's binding loads it by
//          'ctypes'. Bytes go in; the grid of cells -- characters,
//          attributes, colours, the cursor -- is read back as plain values a
//          test prints.
//
//     use hwut::hwut_vterm::Screen;
//     let mut screen = Screen::new(24, 80)?;
//     screen.feed("\x1b[1mbold\x1b[0m plain");
//     println!("{}", screen.line(0));                  // 'bold plain'
//     println!("{}", screen.cell(0, 0)?.bold_f);       // true
//     println!("{:?}", screen.cursor());               // (0, 10)
//
// THE LIBRARY IS FOUND, NOT SHIPPED: 'libvterm.so.0' as the system knows it
// (Debian: 'libvterm0'), or the file the environment variable HWUT_LIBVTERM
// names. NO HEADER is needed: the few structures are declared here as the
// Python binding declares them. Where the library is missing, 'Screen::new'
// returns 'VtermError::LibraryMissing', whose text says how to install it.
//
// THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED: once per library, a scratch
// terminal is fed one attribute at a time, and the bit or the bytes that
// changed are where that attribute stands (Python's '_measured').
//
// TWO TYPES, as Python's two classes:
//     Screen      the grid alone: bytes in, cells out. No process.
//     Terminal    a Screen an APPLICATION RUNS IN ('Deref' to its Screen):
//                 set up, declare what to observe, then 'run()' -- on a
//                 pseudo-terminal, so the application cannot tell. Keys go
//                 in as a keyboard sends them; observation is by closure,
//                 raw ('on_event') or by named region ('on_change').
//
// WHAT PYTHON RAISES is returned: 'Err(VtermError)', 'kind()' Python's
// exception name, the Display its text. 'with' is the value's scope: the
// terminal's memory is freed, and an application still running killed, when
// it is dropped ('close()' does it before).
//______________________________________________________________________________
use std::cell::RefCell;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::fmt;
use std::os::raw::{c_char, c_int, c_void};
use std::rc::Rc;
use std::time::{Duration, Instant};

use crate::posix;

/// The environment variable that names the library's file.
pub const LIBRARY_VARIABLE: &str = "HWUT_LIBVTERM";

/// WHAT IS THE SAME IN EVERY VERSION: six code points of four bytes, then the
/// width; everything behind them is measured.
const CHARS_PER_CELL_N: usize = 6;
const CHARS_BYTE_N:     usize = 4 * CHARS_PER_CELL_N;
const CELL_BYTE_N:      usize = 128;              // room beyond any version's cell
const DAMAGE_MERGE_ROW: c_int = 1;

/// The attributes a cell is asked for, each with the SGR code that sets it,
/// in Python's order.
pub const ATTRIBUTE_SGR_DB: [(&str, &str); 7] = [
    ("bold", "1"), ("italic", "3"), ("underline", "4"), ("blink", "5"),
    ("reverse", "7"), ("conceal", "8"), ("strike", "9"),
];

/// What a person is told where the library is not found: how to get it.
pub const INSTALL_HINT: &str = "HINT: install the library, or name its file:\n\
    \x20   Debian, Ubuntu   apt install libvterm0\n\
    \x20   Fedora           dnf install libvterm\n\
    \x20   Arch             pacman -S libvterm\n\
    \x20   macOS            brew install libvterm\n\
    \x20   elsewhere        export HWUT_LIBVTERM=<path>/libvterm.so\n\
    \x20   or work inside   hwut.dev.podman.enter   (the image holds it)";

/// The properties a terminal reports, by libvterm's number: (name, the
/// value is a flag or a number).
const PROPERTY_DB: [(c_int, &str, bool); 9] = [
    (1, "cursor-visible", true), (2, "cursor-blink", true), (3, "alternate-screen", true),
    (4, "title", false), (5, "icon-name", false), (6, "reverse-video", true),
    (7, "cursor-shape", true), (8, "mouse", true), (9, "focus-report", true),
];

/// RETURN: Option<c_int>, libvterm's number of the key a test presses by
///         'name' ('enter', 'up', 'f5', ...); None where it has none.
fn key_of(name: &str) -> Option<c_int> {
    const KEY_DB: [(&str, c_int); 14] = [
        ("enter", 1), ("tab", 2), ("backspace", 3), ("escape", 4), ("up", 5), ("down", 6),
        ("left", 7), ("right", 8), ("insert", 9), ("delete", 10), ("home", 11), ("end", 12),
        ("pageup", 13), ("pagedown", 14),
    ];
    if let Some((_, key)) = KEY_DB.iter().find(|(n, _)| *n == name) { return Some(*key); }
    let n: c_int = name.strip_prefix('f')?.parse().ok()?;
    if (1..=12).contains(&n) && name == format!("f{}", n) { Some(256 + n) } else { None }
}

/// RETURN: Option<c_int>, the modifier bit of 'name' ('shift', 'alt',
///         'ctrl'); None where it has none.
fn modifier_of(name: &str) -> Option<c_int> {
    match name { "shift" => Some(1), "alt" => Some(2), "ctrl" => Some(4), _ => None }
}

/// What a terminal refuses -- Python's exceptions, by name.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum VtermError {
    LibraryMissing(String),
    IndexError(String),
    KeyError(String),
    RuntimeError(String),
    TimeoutError(String),
    OSError(String),
}

impl VtermError {
    /// RETURN: &str, Python's exception name: 'LibraryMissing', 'KeyError', ...
    pub fn kind(&self) -> &'static str {
        match self {
            VtermError::LibraryMissing(_) => "LibraryMissing", VtermError::IndexError(_) => "IndexError",
            VtermError::KeyError(_) => "KeyError", VtermError::RuntimeError(_) => "RuntimeError",
            VtermError::TimeoutError(_) => "TimeoutError", VtermError::OSError(_) => "OSError",
        }
    }

    /// RETURN: &str, the text -- as Python's 'str(error)' gives it.
    pub fn message(&self) -> &str {
        match self {
            VtermError::LibraryMissing(m) | VtermError::IndexError(m) | VtermError::KeyError(m)
            | VtermError::RuntimeError(m) | VtermError::TimeoutError(m) | VtermError::OSError(m) => m,
        }
    }
}

impl fmt::Display for VtermError {
    /// RETURN: fmt::Result; the text was written.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{}", self.message()) }
}

impl std::error::Error for VtermError {}

// --------------------------------------------- the library's own structures
#[repr(C)]
#[derive(Clone, Copy, Default)]
struct VTermPos { row: c_int, col: c_int }

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct VTermRect { start_row: c_int, end_row: c_int, start_col: c_int, end_col: c_int }

/// 'VTermScreenCallbacks': the five this module answers, the three it leaves
/// null, and spare slots for what later versions append.
#[repr(C)]
struct ScreenCallbacks {
    damage:      Option<extern "C" fn(VTermRect, *mut c_void) -> c_int>,
    moverect:    Option<extern "C" fn(VTermRect, VTermRect, *mut c_void) -> c_int>,
    movecursor:  Option<extern "C" fn(VTermPos, VTermPos, c_int, *mut c_void) -> c_int>,
    settermprop: Option<extern "C" fn(c_int, *mut c_int, *mut c_void) -> c_int>,
    bell:        Option<extern "C" fn(*mut c_void) -> c_int>,
    resize:      *mut c_void,
    sb_pushline: *mut c_void,
    sb_popline:  *mut c_void,
    spare:       [*mut c_void; 8],
}

type P = *mut c_void;
type OutputF = extern "C" fn(*const c_char, usize, *mut c_void);

/// The loaded library: its functions, found by 'dlsym'.
struct Library {
    handle:                        P,
    name:                          String,
    vterm_new:                     unsafe extern "C" fn(c_int, c_int) -> P,
    vterm_free:                    unsafe extern "C" fn(P),
    vterm_set_utf8:                unsafe extern "C" fn(P, c_int),
    vterm_input_write:             unsafe extern "C" fn(P, *const c_char, usize) -> usize,
    vterm_obtain_screen:           unsafe extern "C" fn(P) -> P,
    vterm_obtain_state:            unsafe extern "C" fn(P) -> P,
    vterm_screen_reset:            unsafe extern "C" fn(P, c_int),
    vterm_screen_enable_altscreen: unsafe extern "C" fn(P, c_int),
    vterm_screen_get_cell:         unsafe extern "C" fn(P, VTermPos, P) -> c_int,
    vterm_state_get_cursorpos:     unsafe extern "C" fn(P, *mut VTermPos),
    vterm_output_set_callback:     unsafe extern "C" fn(P, OutputF, P),
    vterm_keyboard_unichar:        unsafe extern "C" fn(P, u32, c_int),
    vterm_keyboard_key:            unsafe extern "C" fn(P, c_int, c_int),
    vterm_screen_set_callbacks:    unsafe extern "C" fn(P, *const ScreenCallbacks, P),
    vterm_screen_set_damage_merge: unsafe extern "C" fn(P, c_int),
    vterm_screen_flush_damage:     unsafe extern "C" fn(P),
    /// ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
    vterm_screen_convert_color_to_rgb: Option<unsafe extern "C" fn(P, P)>,
}

impl Drop for Library {
    fn drop(&mut self) { unsafe { posix::dlclose(self.handle); } }
}

/// WHERE A CELL'S FIELDS STAND in this library's 'VTermScreenCell'.
#[derive(Clone)]
struct Layout {
    mask_db:      [(usize, u8); 7],          // per attribute: (byte offset, bit mask)
    foreground_i: usize,                     // offset of the foreground's red byte
    background_i: usize,
    convert_f:    bool,                      // colours pass 'convert_color_to_rgb' first
    default_fg:   [u8; 3],                   // what an unwritten cell wears
    default_bg:   [u8; 3],
}

thread_local! {
    static LIBRARY: RefCell<Option<Rc<Library>>> = const { RefCell::new(None) };
    //  (layout, done): set, not done, while the defaults are read.
    static LAYOUT:  RefCell<Option<(Layout, bool)>> = const { RefCell::new(None) };
}

/// RETURN: nothing; the library is looked for again at the next screen and
///         its layout measured again -- Python's 'hwut_vterm._library = None'.
pub fn reset_library() {
    LIBRARY.with(|l| *l.borrow_mut() = None);
    LAYOUT.with(|l| *l.borrow_mut() = None);
}

/// RETURN: String, the text of 'dlerror()', '' where it says nothing.
fn dl_error() -> String {
    unsafe {
        let text = posix::dlerror();
        if text.is_null() { String::new() } else { CStr::from_ptr(text).to_string_lossy().into_owned() }
    }
}

/// RETURN: Ok(Rc<Library>), 'libvterm' loaded once and its functions found;
///         Err(VtermError::LibraryMissing) with the install hint where no
///         such library is found.
fn library() -> Result<Rc<Library>, VtermError> {
    if let Some(lib) = LIBRARY.with(|l| l.borrow().clone()) { return Ok(lib); }
    let variable = std::env::var(LIBRARY_VARIABLE).unwrap_or_default();
    let (handle, name) = if !variable.is_empty() {
        let path = CString::new(variable.clone()).unwrap_or_default();
        let handle = unsafe { posix::dlopen(path.as_ptr(), posix::RTLD_NOW) };
        if handle.is_null() {
            return Err(VtermError::LibraryMissing(format!("libvterm cannot be loaded from '{}' -- {}\n{}",
                                                          variable, dl_error(), INSTALL_HINT)));
        }
        (handle, variable)
    } else {
        let found = ["libvterm.so.0", "libvterm.so", "libvterm.0.dylib", "libvterm.dylib"].iter().find_map(|c| {
            let path = CString::new(*c).unwrap();
            let handle = unsafe { posix::dlopen(path.as_ptr(), posix::RTLD_NOW) };
            if handle.is_null() { None } else { Some((handle, c.to_string())) }
        });
        match found {
            Some(found) => found,
            None => return Err(VtermError::LibraryMissing(format!(
                "libvterm is not installed, and '{}' names no file\n{}", LIBRARY_VARIABLE, INSTALL_HINT))),
        }
    };
    let find = |function: &str| -> Result<P, VtermError> {
        let symbol = CString::new(function).unwrap();
        let address = unsafe { posix::dlsym(handle, symbol.as_ptr()) };
        if address.is_null() {
            return Err(VtermError::LibraryMissing(format!("libvterm cannot be loaded from '{}' -- no function '{}'\n{}",
                                                          name, function, INSTALL_HINT)));
        }
        Ok(address)
    };
    macro_rules! found {
        ($f:literal) => { unsafe { std::mem::transmute::<P, _>(match find($f) { Ok(a) => a, Err(e) => {
            posix::dlclose(handle); return Err(e) } }) } };
    }
    let convert = { let symbol = CString::new("vterm_screen_convert_color_to_rgb").unwrap();
                    unsafe { posix::dlsym(handle, symbol.as_ptr()) } };
    let lib = Library {
        handle, name: name.clone(),
        vterm_new: found!("vterm_new"), vterm_free: found!("vterm_free"),
        vterm_set_utf8: found!("vterm_set_utf8"), vterm_input_write: found!("vterm_input_write"),
        vterm_obtain_screen: found!("vterm_obtain_screen"), vterm_obtain_state: found!("vterm_obtain_state"),
        vterm_screen_reset: found!("vterm_screen_reset"),
        vterm_screen_enable_altscreen: found!("vterm_screen_enable_altscreen"),
        vterm_screen_get_cell: found!("vterm_screen_get_cell"),
        vterm_state_get_cursorpos: found!("vterm_state_get_cursorpos"),
        vterm_output_set_callback: found!("vterm_output_set_callback"),
        vterm_keyboard_unichar: found!("vterm_keyboard_unichar"),
        vterm_keyboard_key: found!("vterm_keyboard_key"),
        vterm_screen_set_callbacks: found!("vterm_screen_set_callbacks"),
        vterm_screen_set_damage_merge: found!("vterm_screen_set_damage_merge"),
        vterm_screen_flush_damage: found!("vterm_screen_flush_damage"),
        vterm_screen_convert_color_to_rgb:
            if convert.is_null() { None } else { Some(unsafe { std::mem::transmute::<P, unsafe extern "C" fn(P, P)>(convert) }) },
    };
    let lib = Rc::new(lib);
    LIBRARY.with(|l| *l.borrow_mut() = Some(lib.clone()));
    Ok(lib)
}

/// RETURN: String, 'libvterm found: <name>' where the library loads; the
///         text of 'LibraryMissing' -- what is wrong and how to install it --
///         else.
pub fn detection_text() -> String {
    match library() {
        Ok(lib)    => format!("libvterm found: {}", lib.name),
        Err(error) => error.message().to_string(),
    }
}

/// ONE THING THE TERMINAL DID, as libvterm reports it (the RAW layer).
///
/// kind  'damage'    rows 'row'..'row_end', columns 'column'..'column_end'
///                   changed, ends EXCLUDED
///       'cursor'    the cursor stands at (row, column); 'value' 1 where it
///                   is visible, 0 else
///       'property'  the property 'name' is now 'value' (None where the
///                   value is a text)
///       'bell'      the bell rang
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct Event {
    pub kind:       String,
    pub row:        Option<i32>,
    pub column:     Option<i32>,
    pub row_end:    Option<i32>,
    pub column_end: Option<i32>,
    pub name:       Option<String>,
    pub value:      Option<i64>,
}

impl fmt::Display for Event {
    /// RETURN: fmt::Result; the event on one line, as a test prints it.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let n = |x: Option<i32>| x.unwrap_or(0);
        match self.kind.as_str() {
            "damage" => write!(f, "damage    rows {}..{}  columns {}..{}",
                               n(self.row), n(self.row_end), n(self.column), n(self.column_end)),
            "cursor" => write!(f, "cursor    ({}, {}){}", n(self.row), n(self.column),
                               if self.value.unwrap_or(0) != 0 { "" } else { "  hidden" }),
            "property" => write!(f, "property  {} = {}", self.name.as_deref().unwrap_or(""),
                                 self.value.map_or("None".to_string(), |v| v.to_string())),
            kind => write!(f, "{}", kind),
        }
    }
}

/// ONE CELL OF THE SCREEN, as plain values. 'text' is '' for a cell nothing
/// was written to, and for the right half of a wide character; a colour is
/// (red, green, blue), or None where the cell wears the terminal's default.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Cell {
    pub text:        String,
    pub width:       i32,
    pub bold_f:      bool,
    pub italic_f:    bool,
    pub underline_f: bool,
    pub blink_f:     bool,
    pub reverse_f:   bool,
    pub conceal_f:   bool,
    pub strike_f:    bool,
    pub foreground:  Option<(u8, u8, u8)>,
    pub background:  Option<(u8, u8, u8)>,
}

impl Cell {
    /// RETURN: [bool; 7], the attribute flags in ATTRIBUTE_SGR_DB's order.
    fn flag_list(&self) -> [bool; 7] {
        [self.bold_f, self.italic_f, self.underline_f, self.blink_f, self.reverse_f, self.conceal_f, self.strike_f]
    }

    /// RETURN: String, the attributes that are set, by name and in one fixed
    ///         order, separated by blanks -- 'bold reverse'; '' where none.
    pub fn attribute_text(&self) -> String {
        ATTRIBUTE_SGR_DB.iter().zip(self.flag_list()).filter(|(_, f)| *f).map(|((n, _), _)| *n)
                        .collect::<Vec<_>>().join(" ")
    }
}

/// A TERMINAL OF 'row_n' ROWS AND 'column_n' COLUMNS that draws what it is
/// fed and lets its cells be read.
pub struct Screen {
    pub row_n:    i32,
    pub column_n: i32,
    lib:          Rc<Library>,
    terminal:     P,
    screen:       P,
    state:        P,
}

impl Screen {
    /// RETURN: Ok(Screen), blank, the cursor at (0, 0);
    ///         Err(VtermError::LibraryMissing) where 'libvterm' is not found.
    pub fn new(row_n: i32, column_n: i32) -> Result<Screen, VtermError> {
        let lib = library()?;
        unsafe {
            let terminal = (lib.vterm_new)(row_n, column_n);
            (lib.vterm_set_utf8)(terminal, 1);
            let screen = (lib.vterm_obtain_screen)(terminal);
            let state  = (lib.vterm_obtain_state)(terminal);
            //  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR, and a
            //  full-screen application draws on it.
            (lib.vterm_screen_enable_altscreen)(screen, 1);
            (lib.vterm_screen_reset)(screen, 1);
            Ok(Screen { row_n, column_n, lib, terminal, screen, state })
        }
    }

    /// RETURN: nothing; the terminal's memory is freed -- a second call does
    ///         nothing.
    pub fn close(&mut self) {
        if self.terminal.is_null() { return; }
        unsafe { (self.lib.vterm_free)(self.terminal); }
        self.terminal = std::ptr::null_mut();
        self.screen   = std::ptr::null_mut();
        self.state    = std::ptr::null_mut();
    }

    /// RETURN: usize, the number of bytes the terminal took -- all of them,
    ///         where it works as documented. 'data' is what a program wrote:
    ///         bytes, or a str sent as UTF-8.
    pub fn feed<D: AsRef<[u8]> + ?Sized>(&mut self, data: &D) -> usize {
        let data = data.as_ref();
        unsafe { (self.lib.vterm_input_write)(self.terminal, data.as_ptr() as *const c_char, data.len()) }
    }

    /// RETURN: (i32, i32), the cursor's row and column, from 0.
    pub fn cursor(&self) -> (i32, i32) {
        let mut position = VTermPos::default();
        unsafe { (self.lib.vterm_state_get_cursorpos)(self.state, &mut position); }
        (position.row, position.col)
    }

    /// RETURN: [u8; CELL_BYTE_N], the library's own cell at that place, its
    ///         colours resolved to red, green, blue where the library keeps
    ///         them otherwise (once a layout is measured).
    fn raw(&self, row: i32, column: i32) -> [u8; CELL_BYTE_N] {
        let mut buffer = [0u8; CELL_BYTE_N];
        unsafe {
            (self.lib.vterm_screen_get_cell)(self.screen, VTermPos { row, col: column }, buffer.as_mut_ptr() as P);
        }
        let layout = LAYOUT.with(|l| l.borrow().as_ref().map(|(layout, _)| layout.clone()));
        if let (Some(layout), Some(convert)) = (layout, self.lib.vterm_screen_convert_color_to_rgb) {
            if layout.convert_f {
                //  THE COLOUR'S STRUCTURE begins one byte before its red.
                for start in [layout.foreground_i, layout.background_i] {
                    unsafe { convert(self.screen, buffer.as_mut_ptr().add(start - 1) as P); }
                }
            }
        }
        buffer
    }

    /// RETURN: Ok(Cell), what stands at that place;
    ///         Err(VtermError::IndexError) where the place is not on the screen.
    pub fn cell(&self, row: i32, column: i32) -> Result<Cell, VtermError> {
        if !(0 <= row && row < self.row_n && 0 <= column && column < self.column_n) {
            return Err(VtermError::IndexError(format!("({}, {}) is not on a screen of {} x {}",
                                                      row, column, self.row_n, self.column_n)));
        }
        let layout = measured();
        let raw = self.raw(row, column);
        let text: String = (0..CHARS_BYTE_N).step_by(4)
            .map(|i| u32::from_le_bytes([raw[i], raw[i + 1], raw[i + 2], raw[i + 3]]))
            .filter(|code| *code != 0 && *code != 0xFFFF_FFFF)
            .filter_map(char::from_u32).collect();
        let colour = |i: usize, default: [u8; 3]| -> Option<(u8, u8, u8)> {
            if raw[i..i + 3] == default { None } else { Some((raw[i], raw[i + 1], raw[i + 2])) }
        };
        let flag = |a: usize| raw[layout.mask_db[a].0] & layout.mask_db[a].1 != 0;
        Ok(Cell {
            text,
            width: if raw[CHARS_BYTE_N] != 0 { raw[CHARS_BYTE_N] as i32 } else { 1 },
            bold_f: flag(0), italic_f: flag(1), underline_f: flag(2), blink_f: flag(3),
            reverse_f: flag(4), conceal_f: flag(5), strike_f: flag(6),
            foreground: colour(layout.foreground_i, layout.default_fg),
            background: colour(layout.background_i, layout.default_bg),
        })
    }

    /// RETURN: String, the characters of 'column_n' columns from 'column' of
    ///         'row', blanks at the end dropped; an unwritten cell reads a
    ///         blank, a wide character steps over its right half.
    fn row_text(&self, row: i32, column: i32, column_n: i32) -> String {
        let mut text = String::new();
        let mut at = column;
        while at < column + column_n {
            let cell = match self.cell(row, at) { Ok(cell) => cell, Err(_) => break };
            text.push_str(if cell.text.is_empty() { " " } else { &cell.text });
            at += cell.width.max(1);
        }
        text.trim_end().to_string()
    }

    /// RETURN: String, the row's characters, blanks at its end dropped; a
    ///         cell nothing was written to reads as a blank.
    pub fn line(&self, row: i32) -> String { self.row_text(row, 0, self.column_n) }

    /// RETURN: Vec<String>, every row as 'line()' gives it, top first.
    pub fn line_list(&self) -> Vec<String> { (0..self.row_n).map(|row| self.line(row)).collect() }
}

impl Drop for Screen {
    fn drop(&mut self) { self.close(); }
}

/// RETURN: Layout, where this library's cell keeps each attribute and each
///         colour -- measured once on scratch terminals, then remembered.
fn measured() -> Layout {
    if let Some((layout, true)) = LAYOUT.with(|l| l.borrow().clone()) { return layout; }
    let cell_after = |sequence: &str| -> [u8; CELL_BYTE_N] {
        let mut scratch = Screen::new(2, 4).expect("libvterm loaded before it is measured");
        if !sequence.is_empty() { scratch.feed(&format!("\x1b[{}m", sequence)); }
        scratch.feed("X");
        scratch.raw(0, 0)
    };
    let plain = cell_after("");
    let changed = |raw: &[u8; CELL_BYTE_N]| -> Vec<(usize, u8)> {
        (CHARS_BYTE_N + 1..CELL_BYTE_N).filter(|i| plain[*i] != raw[*i]).map(|i| (i, plain[i] ^ raw[i])).collect()
    };
    let mut mask_db = [(CHARS_BYTE_N + 1, 0u8); 7];
    for (a, (_, code)) in ATTRIBUTE_SGR_DB.iter().enumerate() {
        //  NOTHING MOVED: this library does not know the attribute.
        if let Some(first) = changed(&cell_after(code)).first() { mask_db[a] = *first; }
    }
    //  UNDERLINE IS A NUMBER OF TWO BITS: the double's bit joins the mask.
    for (offset, bits) in changed(&cell_after("21")) {
        if offset == mask_db[2].0 { mask_db[2].1 |= bits; }
    }
    let colour_at = |code: &str| -> usize {
        let raw = cell_after(&format!("{};2;1;2;3", code));
        (CHARS_BYTE_N + 1..CELL_BYTE_N - 2).find(|i| raw[*i..*i + 3] == [1, 2, 3]).unwrap_or(CHARS_BYTE_N + 1)
    };
    let foreground_i = colour_at("38");
    let background_i = colour_at("48");
    let convert_f = library().map(|l| l.vterm_screen_convert_color_to_rgb.is_some()).unwrap_or(false);
    let mut layout = Layout { mask_db, foreground_i, background_i, convert_f, default_fg: [0; 3], default_bg: [0; 3] };
    //  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell is read.
    LAYOUT.with(|l| *l.borrow_mut() = Some((layout.clone(), false)));
    let raw = cell_after("");
    layout.default_fg.copy_from_slice(&raw[foreground_i..foreground_i + 3]);
    layout.default_bg.copy_from_slice(&raw[background_i..background_i + 3]);
    LAYOUT.with(|l| *l.borrow_mut() = Some((layout.clone(), true)));
    layout
}

// --------------------------------------------------------------- Terminal
/// What libvterm's callbacks reach: kept apart from the Terminal, at a fixed
/// address, since the library calls back while the Terminal is borrowed.
struct Observers {
    event_f_list: Vec<Box<dyn FnMut(&Event)>>,
    answer:       Vec<u8>,
}

/// RETURN: 1, libvterm's 'handled'; the event reached every raw callback.
fn emit(user: *mut c_void, event: Event) -> c_int {
    let observers = unsafe { &mut *(user as *mut Observers) };
    for callback in observers.event_f_list.iter_mut() { callback(&event); }
    1
}

extern "C" fn on_damage(r: VTermRect, user: *mut c_void) -> c_int {
    emit(user, Event { kind: "damage".into(), row: Some(r.start_row), column: Some(r.start_col),
                       row_end: Some(r.end_row), column_end: Some(r.end_col), ..Event::default() })
}

extern "C" fn on_cursor(p: VTermPos, _old: VTermPos, visible: c_int, user: *mut c_void) -> c_int {
    emit(user, Event { kind: "cursor".into(), row: Some(p.row), column: Some(p.col),
                       value: Some((visible != 0) as i64), ..Event::default() })
}

extern "C" fn on_property(number: c_int, value: *mut c_int, user: *mut c_void) -> c_int {
    let (name, plain_f) = match PROPERTY_DB.iter().find(|(n, _, _)| *n == number) {
        Some((_, name, plain_f)) => (name.to_string(), *plain_f),
        None                     => (format!("property-{}", number), false),
    };
    let value = if plain_f && !value.is_null() { Some(unsafe { *value } as i64) } else { None };
    emit(user, Event { kind: "property".into(), name: Some(name), value, ..Event::default() })
}

extern "C" fn on_bell(user: *mut c_void) -> c_int {
    emit(user, Event { kind: "bell".into(), ..Event::default() })
}

/// What the TERMINAL says -- a key's sequence, an answer -- is collected for
/// the application.
extern "C" fn on_output(data: *const c_char, length: usize, user: *mut c_void) {
    let observers = unsafe { &mut *(user as *mut Observers) };
    if length > 0 && !data.is_null() {
        observers.answer.extend_from_slice(unsafe { std::slice::from_raw_parts(data as *const u8, length) });
    }
}

/// A rectangle observed by name: (row, row_n, column, column_n).
type Region = (i32, i32, i32, i32);

/// A TERMINAL AN APPLICATION RUNS IN, OBSERVED BY CLOSURES (see the head of
/// this file). It is a 'Screen' ('Deref').
///
///     let mut terminal = Terminal::new(24, 80, 0.1)?;
///     terminal.region("foot", -1, 1, 0, None);
///     terminal.on_change(|name, line_list| println!("{} {:?}", name, line_list));
///     terminal.run(&["my-app"], None, None, 10.0)?;
///     terminal.press("down", &[], 1.0)?;
///     terminal.send("q", 1.0);
///     println!("{:?}", terminal.wait(10.0)?);
pub struct Terminal {
    //  THE SCREEN FIRST: dropped first, so libvterm is gone before what its
    //  callbacks reach.
    screen:        Screen,
    pub settle_s:  f64,
    observers:     Box<Observers>,
    callbacks:     Box<ScreenCallbacks>,
    change_f_list: Vec<Box<dyn FnMut(&str, &[String])>>,
    region_db:     Vec<(String, Region)>,         // in the order of declaration
    told_db:       HashMap<String, Vec<String>>,
    master:        c_int,
    process:       posix::pid_t,
    reaped_f:      bool,
    status:        i32,
    ended_f:       bool,
}

impl std::ops::Deref for Terminal {
    type Target = Screen;
    fn deref(&self) -> &Screen { &self.screen }
}

impl std::ops::DerefMut for Terminal {
    fn deref_mut(&mut self) -> &mut Screen { &mut self.screen }
}

/// RETURN: f64 seconds as the milliseconds 'poll' waits, rounded up.
fn milliseconds(seconds: f64) -> c_int { (seconds * 1000.0).ceil().max(0.0) as c_int }

impl Terminal {
    /// RETURN: Ok(Terminal), blank, nothing running in it;
    ///         Err(VtermError::LibraryMissing) where 'libvterm' is not found.
    ///
    /// 'settle_s' is how long the application must write nothing before its
    /// screen is taken as drawn (Python's default: 0.1).
    pub fn new(row_n: i32, column_n: i32, settle_s: f64) -> Result<Terminal, VtermError> {
        let screen = Screen::new(row_n, column_n)?;
        let mut observers = Box::new(Observers { event_f_list: Vec::new(), answer: Vec::new() });
        let callbacks = Box::new(ScreenCallbacks {
            damage: Some(on_damage), moverect: None, movecursor: Some(on_cursor),
            settermprop: Some(on_property), bell: Some(on_bell),
            resize: std::ptr::null_mut(), sb_pushline: std::ptr::null_mut(), sb_popline: std::ptr::null_mut(),
            spare: [std::ptr::null_mut(); 8],
        });
        let user = &mut *observers as *mut Observers as P;
        unsafe {
            (screen.lib.vterm_output_set_callback)(screen.terminal, on_output, user);
            (screen.lib.vterm_screen_set_callbacks)(screen.screen, &*callbacks, user);
            (screen.lib.vterm_screen_set_damage_merge)(screen.screen, DAMAGE_MERGE_ROW);
        }
        Ok(Terminal { screen, settle_s, observers, callbacks, change_f_list: Vec::new(), region_db: Vec::new(),
                      told_db: HashMap::new(), master: -1, process: 0, reaped_f: false, status: 0, ended_f: false })
    }

    // -------------------------------------------------------- observation
    /// RETURN: nothing; 'callback(event)' is called with every raw 'Event'
    ///         from now on.
    pub fn on_event<F: FnMut(&Event) + 'static>(&mut self, callback: F) {
        self.observers.event_f_list.push(Box::new(callback));
    }

    /// RETURN: nothing; 'callback(name, line_list)' is called for every
    ///         region whose text changed, once the screen is quiet.
    pub fn on_change<F: FnMut(&str, &[String]) + 'static>(&mut self, callback: F) {
        self.change_f_list.push(Box::new(callback));
    }

    /// RETURN: nothing; the rectangle 'name' is observed from now on:
    ///         'row_n' rows from 'row', 'column_n' columns from 'column' (to
    ///         the right edge where None). A NEGATIVE 'row' counts from the
    ///         bottom: -1 is the last row. What stands there now is known,
    ///         not news: only a change is told.
    pub fn region(&mut self, name: &str, row: i32, row_n: i32, column: i32, column_n: Option<i32>) {
        let row = if row < 0 { row + self.screen.row_n } else { row };
        let column_n = column_n.unwrap_or(self.screen.column_n - column);
        match self.region_db.iter_mut().find(|(n, _)| n == name) {
            Some(entry) => entry.1 = (row, row_n, column, column_n),
            None        => self.region_db.push((name.to_string(), (row, row_n, column, column_n))),
        }
        let text = self.region_text(name).unwrap_or_default();
        self.told_db.insert(name.to_string(), text);
    }

    /// RETURN: Ok(Vec<String>), the region's rows as they stand now, blanks
    ///         at each row's end dropped;
    ///         Err(VtermError::KeyError) where no such region was declared.
    pub fn region_text(&self, name: &str) -> Result<Vec<String>, VtermError> {
        let (_, (row, row_n, column, column_n)) = self.region_db.iter().find(|(n, _)| n == name)
            .ok_or_else(|| VtermError::KeyError(format!("'{}'", name)))?;
        Ok((*row..row + row_n).map(|r| self.screen.row_text(r, *column, *column_n)).collect())
    }

    /// RETURN: Vec<String>, the names of the regions whose text differs from
    ///         what was last told -- each told to every 'on_change' callback,
    ///         in the order of declaration.
    pub fn report(&mut self) -> Vec<String> {
        let mut changed_list = Vec::new();
        let name_list: Vec<String> = self.region_db.iter().map(|(n, _)| n.clone()).collect();
        for name in name_list {
            let line_list = self.region_text(&name).unwrap_or_default();
            if self.told_db.get(&name) == Some(&line_list) { continue; }
            self.told_db.insert(name.clone(), line_list.clone());
            for callback in self.change_f_list.iter_mut() { callback(&name, &line_list); }
            changed_list.push(name);
        }
        changed_list
    }

    // ---------------------------------------------------- bytes in and out
    /// RETURN: usize, the number of bytes the terminal took. The raw events
    ///         of what was fed fired before this returns; what the terminal
    ///         answered went to the application, where one runs.
    pub fn feed<D: AsRef<[u8]> + ?Sized>(&mut self, data: &D) -> usize {
        let taken_n = self.screen.feed(data);
        unsafe { (self.screen.lib.vterm_screen_flush_damage)(self.screen.screen); }
        self.forward();
        taken_n
    }

    /// RETURN: Vec<u8>, what the terminal said since the last call and no
    ///         application took -- the reply to a question fed by hand, the
    ///         sequence of a key pressed with nothing running.
    pub fn answer(&mut self) -> Vec<u8> { std::mem::take(&mut self.observers.answer) }

    /// RETURN: nothing; the terminal's words reach the application, if one
    ///         runs; they wait in 'answer()' otherwise.
    fn forward(&mut self) {
        if self.master < 0 || self.observers.answer.is_empty() { return; }
        let data = std::mem::take(&mut self.observers.answer);
        let mut done = 0;
        while done < data.len() {
            let n = unsafe { posix::write(self.master, data[done..].as_ptr() as *const c_void, data.len() - done) };
            if n < 0 {
                if posix::errno() == posix::EINTR { continue; }
                self.ended_f = true;
                break;
            }
            done += n as usize;
        }
    }

    /// RETURN: bool, true where the application still runs after 'text' was
    ///         typed, character by character, as a keyboard sends it, and
    ///         the screen was read until quiet ('react_s' to begin answering).
    pub fn send(&mut self, text: &str, react_s: f64) -> bool {
        for c in text.chars() {
            unsafe { (self.screen.lib.vterm_keyboard_unichar)(self.screen.terminal, c as u32, 0); }
        }
        self.forward();
        self.pump(react_s)
    }

    /// RETURN: Ok(bool), true where the application still runs after 'key'
    ///         was pressed with the modifiers ('shift', 'alt', 'ctrl') --
    ///         'press("c", &["ctrl"], 1.0)' is Ctrl-C;
    ///         Err(VtermError::KeyError) where 'key' or a modifier has no
    ///         name here. 'key' is 'enter', 'up', 'f5', ... or one character.
    pub fn press(&mut self, key: &str, modifier_list: &[&str], react_s: f64) -> Result<bool, VtermError> {
        let mut modifier = 0;
        for name in modifier_list {
            modifier |= modifier_of(name).ok_or_else(|| VtermError::KeyError(format!("'{}'", name)))?;
        }
        let mut chars = key.chars();
        match (chars.next(), chars.next()) {
            (Some(c), None) => unsafe {
                (self.screen.lib.vterm_keyboard_unichar)(self.screen.terminal, c as u32, modifier);
            },
            _ => {
                let code = key_of(key).ok_or_else(|| VtermError::KeyError(format!("'{}'", key)))?;
                unsafe { (self.screen.lib.vterm_keyboard_key)(self.screen.terminal, code, modifier); }
            }
        }
        self.forward();
        Ok(self.pump(react_s))
    }

    // ---------------------------------------------------- the application
    /// RETURN: Ok(bool), true where the application 'argv' still runs once
    ///         its first screen stands;
    ///         Err(VtermError::RuntimeError) where one already runs here,
    ///         Err(VtermError::OSError) where no pseudo-terminal is had.
    ///
    /// It is started on a pseudo-terminal of this terminal's size: stdin,
    /// stdout and stderr are that terminal, and it is the controlling one.
    /// 'env' is its environment (this process's where None); TERM is
    /// 'xterm-256color'; LINES and COLUMNS are taken OUT, since they would
    /// overrule the size the terminal answers.
    pub fn run(&mut self, argv: &[&str], env: Option<&[(String, String)]>, cwd: Option<&str>,
               start_s: f64) -> Result<bool, VtermError> {
        if self.process != 0 {
            return Err(VtermError::RuntimeError("an application already runs in this terminal".to_string()));
        }
        let mut environment: Vec<(String, String)> = match env {
            Some(env) => env.to_vec(),
            None      => std::env::vars_os().map(|(k, v)| (k.to_string_lossy().into_owned(),
                                                          v.to_string_lossy().into_owned())).collect(),
        };
        environment.retain(|(k, _)| k != "TERM" && k != "LINES" && k != "COLUMNS");
        environment.push(("TERM".to_string(), "xterm-256color".to_string()));
        let argv_c: Vec<CString> = argv.iter().map(|a| CString::new(*a).unwrap_or_default()).collect();
        let envp_c: Vec<CString> = environment.iter()
            .filter_map(|(k, v)| CString::new(format!("{}={}", k, v)).ok()).collect();
        let mut argv_p: Vec<*const c_char> = argv_c.iter().map(|a| a.as_ptr()).collect();
        argv_p.push(std::ptr::null());
        let mut envp_p: Vec<*const c_char> = envp_c.iter().map(|e| e.as_ptr()).collect();
        envp_p.push(std::ptr::null());
        let cwd_c = cwd.map(|c| CString::new(c).unwrap_or_default());

        let (mut master, mut slave) = (-1, -1);
        let size = posix::winsize { ws_row: self.screen.row_n as u16, ws_col: self.screen.column_n as u16,
                                    ws_xpixel: 0, ws_ypixel: 0 };
        if unsafe { posix::openpty(&mut master, &mut slave, std::ptr::null_mut(), std::ptr::null(), &size) } != 0 {
            let why = unsafe { CStr::from_ptr(posix::strerror(posix::errno())) }.to_string_lossy().into_owned();
            return Err(VtermError::OSError(format!("openpty: {}", why)));
        }
        unsafe { posix::ioctl(slave, posix::TIOCSWINSZ, &size as *const posix::winsize); }
        use std::io::Write;
        let _ = std::io::stdout().flush();
        let _ = std::io::stderr().flush();
        let pid = unsafe { posix::fork() };
        if pid == 0 {
            //  THE CHILD: it leads its own session, the pseudo-terminal is its
            //  controlling terminal and its three streams. Only C from here.
            unsafe {
                posix::setsid();
                posix::dup2(slave, 0); posix::dup2(slave, 1); posix::dup2(slave, 2);
                posix::ioctl(0, posix::TIOCSCTTY, 0 as c_int);
                for fd in 3..1024 { posix::close(fd); }
                //  RUST IGNORES SIGPIPE, and an ignored signal is inherited.
                posix::signal(posix::SIGPIPE, posix::SIG_DFL);
                if let Some(cwd) = &cwd_c { if posix::chdir(cwd.as_ptr()) != 0 { posix::_exit(127); } }
                posix::execvpe(argv_p[0], argv_p.as_ptr(), envp_p.as_ptr());
                posix::_exit(127);
            }
        }
        unsafe { posix::close(slave); }
        if pid < 0 {
            unsafe { posix::close(master); }
            return Err(VtermError::OSError("fork failed".to_string()));
        }
        self.master   = master;
        self.process  = pid;
        self.reaped_f = false;
        self.ended_f  = false;
        Ok(self.pump(start_s))
    }

    /// RETURN: bool, true where the application still runs; false where it
    ///         ended (reaped, its status kept) or never ran.
    fn poll(&mut self) -> bool {
        if self.process == 0 || self.reaped_f { return false; }
        let mut status = 0;
        if unsafe { posix::waitpid(self.process, &mut status, posix::WNOHANG) } != self.process { return true; }
        self.reaped_f = true;
        self.status   = posix::exit_code_of(status);
        false
    }

    /// RETURN: nothing; the application is killed and reaped.
    fn kill(&mut self) {
        let mut status = 0;
        unsafe {
            posix::kill(self.process, posix::SIGKILL);
            posix::waitpid(self.process, &mut status, 0);
        }
        self.reaped_f = true;
        self.status   = posix::exit_code_of(status);
    }

    /// RETURN: bool, true where the application still runs.
    ///
    /// READ UNTIL QUIET: wait up to 'first_s' for the application to write
    /// at all, then go on reading until it has written nothing for
    /// 'settle_s'. Then the changed regions are reported.
    pub fn pump(&mut self, first_s: f64) -> bool {
        let mut data = vec![0u8; 65536];
        let mut wait_s = first_s;
        while self.master >= 0 && !self.ended_f {
            let mut ready = posix::pollfd { fd: self.master, events: posix::POLLIN, revents: 0 };
            let r = unsafe { posix::poll(&mut ready, 1, milliseconds(wait_s)) };
            if r < 0 && posix::errno() == posix::EINTR { continue; }
            if r <= 0 { break; }
            let n = unsafe { posix::read(self.master, data.as_mut_ptr() as *mut c_void, data.len()) };
            if n < 0 && posix::errno() == posix::EINTR { continue; }
            if n <= 0 { self.ended_f = true; break; }          // the last writer closed: it ended
            self.feed(&data[..n as usize]);
            wait_s = self.settle_s;
        }
        self.report();
        self.poll() && !self.ended_f
    }

    /// RETURN: Ok((row, column)) where 'text' stands on the screen, once it
    ///         does (the column counted in characters);
    ///         Err(VtermError::TimeoutError), carrying the screen, where it
    ///         does not within 'timeout_s'.
    pub fn expect(&mut self, text: &str, timeout_s: f64) -> Result<(usize, usize), VtermError> {
        let deadline = Instant::now() + Duration::from_secs_f64(timeout_s.max(0.0));
        loop {
            for (row, line) in self.screen.line_list().iter().enumerate() {
                if let Some(at) = line.find(text) { return Ok((row, line[..at].chars().count())); }
            }
            if Instant::now() >= deadline || self.ended_f || self.master < 0 {
                return Err(VtermError::TimeoutError(format!("'{}' did not appear; the screen:\n{}",
                                                            text, self.screen.line_list().join("\n"))));
            }
            let settle_s = self.settle_s;
            self.pump(settle_s);
        }
    }

    /// RETURN: Ok(Some(status)), the application's exit status (negative: the
    ///         signal that ended it), once it has ended and its last words
    ///         are on the screen; Ok(None) where no application was run;
    ///         Err(VtermError::TimeoutError) where it still runs after
    ///         'timeout_s' -- it is killed first.
    pub fn wait(&mut self, timeout_s: f64) -> Result<Option<i32>, VtermError> {
        if self.process == 0 { return Ok(None); }
        let deadline = Instant::now() + Duration::from_secs_f64(timeout_s.max(0.0));
        let settle_s = self.settle_s;
        while self.pump(settle_s) {
            if Instant::now() >= deadline {
                self.kill();
                return Err(VtermError::TimeoutError(format!("the application still ran after {:.1} s", timeout_s)));
            }
        }
        let rest = deadline.saturating_duration_since(Instant::now()).max(Duration::from_millis(100));
        let until = Instant::now() + rest;
        while self.poll() {
            if Instant::now() >= until {
                self.kill();
                return Err(VtermError::TimeoutError("the application closed its terminal and did not end".to_string()));
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        Ok(Some(self.status))
    }

    /// RETURN: nothing; an application still running is killed, the
    ///         pseudo-terminal closed, the terminal's memory freed.
    pub fn close(&mut self) {
        if self.poll() { self.kill(); }
        if self.master >= 0 { unsafe { posix::close(self.master); } self.master = -1; }
        self.screen.close();
    }
}

impl Drop for Terminal {
    fn drop(&mut self) {
        self.close();
        let _ = &self.callbacks;                    // lives as long as the terminal
    }
}

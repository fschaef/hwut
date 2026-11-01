// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// A TERMINAL FILE VIEWER -- the program 'screen.rs' tests; no test itself.
//
//     viewer.exe <file>
//
// Full screen, on the terminal's alternate screen: a title bar (reverse
// video), as many lines of the file as fit, and a status line: the keys
// flush left, the lines shown flush right. Keys: 'j' or down one line
// further, 'k' or up one line back, 'q' quits. Built by 'make helpers'
// ('on_entry' in hwut.conf). The terminal is put into raw mode by termios,
// declared here by hand (Linux, glibc): Rust's standard library has none.
//______________________________________________________________________________
use std::io::Write;

const TCSADRAIN: i32   = 1;
const TIOCGWINSZ: u64  = 0x5413;

#[repr(C)]
struct Winsize { ws_row: u16, ws_col: u16, ws_xpixel: u16, ws_ypixel: u16 }

extern "C" {
    fn tcgetattr(fd: i32, termios: *mut u8) -> i32;
    fn tcsetattr(fd: i32, action: i32, termios: *const u8) -> i32;
    fn cfmakeraw(termios: *mut u8);
    fn ioctl(fd: i32, request: u64, ...) -> i32;
    fn read(fd: i32, buffer: *mut u8, n: usize) -> isize;
}

/// RETURN: (usize, usize), the terminal's (column_n, row_n); (80, 24) where
///         stdout is no terminal.
fn terminal_size() -> (usize, usize) {
    let mut size = Winsize { ws_row: 0, ws_col: 0, ws_xpixel: 0, ws_ypixel: 0 };
    if unsafe { ioctl(1, TIOCGWINSZ, &mut size as *mut Winsize) } != 0 || size.ws_col == 0 { return (80, 24); }
    (size.ws_col as usize, size.ws_row as usize)
}

/// RETURN: String, 'text' cut or padded with blanks to exactly 'width'
///         characters.
fn fit(text: &str, width: usize) -> String {
    let cut: String = text.chars().take(width).collect();
    format!("{:<width$}", cut, width = width)
}

/// RETURN: String, the whole screen with the file's line 'top' first.
fn draw(name: &str, line_list: &[String], top: usize, row_n: usize, column_n: usize) -> String {
    let body_n = row_n - 2;
    let shown = &line_list[top..(top + body_n).min(line_list.len())];
    let mut out = String::from("\x1b[H\x1b[2J");
    out += &format!("\x1b[7m{}\x1b[0m\r\n", fit(&format!(" {}", name), column_n));
    for line in shown { out += &format!("{}\r\n", line.chars().take(column_n).collect::<String>()); }
    out += &"\r\n".repeat(body_n - shown.len());
    let place = format!("lines {}-{} of {}", top + 1, top + shown.len(), line_list.len());
    let keys = "j k q";
    out += &format!("\x1b[{};1H{}{:>w$}", row_n, keys, place, w = column_n - 1 - keys.len());
    out
}

/// RETURN: i32, 0 once 'q' was pressed; 1 where the file cannot be read.
fn main_of(path: &str) -> i32 {
    let Ok(text) = std::fs::read_to_string(path) else { eprintln!("viewer: cannot read {}", path); return 1; };
    let line_list: Vec<String> = text.lines().map(str::to_string).collect();
    let name = std::path::Path::new(path).file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let (column_n, row_n) = terminal_size();
    let mut saved = [0u8; 256];                     // 'struct termios': 60 bytes on glibc
    let mut raw = [0u8; 256];
    unsafe {
        tcgetattr(0, saved.as_mut_ptr());
        raw.copy_from_slice(&saved);
        cfmakeraw(raw.as_mut_ptr());
        tcsetattr(0, TCSADRAIN, raw.as_ptr());
    }
    let mut out = std::io::stdout().lock();
    let _ = out.write_all(b"\x1b[?1049h");
    let mut top = 0;
    loop {
        let _ = out.write_all(draw(&name, &line_list, top, row_n, column_n).as_bytes());
        let _ = out.flush();
        let mut key = [0u8; 8];
        let n = unsafe { read(0, key.as_mut_ptr(), key.len()) };
        if n <= 0 { break; }
        match &key[..n as usize] {
            b"q"                => break,
            b"j" | b"\x1b[B"    => top = (top + 1).min(line_list.len().saturating_sub(row_n - 2)),
            b"k" | b"\x1b[A"    => top = top.saturating_sub(1),
            _                   => {}
        }
    }
    let _ = out.write_all(b"\x1b[?1049l");
    let _ = out.flush();
    unsafe { tcsetattr(0, TCSADRAIN, saved.as_ptr()); }
    0
}

/// RETURN: never; exits with what 'main_of' returned.
fn main() {
    let Some(path) = std::env::args().nth(1) else { eprintln!("usage: viewer.exe <file>"); std::process::exit(2); };
    std::process::exit(main_of(&path));
}

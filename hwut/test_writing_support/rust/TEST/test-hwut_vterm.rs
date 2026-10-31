// @hwut {
//     title      = "A terminal's screen read by a test: libvterm through dlopen."
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         attributes { features = ["rust-vterm"] }
//         colours    { features = ["rust-vterm"] }
//         events     { features = ["rust-vterm"] }
//         keys       { features = ["rust-vterm"] }
//         missing    { features = ["rust-vterm"] }
//         regions    { features = ["rust-vterm"] }
//         screen     { features = ["rust-vterm"] }
//         text       { features = ["rust-vterm"] }
//         unnoticed  { features = ["rust-vterm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-hwut_vterm.py', choice for
//          choice, held against its GOOD files by '.link'. WANTS libvterm --
//          found at run time, no header needed to build. The two
//          APPLICATIONS a Terminal runs here are the Python test's,
//          unchanged, run by 'python3': they are the system under test, and
//          what they print is in the shared GOOD files.
//______________________________________________________________________________
use std::cell::RefCell;
use std::rc::Rc;

use hwut::hwut_pytext::{bool_text, str_repr, PyBytes, PyRepr};
use hwut::hwut_runner::HwutRunner;
use hwut::hwut_vterm::{self, Screen, Terminal, VtermError, ATTRIBUTE_SGR_DB};

const ESC: &str = "\x1b";

/// Every row that holds something, framed, then the cursor.
fn shown(screen: &Screen) {
    for (row, line) in screen.line_list().iter().enumerate() {
        if !line.is_empty() { println!("    {} |{}|", row, line); }
    }
    let (row, column) = screen.cursor();
    println!("    cursor ({}, {})", row, column);
}

/// RETURN: nothing; 'function' ran on a library that is there; one line was
///         said where it is not.
fn probe(function: fn() -> Result<(), VtermError>) {
    if let Err(error) = function() { println!("NOT PROBED: {}", error); }
}

fn run_text() -> Result<(), VtermError> {
    {
        let mut screen = Screen::new(4, 12)?;
        println!("-- plain, then carriage return and line feed");
        screen.feed(b"hello\r\nworld");
        shown(&screen);
    }
    {
        let mut screen = Screen::new(4, 12)?;
        println!("-- UTF-8: two bytes, one cell; a wide character, two");
        screen.feed("ä日x");
        shown(&screen);
        for column in 0..4 {
            let cell = screen.cell(0, column)?;
            println!("    column {}: {:<6} width {}", column, str_repr(&cell.text), cell.width);
        }
    }
    {
        let mut screen = Screen::new(3, 5)?;
        println!("-- seven characters on five columns: the line wraps");
        screen.feed(b"abcdefg");
        shown(&screen);
    }
    let mut screen = Screen::new(2, 4)?;
    println!("-- a str is sent as UTF-8; the bytes taken are counted");
    println!("    taken: {}", screen.feed("aä"));
    println!("-- a place off the screen");
    if let Err(error) = screen.cell(2, 0) { println!("    {}: {}", error.kind(), error); }
    Ok(())
}

fn run_screen() -> Result<(), VtermError> {
    let mut screen = Screen::new(5, 20)?;
    println!("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'");
    screen.feed(b"first line\r\nsecond line\r\nthird line");
    screen.feed(&format!("{}[2;4HX", ESC));
    shown(&screen);
    println!("-- erase to the end of that line");
    screen.feed(&format!("{}[K", ESC));
    shown(&screen);
    println!("-- clear the screen, home, one word");
    screen.feed(&format!("{}[2J{}[Hclean", ESC, ESC));
    shown(&screen);
    Ok(())
}

fn run_attributes() -> Result<(), VtermError> {
    let mut screen = Screen::new(3, 20)?;
    for (name, code) in ATTRIBUTE_SGR_DB {
        screen.feed(&format!("{}[{}m{}{}[0m", ESC, code, &name[..1], ESC));
    }
    println!("-- one cell per attribute, set by its own code");
    for (column, (name, _)) in ATTRIBUTE_SGR_DB.iter().enumerate() {
        let cell = screen.cell(0, column as i32)?;
        //  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
        let mut said = cell.attribute_text();
        if said.is_empty() { said = "(none)".to_string(); }
        if *name == "conceal" { said = "conceal, or (none) on libvterm 0.1".to_string(); }
        println!("    {}  {}", str_repr(&cell.text), said);
    }
    println!("-- bold, underline and reverse at once; then reset");
    screen.feed(&format!("\r\n{}[1;4;7mA{}[0mB", ESC, ESC));
    for column in [0, 1] {
        let cell = screen.cell(1, column)?;
        let said = cell.attribute_text();
        println!("    {}  {}", str_repr(&cell.text), if said.is_empty() { "(none)" } else { &said });
    }
    println!("-- double underline (SGR 21) is underlined");
    screen.feed(&format!("{}[21mD", ESC));
    println!("    {}  {}", str_repr("D"), screen.cell(1, 2)?.attribute_text());
    Ok(())
}

fn run_colours() -> Result<(), VtermError> {
    let mut screen = Screen::new(2, 20)?;
    screen.feed(&format!("d{e}[31mr{e}[0m{e}[38;5;196mp{e}[0m{e}[38;2;10;20;30mt{e}[0m", e = ESC));
    screen.feed(&format!("{}[48;2;1;2;3mb{}[0m", ESC, ESC));
    for (column, what) in ["default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3"]
                          .iter().enumerate() {
        let cell = screen.cell(0, column as i32)?;
        //  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: mostly red
        //  is the claim, not its shade.
        let said = if *what == "indexed 31" {
            let (red, green, blue) = cell.foreground.unwrap_or((0, 0, 0));
            format!("fg mostly red: {}", bool_text(red as u32 > 2 * green.max(blue) as u32))
        } else {
            format!("fg {}  bg {}", cell.foreground.py_repr(), cell.background.py_repr())
        };
        println!("    {:<18} {}  {}", what, str_repr(&cell.text), said);
    }
    Ok(())
}

//  THE APPLICATION UNDER OBSERVATION -- the Python test's own, word for word:
//  it says what it sees, asks the terminal where the cursor is, then names
//  every key until 'q'.
const SEEING_APP: &str = r#"
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
"#;

//  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
//  'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
const DRAWING_APP: &str = r#"
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
"#;

fn run_unnoticed() -> Result<(), VtermError> {
    std::env::set_var("COLUMNS", "300");
    let mut terminal = Terminal::new(10, 44, 0.1)?;
    let running = terminal.run(&["python3", "-c", SEEING_APP], None, None, 10.0)?;
    println!("-- still running after its first screen: {}", bool_text(running));
    shown(&terminal);
    terminal.send("q", 1.0);
    println!("-- after 'q': exit status {}", terminal.wait(10.0)?.py_repr());
    shown(&terminal);
    Ok(())
}

fn run_keys() -> Result<(), VtermError> {
    let mut terminal = Terminal::new(10, 44, 0.1)?;
    terminal.region("read", 8, 1, 0, None);
    let pressed = Rc::new(RefCell::new(String::from("(start)")));
    let said = pressed.clone();
    terminal.on_change(move |_name, line_list| println!("    {:<22} {}", said.borrow(), line_list[0]));
    terminal.run(&["python3", "-c", SEEING_APP], None, None, 10.0)?;
    for (key, modifier_list) in [("up", &[][..]), ("enter", &[]), ("tab", &[]), ("escape", &[]), ("f5", &[]),
                                 ("delete", &[]), ("c", &["ctrl"]), ("x", &["alt"]), ("up", &["shift"])] {
        let mut word: Vec<&str> = modifier_list.to_vec();
        word.push(key);
        *pressed.borrow_mut() = word.join(" ");
        terminal.press(key, modifier_list, 1.0)?;
    }
    *pressed.borrow_mut() = "send 'ä'".to_string();
    terminal.send("ä", 1.0);
    *pressed.borrow_mut() = "send 'q'".to_string();
    terminal.send("q", 1.0);
    terminal.wait(10.0)?;
    Ok(())
}

fn run_regions() -> Result<(), VtermError> {
    //  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    //  ONE report on a loaded machine too.
    let mut terminal = Terminal::new(8, 30, 0.3)?;
    terminal.region("head", 0, 1, 0, None);
    terminal.region("body", 2, 2, 0, None);
    terminal.region("foot", -1, 1, 0, None);
    terminal.on_change(|name, line_list| println!("    changed  {:<5} {}", name, line_list.py_repr()));
    println!("-- run");
    terminal.run(&["python3", "-c", DRAWING_APP], None, None, 10.0)?;
    for (said, typed) in [("'n'", "n"), ("'n'", "n"), ("'r': a redraw, nothing new", "r"), ("'f'", "f"),
                          ("'nnn', typed at once", "nnn"), ("'q'", "q")] {
        println!("-- {}", said);
        terminal.send(typed, 1.0);
    }
    let status = terminal.wait(10.0)?;
    println!("-- exit status {}; a region asked by name: {}", status.py_repr(), terminal.region_text("body")?.py_repr());
    if let Err(error) = terminal.region_text("nosuch") { println!("-- no such region: {} {}", error.kind(), error); }
    Ok(())
}

fn run_events() -> Result<(), VtermError> {
    let mut terminal = Terminal::new(4, 20, 0.1)?;
    terminal.on_event(|event| println!("    {}", event));
    for (said, data) in [("'ab'", "ab".to_string()), ("a line feed and 'c'", "\r\nc".to_string()),
                         ("the cursor to row 4, hidden", format!("{}[4;1H{}[?25l", ESC, ESC)),
                         ("the alternate screen", format!("{}[?1049h", ESC)), ("the bell", "\x07".to_string()),
                         ("nothing that draws: a reset of attributes", format!("{}[0m", ESC))] {
        println!("-- fed: {}", said);
        terminal.feed(&data);
    }
    println!("-- asked where the cursor is, nobody running: the answer waits");
    terminal.feed(&format!("{}[2;5H{}[6n", ESC, ESC));
    println!("    answer() = {}", PyBytes(&terminal.answer()).py_repr());
    println!("-- a key pressed with nobody running");
    terminal.press("f1", &[], 0.0)?;
    println!("    answer() = {}", PyBytes(&terminal.answer()).py_repr());
    Ok(())
}

fn run_missing() {
    std::env::set_var(hwut_vterm::LIBRARY_VARIABLE, "/nowhere/libvterm.so");
    hwut_vterm::reset_library();
    match Screen::new(24, 80) {
        Ok(_) => println!("a Screen stands on a library that is not there"),
        Err(error) => {
            //  THE SYSTEM'S OWN WORDS for the failed load are left out; what
            //  this module says -- the line, and the way to install -- stands.
            let text = error.to_string();
            let mut line_list = text.split('\n');
            let first = line_list.next().unwrap_or("");
            println!("{}: {}", error.kind(), first.split(" -- ").next().unwrap_or(""));
            for line in line_list { println!("{}", line); }
        }
    }
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "A terminal's screen read by a test: libvterm through dlopen.", vec![
        ("text",       || probe(run_text)),
        ("screen",     || probe(run_screen)),
        ("attributes", || probe(run_attributes)),
        ("colours",    || probe(run_colours)),
        ("unnoticed",  || probe(run_unnoticed)),
        ("keys",       || probe(run_keys)),
        ("regions",    || probe(run_regions)),
        ("events",     || probe(run_events)),
        ("missing",    run_missing),
    ]).exit();
}

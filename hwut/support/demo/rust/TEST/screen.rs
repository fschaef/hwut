// @hwut {
//     title     = "Demo: a terminal program's screen, as a person sees it"
//     build     { framework = "make", target = "%.exe"
//                 caps { timeout_sec = 900 } }
//     tolerance { regions    = false
//                 comment    = false
//                 whitespace = false }
//     choices {
//         open   { features = ["demo-rust+cover-terminal-screen", "demo-rust+cover-screen-as-seen"] }
//         scroll { features = ["demo-rust+cover-terminal-screen", "demo-rust+cover-screen-as-seen"] }
//     }
// }
//
//______________________________________________________________________________
// SUBJECT  the screen of 'viewer.exe' (of 'viewer.rs'), a full-screen file
//          viewer, run in a terminal of 9 rows and 40 columns and driven by
//          its keys.
// REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
//              as they fit, and a status line -- the keys flush left, the
//              lines shown flush right; 'j' and the down key go one line
//              further, 'k' one back.
//
// The support's 'hwut_vterm::Terminal' runs the viewer on a pseudo-terminal:
// the viewer cannot tell it from a real one. The test PRESSES KEYS and is
// told what CHANGED: three regions are declared -- title, body, status --
// and after every key, once the viewer has gone quiet, each region whose
// text changed is printed. A redraw that changes nothing is not told.
//
// THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
// off, in the header:
//
//     regions = false     the file shown is a GOOD file of hwut, with a
//                         '##! potpourri' ... '####' block. On this screen
//                         those are characters, not a region to open.
//     comment = false     '## ...' lines are characters too, not notes.
//     whitespace = false  the status line's two halves stand flush left and
//                         flush right: every blank between them counts.
//
// libvterm must be installed ('apt install libvterm0'); where it is not, the
// test prints why and probes nothing -- its output differs from GOOD and the
// reason stands in the difference.
//
// CHOICES  open    the viewer opened, then quit.
//          scroll  down, down, 'j', then 'k': three lines on, one back.
//______________________________________________________________________________
use hwut::hwut_vterm::{Terminal, VtermError};

const SAMPLE: &str = "\
## demo.rs race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.
";

/// RETURN: String, the directory this program stands in -- the test
///         directory, where the Makefile built it and 'viewer.exe'.
fn here() -> String {
    std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_string_lossy().into_owned()))
        .unwrap_or_else(|| ".".to_string())
}

/// RETURN: nothing. Prints one region that changed, its rows as they stand
///         on the screen, from the first column.
fn show(name: &str, line_list: &[String]) {
    println!("-- {}", name);
    for line in line_list { println!("{}", line); }
}

/// RETURN: Ok(()), the viewer ran on the sample, 'key_list' was pressed, the
///         viewer quit, and what changed after each step was printed;
///         Err(VtermError) where libvterm is missing or a key has no name.
///         The sample stands in a directory of the choice's own: two choices
///         run at once write it each for itself.
fn view(choice: &str, key_list: &[&str]) -> Result<(), VtermError> {
    let here = here();
    let path = format!("{}/TMP/{}/race.txt", here, choice);
    let _ = std::fs::create_dir_all(format!("{}/TMP/{}", here, choice));
    let _ = std::fs::write(&path, SAMPLE);
    let mut terminal = Terminal::new(9, 40, 0.1)?;
    terminal.region("title",  0, 1, 0, None);
    terminal.region("body",   1, 7, 0, None);
    terminal.region("status", -1, 1, 0, None);
    terminal.on_change(show);
    println!("> viewer.exe race.txt");
    let viewer = format!("{}/viewer.exe", here);
    terminal.run(&[&viewer, &path], None, None, 10.0)?;
    let attribute = terminal.cell(0, 1)?.attribute_text();
    println!("title bar: {}", if attribute.is_empty() { "plain".to_string() } else { attribute });
    for key in key_list {
        println!("> {}", key);
        if key.chars().count() == 1 { terminal.send(key, 1.0); } else { terminal.press(key, &[], 1.0)?; }
    }
    terminal.send("q", 1.0);
    let status = terminal.wait(10.0)?;
    println!("> q -- exit status {}", status.unwrap_or(-1));
    Ok(())
}

/// RETURN: never; exits 0 once the choice named on the command line ran and
///         '<hwut-end>' was printed; 1 where no such choice is, or libvterm
///         is missing (the reason printed).
fn main() {
    let choice = std::env::args().nth(1).unwrap_or_default();
    let key_list: &[&str] = match choice.as_str() {
        "open"   => &[],
        "scroll" => &["down", "down", "j", "k"],
        _ => { println!("choices: open, scroll"); std::process::exit(1); }
    };
    if let Err(error) = view(&choice, key_list) {
        println!("{}", error);
        std::process::exit(1);
    }
    println!("<hwut-end>");
}

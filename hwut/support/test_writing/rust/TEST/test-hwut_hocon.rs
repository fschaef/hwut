// @hwut {
//     title      = "HOCON parser: subset (A), annotated tree"
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         comments  { features = ["rust-hocon"] }
//         faults    { features = ["rust-hocon"] }
//         fuzz      { features = ["rust-hocon"] }
//         numbers   { features = ["rust-hocon"] }
//         oneline   { features = ["rust-hocon"] }
//         positions { features = ["rust-hocon"] }
//         quoting   { features = ["rust-hocon"] }
//         refused   { features = ["rust-hocon"] }
//         scalars   { features = ["rust-hocon"] }
//         structure { features = ["rust-hocon"] }
//         triple    { features = ["rust-hocon"] }
//         unclosed  { features = ["rust-hocon"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-hwut_hocon.py', choice for
//          choice, held against its GOOD files by '.link'. The fuzz draws
//          the deterministic stream exactly as Python draws it; a parse is
//          bounded by running it in a thread of its own.
//______________________________________________________________________________
use std::sync::mpsc;
use std::time::Duration;

use hwut::deterministic_random::DeterministicStream;
use hwut::hwut_hocon::{parse, Node, SourceLine};
use hwut::hwut_pytext::PyRepr;
use hwut::hwut_runner::HwutRunner;

fn banner(label: &str) { println!("\n--- {} ---", label); }

/// RETURN: Vec<SourceLine>, 'text' split at '\n', offsets applied uniformly.
fn lines(text: &str, line_offset: i64, column_offset: i64) -> Vec<SourceLine> {
    text.split('\n').enumerate().map(|(i, l)| SourceLine::new(l, i as i64 + 1 + line_offset, column_offset)).collect()
}

/// Prints the annotated tree, positions included.
fn show(node: &Node, indent: usize) {
    let pad = "    ".repeat(indent);
    match node {
        Node::Object(object) => {
            println!("{}{{ at {}", pad, object.position);
            for entry in &object.entry_list {
                println!("{}  key '{}' at {} ->", pad, entry.key, entry.key_position);
                show(&entry.node, indent + 1);
            }
            println!("{}}}", pad);
        }
        Node::List(list) => {
            println!("{}[ at {}", pad, list.position);
            for item in &list.item_list { show(item, indent + 1); }
            println!("{}]", pad);
        }
        Node::Scalar(scalar) => {
            println!("{}{} ({}) at {}", pad, scalar.value.py_repr(), scalar.value.type_name(), scalar.position);
        }
    }
}

fn run_at(label: &str, text: &str, line_offset: i64, column_offset: i64) {
    banner(label);
    let (document, fault_list) = parse(&lines(text, line_offset, column_offset), "f.hocon");
    show(&Node::Object(document), 0);
    for fault in fault_list { println!("FAULT {}", fault); }
}

fn run(label: &str, text: &str) { run_at(label, text, 0, 0); }

fn test_scalars() {
    run("scalars",
        concat!("a = bare\n", "b = \"quoted \\\"x\\\" and \\n\"\n", "c = 42\n", "d = -3.14\n", "e = 1e-6\n",
                "f = true\n", "g = no\n", "h = make %.exe\n", "i: \"colon-bound\"\n", "j = null\n",
                "k = nihil\n", "l =\n"));
}

fn test_numbers() {
    run("decimal, with sign and exponent", "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n");
    run("the visual helper enters no value", "a = 1_000\nb = 7_000.5_5\n");
    run("hexadecimal, binary, octal", "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n");
    run("roman", "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n");
    run("a sign standing apart from its digits", "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n");
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n");
    run("no arithmetic: this language computes nothing", "a = 5 - 1\n");
}

fn test_quoting() {
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n");
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n");
}

fn test_structure() {
    run("nesting and key-brace", "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n");
    run("lists", concat!("commas   = [one, two, three]\n", "newlines = [\n", "    1\n", "    2\n", "]\n",
                         "objects  = [ { a = 1 }, { a = 2 } ]\n", "empty    = []\n"));
}

fn test_oneline() {
    run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n");
    run("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
    run("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
}

fn test_comments() {
    run("comments", concat!("# whole line\n", "a = 1   # trailing\n", "// slashes too\n",
                            "b = 2   // trailing slashes\n", "c = bare value # comment cut\n"));
}

fn test_refused() {
    run("refused, each by name", "include \"other.conf\"\na = ${outside.value}\nb += appended\nd = survives\n");
}

fn test_triple() {
    let q = "\"\"\"";
    run("several lines: indentation and blank ends go",
        &format!("doc = {}\n    First line.\n\n      indented more\n    last line\n    {}\nafter = 1\n", q, q));
    run("on one line; beside another entry; in a list",
        &format!("a = {}one line{}  b = 2\nc = [{}x{}, \"y\"]\n", q, q, q, q));
    run("as written: a quote, a backslash-n, a comment marker",
        &format!("a = {}says \"no\" \\n # not a comment{}\n", q, q));
    run("never closed: a fault, at its beginning", &format!("a = 1\nb = {}open\nc = 2\n", q));
}

fn test_faults() {
    run("faults accumulate", "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n");
}

fn test_unclosed() {
    run("a list closed by the object's brace", "@hwut { title = \"B\" choices = [ }\nafter = 1\n");
    run("a stray character in a list", "a = [1, ; 2]\n");
}

const FUZZ_SEED_TUPLE: [&str; 2] = [
    concat!("@hwut {\n", "    title    = \"T\"\n", "    choices  = [\"a\", \"b\"]\n",
            "    tolerance { eq_pattern = [\"x.*\"] }\n", "    n        = -1.5e3\n", "    f        = true\n", "}\n"),
    concat!("hwut {\n", "    target     { clean = \"./c.sh\" }\n", "    dependency { \"a.py\" = [\"b.py one\"] }\n",
            "    ignore     = [\"x\"]   // comment\n", "    # comment\n", "}\n"),
];
//  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few that
//  it refuses by name, and some ordinary ones.
const FUZZ_ALPHABET: [&str; 26] = ["{", "}", "[", "]", "\"", ",", "=", ":", "#", "/", "\\", "$", " ", "\n", "\t",
                                   "-", "+", ".", "e", "E", "0", "a", "\"\"\"", "${", "//", "+="];
const FUZZ_INPUT_N: usize = 3000;
const FUZZ_BOUND_S: f64 = 0.5;                // one parse takes well under a millisecond

/// RETURN: String, 'text' edited by one to four random insertions, deletions
///         and duplications of a short stretch -- drawn as Python draws them.
fn mutated(stream: &mut DeterministicStream, text: &str) -> String {
    let mut text: Vec<char> = text.chars().collect();
    for _ in 0..stream.next_int(1, 4) {
        let i = stream.next_int(0, text.len() as i64) as usize;
        match stream.next_int(0, 2) {
            0 => {
                let insert: Vec<char> = stream.select(&FUZZ_ALPHABET).chars().collect();
                text.splice(i..i, insert);
            }
            1 => { if i < text.len() { text.remove(i); } }
            _ => {
                let j = stream.next_int(0, text.len() as i64) as usize;
                let piece: Vec<char> = text[j.min(text.len())..(j + 5).min(text.len())].to_vec();
                text.splice(i..i, piece);
            }
        }
    }
    text.into_iter().collect()
}

fn test_fuzz() {
    let mut stream = DeterministicStream::new(4711);
    let mut tally: [(&str, usize); 4] = [("clean", 0), ("with faults", 0), ("hang", 0), ("exception", 0)];
    let mut example: Vec<(&str, String)> = Vec::new();
    //  A PANIC IS PYTHON'S EXCEPTION: counted, its text kept, not printed.
    std::panic::set_hook(Box::new(|_| {}));
    for _ in 0..FUZZ_INPUT_N {
        let seed = *stream.select(&FUZZ_SEED_TUPLE);
        let text = mutated(&mut stream, seed);
        let (sender, receiver) = mpsc::channel();
        let given = text.clone();
        std::thread::spawn(move || {
            let result = std::panic::catch_unwind(|| parse(&lines(&given, 0, 0), "f.hocon").1.len());
            let _ = sender.send(result.map_err(|e| e.downcast_ref::<String>().cloned()
                                                    .or_else(|| e.downcast_ref::<&str>().map(|s| s.to_string()))
                                                    .unwrap_or_default()));
        });
        match receiver.recv_timeout(Duration::from_secs_f64(FUZZ_BOUND_S)) {
            Ok(Ok(fault_n)) => tally[if fault_n > 0 { 1 } else { 0 }].1 += 1,
            Ok(Err(message)) => {
                tally[3].1 += 1;
                if !example.iter().any(|(k, _)| *k == "exception") {
                    example.push(("exception", format!("panic: {}\n{}", message, text)));
                }
            }
            Err(_) => {                                  // the thread runs on, abandoned
                tally[2].1 += 1;
                if !example.iter().any(|(k, _)| *k == "hang") { example.push(("hang", text)); }
            }
        }
    }
    let _ = std::panic::take_hook();
    banner(&format!("{} mutated headers", FUZZ_INPUT_N));
    for (key, n) in tally { println!("    {:<12} {}", key, n); }
    for (key, text) in example { println!("FIRST {}:\n{}", key.to_uppercase(), text); }
}

fn test_positions() {
    let text = "@hwut {\n    title = \"T\"\n}";
    run("plain: as its own file", text);
    run_at("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "HOCON parser: subset (A), annotated tree;", vec![
        ("scalars",   test_scalars),
        ("numbers",   test_numbers),
        ("quoting",   test_quoting),
        ("structure", test_structure),
        ("oneline",   test_oneline),
        ("comments",  test_comments),
        ("refused",   test_refused),
        ("triple",    test_triple),
        ("unclosed",  test_unclosed),
        ("fuzz",      test_fuzz),
        ("faults",    test_faults),
        ("positions", test_positions),
    ]).exit();
}

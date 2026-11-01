// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN RUST -- the port of
//          'python/hwut_runner.py': the same modes, the same words.
//
//     app --hwut-info      the info block; exit 0.
//     app <choice>         one choice; test output on stdout and stderr,
//                          '<hwut-end>' after it. '-' runs a choice-less test.
//     app --interactive    choices started over stdin, output into two named
//                          sink files per choice, 'done' on the original stdout.
//     app                  the choice-less test; where the application has
//                          choices, refused, naming them.
//
// USAGE:
//
//     use hwut::hwut_runner::HwutRunner;
//     fn plain()  { ... }
//     fn tricky() { ... }
//     fn main() {
//         HwutRunner::new(std::env::args().collect(), "What this tests",
//                         vec![("plain", plain), ("tricky", tricky)]).exit();
//     }
//
// A choice-less test names its one function "-". Before 'run' a test may set
// 'happy' (patterns), 'same_f' and 'parallel_f' (interactive: choices run
// concurrently).
//
// THE INTERACTIVE PROTOCOL is Python's, line for line:
//     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
//     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
// EVERY CHOICE RUNS IN A CHILD PROCESS of its own ('fork'): a choice that
// calls 'std::process::exit' or panics ends that choice, not the session --
// what Python gets by catching SystemExit -- and no choice inherits
// another's state.
//______________________________________________________________________________
use std::ffi::CString;
use std::io::{BufRead, Write};

use crate::posix;

const NONE: &str = "-";

/// The front end of one test application.
pub struct HwutRunner {
    pub argv:        Vec<String>,
    pub title:       String,
    pub choice_list: Vec<(String, fn())>,
    pub happy:       Vec<String>,
    pub same_f:      bool,
    pub parallel_f:  bool,
    sorted:          Vec<String>,
    control_fd:      i32,
    pending:         Vec<(i32, String)>,          // (pid, token) of a running child
}

impl HwutRunner {
    /// RETURN: HwutRunner, ready for 'run()'.
    ///
    /// 'argv' is the command line ('std::env::args()'), 'title' the info
    /// block's title line, 'choice_list' maps a choice's name to its
    /// function -- the one name "-" for a choice-less test.
    pub fn new(argv: Vec<String>, title: &str, choice_list: Vec<(&str, fn())>) -> HwutRunner {
        let choice_list: Vec<(String, fn())> =
            choice_list.into_iter().map(|(n, f)| (n.to_string(), f)).collect();
        let mut sorted: Vec<String> = choice_list.iter().map(|(n, _)| n.clone()).collect();
        sorted.sort();
        HwutRunner { argv, title: title.to_string(), choice_list, happy: Vec::new(),
                     same_f: false, parallel_f: false, sorted, control_fd: -1,
                     pending: Vec::new() }
    }

    /// RETURN: never; the process exits with what 'run()' returned.
    pub fn exit(mut self) -> ! {
        let status = self.run();
        let _ = std::io::stdout().flush();
        std::process::exit(status)
    }

    /// RETURN: true where the application is choice-less ('-' its one choice).
    fn none_f(&self) -> bool { self.choice_list.len() == 1 && self.choice_list[0].0 == NONE }

    /// RETURN: Some(function) of the choice 'name'; None where none is.
    fn function_of(&self, name: &str) -> Option<fn()> {
        self.choice_list.iter().find(|(n, _)| n == name).map(|(_, f)| *f)
    }

    /// RETURN: Vec<String>, the lines of the info block.
    fn info_block_lines(&self) -> Vec<String> {
        let mut result = vec![if self.title.ends_with(';') { self.title.clone() }
                              else { format!("{};", self.title) }];
        if !self.none_f() { result.push(format!("CHOICES: {};", self.sorted.join(", "))); }
        for pattern in &self.happy { result.push(format!("HAPPY: {};", pattern)); }
        if self.same_f { result.push("SAME;".to_string()); }
        result.push("INTERACTIVE;".to_string());
        result
    }

    /// RETURN: i32, the exit status of the mode the command line selects (see
    ///         the head of this file); a refusal is 1.
    pub fn run(&mut self) -> i32 {
        let word = self.argv.get(1).cloned();
        let list = self.sorted.join(", ");
        match word.as_deref() {
            Some("-h") | Some("--hi") | Some("--hwut-info") | Some("--sos") | Some("--wtf") => {
                for line in self.info_block_lines() { println!("{}", line); }
                0
            }
            Some("--interactive") => self.mode_interactive(),
            None => {
                if self.none_f() { return self.run_one(self.choice_list[0].1); }
                println!("error: a choice is required: {} -- name one, or let 'hwut.play' ask.", list);
                1
            }
            Some(word) => {
                if let Some(function) = self.function_of(word) { return self.run_one(function); }
                if self.none_f() {
                    println!("error: '{}': this application has no choices -- call it without one.", word);
                    return 1;
                }
                println!("error: choice '{}' not available.", word);
                println!("error: available: {}.", list);
                if let Some(best) = levenshtein_best_match(Some(word), &self.sorted) {
                    println!("error: did you mean '{}'?", best);
                }
                1
            }
        }
    }

    /// RETURN: i32, 0; the choice ran, then '<hwut-end>' was printed (R-70).
    fn run_one(&self, function: fn()) -> i32 {
        function();
        println!("<hwut-end>");
        let _ = std::io::stdout().flush();
        0
    }

    // ------------------------------------------------------ interactive mode
    /// RETURN: nothing; 'message' and a newline are written on the UP channel.
    fn up(&self, message: &str) {
        let text = format!("{}\n", message);
        unsafe { posix::write(self.control_fd, text.as_ptr() as *const _, text.len()); }
    }

    /// RETURN: nothing; every child that has ended is reported 'done'; where
    ///         'block_f' it waits until none is left.
    fn reap(&mut self, block_f: bool) {
        while !self.pending.is_empty() {
            let mut status = 0;
            let pid = unsafe { posix::waitpid(-1, &mut status, if block_f { 0 } else { posix::WNOHANG }) };
            if pid <= 0 { return; }
            if let Some(i) = self.pending.iter().position(|(p, _)| *p == pid) {
                let (_, token) = self.pending.swap_remove(i);
                self.up(&format!("done {} {}", token, posix::exit_code_of(status)));
            }
        }
    }

    /// RETURN: Some(status), the child's exit status where the choice ran to
    ///         its end in this call (sequential); None where it runs on
    ///         (parallel, reported when reaped). A child that cannot be made
    ///         is status 1.
    fn run_into_sinks(&mut self, function: fn(), sink_out: &str, sink_err: &str, token: &str) -> Option<i32> {
        let _ = std::io::stdout().flush();
        let _ = std::io::stderr().flush();
        let out_path = CString::new(sink_out).unwrap_or_default();
        let err_path = CString::new(sink_err).unwrap_or_default();
        let pid = unsafe { posix::fork() };
        if pid < 0 { return Some(1); }
        if pid == 0 {
            unsafe {
                let mode = posix::O_WRONLY | posix::O_CREAT | posix::O_TRUNC;
                let out = posix::open(out_path.as_ptr(), mode, 0o644);
                let err = posix::open(err_path.as_ptr(), mode, 0o644);
                if out < 0 || err < 0 { posix::_exit(1); }
                posix::dup2(out, 1); posix::dup2(err, 2);
                posix::close(out); posix::close(err);
                posix::close(self.control_fd);
            }
            //  A PANIC IS AN EXCEPTION: its message stands in the error sink,
            //  the status is 1 -- as Python's traceback and status.
            let status = match std::panic::catch_unwind(function) {
                Ok(()) => {
                    if std::env::var_os("HWUT_NO_TERMINAL").map_or(true, |v| v.is_empty()) {
                        println!("<hwut-end>");
                    }
                    0
                }
                Err(_) => 1,
            };
            let _ = std::io::stdout().flush();
            let _ = std::io::stderr().flush();
            unsafe { posix::_exit(status) }
        }
        if self.parallel_f {
            self.pending.push((pid, token.to_string()));
            return None;
        }
        let mut status = 0;
        while unsafe { posix::waitpid(pid, &mut status, 0) } < 0 {}
        Some(posix::exit_code_of(status))
    }

    /// RETURN: Some(function) where 'token' names a choice -- by name, by its
    ///         decimal index into the sorted list, or '-' for the choice-less
    ///         test; None else.
    fn find_choice(&self, token: &str) -> Option<fn()> {
        if let Some(function) = self.function_of(token) { return Some(function); }
        if !token.is_empty() && token.bytes().all(|b| b.is_ascii_digit()) {
            if let Ok(i) = token.parse::<usize>() {
                if i < self.sorted.len() { return self.function_of(&self.sorted[i]); }
            }
        }
        None
    }

    /// RETURN: bool, true where the session goes on; false where it ends.
    fn interprete(&mut self, line: &str) -> bool {
        let field: Vec<&str> = line.split_whitespace().collect();
        match field.as_slice() {
            ["quit"] | ["q"] | ["exit"] => return false,
            ["info"] => {
                for info_line in self.info_block_lines() { self.up(&format!("info: {}", info_line)); }
                self.up("done - 0");
            }
            ["run", token, sink_out, sink_err] => {
                match self.find_choice(token) {
                    None => self.up(&format!("fail {} unknown-choice", token)),
                    Some(function) => {
                        if let Some(status) = self.run_into_sinks(function, sink_out, sink_err, token) {
                            self.up(&format!("done {} {}", token, status));
                        }
                    }
                }
            }
            _ => self.up("fail - bad-command"),
        }
        true
    }

    /// RETURN: i32, 0, once the session ended ('quit' or end of input). The
    ///         original stdout is the UP channel; fd 1 and fd 2 point at a
    ///         stray sink for output outside a running choice.
    fn mode_interactive(&mut self) -> i32 {
        let _ = std::io::stdout().flush();
        let _ = std::io::stderr().flush();
        unsafe {
            self.control_fd = posix::dup(1);
            let mut path = *b"/tmp/hwut_stray_XXXXXX\0";
            let stray = posix::mkstemp(path.as_mut_ptr() as *mut _);
            if stray >= 0 { posix::dup2(stray, 1); posix::dup2(stray, 2); posix::close(stray); }
        }
        let stdin = std::io::stdin();
        let mut input = stdin.lock();
        let mut line = String::new();
        loop {
            self.reap(false);
            line.clear();
            match input.read_line(&mut line) {
                Ok(0) | Err(_) => break,
                Ok(_) => {}
            }
            let text = line.trim();
            if text.is_empty() { continue; }
            let text = text.to_string();
            if !self.interprete(&text) { break; }
        }
        self.reap(true);
        self.up("bye");
        0
    }
}

/// RETURN: Option<&str>, the element of 'haystack' least distant from
///         'needle' (Levenshtein; the first of equally distant ones);
///         None where 'needle' is None or 'haystack' is empty.
pub fn levenshtein_best_match<'a>(needle: Option<&str>, haystack: &'a [String]) -> Option<&'a str> {
    let needle = needle?;
    if haystack.is_empty() { return None; }
    if let Some(same) = haystack.iter().find(|h| *h == needle) { return Some(same); }
    let mut best: Option<(&'a str, usize)> = None;
    for key in haystack {
        let distance = levenshtein_distance(needle, key);
        if best.map_or(true, |(_, d)| distance < d) { best = Some((key, distance)); }
    }
    best.map(|(key, _)| key)
}

/// RETURN: usize, the Levenshtein distance between 'a' and 'b', counted in
///         characters.
pub fn levenshtein_distance(a: &str, b: &str) -> usize {
    let (mut a, mut b): (Vec<char>, Vec<char>) = (a.chars().collect(), b.chars().collect());
    if a == b { return 0; }
    if a.is_empty() { return b.len(); }
    if b.is_empty() { return a.len(); }
    if a.len() < b.len() { std::mem::swap(&mut a, &mut b); }
    let mut previous: Vec<usize> = (0..=b.len()).collect();
    for (i, ca) in a.iter().enumerate() {
        let mut current = vec![i + 1];
        for (j, cb) in b.iter().enumerate() {
            let insert   = current[j] + 1;
            let delete   = previous[j + 1] + 1;
            let exchange = previous[j] + if ca == cb { 0 } else { 1 };
            current.push(insert.min(delete).min(exchange));
        }
        previous = current;
    }
    previous[b.len()]
}

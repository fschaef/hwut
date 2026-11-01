// @hwut {
//     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
//     build   { framework = "make", executable = "%.exe"
//               caps { timeout_sec = 900 } }
//     pype    = "build.pypes"
//     same    = true
//     choices = ["serial", "parallel"]
//     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
//                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
//                 "pype-quantity", "pype-anchors-globs-flush"]
//     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
// }
//
//______________________________________________________________________________
// SUBJECT  the log of a recursive build -- configure, then the directories
//          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary a
//          pype system makes of it.
// REQUIREMENT  A parallel build builds what the serial build builds: the same
//              sources, the same warnings, the same archives and the same
//              program, linked from the same parts.
//
// The application only REPORTS the build as it happens, as 'make -w' would.
// The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
// between it and the comparison (hwut runs it; the application prints no
// '<hwut-end>'): 'normalise.pype' drops a parallel job's tag, 'build.pype'
// writes the summary, sorted -- see their own comments.
//
// 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.rs.txt' -- a link
// to the Python demonstration's 'build.py.txt'. 'choices' is a list: no
// choice states anything of its own. The laws: the compile times sum to
// under 5 s, and nothing broke the build's grammar ('((breaches: 0))').
//
// A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once;
// a pype that judges time is fed live ('protocol.sh slow').
//______________________________________________________________________________
mod clock_random;

use std::sync::{Arc, Mutex};
use std::thread;

use clock_random::Random;

/// What one directory does: its sources, warnings and product.
struct Directory { name: &'static str, source_list: &'static [&'static str],
                   warning_list: &'static [(&'static str, &'static str)], product: &'static str }

const DIRECTORY_LIST: [Directory; 3] = [
    Directory { name: "lib", source_list: &["lib/str.c", "lib/num.c", "lib/map.c"],
                warning_list: &[("lib/num.c", "lib/num.c:14:9: warning: unused variable 'n'")],
                product: "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o" },
    Directory { name: "app/plugins", source_list: &["app/plugins/png.c", "app/plugins/svg.c"],
                warning_list: &[("app/plugins/svg.c", "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'")],
                product: "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o" },
    Directory { name: "app", source_list: &["app/main.c", "app/cli.c"], warning_list: &[],
                product: "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a" },
];

/// RETURN: &Directory, the one named 'name'.
fn directory(name: &str) -> &'static Directory {
    DIRECTORY_LIST.iter().find(|d| d.name == name).expect("a directory of DIRECTORY_LIST")
}

/// RETURN: Vec<String>, what building directory 'name' prints, its sources
///         compiled in the time each takes.
fn compile_lines(name: &str, random: &mut Random) -> Vec<String> {
    let spec = directory(name);
    let mut line_list = Vec::new();
    for source in spec.source_list {
        let took = random.uniform(0.04, 0.12);
        std::thread::sleep(std::time::Duration::from_secs_f64(took));
        let spent = if took < 0.1 { format!("{} ms", (took * 1000.0) as i64) } else { format!("{:.2} s", took) };
        line_list.push(format!("cc -c {} -o {}.o (took {})", source, &source[..source.len() - 2], spent));
        if let Some((_, warning)) = spec.warning_list.iter().find(|(s, _)| s == source) {
            line_list.push(warning.to_string());
        }
    }
    line_list
}

/// RETURN: Vec<String>, the block 'make -w' prints for 'name' at 'level',
///         the block of 'inner' nested before the product.
fn directory_block(name: &str, level: i32, inner: Option<&str>, random: &mut Random) -> Vec<String> {
    let mut line_list = vec![format!("make[{}]: Entering directory '{}'", level, name)];
    line_list.extend(compile_lines(name, random));
    if let Some(inner) = inner { line_list.extend(directory_block(inner, level + 1, None, random)); }
    line_list.push(directory(name).product.to_string());
    line_list.push(format!("make[{}]: Leaving directory '{}'", level, name));
    line_list
}

/// RETURN: nothing. Prints what 'configure' prints, and that make enters
///         the top directory.
fn configure() {
    println!("configure: checking for cc... cc");
    println!("configure: checking for ar... ar");
    println!("make: Entering directory 'demo'");
}

/// RETURN: nothing. Builds one directory after the other.
fn serial() {
    let mut random = Random::from_clock();
    configure();
    for line in directory_block("lib", 1, None, &mut random) { println!("{}", line); }
    for line in directory_block("app", 1, Some("app/plugins"), &mut random) { println!("{}", line); }
    println!("make: Leaving directory 'demo'");
}

/// RETURN: nothing. Builds 'lib' and 'app' at once. Each job prints its block
///         whole when done ('make -O'), every line tagged with the job; which
///         job finishes first is the scheduler's.
fn parallel() {
    configure();
    let lock = Arc::new(Mutex::new(()));
    let pool: Vec<_> = [(1, "lib", None), (2, "app", Some("app/plugins"))].into_iter().map(|(slot, name, inner)| {
        let lock = lock.clone();
        thread::spawn(move || {
            let block = directory_block(name, 1, inner, &mut Random::from_clock());
            let _held = lock.lock().unwrap();
            for line in block { println!("job{}: {}", slot, line); }
        })
    }).collect();
    for job in pool { let _ = job.join(); }
    println!("make: Leaving directory 'demo'");
}

/// RETURN: never; exits 0 once the build named on the command line was
///         reported; 1 where no such choice is.
fn main() {
    match std::env::args().nth(1).as_deref() {
        Some("serial")   => serial(),
        Some("parallel") => parallel(),
        _ => { println!("choices: serial, parallel"); std::process::exit(1); }
    }
}

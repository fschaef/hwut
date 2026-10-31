// @hwut {
//     title      = "hwut_fsm: a state machine as the test's model of the system"
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         syntax    { features = ["rust-fsm"] }
//         refused   { features = ["rust-fsm"] }
//         dfa       { features = ["rust-fsm"] }
//         nfa       { features = ["rust-fsm"] }
//         forbidden { features = ["rust-fsm"] }
//         model     { features = ["rust-fsm"] }
//         report    { features = ["rust-fsm"] }
//         masks     { features = ["rust-fsm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-hwut_fsm.py', choice for
//          choice, held against its GOOD files by '.link'.
//______________________________________________________________________________
use hwut::hwut_fsm::{FsmError, Machine, Where};
use hwut::hwut_pytext::{bool_text, PyRepr, PyTuple};
use hwut::hwut_runner::HwutRunner;

//  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
//  a fault while busy crashes it -- which must never happen.
const PROTOCOL: &str = "
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
";

fn banner(label: &str) { println!("\n--- {} ---", label); }

fn protocol() -> Machine { Machine::from_string(PROTOCOL, true, "fsm").unwrap() }

/// RETURN: String, a path as Python prints the tuple, or 'None'.
fn path_text(path: Option<Vec<String>>) -> String {
    path.map_or("None".to_string(), |p| PyTuple(&p).py_repr())
}

fn run_syntax() {
    banner("the protocol, written back");
    println!("{}", protocol().to_string());
    banner("the author's form: 'state', a chain, ':', blanks around '-->'");
    println!("{}", Machine::from_string("
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    ", true, "fsm").unwrap().to_string());
}

fn run_refused() {
    for text in ["A ---( x )---> B\n: ---( x )---> C", "A ---(  )---> B", ": ---( x )---> B",
                 "A B ---( x )---> C", "initial: A, B\nA ---( x )---> B", "forbidden: Q\nA ---( x )---> B",
                 "# nothing but a comment"] {
        banner(&text.replace('\n', " | "));
        match Machine::from_string(text, true, "fsm") {
            Ok(_)      => println!("accepted"),
            Err(error) => println!("FsmError: {}", error),
        }
    }
}

fn run_dfa() {
    let mut m = protocol();
    for (number, event) in ["request", "release", "grant", "release", "jump", "request"].iter().enumerate() {
        let moved = m.fire(event, number + 1);
        println!("    {:<8} -> {:<5} now {:<8} allowed: {}", event, bool_text(moved),
                 m.state().unwrap(), m.allowed().join(", "));
    }
    banner("questions where it stands");
    println!("can('grant')   {}", bool_text(m.can("grant")));
    println!("can('release') {}", bool_text(m.can("release")));
    println!("in_state('waiting') {}", bool_text(m.in_state("waiting")));
    println!("trace: {}", m.trace().iter().map(|(w, _, e, t)| format!("{}:{}>{}", w, e, t))
                             .collect::<Vec<_>>().join(" "));
}

fn run_nfa() {
    let mut m = Machine::from_string("
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    ", false, "fsm").unwrap();
    for event in ["x", "z", "y"] {
        m.fire(event, format!("t={}", event));
        println!("    after {}: {}", event, m.current().iter().cloned().collect::<Vec<_>>().join(", "));
    }
    banner("'state' asked of a set");
    m.reset();
    m.fire("x", Where::Nowhere);
    match m.state() {
        Ok(state)  => println!("{}", state),
        Err(error) => println!("FsmError: {}", error),
    }
}

fn run_forbidden() {
    let mut m = protocol();
    for (number, event) in ["request", "grant", "fault"].iter().enumerate() {
        println!("    {:<8} -> {}", event, bool_text(m.fire(event, number + 1)));
    }
    println!("now in {} -- breaches: {}", m.state().unwrap(), m.breach_n);
}

fn run_model() {
    let mut m = Machine::from_string(&format!("{}\n    state limbo\n    limbo ---( kick )---> idle\n", PROTOCOL),
                                     true, "fsm").unwrap();
    println!("check: {}", m.check(true));
    banner("path_to");
    for state in ["busy", "crashed", "limbo", "idle"] {
        println!("    {:<8} {}", state, path_text(m.path_to(state, None, true)));
    }
    m.fire("request", Where::Nowhere);
    println!("    busy from now: {}", path_text(m.path_to("busy", Some("now"), true)));
    println!("    state_reachable('idle', start='now'): {}", bool_text(m.state_reachable("idle", Some("now"), true)));
}

fn run_report() {
    let mut m = Machine::from_string(PROTOCOL, true, "protocol").unwrap();
    for event in ["request", "grant", "release", "request", "grant"] { m.fire(event, Where::Nowhere); }
    println!("report returns {}", m.report());
}

fn run_masks() {
    let mut m = protocol();
    banner("'grant' disallowed in every state, since line 2");
    m.disallow("grant", None, 2).unwrap();
    m.fire("request", 3);
    println!("    allowed now: {} -- can('grant'): {}", m.allowed().join(", "), bool_text(m.can("grant")));
    m.fire("grant", 4);
    println!("    path_to('busy'):               {}", path_text(m.path_to("busy", None, true)));
    println!("    path_to('busy', masked=False): {}", path_text(m.path_to("busy", None, false)));
    let n = m.check(true);
    println!("    check(): {}", n);
    let n = m.check(false);
    println!("    check(masked=False): {}", n);
    banner("allowed again; 'busy' forbidden while standing in it");
    m.allow("grant", None, 5).unwrap();
    m.fire("grant", 6);
    m.forbid("busy", 7).unwrap();
    m.fire("release", 8);
    m.fire("request", 9);
    m.fire("grant", 10);
    banner("permitted: 'busy', and the model's own 'crashed'");
    m.permit("busy", 11).unwrap();
    m.permit("crashed", 12).unwrap();
    let moved = m.fire("fault", 13);
    println!("    fault -> {} -- now in {}", bool_text(moved), m.state().unwrap());
    banner("a phase: 'release' disallowed in 'busy' for a block");
    m.reset();
    m.fire("request", Where::Nowhere);
    m.fire("grant", Where::Nowhere);
    m.disallowed("release", Some("busy"), "phase", |m| { m.fire("release", 20); }).unwrap();
    m.fire("release", 21);
    m.disallow("cancel", None, 22).unwrap();
    m.report();
    banner("refused: a word the model never names");
    let call_list: [&dyn Fn(&mut Machine) -> Result<(), FsmError>; 3] = [
        &|m| m.disallow("jump", None, Where::Nowhere),
        &|m| m.forbid("limbo", Where::Nowhere),
        &|m| m.allow("grant", Some("nowhere"), Where::Nowhere),
    ];
    for call in call_list {
        if let Err(error) = call(&mut m) { println!("FsmError: {}", error); }
    }
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "hwut_fsm: a state machine as the test's model of the system", vec![
        ("syntax",    run_syntax),
        ("refused",   run_refused),
        ("dfa",       run_dfa),
        ("nfa",       run_nfa),
        ("forbidden", run_forbidden),
        ("model",     run_model),
        ("report",    run_report),
        ("masks",     run_masks),
    ]).exit();
}

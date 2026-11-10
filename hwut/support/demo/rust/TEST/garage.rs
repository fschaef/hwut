// @hwut {
//     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
//     build    { framework = "make", target = "%.exe"
//                caps { timeout_sec = 900 } }
//     interactive = true
//     choices {
//         space       { features = ["demo-rust+cover-space-from-hocon", "demo-rust+cover-space-iterator", "demo-rust+cover-hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         random      { features = ["demo-rust+cover-deterministic-stream", "demo-rust+cover-hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         race-naive  { features = ["demo-rust+cover-deterministic-timeline", "demo-rust+cover-space-iterator", "demo-rust+cover-hwut-runner"]
//                       tolerance { constraints = ["overbooked > 0"] } }
//         race-atomic { features = ["demo-rust+cover-deterministic-timeline", "demo-rust+cover-space-iterator", "demo-rust+cover-hwut-runner"]
//                       tolerance { constraints = ["overbooked == 0"] } }
//     }
// }
//
//______________________________________________________________________________
// SUBJECT  the counter of free spaces at a garage's gates: which cars it
//          admits, which it refuses, and how many stand inside.
// REQUIREMENT  The garage admits a car only while a space is free, lets a car
//              out only while one stands inside, and never holds more cars
//              than it has spaces -- also when two gates admit at once.
//
// No choice writes its cases out by hand. Each GENERATES them, with one of
// hwut's helpers for writing tests -- the Rust port, the crate 'hwut'
// (support/test_writing/rust), linked by the Makefile beside this file:
//
// space        'garage-space.hocon' states the tested space, read by
//              'hwut_hocon'; 'space_iterator::r#do' walks every combination:
//              3 x 5 x 4 = 60 cases, each one cell of a matrix, checked
//              against the model.
// random       'DeterministicStream::new(4711)' draws 1000 cars at a garage
//              of 5. The draw is the same on every machine and in every
//              language hwut supports -- so this choice's GOOD is the Python
//              demonstration's, by link, and exact.
// race-naive   two gates, one free space; a gate CHECKS, and later ADMITS.
//              'deterministic_timeline' runs the gates as Triggers on
//              timelines drawn as strings; 'space_iterator' generates all six
//              interleavings. Where both check before either admits, both
//              admit: 'overbooked > 0', the GOOD is the violation report.
// race-atomic  the same six, checking and admitting in ONE step.
//
// THE FRONT END is the support's HwutRunner; 'interactive = true': hwut
// starts the application ONCE and asks for the choices one after another --
// an accelerator only: a choice's output equals what it prints alone.
//______________________________________________________________________________
use std::cell::RefCell;
use std::rc::Rc;

use hwut::deterministic_random::DeterministicStream;
use hwut::deterministic_timeline::{shared, SharedTrigger, TimelineError, Trigger, TriggerBase, TriggerDispatcher};
use hwut::hwut_hocon::{self, Node, SourceLine, Value};
use hwut::hwut_runner::HwutRunner;
use hwut::space_iterator;

/// The unit under test: a counter of the spaces a garage has.
struct Garage { capacity: i64, occupied: i64 }

impl Garage {
    /// RETURN: Garage, empty, of 'capacity' spaces.
    fn new(capacity: i64) -> Garage { Garage { capacity, occupied: 0 } }

    /// RETURN: i64, the number of spaces free now -- negative where the
    ///         garage is overbooked.
    fn free(&self) -> i64 { self.capacity - self.occupied }

    /// RETURN: true, a car was admitted, if a space was free;
    ///         false, else (the car is refused).
    fn arrive(&mut self) -> bool {
        if self.free() <= 0 { return false; }
        self.occupied += 1;
        true
    }

    /// RETURN: true, a car drove out, if one stood inside;
    ///         false, else.
    fn leave(&mut self) -> bool {
        if self.occupied == 0 { return false; }
        self.occupied -= 1;
        true
    }
}

/// RETURN: String, the directory this program stands in -- the test
///         directory, where the Makefile built it.
fn here() -> String {
    std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_string_lossy().into_owned()))
        .unwrap_or_else(|| ".".to_string())
}

// _____________________________________________________________________________
// space -- the tested space from HOCON, walked by space_iterator
//
/// RETURN: Vec<(String, Vec<i64>)>, the dimensions of the space in 'path', in
///         the order written: (name, values). Every fault the HOCON reader
///         found is printed with '!!' first.
fn read_space(path: &str) -> Vec<(String, Vec<i64>)> {
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let line_list: Vec<SourceLine> = text.lines().enumerate()
        .map(|(i, line)| SourceLine::new(line, i as i64 + 1, 0)).collect();
    let (document, fault_list) = hwut_hocon::parse(&line_list, "garage-space.hocon");
    for fault in &fault_list { println!("!! {}", fault); }
    let Some(Node::Object(space)) = document.get("space").map(|e| &e.node) else { return Vec::new(); };
    space.entry_list.iter().map(|entry| {
        let value_list = match &entry.node {
            Node::List(list) => list.item_list.iter().filter_map(|item| match item {
                Node::Scalar(s) => match s.value { Value::Int(n) => Some(n as i64), _ => None },
                _ => None,
            }).collect(),
            _ => Vec::new(),
        };
        (entry.key.clone(), value_list)
    }).collect()
}

/// RETURN: String, 'value_list' as Python prints a list of int.
fn list_text(value_list: &[i64]) -> String {
    format!("[{}]", value_list.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(", "))
}

/// RETURN: nothing. Prints every case of the space as a matrix cell.
fn space() {
    let dimension_list = read_space(&format!("{}/garage-space.hocon", here()));
    let value_list: Vec<Vec<i64>> = dimension_list.iter().map(|(_, v)| v.clone()).collect();
    println!("space: {}", dimension_list.iter().map(|(n, v)| format!("{} {}", n, list_text(v)))
                                       .collect::<Vec<_>>().join("  x  "));
    println!("cell: cars inside / cars refused at the gate ('!!' differs from the model)");
    let mut mismatch_n = 0;
    let mut row_db: Vec<((i64, i64), Vec<String>)> = Vec::new();
    for point in space_iterator::r#do(&value_list) {
        let (capacity, arriving, leaving) = (point[0], point[1], point[2]);
        let mut garage = Garage::new(capacity);
        let refused = (0..arriving).filter(|_| !garage.arrive()).count() as i64;
        for _ in 0..leaving { garage.leave(); }
        let admitted = arriving.min(capacity);
        let expected = (admitted - leaving.min(admitted), arriving - admitted);
        let got = (garage.occupied, refused);
        let mark = if got == expected { "  " } else { "!!" };
        if got != expected { mismatch_n += 1; }
        let cell = format!("{}/{}{}", got.0, got.1, mark);
        match row_db.iter_mut().find(|(key, _)| *key == (capacity, arriving)) {
            Some((_, row)) => row.push(cell),
            None           => row_db.push(((capacity, arriving), vec![cell])),
        }
    }
    for capacity in &value_list[0] {
        let head: Vec<String> = value_list[2].iter().map(|l| format!("leave {:<3}", l)).collect();
        println!("capacity {}   {}", capacity, head.join("  ").trim_end());
        for arriving in &value_list[1] {
            let row = &row_db.iter().find(|(key, _)| *key == (*capacity, *arriving)).unwrap().1;
            let cells: Vec<String> = row.iter().map(|c| format!("{:<9}", c)).collect();
            println!("{}", format!("  arrive {}   {}", arriving, cells.join("  ")).trim_end());
        }
    }
    println!("cases {}, differing from the model ((mismatches: {}))",
             row_db.len() * value_list[2].len(), mismatch_n);
}

// _____________________________________________________________________________
// random -- a deterministic stream of arrivals and departures
//
/// RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked.
fn random_stream() {
    let mut stream = DeterministicStream::new(4711);
    let mut garage = Garage::new(5);
    let mut model = 0;
    let (mut arrive_n, mut refused_n, mut leave_n, mut empty_n) = (0, 0, 0, 0);
    let mut histogram = [0usize; 6];
    let mut mismatch_n = 0;
    let mut strip = String::new();
    for _ in 0..1000 {
        if stream.coin(0.55) {
            arrive_n += 1;
            if !garage.arrive() { refused_n += 1; }
            model = (model + 1).min(5);
            strip.push('+');
        } else {
            leave_n += 1;
            if !garage.leave() { empty_n += 1; }
            model = (model - 1).max(0);
            strip.push('-');
        }
        if garage.occupied != model { mismatch_n += 1; }
        histogram[garage.occupied as usize] += 1;
    }
    println!("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves");
    println!("first 60: {}", &strip[..60]);
    println!("arrivals {}, refused {}; departures {}, from an empty garage {}", arrive_n, refused_n, leave_n, empty_n);
    println!("cars inside after each event:");
    for (n, count) in histogram.iter().enumerate() {
        println!("    {}  {:4}  {}", n, count, "#".repeat(count / 10));
    }
    println!("steps differing from the model ((mismatches: {}))", mismatch_n);
}

// _____________________________________________________________________________
// race -- two gates on drawn timelines
//
/// A gate on a timeline: its first tick checks, its second admits.
struct Gate {
    base:     TriggerBase,
    garage:   Rc<RefCell<Garage>>,
    atomic_f: bool,
    log:      Rc<RefCell<Vec<String>>>,
    step:     usize,
    saw_free: bool,
}

impl Trigger for Gate {
    fn base(&self) -> &TriggerBase { &self.base }

    /// RETURN: Ok(()); the gate performed its next step at the tick.
    fn fire(&mut self, _pseudo_time: usize) -> Result<(), TimelineError> {
        let name = self.base.name.clone();
        let mut garage = self.garage.borrow_mut();
        let text = if self.step == 0 && self.atomic_f {
            self.saw_free = garage.arrive();
            if self.saw_free { format!("{} checks+admits", name) } else { format!("{} refuses", name) }
        } else if self.step == 0 {
            self.saw_free = garage.free() > 0;
            format!("{} sees {} free", name, garage.free())
        } else if self.atomic_f {
            if self.saw_free { format!("{} opens", name) } else { format!("{} stays shut", name) }
        } else if self.saw_free {
            garage.occupied += 1;                           // the naive admit
            format!("{} admits", name)
        } else {
            format!("{} refuses", name)
        };
        self.log.borrow_mut().push(text);
        self.step += 1;
        Ok(())
    }
}

/// RETURN: Vec<(String, String)>, every pair of timelines in four ticks in
///         which each of two gates fires twice, never at the same tick:
///         gate A's and gate B's.
fn interleaving_list() -> Vec<(String, String)> {
    let line = |x: usize, y: usize| -> String { (0..4).map(|t| if t == x || t == y { '1' } else { ' ' }).collect() };
    let tick_list: Vec<usize> = (0..4).collect();
    let mut result = Vec::new();
    for point in space_iterator::r#do(&vec![tick_list; 4]) {
        let (a1, a2, b1, b2) = (point[0], point[1], point[2], point[3]);
        let mut all = point.clone();
        all.sort();
        all.dedup();
        if a1 < a2 && b1 < b2 && all.len() == 4 { result.push((line(a1, a2), line(b1, b2))); }
    }
    result
}

/// RETURN: nothing. Plays every interleaving of two gates at one space.
fn race(atomic_f: bool) {
    println!("one free space, two gates, one car at each; timelines: a digit fires");
    println!("    gate A  gate B  what happens                                    inside");
    let mut overbooked_n = 0;
    let interleavings = interleaving_list();
    for (timeline_a, timeline_b) in &interleavings {
        let garage = Rc::new(RefCell::new(Garage::new(1)));
        let log = Rc::new(RefCell::new(Vec::new()));
        let gate = |name: &str, timeline: &str| -> SharedTrigger {
            shared(Gate { base: TriggerBase::new(timeline, name), garage: garage.clone(), atomic_f,
                          log: log.clone(), step: 0, saw_free: false })
        };
        let _ = TriggerDispatcher::new(vec![gate("A", timeline_a), gate("B", timeline_b)]).run();
        let garage = garage.borrow();
        let over_f = garage.occupied > garage.capacity;
        if over_f { overbooked_n += 1; }
        let text = format!("    \"{}\"  \"{}\"  {:<46}  {} {}", timeline_a, timeline_b, log.borrow().join(", "),
                           garage.occupied, if over_f { "!!" } else { "  " });
        println!("{}", text.trim_end());
    }
    println!("interleavings overbooking the garage ((overbooked: {})) of {}", overbooked_n, interleavings.len());
}

/// RETURN: nothing. The gates check, then admit, in two steps.
fn race_naive() { race(false); }

/// RETURN: nothing. The gates check and admit in one step.
fn race_atomic() { race(true); }

/// RETURN: never; the HwutRunner exits with the status of the mode the
///         command line selects.
fn main() {
    HwutRunner::new(std::env::args().collect(),
                    "Demo: a garage's space counter -- a space, a stream and races, generated;",
                    vec![("space", space), ("random", random_stream),
                         ("race-naive", race_naive), ("race-atomic", race_atomic)]).exit();
}

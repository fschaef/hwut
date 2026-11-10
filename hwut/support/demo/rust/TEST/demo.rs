// @hwut {
//     title   = "Demo: what hwut tolerates, and where it is said"
//     build   { framework = "make", target = "%.exe"
//               caps { timeout_sec = 900 } }
//     choices {
//         plain       { features = ["demo-rust", "demo-rust+cover-exact-comparison"] }
//         tolerance   { features = ["demo-rust", "demo-rust+cover-equivalence-pattern", "demo-rust+cover-numeric-ratio"]
//                       tolerance {
//                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
//                           numeric_ratio = 0.01
//                       } }
//         constraints { features = ["demo-rust", "demo-rust+cover-constraints"]
//                       tolerance {
//                           constraints = ["load >= 0 and load <= 100",
//                                          "even % 2 == 0",
//                                          "twice == 2 * once"]
//                       } }
//         analogies   { features = ["demo-rust", "demo-rust+cover-analogies"] }
//         race        { features = ["demo-rust", "demo-rust+cover-order-free-block"] }
//         pool        { features = ["demo-rust", "demo-rust+cover-potpourri-subset-duplicates"] }
//         progress    { features = ["demo-rust", "demo-rust+cover-visible-nothing"]
//                       tolerance { nothing = ["[.]+"] } }
//         lisp        { features = ["demo-rust", "demo-rust+cover-analogy-markers"]
//                       tolerance { analogy = ["{", "}"] } }
//         clusters    { features = ["demo-rust", "demo-rust+cover-point-cloud-pair-distance"] }
//     }
// }
//
//______________________________________________________________________________
// A TEST APPLICATION OF HWUT, FOR READING -- the template, in Rust.
//
//     hwut.run                   builds 'demo.exe' by the Makefile beside
//                                this file, runs every choice below,
//                                compares with GOOD/
//     hwut.play demo.rs plain    runs one choice and records it in OUT/
//     hwut.accept demo.rs plain  blesses that recording as GOOD; it runs
//                                nothing. Where a GOOD stands, the change
//                                is 'hwut.merge's -- or '--force' (also
//                                '--as-is') replaces it whole.
//     hwut.merge                 shows OUTPUT against GOOD, key by key
//     hwut.config.show demo.rs   prints what hwut READ from the header above
//
// The header above is the whole configuration: a title, how the program is
// built ('build': the Makefile here makes '%.exe' of '%.rs'), and one scope
// per choice. hwut calls 'demo.exe <choice>' and compares what it prints on
// stdout with 'GOOD/demo.rs--<choice>.txt' -- each of which is a '.link' to
// the Python demonstration's GOOD: the same output, accepted once.
// '<hwut-end>' closes the stream: a stream without it never COMPLETED and is
// not accepted.
//
// Every run is seeded by the clock, so the output differs from run to run --
// and every choice passes anyway. What each choice shows, and why it passes,
// is said at its function below and in '../../python/TEST/demo.py'.
//______________________________________________________________________________
mod clock_random;

use std::sync::{Arc, Mutex};
use std::thread;

use clock_random::Random;

const GREETING_LIST: [&str; 6] = ["hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj"];

/// RETURN: nothing. Prints what never varies. Nothing is tolerated: the
///         output must equal GOOD, line by line.
fn plain(_: &mut Random) {
    println!("the first line");
    println!("the second line: 1 2 3");
}

/// RETURN: nothing. Prints a greeting and a value, both drawn at random.
///         'eq_pattern' makes any greeting equivalent to any other;
///         'numeric_ratio' takes any value of [19.91, 20.09] -- the band is
///         the GOOD's number times the ratio.
fn tolerance(random: &mut Random) {
    println!("greeting: {}, world", random.choice(&GREETING_LIST));
    println!("value:    {:.2}", random.uniform(19.91, 20.09));
}

/// RETURN: nothing. Prints bindings '((name: value))', each drawn at random,
///         each lawful: the constraints judge them, not the GOOD's values.
fn constraints(random: &mut Random) {
    println!("load  ((load: {:.1})) %", random.uniform(0.0, 100.0));
    println!("even  ((even: {}))", 2 * random.randint(0, 500));
    let once = random.randint(1, 50);
    println!("once  ((once: {}))", once);
    println!("twice ((twice: {}))", 2 * once);
}

/// RETURN: nothing. Prints two handles '((x))', each drawn at random, each
///         used consistently from opening to closing.
fn analogies(random: &mut Random) {
    let (first, second) = random.two_of(0x1000, 0x10000);
    println!("open  (({:04x})) input.txt", first);
    println!("open  (({:04x})) output.txt", second);
    println!("read  (({:04x})) 17 lines", first);
    println!("write (({:04x})) 17 lines", second);
    println!("close (({:04x}))", first);
    println!("close (({:04x}))", second);
}

/// RETURN: nothing. Three workers print as they finish; the order is the
///         scheduler's, the facts are not. The program frames the unordered
///         block itself: '##! potpourri' ... '####'.
fn race(_: &mut Random) {
    let lock = Arc::new(Mutex::new(()));
    println!("start");
    println!("##! potpourri");
    let pool: Vec<_> = [("A", 3), ("B", 5), ("C", 2)].into_iter().map(|(name, jobs)| {
        let lock = lock.clone();
        thread::spawn(move || {
            Random::from_clock().sleep(0.0, 0.02);
            let _held = lock.lock().unwrap();
            println!("worker {} done: {} jobs", name, jobs);
        })
    }).collect();
    for worker in pool { let _ = worker.join(); }
    println!("####");
    println!("all joined");
}

/// RETURN: nothing. Four workers take twelve jobs from one queue; each
///         reports the job it finished. Who takes how many is the
///         scheduler's: '##! potpourri subset duplicates'.
fn pool(_: &mut Random) {
    let queue = Arc::new(Mutex::new((0..12).collect::<Vec<i32>>()));
    let done_list = Arc::new(Mutex::new(Vec::<String>::new()));
    let pool: Vec<_> = ["A", "B", "C", "D"].into_iter().map(|name| {
        let (queue, done_list) = (queue.clone(), done_list.clone());
        thread::spawn(move || {
            let mut random = Random::from_clock();
            loop {
                if queue.lock().unwrap().pop().is_none() { return; }
                random.sleep(0.0, 0.005);
                done_list.lock().unwrap().push(format!("job done by worker {}", name));
            }
        })
    }).collect();
    for worker in pool { let _ = worker.join(); }
    let done_list = done_list.lock().unwrap();
    println!("twelve jobs, four workers:");
    println!("##! potpourri subset duplicates");
    for line in done_list.iter() { println!("{}", line); }
    println!("####");
    println!("jobs done: {}", done_list.len());
}

/// RETURN: nothing. A download that prints dots while it waits; how many is
///         the network's. 'nothing' makes a line of dots no line.
fn progress(random: &mut Random) {
    println!("connecting to mirror");
    for _ in 0..random.randint(0, 3) {
        println!("{}", ".".repeat(random.randint(1, 8) as usize));
    }
    println!("connected");
    println!("received 1024 bytes");
}

/// RETURN: nothing. A Lisp session at its prompt: two objects, each printed
///         with its address '{...}', drawn anew per run, and each used again.
fn lisp(random: &mut Random) {
    let (table, worker) = random.two_of(0x10_0000_0000, 0x11_0000_0000);
    println!("* (defvar *cache* (make-hash-table))");
    println!("#<HASH-TABLE :TEST EQL :COUNT 0 {{{:X}}}>", table);
    println!("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))");
    println!("#<THREAD \"worker\" RUNNING {{{:X}}}>", worker);
    println!("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))");
    println!("#<THREAD \"worker\" RUNNING {{{:X}}}>", worker);
    println!("* *cache*");
    println!("#<HASH-TABLE :TEST EQL :COUNT 1 {{{:X}}}>", table);
}

/// RETURN: f64, the squared distance between 'p' and 'c'.
fn distance2(p: (f64, f64), c: (f64, f64)) -> f64 { (p.0 - c.0).powi(2) + (p.1 - c.1).powi(2) }

/// RETURN: nothing. Clusters 90 noisy points around three centres and prints
///         the centroids in the order the run found them:
///         '##! point-cloud limit=0.3 pair dist=Linf'.
fn clusters(random: &mut Random) {
    let centre_list = [(1.0, 1.0), (5.0, 4.0), (9.0, 1.0)];
    let mut point_list: Vec<(f64, f64)> = Vec::new();
    for (x, y) in centre_list {
        for _ in 0..30 { point_list.push((x + random.gauss(0.0, 0.3), y + random.gauss(0.0, 0.3))); }
    }
    random.shuffle(&mut point_list);
    //  The start: one point at random, then twice the point farthest from
    //  every start chosen so far -- one start per cluster.
    let mut centroid_list = vec![*random.choice(&point_list)];
    while centroid_list.len() < 3 {
        let nearest = |p: (f64, f64)| centroid_list.iter().map(|c| distance2(p, *c)).fold(f64::INFINITY, f64::min);
        let farthest = point_list.iter().copied()
            .fold(None, |best: Option<(f64, f64)>, p| match best {
                Some(b) if nearest(b) >= nearest(p) => Some(b),
                _ => Some(p),
            }).unwrap();
        centroid_list.push(farthest);
    }
    for _ in 0..10 {
        let mut member_list: Vec<Vec<(f64, f64)>> = vec![Vec::new(); 3];
        for p in &point_list {
            let mut best = 0;
            for i in 1..3 { if distance2(*p, centroid_list[i]) < distance2(*p, centroid_list[best]) { best = i; } }
            member_list[best].push(*p);
        }
        centroid_list = member_list.iter().map(|m| {
            let n = m.len() as f64;
            (m.iter().map(|p| p.0).sum::<f64>() / n, m.iter().map(|p| p.1).sum::<f64>() / n)
        }).collect();
    }
    println!("centroids (x y), in the order found:");
    println!("##! point-cloud limit=0.3 pair dist=Linf");
    for (x, y) in centroid_list { println!("    {:5.2} {:5.2}", x, y); }
    println!("####");
}

const CHOICE_LIST: [(&str, fn(&mut Random)); 9] = [
    ("plain", plain), ("tolerance", tolerance), ("constraints", constraints),
    ("analogies", analogies), ("race", race), ("pool", pool),
    ("progress", progress), ("lisp", lisp), ("clusters", clusters)];

/// RETURN: never; exits 0 once the choice named on the command line ran and
///         '<hwut-end>' was printed; 1 where no such choice is.
fn main() {
    let choice = std::env::args().nth(1).unwrap_or_default();
    match CHOICE_LIST.iter().find(|(name, _)| *name == choice) {
        Some((_, function)) => function(&mut Random::from_clock()),
        None => {
            let name_list: Vec<&str> = CHOICE_LIST.iter().map(|(name, _)| *name).collect();
            println!("choices: {}", name_list.join(", "));
            std::process::exit(1);
        }
    }
    println!("<hwut-end>");
}

// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: THE PRODUCER OF 'protocol.sh clean' -- no test, a helper.
//          Five clients talk to a service at once, each in a thread of its
//          own: 'request <n>', then 'response <n>', each after a pause drawn
//          at random; then 'shutdown'. The order of the lines is the
//          scheduler's; 'protocol.pype' judges it. Built by 'make helpers'
//          ('on_entry' in hwut.conf).
//______________________________________________________________________________
mod clock_random;

use std::io::Write;
use std::sync::{Arc, Mutex};
use std::thread;

use clock_random::Random;

/// RETURN: nothing; 'text' was printed as one line, flushed, under 'lock'.
fn say(lock: &Mutex<()>, text: &str) {
    let _held = lock.lock().unwrap();
    let mut out = std::io::stdout().lock();
    let _ = writeln!(out, "{}", text);
    let _ = out.flush();
}

/// RETURN: nothing; exits 0 once all five clients and the shutdown spoke.
fn main() {
    let lock = Arc::new(Mutex::new(()));
    let pool: Vec<_> = (1..=5).map(|n| {
        let lock = lock.clone();
        thread::spawn(move || {
            let mut random = Random::from_clock();
            random.sleep(0.0, 0.02);
            say(&lock, &format!("request {}", n));
            random.sleep(0.0, 0.02);
            say(&lock, &format!("response {}", n));
        })
    }).collect();
    for client in pool { let _ = client.join(); }
    say(&lock, "shutdown");
}

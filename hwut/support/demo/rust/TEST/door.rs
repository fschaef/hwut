// @hwut {
//     title   = "Demo: a door's state machine, watched by a pype"
//     build   { framework = "make", executable = "%.exe"
//               caps { timeout_sec = 900 } }
//     pype    = "door.pype"
//     choices {
//         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
//         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
//     }
// }
//
//______________________________________________________________________________
// A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
// may do.
//
// The application prints its log as it happens: noise, and a line 'door:
// <event>' for each thing the door does. It prints no '<hwut-end>': the
// header names 'door.pype', which stands between it and the comparison and
// closes the stream at '<eof>'. 'door.pype' is the Python demonstration's,
// unchanged: a pype script is written in pype (Python), whatever language
// the application is -- it fires every event into 'hwut_fsm':
//
//     closed ---( open )---> open ---( close )---> closed
//     closed ---( lock )---> locked ---( unlock )---> closed
//     open   ---( slam )---> jammed          # forbidden
//
// kept     the door does what the model allows; the report shows which
//          transitions were taken and which not, and 'ended in closed'.
// broken   the controller locks an open door, slams it into a jam and tries
//          to unlock it: each surprise is ONE 'BREACH' line, the end outside
//          the final states one more. The GOOD file holds them.
//______________________________________________________________________________

const STORY_LIST: [(&str, &[&str]); 2] = [
    ("broken", &["open", "lock", "slam", "unlock"]),
    ("kept",   &["open", "close", "lock", "unlock", "open", "close"]),
];

/// RETURN: never; exits 0 once the log of the door for the choice named on
///         the command line was printed; 1 where no such choice is.
fn main() {
    let choice = std::env::args().nth(1).unwrap_or_default();
    let Some((_, story)) = STORY_LIST.iter().find(|(name, _)| *name == choice) else {
        println!("error: a choice is required: broken, kept");
        std::process::exit(1);
    };
    println!("controller 2.1 up");
    for (number, event) in story.iter().enumerate() {
        println!("tick {}: sensors read", number + 1);
        println!("door: {}", event);
    }
    println!("controller down");
}

#! /usr/bin/env node
//
// @hwut {
//     title   = "Demo: a door's state machine, watched by a pype"
//     pype    = "door.pype"
//     choices {
//         kept   { features = ["demo-node", "demo-node+cover-fsm-law-kept"] }
//         broken { features = ["demo-node", "demo-node+cover-fsm-law-broken"] }
//     }
// }
//
/*
______________________________________________________________________________
A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
may do.

The application prints its log as it happens: noise, and a line 'door:
<event>' for each thing the door does. It prints no '<hwut-end>': the
header names 'door.pype', which stands between it and the comparison and
closes the stream at '<eof>'.

'door.pype' parses the log and fires every event into a state machine
('hwut_fsm'):

    closed ---( open )---> open ---( close )---> closed
    closed ---( lock )---> locked ---( unlock )---> closed
    open   ---( slam )---> jammed          # forbidden

THE PYPE IS hwut's, IN EVERY LANGUAGE: a pype script's actions are Python,
so 'door.pype' is the Python demo's, unchanged, and fires into the Python
'hwut_fsm' -- 'hwut_fsm.js' in the node support is the same machine for a
node test that holds the model ITSELF. What the application is written in
does not reach the pype: it reads a log.

kept     the door does what the model allows; the report shows which
         transitions were taken and which not, and 'ended in closed'.
broken   the controller locks an open door, slams it into a jam and
         tries to unlock it: each surprise is ONE 'BREACH' line in the
         output, the jam included, and the end outside the final states
         is one more. The GOOD file holds them and a run that stops
         breaching -- or breaches differently -- shows up as a difference.

Both choices pass on every run: what they print does not depend on time.
______________________________________________________________________________
*/
'use strict';

const STORY_DB = {
    kept:   ['open', 'close', 'lock', 'unlock', 'open', 'close'],
    broken: ['open', 'lock', 'slam', 'unlock'],
};

/* RETURN: number, 0 -- the log of the door for 'choice', printed. */
function main(choice) {
    console.log('controller 2.1 up');
    STORY_DB[choice].forEach((event, i) => {
        console.log(`tick ${i + 1}: sensors read`);
        console.log(`door: ${event}`);
    });
    console.log('controller down');
    return 0;
}

const word = process.argv[2];
if (process.argv.length !== 3 || !Object.prototype.hasOwnProperty.call(STORY_DB, word)) {
    console.log(`error: a choice is required: ${Object.keys(STORY_DB).sort().join(', ')}`);
    process.exit(1);
}
process.exitCode = main(word);

#! /usr/bin/env node
//
// @hwut {
//     title     = "Demo: a terminal program's screen, as a person sees it"
//     tolerance { regions    = false
//                 comment    = false
//                 whitespace = false }
//     choices {
//         open   { features = ["demo-node+cover-terminal-screen", "demo-node+cover-screen-as-seen"] }
//         scroll { features = ["demo-node+cover-terminal-screen", "demo-node+cover-screen-as-seen"] }
//     }
// }
//
/*
______________________________________________________________________________
SUBJECT  the screen of 'viewer.js', a full-screen file viewer, run in a
         terminal of 9 rows and 40 columns and driven by its keys.
REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
             as they fit, and a status line -- the keys flush left, the lines
             shown flush right; 'j' and the down key go one line further,
             'k' one back.

hwut_vterm's 'Terminal' (the node port, libvterm through koffi) runs the
viewer on a pseudo-terminal: the viewer cannot tell it from a real one.
The test PRESSES KEYS and is told what CHANGED: three regions are declared
-- title, body, status -- and after every key, once the viewer has gone
quiet, each region whose text changed is printed. A redraw that changes
nothing is not told: the title is told once.

THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
off, in the header:

    regions = false     the file shown is a GOOD file of hwut, with a
                        '##! potpourri' ... '####' block. On this screen
                        those are characters, not a region to open.
    comment = false     '## ...' lines are characters too, not notes.
    whitespace = false  the status line's two halves stand flush left and
                        flush right: every blank between them counts. A
                        half moved by one column is red. (A line's leading
                        and trailing blanks are stripped all the same.)

libvterm must be installed ('apt install libvterm0'), and koffi ('npm
install' in the node support's directory); where either is not, the test
prints why and probes nothing -- its output differs from GOOD and the
reason stands in the difference.

CHOICES  open    the viewer opened, then quit.
         scroll  down, down, 'j', then 'k': three lines on, one back.
______________________________________________________________________________
*/
'use strict';
const fs   = require('fs');
const path = require('path');

const support = require('./hwut_support.js');
const { Terminal, LibraryMissing } = support('hwut_vterm');

const SAMPLE = [
    '## demo.py race -- three workers',
    'start',
    '##! potpourri',
    'worker B done: 5 jobs',
    'worker A done: 3 jobs',
    'worker C done: 2 jobs',
    '####',
    'all joined',
    '## the order between the markers is',
    '## free; the lines are not.',
    ''].join('\n');

/* RETURN: undefined. Prints one region that changed, its rows as they
 *         stand on the screen, from the first column. */
function show(name, lineList) {
    console.log(`-- ${name}`);
    for (const line of lineList) console.log(line);
}

/* RETURN: undefined. Runs the viewer on the sample, presses 'keyList',
 *         quits, and prints what changed after each step. */
function view(keyList) {
    const file = path.join(__dirname, 'TMP', 'race.txt');
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, SAMPLE);
    new Terminal(9, 40).use(terminal => {
        terminal.region('title',  0);
        terminal.region('body',   1, 7);
        terminal.region('status', -1);
        terminal.on_change(show);
        console.log('> viewer.js race.txt');
        terminal.run([process.execPath, path.join(__dirname, 'viewer.js'), file]);
        const cell = terminal.cell(0, 1);
        console.log(`title bar: ${cell.attribute_text() || 'plain'}`);
        for (const key of keyList) {
            console.log(`> ${key}`);
            if (key.length === 1) terminal.send(key);
            else                  terminal.press(key);
        }
        terminal.send('q');
        console.log(`> q -- exit status ${terminal.wait()}`);
    });
}

const CHOICE_DB = { open: [], scroll: ['down', 'down', 'j', 'k'] };

const word = process.argv[2] || '';
if (!Object.prototype.hasOwnProperty.call(CHOICE_DB, word)) {
    console.log(`choices: ${Object.keys(CHOICE_DB).join(', ')}`);
    process.exit(1);
}
try {
    view(CHOICE_DB[word]);
} catch (error) {
    if (!(error instanceof LibraryMissing)) throw error;
    console.log(error.message);
    process.exit(1);
}
console.log('<hwut-end>');

#! /usr/bin/env node
//
// @hwut {
//     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
//     pype    = "build.pypes"
//     same    = true
//     choices = ["serial", "parallel"]
//     features = ["demo-node+cover-pype-in-header", "demo-node+cover-pype-system", "demo-node+cover-same-nominal", "demo-node+cover-choices-as-list",
//                 "demo-node+cover-pype-push-pop", "demo-node+cover-pype-entry-exit", "demo-node+cover-pype-import", "demo-node+cover-pype-repeat-group",
//                 "demo-node+cover-pype-quantity", "demo-node+cover-pype-anchors-globs-flush"]
//     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
// }
//
/*
______________________________________________________________________________
SUBJECT  the log of a recursive build -- configure, then the directories
         'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
         a pype system makes of it.
REQUIREMENT  A parallel build builds what the serial build builds: the same
             sources, the same warnings, the same archives and the same
             program, linked from the same parts.

The application only REPORTS the build as it happens, as 'make -w' would.
The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
between it and the comparison (hwut runs it; the application prints no
'<hwut-end>'):

    build.pypes       --> normalise.pype         stdin to the first
                      normalise.pype --> build.pype
    normalise.pype    a parallel build tags each line with its job,
                      'job2: cc -c ...'; the tag goes, every other line
                      passes unchanged ('flush')
    build.pype        the summary, sorted -- see its own comments: modes
                      pushed on 'Entering directory' and popped on
                      'Leaving' (nested: 'app/plugins' inside 'app'),
                      '<entry>'/'<exit>' around each, a vocabulary
                      imported from 'compiler.pype', a repeat group over
                      the parts of a link, durations read as quantities

'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.js.txt'. Serial or
parallel, the summary must be the same -- that is the requirement, and
the header says it once. 'choices' is a list: no choice states anything
of its own.

The laws: the compile times sum to under 5 s ('((compile: ...))', in
s, whatever unit the log used), and nothing in the log broke the build's
grammar ('((breaches: 0))').

A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
build here; a pype that judges time is fed live ('protocol.sh slow').

'parallel' in node: the two jobs are coroutines on one event loop, each
waiting out its compile times; which finishes first is the timers'.
______________________________________________________________________________
*/
'use strict';

//  What each directory does: its sources, warnings and products.
const DIRECTORY_DB = {
    'lib':         { source_list: ['lib/str.c', 'lib/num.c', 'lib/map.c'],
                     warning_db:  { 'lib/num.c': "lib/num.c:14:9: warning: unused variable 'n'" },
                     product:     'ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o' },
    'app/plugins': { source_list: ['app/plugins/png.c', 'app/plugins/svg.c'],
                     warning_db:  { 'app/plugins/svg.c': "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'" },
                     product:     'ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o' },
    'app':         { source_list: ['app/main.c', 'app/cli.c'],
                     warning_db:  {},
                     product:     'ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a' },
};

const say   = text => console.log(text);
/* RETURN: Promise, resolved after 'seconds'. */
const sleep = seconds => new Promise(resolve => setTimeout(resolve, seconds * 1000));

/* RETURN: Promise of array of strings, what building directory 'name'
 *         prints, its sources compiled in the time each takes. */
async function compileLines(name) {
    const spec = DIRECTORY_DB[name], lineList = [];
    for (const source of spec.source_list) {
        const took = 0.04 + 0.08 * Math.random();
        await sleep(took);
        const spent = took < 0.1 ? `${Math.trunc(took * 1000)} ms` : `${took.toFixed(2)} s`;
        lineList.push(`cc -c ${source} -o ${source.slice(0, -2)}.o (took ${spent})`);
        if (source in spec.warning_db) lineList.push(spec.warning_db[source]);
    }
    return lineList;
}

/* RETURN: Promise of array of strings, the block 'make -w' prints for
 *         'name' at 'level', the block of 'inner' nested before the
 *         product. */
async function directoryBlock(name, level, inner = null) {
    let lineList = [`make[${level}]: Entering directory '${name}'`];
    lineList = lineList.concat(await compileLines(name));
    if (inner) lineList = lineList.concat(await directoryBlock(inner, level + 1));
    lineList.push(DIRECTORY_DB[name].product);
    lineList.push(`make[${level}]: Leaving directory '${name}'`);
    return lineList;
}

/* RETURN: undefined. Prints what 'configure' prints, and that make enters
 *         the top directory. */
function configure() {
    say('configure: checking for cc... cc');
    say('configure: checking for ar... ar');
    say("make: Entering directory 'demo'");
}

/* RETURN: Promise of undefined. Builds one directory after the other. */
async function serial() {
    configure();
    for (const line of (await directoryBlock('lib', 1)).concat(await directoryBlock('app', 1, 'app/plugins')))
        say(line);
    say("make: Leaving directory 'demo'");
}

/* RETURN: Promise of undefined. Builds 'lib' and 'app' at once. Each job
 *         prints its block whole when done ('make -O'), every line tagged
 *         with the job; which job finishes first is the timers'. */
async function parallel() {
    configure();
    const job = async (slot, name, inner = null) => {
        for (const line of await directoryBlock(name, 1, inner)) say(`job${slot}: ${line}`);
    };
    await Promise.all([job(1, 'lib'), job(2, 'app', 'app/plugins')]);
    say("make: Leaving directory 'demo'");
}

const CHOICE_DB = { serial, parallel };

const word = process.argv[2] || '';
if (!Object.prototype.hasOwnProperty.call(CHOICE_DB, word)) {
    say(`choices: ${Object.keys(CHOICE_DB).join(', ')}`);
    process.exit(1);
}
CHOICE_DB[word]();

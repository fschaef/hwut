// @hwut {
//     title      = "hwut_fsm: a state machine as the test's model of the system"
//     choices {
//         dfa       { features = ["node-fsm"] }
//         forbidden { features = ["node-fsm"] }
//         masks     { features = ["node-fsm"] }
//         model     { features = ["node-fsm"] }
//         nfa       { features = ["node-fsm"] }
//         refused   { features = ["node-fsm"] }
//         report    { features = ["node-fsm"] }
//         syntax    { features = ["node-fsm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-hwut_fsm.py', choice for choice,
//          held against its GOOD files by '.link'.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const { HwutRunner }        = require(path.join(__dirname, '..', 'hwut_runner.js'));
const { Machine, FsmError } = require(path.join(__dirname, '..', 'hwut_fsm.js'));
const { boolText, tupleRepr, strRepr } = require(path.join(__dirname, '..', 'pytext.js'));

//  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
//  a fault while busy crashes it -- which must never happen.
const PROTOCOL = `
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
`;

const say    = text => console.log(text);
const banner = label => say(`\n--- ${label} ---`);
/* RETURN: string, a path as Python prints the tuple 'path_to' returns, or 'None'. */
const pathText = p => p === null ? 'None' : tupleRepr(p, true);

/* RETURN: undefined; 'f()' ran, an FsmError it threw printed as Python's test prints it. */
function printingFsmError(f) {
    try { f(); }
    catch (error) {
        if (!(error instanceof FsmError)) throw error;
        say(`FsmError: ${error.message}`);
    }
}

function runSyntax() {
    banner('the protocol, written back');
    say(Machine.from_string(PROTOCOL).to_string());
    banner("the author's form: 'state', a chain, ':', blanks around '-->'");
    say(Machine.from_string(`
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    `).to_string());
}

function runRefused() {
    for (const text of ['A ---( x )---> B\n: ---( x )---> C',
                        'A ---(  )---> B',
                        ': ---( x )---> B',
                        'A B ---( x )---> C',
                        'initial: A, B\nA ---( x )---> B',
                        'forbidden: Q\nA ---( x )---> B',
                        '# nothing but a comment']) {
        banner(text.replace(/\n/g, ' | '));
        printingFsmError(() => { Machine.from_string(text); say('accepted'); });
    }
}

function runDfa() {
    const m = Machine.from_string(PROTOCOL);
    ['request', 'release', 'grant', 'release', 'jump', 'request'].forEach((event, i) => {
        const moved = m.fire(event, i + 1);
        say(`    ${event.padEnd(8)} -> ${boolText(moved).padEnd(5)} now ${m.state.padEnd(8)} allowed: ${m.allowed().join(', ')}`);
    });
    banner('questions where it stands');
    say(`can('grant')   ${boolText(m.can('grant'))}`);
    say(`can('release') ${boolText(m.can('release'))}`);
    say(`in_state('waiting') ${boolText(m.in_state('waiting'))}`);
    say(`trace: ${m.trace().map(([w, , e, t]) => `${w}:${e}>${t}`).join(' ')}`);
}

function runNfa() {
    const m = Machine.from_string(`
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    `, { DFA: false });
    for (const event of ['x', 'z', 'y']) {
        m.fire(event, `t=${event}`);
        say(`    after ${event}: ${[...m.current()].sort().join(', ')}`);
    }
    banner("'state' asked of a set");
    m.reset(); m.fire('x');
    printingFsmError(() => say(m.state));
}

function runForbidden() {
    const m = Machine.from_string(PROTOCOL);
    ['request', 'grant', 'fault'].forEach((event, i) => {
        say(`    ${event.padEnd(8)} -> ${boolText(m.fire(event, i + 1))}`);
    });
    say(`now in ${m.state} -- breaches: ${m.breach_n}`);
}

function runModel() {
    const m = Machine.from_string(PROTOCOL + '\n    state limbo\n    limbo ---( kick )---> idle\n');
    say(`check: ${m.check()}`);
    banner('path_to');
    for (const state of ['busy', 'crashed', 'limbo', 'idle'])
        say(`    ${state.padEnd(8)} ${pathText(m.path_to(state))}`);
    m.fire('request');
    say(`    busy from now: ${pathText(m.path_to('busy', 'now'))}`);
    say(`    state_reachable('idle', start='now'): ${boolText(m.state_reachable('idle', 'now'))}`);
}

function runReport() {
    const m = Machine.from_string(PROTOCOL, { name: 'protocol' });
    for (const event of ['request', 'grant', 'release', 'request', 'grant']) m.fire(event);
    say(`report returns ${m.report()}`);
}

function runMasks() {
    const m = Machine.from_string(PROTOCOL);
    banner("'grant' disallowed in every state, since line 2");
    m.disallow('grant', null, 2);
    m.fire('request', 3);
    say(`    allowed now: ${m.allowed().join(', ')} -- can('grant'): ${boolText(m.can('grant'))}`);
    m.fire('grant', 4);
    say(`    path_to('busy'):               ${pathText(m.path_to('busy'))}`);
    say(`    path_to('busy', masked=False): ${pathText(m.path_to('busy', null, false))}`);
    say(`    check(): ${m.check()}`);
    say(`    check(masked=False): ${m.check(false)}`);
    banner("allowed again; 'busy' forbidden while standing in it");
    m.allow('grant', null, 5);
    m.fire('grant', 6);
    m.forbid('busy', 7);
    m.fire('release', 8);
    m.fire('request', 9);
    m.fire('grant', 10);
    banner("permitted: 'busy', and the model's own 'crashed'");
    m.permit('busy', 11);
    m.permit('crashed', 12);
    say(`    fault -> ${boolText(m.fire('fault', 13))} -- now in ${m.state}`);
    banner("a phase: 'release' disallowed in 'busy' for a block");
    m.reset();
    m.fire('request'); m.fire('grant');
    m.disallowed('release', 'busy', 'phase').run(() => { m.fire('release', 20); });
    m.fire('release', 21);
    m.disallow('cancel', null, 22);
    m.report();
    banner('refused: a word the model never names');
    for (const call of [() => m.disallow('jump'), () => m.forbid('limbo'),
                        () => m.allow('grant', 'nowhere')])
        printingFsmError(call);
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      "hwut_fsm: a state machine as the test's model of the system",
    choice_map: {
        syntax:    runSyntax,
        refused:   runRefused,
        dfa:       runDfa,
        nfa:       runNfa,
        forbidden: runForbidden,
        model:     runModel,
        report:    runReport,
        masks:     runMasks,
    },
}).run();

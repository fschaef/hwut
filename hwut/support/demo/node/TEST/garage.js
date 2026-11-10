#! /usr/bin/env node
//
// @hwut {
//     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
//     interactive = true
//     choices {
//         space       { features = ["demo-node+cover-space-from-hocon", "demo-node+cover-space-iterator", "demo-node+cover-hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         random      { features = ["demo-node+cover-deterministic-stream", "demo-node+cover-hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         race-naive  { features = ["demo-node+cover-deterministic-timeline", "demo-node+cover-space-iterator", "demo-node+cover-hwut-runner"]
//                       tolerance { constraints = ["overbooked > 0"] } }
//         race-atomic { features = ["demo-node+cover-deterministic-timeline", "demo-node+cover-space-iterator", "demo-node+cover-hwut-runner"]
//                       tolerance { constraints = ["overbooked == 0"] } }
//     }
// }
//
/*
______________________________________________________________________________
SUBJECT  the counter of free spaces at a garage's gates: which cars it
         admits, which it refuses, and how many stand inside.
REQUIREMENT  The garage admits a car only while a space is free, lets a car
             out only while one stands inside, and never holds more cars
             than it has spaces -- also when two gates admit at once.

No choice writes its cases out by hand. Each GENERATES them, with one of
hwut's helpers for writing tests -- the node port of the Python support
(support/test_writing/node), found through 'hwut_support.js':

space        'garage-space.hocon' states the tested space -- capacities,
             cars arriving, cars leaving -- in hwut's HOCON, read by
             'hwut_hocon'. A reviewer edits the space without reading
             JavaScript. 'space_iterator.do' walks every combination: 3 x 5
             x 4 = 60 cases. Each is printed as one cell of a matrix, and
             checked against the model: admitted = min(arriving,
             capacity), out = min(leaving, admitted).

random       'DeterministicStream(4711)' draws 1000 cars arriving and
             leaving at a garage of 5. The draw is the same on every
             machine and in every language hwut supports -- the stream is
             a linear congruential generator, not 'Math.random' -- so the
             GOOD is exact (the Python demo's, by '.link'), and a failing
             run can be replayed by its seed.

race-naive   two gates, one free space. A gate CHECKS whether a space is
             free, and later ADMITS its car. 'deterministic_timeline'
             runs the two gates as Triggers on timelines drawn as
             strings -- '1 1 ' fires at tick 0 and tick 2 -- so every
             interleaving is played exactly, not hoped for with sleeps.
             'space_iterator' generates all six interleavings of two
             two-step gates in four ticks. Where both gates check before
             either admits, both admit: the garage is overbooked. The law
             is 'overbooked > 0': the GOOD is the accepted violation
             report.

race-atomic  the same six interleavings, the gate checking and admitting
             in ONE step (one event loop: no other gate runs in between).
             'overbooked == 0'.

THE FRONT END is hwut's HwutRunner: the choice map below is the whole
command line, '--hwut-info' included. The header says
'interactive = true': hwut starts the application ONCE and asks for the
choices one after another -- an accelerator only: a choice's output equals
what it prints when run alone (node's runner runs each in a child).
______________________________________________________________________________
*/
'use strict';
const fs   = require('fs');
const path = require('path');

const support        = require('./hwut_support.js');
const spaceIterator  = support('space_iterator');
const hwutHocon      = support('hwut_hocon');
const { DeterministicStream }        = support('deterministic_random');
const { Trigger, TriggerDispatcher } = support('deterministic_timeline');
const { HwutRunner } = support('hwut_runner');
const { listRepr }   = support('pytext');

const say = text => console.log(text);

class Garage {
    /* RETURN: Garage, empty, of 'capacity' spaces -- the unit under test. */
    constructor(capacity) {
        this.capacity = capacity;
        this.occupied = 0;
    }

    /* RETURN: number, the spaces free now -- negative where the garage is
     *         overbooked. */
    free() { return this.capacity - this.occupied; }

    /* RETURN: true, a car was admitted, if a space was free;
     *         false, else (the car is refused). */
    arrive() {
        if (this.free() <= 0) return false;
        this.occupied += 1;
        return true;
    }

    /* RETURN: true, a car drove out, if one stood inside;
     *         false, else. */
    leave() {
        if (this.occupied === 0) return false;
        this.occupied -= 1;
        return true;
    }
}

// _____________________________________________________________________________
// space -- the tested space from HOCON, walked by space_iterator
//
/* RETURN: array of [string, array], the dimensions of the space in 'file',
 *         in the order written: [name, values]. Every fault the HOCON
 *         reader found is printed with '!!' first. */
function readSpace(file) {
    let textList = fs.readFileSync(file, 'utf8').split('\n');
    if (textList.length && textList[textList.length - 1] === '') textList.pop();
    const lineList = textList.map((text, i) => new hwutHocon.SourceLine(text, i + 1, 0));
    const [document, faultList] = hwutHocon.parse(lineList, path.basename(file));
    for (const fault of faultList) say(`!! ${fault}`);
    const space = document.get('space').node;
    return space.entry_list.map(e => [e.key, e.node.item_list.map(item => item.value)]);
}

/* RETURN: undefined. Prints every case of the space as a matrix cell. */
function space() {
    const dimensionList = readSpace(path.join(__dirname, 'garage-space.hocon'));
    const valueList     = dimensionList.map(([, values]) => values);
    say(`space: ${dimensionList.map(([n, v]) => `${n} ${listRepr(v)}`).join('  x  ')}`);
    say("cell: cars inside / cars refused at the gate ('!!' differs from the model)");
    let mismatchN = 0;
    const rowDb = new Map();
    for (const [capacity, arriving, leaving] of spaceIterator.do(valueList)) {
        const garage = new Garage(capacity);
        let refused = 0;
        for (let i = 0; i < arriving; i += 1) if (!garage.arrive()) refused += 1;
        for (let i = 0; i < leaving; i += 1) garage.leave();
        const admitted = Math.min(arriving, capacity);
        const expected = [admitted - Math.min(leaving, admitted), arriving - admitted];
        const got      = [garage.occupied, refused];
        const sameF    = got[0] === expected[0] && got[1] === expected[1];
        mismatchN += sameF ? 0 : 1;
        const key = `${capacity},${arriving}`;
        if (!rowDb.has(key)) rowDb.set(key, []);
        rowDb.get(key).push(`${got[0]}/${got[1]}${sameF ? '  ' : '!!'}`);
    }
    for (const capacity of valueList[0]) {
        say(`capacity ${capacity}   ${valueList[2].map(l => `leave ${String(l).padEnd(3)}`).join('  ')}`.trimEnd());
        for (const arriving of valueList[1])
            say(`  arrive ${arriving}   ${rowDb.get(`${capacity},${arriving}`).map(c => c.padEnd(9)).join('  ')}`.trimEnd());
    }
    say(`cases ${rowDb.size * valueList[2].length}, differing from the model ((mismatches: ${mismatchN}))`);
}

// _____________________________________________________________________________
// random -- a deterministic stream of arrivals and departures
//
/* RETURN: undefined. Prints the summary of 1000 drawn cars, model-checked. */
function randomStream() {
    const stream = new DeterministicStream(4711);
    const garage = new Garage(5);
    let model = 0, mismatchN = 0, strip = '';
    const count = { arrive: 0, refused: 0, leave: 0, empty: 0 };
    const histogram = new Array(6).fill(0);
    for (let i = 0; i < 1000; i += 1) {
        if (stream.coin(0.55)) {
            count.arrive += 1;
            if (!garage.arrive()) count.refused += 1;
            model = Math.min(5, model + 1);
            strip += '+';
        } else {
            count.leave += 1;
            if (!garage.leave()) count.empty += 1;
            model = Math.max(0, model - 1);
            strip += '-';
        }
        mismatchN += garage.occupied !== model ? 1 : 0;
        histogram[garage.occupied] += 1;
    }
    say("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves");
    say(`first 60: ${strip.slice(0, 60)}`);
    say(`arrivals ${count.arrive}, refused ${count.refused}; departures ${count.leave}, from an empty garage ${count.empty}`);
    say('cars inside after each event:');
    histogram.forEach((n, inside) => say(`    ${inside}  ${String(n).padStart(4)}  ${'#'.repeat(Math.floor(n / 10))}`));
    say(`steps differing from the model ((mismatches: ${mismatchN}))`);
}

// _____________________________________________________________________________
// race -- two gates on drawn timelines
//
class Gate extends Trigger {
    /* RETURN: Gate, a gate on 'timeline': its first tick checks, its second
     *         admits; what it does goes to 'log'. */
    constructor(name, timeline, garage, atomic, log) {
        super(timeline, name);
        this.garage = garage; this.atomic = atomic; this.log = log;
        this.step = 0;
        this.saw_free = false;
    }

    /* RETURN: Promise of undefined. Performs the gate's next step at
     *         'pseudo_time'. */
    async fire(pseudo_time) {
        if (this.step === 0 && this.atomic) {
            this.saw_free = this.garage.arrive();
            this.log(this.saw_free ? `${this.name} checks+admits` : `${this.name} refuses`);
        } else if (this.step === 0) {
            this.saw_free = this.garage.free() > 0;
            this.log(`${this.name} sees ${this.garage.free()} free`);
        } else if (this.atomic) {
            this.log(this.saw_free ? `${this.name} opens` : `${this.name} stays shut`);
        } else if (this.saw_free) {
            this.garage.occupied += 1;                    // the naive admit
            this.log(`${this.name} admits`);
        } else {
            this.log(`${this.name} refuses`);
        }
        this.step += 1;
    }
}

/* RETURN: array of [string, string], every pair of timelines in four ticks
 *         in which each of two gates fires twice, never at the same tick:
 *         gate A's and gate B's. */
function interleavingList() {
    const result = [], tick = [0, 1, 2, 3];
    const line = (x, y) => tick.map(t => (t === x || t === y) ? '1' : ' ').join('');
    for (const [a1, a2, b1, b2] of spaceIterator.do([tick, tick, tick, tick]))
        if (a1 < a2 && b1 < b2 && new Set([a1, a2, b1, b2]).size === 4)
            result.push([line(a1, a2), line(b1, b2)]);
    return result;
}

/* RETURN: Promise of undefined. Plays every interleaving of two gates at
 *         one space. */
async function race(atomic) {
    say('one free space, two gates, one car at each; timelines: a digit fires');
    say('    gate A  gate B  what happens                                    inside');
    let overbookedN = 0;
    for (const [timelineA, timelineB] of interleavingList()) {
        const garage = new Garage(1), eventList = [];
        const log = text => eventList.push(text);
        await new TriggerDispatcher([new Gate('A', timelineA, garage, atomic, log),
                                     new Gate('B', timelineB, garage, atomic, log)]).run();
        const overF = garage.occupied > garage.capacity;
        overbookedN += overF ? 1 : 0;
        say(`    "${timelineA}"  "${timelineB}"  ${eventList.join(', ').padEnd(46)}  ${garage.occupied} ${overF ? '!!' : '  '}`.trimEnd());
    }
    say(`interleavings overbooking the garage ((overbooked: ${overbookedN})) of ${interleavingList().length}`);
}

/* RETURN: Promise of undefined. The gates check, then admit, in two steps. */
const raceNaive  = () => race(false);
/* RETURN: Promise of undefined. The gates check and admit in one step. */
const raceAtomic = () => race(true);

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      "Demo: a garage's space counter -- a space, a stream and races, generated;",
    choice_map: { 'space':       space,
                  'random':      randomStream,
                  'race-naive':  raceNaive,
                  'race-atomic': raceAtomic },
}).run();

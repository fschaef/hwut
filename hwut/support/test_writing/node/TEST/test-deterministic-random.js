// @hwut {
//     title      = "DeterministicStream RNG and SelectionMarker spread"
//     choices {
//         gauss      { features = ["node-random"] }
//         primitives { features = ["node-random"] }
//         ranges     { features = ["node-random"] }
//         sample     { features = ["node-random"] }
//         seed_sweep { features = ["node-random"] }
//         select     { features = ["node-random"] }
//         unchosen   { features = ["node-random"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-deterministic-random.py', choice
//          for choice. Its GOOD files are the Python test's, by '.link': the
//          two modules owe the same stream, byte for byte.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
const { DeterministicStream, SelectionMarker } = require(path.join(__dirname, '..', 'deterministic_random.js'));
const { floatRepr, listRepr } = require(path.join(__dirname, '..', 'pytext.js'));

const SEED = 0x42;

//  THE ONE PLACE THE LIBM PATH IS TOLERATED, as in the Python test.
const TOLERANCE_REGION_BEGIN = '##! table numeric={1:1e-12}';
const REGION_END             = '####';

const say    = text => console.log(text);
const banner = label => say(`\n--- ${label} ---`);
const stream = () => new DeterministicStream(SEED);
const pad2   = i => String(i).padStart(2, '0');
const times  = (n, f) => Array.from({ length: n }, (_, i) => f(i));

function runPrimitives() {
    banner('next_int(0, 1000000) -- first 20');
    let s = stream();
    for (let i = 0; i < 20; i += 1) say(`[${pad2(i)}] ${s.next_int(0, 1000000)}`);

    banner('next_float -- first 10 (full precision)');
    s = stream();
    for (let i = 0; i < 10; i += 1) say(`[${pad2(i)}] ${floatRepr(s.next_float())}`);

    banner('coin(0.5) -- 40 draws');
    s = stream();
    say(times(40, () => s.coin(0.5) ? 'T' : 'F').join(' '));
}

function runRanges() {
    banner('next_int(0, 9) -- 30 draws');
    let s = stream();
    say(times(30, () => s.next_int(0, 9)).join(' '));

    banner('next_int(5, 5) -- degenerate range returns the bound');
    s = stream();
    say(times(5, () => s.next_int(5, 5)).join(' '));

    banner('next_int(-3, 3) -- spanning zero');
    s = stream();
    say(times(20, () => { const v = s.next_int(-3, 3); return (v >= 0 ? '+' : '') + v; }).join(' '));
}

function runGauss() {
    banner('gauss(0, 1) -- 10 draws (full precision)');
    let s = stream();
    say(TOLERANCE_REGION_BEGIN);
    for (let i = 0; i < 10; i += 1) say(`[${pad2(i)}] ${floatRepr(s.gauss(0.0, 1.0))}`);
    say(REGION_END);

    banner('gauss(0, 1) clamped to [-1, 1]');
    s = stream();
    say(TOLERANCE_REGION_BEGIN);
    for (let i = 0; i < 10; i += 1) say(`[${pad2(i)}] ${floatRepr(s.gauss(0.0, 1.0, -1.0, 1.0))}`);
    say(REGION_END);

    banner('gauss_int(100, 15) -- 20 draws');
    s = stream();
    say(times(20, () => s.gauss_int(100.0, 15.0)).join(' '));
}

function runSample() {
    banner('sample_indices(10, 10) -- full permutation');
    let s = stream();
    say(listRepr(s.sample_indices(10, 10)));

    banner('sample_indices(20, 5) -- partial draw');
    s = stream();
    say(listRepr(s.sample_indices(20, 5)));

    banner('choice from a list -- 20 draws');
    s = stream();
    const pool = ['alpha', 'beta', 'gamma', 'delta', 'epsilon'];
    say(times(20, () => s.choice(pool)).join(' '));

    banner('sample(list, 4) -- unique elements');
    s = stream();
    say(listRepr(s.sample('ABCDEFGH'.split(''), 4), true));
}

function runSelect() {
    banner('select over a list -- 20 draws');
    let s = stream();
    const pool = ['a', 'b', 'c', 'd'];
    say(times(20, () => s.select(pool)).join(' '));

    banner('select over a tuple -- 12 draws');
    s = stream();
    const branch = Object.freeze(['p', 'q', 'r']);
    say(times(12, () => s.select(branch)).join(' '));
}

function runUnchosen() {
    banner('stable pool -- three full cycles of 4 elements');
    let s = stream();
    let pool = ['a', 'b', 'c', 'd'];
    let m = new SelectionMarker();
    say(times(12, () => s.select_unchosen(pool, m)).join(' '));

    banner('FRESH container each call -- identical to the stable pool above');
    s = stream();
    m = new SelectionMarker();
    say(times(12, () => s.select_unchosen(['a', 'b', 'c', 'd'], m)).join(' '));

    banner('sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]');
    s = stream();
    m = new SelectionMarker();
    const full = ['a', 'b', 'c', 'd'];
    const sub  = ['a', 'b'];
    const first = s.select_unchosen(sub, m);
    const rest  = times(3, () => s.select_unchosen(full, m));
    say(`first(from sub): ${first}  then(from full): ${rest.join(' ')}`);

    banner('reset() restarts the cycle');
    s = stream();
    pool = ['a', 'b', 'c', 'd'];
    m = new SelectionMarker();
    const before = times(4, () => s.select_unchosen(pool, m));
    m.reset();
    const after  = times(4, () => s.select_unchosen(pool, m));
    say(`before reset: ${before.join(' ')}`);
    say(`after  reset: ${after.join(' ')}`);
}

function runSeedSweep() {
    banner('first next_int(0, 1000000) per seed 0..15');
    for (let seed = 0; seed < 16; seed += 1) {
        const s = new DeterministicStream(seed);
        say(`seed=${String(seed).padStart(2)} -> ${s.next_int(0, 1000000)}`);
    }
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      'DeterministicStream RNG and SelectionMarker spread',
    choice_map: {
        primitives: runPrimitives,
        ranges:     runRanges,
        gauss:      runGauss,
        sample:     runSample,
        select:     runSelect,
        unchosen:   runUnchosen,
        seed_sweep: runSeedSweep,
    },
}).run();

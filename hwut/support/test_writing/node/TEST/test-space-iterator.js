// @hwut {
//     title      = "space_iterator: every combination of a parameter basis"
//     choices {
//         product { features = ["node-space"] }
//         edges   { features = ["node-space"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-space-iterator.py', held against
//          its GOOD files by '.link'.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const { HwutRunner }  = require(path.join(__dirname, '..', 'hwut_runner.js'));
const spaceIterator   = require(path.join(__dirname, '..', 'space_iterator.js'));

/* RETURN: undefined. Section heading. */
function banner(label) { console.log(`\n--- ${label} ---`); }

/* RETURN: undefined. Every point of 'basis', one per line, then the count. */
function points(basis) {
    let n = 0;
    for (const point of spaceIterator.do(basis)) {
        console.log(`  (${point.join(', ')})`);
        n += 1;
    }
    console.log(`  ${n} point(s)`);
}

function runProduct() {
    banner('[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points');
    points([[0, 2, 4], ['otto', 'heinz'], [1, 2]]);
}

function runEdges() {
    banner('an EMPTY basis -- one point, the empty one');
    points([]);
    banner('a basis with an EMPTY dimension -- nothing');
    points([[1, 2], [], [3]]);
    banner('ONE dimension -- its values one by one');
    points([['a', 'b', 'c']]);
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      'space_iterator: every combination of a parameter basis',
    choice_map: { product: runProduct, edges: runEdges },
}).run();

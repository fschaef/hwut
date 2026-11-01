// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
//          'python/space_iterator.py'. A generator of the cartesian product,
//          the RIGHTMOST dimension changing fastest:
//
//     const spaceIterator = require(path.join(__dirname, '..', 'space_iterator.js'));
//     for (const [x, name, number] of spaceIterator.do([[0, 2], ['otto'], [1, 2]])) ...
//
// An empty basis yields exactly one point, '[]'; a basis with an empty
// dimension yields nothing.
//_____________________________________________________________________________
'use strict';

/* RETURN: generator of arrays, each one element of every dimension of
 *         'basis' (an array of iterables), in basis order -- the cartesian
 *         product, rightmost dimension fastest; one empty array for an empty
 *         basis; nothing where a dimension is empty. */
function* product(basis) {
    if (basis.length === 0) { yield []; return; }
    const pool = basis.map(dim => Array.from(dim));
    if (pool.some(dim => dim.length === 0)) return;
    const index = pool.map(() => 0);
    while (true) {
        yield index.map((i, d) => pool[d][i]);
        let d = pool.length - 1;
        while (d >= 0 && ++index[d] === pool[d].length) { index[d] = 0; d -= 1; }
        if (d < 0) return;
    }
}

module.exports = { do: product, product };

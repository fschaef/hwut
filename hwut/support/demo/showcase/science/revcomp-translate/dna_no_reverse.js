// dna_no_reverse.js -- the bug: 'reverse complement' that only complements.
// The result is the OTHER strand read 3'->5'; every minus-strand frame built
// on it is wrong, and revcomp(revcomp(s)) == s still holds.
'use strict';
const dna = require('./dna');
module.exports = { ...dna, revcomp: s => dna.complement(s) };

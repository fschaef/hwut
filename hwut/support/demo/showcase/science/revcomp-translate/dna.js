// dna.js -- reverse complement and codon translation.
// Genetic codes in NCBI order: first base T C A G (16 codons each), second
// base T C A G (4 each), third base T C A G. '*' is a stop.
'use strict';
const BASES = 'TCAG';
const TABLE = {
    1: 'FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG',  // standard
    2: 'FFLLSSSSYY**CCWWLLLLPPPPHHQQRRRRIIMMTTTTNNKKSS**VVVVAAAADDEEGGGG',  // vertebrate mitochondrial
};
const PAIR = { A: 'T', T: 'A', C: 'G', G: 'C', N: 'N' };

function complement(s) { return s.split('').map(b => PAIR[b]).join(''); }
function revcomp(s)    { return complement(s).split('').reverse().join(''); }

function aminoAcid(codon, table) {
    const i = BASES.indexOf(codon[0]) * 16 + BASES.indexOf(codon[1]) * 4 + BASES.indexOf(codon[2]);
    return i >= 0 && codon.length === 3 && !/[^TCAG]/.test(codon) ? TABLE[table][i] : 'X';
}

// translate(s, table = 1): codon by codon from s[0]; a trailing partial codon is dropped.
function translate(s, table = 1) {
    let protein = '';
    for (let i = 0; i + 3 <= s.length; i += 3) protein += aminoAcid(s.slice(i, i + 3), table);
    return protein;
}

module.exports = { BASES, TABLE, complement, revcomp, translate, aminoAcid };

#! /usr/bin/env node
// @hwut {
//     title    = "Reverse complement and the six reading frames, standard genetic code"
//     choices {
//         standard   { features = ["six-frames", "standard-code", "antiparallel", "involution"]
//                      tolerance { constraints = ["codon_diffs == 0", "internal_stops == 0", "unpaired == 0",
//                                                    "roundtrip_errors == 0", "antiparallel_errors == 0"] } }
//         no-reverse { features = ["six-frames", "involution-blind", "breach-shown"]
//                      tolerance { constraints = ["unpaired > 0", "roundtrip_errors == 0", "antiparallel_errors > 0"] } }
//         mito-table { features = ["six-frames", "breach-shown"]
//                      tolerance { constraints = ["codon_diffs > 0", "internal_stops > 0"] } }
//     }
// }
'use strict';
/*
______________________________________________________________________________
SUBJECT  the codon table, reverse complement and six reading frames one
         implementation (../dna*.js) gives for test sequences
HISTORY  The two strands of DNA run antiparallel (Watson & Crick, Nature
171:737, 1953): the minus strand of 5'-ATGC-3' is 5'-GCAT-3', the reverse
complement -- complementing without reversing gives the right bases in the
wrong direction. A protein-coding gene can lie in any of six reading
frames, three per strand. The codon -> amino acid map is the standard
genetic code (NCBI translation table 1); variant codes exist, e.g. the
vertebrate mitochondrial code (table 2: TGA = Trp, AGA/AGG = stop,
ATA = Met). Using the wrong table, or a "reverse complement" without the
reverse, are recurring bugs of hand-rolled sequence code. Reference: NCBI
"The Genetic Codes" (www.ncbi.nlm.nih.gov/Taxonomy/Utils/wprintgc.cgi).

REQUIREMENT  revcomp(s) is the minus strand read 5'->3'; translate() uses
the standard code; so the six frames of a sequence are the ones a
biologist would read off the two strands.

The unit is node, '../dna.js'. Broken fixtures, each a faithful model of a
mistake: '../dna_no_reverse.js' (complement only), '../dna_mito.js' (the
default table is table 2). The test prints
    1. the CODON TABLE the unit translates with (a 16 x 4 grid, as in a
       textbook), each cell checked against table 1 written into this test
       from NCBI: a differing cell is marked '!'; '((codon_diffs: N))';
    2. the SIX FRAMES of the Biopython tutorial sequence: the plus strand,
       frames +1..+3 with each amino acid under the middle base of its
       codon; the unit's minus strand drawn 3'->5' under it, with '|'
       where the two strands pair (A-T, C-G) and 'x' where they do not; the
       frames -1..-3 placed the same way (read right to left); the 'x'
       count is '((unpaired: N))';
    3. a CODON SWEEP ORF: ATG, the 61 sense codons of table 1 once each,
       TAA. Translated in frame +1 it must stop only at its end:
       '((internal_stops: N))';
    4. two LAWS over 500 random sequences (a MINSTD stream as in hwut's
       deterministic_random, seed as a comment):
         involution    revcomp(revcomp(s)) == s       '((roundtrip_errors: N))'
         antiparallel  revcomp(a + b) == revcomp(b) + revcomp(a)
                                                       '((antiparallel_errors: N))'

CHOICES
    standard    all five counts 0.
    no-reverse  the strands no longer pair ('x' row), the minus frames are
                nonsense -- and the involution law is STILL 0: complement
                is its own inverse. The pairing count and the antiparallel
                law see the bug ('unpaired > 0', 'antiparallel_errors > 0');
                'roundtrip_errors == 0' is kept in the header to document
                the blindness of the round trip. (A reversal WITHOUT
                complement passes both algebraic laws -- reverse is an
                involution and antiparallel too; only the pairing count
                sees it.)
    mito-table  the table shows '!' at TGA, AGA, AGG, ATA; the sweep ORF
                stops at AGA ('internal_stops > 0', 'codon_diffs > 0').

HWUT CONCEPTS  verbatim for the frames (each letter's column is its codon);
constraints carry the laws; the test is node with a '//' @hwut block.

READING THE GOOD  The 'pairs' row must be all '|' ('x' a base that does not pair);
the grid must carry no '!'. Every count ends with its law and verdict.
______________________________________________________________________________
*/
const path = require('path');
const UNIT_DB = { 'standard': 'dna.js', 'no-reverse': 'dna_no_reverse.js', 'mito-table': 'dna_mito.js' };
const NCBI_1 = 'FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG';
const SAMPLE = 'ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG';
const SEED = 1953;
const PAIRS = { A: 'T', T: 'A', C: 'G', G: 'C' };

function minstd(seed) {                       // deterministic_random.DeterministicStream.next_int
    let state = seed & 0x7FFFFFFF;
    return (lo, hi) => { state = (48271 * state) % 2147483647; return lo + state % (hi - lo + 1); };
}

function main(choice) {
    const dna = require(path.join(__dirname, '..', UNIT_DB[choice]));
    const B = 'TCAG';
    console.log('unit: ' + UNIT_DB[choice]);
    console.log();
    console.log('CODON TABLE used by translate()  (\'!\' = differs from NCBI table 1)');
    console.log('##! verbatim');
    console.log('       ' + B.split('').map(b => '  2nd ' + b + '   ').join('').trimEnd());
    let codonDiffs = 0;
    for (const b1 of B) for (const b3 of B) {
        let row = '  ' + b1 + '.' + b3 + '  ';
        for (const b2 of B) {
            const codon = b1 + b2 + b3, aa = dna.translate(codon);
            const ref = NCBI_1[B.indexOf(b1) * 16 + B.indexOf(b2) * 4 + B.indexOf(b3)];
            codonDiffs += aa !== ref;
            row += '  ' + codon + ' ' + aa + (aa !== ref ? '!' : ' ') + '  ';
        }
        console.log(row.trimEnd());
    }
    console.log('####');
    const law = (k) => 'law == 0   ' + (k === 0 ? 'kept' : 'BROKEN');
    console.log('codons differing from table 1 ((codon_diffs: ' + codonDiffs + '))   ' + law(codonDiffs));
    console.log();

    const s = SAMPLE, n = s.length;
    const minus = dna.revcomp(s);
    const lane = () => new Array(n).fill(' ');
    const plusLanes = [1, 2, 3].map(k => {
        const l = lane(), p = dna.translate(s.slice(k - 1));
        for (let j = 0; j < p.length; ++j) l[k + 3 * j] = p[j];
        return l.join('').trimEnd();
    });
    const minusLanes = [1, 2, 3].map(k => {
        const l = lane(), p = dna.translate(minus.slice(k - 1));
        for (let j = 0; j < p.length; ++j) l[n - 1 - k - 3 * j] = p[j];
        return l.join('').trimEnd();
    });
    const drawn = minus.split('').reverse().join('');           // minus strand, 3' -> 5'
    const pairs = s.split('').map((b, i) => PAIRS[b] === drawn[i] ? '|' : 'x').join('');
    console.log('SIX FRAMES of ' + n + ' bp; amino acids under the middle base of their codon;');
    console.log('pairs: \'|\' the two strands complementary at that base, \'x\' not');
    console.log('##! verbatim');
    console.log('          1        10        20        30');
    console.log('  5\'      ' + s + '  3\'');
    plusLanes.forEach((l, i) => console.log('  +' + (i + 1) + '      ' + l));
    console.log('  pairs   ' + pairs);
    console.log('  3\'      ' + drawn + '  5\'');
    minusLanes.forEach((l, i) => console.log('  -' + (i + 1) + '      ' + l));
    console.log('####');
    const unpaired = pairs.split('x').length - 1;
    console.log('bases of the minus strand not pairing with the plus strand ((unpaired: ' + unpaired + '))   ' + law(unpaired));
    console.log('  +1 ' + dna.translate(s));
    console.log('  -1 ' + dna.translate(minus));
    console.log();

    const sense = [];
    for (const b1 of B) for (const b2 of B) for (const b3 of B)
        if (NCBI_1[B.indexOf(b1) * 16 + B.indexOf(b2) * 4 + B.indexOf(b3)] !== '*') sense.push(b1 + b2 + b3);
    const orf = 'ATG' + sense.join('') + 'TAA';
    const protein = dna.translate(orf);
    const stops = [];
    for (let i = 0; i < protein.length - 1; ++i) if (protein[i] === '*') stops.push(orf.slice(3 * i, 3 * i + 3) + ' at codon ' + (i + 1));
    console.log('CODON SWEEP ORF: ATG + ' + sense.length + ' sense codons + TAA = ' + orf.length + ' bp');
    console.log('  protein ' + protein);
    for (const t of stops) console.log('  !! internal stop ' + t);
    console.log('internal stops ((internal_stops: ' + stops.length + '))   ' + law(stops.length));
    console.log();

    const rnd = minstd(SEED);
    const randomSeq = () => { let x = ''; const len = rnd(1, 60); for (let i = 0; i < len; ++i) x += 'ACGT'[rnd(0, 3)]; return x; };
    let roundtrip = 0, antiparallel = 0, example = '';
    for (let i = 0; i < 500; ++i) {
        const a = randomSeq(), b = randomSeq();
        if (dna.revcomp(dna.revcomp(a)) !== a) roundtrip += 1;
        if (dna.revcomp(a + b) !== dna.revcomp(b) + dna.revcomp(a)) {
            if (!antiparallel) example = '  e.g. a = ' + a.slice(0, 12) + '..., b = ' + b.slice(0, 12) + '...';
            antiparallel += 1;
        }
    }
    console.log('## seed ' + SEED);
    console.log('LAWS over 500 random pairs (a, b), length 1..60');
    console.log('  involution    revcomp(revcomp(a)) == a                  errors ((roundtrip_errors: ' + roundtrip + '))   ' + law(roundtrip));
    console.log('  antiparallel  revcomp(a + b) == revcomp(b) + revcomp(a)  errors ((antiparallel_errors: ' + antiparallel + '))   ' + law(antiparallel));
    if (example) console.log(example);
}

const choice = process.argv[2] || '';
if (!(choice in UNIT_DB)) {
    console.log('choices: ' + Object.keys(UNIT_DB).join(', '));
    process.exit(1);
}
main(choice);
console.log('<hwut-end>');

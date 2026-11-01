// dna_mito.js -- the bug: a pipeline built for mitochondrial genomes left
// its translation table as the default for nuclear genes: vertebrate
// mitochondrial code (NCBI table 2) -- TGA is Trp, AGA/AGG are stops, ATA is Met.
'use strict';
const dna = require('./dna');
module.exports = { ...dna, translate: (s, table = 2) => dna.translate(s, table) };

#! /usr/bin/env python3
# @hwut {
#     title    = "BED (0-based, half-open) and GFF/VCF (1-based, closed) name the same bases"
#     choices {
#         correct { features = ["same-bases", "vcf-ref", "roundtrip"]
#                   tolerance { constraints = ["misplaced == 0", "roundtrip_errors == 0"] } }
#         legacy  { features = ["misplaced-shown"]
#                   tolerance { constraints = ["misplaced > 0", "roundtrip_errors > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the bases a coordinate converter (../convert.awk or
         ../convert_legacy.awk) names for each feature, drawn on a 40 bp
         reference
HISTORY  The UCSC Genome Browser's BED format counts from 0 and leaves the
end open (a feature on the first base is 'chr1 0 1'); GFF, and VCF's POS,
count from 1 and include the end (the same base is 'chr1 1 1'). Converting
between them needs exactly one shift, of the start only, in each
direction; forgetting it is the classic off-by-one of genomics pipelines.
References: UCSC "BED format" (genome.ucsc.edu/FAQ/FAQformat), the GFF3
specification (Sequence Ontology), and Danecek et al., "The variant call
format and VCFtools", Bioinformatics 27:2156, 2011.

REQUIREMENT  A feature converted from BED to GFF covers the same bases,
a single-base feature written as VCF names the reference base as REF, and
BED -> GFF -> BED returns every interval unchanged.

The unit is an awk converter: '../convert.awk' (correct) and
'../convert_legacy.awk' (forgets the +1 on the BED -> GFF side, keeps the -1
on the way back -- the historical mistake). The test converts
'../features.bed' to GFF and back, reads each side by ITS OWN convention,
and draws on a base-pair ruler of '../ref.fa':
    1. the RULER: 0-based digits above, 1-based digits below the
       sequence, so a column is one base read both ways;
    2. per feature three rows -- BED as written, GFF as a GFF reader
       understands it, BED after the round trip -- each '=' a base the row
       claims, with its coordinates and the bases it covers;
    3. a VCF line for each single-base feature: POS and the REF the
       reference has there;
    4. a seeded sweep of 300 random intervals (deterministic_random, seed
       in the GOOD as a comment) through the round trip.
Counts are bindings: '((misplaced: N))' = features whose GFF reading covers
other bases than the BED, plus VCF REFs that are not the BED base;
'((roundtrip_errors: N))' = sweep intervals that come back changed.

CHOICES
    correct  every row of a feature covers the same columns; REF = the BED
             base; laws 'misplaced == 0', 'roundtrip_errors == 0'.
    legacy   the GFF rows start one base to the left (one base too long);
             the BED round trip moves every interval one base left; 'cap'
             at the chromosome start gets GFF start 0, a position that does
             not exist. Laws 'misplaced > 0', 'roundtrip_errors > 0'.

HWUT CONCEPTS  the ruler picture stands in '##! verbatim': whitespace
folding outside a region would make a feature shifted by one column EQUAL
to the original (LOG B-1, C-1). Constraints carry the verdict.

READING THE GOOD  Look down each feature's three '=' rows: they must stand
in the same columns. A '<' in the first column means the interval starts
before the sequence (a position that does not exist). The two counts end
with their law and verdict; the first counts the drawn features plus the
VCF records.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CHOICE_DB = {"correct": "convert.awk", "legacy": "convert_legacy.awk"}
SEED = 0xBED5


def convert(script, to, text):
    r = subprocess.run(["awk", "-v", "to=" + to, "-f", os.path.join(UNIT, script)],
                       input=text, capture_output=True, text=True, check=True)
    return [l.split("\t") for l in r.stdout.splitlines()]


def bar(first, last, width):
    """'=' over 0-based columns first..last (inclusive); '.' elsewhere; '<' in
    the first column where the interval starts before the sequence."""
    s = "".join("=" if first <= i <= last else "." for i in range(width))
    return "<" + s[1:] if first < 0 else s


def main(choice):
    script = CHOICE_DB[choice]
    ref = "".join(l.strip() for l in open(os.path.join(UNIT, "ref.fa")) if not l.startswith(">"))
    bed_text = open(os.path.join(UNIT, "features.bed")).read()
    bed = [l.split("\t") for l in bed_text.splitlines()]
    gff = convert(script, "gff", bed_text)
    back = convert(script, "bed", "".join("\t".join(r) + "\n" for r in gff))
    n = len(ref)

    print("unit: %s; reference chr1, %d bp" % (script, n))
    print()
    print("##! verbatim")
    print("                " + "".join(str(i // 10) if i % 10 == 0 else " " for i in range(n)) + "   0-based (BED)")
    print("                " + "".join(str(i % 10) for i in range(n)))
    print("  chr1          " + ref)
    print("                " + "".join(str((i + 1) % 10) for i in range(n)) + "   1-based (GFF, VCF)")
    print("                " + "".join(str((i + 1) // 10) if (i + 1) % 10 == 0 else " " for i in range(n)))
    misplaced = 0
    vcf_list = []
    for b, g, r in zip(bed, gff, back):
        name = b[3]
        bs, be = int(b[1]), int(b[2])               # 0-based, half-open
        gs, ge = int(g[3]), int(g[4])               # 1-based, closed
        rs, re_ = int(r[1]), int(r[2])
        bed_bases = ref[bs:be]
        gff_bases = ref[max(gs - 1, 0):ge]
        bad = (gs - 1, ge - 1) != (bs, be - 1)
        misplaced += bad
        print()
        print("  BED  %-8s  %s   %-8s %s" % (name, bar(bs, be - 1, n), "%d %d" % (bs, be), bed_bases))
        print("  GFF  %-8s  %s   %-8s %s%s" % (name, bar(gs - 1, ge - 1, n), "%d..%d" % (gs, ge), gff_bases,
                                                 "   !! other bases" if bad else "")
              + ("   !! start 0 does not exist" if gs < 1 else ""))
        print("  BED' %-8s  %s   %-8s %s%s" % (name, bar(rs, re_ - 1, n), "%d %d" % (rs, re_), ref[max(rs, 0):re_],
                                                  "   !! moved" if (rs, re_) != (bs, be) else ""))
        if be - bs == 1:
            vcf_list.append((name, gs, ref[gs - 1] if gs >= 1 else "?", bed_bases))
    print("####")
    print()
    print("VCF  (#CHROM POS ID REF; POS from the GFF start, REF read at POS)")
    for name, pos, base, bed_base in vcf_list:
        bad = base != bed_base
        misplaced += bad
        print("  chr1  %d  %s  %s   BED base %s%s" % (pos, name, base, bed_base, "   !! REF is not the BED base" if bad else ""))
    print()

    rng = DeterministicStream(SEED)
    sweep = []
    for _ in range(300):
        s = rng.next_int(0, 999999)
        sweep.append((s, s + rng.next_int(1, 5000)))
    gff = convert(script, "gff", "".join("chr1\t%d\t%d\tr%d\n" % (s, e, i) for i, (s, e) in enumerate(sweep)))
    back = convert(script, "bed", "".join("\t".join(r) + "\n" for r in gff))
    changed = [(s, e, int(r[1]), int(r[2])) for (s, e), r in zip(sweep, back) if (s, e) != (int(r[1]), int(r[2]))]
    print("## seed %d" % SEED)
    print("sweep: 300 random BED intervals -> GFF -> BED")
    for s, e, rs, re_ in changed[:3]:
        print("  [%d, %d) came back as [%d, %d)" % (s, e, rs, re_))
    if len(changed) > 3:
        print("  ... and %d more" % (len(changed) - 3))
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("features misplaced ((misplaced: %d)) of %d (%d features + %d VCF record)   %s"
          % (misplaced, len(bed) + len(vcf_list), len(bed), len(vcf_list), law(misplaced)))
    print("sweep intervals changed ((roundtrip_errors: %d)) of 300   %s" % (len(changed), law(len(changed))))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")

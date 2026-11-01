#! /usr/bin/env python3
# @hwut {
#     title    = "FASTQ qualities: Phred+33 and Phred+64 decode to the same Q per base"
#     choices {
#         phred33  { features = ["detected", "same-q", "bars"]
#                    tolerance { constraints = ["negative_q == 0", "mismatch == 0"] } }
#         phred64  { features = ["detected", "same-q", "bars"]
#                    tolerance { constraints = ["negative_q == 0", "mismatch == 0"] } }
#         detection { features = ["detected", "ambiguous-said"]
#                     tolerance { constraints = ["misdetected == 0"] } }
#         assume64 { features = ["bars", "breach-shown"]
#                    tolerance { constraints = ["negative_q > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the quality Q per base that ../phred.awk decodes from one FASTQ file,
         and the offset ../detect.awk detects
HISTORY  FASTQ stores a Phred quality Q = -10 log10(P_error) per base as one
ASCII character. Sanger chose offset 33 ('!' = Q0); Illumina pipelines
1.3 to 1.7 wrote offset 64 ('@' = Q0), and Illumina 1.8 (2011) went back to
33. The same file therefore reads correctly or 31 Q units off, depending
on what the reader assumes; neither file says which it is. Reference:
Cock, Fields, Goto, Heuer, Rice, "The Sanger FASTQ file format for
sequences with quality scores, and the Solexa/Illumina FASTQ variants",
Nucleic Acids Research 38:1767, 2010.

REQUIREMENT  A reader decodes each base's Q with the file's own offset: the
same reads, written once +33 and once +64, give the same Q for every base,
and no Q is negative.

The unit is awk: '../detect.awk' guesses the encoding from the range of
quality characters (lowest < ';' -> +33; lowest >= '@' and highest > 'J'
-> +64; else 'ambiguous' -- a +33 file of only high qualities cannot be
told apart, and the detector says so instead of guessing); '../phred.awk'
decodes with '-v offset=N' and DEFAULTS TO 64 when no offset is passed (it
was written for Illumina 1.3). Fixtures: the same three reads as
'../reads.p33.fq' and '../reads.p64.fq'. The test prints
    1. the detection of the choice's file and the offset used;
    2. per read the QUALITY BARS: one column per base, '*' in row t when
       Q >= t, a 'v' in row '<0' for a negative Q; min and mean Q. In
       '##! verbatim' -- the columns are the bases;
    3. '((negative_q: N))' bases with Q < 0, and '((mismatch: N))' bases
       whose Q differs from the other file decoded with ITS detected offset.

CHOICES
    detection the detector over four files, each with the verdict it must
              give: reads.p33.fq +33, reads.p64.fq +64, and two Phred+33
              files that lie in the AMBIGUOUS range -- reads.mid33.fq
              (lowest ';' = 59: Q26 in +33, or Q-5 in Solexa+64) and
              reads.hiq33.fq (only Q31..Q40 = '@'..'I', valid +64 too).
              For those the detector must say 'ambiguous', not guess.
              '((misdetected: N))', law 'misdetected == 0'.
    phred33   reads.p33.fq, detected +33, decoded with 33.
    phred64   reads.p64.fq, detected +64, decoded with 64. Same bars.
    assume64  the historical mistake: reads.p33.fq through a caller that
              never passes the offset -- the default 64 is used. Every Q is
              31 too low, about half the bases come out negative. Law
              'negative_q > 0'.

HWUT CONCEPTS  verbatim for the bar picture; constraints for the laws. The
cross-check against the other file makes the two fixtures each other's
oracle.

READING THE GOOD  phred33 and phred64 must show identical bars; assume64's
bars are short, and its '<0' rows are not empty.
______________________________________________________________________________
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
DETECT_DB = [("reads.p33.fq", "phred+33"), ("reads.p64.fq", "phred+64"),
             ("reads.mid33.fq", "ambiguous"), ("reads.hiq33.fq", "ambiguous")]
CHOICE_DB = {"detection": None,
             "phred33": ("reads.p33.fq", True, "reads.p64.fq"),
             "phred64": ("reads.p64.fq", True, "reads.p33.fq"),
             "assume64": ("reads.p33.fq", False, "reads.p64.fq")}


def awk(script, fastq, offset=None):
    cmd = ["awk"] + (["-v", "offset=%d" % offset] if offset is not None else []) + ["-f", os.path.join(UNIT, script), os.path.join(UNIT, fastq)]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def detect(fastq):
    lo, hi, verdict = awk("detect.awk", fastq).split()
    return int(lo), int(hi), verdict


def decode(fastq, offset=None):
    return [(n, s, [int(x) for x in q.split(",")]) for n, s, q in
            (l.split("\t") for l in awk("phred.awk", fastq, offset).splitlines())]


def detection():
    misdetected = 0
    print("DETECTION  lowest and highest quality character, the verdict, the verdict required")
    print("##! verbatim")
    for fastq, required in DETECT_DB:
        lo, hi, verdict = detect(fastq)
        misdetected += verdict != required
        print(("  %-15s  '%c' %3d .. '%c' %3d   %-9s  required %-9s%s"
               % (fastq, lo, lo, hi, hi, verdict, required, "" if verdict == required else "  !! misdetected")).rstrip())
    print("####")
    print("files misdetected ((misdetected: %d)) of %d   law == 0   %s"
          % (misdetected, len(DETECT_DB), "kept" if misdetected == 0 else "BROKEN"))


def main(choice):
    if choice == "detection":
        return detection()
    fastq, pass_offset, other = CHOICE_DB[choice]
    lo, hi, verdict = detect(fastq)
    offset = {"phred+33": 33, "phred+64": 64}.get(verdict) if pass_offset else None
    print("file: %s   quality characters '%c' (%d) .. '%c' (%d)   detected: %s"
          % (fastq, lo, lo, hi, hi, verdict))
    print("decoded with: %s" % ("-v offset=%d" % offset if pass_offset else "no offset passed (phred.awk's default)"))
    reads = decode(fastq, offset)
    o_lo, o_hi, o_verdict = detect(other)
    reference = {n: q for n, _, q in decode(other, {"phred+33": 33, "phred+64": 64}[o_verdict])}
    negative = mismatch = 0
    print("bars: one row per Q >= 40, 30, 20, 10, 0 and one for Q < 0; '*' the base")
    print("      reaches the row, 'v' its Q is below 0, '.' neither")
    print("##! verbatim")
    for name, seq, q in reads:
        negative += sum(1 for x in q if x < 0)
        mismatch += sum(1 for x, y in zip(q, reference[name]) if x != y)
        print("  %-4s %s   min Q %d, mean Q %.1f" % (name, seq, min(q), sum(q) / len(q)))
        for t in (40, 30, 20, 10, 0):
            print("  %3d  %s" % (t, "".join("*" if x >= t else "." for x in q)))
        print("   <0  %s" % "".join("v" if x < 0 else "." for x in q))
        print()
    print("####")
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("bases with Q < 0 ((negative_q: %d))   %s" % (negative, law(negative)))
    print("bases with Q differing from %s (%s) ((mismatch: %d))   %s" % (other, o_verdict, mismatch, law(mismatch)))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")

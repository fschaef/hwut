# detect.awk -- guess the quality encoding from the range of quality characters.
#   lowest < ';' (59)                -> Phred+33 (Sanger, Illumina 1.8+)
#   lowest >= '@' (64), highest > 'J' -> Phred+64 (Illumina 1.3-1.7)
#   otherwise                        -> ambiguous (say so; do not guess)
BEGIN { for (i = 32; i < 127; ++i) ord[sprintf("%c", i)] = i; lo = 999; hi = 0 }
NR % 4 == 0 { for (i = 1; i <= length($0); ++i) { c = ord[substr($0, i, 1)]; if (c < lo) lo = c; if (c > hi) hi = c } }
END {
    verdict = lo < 59 ? "phred+33" : (lo >= 64 && hi > 74 ? "phred+64" : "ambiguous")
    printf "%d %d %s\n", lo, hi, verdict
}

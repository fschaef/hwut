# phred.awk -- decode the quality line of FASTQ records.
# usage: awk -v offset=33 -f phred.awk reads.fq
# out:   name <TAB> sequence <TAB> Q1,Q2,...      (Q = ASCII code - offset)
BEGIN { OFS = "\t"; for (i = 32; i < 127; ++i) ord[sprintf("%c", i)] = i
        if (offset == "") offset = 64 }          # the reader was written for Illumina 1.3
NR % 4 == 1 { name = substr($0, 2) }
NR % 4 == 2 { seq = $0 }
NR % 4 == 0 {
    q = ""
    for (i = 1; i <= length($0); ++i) q = q (i > 1 ? "," : "") (ord[substr($0, i, 1)] - offset)
    print name, seq, q
}

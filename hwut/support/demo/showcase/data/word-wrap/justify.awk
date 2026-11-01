# justify.awk -- fill and justify paragraphs to a fixed width.
#
#   awk -v W=40 -f justify.awk text.txt
#
# A paragraph is a run of non-empty lines. Words are filled greedily; every
# line but the last of a paragraph is padded to exactly W columns by
# widening the gaps, the leftmost gaps first. The last line stays ragged.
function flush_line(n, last,    i, gap_n, pad, extra, line, w) {
    if (n == 0) return
    line = word[1]
    gap_n = n - 1
    if (last || gap_n == 0) {
        for (i = 2; i <= n; i++) line = line " " word[i]
        print line
        return
    }
    w = 0
    for (i = 1; i <= n; i++) w += length(word[i])
    pad   = int((W - w) / gap_n)
    extra = (W - w) - pad * gap_n
    for (i = 2; i <= n; i++) {
        line = line sprintf("%*s", pad + ((i - 1) <= extra ? 1 : 0), "") word[i]
    }
    print line
}
function flush_paragraph(    i, n, width) {
    n = 0; width = 0
    for (i = 1; i <= para_n; i++) {
        if (n > 0 && width + 1 + length(para[i]) > W) {
            flush_line(n, 0)
            n = 0; width = 0
        }
        word[++n] = para[i]
        width += (n > 1 ? 1 : 0) + length(para[i])
    }
    flush_line(n, 1)
    para_n = 0
}
BEGIN   { if (W == "") W = 72; para_n = 0; para_seen = 0 }
NF == 0 { if (para_n > 0) { if (para_seen++) print ""; flush_paragraph() } next }
        { for (i = 1; i <= NF; i++) para[++para_n] = $i }
END     { if (para_n > 0) { if (para_seen++) print ""; flush_paragraph() } }

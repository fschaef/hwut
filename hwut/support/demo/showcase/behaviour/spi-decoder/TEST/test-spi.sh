#! /bin/bash
# @hwut {
#     title    = "SPI decoder (awk): transactions and bytes out of a 4-lane capture"
#     features = ["whole-bytes", "rising-edge"]
#     choices {
#         read-id      { features = ["whole-bytes", "rising-edge", "part-identified"]
#                        tolerance { constraints = ["truncated == 0", "capacity == 128 Mibit"] } }
#         write-enable { features = ["whole-bytes", "rising-edge", "cs-frames"]
#                        tolerance { constraints = ["truncated == 0"] } }
#         cs-glitch    { features = ["truncated-named", "cs-frames"]
#                        tolerance { constraints = ["truncated > 0"] } }
#     }
# }
# ____________________________________________________________________________
# SUBJECT  the transactions and bytes the awk SPI decoder finds in one 4-lane
#          capture, drawn under the lanes they came from
# REQUIREMENT  Every CS-low phase is decoded into whole bytes on MOSI and MISO,
#              MSB first, sampled at the rising SCK edge (mode 0); a phase
#              that ends inside a byte is reported as truncated, with the
#              number of bits left over.
#
# The unit is the awk script '../spi_decode.awk', a protocol decoder for
# logic-analyser exports drawn as text ('../captures/*.cap', recipe in
# '../captures/make_captures.py'). It prints records (BEGIN, BIT, BYTE, END,
# TRUNC); this test draws them UNDER the four lanes of the capture:
#
#     look   '^' in every column where the decoder sampled a bit
#     MOSI   '<--9f-->' over the samples that made up each byte
#     MISO   the same for the other direction
#     frame  '|' where a transaction opened and closed, '!' where it closed
#            inside a byte
#
# read-id       a JEDEC 'read ID' to a W25Q128: 9f 00 00 00 out, ff ef 40 18
#               back (manufacturer Winbond, type 40, capacity 2^0x18 bytes).
#               The capacity the decoded ID announces is bound as a QUANTITY,
#               '((capacity: 16777216 B))', and judged against the part's
#               datasheet name, '128M-bit', in the datasheet's unit: law
#               'capacity == 128 Mibit'. A decoder that shifts a bit of the
#               third ID byte announces 2^0x30 or 2^0x0c bytes and breaks it.
#               TRAP, on purpose in the law: the datasheet's 'M' is binary
#               (2^20); pint's 'Mbit' is decimal (10^6) -- 'capacity == 128
#               Mbit' would be broken by the right part (16 MiB = 134.2 Mbit).
#               Binary prefixes ('Mi', 'Ki') say what the datasheet means.
# write-enable  two transactions: 06, then 05 00 with status 02 (WEL set).
# cs-glitch     EMI lifts CS for two samples after bit 11 of a read ID: the
#               decoder must report TWO truncated transactions (11 = 1 byte
#               + 3 bits, 20 = 2 bytes + 4 bits), not invent bytes. The GOOD
#               file is the accepted picture of that failure.
#
# HWUT CONCEPTS  The lanes and the marks stand in one '##! verbatim' region
# (columns are time). Everything is deterministic; no tolerance. The number
# of truncated transactions is a constraint binding, '((truncated: N))':
# 'truncated == 0' on the clean captures, 'truncated > 0' on cs-glitch -- so
# 'hwut.accept' refuses a decoder that invents a truncation on a clean bus,
# or one that stops reporting the glitch. Nothing in the test knows awk is
# the unit's language -- it reads what it prints.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
case "$1" in
    read-id|write-enable|cs-glitch) cap="$HERE/../captures/$1.cap" ;;
    *) echo "choices: read-id, write-enable, cs-glitch"; exit 1 ;;
esac

echo "capture: captures/$1.cap -- $(sed -n '1s/^# //p' "$cap")"
echo
awk -f "$HERE/../spi_decode.awk" "$cap" | awk -v cap="$cap" '
function span(row, first, last, label,    w, l, r, i, s) {
    w = last - first + 1; l = int((w - 2 - length(label)) / 2); r = w - 2 - length(label) - l
    s = "<"; for (i = 0; i < l; ++i) s = s "-"; s = s label; for (i = 0; i < r; ++i) s = s "-"; s = s ">"
    return substr(row, 1, first) s substr(row, last + 2)
}
function put(row, at, ch) { return substr(row, 1, at) ch substr(row, at + 2) }
function hex(s,    v, i) { v = 0; for (i = 1; i <= length(s); ++i) v = 16 * v + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
function blank(n,    s) { s = ""; while (length(s) < n) s = s "."; return s }
BEGIN { while ((getline line < cap) > 0) if (line !~ /^#/) { split(line, f, " "); lane[f[1]] = f[2] } }
      { rec[NR] = $0 }
END {
    n = length(lane["CS"])
    look = blank(n); bmosi = blank(n); bmiso = blank(n); frame = blank(n)
    t = 0
    for (k = 1; k <= NR; ++k) {
        split(rec[k], f, " ")
        if (f[1] == "BEGIN") { frame = put(frame, f[2], "|"); ++t; bit_n = 0; tail = -1 }
        if (f[1] == "BIT")   { look = put(look, f[2], "^"); if (tail < 0) tail = f[2] }
        if (f[1] == "BYTE")  { bmosi = span(bmosi, f[2], f[3], f[4]); bmiso = span(bmiso, f[2], f[3], f[5]);
                               mo[t] = mo[t] " " f[4]; mi[t] = mi[t] " " f[5]; tail = -1 }
        if (f[1] == "END")   { frame = put(frame, f[2], "|"); bits[t] = f[3]; from[t] = last_begin; to[t] = f[2] }
        if (f[1] == "BEGIN") last_begin = f[2]
        if (f[1] == "TRUNC") { frame = put(frame, f[2], "!"); trunc[t] = f[3];
                               bmosi = span(bmosi, tail, f[2] - 1, f[3] "b?"); bmiso = span(bmiso, tail, f[2] - 1, f[3] "b?") }
    }
    ruler = ""
    for (i = 0; i < n; ++i) {
        if (i % 10 == 0) { label = sprintf("%d", i); ruler = ruler label; skip = length(label) - 1 }
        else if (skip > 0) --skip
        else ruler = ruler " "
    }
    print "##! verbatim"
    printf "%-7s%s\n", "sample", ruler
    printf "%-7s%s\n", "CS",   lane["CS"]
    printf "%-7s%s\n", "SCK",  lane["SCK"]
    printf "%-7s%s\n", "MOSI", lane["MOSI"]
    printf "%-7s%s\n", "MISO", lane["MISO"]
    printf "%-7s%s\n", "look", look
    printf "%-7s%s\n", "MOSI", bmosi
    printf "%-7s%s\n", "MISO", bmiso
    printf "%-7s%s\n", "frame", frame
    print "####"
    print "(one character per sample, an SCK period is 2; look: ^ a bit sampled at a rising SCK edge;"
    print " MOSI/MISO: <--9f--> the samples of one byte, <3b?> 3 bits left over; frame: | CS falls or"
    print " rises, ! CS rises inside a byte)"
    print ""
    for (i = 1; i <= t; ++i) {
        printf "transaction %d: samples %d..%d, %d bits", i, from[i], to[i], bits[i]
        if (trunc[i]) printf " -- !! ends inside a byte: %d whole byte(s) + %d bit(s)", int(bits[i] / 8), trunc[i]
        print ""
        printf "    MOSI %s\n", mo[i] == "" ? " -" : mo[i]
        printf "    MISO %s\n", mi[i] == "" ? " -" : mi[i]
        if (mo[i] ~ /^ 9f/ && split(mi[i], id, " ") == 4) {
            printf "    JEDEC ID: manufacturer %s, type %s, capacity 2^0x%s bytes\n", id[2], id[3], id[4]
            printf "    capacity ((capacity: %d B)) = %g Mibit   law == 128 Mibit (W25Q128)   %s\n", 2 ^ hex(id[4]), 2 ^ hex(id[4]) * 8 / 1048576, (2 ^ hex(id[4]) == 16777216 ? "kept" : "BROKEN")
        }
        trunc_n += trunc[i] > 0
    }
    printf "truncated transactions: ((truncated: %d))   (a clean bus has 0)   %s\n", trunc_n, (trunc_n ? "!! reported" : "clean")
}'
echo "<hwut-end>"

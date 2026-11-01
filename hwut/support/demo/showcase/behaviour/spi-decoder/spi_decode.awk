# spi_decode.awk -- an SPI mode-0 protocol decoder for logic-analyser
# captures drawn as text (lines 'CS', 'SCK', 'MOSI', 'MISO'; '-' high, '_'
# low; one character per sample; '#' lines are notes).
#
# Prints one record per event, for whatever draws or checks it:
#     BEGIN <sample>                      CS falls: a transaction opens
#     BIT   <sample> <mosi> <miso>        SCK rises while CS is low
#     BYTE  <first> <last> <mosi> <miso>  eight bits, MSB first, in hex
#     END   <sample> <bits>               CS rises: the transaction closes
#     TRUNC <sample> <bits>               ...inside a byte: bits left over
/^#/ { next }
     { lane[$1] = $2 }
END {
    n = length(lane["CS"]); open = 0
    for (i = 1; i <= n; ++i) {
        cs   = substr(lane["CS"],   i, 1); pcs  = i > 1 ? substr(lane["CS"],  i-1, 1) : "-"
        sck  = substr(lane["SCK"],  i, 1); psck = i > 1 ? substr(lane["SCK"], i-1, 1) : "_"
        mosi = substr(lane["MOSI"], i, 1) == "-"
        miso = substr(lane["MISO"], i, 1) == "-"
        if (pcs == "-" && cs == "_") { printf "BEGIN %d\n", i-1; open = 1; bits = 0; mo = 0; mi = 0 }
        if (open && cs == "_" && psck == "_" && sck == "-") {
            printf "BIT %d %d %d\n", i-1, mosi, miso
            if (bits % 8 == 0) first = i-1
            mo = mo * 2 + mosi; mi = mi * 2 + miso; ++bits
            if (bits % 8 == 0) { printf "BYTE %d %d %02x %02x\n", first, i-1, mo, mi; mo = 0; mi = 0 }
        }
        if (open && pcs == "_" && cs == "-") {
            printf "END %d %d\n", i-1, bits
            if (bits % 8) printf "TRUNC %d %d\n", i-1, bits % 8
            open = 0
        }
    }
}

# invoice.awk -- the legacy invoice tool: one line per item, VAT per line.
#   awk -F';' -f invoice.awk invoice.csv
# Amounts are binary floating point; '%.2f' does the rounding.
/^#/ || NF < 4 { next }
{
    net   = $2 * $3
    vat   = net * $4 / 100
    printf "%s;%.2f;%.2f;%.2f\n", $1, net, vat, net + vat
    total_net += sprintf("%.2f", net); total_vat += sprintf("%.2f", vat)
}
END { printf "TOTAL;%.2f;%.2f;%.2f\n", total_net, total_vat, total_net + total_vat }

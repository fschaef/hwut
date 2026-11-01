# convert.awk -- BED <-> GFF coordinates.
#   BED   0-based, half-open:  start = first base - 1 ... end = last base
#   GFF   1-based, closed:     start = first base     ... end = last base
#   (VCF POS is 1-based like GFF.)
# usage: awk -v to=gff -f convert.awk x.bed   |   awk -v to=bed -f convert.awk x.gff
BEGIN { FS = OFS = "\t" }
to == "gff" { print $1, "conv", "region", $2 + 1, $3, ".", ".", ".", "Name=" $4; next }
to == "bed" { sub(/^Name=/, "", $9); print $1, $4 - 1, $5, $9 }

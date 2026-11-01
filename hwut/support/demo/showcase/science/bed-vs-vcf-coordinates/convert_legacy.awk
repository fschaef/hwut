# convert_legacy.awk -- BED <-> GFF coordinates, as an old pipeline script
# had it: the GFF side subtracts one on the way back, but the BED side was
# "already numbers" and is copied as it stands.
BEGIN { FS = OFS = "\t" }
to == "gff" { print $1, "conv", "region", $2, $3, ".", ".", ".", "Name=" $4; next }
to == "bed" { sub(/^Name=/, "", $9); print $1, $4 - 1, $5, $9 }

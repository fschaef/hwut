#! /bin/sh
#  CHECK-TREE: one 'sha256  path' per source file, sorted, relative to
#  the tree root. Same exclusions as the delivery scripts use, so its
#  output can be compared against them directly.
#
#  Run from INSIDE the source tree (the directory holding
#  'hwut-root.conf'):
#
#      sh check-tree.sh > my-hashes.txt
#
find . -type f \
     ! -path "*/.git/*"        ! -path "*/__pycache__/*" \
     ! -path "*/.ruff_cache/*" ! -path "*/.venv/*" \
     ! -path "*/TEST/TMP/*"    ! -path "*/TEST/OUT/*" \
     ! -path "*/TEST/ADM/*"    ! -path "*/.hwut-store/*" \
     ! -name "*.pyc"           ! -name "*.log" \
     ! -name "*.rej"           ! -name "*.orig" \
     ! -name "book.csv"        ! -name "result_db.csv" \
     ! -name "hwut-traces.csv" \
     ! -name "observations.bin" \
     -print0 \
| xargs -0 sha256sum \
| sed 's|  \./|  |' \
| sort -k2

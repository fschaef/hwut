#! /usr/bin/env python3
# @hwut {
#     title    = "Gene symbols survive a spreadsheet round trip (Ziemann et al. 2016)"
#     choices {
#         smart     { features = ["symbols-survive", "mangled-named", "artifact-any-order"]
#                     tolerance { constraints = ["mangled > 0", "header_first == \"yes\""] } }
#         text      { features = ["symbols-survive", "artifact-any-order"]
#                     tolerance { constraints = ["mangled == 0", "header_first == \"yes\""] } }
#         hgnc-2020 { features = ["renamed-symbols", "mangled-named", "artifact-any-order"]
#                     tolerance { constraints = ["dates == 0", "mangled > 0", "header_first == \"yes\""] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the gene symbols of one gene list after a spreadsheet round trip
         (../sheet.py), cell by cell
HISTORY  Ziemann, Eren and El-Osta screened the supplementary Excel files of
18 journals (2005-2015) and found gene-name errors in 987 files of 704
articles -- about one in five papers that published a gene list in Excel
(Genome Biology 17:177, 2016, "Gene name errors are widespread in the
scientific literature"). The cause: the spreadsheet's General cell format
reads SEPT2 and MARCH1 as dates (2-Sep, 1-Mar) and RIKEN clone accessions
such as 2310009E13 as numbers in scientific notation; saved again, the
original symbol is gone. In 2020 the HGNC renamed the affected human genes
(SEPT2 -> SEPTIN2, MARCH1 -> MARCHF1, DEC1 -> DELEC1; Bruford et al., Nature
Genetics 52:754, 2020), partly for this reason.

REQUIREMENT  A gene list that goes through an import and an export comes
out with every symbol spelled as it went in.

The unit is '../sheet.py', a model of a spreadsheet's CSV import (typed
cells: 'smart' guesses date/number/text like the General format, 'text'
keeps every cell as text) and export (each cell as displayed). The test
reads '../genes.csv' (or '../genes-2020.csv'), round-trips it, and prints
    1. the SYMBOL TABLE: symbol in, the cell type the import chose, symbol
       out; a changed symbol is marked '!! mangled'. In '##! verbatim': the
       columns are the picture.
    2. the counts as bindings: '((dates: N))' symbols turned into dates,
       '((numbers: N))' into numbers, '((mangled: N))' changed at all.
    3. the EXPORTED ARTIFACT: the UNIT writes 'significant.csv' (rows with
       padj < 0.05) into a temp directory with sheet.save_significant(),
       which drops duplicate rows through a set -- so the unit itself
       writes the data rows in an order that changes from process to
       process (string hash randomisation); the test only reads the file
       back. Line 1 must be the header: it is printed OUTSIDE the region,
       exactly, with the law '((header_first: "yes"))' -- a file with the
       header anywhere else is refused. Lines 2..n stand in
       '##! potpourri': each must find a partner, in any order. A mangled
       symbol is visible there as the downstream tool reads it ('2-Sep,1.21').

CHOICES
    smart      the historical mistake: General format. SEPT2, SEPT9, MARCH1,
               MARCH5, DEC1 become dates, 2310009E13 a number. Law
               'mangled > 0' -- the violation, not its exact count.
    text       the same list imported as text: law 'mangled == 0'.
    hgnc-2020  the renamed symbols through the SAME smart import: no date
               any more ('dates == 0'), but the RIKEN accession is still a
               number -- renaming human genes cured only the dates
               ('mangled > 0').

HWUT CONCEPTS  constraints carry the requirement (a re-accept cannot bless
a new mangled symbol in 'text'); verbatim keeps the table's columns exact;
potpourri judges the rows of a file whose order the unit does not define,
while what IS ordered (the header in line 1) stays outside it. The
potpourri cannot carry bindings (MANUAL 13), so the counts stand outside.

READING THE GOOD  Read the '!!' rows of the table and the potpourri lines:
the symbols a reader of the supplementary file would see. In 'hgnc-2020'
the last column names the pre-2020 symbol ('-' unchanged): the renames are
why no date appears. The count lines end with their law and verdict.
______________________________________________________________________________
"""
import csv
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sheet

CHOICE_DB = {"smart": ("genes.csv", "smart"), "text": ("genes.csv", "text"),
             "hgnc-2020": ("genes-2020.csv", "smart")}


def main(choice):
    file_name, mode = CHOICE_DB[choice]
    rows = list(csv.reader(open(os.path.join(HERE, "..", file_name))))
    header, rows = rows[0], rows[1:]
    sheet_rows = [[sheet.import_cell(c, mode) for c in r] for r in rows]
    out_rows = [[sheet.export_cell(c) for c in r] for r in sheet_rows]

    print("input: %s (%d genes), import: %s" % (file_name, len(rows), mode))
    print()
    renamed = choice == "hgnc-2020"
    if renamed:                    # the same genes under their pre-2020 symbols, row by row
        old = [r[0] for r in list(csv.reader(open(os.path.join(HERE, "..", "genes.csv"))))[1:]]
    print("##! verbatim")
    print("  symbol in     cell type  symbol out" + ("    HGNC renamed it from" if renamed else ""))
    count = {"date": 0, "number": 0}
    mangled = 0
    for k, (r, s, o) in enumerate(zip(rows, sheet_rows, out_rows)):
        bad = r[0] != o[0]
        mangled += bad
        if bad:
            count[s[0][0]] += 1
        was = ("    %-12s" % (old[k] if old[k] != r[0] else "-")) if renamed else ""
        print(("  %-12s  %-9s  %-12s%s%s" % (r[0], s[0][0], o[0], was, "  !! mangled" if bad else "")).rstrip())
    print("####")
    print("symbols turned into dates ((dates: %d)), into numbers ((numbers: %d))"
          % (count["date"], count["number"]))
    print("symbols changed ((mangled: %d)) of %d   law == 0   %s"
          % (mangled, len(rows), "kept" if mangled == 0 else "BROKEN"))
    print()
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "significant.csv")
        written = sheet.save_significant(path, header, sheet_rows, 2)
        lines = open(path).read().splitlines()
    finally:
        shutil.rmtree(tmp)
    print("artifact significant.csv, written by sheet.save_significant (padj < 0.05): %d rows" % written)
    first = "yes" if lines[0] == "symbol,log2fc" else "no"
    print("line 1: %s   header first ((header_first: \"%s\"))   law: yes   %s"
          % (lines[0], first, "kept" if first == "yes" else "BROKEN"))
    print("rows 2..%d, in the order the unit wrote them (undefined):" % len(lines))
    print("##! potpourri")
    for line in lines[1:]:
        print(line)
    print("####")


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")

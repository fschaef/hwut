#! /usr/bin/env python3
#
# @hwut {
#     title   = "CSV export to JSON: typed by a schema, broken rows named"
#     choices {
#         orders { features = ["typed", "quoting", "all-or-named"]
#                  tolerance { constraints = ["rejected == 0"] } }
#         export { features = ["violation-shown"]
#                  tolerance { constraints = ["rejected > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the JSON objects ../csv2json.js makes of one CSV export, row beside
         object, and the rows it rejects with their broken rules
REQUIREMENT. ../csv2json.js (node) turns a CSV export into JSON against
../schema.json:
    R1  every valid row becomes one object, keys in schema order, typed:
        int and number as JSON numbers, an empty optional field as null;
    R2  quoted fields keep their commas and quotes ("" is one quote);
    R3  a row that breaks the schema is left out and every broken rule is
        named on stderr as file:line: column: what; exit status 1.

CHOICES
    orders  ../orders.csv: four valid rows, with a quoted comma, a quoted
            quote, a leap day, a negative amount. All in, exit 0.
    export  ../orders-export.csv, as a partner system sent it: 29 Feb of a
            common year, an empty customer, a status 'shipped', a German
            decimal comma, one field too many, a US date. One row survives;
            six are named (law: rejected > 0; for orders: rejected == 0).

HWUT CONCEPT. Input and output side by side, field against field, so a
reader sees the typing ('1499.00' became the number 1499, '' became null)
without reading JSON. The tool's stderr and exit status are captured by the
test application and printed as part of the picture. Exact comparison:
nothing varies; every cell is printed in full. The number of rejected rows
is a constraint binding '((rejected: n))', judged by the choice's law.

READING THE GOOD. Per CSV line: left the cells as read ('""' an empty
cell), right the JSON member or the rule it broke; '!' marks the field a
rejected row breaks, '-' a field with nothing to say. 'exit', the count, the
law 'rejected == 0' (a clean export) and its verdict close the page.
______________________________________________________________________________
"""
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")


def main(choice):
    name = "orders.csv" if choice == "orders" else "orders-export.csv"
    p = subprocess.run(["node", os.path.join(TOP, "csv2json.js"), os.path.join(TOP, "schema.json"), name],
                       cwd=TOP, capture_output=True, text=True)
    objects = json.loads(p.stdout) if p.stdout.strip() else []
    complaint_db = {}
    for line in p.stderr.splitlines():
        _, number, column, what = line.split(":", 3)
        complaint_db.setdefault(int(number), []).append((column.strip(), what.strip()))
    with open(os.path.join(TOP, name), newline="") as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    print("node csv2json.js schema.json %s" % name)
    k = 0
    for number, cells in enumerate(rows[1:], start=2):
        print("-" * 76)
        if number in complaint_db:
            print("%-36s | REJECTED" % ("csv line %d" % number))
        else:
            print("%-36s | json object %d" % ("csv line %d" % number, k + 1))
        obj = objects[k] if number not in complaint_db else None
        broken = dict(complaint_db.get(number, []))
        for i, cell in enumerate(cells):
            col = header[i] if i < len(header) else "(extra)"
            mark = "!" if col in broken else " "
            left = "%s %-9s %s" % (mark, col, cell if cell else '""')
            if obj is not None:
                right = "%s: %s" % (json.dumps(col), json.dumps(obj[col], ensure_ascii=False))
            elif col in broken:
                right = "%s: %s" % (col, broken[col])
            else:
                right = "-"
            print("%-36s | %s" % (left, right))
        if "row" in broken:
            print("%-36s | row: %s" % ("! (the row)", broken["row"]))
        k += obj is not None
    print("-" * 76)
    print("exit %d: %d of %d rows converted, rejected ((rejected: %d))   law == 0   %s"
          % (p.returncode, len(objects), len(rows) - 1, len(complaint_db),
             "kept" if not complaint_db else "BROKEN (by the input rows)"))


if len(sys.argv) < 2 or sys.argv[1] not in ("orders", "export"):
    print("choices: orders, export")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")

#! /usr/bin/env python3
#
# @hwut {
#     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
#     tolerance { stderr_ignored = true }
#     choices {
#         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
#         report { features = ["output-file", "keyed-table-separator", "dependency",
#                              "frame-scripts", "test-scripts", "stderr-ignored"]
#                  output   = ["<stdout>", "stock.csv"] }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
         comes in, three clerks sell at once, and the stock is reported.
REQUIREMENT  Every movement of the stock is journalled, so that the stock
             always ADDS UP: opening quantity plus the journal's movements.

THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
this file, read it first. hwut, when it enters this directory:

    on_entry        'fixture.py open': a fresh 'TMP/shop.db', stocked
    on_before_test  'fixture.py check before $HWUT_TEST $HWUT_CHOICE',
    on_after_test   'fixture.py check after ...': around every test run,
                    whether the stock adds up, into 'TMP/frame.log' --
                    hwut sets the two variables for the run
    on_exit         'fixture.py close'
    apps            'delivery.json' is a test, though it carries no
                    header: JSON has no comment to carry one. 'admit'
                    takes it out of the files hwut ignores by default
                    ('*.json'); 'execute' says how it is run --
                    'shop.py deliver delivery.json'.
    collision       'delivery.json' and 'shop.py sell' both write the
                    database. SQLite lets one writer at a time hold the
                    file; one that waits too long fails with 'database
                    is locked'. hwut never runs the two at once.
    dependency      'shop.py report' runs after both, whatever their
                    verdict: it reports what they left.

STDERR  Every SQL statement is logged on stderr, as a server would. A
word on stderr fails a run ('unexpected stderr') unless the header says
'stderr_ignored = true': the words there are on purpose, and no error.

CHOICES

sell     three clerks sell at once, each in a thread of its own. The sales
         are printed as '##! table unordered sep={;}': rows of 'item;qty',
         in any order -- and no column is a key, 'apple;1' stands four
         times.

report   the stock, as '##! table key=0 sep={;}', and the same rows
         written to 'stock.csv': 'output' names the file, hwut reads it
         after the run and compares it with its own GOOD. Then the frame
         log of the shop's tests: what 'on_before_test' and 'on_after_test'
         found around the delivery and the sale ('##! potpourri': which
         ran first is free), and before this report.

deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
         delivery note: every line on the stock and into the journal, in
         one transaction.
______________________________________________________________________________
"""
import json
import os
import sqlite3
import sys
import threading

HERE     = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(HERE, "TMP", "shop.db")
LOG_PATH = os.path.join(HERE, "TMP", "frame.log")

#  What each clerk sells, one item per sale.
CLERK_DB = {"anna":  ["apple", "apple", "pear"],
            "ben":   ["apple", "plum"],
            "chloe": ["apple"]}


def connect():
    """
    RETURN: sqlite3.Connection, to the shop's database, every statement it
            executes logged on stderr.
    Exits 1 where the database does not stand: 'on_entry' writes it.
    """
    if not os.path.exists(DB_PATH):
        print("shop.py: no %s -- 'on_entry' writes it; by hand: "
              "'hwut.execute fixture open'" % DB_PATH, file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    db.set_trace_callback(lambda sql: print("sql: " + sql, file=sys.stderr))
    return db


def move(db, item, delta, source):
    """RETURN: None. Changes the stock of 'item' by 'delta' and journals it,
    in one transaction."""
    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", (delta, item))
    db.execute("INSERT INTO journal VALUES (?, ?, ?)", (item, delta, source))
    db.execute("COMMIT")


def deliver(path):
    """RETURN: None. Books the delivery note in 'path' and prints it."""
    with open(path) as fh:
        note = json.load(fh)
    db = connect()
    db.execute("BEGIN IMMEDIATE")
    for line in note["lines"]:
        db.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", (line["qty"], line["item"]))
        db.execute("INSERT INTO journal VALUES (?, ?, ?)", (line["item"], line["qty"], note["note"]))
    db.execute("COMMIT")
    print("delivery note %s from %s:" % (note["note"], note["supplier"]))
    for line in note["lines"]:
        print("    %-6s +%d" % (line["item"], line["qty"]))


def sell():
    """RETURN: None. Three clerks sell at once; prints every sale."""
    sale_list, error_list = [], []
    lock = threading.Lock()

    def clerk(name, item_list):
        try:
            db = connect()
            for item in item_list:
                move(db, item, -1, name)
                with lock:
                    sale_list.append("%s;1" % item)
            db.close()
        except Exception as error:
            error_list.append("%s: %s" % (name, error))

    connect().close()
    pool = [threading.Thread(target=clerk, args=pair) for pair in CLERK_DB.items()]
    for thread in pool: thread.start()
    for thread in pool: thread.join()
    if error_list:
        print("shop.py: a sale failed -- %s" % "; ".join(error_list), file=sys.stderr)
        sys.exit(1)
    print("sales, item;qty -- in the order the clerks booked them:")
    print("##! table unordered sep={;}")
    for row in sale_list:
        print(row)
    print("####")


def report():
    """RETURN: None. Prints the stock and the frame log; writes 'stock.csv'."""
    db = connect()
    row_list = db.execute("SELECT item, qty FROM stock ORDER BY qty, item").fetchall()
    with open(os.path.join(HERE, "stock.csv"), "w") as fh:
        fh.write("item;qty\n")
        for item, qty in sorted(row_list):
            fh.write("%s;%d\n" % (item, qty))
    print("stock, item;qty (also written to stock.csv):")
    print("##! table key=0 sep={;}")
    for item, qty in row_list:
        print("%s;%d" % (item, qty))
    print("####")
    with open(LOG_PATH) as fh:
        line_list = [line.rstrip() for line in fh]
    print("the frame, around the delivery and the sale:")
    print("##! potpourri")
    for line in line_list:
        if "shop.py report" not in line: print(line)
    print("####")
    for line in line_list:
        if "shop.py report" in line: print(line)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if   command == "deliver": deliver(sys.argv[2])
    elif command == "sell":    sell()
    elif command == "report":  report()
    else:
        print("choices: sell, report")
        sys.exit(1)
    print("<hwut-end>")

#! /usr/bin/env python3
"""
______________________________________________________________________________
THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.

    fixture.py open            a fresh 'TMP/shop.db', stocked as below, and
                               an empty 'TMP/frame.log' ('on_entry', and
                               'hwut.execute fixture open')
    fixture.py close           both removed ('on_exit')
    fixture.py check <when> <app> [<choice>]
                               'when' is 'before' or 'after': whether the
                               stock adds up around the test run '<app>
                               <choice>', appended to 'TMP/frame.log'
                               ('on_before_test', 'on_after_test')

'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
which hwut sets for the run the check stands around; a test without
choices has none. 'check' concerns the shop's tests alone. The stock ADDS UP where every item's quantity is its opening
quantity plus every movement of the journal.
______________________________________________________________________________
"""
import os
import sqlite3
import sys

HERE     = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(HERE, "TMP", "shop.db")
LOG_PATH = os.path.join(HERE, "TMP", "frame.log")
OPENING_DB = {"apple": 10, "pear": 5, "plum": 5}
SHOP_TEST_SET = ("delivery.json", "shop.py")


def open_shop():
    """RETURN: None. Writes a fresh, stocked database and an empty log."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    for path in (DB_PATH, LOG_PATH):
        if os.path.exists(path): os.remove(path)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)")
        db.execute("CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)")
        db.execute("CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)")
        for item, qty in OPENING_DB.items():
            db.execute("INSERT INTO opening VALUES (?, ?)", (item, qty))
            db.execute("INSERT INTO stock   VALUES (?, ?)", (item, qty))
    open(LOG_PATH, "w").close()


def close_shop():
    """RETURN: None. Removes the database and the log."""
    for path in (DB_PATH, LOG_PATH):
        if os.path.exists(path): os.remove(path)


def adds_up():
    """
    RETURN: True, if every item's stock is its opening quantity plus its
                  journal's movements;
            False, else.
    """
    with sqlite3.connect(DB_PATH) as db:
        row_list = db.execute(
            "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
            "  FROM opening o JOIN stock s ON s.item = o.item"
            "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item").fetchall()
    return all(expected == got for _, expected, got in row_list)


def check(when, test, choice=""):
    """RETURN: None. Appends one line to the log for a shop test run."""
    if test not in SHOP_TEST_SET: return
    run = ("%s %s" % (test, choice)).strip()
    with open(LOG_PATH, "a") as fh:
        fh.write("%-6s %-15s %s\n" % (when, run, "stock adds up" if adds_up() else "STOCK BROKEN"))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if   command == "open":  open_shop()
    elif command == "close": close_shop()
    elif command == "check": check(*sys.argv[2:5])
    else:
        print("usage: fixture.py open | close | check before|after <app> <choice>",
              file=sys.stderr)
        sys.exit(2)

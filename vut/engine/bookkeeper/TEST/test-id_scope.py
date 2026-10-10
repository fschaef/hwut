#! /usr/bin/env python3
#
# @hwut {
#     title      = "The id scope: one allocation law, and the spellings of an id"
#     choices    = ["allocate", "ceiling", "give_back", "mark_line", "spellings"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ID SCOPE -- the counter behind app ids, choice ids, group
         ids and feature ids, and the texts an id is written in.

CHOICES: allocate, give_back, ceiling, mark_line, spellings;

allocate   a scope counting from 0 and one counting from 1 issue the
           number above the highest they ever issued; 'raise_to' lifts
           the mark and never lowers it.

give_back  the last id issued steps the mark back and is issued again;
           an earlier one is retired and the mark stands.

ceiling    a scope whose next id is ID_LIMIT issues nothing, and its
           refusal names the scope.

mark_line  the one mark, written as 'N:<next>' and as
           'issued = <mark>'; what 'mark_of_text' takes and leaves.

spellings  decimal ('47', '47.66') and base 64 at one width, each read
           back to the number it was written from.
______________________________________________________________________________
"""
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.id_scope import (IdScope,           # noqa E402
                                              ID_LIMIT,
                                              decimal_parts,
                                              decimal_text,
                                              id_number,
                                              id_text,
                                              number_of_decimal)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def state(scope):
    """RETURN: str, 'mark=<n> next=<n>' of 'scope'."""
    return "mark=%i next=%i" % (scope.mark, scope.next)


def test_allocate():
    """RETURN: None. Prints what two fresh scopes issue."""
    banner("a scope counting from 0")
    zero = IdScope("the app scope")
    print("INSPECT: fresh             -> %s" % state(zero))
    zero_list = [zero.allocate() for _ in range(3)]
    print("INSPECT: three allocations -> %s   %s" % (zero_list, state(zero)))

    banner("a scope counting from 1")
    one = IdScope("the feature scope", first=1)
    print("INSPECT: fresh             -> %s" % state(one))
    one_list = [one.allocate() for _ in range(3)]
    print("INSPECT: three allocations -> %s   %s" % (one_list, state(one)))

    banner("a scope taken up where a file left it")
    resumed = IdScope("the group scope", next_id=7)
    print("INSPECT: next_id=7         -> %s, issues %i"
          % (state(resumed), resumed.allocate()))

    banner("raise_to")
    lifted  = one.raise_to(9)
    lowered = one.raise_to(4)
    print("INSPECT: raise_to(9) -> %s   raise_to(4) -> %s   %s"
          % (lifted, lowered, state(one)))
    print("INSPECT: issued_f: 0 -> %s, 1 -> %s, 9 -> %s, 10 -> %s"
          % tuple(one.issued_f(n) for n in (0, 1, 9, 10)))

    ok = check([
        (zero_list == [0, 1, 2],  "from 0: the first id is 0"),
        (one_list == [1, 2, 3],   "from 1: the first id is 1"),
        (lifted and not lowered and one.mark == 9,
         "the mark is lifted, never lowered"),
        (one.allocate() == 10,    "allocation goes on above a lifted mark"),
    ])
    verdict(ok, "the next id lies above the highest ever issued.")


def test_give_back():
    """RETURN: None. Prints what giving an id back does to the mark."""
    scope = IdScope("the app scope")
    for _ in range(3): scope.allocate()
    banner("the last id issued")
    last = scope.give_back(2)
    print("INSPECT: give_back(2) -> %s   %s" % (last, state(scope)))
    again = scope.allocate()
    print("INSPECT: the next allocation -> %i" % again)

    banner("an id that is not the last")
    early = scope.give_back(0)
    print("INSPECT: give_back(0) -> %s   %s" % (early, state(scope)))
    after = scope.allocate()
    print("INSPECT: the next allocation -> %i" % after)

    banner("the only id of a scope counting from 1")
    one = IdScope("the feature scope", first=1)
    one.allocate()
    only = one.give_back(1)
    print("INSPECT: give_back(1) -> %s   %s" % (only, state(one)))

    ok = check([
        (last and again == 2,  "the last id issued is issued again"),
        (not early and after == 3,
         "an earlier id is retired: the mark stands"),
        (only and one.allocate() == 1,
         "a scope given back whole starts at its first id"),
    ])
    verdict(ok, "no id is issued twice while it stands.")


def test_ceiling():
    """RETURN: None. Prints what a scope at ID_LIMIT answers."""
    banner("one id below the ceiling")
    scope = IdScope("the choice scope of app 3", next_id=ID_LIMIT - 1)
    below = scope.allocate()
    print("INSPECT: next = ID_LIMIT - 1 -> issued: %s"
          % (below == ID_LIMIT - 1))

    banner("at the ceiling")
    at = scope.allocate()
    print("INSPECT: next = ID_LIMIT -> %s" % at)
    print("INSPECT: %s" % scope.refusal_text())
    stands = scope.next == ID_LIMIT

    ok = check([
        (below == ID_LIMIT - 1, "the last id is ID_LIMIT - 1"),
        (at is None and stands, "ID_LIMIT itself is never issued; the "
                                "mark stands"),
        (scope.refusal_text().startswith("the choice scope of app 3 "),
         "the refusal names the scope"),
    ])
    verdict(ok, "a scope at its ceiling refuses by name.")


def test_mark_line():
    """RETURN: None. Prints the two writings of the mark and what
    'mark_of_text' takes."""
    scope = IdScope("the feature scope", first=1)
    scope.allocate(); scope.allocate()
    banner("one mark, two writings")
    print("INSPECT: 'N:%s'   'issued = %s'"
          % (scope.next_text(), scope.mark_text()))

    banner("mark_of_text, on a scope counting from 1")
    result_list = []
    for text in ("5", " 7 ", "0", "-1", "", "x", "1.5",
                 "%i" % (ID_LIMIT - 1), "%i" % ID_LIMIT):
        probe = IdScope("the feature scope", first=1)
        taken = probe.mark_of_text(text)
        print("         %-12s -> %-5s %s" % (repr(text), taken, state(probe)))
        result_list.append((text, taken, probe.mark))

    db = {text: (taken, mark) for text, taken, mark in result_list}
    ok = check([
        (scope.next_text() == "3" and scope.mark_text() == "2",
         "'N:' carries the next id, 'issued =' the highest issued"),
        (db["5"] == (True, 5) and db[" 7 "] == (True, 7),
         "a decimal number is taken"),
        (db["0"] == (True, 0), "'issued = 0' is the fresh scope"),
        (all(db[t] == (False, 0) for t in ("-1", "", "x", "1.5")),
         "what spells no mark leaves the mark standing"),
        (db["%i" % (ID_LIMIT - 1)][0] and not db["%i" % ID_LIMIT][0],
         "a mark at ID_LIMIT is not taken"),
    ])
    verdict(ok, "the mark is read back as it was written.")


def test_spellings():
    """RETURN: None. Prints ids in decimal and in base 64."""
    banner("decimal")
    for number, sub_number in ((47, None), (47, 66), (0, 0)):
        text = decimal_text(number, sub_number)
        print("INSPECT: %-10s -> '%s' -> %s"
              % ((number, sub_number), text, decimal_parts(text)))
    for text in ("47.", "4.7.1", "a", ""):
        print("INSPECT: decimal_parts(%-7s) -> %s"
              % (repr(text), decimal_parts(text)))
    for text in ("12", " 12 ", "-12", "1 2", "+3"):
        print("INSPECT: number_of_decimal(%-6s) -> %s"
              % (repr(text), number_of_decimal(text)))

    banner("base 64 at one width")
    number_list = (0, 9, 10, 35, 36, 37, 63, 64, 4095, 4096)
    text_list   = [id_text(n, 3) for n in number_list]
    for number, text in zip(number_list, text_list):
        print("INSPECT: %5i -> '%s' -> %i" % (number, text, id_number(text)))
    try:               id_number("a-b"); bad = "nothing"
    except ValueError: bad = "ValueError"
    print("INSPECT: id_number('a-b') -> %s" % bad)

    ok = check([
        (decimal_parts(decimal_text(47, 66)) == (47, 66),
         "a decimal id reads back, with and without a number below it"),
        (all(id_number(t) == n for n, t in zip(number_list, text_list)),
         "a base-64 id reads back"),
        (text_list == sorted(text_list),
         "at one width, sorting the text sorts the numbers"),
        (bad == "ValueError", "a character outside the alphabet is refused"),
    ])
    verdict(ok, "every spelling reads back to its number.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The id scope: one allocation law, and the spellings of an id",
        choice_map = {
            "allocate":  test_allocate,
            "give_back": test_give_back,
            "ceiling":   test_ceiling,
            "mark_line": test_mark_line,
            "spellings": test_spellings,
        },
        happy      = "SUCCESS.*",
    ).run()

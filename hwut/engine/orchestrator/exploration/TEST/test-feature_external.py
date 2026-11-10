#! /usr/bin/env python3
#
# @hwut {
#     title      = "The map to external names: our id, their name"
#     choices {
#         read   { features = ["external-read"] }
#         faults { features = ["external-faults-named"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut-feature-external-map.csv', read (spec 43 section 3;
         intend/43 T-e, T-f, T-r): '<our feature id> ; <their name>'.

CHOICES: read, faults;

read    one line per pair, several names for one id in file order, a name
        standing twice once, the outside's name a free string; comments and
        blanks dropped; no file, None.

faults  a line with no ';', an empty side, an id the forest does not hold
        (with 'did you mean').
______________________________________________________________________________
"""
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration.feature_forest \
    import forest_of_text                                          # noqa E402
from hwut.engine.orchestrator.exploration.feature_external \
    import external_of_text, read_external, ExternalFault          # noqa E402

FOREST = forest_of_text("gateway : forwarding, keep-order\n")


def read():
    """RETURN: None. The map as read."""
    found = external_of_text("""# ours ; theirs
keep-order ; REQ-4711
gateway    ; Gateway (customer spec 2.1) ; with a semicolon

keep-order ; Kundenanforderung 12
keep-order ; REQ-4711
""", FOREST)
    for each in sorted(found):
        print("%-11s %s" % (each, found[each]))
    print("no file    %s" % read_external(tempfile.mkdtemp(), FOREST))


def faults():
    """RETURN: None. Each fault as it is said."""
    for label, text in (("no semicolon", "gateway REQ-1\n"),
                        ("empty ours",   " ; REQ-1\n"),
                        ("empty theirs", "gateway ;\n"),
                        ("unknown id",   "keeporder ; REQ-1\n")):
        try:
            external_of_text(text, FOREST)
            print("%-13s read" % label)
        except ExternalFault as fault:
            print("%-13s %s" % (label, fault))


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The map to external names: our id, their name",
        choice_map = {"read": read, "faults": faults},
    ).run()

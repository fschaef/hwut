#! /usr/bin/env python3
#
# @hwut {
#     title      = "The one detector: what the feature files and the links disagree about"
#     choices {
#         notes { features = ["detector-notes"] }
#         clean { features = ["detector-notes"] }
#         past  { features = ["detector-names-past-files"] }
#         prototypes { features = ["detector-notes"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DETECTOR ('feature_detector', spec 43 section 6; intend/43
         T-h, t-5, t-6): notes, never faults, in one vocabulary for
         'hwut.features.register' and 'hwut.sanitize.propose --relations'.

CHOICES: notes, clean, past, prototypes;

notes   a documented feature in no forest line (with 'did you mean' where a
        forest id is near), an undocumented ROOT, a non-root without a block
        is silent, a link to an id that stands nowhere (with 'did you mean')
        and one to a retired id -- each id once.

clean   a tree whose files and links agree: no note.

past    the files of the past -- a TEST directory's 'hwut-features.conf',
        'hwut-root-features.conf', 'hwut-feature-map.conf' -- named; one in
        a bubble with a forest of its own is not this forest's; one in a
        bubble without is.

prototypes  (intend/44 p-8) a prototype no feature aggregates; a member
        without a block in a prototype without one, nor one around it; a
        member documented, or under a documented prototype, is silent; a
        link to a bare member stands outside.
______________________________________________________________________________
"""
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

import _feature_tree as ft                                       # noqa E402
from hwut.engine.orchestrator.exploration.feature_detector \
    import detect_of_tree                                          # noqa E402


def _notes(root):
    """RETURN: None. The detector's notes of the tree at 'root'."""
    found = detect_of_tree(root)
    for each in found:
        print("%-13s %s" % (each.kind, ft.masked(each.text)))
    if not found: print("no note")


def notes():
    """RETURN: None. The gateway tree, a near-miss beside 'lonely'."""
    root = ft.tree("gateway    : forwarding, buses\n"
                   "forwarding : fwd, keep-order\n"
                   "spare      : x\n",
                   "[[forwarding]]\nFrames reach.\n"
                   "[[keeporder]]\nOrder is kept.\n"
                   "[[gone:retired]]\nOnce.\n",
                   test_db={"a/TEST/test-a.sh": [
                                'features = ["fwd", "fwdd", "gone"]',
                                'choices = ["one", "two"]'],
                            "b/TEST/test-b.sh": [
                                'features = ["fwdd"]']})
    _notes(root)


def clean():
    """RETURN: None. A tree that agrees with itself."""
    _notes(ft.tree("gateway : fwd\n",
                   "[[gateway]]\nThe gateway.\n",
                   test_db={"a/TEST/test-a.sh": ['features = ["fwd"]']}))


def prototypes():
    """RETURN: None. Prototypes, aggregated and not, documented and not."""
    _notes(ft.tree("port : +show\n"
                   "+show : greet, +talk\n+talk : ask\n"
                   "+bare : thing\n+lone : solo\n",
                   "[[port]]\nA port.\n[[greet]]\nHello.\n"
                   "[[+lone]]\nAlone.\n",
                   test_db={"a/TEST/test-a.sh": [
                                'features = ["port+greet", "ask"]']}))


def past():
    """RETURN: None. Files of the past, in the tree and in bubbles."""
    root = ft.tree("gateway : fwd\n", "[[gateway]]\nThe gateway.\n")
    ft.write(root, "gw/TEST/hwut-features.conf", "features { }\n")
    ft.write(root, "gw/hwut-feature-map.conf", "map { }\n")
    ft.write(root, "inner/hwut-root.conf", "hwut {\n}\n")
    ft.write(root, "inner/x/TEST/hwut-features.conf", "features { }\n")
    ft.write(root, "own/hwut-root.conf", "hwut {\n}\n")
    ft.write(root, "own/hwut-feature-forest.csv", "a : b\n")
    ft.write(root, "own/hwut-root-features.conf", "features { }\n")
    ft.write(root, "gw/TMP/hwut-features.conf", "features { }\n")
    _notes(root)


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "The one detector: what the feature files and "
                         "the links disagree about",
            choice_map = {"notes": notes, "clean": clean, "past": past,
                          "prototypes": prototypes},
        ).run()
    finally:
        ft.removed()

#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.features.rename and retire: the files and the links, in one step"
#     choices {
#         rename  { features = ["rename-follows"] }
#         retire  { features = ["retire-moves"] }
#         refused { features = ["rename-follows", "retire-moves"] }
#         prototypes { features = ["rename-follows", "retire-moves"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE FACES that write (spec 43 section 5; intend/43 t-4,
         T-s), each called as a person calls it, on a scratch tree; the
         files and the links shown before and after.

CHOICES: rename, retire, refused, prototypes;

rename   'keep-order' -> 'keeporder': both sides of the forest's lines, the
         doc file's heading (its audience kept), the map's left column (the
         outside's name untouched), the links of a test header and of a
         conf's application -- each file named; then a root renamed; the
         views agree before and after.

retire   a childless feature: its heading '[[<id>:retired]]', its id out
         of its parent's line, the line dropped where it names no other
         child; a feature with no block gets one; the label 'f/<id>' then
         refuses it.

refused  rename: an old id that stands nowhere ('did you mean'), a new id
         that is no id, 'CUSTOMERS', one that stands already, a file with a
         fault, no forest; retire: an id with children, one named in the
         map, one retired already, one that stands nowhere. Nothing is
         written where anything is refused.

prototypes (intend/44 p-7) a member renamed: its prototype's line, its
         block, the instances' blocks, the map, every link to an instance
         -- in one step; a prototype renamed: its line, its aggregations,
         its block, the links of every instance of an inner prototype; an
         owner renamed carries its instances; a member retired: out of its
         prototype's line, its block retired, its instances' links then
         name a retired claim. Refused: retiring the last member, a
         prototype, an instance, a member whose instance has a block or
         whose instance the map names.
______________________________________________________________________________
"""
import os
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

import _fixture as fx                                            # noqa E402
from hwut.services.lib.features import rename, retire           # noqa E402
from hwut.engine.orchestrator.exploration.feature_view \
    import (feature_label_case_set, forget_views)                 # noqa E402
from hwut.engine.orchestrator.exploration.task_list \
    import SelectionError                                          # noqa E402

FILE_TUPLE = ("hwut-feature-forest.csv", "hwut-feature-doc.dat",
              "hwut-feature-external-map.csv")


def _files(root):
    """RETURN: None. The three files and the links, as they stand."""
    for each in FILE_TUPLE:
        fx.shown(root, each)
    for each in ("gw/TEST/test-fwd.sh", "gw/TEST/hwut.conf"):
        with open(os.path.join(root, each)) as fh:
            print("    [%s] %s" % (each, " | ".join(
                line.strip(" #") for line in fh.read().split("\n")
                if "features" in line)))


def _snapshot(root):
    """RETURN: dict, path -> text of every file below 'root'."""
    result = {}
    for here, _, file_list in os.walk(root):
        for name in file_list:
            path = os.path.join(here, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                result[path] = fh.read()
    return result


def run_rename():
    """RETURN: None. A feature renamed, then a root."""
    root = fx.gateway()
    fx.call("hwut.features.rename keep-order keeporder", rename,
            ["keep-order", "keeporder"], root)
    _files(root)
    fx.call("hwut.features.rename gateway gw", rename, ["gateway", "gw"],
            os.path.join(root, "gw/TEST"))
    fx.shown(root, "hwut-feature-forest.csv")
    fx.shown(root, "hwut-feature-external-map.csv")


def run_retire():
    """RETURN: None. Features retired."""
    root = fx.gateway()
    fx.write(root, "hwut-feature-external-map.csv", "gateway ; GW\n")
    fx.call("hwut.features.retire fwd", retire, ["fwd"], root)
    fx.shown(root, "hwut-feature-forest.csv")
    fx.call("hwut.features.retire keep-order: its parent's line goes",
            retire, ["keep-order"], root)
    fx.call("hwut.features.retire decode: no block of its own", retire,
            ["decode"], root)
    for each in FILE_TUPLE[:2]:
        fx.shown(root, each)
    forget_views()
    try:
        feature_label_case_set(root, "f/fwd")
    except SelectionError as error:
        print(">>> f/fwd\n    REFUSED: %s" % error)


def run_refused():
    """RETURN: None. What is refused, and that nothing was written."""
    root   = fx.gateway()
    before = _snapshot(root)
    for label, face, argv in (
            ("rename an id that stands nowhere", rename, ["keep-ordr", "x"]),
            ("rename to no id", rename, ["fwd", "f.w.d"]),
            ("rename to CUSTOMERS", rename, ["fwd", "CUSTOMERS"]),
            ("rename to an id that stands", rename, ["fwd", "buses"]),
            ("rename to an unplaced id", rename, ["fwd", "spare"]),
            ("rename with one word", rename, ["fwd"]),
            ("retire an id with children", retire, ["forwarding"]),
            ("retire an id the map names", retire, ["keep-order"]),
            ("retire an id that stands nowhere", retire, ["fwdd"])):
        fx.call(label, face, argv, root)
    print(">>> nothing written: %s" % (_snapshot(root) == before))
    fx.call("retire, then retire again", retire, ["spare"], root)
    fx.call("", retire, ["spare"], root)
    fx.write(root, "hwut-feature-doc.dat", "[[a.b]]\n")
    fx.call("a doc file that states a fault", rename, ["fwd", "fwd2"], root)
    os.remove(os.path.join(root, "hwut-feature-forest.csv"))
    fx.call("no forest", retire, ["fwd"], root)


PROTOTYPE_DB = {
    "hwut-feature-forest.csv": "port : +show, own\n+show : greet, bye, +talk\n"
                               "+talk : ask\n+lone : solo\n",
    "hwut-feature-doc.dat": "[[+show]]\nWhat every port shows.\n"
                            "[[greet]]\nIt says hello.\n"
                            "[[port+bye]]\nThis port says goodbye.\n",
    "hwut-feature-external-map.csv": "port+greet ; REQ-1\n",
}


def _prototype_files(root):
    """RETURN: None. The three files and the test's links."""
    for each in FILE_TUPLE:
        fx.shown(root, each)
    with open(os.path.join(root, "p/TEST/test-p.sh")) as fh:
        print("    [p/TEST/test-p.sh] %s" % " | ".join(
            line.strip(" #") for line in fh.read().split("\n")
            if "features" in line))


def run_prototypes():
    """RETURN: None. Members, prototypes and owners renamed and retired."""
    root = fx.tree(PROTOTYPE_DB)
    fx.test(root, "p/TEST/test-p.sh",
            ['features = ["port+greet", "port+ask", "port+bye", "own"]'])
    fx.call("hwut.features.rename greet hello: a member", rename,
            ["greet", "hello"], root)
    fx.call("hwut.features.rename talk chat: an inner prototype", rename,
            ["talk", "chat"], root)
    fx.call("hwut.features.rename port gate: an owner", rename,
            ["port", "gate"], root)
    _prototype_files(root)
    for label, argv in (("the last member", ["solo"]),
                        ("a prototype", ["show"]),
                        ("an instance", ["gate+hello"]),
                        ("a member whose instance has a block", ["bye"])):
        fx.call("hwut.features.retire: " + label, retire, argv, root)
    fx.call("hwut.features.retire hello: the map names an instance",
            retire, ["hello"], root)
    fx.write(root, "hwut-feature-external-map.csv", "own ; REQ-2\n")
    fx.call("hwut.features.retire hello: a member", retire, ["hello"], root)
    _prototype_files(root)
    forget_views()
    try:
        feature_label_case_set(root, "f/gate+hello")
    except SelectionError as error:
        print(">>> f/gate+hello\n    REFUSED: %s" % error)


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "hwut.features.rename and retire: the files and "
                         "the links, in one step",
            choice_map = {"rename": run_rename, "retire": run_retire,
                          "refused": run_refused,
                          "prototypes": run_prototypes},
        ).run()
    finally:
        fx.removed()

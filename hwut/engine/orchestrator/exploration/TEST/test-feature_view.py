#! /usr/bin/env python3
#
# @hwut {
#     title      = "The view of the features: the forest joined with the links"
#     choices {
#         states  { features = ["view-states-fold"] }
#         cut     { features = ["view-cut-by-id"] }
#         label   { features = ["feature-label-runs"] }
#         refused { features = ["view-refused-named"] }
#         removal { features = ["removal-names-unproven"] }
#         prototypes { features = ["view-states-fold", "feature-label-runs"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'feature_view': the forest, the doc file and the map joined with
         the links of the tree's test runs (spec 43 section 4; intend/43
         T-n, t-2, T-u).

CHOICES: states, cut, label, refused, removal, prototypes;

states   every feature folds its own runs and its children's: a feature
         with runs and children, one with children only, one with neither
         (OPEN untested), the worst verdict; the counts of the childless;
         the unplaced, the retired, the links outside (an id standing
         nowhere, with 'did you mean'; a retired one); the audiences and
         the outside's names; asked below the top, the same view, its
         paths written from there.

cut      the view kept to the subtree of an id, the ids above it as
         headers, folded and counted anew; two ids a union; an unplaced id.

label    'f/<id>': the runs of the feature and of every feature below it;
         a retired id refused; an unknown one refused with 'did you mean',
         or -- not strict -- no run; no forest, refused.

refused  no forest ('=> hwut.features.init'); a fault of each file stops
         the view, named.

removal  what a removal leaves unproven: a feature linked by what goes and
         by no other run of the tree; one linked from another directory
         too is not; an id that stands nowhere is not; one choice of a test.

prototypes (intend/44) the instances stand in the trees and fold their
         runs like any feature; a link to a bare member or to a prototype
         stands outside, named; a retired member retires its instances.
         'f/' takes a glob anywhere -- 'f/*+greet', 'f/port-?', 'f/*' --
         and refuses one that matches nothing, a bare member, a
         prototype ('f/+show'); what matches no feature, not strict,
         selects nothing.
______________________________________________________________________________
"""
import os
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

import _feature_tree as ft                                       # noqa E402
from hwut.engine.orchestrator.exploration.feature_view \
    import (view_of, view_kept, feature_label_case_set, ViewRefused,
            forget_views, unproven_by_removal)                    # noqa E402
from hwut.engine.orchestrator.exploration.task_list \
    import SelectionError                                          # noqa E402
from hwut.services.lib.report.features \
    import view_state_text                                         # noqa E402


def _printed(view):
    """RETURN: None. Every feature of 'view', indented, with its state,
    its own runs, its counts where it has children, its audiences and its
    names; then the unplaced, the retired, the outside."""
    def walk(node, depth):
        print("%s%-12s %-22s runs=%i%s%s%s" % (
            "  " * depth, node.id, view_state_text(node.state),
            len(node.run_tuple),
            "  counts=%s" % ",".join("%s:%i" % pair for pair
                                     in sorted(node.count_db.items()))
            if node.child_tuple else "",
            "  audience=%s" % ",".join(node.audience_tuple)
            if node.audience_tuple else "",
            "  names=%s" % ",".join(node.external_tuple)
            if node.external_tuple else ""))
        for child in node.child_tuple: walk(child, depth + 1)

    for each in view.root_tuple: walk(each, 0)
    for each in view.unplaced:
        print("unplaced  %s  %s" % (each.id, view_state_text(each.state)))
    for each in view.retired_tuple:
        print("retired   %s" % each.id)
    for path, test, choice, feature_id, why in view.outside_tuple:
        print("outside   %s/%s %s '%s': %s" % (path, test, choice,
                                               feature_id, why))
    print("count     %s" % ",".join("%s:%i" % pair for pair
                                    in sorted(view.count_db().items())))


def states():
    """RETURN: None. The view of the gateway tree, at the top and below."""
    root = ft.gateway("gateway ; GW-1\nkeeporder ; REQ-4711\n")
    _printed(view_of(root))
    print("--- asked in bus/TEST: the same features, paths from there")
    view = view_of(os.path.join(root, "bus/TEST"))
    print(" ".join("%s/%s" % (view.run_path(run), run.test)
                   for run in view.node_of("decode").run_tuple))
    print("whole view: %s" % (len(view.node_list())
                              == len(view_of(root).node_list())))


def cut():
    """RETURN: None. The view cut by ids."""
    root = ft.gateway()
    view = view_of(root)
    for id_set in ({"forwarding"}, {"fwd", "decode"}, {"lonely"},
                   {"gateway"}):
        print("--- %s" % ", ".join(sorted(id_set)))
        _printed(view_kept(view, id_set))


def label():
    """RETURN: None. The runs of 'f/<id>'."""
    root = ft.gateway()

    def shown(name, strict_f=True):
        try:
            found = feature_label_case_set(root, name, strict_f)
            print("%-14s %s" % (name, " ".join(sorted(
                "%s [%s]" % (os.path.relpath(path, root), choice)
                for path, choice in found)) or "(none)"))
        except SelectionError as error:
            print("%-14s REFUSED: %s" % (name, ft.masked(str(error))))

    for name in ("f/fwd", "f/forwarding", "f/gateway", "f/buses",
                 "f/encode", "f/lonely", "f/old", "f/decod"):
        shown(name)
    shown("f/decod", strict_f=False)
    forget_views()
    empty = ft.tree("", "")
    os.remove(os.path.join(empty, "hwut-feature-forest.csv"))
    try:
        feature_label_case_set(empty, "f/fwd")
    except SelectionError as error:
        print("no forest      REFUSED: %s" % ft.masked(str(error)))


def refused():
    """RETURN: None. A view that cannot be had."""
    root = ft.tree("", "")
    os.remove(os.path.join(root, "hwut-feature-forest.csv"))
    for label, forest, doc, external in (
            ("no forest", None, "", None),
            ("forest",  "a : b\nb : a\n", "", None),
            ("doc",     "a : b\n", "[[b:retired]]\n", None),
            ("map",     "a : b\n", "", "c ; X\n")):
        if forest is not None:
            root = ft.tree(forest, doc, external)
        try:
            view_of(root)
            print("%-9s viewed" % label)
        except ViewRefused as error:
            print("%-9s %s" % (label, ft.masked(str(error))))


def removal():
    """RETURN: None. The features a removal leaves without a run."""
    root = ft.gateway()
    ft.test(root, "bus/TEST/test-also.sh", ['features = ["keeporder"]'])
    for directory, test, choice in (("gw/TEST", "test-fwd.sh", None),
                                    ("gw/TEST", "test-fwd.sh", "one"),
                                    ("gw/TEST", "test-order.sh", None),
                                    ("bus/TEST", "test-bus.sh", None),
                                    ("bus/TEST", "test-typo.sh", None),
                                    ("gw/TEST", "test-plain.sh", None)):
        print("%s %s %s -> %s" % (directory, test, choice, unproven_by_removal(
            os.path.join(root, directory), test, choice)))


PROTOTYPE_FOREST = """port-a : +show, own
port-b : +show
+show  : greet, bye, +talk
+talk  : ask
"""

PROTOTYPE_DOC = """[[+show]]
What every port shows.
[[bye:retired]]
Once it said goodbye.
"""

PROTOTYPE_TEST_DB = {
    "a/TEST/test-a.sh": ['features = ["port-a+greet", "port-a+ask"]'],
    "b/TEST/test-b.sh": ['features = ["port-b+greet", "greet", "+show"]'],
    "b/TEST/test-c.sh": ['features = ["port-b+bye"]'],
}


def prototypes():
    """RETURN: None. A prototype aggregated by two ports: the view, the
    outside, and the labels with globs."""
    forest = PROTOTYPE_FOREST.replace("greet, bye,", "greet,")
    root = ft.tree(forest, PROTOTYPE_DOC, None, PROTOTYPE_TEST_DB,
                   {("a/TEST", "test-a.sh", None): True,
                    ("b/TEST", "test-b.sh", None): False})
    _printed(view_of(root))

    def shown(name, strict_f=True):
        try:
            found = feature_label_case_set(root, name, strict_f)
            print("%-14s %s" % (name, " ".join(sorted(
                "%s [%s]" % (os.path.relpath(path, root), choice)
                for path, choice in found)) or "(none)"))
        except SelectionError as error:
            print("%-14s REFUSED: %s" % (name, ft.masked(str(error))))

    for name in ("f/port-a+greet", "f/*+greet", "f/port-?", "f/port-a+*",
                 "f/*", "f/*+nothing", "f/greet", "f/+show", "f/port-b+bye"):
        shown(name)
    shown("f/*+nothing", strict_f=False)
    forget_views()


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "The view of the features: the forest joined "
                         "with the links",
            choice_map = {"states": states, "cut": cut, "label": label,
                          "refused": refused,
                          "removal": removal,
                          "prototypes": prototypes},
        ).run()
    finally:
        ft.removed()

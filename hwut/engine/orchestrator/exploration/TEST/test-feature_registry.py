#! /usr/bin/env python3
#
# @hwut {
#     title      = "The central feature file: directory_map, tree, retired, identifiers, states"
#     choices {
#         read        { features = ["registry-read"] }
#         faults      { features = ["registry-read"] }
#         identifiers { features = ["registry-read"] }
#         states      { features = ["registry-states"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CENTRAL FILE OF THE FEATURES, read (spec 23 VERSION 10,
         RATIONALE R-96): 'hwut-root-features.conf' with its
         'directory_map', its 'tree' of aggregates and leaves and its
         'retired' claims; the identifiers of o-10; the two axes of a
         claim's state (o-14).

CHOICES: read, faults, identifiers, states;

read         the file as stated: the directories, the tree with its tree
             paths (unplaced leaves at the top), the keys an aggregate
             passes down, the retired claims as they were.

faults       what the file states that is not read, each named with its
             line: a directory id of the wrong shape, a path that leaves
             the root, a name standing twice, an aggregate key equal to an
             external id, a claim that was retired and is bound again,
             'none' in the tree, an unknown key.

identifiers  UAX #31 widened by digits at the start and '-' inside, NFC
             enforced: which words are identifiers, which external ids,
             which internal ids, which directory ids.

states       IMPLEMENTED / OPEN / RETIRED with the verdict beside: a leaf
             from the verdicts of its runs, an aggregate from the states
             below it.
______________________________________________________________________________
"""
import sys
import unicodedata

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration import feature_registry as fr  # noqa E402
from hwut.engine.orchestrator.exploration.feature_relation \
                                 import PASS, FAIL as RUN_FAIL, NO_VERDICT  # noqa E402


FILE_TEXT = """features {
    # the directories, below the directory holding hwut-root.conf
    directory_map {
        "Qm9xB_2a" = "gateway/router"
        "Zk3aT-7c" = "gateway/most"
    }
    tree {
        gateway {
            title = "CAN-MOST gateway"
            keys  = ["product"]
            childs {
                forwarding {
                    title     = "Frames reach their destination."
                    keys      = ["latency"]
                    documents = ["README.txt#3"]
                    childs {
                        "router.forward" = "Qm9xB_2a:forward"
                        "most.send"      = "Zk3aT-7c:send"
                    }
                }
                buses { title = "Both buses are served." }
            }
        }
        "new-thing" = "Qm9xB_2a:new-thing"
    }
    retired {
        "scroll-old" {
            id    = "Qm9xB_2a:scroll"
            title = "The view scrolls by one line."
            keys  = ["display"]
        }
        "old-group" {
            title  = "Gone as a group."
            childs { "old.one" { id = "Zk3aT-7c:one" title = "One." } }
        }
    }
}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _faults(text):
    """RETURN: None. Prints the faults 'text' states, one per line."""
    registry = fr.registry_of_text(text, "f")
    for fault in registry.fault_tuple:
        print("  %s" % fault)
    if not registry.fault_tuple:
        print("  no fault")
    return registry


def test_read():
    """RETURN: None. Prints the central file as read."""
    registry = fr.registry_of_text(FILE_TEXT, "f")
    banner("faults")
    print("  %d" % len(registry.fault_tuple))
    banner("directories")
    for each in registry.directory_tuple:
        print("  %s -> %s   (line %d)" % (each.id, each.path, each.line_n))
    print("  of 'gateway/most': %s" % registry.directory_of_path(
        "gateway/most").id)
    print("  of id 'nowhere1': %s" % registry.directory_of_id("nowhere1"))
    banner("leaves, with the tree path")
    for path, leaf in fr.leaf_list(registry):
        print("  %-20s %-16s %s   keys above: %s"
              % (path or "(unplaced)", leaf.external, leaf.internal,
                 fr.aggregate_key_tuple(registry, leaf.external)))
    print("  keys above a leaf that is not there: %s"
          % (fr.aggregate_key_tuple(registry, "nothing"),))
    banner("aggregates")
    for path, aggregate in fr.aggregate_list(registry):
        print("  %-20s title=%r keys=%s documents=%s"
              % (path, aggregate.title, aggregate.key_tuple,
                 aggregate.document_tuple))
    banner("retired, as they were")
    for each in registry.retired_tuple:
        print("  %-12s leaf=%-5s internal=%s title=%r keys=%s below=%s"
              % (each.name, each.leaf_f, each.internal, each.title,
                 each.key_tuple,
                 [(k.name, k.internal) for k in each.child_tuple]))
    banner("a file that is not there, and an empty one")
    print("  %s" % (fr.read_registry("/nonexistent-hwut-root"),))
    empty = fr.registry_of_text("features {\n}\n", "f")
    print("  %d directories, %d in the tree, %d retired, %d faults"
          % (len(empty.directory_tuple), len(empty.tree_tuple),
             len(empty.retired_tuple), len(empty.fault_tuple)))


def test_faults():
    """RETURN: None. Prints the faults of files that state what is not
    read."""
    cases = [
        ("a directory id of the wrong shape",
         'features { directory_map { "short" = "a/b"  "Qm9xB_2a" = "a/b" } }'),
        ("a path that leaves the root, or is none",
         'features { directory_map { "Qm9xB_2a" = "../a"  "Zk3aT-7c" = "/a"'
         '  "AAAAAAAA" = "."  "BBBBBBBB" = "a//b"  "CCCCCCCC" = 5 } }'),
        ("an unknown key, and a statement that is not a block",
         'features { directory_map = "x"  tree { }  forest { } }'),
        ("'none' in the tree, a name that is no identifier",
         'features { tree { "gone" = none  "a/b" = "Qm9xB_2a:x"'
         '  "a b" { }  "c.d" { } } }'),
        ("an internal id of the wrong shape",
         'features { tree { "a" = "x"  "b" = "Qm9xB_2a:"  "c" = "Qm9xB_2a:x:y"'
         '  "d" = "short:x"  "e" = 7 } }'),
        ("a name twice across blocks, in one namespace",
         "features {\n tree {\n  g { childs {\n   \"x\" = \"Qm9xB_2a:a\"\n  } }\n"
         "  h { childs {\n   \"x\" = \"Qm9xB_2a:b\"\n  } }\n  x { }\n"
         "  \"y\" = \"Qm9xB_2a:a\"\n }\n}\n"),
        ("an aggregate key equal to an external id",
         "features {\n tree {\n  g { childs {\n   forwarding { }\n  } }\n"
         "  \"forwarding\" = \"Qm9xB_2a:f\"\n }\n}\n"),
        ("retired, and bound again",
         "features {\n tree {\n  \"scroll-old\" = \"Qm9xB_2a:n\"\n"
         "  \"other\" = \"Qm9xB_2a:s\"\n  grp { childs {\n"
         "   \"ok\" = \"Qm9xB_2a:ok\"\n  } }\n }\n retired {\n"
         "  \"scroll-old\" { id = \"Qm9xB_2a:s\" }\n"
         "  \"grp\" { childs { \"a\" { id = \"Qm9xB_2a:a\" } } }\n }\n}\n"),
        ("retired: a leaf and an aggregate at once, no id, a bad id",
         'features { retired { "a" { id = "Qm9xB_2a:a"  childs { } }'
         '  "b" { id = "nope" }  "c" = "text"  "d" { bogus = 1 } } }'),
        ("an unknown key in an aggregate, a documents list that is none",
         'features { tree { g { title = "T"  colour = "red"'
         '  documents = "x"  keys = ["a.b"] } } }'),
        ("a file that does not parse, and one with no outer node",
         'features { tree { g { '),
        ("no outer node", 'tree { }'),
    ]
    for label, text in cases:
        banner(label)
        _faults(text)


def test_identifiers():
    """RETURN: None. Prints which texts are identifiers, external ids,
    internal ids, directory ids and paths."""
    nfd = unicodedata.normalize("NFD", "ä")        # a + combining
    word_list = ["scroll", "007", "2nd-try", "a-b", "_x", "x_", "-x", "x-",
                 "Größe", "比分", "café" + nfd,
                 "a" + nfd, "a b", "a.b", "", "a:b", "a*", "²", "x²",
                 "Abc", "abc"]
    banner("words (UAX #31 + digit at the start + '-' inside, NFC)")
    for word in word_list:
        print("  %-12s %s" % (ascii(word), fr.word_valid_f(word)))
    banner("external ids")
    for text in ["router.forward", "a", "a.b.c", ".a", "a.", "a..b", "a/b",
                 "a b", "a*", "2.0", "x:y", ""]:
        print("  %-16s %s" % (ascii(text), fr.external_id_valid_f(text)))
    banner("internal ids")
    for text in ["Qm9xB_2a:forward", "Qm9xB_2a:007", "Qm9x:forward",
                 "Qm9xB_2a:", ":forward", "Qm9xB_2a:a:b", "Qm9xB_2a:a.b",
                 "Qm9xB-2a:x", "Qm9xB/2a:x"]:
        print("  %-18s %s" % (text, fr.internal_id_split(text)))
    banner("paths below the root")
    for text in ["gateway/router", "a", ".", "", "/a", "../a", "a/../b",
                 "a//b", "a/", "./a", "a/./b"]:
        print("  %-16s %s" % (ascii(text), fr.path_valid_f(text)))
    banner("directory ids")
    for text in ["Qm9xB_2a", "Zk3aT-7c", "short", "toolong123", "Qm9xB/2a",
                 "Qm9xB+2a", "Qm9xB=2a", "--------"]:
        print("  %-12s %s" % (text, bool(fr.DIRECTORY_ID_RE.match(text))))


def test_states():
    """RETURN: None. Prints the states of leaves and of aggregates."""
    def show(label, state):
        print("  %-52s %s" % (label, state))

    banner("a leaf, from the verdicts of its runs")
    show("no run", fr.leaf_state(()))
    show("one run, passes", fr.leaf_state((PASS,)))
    show("two runs, both pass", fr.leaf_state((PASS, PASS)))
    show("two runs, one fails", fr.leaf_state((PASS, RUN_FAIL)))
    show("one run, no verdict yet", fr.leaf_state((NO_VERDICT,)))
    show("retired", fr.retired_state())
    banner("an aggregate, from the states below it")
    ok  = fr.leaf_state((PASS,))
    bad = fr.leaf_state((RUN_FAIL,))
    opn = fr.leaf_state(())
    ret = fr.retired_state()
    show("nothing below (assumed OPEN)", fr.aggregate_state(()))
    show("ok, ok", fr.aggregate_state((ok, ok)))
    show("ok, fail", fr.aggregate_state((ok, bad)))
    show("ok, open", fr.aggregate_state((ok, opn)))
    show("fail, open", fr.aggregate_state((bad, opn)))
    show("retired, retired", fr.aggregate_state((ret, ret)))
    show("ok, retired (the retired are ignored)",
         fr.aggregate_state((ok, ret)))
    show("open, retired", fr.aggregate_state((opn, ret)))
    show("fail, retired", fr.aggregate_state((bad, ret)))
    banner("aggregates of aggregates")
    inner_ok  = fr.aggregate_state((ok, ok))
    inner_bad = fr.aggregate_state((ok, bad))
    inner_ret = fr.aggregate_state((ret,))
    show("[ok,ok] and [ok,fail]", fr.aggregate_state((inner_ok, inner_bad)))
    show("[ok,ok] and [retired]", fr.aggregate_state((inner_ok, inner_ret)))
    show("[retired] alone", fr.aggregate_state((inner_ret,)))


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The central feature file: directory_map, tree, "
                     "retired, identifiers, states",
        choice_map = {
            "read":        test_read,
            "faults":      test_faults,
            "identifiers": test_identifiers,
            "states":      test_states,
        },
    ).run()

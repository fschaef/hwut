#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.features.init, register and tree on scratch trees"
#     choices {
#         init     { features = ["init-writes"] }
#         register { features = ["register-adds"] }
#         tree     { features = ["tree-prints"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE FACES of the central file (spec 23 VERSION 10 section 8,
         R-96), each called as a person calls it, on a scratch tree; the
         random directory ids stand in for counted ones so the pages hold.

CHOICES: init, register, tree;

init      the file written -- header, directory ids, leaves unplaced --;
          refused where it stands, where files of the past stand, where no
          'hwut-root.conf' stands, and for a word it does not take.

register  nothing to register; a new feature; a new directory below a
          directory named, and the one outside not touched; a directory
          moved (named, not acted on, exit 1); no central file; a central
          file with a fault (nothing written); a directory outside the root.

tree      the tree with titles, '-e', '--list', '-b', a base, a base that is
          no aggregate, '--list' with '-b'.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.services.lib.features import init, register, tree    # noqa E402


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def _features(root, component, pair_list):
    """RETURN: None. 'component/TEST/hwut-features.conf' defining the
    (name, title) pairs."""
    _write(root, component + "/TEST/hwut-features.conf",
           "features {\n  childs {\n%s  }\n}\n" % "".join(
               '    %s { title = "%s" }\n' % pair for pair in pair_list))


def _tree():
    """RETURN: str, the root of a scratch tree: 'gw/can' (decode, encode),
    'gw/most' (send)."""
    root = tempfile.mkdtemp(prefix="hwut-features-")
    _ROOT_LIST.append(root)
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _features(root, "gw/can", [("decode", "A frame is decoded."),
                               ("encode", "A frame is encoded.")])
    _features(root, "gw/most", [("send", "A message is sent.")])
    return root


class _Counter:
    """Stands in for the random source: 6 bytes counting up."""

    def __init__(self):
        """RETURN: None."""
        self.n = 0

    def __call__(self):
        """RETURN: bytes, the next 6 bytes."""
        self.n += 1
        return bytes([65, 65, 65, 65, 65, 64 + self.n])


_ROOT_LIST = []


def _masked(text):
    """RETURN: str, 'text' with every scratch root written '<root>': the
    page must not depend on where the temporary directory lay."""
    for root in _ROOT_LIST:
        text = text.replace(os.path.realpath(root), "<root>") \
                   .replace(root, "<root>")
    return text


def _call(label, face, argv, directory, **kw):
    """RETURN: None. Calls 'face.main' in 'directory', prints what it wrote
    and its exit status."""
    print(">>> %s" % label)
    here = os.getcwd()
    os.chdir(directory)
    try:
        code = face.main(argv, write=lambda text: print(
            "    " + _masked(text).replace("\n", "\n    ")), **kw)
    finally:
        os.chdir(here)
    print("    exit %d" % int(code))


def _file(root):
    """RETURN: None. Prints the central file below its header."""
    with open(os.path.join(root, "hwut-root-features.conf")) as fh:
        text = fh.read()
    print("    | " + "\n    | ".join(text[text.index("features {"):]
                                      .rstrip("\n").split("\n")))


ID_LIST = ["Aaaaaaa1", "Bbbbbbb2", "Ccccccc3"]


def test_init():
    """RETURN: None. Prints what 'hwut.features.init' writes and refuses."""
    root = _tree()
    try:
        banner("written")
        _call("hwut.features.init", init, [], root, id_list=ID_LIST)
        with open(os.path.join(root, "hwut-root-features.conf")) as fh:
            text = fh.read()
        print("    header: %d comment lines, first: %s"
              % (len([l for l in text.split("\n") if l.startswith("#")]),
                 text.split("\n")[0]))
        _file(root)
        banner("refused")
        _call("it stands already", init, [], root)
        _call("a word it does not take", init, ["gw"], root)
        os.remove(os.path.join(root, "hwut-root-features.conf"))
        _write(root, "gw/hwut-features.conf", 'features {\n title = "G"\n}\n')
        _write(root, "hwut-feature-map.conf", "map {\n}\n")
        _call("files of the past stand", init, [], os.path.join(root, "gw"))
        print("    written: %s" % os.path.exists(
            os.path.join(root, "hwut-root-features.conf")))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    #  OUTSIDE EVERY TREE: under 'hwut.run' the temporary directory lies
    #  inside the tree tested, and its 'hwut-root.conf' would be found.
    nowhere = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _ROOT_LIST.append(nowhere)
    try:
        _call("no hwut-root.conf", init, [], nowhere)
    finally:
        shutil.rmtree(nowhere, ignore_errors=True)


def test_register():
    """RETURN: None. Prints what 'hwut.features.register' adds and names."""
    root = _tree()
    try:
        _call("no central file", register, [], root)
        here = os.getcwd()
        os.chdir(root)
        init.main([], write=lambda text: None, id_list=ID_LIST[:2])
        os.chdir(here)
        banner("adding")
        _call("nothing to register", register, [], root)
        _features(root, "gw/can", [("decode", "A frame is decoded."),
                                   ("encode", "A frame is encoded."),
                                   ("reset", "The decoder is reset.")])
        _features(root, "gw/router", [("forward", "A frame is forwarded.")])
        _features(root, "misc", [("x", "X.")])
        _call("below 'gw': a new feature, a new directory; 'misc' not "
              "touched", register, ["gw"], root, token=_Counter())
        _call("from 'misc' itself", register, [], os.path.join(root, "misc"),
              token=_Counter())
        _file(root)
        banner("disagreements are named, not acted on")
        os.rename(os.path.join(root, "gw/can"),
                  os.path.join(root, "gw/bus-can"))
        _call("gw/can moved to gw/bus-can", register, [], root)
        _call("only below 'misc'", register, ["misc"], root)
        banner("refused")
        _call("two directories", register, ["gw", "misc"], root)
        _call("an option it does not take", register, ["--force"], root)
        _call("a directory outside the root", register, [".."], root)
        _call("no such directory", register, ["nowhere"], root)
        with open(os.path.join(root, "hwut-root-features.conf"), "a") as fh:
            fh.write("extra { }\n")
        _call("the central file states a fault", register, [], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_tree():
    """RETURN: None. Prints the tree in its forms."""
    root = _tree()
    try:
        _features(root, "gw/router", [("forward", "A frame is forwarded.")])
        _write(root, "hwut-root-features.conf", """features {
    directory_map {
        "Aaaaaaa1" = "gw/can"
        "Bbbbbbb2" = "gw/most"
        "Ccccccc3" = "gw/router"
    }
    tree {
        gateway {
            title  = "CAN-MOST gateway"
            childs {
                forwarding {
                    title  = "Frames reach their destination."
                    childs {
                        "router.forward" = "Ccccccc3:forward"
                        "most.send"      = "Bbbbbbb2:send"
                    }
                }
                buses {
                    childs { "can.decode" = "Aaaaaaa1:decode" }
                }
            }
        }
        "can.encode" = "Aaaaaaa1:encode"
    }
    retired {
        "old" { id = "Aaaaaaa1:old"  title = "Gone." }
    }
}
""")
        for argv in ([], ["-e"], ["--list"], ["-b"],
                     ["gateway/forwarding"], ["gateway/forwarding", "--list"],
                     ["gateway/buses", "-b"], ["nope"],
                     ["--list", "-b"], ["-x"]):
            _call("hwut.features.tree %s" % " ".join(argv), tree, argv, root)
        _write(root, "hwut-root-features.conf", "features {\n tree { }\n}\n")
        _call("an empty tree", tree, [], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.features.init, register and tree on scratch trees",
        choice_map = {
            "init":     test_init,
            "register": test_register,
            "tree":     test_tree,
        },
    ).run()

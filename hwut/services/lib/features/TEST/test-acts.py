#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.features.retire, move, key.add, key.remove on scratch trees"
#     choices {
#         retire { features = ["retire-moves"] }
#         move   { features = ["move-follows"] }
#         keys   { features = ["keys-edited"] }
#         rename { }
#         held   { }
#         root   { }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE FACES THAT TOUCH MORE THAN THE CENTRAL FILE (spec 23
         VERSION 10 sections 3, 8, 9; R-96), called as a person calls them
         on a scratch tree; after each act the files it touched are printed.

CHOICES: retire, move, keys, rename, held, root;

retire  a leaf: its line and its definition leave, a block in 'retired'
        holds both as they were; an aggregate with everything below it,
        re-indented to its new place; a leaf whose definition stood
        nowhere; refused: a retired id, an unknown id, two words. The
        result is read again: no fault, and the retired ids are never
        bound again.

move    a directory and the 'directory_map' lines at and below it; a
        parent with two registered directories below; a directory without
        an id; refused: a target that stands, one inside the source, a
        parent that does not stand, the root, a directory that does not
        stand, one outside the root.

keys    a key added to a leaf (in its TEST directory) and to an aggregate
        (in the central file); taken off again; a key from above is not
        taken off the claim below; '--all' over aggregates, definitions
        and a file's keys for all its features; refused: a key that is no
        key, a key stated already, '--all' of a key no claim states.
rename  'hwut.features.rename <external id> <new name>': the definition in
        its TEST directory, every link in that directory's test headers,
        the leaf's internal id -- the external id stays; two renames in
        one directory; afterwards 'register' finds nothing. Refused: a
        name defined already, an aggregate, no word, an unknown id
        (the book's D-7).

held    the same two renames BY HAND: 'register' writes NO line -- the
        two new names are the candidates of the two gone and are held,
        each side naming the other (it registered both and said
        'candidates: none', the book's D-7). One gone retired, still held;
        both retired, the new are registered.

root    the root's own TEST directory defines 'shot' and 'gateway':
        'register' gives it a directory id standing for '.', and its
        leaves bare names -- 'gateway' clashes with the aggregate and
        is qualified; again, nothing more is registered (the scratch
        tree's own 'can.ghost' is said); the root is not moved. MEASURED 2026-10-19 before (the book's D-3): nothing
        registered, the hint 'root-test'.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.services.lib.features import retire, move, tree       # noqa E402
from hwut.services.lib.features import rename, register         # noqa E402
from hwut.services.lib.features.key import add, remove          # noqa E402
from hwut.engine.orchestrator.exploration.feature_registry \
                                         import read_registry   # noqa E402

CENTRAL = """features {
    directory_map {
        "Aaaaaaa1" = "gw/can"
        "Bbbbbbb2" = "gw/most"
    }
    tree {
        gateway {
            title = "CAN-MOST gateway"
            keys  = ["product"]
            childs {
                can {
                    childs {
                        "can.decode" = "Aaaaaaa1:decode"
                        "can.encode" = "Aaaaaaa1:encode"
                    }
                }
                most {
                    title = "MOST side"
                    childs {
                        "most.send"    = "Bbbbbbb2:send"
                        "most.receive" = "Bbbbbbb2:receive"
                    }
                }
            }
        }
        "can.ghost" = "Aaaaaaa1:ghost"
    }
    retired {
    }
}
"""

CAN = """features {
  keys = ["bus"]
  childs {
    decode { title = "A frame is decoded."
             keys  = ["latency"] }
    encode { title = "A frame is encoded."
             doc   = \"\"\"
                 Both directions.
                 \"\"\" }
  }
}
"""

MOST = """features {
  childs {
    send    { title = "A message is sent." }
    receive { title = "A message arrives."  keys = ["bus"] }
  }
}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def _tree():
    """RETURN: str, the root of a scratch tree with the central file above."""
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "gw/can/TEST/hwut-features.conf", CAN)
    _write(root, "gw/most/TEST/hwut-features.conf", MOST)
    _write(root, "hwut-root-features.conf", CENTRAL)
    return root


def _call(label, face, argv, root):
    """RETURN: None. Calls 'face.main' at 'root', prints what it wrote and
    its exit status."""
    print(">>> %s" % label)
    here = os.getcwd()
    os.chdir(root)
    try:
        code = face.main(argv, write=lambda text: print(
            "    " + text.replace(root, "<root>").replace("\n", "\n    ")))
    finally:
        os.chdir(here)
    print("    exit %d" % int(code))


def _show(root, *path_list):
    """RETURN: None. Prints the files 'path_list' below 'root'."""
    for path in path_list:
        print("    %s:" % path)
        with open(os.path.join(root, path)) as fh:
            text = fh.read()
        if path == "hwut-root-features.conf":
            text = text[text.index("features {"):]
        print("    | " + "\n    | ".join(text.rstrip("\n").split("\n")))


def _sound(root):
    """RETURN: None. Prints whether the central file is read without a
    fault, and what it retired."""
    registry = read_registry(root)
    print("    read again: %d fault(s); retired: %s"
          % (len(registry.fault_tuple),
             ", ".join(each.name for each in registry.retired_tuple)
             or "none"))


def test_retire():
    """RETURN: None. Prints what retiring does to the files."""
    root = _tree()
    try:
        banner("a leaf")
        _call("hwut.features.retire can.encode", retire, ["can.encode"], root)
        _show(root, "hwut-root-features.conf",
              "gw/can/TEST/hwut-features.conf")
        _sound(root)
        banner("an aggregate with everything below it")
        _call("hwut.features.retire most", retire, ["most"], root)
        _show(root, "hwut-root-features.conf",
              "gw/most/TEST/hwut-features.conf")
        _sound(root)
        banner("a leaf whose definition stood nowhere")
        _call("hwut.features.retire can.ghost", retire, ["can.ghost"], root)
        _sound(root)
        banner("refused")
        _call("retired already", retire, ["can.encode"], root)
        _call("a retired aggregate", retire, ["most"], root)
        _call("no claim of the tree", retire, ["nothing"], root)
        _call("two words", retire, ["can.decode", "most"], root)
        _call("no word", retire, [], root)
        banner("the tree left")
        _call("hwut.features.tree -e", tree, ["-e"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


_LINKER = """#! /bin/sh
# @hwut {
#     title    = "Codec"
#     choices {
#         one { features = ["decode", "encode"] }
#         two { features = ["encode"] }
#     }
# }
echo x
"""


def _linked_tree():
    """RETURN: str, the scratch tree with a test in 'gw/can/TEST' linking
    'decode' and 'encode'."""
    root = _tree()
    _write(root, "gw/can/TEST/test-codec.sh", _LINKER)
    os.chmod(os.path.join(root, "gw/can/TEST/test-codec.sh"), 0o755)
    return root


def test_rename():
    """RETURN: None. Prints what renaming a feature does to the files."""
    root = _linked_tree()
    try:
        banner("two features of one directory renamed")
        _call("hwut.features.rename can.decode parse", rename,
              ["can.decode", "parse"], root)
        _call("hwut.features.rename can.encode render", rename,
              ["can.encode", "render"], root)
        _show(root, "hwut-root-features.conf",
              "gw/can/TEST/hwut-features.conf", "gw/can/TEST/test-codec.sh")
        _sound(root)
        _call("hwut.features.register", register, [], root)
        banner("refused")
        _call("defined already", rename, ["can.decode", "render"], root)
        _call("an aggregate", rename, ["can", "x"], root)
        _call("no word", rename, ["can.decode", "a b"], root)
        _call("no claim of the tree", rename, ["nothing", "x"], root)
        _call("one word", rename, ["can.decode"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_held():
    """RETURN: None. Prints what 'register' does after two renames by
    hand."""
    root = _linked_tree()
    try:
        for path, old, new in (
                ("gw/can/TEST/hwut-features.conf", "decode {", "parse {"),
                ("gw/can/TEST/hwut-features.conf", "encode {", "render {"),
                ("gw/can/TEST/test-codec.sh", '"decode"', '"parse"'),
                ("gw/can/TEST/test-codec.sh", '"encode"', '"render"')):
            full = os.path.join(root, path)
            with open(full) as fh: text = fh.read()
            with open(full, "w") as fh: fh.write(text.replace(old, new))
        _call("hwut.features.retire can.ghost  (a leaf with no definition)",
              retire, ["can.ghost"], root)
        banner("two renames by hand: nothing written")
        _call("hwut.features.register", register, [], root)
        _show(root, "hwut-root-features.conf")
        banner("one gone retired: one gone, two new -- still held")
        _call("hwut.features.retire can.encode", retire, ["can.encode"],
              root)
        _call("hwut.features.register", register, [], root)
        banner("both retired: the new are registered")
        _call("hwut.features.retire can.decode", retire, ["can.decode"],
              root)
        _call("hwut.features.register", register, [], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_root():
    """RETURN: None. Prints what 'register' makes of the root's own TEST
    directory."""
    from hwut.engine.orchestrator.exploration.feature_registry_act \
        import register as act_register
    root = _tree()
    try:
        _write(root, "TEST/hwut-features.conf", """features {
  childs {
    shot    { title = "A held key ends in a rolling ball." }
    gateway { title = "The whole gateway forwards." }
  }
}
""")
        banner("register: an id for '.', bare names, a clash qualified")
        directory_list, leaf_list, found = act_register(
            root, token=lambda: b"\x00" * 6)
        for directory_id, path in directory_list:
            print("    directory  %s = %s" % (directory_id, path))
        for external, internal in leaf_list:
            print("    leaf       %s = %s" % (external, internal))
        print("    then: %s" % (", ".join(each.kind for each in found)
                                or "nothing found"))
        _call("hwut.features.register  (again)", register, [], root)
        _call("hwut.features.move . elsewhere", move, [".", "elsewhere"],
              root)
        _sound(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_move():
    """RETURN: None. Prints what moving a directory does."""
    root = _tree()
    try:
        os.makedirs(os.path.join(root, "gw/plain"))
        banner("moved, the lines follow")
        _call("hwut.features.move gw/can gw/bus-can", move,
              ["gw/can", "gw/bus-can"], root)
        _call("a parent with two registered directories below: gw -> gateway",
              move, ["gw", "gateway"], root)
        _call("a directory without an id", move,
              ["gateway/plain", "gateway/plain-2"], root)
        _show(root, "hwut-root-features.conf")
        print("    stands: %s" % ", ".join(sorted(
            os.listdir(os.path.join(root, "gateway")))))
        banner("refused")
        _call("the target stands", move, ["gateway/most", "gateway/bus-can"],
              root)
        _call("the target inside the source", move,
              ["gateway", "gateway/x"], root)
        _call("its parent does not stand", move, ["gateway/most", "a/b"],
              root)
        _call("the root", move, [".", "x"], root)
        _call("no such directory", move, ["nowhere", "x"], root)
        _call("outside the root", move, ["gateway", "../x"], root)
        _call("one word", move, ["gateway"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_keys():
    """RETURN: None. Prints what adding and removing keys does."""
    root = _tree()
    try:
        banner("added")
        _call("on a leaf", add, ["can.decode", "safety"], root)
        _call("on a leaf without keys", add, ["most.send", "slow"], root)
        _call("on an aggregate", add, ["most", "nightly"], root)
        _show(root, "gw/can/TEST/hwut-features.conf",
              "gw/most/TEST/hwut-features.conf")
        banner("taken off")
        _call("its own", remove, ["can.decode", "latency"], root)
        _call("one from above is not its own", remove,
              ["can.decode", "product"], root)
        _call("on an aggregate", remove, ["most", "nightly"], root)
        banner("--all")
        _call("--all bus: a definition and a whole file", remove,
              ["--all", "bus"], root)
        _show(root, "gw/can/TEST/hwut-features.conf",
              "gw/most/TEST/hwut-features.conf")
        _call("--all product: an aggregate", remove, ["--all", "product"],
              root)
        _sound(root)
        banner("refused")
        _call("no key", add, ["can.decode", "a.b"], root)
        _call("stated already", add, ["can.decode", "safety"], root)
        _call("a key it does not state", remove, ["can.decode", "zzz"], root)
        _call("--all of a key no claim states", remove, ["--all", "zzz"],
              root)
        _call("--all with two keys", remove, ["--all", "a", "b"], root)
        _call("an unknown id", add, ["nothing", "k"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.features.retire, move, key.add, key.remove on "
                     "scratch trees",
        choice_map = {
            "retire": test_retire,
            "move":   test_move,
            "keys":   test_keys,
            "rename": test_rename,
            "held":   test_held,
            "root":   test_root,
        },
    ).run()

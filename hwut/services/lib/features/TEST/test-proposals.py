#! /usr/bin/env python3
#
# @hwut {
#     title      = "The detector's proposals through hwut.sanitize; the hint of hwut.run, said out by hwut.help"
#     choices {
#         propose { features = ["sanitize-proposes"] }
#         apply   { features = ["sanitize-applies"] }
#         verbs   { features = ["sanitize-applies"] }
#         hint    { features = ["run-hints-registration"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CENTRAL FILE OF FEATURES HEALED THROUGH 'hwut.sanitize' (spec
         23 VERSION 10 section 7, R-96) -- the detector's proposals as lines
         of a proposal, done by 'hwut.sanitize.apply' and one by one by
         'hwut.sanitize <verb>' -- and the one line 'hwut.run' ends with
         where features are not registered, said out by 'hwut.help'. Every
         face is called by its launcher, as a person calls it, on a scratch
         tree outside every other tree.

CHOICES: propose, apply, verbs, hint;

propose  a directory moved and a leaf renamed in it, a new directory, a
         twin: one line each, the old value in the note; what cannot be
         paired is a NOTE on stderr, no line; a tree in agreement proposes
         nothing (exit 3).

apply    the proposal done; afterwards register finds nothing; a swap of two
         directories applied as two lines, the second NOTHING.

verbs    one verb at a time: a line the detector proposes no more is
         NOTHING; 'register' of a directory; no central file: refused.

hint     'hwut.run' without a central file says nothing; with every feature
         registered nothing; a feature renamed and a directory new: the
         count, for the tree and for a directory below; 'hwut.help' names
         them.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))
BIN  = os.path.normpath(os.path.join(HERE, "../../../../bin"))


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def _features(root, component, name_list):
    """RETURN: None. 'component/TEST/hwut-features.conf' defining the names,
    each titled by itself."""
    _write(root, component + "/TEST/hwut-features.conf",
           "features {\n  childs {\n%s  }\n}\n" % "".join(
               '    %s { title = "%s." }\n' % (name, name)
               for name in name_list))


def _central(root, directory_db, leaf_list):
    """RETURN: None. The central file: 'directory_db' id -> path, the
    leaves (external, internal) unplaced."""
    _write(root, "hwut-root-features.conf", "features {\n  directory_map {\n"
           + "".join('    "%s" = "%s"\n' % pair
                     for pair in directory_db.items())
           + "  }\n  tree {\n"
           + "".join('    "%s" = "%s"\n' % pair for pair in leaf_list)
           + "  }\n  retired {\n  }\n}\n")


def _tree(with_central_f=True):
    """RETURN: str, a scratch tree outside every other tree: gw/can (decode,
    encode), gw/most (send, receive), each registered."""
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _write(root, "hwut-root.conf",
           'hwut {\n    language-setup { bash { extensions = [".sh"] '
           'interpreter = "bash" } }\n}\n')
    _features(root, "gw/can", ["decode", "encode"])
    _features(root, "gw/most", ["send", "receive"])
    if with_central_f:
        _central(root, {"Aaaaaaa1": "gw/can", "Bbbbbbb2": "gw/most"},
                 [("can.decode", "Aaaaaaa1:decode"),
                  ("can.encode", "Aaaaaaa1:encode"),
                  ("most.send", "Bbbbbbb2:send"),
                  ("most.receive", "Bbbbbbb2:receive")])
    return root


def _id_set(root):
    """RETURN: set of str, the directory ids the central file of 'root'
    holds now; empty where it does not stand."""
    from hwut.engine.orchestrator.exploration.feature_registry \
                                         import read_registry
    registry = read_registry(root)
    return set() if registry is None else {
        each.id for each in registry.directory_tuple}


def _face(root, label, *argv, cwd=None, keep=None):
    """RETURN: None. Calls the launcher 'argv[0]' in 'root' (or 'cwd'), and
    prints its exit status and what it wrote -- the lines matching 'keep'
    only, where 'keep' is given; stderr after 'err:'."""
    print(">>> %s" % label)
    environment = dict(os.environ, PYTHONPATH="")
    before = _id_set(root)
    done = subprocess.run([os.path.join(BIN, argv[0])] + list(argv[1:]),
                          cwd=cwd or root, capture_output=True, text=True,
                          env=environment, stdin=subprocess.DEVNULL)
    #  A GENERATED ID IS RANDOM: the page names it '<new id>'.
    fresh = sorted(_id_set(root) - before)
    for stream, head in ((done.stdout, ""), (done.stderr, "err: ")):
        for each in fresh:
            stream = stream.replace(each, "<new id>")
        for line in stream.rstrip("\n").split("\n"):
            if not line.strip(): continue
            if keep is not None and keep not in line: continue
            print("    %s%s" % (head, line.replace(root, "<root>")
                                         .replace(os.path.realpath(root),
                                                  "<root>")))
    print("    exit %d" % done.returncode)


def _commands(path):
    """RETURN: None. Prints the lines of a proposal file that are commands
    (not '#')."""
    with open(path) as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                print("    | " + line.rstrip("\n"))


def _changed(root):
    """RETURN: None. gw/can moved to gw/bus-can, 'encode' renamed there to
    'encode-frame'; misc/ new."""
    os.rename(os.path.join(root, "gw/can"), os.path.join(root, "gw/bus-can"))
    _features(root, "gw/bus-can", ["decode", "encode-frame"])
    _features(root, "misc", ["x"])


def test_propose():
    """RETURN: None. Prints what 'hwut.sanitize.propose --relations'
    proposes for the central file."""
    root = _tree()
    try:
        banner("in agreement")
        _face(root, "nothing to propose", "hwut.sanitize.propose",
              "--relations", keep="")
        banner("moved, renamed, new")
        _changed(root)
        _face(root, "proposed", "hwut.sanitize.propose", "--relations",
              "-o", "heal.txt")
        _commands(os.path.join(root, "heal.txt"))
        banner("what cannot be paired: a note, no line")
        _features(root, "gw/bus-can", ["decode-frame", "encode-frame"])
        _face(root, "moved, and every feature renamed: nothing to pair by", "hwut.sanitize.propose",
              "--relations", "-o", "heal.txt")
        _commands(os.path.join(root, "heal.txt"))
        banner("one path, two ids")
        _central(root, {"Aaaaaaa1": "gw/most", "Ccccccc3": "gw/most"},
                 [("most.send", "Aaaaaaa1:send"),
                  ("most.receive", "Aaaaaaa1:receive"),
                  ("most.send-2", "Ccccccc3:send")])
        _face(root, "a twin", "hwut.sanitize.propose", "--relations",
              "-o", "heal.txt")
        _commands(os.path.join(root, "heal.txt"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply():
    """RETURN: None. Prints what applying the proposal does."""
    root = _tree()
    try:
        _changed(root)
        _face(root, "propose", "hwut.sanitize.propose", "--relations",
              "-o", "heal.txt")
        _face(root, "apply", "hwut.sanitize.apply", "heal.txt")
        _face(root, "register afterwards", "hwut.features.register")
        _face(root, "the tree", "hwut.features.tree", "-e")
        banner("a swap: two lines, the second NOTHING")
        os.rename(os.path.join(root, "gw/bus-can"), os.path.join(root, "t"))
        os.rename(os.path.join(root, "gw/most"),
                  os.path.join(root, "gw/bus-can"))
        os.rename(os.path.join(root, "t"), os.path.join(root, "gw/most"))
        _face(root, "propose", "hwut.sanitize.propose", "--relations",
              "-o", "swap.txt")
        _commands(os.path.join(root, "swap.txt"))
        _face(root, "apply", "hwut.sanitize.apply", "swap.txt")
        _face(root, "register afterwards", "hwut.features.register")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_verbs():
    """RETURN: None. Prints the verbs done one at a time."""
    root = _tree()
    try:
        _changed(root)
        _face(root, "a redirect the detector proposes", "hwut.sanitize",
              "redirect", "Aaaaaaa1", "gw/bus-can")
        _face(root, "the same once more: proposed no more", "hwut.sanitize",
              "redirect", "Aaaaaaa1", "gw/bus-can")
        _face(root, "a repoint to another name than proposed",
              "hwut.sanitize", "repoint", "can.encode", "Aaaaaaa1:decode")
        _face(root, "the repoint proposed", "hwut.sanitize", "repoint",
              "can.encode", "Aaaaaaa1:encode-frame")
        _face(root, "register misc", "hwut.sanitize", "register", "misc")
        _face(root, "register misc again", "hwut.sanitize", "register",
              "misc")
        _face(root, "fold, nothing twin", "hwut.sanitize", "fold",
              "Aaaaaaa1", "Bbbbbbb2")
        _face(root, "a word too few", "hwut.sanitize", "repoint",
              "can.encode")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    root = _tree(with_central_f=False)
    try:
        _face(root, "no central file: register", "hwut.sanitize",
              "register", "gw/can")
        _face(root, "no central file: redirect", "hwut.sanitize",
              "redirect", "Aaaaaaa1", "gw/can")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_hint():
    """RETURN: None. Prints the one line 'hwut.run' ends with, and what
    'hwut.help' says of it."""
    root = _tree(with_central_f=False)
    try:
        _write(root, "gw/can/TEST/test-d.sh",
               '#! /bin/bash\n# @hwut {\n#     title = "d"\n'
               '#     features = ["decode"]\n# }\necho ok\n'
               'echo "<hwut-end>"\n')
        os.chmod(os.path.join(root, "gw/can/TEST/test-d.sh"), 0o755)
        keep = "not registered"
        _face(root, "accepted, so the help speaks of nothing else",
              "hwut.accept", "--dont-ask", "--force", keep="ACCEPTED")
        _face(root, "no central file", "hwut.run", "--silent", keep=keep)
        _face(root, "init", "hwut.features.init", keep="written")
        _face(root, "every feature registered", "hwut.run", "--silent",
              keep=keep)
        _changed(root)
        _face(root, "renamed, moved, new: the tree", "hwut.run", "--silent",
              keep=keep)
        _face(root, "below gw only", "hwut.run", "--silent", keep=keep,
              cwd=os.path.join(root, "gw"))
        _face(root, "hwut.help", "hwut.help", keep="")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The detector's proposals through hwut.sanitize; the "
                     "hint of hwut.run, said out by hwut.help",
        choice_map = {
            "propose": test_propose,
            "apply":   test_apply,
            "verbs":   test_verbs,
            "hint":    test_hint,
        },
    ).run()

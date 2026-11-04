#! /usr/bin/env python3
#
# @hwut {
#     title      = "One registry spans the bubbles that have none of their own"
#     choices {
#         register { features = ["registry-spans-bubbles"] }
#         view     { features = ["registry-spans-bubbles"] }
#         begin    { features = ["registry-begun-in-a-bubble"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A BUBBLE WITHOUT A REGISTRY OF ITS OWN BELONGS TO THE NEAREST ONE
         ABOVE IT (ruled 2026-11-03 for plan/42 P-8, against a
         'hwut.features.split'); a bubble with one is a registry of its
         own. The scratch tree:

    .                  hwut-root.conf, hwut-root-features.conf
    gw/can/TEST        decode, encode
    inner/             hwut-root.conf -- no registry
    inner/x/TEST       read
    own/               hwut-root.conf, hwut-root-features.conf
    own/y/TEST         write

CHOICES: register, view, begin;

register  'hwut.features.init' at the top registers 'inner/x' and not
          'own/y'; the NOTE names 'own/' alone; 'register' called inside
          'inner/' works on the top's file, nothing new below 'inner'.
view      the features view from the top and from inside 'inner/': the
          top's registry, the TEST directories, every leaf with its TEST
          directory -- 'own/y' in neither; 'hwut.sanitize's registry
          issues inside 'inner/': the NOTE that the top's file governs.
begin     'hwut.features.init' inside 'inner/' begins a registry there,
          the bubble's own (the nearest 'hwut-root.conf'); from then on
          the top's file names 'inner/x' as a directory gone.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.services.lib.features import init, register            # noqa E402
from hwut.engine.orchestrator.exploration.feature_view import view_of  # noqa E402
from hwut.services.sanitize import registry_issue_list           # noqa E402

_ROOT_LIST = []


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
    """RETURN: None. 'component/TEST/hwut-features.conf' defining the
    names of 'name_list'."""
    _write(root, component + "/TEST/hwut-features.conf",
           "features {\n  childs {\n%s  }\n}\n" % "".join(
               '    %s { title = "%s." }\n' % (name, name.capitalize())
               for name in name_list))


def _masked(text):
    """RETURN: str, 'text' with every scratch root written '<root>'."""
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


def _tree():
    """RETURN: str, the root of the scratch tree of the PURPOSE, the
    registries of the top and of 'own/' written by 'hwut.features.init'."""
    root = tempfile.mkdtemp(prefix="hwut-features-span-")
    _ROOT_LIST.append(root)
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _features(root, "gw/can", ["decode", "encode"])
    _write(root, "inner/hwut-root.conf", "hwut {\n}\n")
    _features(root, "inner/x", ["read"])
    _write(root, "own/hwut-root.conf", "hwut {\n}\n")
    _features(root, "own/y", ["write"])
    here = os.getcwd()
    try:
        os.chdir(os.path.join(root, "own"))
        init.main([], write=lambda text: None, id_list=["Ooooooo1"])
    finally:
        os.chdir(here)
    return root


def _map(root, where="."):
    """RETURN: None. Prints the 'directory_map' of the registry at
    'root/where'."""
    with open(os.path.join(root, where, "hwut-root-features.conf")) as fh:
        text = fh.read()
    body = text[text.index("directory_map {"):]
    body = body[:body.index("}") + 1]
    print("    %s: %s" % (where, " ".join(body.split())))


def test_register():
    """RETURN: None. The top's file spans 'inner/', not 'own/'."""
    root = _tree()
    try:
        _call("hwut.features.init at the top", init, [], root,
              id_list=["Aaaaaaa1", "Bbbbbbb2"])
        _map(root)
        _call("hwut.features.register at the top", register, [], root)
        _call("hwut.features.register inside 'inner/'", register, [],
              os.path.join(root, "inner"))
        _features(root, "inner/x", ["read", "seek"])
        _call("a feature added in 'inner/x', registered from 'inner/'",
              register, [], os.path.join(root, "inner"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _view(asked):
    """RETURN: None. Prints the view of 'asked': its top, its TEST
    directories, its leaves."""
    view = view_of(asked)
    print("    top        %s" % _masked(view.top))
    print("    TEST       %s" % ", ".join(sorted(
        view.relation.test_directory_db)))
    for each in sorted(view.leaf_list(), key=lambda l: l.leaf.external):
        print("    leaf       %-14s %-20s %s"
              % (each.leaf.external, each.leaf.internal, each.test_path))


def test_view():
    """RETURN: None. The view from the top and from inside 'inner/'."""
    root = _tree()
    try:
        here = os.getcwd()
        os.chdir(root)
        init.main([], write=lambda text: None,
                  id_list=["Aaaaaaa1", "Bbbbbbb2"])
        os.chdir(here)
        banner("from the top")
        _view(root)
        banner("from inside 'inner/'")
        _view(os.path.join(root, "inner"))
        banner("hwut.sanitize inside 'inner/'")
        issue_list, note_list = registry_issue_list(os.path.join(root,
                                                                 "inner"))
        print("    issues %d" % len(issue_list))
        for note in note_list: print("    %s" % _masked(note))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_begin():
    """RETURN: None. A registry begun inside 'inner/'."""
    root = _tree()
    try:
        here = os.getcwd()
        os.chdir(root)
        init.main([], write=lambda text: None,
                  id_list=["Aaaaaaa1", "Bbbbbbb2"])
        os.chdir(here)
        _call("hwut.features.init inside 'inner/'", init, [],
              os.path.join(root, "inner"), id_list=["Iiiiiii1"])
        _map(root, "inner")
        _call("hwut.features.register at the top", register, [], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "One registry spans the bubbles that have none of "
                     "their own",
        choice_map = {
            "register": test_register,
            "view":     test_view,
            "begin":    test_begin,
        },
    ).run()

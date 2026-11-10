"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A SCRATCH TREE OF FEATURES for the pages of the feature view and
         the detector: the three files at the top, tests linking ids, the
         book verdicts written by the bookkeeper. Not a test application
         ('hwut-info.dat' says so).

    tree(forest, doc, external=None, link_db=None, verdict_db=None) -> root
    removed()                                   every tree made, gone
______________________________________________________________________________
"""
import os
import shutil
import tempfile

_ROOT_LIST = []


def write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def test(root, path, body):
    """RETURN: None. A shell test at 'root/path' whose block holds the
    lines of 'body'."""
    write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
          % "\n".join("#     " + line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def tree(forest, doc, external=None, test_db=None, verdict_db=None):
    """
    RETURN: str, the root of a new scratch tree: 'hwut-root.conf', the
            forest and doc file as given ('external' the map, None: none),
            the tests of 'test_db' (path -> lines of its block), and the
            verdicts of 'verdict_db' ((TEST directory, test, choice) ->
            True pass, False fail, None aspirant) written by the book.
    """
    from hwut.engine.bookkeeper.api import Bookkeeper
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _ROOT_LIST.append(root)
    write(root, "hwut-root.conf", "hwut {\n}\n")
    write(root, "hwut-feature-forest.csv", forest)
    write(root, "hwut-feature-doc.dat", doc)
    if external is not None:
        write(root, "hwut-feature-external-map.csv", external)
    for path, body in (test_db or {}).items():
        test(root, path, body)
    for (directory, name, choice), verdict in (verdict_db or {}).items():
        book = Bookkeeper(os.path.join(root, directory))
        if verdict is None:
            book.note_accept(name, choice, aspirant_f=True)
        else:
            book.note_accept(name, choice, equivalent_f=verdict)
    return root


def masked(text):
    """RETURN: str, 'text' with every scratch root written '<root>'."""
    for root in _ROOT_LIST:
        text = text.replace(os.path.realpath(root), "<root>") \
                   .replace(root, "<root>")
    return text


def removed():
    """RETURN: None. Every tree made here, gone."""
    for root in _ROOT_LIST:
        shutil.rmtree(root, ignore_errors=True)
    del _ROOT_LIST[:]


FOREST = """gateway    : forwarding, buses
forwarding : fwd, keeporder
buses      : decode, encode
"""

DOC = """[[CUSTOMERS]]
manager: the one who asks
[[gateway to manager]]
documents: README.txt
The gateway forwards what reaches it.
[[forwarding]]
Frames reach their destination.
[[fwd]]
A frame is forwarded.
[[keeporder]]
Order is kept per sender.
[[decode]]
A frame is decoded.
[[lonely]]
A promise with no place.
[[old:retired]]
What was once claimed.
"""

TEST_DB = {
    "gw/TEST/test-fwd.sh":    ['features = ["fwd"]',
                               'choices = ["one", "two"]'],
    "gw/TEST/test-order.sh":  ['features = ["keeporder", "forwarding"]'],
    "gw/TEST/test-plain.sh":  ['choices = ["x"]'],
    "bus/TEST/test-bus.sh":   ['features = ["decode", "lonely"]'],
    "bus/TEST/test-typo.sh":  ['features = ["decod", "old"]'],
}

VERDICT_DB = {
    ("gw/TEST", "test-fwd.sh", "one"):   True,
    ("gw/TEST", "test-fwd.sh", "two"):   False,
    ("gw/TEST", "test-order.sh", None):  True,
    ("bus/TEST", "test-bus.sh", None):   True,
}


def gateway(external=None):
    """RETURN: str, the root of the gateway tree: the forest, the doc file
    and the tests above; 'external' the map."""
    return tree(FOREST, DOC, external, TEST_DB, VERDICT_DB)

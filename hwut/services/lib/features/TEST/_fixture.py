"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE PAGES OF THE FEATURE FACES SHARE: a scratch tree, the
         call of a face as a person calls it, the files shown. Not a test
         application ('hwut-info.dat' says so).
______________________________________________________________________________
"""
import os
import shutil
import tempfile

_ROOT_LIST = []


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def test(root, path, body):
    """RETURN: None. A shell test at 'root/path' whose block holds the
    lines of 'body'."""
    write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
          % "\n".join("#     " + line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def tree(file_db=None):
    """RETURN: str, the root of a new scratch tree: 'hwut-root.conf' and
    the files of 'file_db' (path below the root -> text)."""
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _ROOT_LIST.append(root)
    write(root, "hwut-root.conf", "hwut {\n}\n")
    for path, text in (file_db or {}).items():
        write(root, path, text)
    return root


def removed():
    """RETURN: None. Every tree made here, gone."""
    for root in _ROOT_LIST:
        shutil.rmtree(root, ignore_errors=True)
    del _ROOT_LIST[:]


def masked(text):
    """RETURN: str, 'text' with every scratch root written '<root>'."""
    for root in _ROOT_LIST:
        text = text.replace(os.path.realpath(root), "<root>") \
                   .replace(root, "<root>")
    return text


def call(label, face, argv, directory):
    """RETURN: None. Calls 'face.main' in 'directory' as a person calls
    it, prints what it wrote and its exit status."""
    print(">>> %s" % label)
    here = os.getcwd()
    os.chdir(directory)
    try:
        code = face.main(argv, write=lambda text: print(
            "    " + masked(text).replace("\n", "\n    ")))
    finally:
        os.chdir(here)
    print("    exit %d" % int(code))


def shown(root, path):
    """RETURN: None. Prints the file 'root/path' below its '#' header,
    '(absent)' where it does not stand."""
    full = os.path.join(root, path)
    print("    [%s]" % path)
    if not os.path.exists(full):
        print("    (absent)")
        return
    with open(full, encoding="utf-8") as fh:
        line_list = fh.read().split("\n")
    while line_list and (line_list[0].startswith("#") or not line_list[0]):
        line_list.pop(0)
    for line in line_list:
        if line: print("    | %s" % line)


FOREST = """# the gateway
gateway    : forwarding, buses
forwarding : fwd, keep-order
buses      : decode
"""

DOC = """[[CUSTOMERS]]
manager: the one who asks

[[gateway to manager]]
The gateway forwards what reaches it.

[[forwarding]]
Frames reach their destination.

[[fwd]]
A frame is forwarded.

[[keep-order not manager]]
Order is kept per sender.

[[spare]]
A promise with no place.
"""

EXTERNAL = "keep-order ; REQ-4711\ngateway ; GW\n"


def gateway():
    """RETURN: str, the root of the gateway tree: the three files, a test
    linking features in its header, a conf whose application links one."""
    root = tree({"hwut-feature-forest.csv": FOREST,
                 "hwut-feature-doc.dat": DOC,
                 "hwut-feature-external-map.csv": EXTERNAL,
                 "gw/TEST/hwut.conf":
                     'hwut {\n    apps {\n        note.json { execute = '
                     '"cat $file"  features = ["keep-order", "fwd"] }\n'
                     '    }\n}\n',
                 "gw/TEST/note.json": "{}\n"})
    test(root, "gw/TEST/test-fwd.sh",
         ['features = ["fwd", "keep-order"]',
          'choices {', '    one { }',
          '    two { features = ["keep-order"] }', '}'])
    return root

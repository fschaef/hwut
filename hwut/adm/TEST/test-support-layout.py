#! /usr/bin/env python3
#
# @hwut {
#     title   = "adm/support_layout.py: the 'home' flag of support/test_writing (E-216)"
#     choices {
#         this-tree { features = ["support-layout-holds"] }
#         bites     { features = ["support-layout-bites"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PORTS OF THE TEST WRITING SUPPORT, AND WHERE EACH LIVES.
         'this-tree' -- the layout holds on this tree: every port listed,
         Python the one reference with 'home = "hwut"'.
         'bites' -- a made-up tree with one of each fault, and the records
         and the feature registry, which name a departing port without
         a fault.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE   = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "support_layout.py")

#  A DEPARTING PORT'S PATH, built and not written: this file is hwut's own,
#  and a hwut file naming a 'home = "support"' port is what the check finds.
PERL_PATH = "/".join(("support", "test_writing", "perl"))

LANGUAGES = '''python { home = "hwut", reference = true }
perl   { home = "support" }
cobol  { home = "support" }
lisp   { home = "elsewhere" }
'''


def put(path, text):
    """RETURN: None. 'text' is the file at 'path'."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh: fh.write(text)


def call(*word_list):
    """RETURN: None. The script, its output and exit status printed."""
    done = subprocess.run([sys.executable, SCRIPT] + list(word_list),
                          capture_output=True, text=True)
    for line in (done.stdout + done.stderr).splitlines():
        print("   %s" % line)
    print("   exit %i" % done.returncode)


def test_this_tree():
    call()


def test_bites():
    root = tempfile.mkdtemp(prefix="hwut_support_layout_")
    try:
        tw = os.path.join(root, "support", "test_writing")
        put(os.path.join(tw, "LANGUAGES.conf"), LANGUAGES)
        put(os.path.join(tw, "python", "TEST", "GOOD", "t.txt"), "nominal\n")
        put(os.path.join(tw, "perl", "TEST", "GOOD", "t--a.link"),
            "../../../python/TEST/GOOD/t.txt\n")
        put(os.path.join(tw, "perl", "TEST", "GOOD", "t--b.link"),
            "../../../../../engine/GOOD.txt\n")
        put(os.path.join(tw, "fortran", "README.txt"), "not listed\n")
        put(os.path.join(root, "engine", "x.py"),
            "# reads %s/x.pl\n" % PERL_PATH)
        put(os.path.join(root, "engine", "RATIONALE.txt"),
            "E-1 once lived in %s\n" % PERL_PATH)
        put(os.path.join(root, "hwut-root-features.conf"),
            '"aBcD1234" = "%s"\n' % PERL_PATH)
        put(os.path.join(root, "services", "y.txt"),
            "uses support/test_writing/python only\n")
        call(root)
        print("-- two references")
        put(os.path.join(tw, "LANGUAGES.conf"),
            'python { home = "hwut", reference = true }\n'
            'perl   { home = "support", reference = true }\n'
            'fortran { home = "support" }\n')
        os.remove(os.path.join(root, "engine", "x.py"))
        os.remove(os.path.join(tw, "perl", "TEST", "GOOD", "t--b.link"))
        call(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


{"this-tree": test_this_tree,
 "bites":     test_bites}[sys.argv[1]]()
print("<hwut-end>")

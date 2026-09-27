#! /usr/bin/env python3
#
# @hwut {
#     title      = "Keeping a tried tolerance: the question, TMP, the header."
#     choices    = ["unchanged", "store", "enter-replace", "enter-add",
#                   "enter-oneline", "refuse-apps", "refuse-choice",
#                   "cancel", "omit", "nobody"]
#     tolerance { comment = []  analogy = [] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'services/lib/accept/keep.py' (intend 21, 2.7) -- what the merge
         asks when it ends with the tolerance in memory changed, and what
         each answer writes. A scratch directory stands for the test's;
         its files are printed as they are left. The test's own tolerance
         is made up here as the header would give it ('regions = false'
         where the header says so).

         'comment' and 'analogy' are OFF for this page: the files printed
         hold '##' and '((' as data, which compare would otherwise read.

    unchanged      nothing changed: nothing is asked
    store          (1): the TMP file
    enter-replace  (2): the header's own 'tolerance' scope replaced
    enter-add      (2): a header without one gains the line, in its lead
    enter-oneline  (2): a one-line header
    refuse-apps    (2) on a file without a header: refused, (1) instead
    refuse-choice  (2) where the choice states its own: refused, (1)
    cancel         a cancelled session offers (1) and (3) only
    omit           (3) after a commit: the NOTE
    nobody         no answer can be read: (1)
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

from vut.engine.compare.api       import Configuration
from vut.services.lib.accept.keep import keep_question


class Adapter:
    """The two configurations the keyed driver holds, and its verdict."""
    def __init__(self, page, tried):
        self.page_options, self.tolerance_options = page, tried
    def tolerance_changed_f(self):
        return self.page_options is not self.tolerance_options


class Key:
    """The engine's key shape, as far as the question reads it."""
    def __init__(self, test, choice):
        self.test, self.choice = test, choice
        self.label = test if choice is None else "%s %s" % (test, choice)


def configurations(regions_f=True):
    """RETURN: (Configuration, Configuration), the test's own and the one
               tried: numeric 0.047 and one pattern added."""
    page = Configuration()
    page.pattern_finder.regions_f = regions_f
    tried = Configuration()
    tried.pattern_finder.regions_f = regions_f
    tried.pattern_finder.numeric_tolerance_ratio = 0.047
    tried.pattern_finder.equivalent_pattern_list = ["id=[0-9abz]{3,4};", "a\\.b"]
    return page, tried


def run(source_text, answer_list, commit_f=True, choice="one", unchanged_f=False,
        regions_f=True):
    """RETURN: None. The question asked with 'answer_list' as the person's
               answers, in a scratch directory holding 'test.sh' as
               'source_text'; everything left there is printed."""
    directory = tempfile.mkdtemp()
    try:
        if source_text is not None:
            with open(os.path.join(directory, "test.sh"), "w") as file_handle:
                file_handle.write(source_text)
        page, tried = configurations(regions_f)
        adapter = Adapter(page, page if unchanged_f else tried)
        answer_iter = iter(answer_list)
        def ask(prompt):
            """RETURN: str, the next answer; EOFError where none is left."""
            answer = next(answer_iter, None)
            print("   | %s%s" % (prompt, "" if answer is None else answer))
            if answer is None: raise EOFError
            return answer
        def err(text): print("   | %s" % text)
        result = keep_question(adapter, Key("test.sh", choice), directory,
                               commit_f, err, ask)
        print("   -> %s" % result)
        for root, _, file_list in sorted(os.walk(directory)):
            for name in sorted(file_list):
                path = os.path.join(root, name)
                print("\n   == %s" % os.path.relpath(path, directory))
                with open(path) as file_handle:
                    for line in file_handle.read().splitlines():
                        print("   %s" % line)
    finally:
        shutil.rmtree(directory)


HEADER_WITH = """#! /bin/sh
# @hwut {
#     title   = "T"
#     choices = ["one", "two"]
#     tolerance {
#         regions = false
#     }
# }
echo hello
"""
HEADER_WITHOUT = """#! /bin/sh
# @hwut {
#     title   = "T"
#     choices = ["one", "two"]
# }
echo hello
"""
HEADER_ONELINE = """#! /bin/sh
# @hwut { title = "T"  choices = ["one"] }
echo hello
"""
HEADER_CHOICE = """#! /bin/sh
# @hwut {
#     title   = "T"
#     choices {
#         one { tolerance { slash = false } }
#     }
# }
echo hello
"""


CHOICE_DB = {
    "unchanged":     lambda: run(HEADER_WITH, [], unchanged_f=True, regions_f=False),
    "store":         lambda: run(HEADER_WITH, ["1"], regions_f=False),
    "enter-replace": lambda: run(HEADER_WITH, ["2"], regions_f=False),
    "enter-add":     lambda: run(HEADER_WITHOUT, ["2"]),
    "enter-oneline": lambda: run(HEADER_ONELINE, ["2"]),
    "refuse-apps":   lambda: run("echo no header\n", ["2"]),
    "refuse-choice": lambda: run(HEADER_CHOICE, ["2"]),
    "cancel":        lambda: run(HEADER_WITH, ["2", "x", "3"], commit_f=False,
                                 regions_f=False),
    "omit":          lambda: run(HEADER_WITH, ["3"], regions_f=False),
    "nobody":        lambda: run(HEADER_WITH, [], regions_f=False),
}

choice = sys.argv[1] if len(sys.argv) > 1 else "store"
CHOICE_DB[choice]()
print("<hwut-end>")

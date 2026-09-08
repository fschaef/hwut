#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.sanitize --books: the three records of acceptance"
#     choices    = ["agree", "apply_keeps", "disagree"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE THREE RECORDS OF ACCEPTANCE MUST AGREE (services E-41): the
nominals in GOOD/, the register 'test_ids.dat', the book's
'last_accept'. 'hwut.sanitize --books' names every disagreement and
'--apply' never touches one.

    disagree     one fixture holds all three disagreements:
                   test-reg.py     registered, no nominal
                   test-nom.py     a nominal, not registered
                   test-book.py    a nominal, registered, booked by a
                                   run and never accepted
                 and each is named once, by its record.
    agree        the same directory after 'hwut.accept': silence.
    apply_keeps  '--apply' reports 'kept', and the three records stand.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.sanitize import main as sanitize_main        # noqa E402
from   vut.services.run      import main as run_main             # noqa E402
from   vut.services.accept   import main as accept_main          # noqa E402
from   vut.engine.bookkeeper.api import Bookkeeper, TestIdDb     # noqa E402

ROOT_CONF = """\
hwut {
    language-setup {
        python { extensions  = [".py"]
                 interpreter = "python3" }
    }
}
"""

SCRIPT = '''\
#! /usr/bin/env python3
# @hwut { title = "%s" }
print("%s")
print("<hwut-end>")
'''


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def fixture():
    """RETURN: (str, str), the tree root and a TEST directory whose
    three records disagree in the three ways."""
    root = tempfile.mkdtemp(prefix="vut_books_")
    tree_boundary(root, ROOT_CONF)
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)

    def put(directory, name, content, executable_f=False):
        path = os.path.join(directory, name)
        with open(path, "w") as fh: fh.write(content)
        if executable_f: os.chmod(path, 0o755)

    put(test, "hwut.conf", "hwut { }\n")
    for stem in ("reg", "nom", "book"):
        put(test, "test-%s.py" % stem, SCRIPT % (stem, stem), True)
    put(good, "test-nom.py.txt",  "nom\n<hwut-end>\n")
    put(good, "test-book.py.txt", "book\n<hwut-end>\n")
    register = TestIdDb(test)
    register.run_id_of("test-reg.py", allocate_f=True)
    register.run_id_of("test-book.py", allocate_f=True)
    #  A RUN books 'test-book.py' with a verdict and no 'last_accept'.
    run_main(["test-book.py", "--directory=%s" % test, "--silent"],
             write=lambda _: None, write_error=lambda _: None)
    return root, test


def _sanitize(test, *extra):
    """RETURN: list[str], what the face wrote."""
    line_list = []
    sanitize_main(["--books", "--directory=%s" % test] + list(extra),
                  write=line_list.append)
    return line_list


def _finding_list(line_list):
    """RETURN: list[str], the finding lines, whitespace folded."""
    return [" ".join(l.split()) for l in line_list
            if l.startswith("      ")]


def test_disagree():
    """Each disagreement named once, by its record."""
    root, test = fixture()
    finding_list = _finding_list(_sanitize(test))
    for line in finding_list: print("  " + line)
    ok = _check([
        (len(finding_list) == 3, "three findings"),
        (any(l.startswith(".: register test-reg.py") for l in finding_list),
         "the register ahead: registered, no nominal"),
        (any(l.startswith(".: GOOD/ test-nom.py") for l in finding_list),
         "the register behind: a nominal, not registered"),
        (any(l.startswith(".: book test-book.py") and "last_accept" in l
             for l in finding_list),
         "the book: a nominal, and 'last_accept' empty"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "every disagreement is named by its record.")


def test_agree():
    """After acceptance the three agree, and the face is silent."""
    root, test = fixture()
    #  MEND BY HAND, as the face says: accept what has a candidate.
    accept_main(["test-book.py", "--yes", "--force",
                 "--directory=%s" % test],
                write=lambda _: None)
    #  'test-reg.py' and 'test-nom.py' are still apart; remove their
    #  disagreement the same way -- a nominal for one, none for the
    #  other -- so only agreement remains.
    os.remove(os.path.join(test, "GOOD", "test-nom.py.txt"))
    TestIdDb(test).remove_app(TestIdDb(test).run_id_of("test-reg.py").app_id)
    finding_list = _finding_list(_sanitize(test))
    for line in finding_list: print("  " + line)
    entry = Bookkeeper(test).result("test-book.py", None)
    ok = _check([
        (entry is not None and bool(entry.get("last_accept")),
         "accept wrote 'last_accept'"),
        (not finding_list, "no finding: the three agree"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "where the records agree, the aspect is silent.")


def test_apply_keeps():
    """'--apply' keeps every books finding and says so."""
    root, test = fixture()
    line_list = _sanitize(test, "--apply")
    kept = [" ".join(l.split()) for l in line_list if "kept:" in l]
    for line in kept: print("  " + line)
    ok = _check([
        (len(kept) == 3, "three kept, none removed"),
        (os.path.isfile(os.path.join(test, "GOOD", "test-nom.py.txt")),
         "the nominal stands"),
        (TestIdDb(test).run_id_of("test-reg.py") is not None,
         "the register entry stands"),
        (Bookkeeper(test).result("test-book.py", None) is not None,
         "the book entry stands"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "a disagreement is mended by hand, never by --apply.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.sanitize --books: the three records of acceptance",
        choice_map = {
            "agree":       test_agree,
            "apply_keeps": test_apply_keeps,
            "disagree":    test_disagree,
        }).run()

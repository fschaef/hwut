#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.sanitize.propose --books: the records of acceptance"
#     choices    = ["agree", "apply_books", "disagree"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE TWO RECORDS OF ACCEPTANCE MUST AGREE (services E-41): the nominals
in GOOD/, and the book -- which is also the register (B-13) and carries
'last_accept'. 'hwut.sanitize.propose --books' proposes a 'book' for
every disagreement, each under its kind (E-125). A test the book calls
ASPIRANT with no nominal is not a disagreement (B-14).

    disagree     one fixture holds all three disagreements:
                   test-reg.py     the book says aspirant, a nominal
                                   stands
                   test-nom.py     a nominal, and no entry in the book
                   test-book.py    a nominal, booked by a run and never
                                   accepted: 'last_accept' empty
                 and each is proposed once, under its kind.
    agree        the same directory after 'hwut.accept': nothing
                 proposed.
    apply_books  the proposal applied: each disagreement booked, nothing
                 in GOOD/ moved, the aspirant still an aspirant; proposed
                 again, nothing.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.lib.sanitize.propose import main as propose_main  # noqa E402
from   vut.services.lib.sanitize.apply   import main as apply_main    # noqa E402
from   vut.services.run      import main as run_main             # noqa E402
from   vut.services.accept   import main as accept_main          # noqa E402
from   vut.engine.bookkeeper.api import (Bookkeeper,              # noqa E402
                                         E_TestVerdict)

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
    two records disagree in the three ways (B-14) -- and hold one
    ASPIRANT, which is no disagreement at all."""
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
    for stem in ("reg", "nom", "book", "asp"):
        put(test, "test-%s.py" % stem, SCRIPT % (stem, stem), True)
    put(good, "test-nom.py.txt",  "nom\n<hwut-end>\n")
    put(good, "test-book.py.txt", "book\n<hwut-end>\n")
    #  THE BOOK IS THE REGISTER (B-13), and an id issued with no
    #  nominal makes an ASPIRANT row (B-14). 'test-asp.py' stays one.
    #  'test-reg.py' gets a nominal AFTER the book called it aspirant:
    #  accepted outside the book, the finding that replaced
    #  "registered, no nominal".
    keeper = Bookkeeper(test)
    keeper.run_id_of("test-reg.py",  allocate_f=True)
    keeper.run_id_of("test-asp.py",  allocate_f=True)
    keeper.run_id_of("test-book.py", allocate_f=True)
    put(good, "test-reg.py.txt",  "reg\n<hwut-end>\n")
    #  A RUN books 'test-book.py' with a verdict and no 'last_accept'.
    run_main(["test-book.py", "--directory=%s" % test, "--silent"],
             write=lambda _: None, write_error=lambda _: None)
    return root, test


def _proposal(test):
    """RETURN: list[str], the proposal '--books' writes for 'test' -- its
               block comments and commands, the head left out."""
    text_list = []
    old = os.getcwd()
    os.chdir(test)
    try:
        propose_main(["--books"], write=text_list.append,
                     err=lambda _: None)
    finally:
        os.chdir(old)
    line_list = "".join(text_list).splitlines()
    first = next((i for i, text in enumerate(line_list) if not text.strip()),
                 len(line_list))
    return [text for text in line_list[first:] if text.strip()]


def _finding_list(line_list):
    """RETURN: list[str], the command lines of a proposal."""
    return [text for text in line_list if not text.startswith("#")]


def test_disagree():
    """Each disagreement named once, by its record."""
    root, test = fixture()
    line_list    = _proposal(test)
    for line in line_list: print("  " + line)
    finding_list = _finding_list(line_list)

    def under(kind_word, command):
        """RETURN: bool, 'command' stands in the block whose comment
                   opens with 'kind_word'."""
        head = next((i for i, text in enumerate(line_list)
                     if text.startswith("# " + kind_word)), None)
        return head is not None and command in line_list[head:] \
               and all(text.startswith("#") or text.startswith("book ")
                       for text in line_list[head:line_list.index(command)])
    ok = _check([
        (len(finding_list) == 3, "three commands"),
        (under("BOOK STALE", "book test-reg.py"),
         "the book stale: it says aspirant, and a nominal stands"),
        (under("BOOK BEHIND", "book test-nom.py"),
         "the book behind: a nominal, and no entry"),
        (not any("test-asp.py" in text for text in finding_list),
         "an aspirant is no disagreement (B-14)"),
        (under("ACCEPTANCE UNDATED", "book test-book.py"),
         "the book: a nominal, and 'last_accept' empty"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "every disagreement is proposed under its kind.")


def test_agree():
    """After acceptance the three agree, and the face is silent."""
    root, test = fixture()
    #  MEND BY HAND, as the face says: accept what has a candidate.
    accept_main(["test-book.py", "--force",
                 "--directory=%s" % test],
                write=lambda _: None)
    #  'test-reg.py' and 'test-nom.py' are still apart; mend them the
    #  same way -- accept the one the book calls aspirant, remove the
    #  nominal the book never knew -- so only agreement remains.
    #  'test-asp.py' stays an aspirant, which is agreement.
    os.remove(os.path.join(test, "GOOD", "test-nom.py.txt"))
    accept_main(["test-reg.py", "--force", "--directory=%s" % test],
                write=lambda _: None)
    finding_list = _finding_list(_proposal(test))
    for line in finding_list: print("  " + line)
    entry = Bookkeeper(test).result("test-book.py", None)
    ok = _check([
        (entry is not None and bool(entry.get("last_accept")),
         "accept wrote 'last_accept'"),
        (not finding_list, "nothing proposed: the records agree"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "where the records agree, nothing is proposed.")


def test_apply_books():
    """The proposal applied books every disagreement; GOOD/ is not
    touched; asked again, nothing is proposed."""
    root, test = fixture()
    good = os.path.join(test, "GOOD")

    def good_db():
        """RETURN: dict, name -> content of every nominal."""
        return {n: open(os.path.join(good, n)).read()
                for n in sorted(os.listdir(good)) if n != "book.csv"}
    before = good_db()
    proposal = os.path.join(root, "p.txt")
    with open(proposal, "w") as fh:
        fh.write("\n".join(_proposal(test)) + "\n")
    said = []
    apply_main([proposal, "--directory=%s" % test], write=said.append)
    for line in said:
        if line.startswith(" book "): print("  " + " ".join(line.split()))
    book = Bookkeeper(test)
    ok = _check([
        (sum(1 for text in said if text.startswith(" book ")
             and text.endswith("[DONE]")) == 3, "three booked"),
        (good_db() == before, "nothing in GOOD/ moved"),
        (all(book.result(t, None) is not None
             and bool(book.result(t, None).get("last_accept"))
             for t in ("test-reg.py", "test-nom.py", "test-book.py")),
         "each carries 'last_accept'"),
        ((book.result("test-asp.py", None) or {}).get("verdict")
         is E_TestVerdict.ASPIRANT, "the aspirant is still an aspirant"),
        (not _finding_list(_proposal(test)), "asked again: nothing"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "'book' mends the book and never GOOD/.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.sanitize.propose --books: the records of acceptance",
        choice_map = {
            "agree":       test_agree,
            "apply_books": test_apply_books,
            "disagree":    test_disagree,
        }).run()

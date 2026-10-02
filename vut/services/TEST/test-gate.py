#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.run admits by the nominal (E-41)"
#     choices    = ["backup_shaped", "new_choice", "not_accepted",
#                   "plan_agrees", "registered"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE GATE IS ON THE NOMINAL (services E-41). One fixture tree holds:

    test-old.py            accepted: a nominal in GOOD/, NO register
    test-old.py.backup     a copy, header and all -- backup-shaped name
    test-new.py            never accepted: no nominal
    test-two.py            choices 'a' (accepted) and 'b' (not)

    backup_shaped   the copy is REFUSED at candidacy, by name, in the
                    closing REFUSED block; it is not run and the book
                    has no entry for it.
    not_accepted    the new test is NOT RUN, and FAILS: 'no GOOD file
                    [FAIL]' in the flow, the way in named in HINTS,
                    counted, the run red (display D-32); not booked.
    registered      the accepted test RUNS, gets a register entry on
                    the nominal's word, and the run SAYS so (NOTE).
    plan_agrees     'hwut.plan' refuses exactly what 'hwut.run' does not
                    run: the copy it refuses, the cases with no GOOD file
                    it fails.
    new_choice      THE GATE IS PER CASE: 'test-two.py a' runs and
                    passes; 'test-two.py b' fails by name, 'no GOOD
                    file'.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.run  import main as run_main                 # noqa E402
from   vut.services.plan import main as plan_main                # noqa E402
from   vut.engine.bookkeeper.api import Bookkeeper, E_TestVerdict  # noqa E402

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

TWO = '''\
#! /usr/bin/env python3
# @hwut { title = "Two" choices = ["a", "b"] }
import sys
print("two " + sys.argv[1])
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
    """RETURN: (str, str), the tree root and its TEST directory."""
    root = tempfile.mkdtemp(prefix="vut_gate_")
    tree_boundary(root, ROOT_CONF)
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)

    def put(directory, name, content, executable_f=False):
        path = os.path.join(directory, name)
        with open(path, "w") as fh: fh.write(content)
        if executable_f: os.chmod(path, 0o755)

    put(test, "hwut.conf", "hwut { }\n")
    put(test, "test-old.py", SCRIPT % ("Old", "old"), True)
    put(good, "test-old.py.txt", "old\n<hwut-end>\n")
    put(test, "test-old.py.backup", SCRIPT % ("Old", "old"), True)
    put(test, "test-new.py", SCRIPT % ("New", "new"), True)
    put(test, "test-two.py", TWO, True)
    put(good, "test-two.py--a.txt", "two a\n<hwut-end>\n")
    return root, test


def _run(root):
    """RETURN: (E_ExitCode, list[str], list[str]), the status, the
    rendering and the FAULT/NOTE lines (SILENT tier: on write_error)."""
    line_list  = []
    error_list = []
    status = run_main(["--directory=%s" % root, "--plain"],
                      write=line_list.append, write_error=error_list.append)
    return status, line_list, error_list


def _expanded(line_list):
    """
    RETURN: list[str], the same lines with every ':' ELISION RESOLVED
            to the application it repeats -- so a reader may scan a
            verdict line for the file that produced it.

    A READER OF AN ELIDED FLOW MUST EXPAND BEFORE IT COMPARES, which
    is the rule 'test-run.pype' has always kept ('EXPANSION COMES
    FIRST'). Since D-15 every run writes a 'START' and an 'END', and
    the END repeats the START's application, so a verdict line
    carrying a choice reads ':' -- correctly, and unreadably to a
    filter looking for the name.
    """
    result = []
    last   = None
    for line in line_list:
        field = line.split()
        if len(field) > 1 and field[1] == ":" and last is not None:
            result.append(line.replace(":", last, 1))
        else:
            if len(field) > 1 and field[0] in ("START", "END", "DONE",
                                               "SKIP"):
                last = field[1]
            result.append(line)
    return result


def _refused_block(line_list):
    """RETURN: list[str], the lines of the REFUSED block, stripped;
    empty where none stands."""
    result = []
    in_f   = False
    for line in line_list:
        if line.startswith("REFUSED -- not run"): in_f = True; continue
        if in_f and line.startswith("="):           break
        if in_f and line.startswith("    "):        result.append(line.strip())
    return result


def _hints_block(line_list):
    """RETURN: list[str], the lines of the HINTS block, stripped; empty
    where none stands."""
    import re
    result = []
    in_f   = False
    last   = None
    for line in line_list:
        if line.startswith("HINTS"):                 in_f = True; continue
        if in_f and line.startswith("="):            break
        if not (in_f and line.startswith("    ")):   continue
        #  A READER OF AN ELIDED BLOCK EXPANDS BEFORE IT COMPARES (D-35):
        #  ':' in the phrase column is the phrase of the line above.
        text  = line.strip()
        match = re.match(r"^(.*\S)\s{2,}(\S.*)$", text)
        if match is not None:
            said = match.group(2)
            if said == ":": said = last
            else:           last = said
            text = "%s   %s" % (match.group(1), said)
        result.append(text)
    return result


def _no_good_flow(line_list):
    """RETURN: list[str], the expanded flow lines that fail a case for
    want of a GOOD file (display D-32)."""
    return [text for text in _expanded(line_list) if "no GOOD file [FAIL]" in text]


def test_backup_shaped():
    """The copy is refused by name; not run, not booked."""
    root, test = fixture()
    status, line_list, _ = _run(root)
    block = _refused_block(line_list)
    hit   = [l for l in block if l.startswith("test-old.py.backup")]
    for line in hit: print("  " + line)
    ok = _check([
        (len(hit) == 1, "the copy stands once in the REFUSED block"),
        (hit and "backup-shaped" in hit[0], "the reason is the name"),
        #  B-17: it DOES appear in the flow -- once, tagged '[REFUSED]'.
        #  A file passed over in silence read as though nobody had
        #  looked at it.
        (len([l for l in line_list
              if "test-old.py.backup" in l and "[REFUSED]" in l]) == 1,
         "it appears in the flow, tagged [REFUSED]"),
        ("test-old.py.backup" not in Bookkeeper(test).tests(),
         "the book has no entry for it"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "a backup-shaped name is refused, not run.")


def test_not_accepted():
    """No nominal: not run, and a failure -- by name, the way in named,
    counted (display D-32)."""
    root, test = fixture()
    status, line_list, _ = _run(root)
    hint  = [text for text in _hints_block(line_list) if text.startswith("test-new.py")]
    flow  = [text for text in _no_good_flow(line_list) if "test-new.py" in text]
    for line in hint: print("  " + line)
    count = [text for text in line_list if text.startswith("DIRECTORIES")]
    print("  %s" % (count[0].split(None, 1)[1].rsplit(",", 1)[0].strip()
                    if count else "?"))   # the count, never the clock
    ok = _check([
        (len(flow) == 1, "the flow says 'no GOOD file [FAIL]', once"),
        (len(hint) == 1 and "no GOOD file" in hint[0],
         "HINTS names it"),
        (not any(text.startswith("test-new.py")
                 for text in _refused_block(line_list)),
         "it is no refusal"),
        (count and "2 ok, 2 fail" in count[0],
         "it is counted: two ok, two failed (and 'test-two.py b')"),
        ("test-new.py" not in Bookkeeper(test).tests(),
         "the book has no entry for it"),
        (status.value == 1, "the run fails"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "no GOOD file, no run -- a failure, named in HINTS.")


def test_registered():
    """The accepted test runs; the register gets its entry on the
    nominal's word; the run says so."""
    root, test = fixture()
    before = Bookkeeper(test).run_id_of("test-old.py")
    status, line_list, error_list = _run(root)
    #  A NOTE STANDS IN THE FLOW now (O-24), not on write_error.
    note = [l for l in line_list if "REGISTERED test-old.py" in l]
    for line in note: print("  " + line.split("REGISTERED", 1)[1].strip()
                             .replace("test-old.py", "REGISTERED test-old.py", 1))
    entry = Bookkeeper(test).result("test-old.py", None)
    ok = _check([
        (before is None, "before: no register entry"),
        (Bookkeeper(test).run_id_of("test-old.py") is not None,
         "after: the register has the test"),
        (len(note) == 1, "the run said so, once (NOTE)"),
        (entry is not None and entry.get("verdict") is E_TestVerdict.PASS,
         "the book has the run's verdict"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "a nominal's word registers the test, and says so.")


def test_plan_agrees():
    """What 'hwut.plan' refuses, 'hwut.run' does not run: the copy it
    refuses too, the cases with no GOOD file it fails."""
    root, test = fixture()
    plan_list = []
    plan_main(["--directory=%s" % test], write=plan_list.append)
    refused = sorted(text.split(":", 1)[1].split(" -- ")[0].strip()
                     for text in plan_list if text.startswith("REFUSED:"))
    for name in refused: print("  plan refuses: %s" % name)
    _, line_list, _ = _run(root)
    run_refused = [text.split("  ")[0].strip() for text in _refused_block(line_list)]
    run_failed  = [" ".join(text.split("no GOOD file")[0].split())
                   for text in _hints_block(line_list) if "no GOOD file" in text]
    run_not_run = sorted(run_refused + run_failed)
    ok = _check([
        (refused == ["test-new.py", "test-old.py.backup", "test-two.py b"],
         "the plan refuses the copy, the new test and the new choice"),
        (refused == run_not_run,
         "and the run runs none of them: the copy refused, the rest failed"),
        (any("test-old.py" == text.strip().split()[0] for text in plan_list
             if text.strip() and not text.startswith(("REFUSED", "WISH", "REPORT"))),
         "the accepted test is in the plan"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "plan and run admit by the same gate.")


def test_new_choice():
    """One accepted choice runs, the other fails by name: no GOOD file."""
    root, test = fixture()
    _, line_list, _ = _run(root)
    flow = [text for text in _expanded(line_list)
            if "test-two.py" in text and "[" in text]
    miss = [" ".join(text.split("no GOOD file")[0].split())
            for text in _hints_block(line_list)
            if text.startswith("test-two.py") and "no GOOD file" in text]
    for name in miss: print("  " + name)
    ok = _check([
        (miss == ["test-two.py b"] and len([text for text in flow if " b " in text
                                             and "no GOOD file [FAIL]" in text]) == 1,
         "'b' fails by name: no GOOD file"),
        (len([text for text in flow if " a " in text and "[OK]" in text]) == 1,
         "'a' ran and passed"),
        (Bookkeeper(test).choices("test-two.py") == ["a"],
         "the book knows 'a' and not 'b'"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "the gate is per case.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.run admits by the nominal (E-41)",
        choice_map = {
            "backup_shaped": test_backup_shaped,
            "new_choice":    test_new_choice,
            "not_accepted":  test_not_accepted,
            "plan_agrees":   test_plan_agrees,
            "registered":    test_registered,
        }).run()

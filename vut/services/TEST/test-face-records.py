#! /usr/bin/env python3
#
# @hwut {
#     title      = "The face contract: Request, do(), Result (E-101)"
#     choices    = ["accept", "plain", "refuse", "reuse", "run", "split",
#                   "stream"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

'services/lib/face.py' and the two faces cut to it, 'hwut.wishlist' and
'hwut.plan'. What is pinned here is the CONTRACT, not the pages: the
pages are pinned where they always were, and that they did not move is
the proof of the cut.

    reuse    'do(Request)' answers a caller that is not a command line:
             a Result in hand, no output, no exit
    plain    every field of both records is plain -- str, int, bool,
             None, tuples of those -- so a schema or a server can be
             derived from them ('record_check')
    refuse   a refusal is an OUTCOME: 'Refused'/'Fault' carry the
             sentence and the exit code the face has always used, and
             'answered' is the one place they become a page
    split    the acting split from the saying (E-103): 'sanitize'
             removes and answers WHAT BECAME of each finding; the page
             is made from that answer, not written from inside it
    accept   what 'hwut.accept' DECIDED, as data (E-105): one Outcome
             per key, and the page -- report block or brief row -- made
             from it
    run      'hwut.run' as a library (E-104): the run streams its own
             events to a sink, renders through nobody, and answers a
             Tally -- the exit code is a function of that Tally
    stream   a STREAMING face (E-102): 'do' takes a sink and feeds it
             items as they happen; what it returns is the tally.
             'collected' is the batch reading of the same face
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile

from   config import HwutRunner                                  # noqa F401,E402
from   vut.services import wishlist, plan                        # noqa: E402
from   vut.services.lib.face import (record_check, Refused, Fault,  # noqa: E402
                                     Empty, answered)
from   vut.services._exit import E_ExitCode                      # noqa: E402

ROOT = tempfile.mkdtemp(prefix="hwut-face-")
TEST = os.path.join(ROOT, "suite", "TEST")


def fixture():
    """RETURN: None. A tree of two applications, one with two choices."""
    os.makedirs(TEST, exist_ok=True)
    with open(os.path.join(ROOT, "hwut-root.conf"), "w") as fh:
        fh.write("hwut {\n}\n")
    for name, extra in (("test-a.sh", ' choices = ["one", "two"]'),
                        ("test-b.sh", "")):
        path = os.path.join(TEST, name)
        with open(path, "w") as fh:
            fh.write('#!/bin/bash\n# @hwut { title = "%s"%s }\n'
                     'echo "line $1"\necho "<hwut-end>"\n' % (name, extra))
        os.chmod(path, 0o755)


def masked(text):
    """RETURN: str, 'text' with the fixture's temporary root spelled
               '<ROOT>' -- the page must not carry a path that changes
               with every run."""
    return text.replace(ROOT, "<ROOT>")


def banner(label):
    print(); print("--- %s ---" % label)


def test_reuse():
    fixture()
    banner("hwut.wishlist, called as a library")
    result = wishlist.do(wishlist.Request(directory=TEST))
    for line in result.line_tuple: print("    %s" % line)
    print("    warnings: %s" % (list(result.warning_tuple) or "none"))

    banner("the same, narrowed by the wish -- no argv anywhere")
    result = wishlist.do(wishlist.Request(directory=TEST,
                                          glob_tuple=("test-a.sh one",)))
    for line in result.line_tuple: print("    %s" % line)

    banner("hwut.plan, called as a library -- nothing is accepted yet, so")
    print("   the plan is empty; what matters is that it is a RECORD")
    result = plan.do(plan.Request(directory=TEST))
    print("    wish        : %s" % result.wish_text)
    print("    nodes       : %s" % [node.name for node in result.node_tuple])
    print("    kinds       : %s" % sorted({n.kind for n in result.node_tuple}))
    print("    links       : %s" % [(l.source, l.arrow, l.target)
                                    for l in result.link_tuple])
    print("    exclusions  : %s" % [list(e) for e in result.exclusion_tuple])
    print("    fault_f     : %s" % result.fault_f)

    banner("nothing was printed by 'do': the page above is this test's")


def test_plain():
    fixture()
    for name, record in (
            ("wishlist.Request", wishlist.Request(directory=TEST)),
            ("wishlist.Result",  wishlist.do(wishlist.Request(directory=TEST))),
            ("plan.Request",     plan.Request(directory=TEST)),
            ("plan.Result",      plan.do(plan.Request(directory=TEST)))):
        fault_list = record_check(record)
        print("    %-18s plain: %s" % (name, fault_list or "yes"))  # noqa: E501

    banner("what the rule refuses: an engine object in a record")
    from dataclasses import dataclass
    from pathlib import Path

    @dataclass(frozen=True)
    class Bad:
        where: Path = Path(".")
        pair:  tuple = ((1, Path("x")),)
    for line in record_check(Bad()): print("    %s" % line)

    banner("a Wish is the engine's; the record states its keywords")
    request = wishlist.Request(directory=TEST, fail_f=True, since_spec="2h")
    wish = wishlist.wish_of(request)
    print("    request -> wish: fail_f=%s since=%r"
          % (wish.fail_f, wish.since_spec))
    print("    wish -> request: %s"
          % (wishlist.request_of(wish, TEST, []).since_spec,))


def test_refuse():
    fixture()
    for label, call in (
        ("a directory that does not stand",
         lambda: wishlist.do(wishlist.Request(directory=os.path.join(ROOT, "nope")))),
        ("no root conf above",
         lambda: plan.do(plan.Request(directory="/tmp"))),
    ):
        banner(label)
        try:
            call()
            print("    answered")
        except (Refused, Fault, Empty) as error:
            print("    %-8s %-8s %s" % (type(error).__name__, error.code.name,
                                        masked(error.said)))

    banner("'answered' is the one place an outcome becomes a page")
    line_list = []
    code = answered(wishlist.do,
                    wishlist.Request(directory=os.path.join(ROOT, "nope")),
                    line_list.append, wishlist.printed, usage="usage: ...")
    print("    exit %s" % code.name)
    for line in line_list: print("    | %s" % masked(line))

    banner("an EMPTY selection is a Result, not a refusal: the warning stands")
    result = wishlist.do(wishlist.Request(directory=TEST,
                                          glob_tuple=("no-such-test.sh",)))
    print("    lines %d, warnings %d" % (len(result.line_tuple),
                                         len(result.warning_tuple)))
    line_list = []
    print("    printed -> exit %s" % wishlist.printed(result,
                                                      line_list.append).name)


def test_stream():
    """RETURN: None. The streaming shape, on a face small enough to
               stand in the test: items reach the sink AS THEY HAPPEN,
               the Result is the tally, and 'collected' reads the same
               face in one go."""
    from dataclasses import dataclass
    from vut.services.lib.face import collected

    @dataclass(frozen=True)
    class Tally:
        item_n: int = 0
        fail_n: int = 0

    def do_stream(request, sink):
        """RETURN: Tally. Every case handed to 'sink' as it is judged."""
        fail_n = 0
        for i, name in enumerate(request):
            good_f = not name.endswith("-bad")
            if not good_f: fail_n += 1
            sink({"kind": "case", "name": name, "good_f": good_f, "order": i})
        return Tally(item_n=len(request), fail_n=fail_n)

    banner("the sink sees each item while the run is still going")
    seen = []
    def watching(item):
        seen.append("%s %s" % (item["name"], "ok" if item["good_f"] else "FAIL"))
        print("    ... %s (%d so far)" % (seen[-1], len(seen)))
    tally = do_stream(["a", "b-bad", "c"], watching)
    print("    tally: %d item(s), %d failure(s)" % (tally.item_n, tally.fail_n))

    banner("'collected': the same face read in one go")
    tally, item_list = collected(do_stream, ["a", "b-bad", "c"])
    print("    items  : %s" % [i["name"] for i in item_list])
    print("    tally  : %d item(s), %d failure(s)" % (tally.item_n, tally.fail_n))
    print("    plain  : %s" % (record_check(tally) or "yes"))

    banner("what a sink is NOT: a printer")
    print("    an item is a record or a plain dict -- never a line;")
    print("    a face that writes lines into a sink has been moved, not cut")


def test_split():
    """RETURN: None. E-103: 'sanitize.removal_of' removes and ANSWERS;
               nothing is printed from inside the action."""
    from vut.services.sanitize import removal_of, Removal, CFinding
    banner("a books finding is kept BY DESIGN, and says why")
    removal = removal_of(CFinding("books", "suite/TEST: book x one",
                                  "the book and the register disagree"), ROOT)
    print("    %-9s gone=%-5s kept=%-5s fault=%s"
          % (removal.path.split(":")[0], removal.gone_f, removal.kept_f,
             removal.fault))
    print("    said : %s" % removal.said)

    banner("a file that stands: gone")
    fixture()
    victim = os.path.join(TEST, "OUT")
    os.makedirs(victim, exist_ok=True)
    with open(os.path.join(victim, "x.txt"), "w") as fh: fh.write("x\n")
    removal = removal_of(CFinding("out", os.path.relpath(victim, ROOT),
                                  "the last run's output"), ROOT)
    print("    gone=%-5s exists now: %s" % (removal.gone_f,
                                            os.path.exists(victim)))

    banner("a path that cannot go: the fault is ANSWERED, not printed")
    removal = removal_of(CFinding("out", "no/such/place", "gone already"), ROOT)
    print("    gone=%-5s fault=%s" % (removal.gone_f,
                                      removal.fault is not None))

    banner("the record is plain")
    print("    %s" % (record_check(Removal("p")) or "yes"))


def test_run():
    """RETURN: None. E-104: the run, called by something that is not a
               command line."""
    import subprocess
    from vut.services import run
    fixture()
    for name in ("test-a.sh", "test-b.sh"):
        for choice in (["one", "two"] if name == "test-a.sh" else [""]):
            argv = [name] + ([choice] if choice else [])
            subprocess.run([sys.executable, "-m", "vut.services.play"] + argv
                           + ["--save"], cwd=TEST, capture_output=True)
            subprocess.run([sys.executable, "-m", "vut.services.accept"] + argv
                           + ["--force"], cwd=TEST, capture_output=True)

    banner("the whole tree, silent: every event to the sink")
    seen = []
    tally = run.do(run.Request(directory=TEST), sink=seen.append)
    print("    events : %d" % len(seen))
    print("    kinds  : %s" % sorted({item["kind"] for item in seen}))
    print("    tally  : %d case(s), %d failure(s), good_f=%s, empty=%s"
          % (tally.case_n, tally.fail_n, tally.good_f, tally.empty_f))
    print("    exit   : %s" % run.exit_code_of(tally).name)
    print("    plain  : %s" % (record_check(tally) or "yes"))

    banner("an event is a plain dict -- JSON as it stands")
    import json
    print("    %s" % json.dumps({k: v for k, v in sorted(seen[0].items())
                                 if k in ("format", "kind")}))

    banner("narrowed by the wish, and nothing selected")
    tally = run.do(run.Request(directory=TEST, glob_tuple=("test-a.sh one",)),
                   sink=lambda item: None)
    print("    one case : %d case(s), exit %s"
          % (tally.case_n, run.exit_code_of(tally).name))
    tally = run.do(run.Request(directory=TEST, glob_tuple=("no-such.sh",)),
                   sink=lambda item: None)
    print("    none     : empty=%s, exit %s"
          % (tally.empty_f, run.exit_code_of(tally).name))

    banner("a refusal is an outcome here too")
    try:
        run.do(run.Request(directory=os.path.join(ROOT, "nope")),
               sink=lambda item: None)
    except Refused as error:
        print("    %s" % masked(error.said))


def test_accept():
    """RETURN: None. E-105: the outcomes, and the two pages made from
               them -- the same sentences, out of a record."""
    from vut.services.accept import (Outcome, outcome_tuple_of,
                                     report_written, brief_row_of)

    class _Key:
        """A key as the page names it."""
        def __init__(self, name): self.name = name
        @property
        def test(self):   return self.name.split()[0]
        @property
        def choice(self): return None

    blessed   = [_Key("test-a.sh one .stdout")]
    undecided = [_Key("test-b.sh .stdout")]
    merge     = [_Key("test-c.sh .stdout")]
    cancelled = [_Key("test-d.sh .stdout")]
    skipped   = [_Key("test-e.sh .stdout")]
    outcome_tuple = outcome_tuple_of(".", blessed, undecided, merge,
                                     cancelled, skipped)
    banner("one outcome per key")
    for outcome in outcome_tuple:
        print("    %-12s %s" % (outcome.kind, outcome.name))
    print("    plain: %s" % (record_check(outcome_tuple[0]) or "yes"))

    banner("the report block, made from them")
    report_written(outcome_tuple, len(outcome_tuple), lambda l: print("    %s" % l))

    banner("the brief column, made from the same")
    for outcome in outcome_tuple:
        label, verdict, note = brief_row_of(outcome)
        print("    %-24s %-6s %s" % (label, verdict, note or ""))

    banner("what a caller asks: which keys need a merge")
    print("    %s" % [o.name for o in outcome_tuple if o.kind == "needs-merge"])


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "The face contract: Request, do(), Result (E-101)",
            choice_map = {
                "plain":  test_plain,
                "refuse": test_refuse,
                "accept": test_accept,
                "run":    test_run,
                "split":  test_split,
                "stream": test_stream,
                "reuse":  test_reuse,
            }).run()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)

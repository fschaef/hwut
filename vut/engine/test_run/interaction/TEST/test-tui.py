#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE TUI TIER.

    UNIT     'TuiDisplay' (tui.py) -- the terminal driver: rendering
             of the FULL compare vocabulary (every tolerance kind,
             every region kind), the two marking views (verdict /
             reading), the '$EDITOR' loop, the three answers. The
             service FACES built on this driver are tested where they
             live: services/TEST.

    CAUSAL CONTRACT
             the driver renders what DOWN carries and aligns nothing;
             an edit is answered as a REALIGN and the fresh association
             comes from compare, through the hub; the reading view is
             the stream fed against ITSELF, so only interpretation
             shows.

    CONSISTENCY CONTRACT
             an author who saved nothing is re-prompted LOCALLY -- the
             hub never sees a no-progress REALIGN from this driver; a
             CANCEL carries nothing out; what is rendered is what DOWN
             carried, and nothing else.
______________________________________________________________________________
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.test_run.interaction.feed import (E_DisplayTarget,      # noqa E402
                                                    E_Intent,
                                                    driver_for,
                                                    feed_down,
                                                    merge_session)
from   vut.engine.test_run.interaction.tui  import TuiDisplay             # noqa E402
from   vut.engine.compare.configuration     import Configuration          # noqa E402

MOCK_EDITOR = os.path.join(os.path.dirname(__file__), "mock", "mock_editor.py")


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


def _session(subject, nominal, answer_list, editor_mode=None, merge_f=True,
             compare_options=None):
    """
    RETURN: (TuiDisplay, str, str|None, E_Intent), the driver, its full
            rendering, and the session's outcome -- one TUI merge run,
            scripted end to end.
    """
    out     = io.StringIO()
    answers = iter(answer_list)

    def scripted_input(prompt):
        """RETURN: str, the next scripted answer. Raises EOFError when
        the script is exhausted -- exactly input()'s own contract."""
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    editor = None
    if editor_mode is not None:
        editor = [sys.executable, MOCK_EDITOR, editor_mode]
    driver = TuiDisplay(out=out, input_f=scripted_input,
                        color_f=False, editor_argv=editor, merge_f=merge_f)
    text, intent = asyncio.run(merge_session(compare_options,
                                             subject, nominal, driver,
                                             "tui-under-test"))
    return driver, out.getvalue(), text, intent


def test_rendering():
    """WHAT THE AUTHOR SEES: the setup banner, compare's section
    boundaries, one row per equivalent pair, an S and an N row per
    differing one, verdict marks on the differing SPAN (not on compare's
    tokens), and the provenance DOWN already carries -- where an analogy
    was first established."""
    subject = ("alpha\n"
               "value 3.14\n"
               "gamma\n"
               "id ((X9)) ready\n"
               "id ((X9)) again\n")
    nominal = ("alpha\n"
               "value 3.1\n"
               "gamma\n"
               "id ((K2)) ready\n"
               "id ((K2)) again\n")
    driver, rendering, text, intent = _session(subject, nominal, ["c"])

    print(rendering)
    ok = _check([
        (intent is E_Intent.COMMIT and text == nominal,
         "committing without an edit commits the nominal AS IS"),
        (driver.generation_n == 1,
         "no edit was made, so ONE generation crossed"),
        ("setup | numeric=exact" in rendering,
         "the compare SETUP is shown -- the rules the verdicts obey"),
        ("--[ " in rendering,
         "section boundaries are compare's, and they are shown"),
        ("[3.14]" in rendering and "[3.1]" in rendering,
         "a differing span is marked on BOTH sides"),
        ("~((X9))~" in rendering,
         "a tolerated span is marked as tolerated, not hidden"),
        ("established at S:4/N:4" in rendering,
         "analogy provenance: the FIRST binding site is named"),
    ])
    _verdict(ok, "the TUI shows what DOWN carries -- and adds nothing.")


def test_every_element_kind():
    """THE FULL ELEMENT VOCABULARY through the VERDICT view: numeric
    (tolerated AND out of tolerance), analogy (consistent AND in
    conflict, each with its provenance), equivalence pattern, visible
    nothing, constraint binding, a type difference, and the plain
    insert/delete rows. Every tolerance kind of the reading appears;
    every meta note DOWN carries is shown."""
    configuration = Configuration()
    configuration.pattern_finder.numeric_tolerance_ratio      = 0.01
    configuration.pattern_finder.equivalent_pattern_list      = \
                                                [r"v[0-9.]+-build[0-9]+"]
    configuration.pattern_finder.visible_nothing_pattern_list = ["_"]
    configuration.constraint_db = {"limit": "limit > 0"}

    subject = ("id ((X9)) opened\n"
               "id ((X9)) reused\n"
               "value 3.140\n"
               "value 9.000\n"
               "count 42 items\n"
               "version v1.2.3-build907\n"
               "filler\n"
               "((limit: 100))\n"
               "only here\n")
    nominal = ("id ((K2)) opened\n"
               "id ((ZZ)) reused\n"
               "value 3.141\n"
               "value 4.000\n"
               "count fortytwo items\n"
               "version v9.9.9-build111\n"
               "_ filler\n"
               "((limit: 100))\n"
               "only there\n")
    driver, rendering, text, intent = _session(
        subject, nominal, ["q"], compare_options=configuration)

    print(rendering)
    ok = _check([
        ("~3.140~" in rendering,
         "a numeric WITHIN tolerance is tolerated, and marked so"),
        ("numeric: off by 0.001, within the limit of 0.03141" in rendering,
         "... and the MEASUREMENT says by how much, against what"),
        ("[9.000]" in rendering and "[4.000]" in rendering,
         "a numeric OUT of tolerance is a mismatch, on both sides"),
        ("numeric: off by 5 against a limit of 0.04 (125.0x over)"
         in rendering,
         "... with the number that decides widen-the-limit vs "
         "fix-the-code"),
        ("established at S:1/N:1" in rendering,
         "the consistent analogy names its FIRST binding site"),
        ("CONFLICT: '((X9))' vs '((ZZ))'" in rendering,
         "the conflicting analogy is told as a CONFLICT ..."),
        ("binding established at S:1/N:1" in rendering,
         "... naming the site of the binding it conflicts with"),
        ("~v1.2.3-build907~" in rendering,
         "two elements matching one equivalence pattern are tolerated"),
        ("pattern: matches 'v[0-9.]+-build[0-9]+'" in rendering,
         "... and the pattern that tolerated them is NAMED"),
        ("~_~" in rendering,
         "a visible nothing pairs against NOTHING -- and is marked as "
         "the tolerance it is"),
        ("constraint binding ((limit: 100))" in rendering,
         "a constraint binding is noted -- a value entered the space"),
        ("type differs" in rendering,
         "a number-vs-word mismatch names its KIND"),
        ("S " in rendering and "N " in rendering,
         "differing pairs split into an S row and an N row"),
    ])
    _verdict(ok, "every element kind renders, with the meta DOWN carries.")


def test_every_region_kind():
    """THE FULL REGION VOCABULARY: the outer LINE_SEQUENCE and all five
    region kinds -- potpourri (unordered), table (key-matched), point-
    cloud (within limit), verbatim (exact), ignore (tolerated). Each
    section boundary is compare's, and the crossed line numbers make
    the unordered matches VISIBLE."""
    subject = ("start\n"
               "##! potpourri\n"
               "worker-2 done\n"
               "worker-1 done\n"
               "####\n"
               "##! table key=0\n"
               "1 orange 3.20\n"
               "2 apple  1.10\n"
               "####\n"
               "##! point-cloud limit=0.5\n"
               "0.10 0.20\n"
               "####\n"
               "##! verbatim\n"
               "raw   $$ exact\n"
               "####\n"
               "##! ignore\n"
               "timestamp 12:33:01\n"
               "####\n"
               "end\n")
    nominal = ("start\n"
               "##! potpourri\n"
               "worker-1 done\n"
               "worker-2 done\n"
               "####\n"
               "##! table key=0\n"
               "2 apple  1.10\n"
               "1 orange 3.20\n"
               "####\n"
               "##! point-cloud limit=0.5\n"
               "0.11 0.21\n"
               "####\n"
               "##! verbatim\n"
               "raw   $$ exact\n"
               "####\n"
               "##! ignore\n"
               "timestamp 09:00:00\n"
               "####\n"
               "end\n")
    driver, rendering, text, intent = _session(subject, nominal, ["q"])

    print(rendering)
    section_list = [line for line in rendering.splitlines()
                    if line.startswith("--[")]
    ok = _check([
        (section_list == ["--[ LINE_SEQUENCE/LINE_SEQUENCE ]--",
                          "--[ POTPOURRI/POTPOURRI ]--",
                          "--[ TABLE/TABLE ]--",
                          "--[ POINT_CLOUD/POINT_CLOUD ]--",
                          "--[ VERBATIM/VERBATIM ]--",
                          "--[ IGNORE/IGNORE ]--",
                          "--[ LINE_SEQUENCE/LINE_SEQUENCE ]--",
                          ],
         "every region kind opens its own section, in stream order"),
        ("     3    4 |" in rendering and "     4    3 |" in rendering,
         "potpourri: the crossed line numbers SHOW the unordered match"),
        ("     7    8 |" in rendering and "     8    7 |" in rendering,
         "table: rows met by KEY, not by position"),
        ("~0.10 0.20~" in rendering,
         "point-cloud: a point within the limit is tolerated"),
        ("raw   $$ exact" in rendering,
         "verbatim: carried exactly, spacing and all"),
        ("~timestamp 12:33:01~" in rendering,
         "ignore: present, shown, and entirely tolerated"),
        (driver.bad_pair_n == 0,
         "and the whole stream is EQUIVALENT under its regions"),
    ])
    _verdict(ok, "all five region kinds render under compare's framing.")


def test_reading_view():
    """THE READING made visible: one stream fed against ITSELF, marks
    by TOLERANCE KIND -- what CAN vary, under the given setup. The
    legend is part of the banner; the analogy's self-binding names the
    line where the value first bound."""
    configuration = Configuration()
    configuration.pattern_finder.numeric_tolerance_ratio      = 0.01
    configuration.pattern_finder.equivalent_pattern_list      = \
                                                [r"v[0-9.]+-build[0-9]+"]
    configuration.pattern_finder.visible_nothing_pattern_list = ["_"]

    text = ("id ((X9)) opened\n"
            "count 42 items\n"
            "version v1.2.3-build907\n"
            "_ filler\n"
            "((limit: 100))\n")

    out    = io.StringIO()
    driver = TuiDisplay(out=out, color_f=False, merge_f=False,
                        reading_f=True)
    #  THE READING is the stream fed against ITSELF -- straight through
    #  the display door; the services' reading face is just this call.
    asyncio.run(feed_down(configuration, io.StringIO(text),
                          io.StringIO(text), driver, "reading-probe"))
    rendering = out.getvalue()

    print(rendering)
    ok = _check([
        ("reading | {numeric} ~analogy~ <pattern> !binding! |nothing|"
         in rendering,
         "the legend states the marks -- it is part of the rules"),
        ("{42}" in rendering,
         "a numeric is marked as numeric -- it CAN vary"),
        ("~((X9))~" in rendering,
         "an analogy is marked as analogy"),
        ("established at S:1/N:1" in rendering,
         "and its self-binding names the FIRST occurrence"),
        ("<v1.2.3-build907>" in rendering,
         "an equivalence-pattern element is marked as pattern"),
        ("|_|" in rendering,
         "a visible nothing is marked as nothing"),
        ("!((limit: 100))!" in rendering,
         "a constraint binding is marked as binding"),
        (driver.bad_pair_n == 0,
         "self-feed: every pair equivalent BY CONSTRUCTION"),
    ])
    _verdict(ok, "the reading shows the interpretation, nothing else.")


def test_editor_loop():
    """THE LOOP THROUGH A REAL EDITOR: 'e' hands the nominal to the
    editor, the edit comes back as a REALIGN, the hub answers with a
    FRESH association, and the author commits what they now see."""
    driver, rendering, text, intent = _session(
        "alpha\nbeta\ngamma\n",
        "alpha\nBETA\ngamma\n",
        ["e", "c"], editor_mode="append")

    print("INSPECT: intent=%s generations=%i" % (intent,
                                                 driver.generation_n))
    ok = _check([
        (intent is E_Intent.COMMIT,
         "the session ends on the author's COMMIT"),
        (text is not None and
         text.endswith("appended by the mock editor\n"),
         "the committed artifact IS the edited nominal"),
        (driver.generation_n == 2,
         "the edit was answered with a SECOND generation"),
        ("round 2" in rendering,
         "and the author saw it, as round 2"),
        ("appended by the mock editor" in rendering,
         "the fresh association contains the edit"),
    ])
    _verdict(ok, "edit, realign, see it fresh, commit -- the loop.")


def test_undecided_author():
    """AN AUTHOR IS NOT A BROKEN DRIVER. Saving the nominal untouched is
    hesitation, not an answer: the TUI re-prompts LOCALLY and the hub
    never sees a no-progress REALIGN it would end the session over.
    An editor that FAILED changes nothing either. EOF on the answer
    channel is a CANCEL -- walking away stores nothing."""
    driver, rendering, text, intent = _session(
        "alpha\n", "beta\n", ["e", "q"], editor_mode="noop")

    driver2, rendering2, text2, intent2 = _session(
        "alpha\n", "beta\n", ["e", "q"], editor_mode="fail")

    driver3, rendering3, text3, intent3 = _session(
        "alpha\n", "beta\n", [])          # exhausted input -> EOFError

    print("INSPECT: noop -> %s after %i generation(s)"
          % (intent, driver.generation_n))
    print("         fail -> %s, editor's exit code told"
          % intent2)
    print("         eof  -> %s, %r" % (intent3, text3))
    ok = _check([
        ("no change -- nothing to realign" in rendering,
         "the unchanged edit is answered HERE, with a re-prompt"),
        (driver.generation_n == 1,
         "the hub never saw it: ONE generation, no REALIGN"),
        (intent is E_Intent.CANCEL and text is None,
         "the author's 'q' cancels; nothing is carried out"),
        ("editor exited with 3" in rendering2,
         "a failing editor is told, with its exit code"),
        (intent2 is E_Intent.CANCEL,
         "and the nominal stayed untouched"),
        (intent3 is E_Intent.CANCEL and text3 is None,
         "EOF on the answer channel is a CANCEL, not a crash"),
    ])
    _verdict(ok, "hesitation re-prompts; only decisions leave the TUI.")


def test_display_only():
    """DISPLAY WITHOUT MERGE: 'merge_f' False makes 'resolve' answer
    None -- one generation is rendered, no question is asked, and the
    session ends as a CANCEL carrying nothing."""
    driver, rendering, text, intent = _session(
        "alpha\nbeta\n", "alpha\nBETA\n", [], merge_f=False)

    print("INSPECT: %s, %r after %i generation(s)"
          % (intent, text, driver.generation_n))
    ok = _check([
        (intent is E_Intent.CANCEL and text is None,
         "no merge was offered, so nothing was resolved"),
        (driver.generation_n == 1,
         "exactly one generation was rendered"),
        ("differing pair" not in rendering,
         "and no question was asked"),
        ("[beta]" in rendering.lower() or "[BETA]" in rendering,
         "the comparison itself was shown"),
    ])
    _verdict(ok, "display-only renders once and resolves nothing.")


def test_target_wiring():
    """THE TIER IS A TARGET like any other: 'driver_for' builds it from
    the name, and the driver arrives configured -- adding the tier
    touched 'driver_for' and nothing else."""
    driver = driver_for(E_DisplayTarget.TUI,
                        out=io.StringIO(), color_f=False, merge_f=False)

    print("INSPECT: driver_for(TUI) -> %s" % type(driver).__name__)
    ok = _check([
        (isinstance(driver, TuiDisplay),
         "the TUI target names the TUI driver"),
        (driver.merge_f is False and driver.color_f is False,
         "and the caller's configuration reached it"),
    ])
    _verdict(ok, "a caller names an outcome; driver_for builds the tool.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The TUI tier",
        choice_map = {
            "rendering":        test_rendering,
            "elements":         test_every_element_kind,
            "regions":          test_every_region_kind,
            "reading":          test_reading_view,
            "editor_loop":      test_editor_loop,
            "undecided_author": test_undecided_author,
            "display_only":     test_display_only,
            "target_wiring":    test_target_wiring,
        },
        happy      = "SUCCESS.*",
    ).run()

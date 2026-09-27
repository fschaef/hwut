#! /usr/bin/env python3
#
# @hwut {
#     title      = "The keyed merge's editing panes: GOOD typed into, the tolerance tried."
#     choices    = ["good-type", "good-undo", "good-unchanged", "good-editor",
#                   "good-cc", "pane", "try", "fault", "from-report",
#                   "main-keys", "view"]
#     tolerance { comment = []  analogy = [] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EDITING PANES (intend 21) driven by REAL KEYS: the screen runs
         on 'prompt_toolkit''s pipe input and a dummy output, so every
         byte below passes the key bindings a terminal's would -- no
         terminal needed, and nothing drawn is recorded.

    good-type       'e', the cursor down, a character replaced, <F5>: the
                    edit becomes the nominal, and a round realigns
    good-undo       the same, undone with 'c-z' before <F5>: no round
    good-unchanged  'e' then <F5>: no round, the merge goes on
    good-editor     'e', then 'c-e': $EDITOR's exit ends the edit
    good-cc         'c-c' inside the edit means nothing; outside it cancels
    pane            <F5>: the tolerance pane as it opens -- every key, the
                    proposals below
    try             <F5>, 'c-e' uncommenting the numeric proposal: the next
                    round aligns under it (the id still differs); every
                    proposal: nothing differs. The memory differs from
                    the test's own; the lower line stands
    fault           a text the header's reader refuses keeps the pane open
                    with the fault; a readable one closes it
    from-report     <F5> while the 't' report is up opens the pane
    main-keys       'c-z'/'c-y' beside 'u'/'r' in the merge itself
    view            the viewing table: neither 'e' nor <F5> acts

'comment' and 'analogy' are OFF for this page: the pane holds '##' and
'((' as data.
______________________________________________________________________________
"""
import asyncio
import sys

from prompt_toolkit.input  import create_pipe_input
from prompt_toolkit.output import DummyOutput

from vut.services.lib.viewers.keyed.driver import KeyedDisplay
from vut.services.lib.viewers.keyed.act    import E_Act
from vut.services.lib.accept.engine        import merge_text

F5, DOWN, END, BACKSPACE = "\x1b[15~", "\x1b[B", "\x1b[F", "\x7f"
C_C, C_E, C_Y, C_Z       = "\x03", "\x05", "\x19", "\x1a"

SUBJECT = "head\ntime: 12.51 ms  id=ab12;\nb\n<hwut-end>\n"
NOMINAL = "head\ntime: 12.00 ms  id=zz7;\nc\n<hwut-end>\n"


class Watched(KeyedDisplay):
    """The keyed driver, telling what each round aligned."""
    def __init__(self, **argument_db):
        super().__init__(**argument_db)
        self.round_n = 0
    async def resolve(self, *argument_list):
        self.round_n += 1
        print("     round %i: %i pair(s) differ, numeric ratio %s"
              % (self.round_n, self.bad_pair_n, self.numeric_ratio))
        return await super().resolve(*argument_list)
    def _close_edit(self):
        super()._close_edit()
        if self.edit_fault is not None:
            print("     pane stays open: %s" % self.edit_fault)


def session(key_list, editor_argv=None):
    """RETURN: Watched, the driver after a merge of SUBJECT against
               NOMINAL driven by 'key_list' -- each sent as one chunk, as
               a terminal delivers a key; the outcome printed."""
    with create_pipe_input() as pipe:
        display = Watched(pt_input=pipe, pt_output=DummyOutput(),
                          color_f=False, editor_argv=editor_argv)
        for key in key_list: pipe.send_text(key)
        text, intent = asyncio.run(asyncio.wait_for(
                           merge_text(SUBJECT, NOMINAL, display, "t.sh one", None),
                           30))
    print("     -> %s %s" % (intent.name, None if text is None else text.split("\n")))
    print("     tolerance changed in memory: %s" % display.tolerance_changed_f())
    return display


def test_good_type():
    print("-- 'e', down, end, backspace, 'b', <F5>, 'q'")
    session(["e", DOWN, DOWN, END, BACKSPACE, "b", F5, "q"])


def test_good_undo():
    print("-- the same, 'c-z' twice before <F5>: nothing changed, no round")
    session(["e", DOWN, DOWN, END, BACKSPACE, "b", C_Z, C_Z, F5, "q"])


def test_good_unchanged():
    print("-- 'e', <F5>, 'q'")
    session(["e", F5, "q"])


def test_good_editor():
    print("-- 'e', 'c-e' under an editor replacing 'c' by 'b', 'q'")
    session(["e", C_E, "q"], editor_argv=["sed", "-i", "s/^c$/b/"])


def test_good_cc():
    print("-- 'e', 'c-c', <F5>, 'c-c'")
    session(["e", C_C, F5, C_C])


def test_pane():
    print("-- <F5>: the pane as it opens")
    display = session([F5, "\x1b[B", F5, "q"])
    print("\n   the text it showed:")
    display.editing = None
    for line in display._tolerance_pane_text().splitlines():
        print("     | %s" % line)


def test_try():
    print("-- <F5>, 'c-e' uncommenting the numeric proposal, 'q'")
    display = session([F5, C_E, "q"], editor_argv=[
                          "sed", "-i", "s/# numeric_ratio = /numeric_ratio = /"])
    print("     in memory: numeric ratio %s"
          % display.tolerance_options.pattern_finder.numeric_tolerance_ratio)
    print("\n-- <F5>, 'c-e' uncommenting every proposal, 'q'")
    display = session([F5, C_E, "q"], editor_argv=[
                          "sed", "-i", "-E",
                          "s/# (numeric_ratio|eq_pattern) = /\\1 = /"])
    print("     in memory: numeric ratio %s"
          % display.tolerance_options.pattern_finder.numeric_tolerance_ratio)


def test_fault():
    print("-- <F5>, 'c-e' writing an unknown key, 'c-e' taking it out, 'q'")
    editor = ["sh", "-c",
              "if grep -q bogus \"$0\"; then sed -i '/bogus/d' \"$0\"; "
              "else sed -i 's/^tolerance {/tolerance {\\n    bogus = 1/' \"$0\"; fi"]
    session([F5, C_E, C_E, "q"], editor_argv=editor)


def test_from_report():
    print("-- 't', <F5>: the report closes, the pane opens; <F5>, 'q'")
    display = Watched(act_script=[E_Act.REPORT, E_Act.TOLERANCE])
    display.pair_db = []
    for act in display.act_script: display._apply(act)
    print("     report up: %s, editing: %s" % (display.reporting_f, display.editing))


def test_main_keys():
    print("-- 'A' takes all; 'c-z' undoes it, 'c-y' redoes it; 'q'")
    session(["A", C_Z, C_Y, "q"])
    print("-- 'A', 'c-z', 'q'")
    session(["A", C_Z, "q"])


def test_view():
    print("-- the viewing table binds neither 'e' nor <F5>")
    from vut.services.lib.viewers.keyed import keymap
    for key in ("e", "f5", "c-e", "c-z"):
        print("     %-4s -> %s" % (key, keymap.act_of(key, keymap.VIEW_KEYMAP)))
    display = KeyedDisplay(view_only_f=True, act_script=[])
    display._apply(E_Act.EDIT_HERE)
    display._apply(E_Act.TOLERANCE)
    print("     scripted 'e' and <F5> in a view: editing = %s" % display.editing)


CHOICE_DB = {
    "good-type":      test_good_type,
    "good-undo":      test_good_undo,
    "good-unchanged": test_good_unchanged,
    "good-editor":    test_good_editor,
    "good-cc":        test_good_cc,
    "pane":           test_pane,
    "try":            test_try,
    "fault":          test_fault,
    "from-report":    test_from_report,
    "main-keys":      test_main_keys,
    "view":           test_view,
}

choice = sys.argv[1] if len(sys.argv) > 1 else "good-type"
CHOICE_DB[choice]()
print("<hwut-end>")

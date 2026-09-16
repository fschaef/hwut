#! /usr/bin/env python3
#
# @hwut {
#     title      = "The keyed merge: the laws of taking, and the keymap."
#     choices    = ["crossing", "cut", "filler", "keymap", "latch",
#                   "reindex", "split", "take", "token", "undo", "view"]
#     tolerance { regions = false }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE KEYED MERGE, laws L-1..L-12 and the keymap.

Every choice here runs with NO terminal and NO 'prompt_toolkit': the
core is a list of acts in and a state out, which is the whole reason it
was kept apart from the driver.
______________________________________________________________________________
"""
import sys

from vut.services.lib.viewers.keyed.act    import E_Act, E_Pane
from vut.services.lib.viewers.keyed.state  import MergeState
from vut.services.lib.viewers.keyed.reduce import reduce
from vut.services.lib.viewers.keyed.region import (region_list_of, region_of,
                                                   take, filler_region,
                                                   FILLER_LINE)
from vut.services.lib.viewers.keyed.project import project
import vut.services.lib.viewers.keyed.keymap as keymap


SUBJECT = ("alpha", "beta", "gamma", "<hwut-end>")
NOMINAL = ("##! unaccepted", "--?--", "--?--", "--?--", "####", "<hwut-end>")
PAIRING = {0: 1, 1: 2, 2: 3}


def fresh():
    """RETURN: MergeState, the opening state of a first acceptance --
               three subject lines against one region of three fillers.
    """
    return MergeState(subject_line_list=SUBJECT, nominal_line_list=NOMINAL,
                      pairing=dict(PAIRING))


def show(state, tag):
    """RETURN: None. Prints the nominal and what a take would touch."""
    print("  %s" % tag)
    for i, line in enumerate(state.nominal_line_list):
        print("     %2i  %s" % (i, line))
    print("     subject_range=%s target=%s derived=%s virgin=%s stale=%i"
          % (state.subject_range(), state.target_range(),
             state.derived_target(), state.virgin_f,
             state.take_n_since_realign))


def play(state, act_list):
    """RETURN: MergeState, the state after every act of 'act_list', each
               given as the act alone or as (act, argument).
    """
    for each in act_list:
        act, argument = each if isinstance(each, tuple) else (each, None)
        state = reduce(state, act, argument)
    return state


def test_split():
    print("L-2/L-3/L-4: what a take does to the framing around it")
    print("\n-- L-2 a take in the middle SPLITS the region")
    show(play(fresh(), [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE]), "took 'beta'")

    print("\n-- L-3 a take of the WHOLE region leaves no framing")
    show(play(fresh(), [E_Act.TAKE_ALL]), "took everything")

    print("\n-- P-24 a take at the region's first line yields ONE region")
    show(play(fresh(), [E_Act.TAKE_RANGE]), "took 'alpha'")

    print("\n-- P-24 a take at the region's last line yields ONE region")
    show(play(fresh(), [E_Act.MOVE_DOWN, E_Act.MOVE_DOWN, E_Act.TAKE_RANGE]),
         "took 'gamma'")

    print("\n-- L-4 a take OUTSIDE every region replaces, and creates none")
    plain = ("alpha", "beta", "gamma")
    for line in take(plain, 1, 1, ("BETA",)): print("     ", line)
    print("     regions:", region_list_of(take(plain, 1, 1, ("BETA",))))


def test_cut():
    print("No region of any other kind is ever CUT by a take")
    N = ("alpha", "##! potpourri", "p1", "p2", "p3", "####", "omega")
    print("\n     nominal:", list(N))
    for tag, first_i, last_i in (("part of the content (p2 only)", 3, 3),
                                 ("part, leaving p3 behind",        2, 3),
                                 ("straddling its '####'",          4, 6)):
        r = take(N, first_i, last_i, ("X",))
        print("     %-32s -> %s" % (tag, "REFUSED" if r is None else list(r)))
    print("\n-- the whole content: the region goes ENTIRE, markers too")
    for i, line in enumerate(take(N, 2, 4, ("X", "Y"))):
        print("     %2i  %s" % (i, line))
    print("\n-- two regions at once is refused, whatever their kinds")
    U = ("##! unaccepted", "--?--", "--?--", "####", "##! table", "t1", "####")
    print("     straddle ->", "REFUSED" if take(U, 2, 5, ("a",)) is None else "TAKEN")
    print("\n-- THE SAME LAW ON THE SUBJECT SIDE: a subject region goes")
    print("   over framed and entire, or not at all")
    S = ("alpha", "##! table", " a | b", " c | d", "####", "omega", "<hwut-end>")
    N2 = ("##! unaccepted", "--?--", "####", "##! unaccepted", "--?--", "--?--",
          "####", "##! unaccepted", "--?--", "####", "<hwut-end>")
    P2 = {0: 1, 2: 4, 3: 5, 5: 8}
    for tag, cs, anchor in (("one table row",            2, None),
                            ("both rows",                3, 2),
                            ("row 3 straddling 'omega'", 5, 3)):
        st = MergeState(subject_line_list=S, nominal_line_list=N2,
                        pairing=dict(P2), cursor_s=cs, anchor_s=anchor)
        r = reduce(st, E_Act.TAKE_RANGE)
        print("     %-26s -> %s" % (tag, "REFUSED" if r is st else "taken"))
    st = MergeState(subject_line_list=S, nominal_line_list=N2,
                    pairing=dict(P2), cursor_s=3, anchor_s=2)
    for i, line in enumerate(reduce(st, E_Act.TAKE_RANGE).nominal_line_list):
        print("     %2i  %s" % (i, line))

    print("\n     A remainder of a potpourri left trailing after a merge is")
    print("     a nominal nobody wrote and compare cannot read. Only an")
    print("     'unaccepted' region may be split, because splitting it")
    print("     is what deciding part of it MEANS.")


def test_take():
    print("L-1: the target range is replaced WHOLE, N != M allowed")
    for tag, taken in (("N < M  one line over three", ("ONE",)),
                       ("N = M  three over three",    ("A", "B", "C")),
                       ("N > M  five over three",     ("A","B","C","D","E"))):
        print("\n-- %s" % tag)
        for line in take(NOMINAL, 1, 3, taken): print("     ", line)


def test_latch():
    print("L-5/L-6/L-7: the virgin target, and when it stops tracking")
    print("\n-- L-5 while virgin the target FOLLOWS the subject cursor")
    state = fresh()
    for tag in ("at rest", "after j", "after jj"):
        print("     %-10s derived=%s" % (tag, state.derived_target()))
        state = reduce(state, E_Act.MOVE_DOWN)

    print("\n-- L-6 entry alone does NOT latch: tab, look, tab back")
    state = play(fresh(), [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.SWAP_PANE])
    print("     virgin=%s  (it must still be tracking)" % state.virgin_f)

    print("\n-- L-6 MODIFYING the target latches it")
    state = play(fresh(), [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.ANCHOR,
                           E_Act.MOVE_DOWN])
    print("     virgin=%s target=%s derived=%s"
          % (state.virgin_f, state.target_range(), state.derived_target()))

    print("\n-- L-6 and the subject then moves WITHOUT dragging it")
    state = play(state, [E_Act.SWAP_PANE, E_Act.MOVE_DOWN])
    print("     target=%s derived=%s" % (state.target_range(),
                                         state.derived_target()))

    print("\n-- L-7 after a take, virginity returns and the anchors clear")
    state = reduce(state, E_Act.TAKE_RANGE)
    print("     virgin=%s anchor_s=%s anchor_n=%s"
          % (state.virgin_f, state.anchor_s, state.anchor_n))


def test_undo():
    print("L-9/L-10: undo restores the whole state; a bulk take is ONE act")
    print("\n-- L-9 a bulk take, then one undo")
    state = fresh()
    taken = reduce(state, E_Act.TAKE_ALL)
    back  = reduce(taken, E_Act.UNDO)
    print("     nominal restored: %s" % (back.nominal_line_list == NOMINAL))
    print("     stale restored  : %i" % back.take_n_since_realign)

    print("\n-- L-9 the latch is restored too, not only the text")
    state = play(fresh(), [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.ANCHOR,
                           E_Act.MOVE_DOWN])
    print("     before take: virgin=%s" % state.virgin_f)
    print("     after undo : virgin=%s"
          % reduce(reduce(state, E_Act.TAKE_RANGE), E_Act.UNDO).virgin_f)

    print("\n-- L-10 every take raises the stale count; 'r' zeroes it")
    state = play(fresh(), [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    print("     after one take : %i" % state.take_n_since_realign)
    print("     after realign  : %i"
          % reduce(state, E_Act.REALIGN).take_n_since_realign)

    print("\n-- undo with nothing done is not an error")
    print("     same state back: %s" % (reduce(fresh(), E_Act.UNDO)
                                        == fresh()))


def test_reindex():
    print("L-12: the local re-index, and what it refuses to invent")
    state = play(fresh(), [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    print("\n-- where each subject line now stands")
    for i_s in sorted(state.pairing):
        i_n = state.pairing[i_s]
        print("     subject %i %-8r -> nominal %-4s %r"
              % (i_s, SUBJECT[i_s], i_n,
                 state.nominal_line_list[i_n] if i_n is not None else None))
    print("\n     It shifts what is below by N-M and pairs the taken")
    print("     stretch 1:1. A tolerance, a numeric within its limit, an")
    print("     analogy binding -- only compare knows those, and they go")
    print("     STALE. That is what the banner's count is for.")


def test_token():
    print("L-11: the closing token is takeable, and it ENDS the nominal")
    state = fresh()
    print("     token at %i, last reachable %i"
          % (state.token_i_s(), state.last_reachable_s()))
    walked = play(state, [E_Act.MOVE_DOWN] * 10)
    print("     after ten 'j': cursor_s=%i" % walked.cursor_s)

    def taken(tag, subject, nominal, pairing, act_list):
        """RETURN: None. One take, and the nominal it leaves."""
        state = play(MergeState(subject_line_list=subject,
                                nominal_line_list=nominal,
                                pairing=pairing), act_list)
        print("\n-- %s" % tag)
        for i, line in enumerate(state.nominal_line_list):
            print("     %2i  %s" % (i, line))
        print("     spent %s" % sorted(state.copied_s))

    taken("the token alone, DERIVED target: it lands on its partner, the\n"
          "   nominal's token, so nothing follows and nothing is cut",
          ("alpha", "<hwut-end>"),
          ("alpha", "stale 1", "stale 2", "<hwut-end>"),
          {0: 0, 1: 3},
          [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    taken("the token alone, AIMED at 'stale 1': everything from there goes",
          ("alpha", "<hwut-end>"),
          ("alpha", "stale 1", "stale 2", "<hwut-end>"),
          {0: 0, 1: 3},
          [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.ANCHOR, E_Act.SWAP_PANE,
           E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    taken("a range ENDING in the token, AIMED at 'old'",
          ("alpha", "beta", "<hwut-end>"),
          ("alpha", "old", "tail", "<hwut-end>"),
          {0: 0, 1: None, 2: 3},
          [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.ANCHOR, E_Act.SWAP_PANE,
           E_Act.MOVE_DOWN, E_Act.ANCHOR, E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    taken("'gamma' and the token, the target AIMED inside the region:\n"
          "   the region's rest goes, what stands above it stays framed",
          SUBJECT, NOMINAL, {**PAIRING, 3: 5},
          [E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.MOVE_DOWN, E_Act.ANCHOR,
           E_Act.SWAP_PANE, E_Act.MOVE_DOWN, E_Act.MOVE_DOWN, E_Act.ANCHOR,
           E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    taken("TAKE_ALL: one token, and it is spent too",
          SUBJECT, NOMINAL, {**PAIRING, 3: 5}, [E_Act.TAKE_ALL])
    taken("an AIMED take onto the nominal's own token stops above it",
          ("f", "<hwut-end>"), ("<hwut-end>",), {0: None, 1: 0},
          [E_Act.SWAP_PANE, E_Act.ANCHOR, E_Act.SWAP_PANE, E_Act.TAKE_RANGE])
    taken("an AIMED take onto a region's label stays out of the markers",
          ("a", "<hwut-end>"),
          ("##! unaccepted", "--?--", "####", "<hwut-end>"), {0: 1, 1: 3},
          [E_Act.SWAP_PANE, E_Act.ANCHOR, E_Act.SWAP_PANE, E_Act.TAKE_RANGE])


def test_filler():
    print("P-2: one filler per subject line, and what the filler is")
    for line_n in (0, 1, 3):
        print("     %i subject line(s) -> %s" % (line_n, filler_region(line_n)))
    print("\n     filler = %r" % FILLER_LINE)
    print("     It is significant CONTENT, so a filler against a subject")
    print("     line is a REAL difference -- which is what 'nobody has")
    print("     judged this' must look like. Anything of the '##'..'##'")
    print("     family would read as VISIBLE_NOTHING and the region would")
    print("     compare EQUIVALENT: a first acceptance that PASSES.")


def test_keymap():
    print("P-20/P-21/P-22: the table is the keymap")
    print("\n-- the help screen IS the table")
    for line in keymap.help_line_list(): print("     %s" % line)
    print("\n-- no key is bound twice")
    print("     keyed   : %s" % (keymap.duplicate_key_list() or "none"))
    print("     fallback: %s"
          % (keymap.duplicate_key_list(keymap.FALLBACK_KEYMAP) or "none"))
    print("\n-- the fallback speaks the SAME acts")
    for key_tuple, act, _, _ in keymap.FALLBACK_KEYMAP:
        print("     %-4s -> %s" % (key_tuple[0], act.name))
    print("\n-- an unbound key means nothing, and that is not an error")
    print("     act_of('Z') = %s" % keymap.act_of("Z"))


def test_crossing():
    print("A subject line is drawn ONCE, and a take is paired where it stands")

    def rows_of(state):
        """RETURN: None. The two panes as the screen lays them out, and
                   the check that no subject line appears twice."""
        index_list = []
        for row in project(state):
            s, n = row.subject, row.nominal
            if s.index >= 0: index_list.append(s.index)
            print("     %2s %-12s | %2s %s"
                  % (s.index if s.index >= 0 else "", s.text,
                     n.index if n.index >= 0 else "", n.text))
        print("     subject rows %s -- each once: %s"
              % (index_list, index_list == sorted(set(index_list))))

    print("\n-- an unpaired line taken beside an EARLIER identical line")
    print("   'c' is inserted at the seam below 'b'; the 'c' above it is")
    print("   the nominal's own and must not be mistaken for the take")
    state = MergeState(
        subject_line_list=("f", "b", "d", "c", "<hwut-end>"),
        nominal_line_list=("d", "d", "b", "f", "c", "b", "<hwut-end>"),
        pairing={0: 3, 1: 5, 2: None, 3: None, 4: 6})
    state = play(state, [E_Act.MOVE_DOWN] * 3 + [E_Act.TAKE_RANGE])
    print("     pairing %s" % dict(sorted(state.pairing.items())))
    rows_of(state)

    print("\n-- an AIMED take above the partner of an earlier line")
    print("   'beta' goes to nominal 0; 'alpha' is still paired below it.")
    print("   The crossing pair cannot stand side by side: its nominal")
    print("   line stands alone until 'r'")
    state = MergeState(
        subject_line_list=("alpha", "beta", "<hwut-end>"),
        nominal_line_list=("zeta", "alpha", "<hwut-end>"),
        pairing={0: 1, 1: None, 2: 2})
    state = play(state, [E_Act.MOVE_DOWN, E_Act.SWAP_PANE, E_Act.ANCHOR,
                         E_Act.SWAP_PANE, E_Act.TAKE_RANGE])
    print("     pairing %s" % dict(sorted(state.pairing.items())))
    rows_of(state)


def test_view():
    print("E-79: the screen for LOOKING -- 'hwut.diff'")
    import asyncio
    from types import SimpleNamespace
    from vut.services.lib.viewers.keyed.driver import KeyedDisplay

    print("\n-- the viewing table: nothing that changes the nominal")
    for line in keymap.help_line_list(keymap.VIEW_KEYMAP):
        print("     %s" % line)

    print("\n-- a take, an undo, a commit: ignored; 'q' ends the view")
    display = KeyedDisplay(view_only_f=True,
                           act_script=[E_Act.TAKE_ALL, E_Act.MOVE_DOWN,
                                       E_Act.UNDO, E_Act.COMMIT,
                                       E_Act.CANCEL, E_Act.MOVE_DOWN])
    relation = lambda name: SimpleNamespace(name=name)
    pair = SimpleNamespace(line_n_s=1, line_n_n=1,
                           cells_s=(SimpleNamespace(relation_id=relation("SUBSTITUTE"),
                                                    tolerance_id=relation("STRING"),
                                                    subject="alpha"),),
                           cells_n=(SimpleNamespace(relation_id=relation("SUBSTITUTE"),
                                                    tolerance_id=relation("STRING"),
                                                    nominal="omega"),))

    async def session():
        """RETURN: None. One delivery, then the view."""
        await display.open("x")
        await display.present(pair)
        await display.close()
        await display.view("x", "alpha\nbeta\n", "omega\nbeta\n")
    asyncio.run(session())
    print("     nominal        %s" % (display.state.nominal_line_list,))
    print("     spent          %s" % sorted(display.state.copied_s))
    print("     cursor_s       %i  (one move before 'q', none after)"
          % display.state.cursor_s)
    print("     left by        %s" % display.leaving_act.name)
    print("     differing      %i" % display.bad_pair_n)
    print("     banner         %s" % display._banner())


CHOICE_DB = {
    "view":     test_view,
    "crossing": test_crossing,
    "split":   test_split,
    "take":    test_take,
    "cut":     test_cut,
    "latch":   test_latch,
    "undo":    test_undo,
    "reindex": test_reindex,
    "token":   test_token,
    "filler":  test_filler,
    "keymap":  test_keymap,
}

choice = sys.argv[1] if len(sys.argv) > 1 else "split"
CHOICE_DB[choice]()
print("<hwut-end>")

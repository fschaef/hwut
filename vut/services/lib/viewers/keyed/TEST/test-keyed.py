#! /usr/bin/env python3
#
# @hwut {
#     title      = "The keyed merge: the laws of taking, and the keymap."
#     choices    = ["crossing", "cut", "element", "filler", "header",
#                   "keymap", "latch", "merge-colour", "reindex", "remove",
#                   "report", "split", "take", "token", "undo", "view"]
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

    print("\n-- L-10 every take raises the stale count; 'g' zeroes it")
    state = play(fresh(), [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    print("     after one take : %i" % state.take_n_since_realign)
    print("     after realign  : %i"
          % reduce(state, E_Act.REALIGN).take_n_since_realign)

    print("\n-- undo with nothing done is not an error")
    print("     same state back: %s" % (reduce(fresh(), E_Act.UNDO)
                                        == fresh()))

    print("\n-- E-89 redo: what undo took back, 'r' does again")
    one = play(fresh(), [E_Act.TAKE_RANGE])
    two = play(one, [E_Act.MOVE_DOWN, E_Act.TAKE_RANGE])
    step = lambda st, *act_list: play(st, list(act_list)).nominal_line_list
    print("     three states differ   : %s"
          % (len({fresh().nominal_line_list, one.nominal_line_list,
                  two.nominal_line_list}) == 3))
    print("     undo                  -> one  : %s"
          % (step(two, E_Act.UNDO) == one.nominal_line_list))
    print("     undo redo             -> two  : %s"
          % (step(two, E_Act.UNDO, E_Act.REDO) == two.nominal_line_list))
    print("     undo undo redo redo   -> two  : %s"
          % (step(two, E_Act.UNDO, E_Act.UNDO, E_Act.REDO, E_Act.REDO)
             == two.nominal_line_list))
    print("     redo with nothing undone: same state: %s"
          % (reduce(two, E_Act.REDO) == two))
    print("\n-- E-89 a new act after undo forks history: no redo past it")
    forked = play(two, [E_Act.UNDO, E_Act.MOVE_DOWN, E_Act.TAKE_ALL])
    print("     redo after a new act: same state: %s"
          % (reduce(forked, E_Act.REDO) == forked))
    print("\n-- E-89 'R' resets to the opening state, and nothing is redoable")
    print("     reset -> opening      : %s"
          % (step(two, E_Act.RESET) == fresh().nominal_line_list))
    print("     redo after reset      : same state: %s"
          % (reduce(reduce(two, E_Act.RESET), E_Act.REDO)
             == reduce(two, E_Act.RESET)))
    print("     undo after reset      : same state: %s"
          % (reduce(reduce(two, E_Act.RESET), E_Act.UNDO)
             == reduce(two, E_Act.RESET)))


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
    print("   line stands alone until 'g'")
    state = MergeState(
        subject_line_list=("alpha", "beta", "<hwut-end>"),
        nominal_line_list=("zeta", "alpha", "<hwut-end>"),
        pairing={0: 1, 1: None, 2: 2})
    state = play(state, [E_Act.MOVE_DOWN, E_Act.SWAP_PANE, E_Act.ANCHOR,
                         E_Act.SWAP_PANE, E_Act.TAKE_RANGE])
    print("     pairing %s" % dict(sorted(state.pairing.items())))
    rows_of(state)


def test_remove():
    print("E-86: 'd' removes from GOOD -- lines, or a whole region")

    def removed(tag, nominal, act_list, pairing=None, copied_s=frozenset()):
        """RETURN: None. One removal, and what GOOD is left holding."""
        state = MergeState(subject_line_list=("alpha", "beta", "<hwut-end>"),
                           nominal_line_list=nominal,
                           pairing=pairing or {},
                           copied_s=copied_s)
        after = play(state, act_list)
        print("\n-- %s" % tag)
        for i, line in enumerate(after.nominal_line_list):
            print("     %2i  %s" % (i, line))
        print("     cursor_n=%i spent=%s stale=%i undo->%s"
              % (after.cursor_n, sorted(after.copied_s),
                 after.take_n_since_realign,
                 play(after, [E_Act.UNDO]).nominal_line_list == nominal))

    region = ("x", "##! unaccepted", "--?--", "--?--", "####", "y",
              "<hwut-end>")
    to_nominal = [E_Act.SWAP_PANE]
    removed("the cursor INSIDE an unaccepted region: the region, whole",
            region, to_nominal + [E_Act.MOVE_DOWN, E_Act.MOVE_DOWN,
                                  E_Act.REMOVE])
    removed("the cursor ON its '##! unaccepted' line: the same",
            region, to_nominal + [E_Act.MOVE_DOWN, E_Act.REMOVE])
    removed("the cursor ON its '####': the same",
            region, to_nominal + [E_Act.MOVE_DOWN] * 4 + [E_Act.REMOVE])
    removed("a plain line: that line",
            region, to_nominal + [E_Act.REMOVE])
    removed("a marked line INSIDE the region: the region shrinks",
            ("##! unaccepted", "--?--", "--?--", "--?--", "####",
             "<hwut-end>"),
            to_nominal + [E_Act.MOVE_DOWN, E_Act.MOVE_DOWN, E_Act.ANCHOR,
                          E_Act.REMOVE])
    removed("a marked range across a plain line and the region's start:\n"
            "   'x' and the filler go, the region keeps its other filler",
            region, to_nominal + [E_Act.ANCHOR, E_Act.MOVE_DOWN,
                                  E_Act.MOVE_DOWN, E_Act.REMOVE])
    removed("a marked range across ALL of the region's content: the\n"
            "   region goes, markers included",
            region, to_nominal + [E_Act.MOVE_DOWN, E_Act.MOVE_DOWN,
                                  E_Act.ANCHOR, E_Act.MOVE_DOWN,
                                  E_Act.REMOVE])
    removed("a potpourri is removed whole or not at all: part refused",
            ("##! potpourri", "p", "q", "####", "<hwut-end>"),
            to_nominal + [E_Act.MOVE_DOWN, E_Act.ANCHOR, E_Act.REMOVE])
    removed("GOOD holding only its token: nothing goes",
            ("<hwut-end>",), to_nominal + [E_Act.REMOVE])
    removed("the subject pane: 'd' does nothing there",
            region, [E_Act.REMOVE])
    removed("a COPY removed: its subject line is takeable again",
            ("alpha", "beta", "<hwut-end>"),
            to_nominal + [E_Act.REMOVE],
            pairing={0: 0, 1: 1, 2: 2}, copied_s=frozenset({0}))


def test_header():
    print("E-90: no header line; the keys at the foot, the name in OUTPUT's title")
    from vut.services.lib.viewers.keyed.project import banner, pane_title
    state = MergeState(subject_line_list=("a", "<hwut-end>"),
                       nominal_line_list=("b", "<hwut-end>"))
    print("\n-- the bottom bar: <F1>=help at the left, whole hints right-aligned")
    for width in (None, 100, 86, 80, 70, 50, 30, 15):
        print("     %-4s |%s|" % (width, banner(state, "", width=width)))
    print("\n-- the keys come from the table")
    print("     merge: %s" % keymap.basic_text())
    print("     view : %s" % keymap.basic_text(keymap.VIEW_BASIC_TUPLE,
                                               keymap.VIEW_KEYMAP))
    print("\n-- the titles: 'OUTPUT of <test> <choice>' and 'GOOD', the driven one marked")
    for pane in (E_Pane.SUBJECT, E_Pane.NOMINAL):
        print("     driving %-8s |%s|%s|" % (pane.name,
              pane_title(state.with_(pane=pane), E_Pane.SUBJECT, "test-app.sh one"),
              pane_title(state.with_(pane=pane), E_Pane.NOMINAL, "test-app.sh one")))


def test_merge_colour():
    """RETURN: None. E-94: both panes, and the cursor line, are split
               into element fragments under real colour -- the cursor's
               reverse and an element's pen stand together."""
    import asyncio
    from vut.services.lib.viewers.keyed.driver import KeyedDisplay
    from vut.services.lib.viewers.keyed.project import project
    from vut.services.lib.accept import engine
    from vut.engine.compare.api import Configuration
    display = KeyedDisplay(act_script=[E_Act.CANCEL], color_f=None)
    display.plain_f = False
    asyncio.run(engine.merge_text("value 3.14 ((a))\n<hwut-end>\n",
                                  "value 3.15 ((b))\n<hwut-end>\n",
                                  display, "t.sh one", Configuration()))
    display.state = display.state.with_(cursor_s=0)
    for pane in (E_Pane.SUBJECT, E_Pane.NOMINAL):
        for row in project(display.state):
            cell = row.subject if pane is E_Pane.SUBJECT else row.nominal
            if cell.index != 0: continue
            frag = display._pieces_of(cell, pane)
            kinds = [s.split("el.")[-1].split()[0] for s, _ in frag if "el." in s]
            cursor = all("cursor.active" in s for s, _ in frag) \
                     if pane is E_Pane.SUBJECT else True
            print("     %-8s elements: %s%s" % (pane.name, kinds,
                  "  (all under the cursor)" if pane is E_Pane.SUBJECT
                  and cursor else ""))


def test_element():
    print("E-87: the line elements on the screen, and the status bar")
    from types import SimpleNamespace as N
    from vut.services.lib.viewers.keyed import element
    from vut.services.lib.viewers.keyed.driver import _expanded
    kind = lambda name: N(name=name)

    def cell(side, tolerance, text, relation="OK_GOOD", ref=None):
        """RETURN: a cell as compare bakes one."""
        return N(tolerance_id=kind(tolerance), relation_id=kind(relation),
                 subject_ref_i=ref, **{side: text})

    subject = [cell("subject", "STRING", "indented"),
               cell("subject", "SEPERATOR", "\t"),
               cell("subject", "NUMERIC", "3.14", "BAD_NOMINAL_DIFFERS"),
               cell("subject", "SEPERATOR", " "),
               cell("subject", "ANALOGY", "((x))")]
    nominal = [cell("nominal", "STRING", "indented", ref=0),
               cell("nominal", "SEPERATOR", "\t", ref=1),
               cell("nominal", "NUMERIC", "3.15", "BAD_NOMINAL_DIFFERS", ref=2),
               cell("nominal", "SEPERATOR", " ", ref=3),
               cell("nominal", "ANALOGY", "((y))", ref=4)]
    s_piece = element.pieces_of_cells(subject, "subject", nominal)
    n_piece = element.pieces_of_cells(nominal, "nominal", subject)

    print("\n-- compare drops the leading blanks; the pieces are PLACED")
    line = "  indented\t3.14 ((x))"
    print("     key  %r" % element.key_of(line))
    for piece in element.placed(line, s_piece):
        print("     %-10s %-8r differs=%-5s partner=%r"
              % (piece.kind, piece.text, piece.differs_f, piece.partner))
    print("     a piece out of order: %s"
          % element.placed("3.14 indented", s_piece))

    print("\n-- where the element cursor stops")
    placed = element.placed(line, s_piece)
    print("     %s" % [(i, placed[i].text)
                       for i in element.meta_index_list(placed)])

    print("\n-- the status bar, on the line and on each stop")
    print("     line      : %s" % element.line_status(placed))
    print("     plain line: %r" % element.line_status(
        element.placed("plain", [element.Piece("STRING", "plain",
                                                False, None)])))
    for ratio in (0, 0.01):
        for i in element.meta_index_list(placed):
            print("     S r=%-4g: %s" % (ratio, element.status_of(
                placed[i], "subject", ratio)))
        n_placed = element.placed("indented\t3.15 ((y))", n_piece)
        print("     N r=%-4g: %s" % (ratio, element.status_of(
            n_placed[2], "nominal", ratio)))
    for kind_name, text in (("EQUIVALENCE_PATTERN", "0x1f"),
                            ("CONSTRAINT_BINDING", "<id>"),
                            ("VISIBLE_NOTHING", "")):
        print("     %-19s: %s" % (kind_name, element.status_of(
            element.Piece(kind_name, text, False, None), "subject", 0)))
    print("     no partner    : %s" % element.status_of(
        element.Piece("NUMERIC", "7", False, None), "subject", 0.05))

    print("\n-- a tab is drawn as blanks, from where the piece starts")
    for column, text in ((0, "\t"), (2, "\t"), (7, "\tx"), (8, "\t"),
                         (3, "no tab")):
        print("     column %i %-9r -> %r" % (column, text,
                                              _expanded(text, column)))


def test_report():
    print("E-91: the tolerance report, line numbers, <number>g, counts")
    from types import SimpleNamespace as N
    from vut.services.lib.viewers.keyed import report
    from vut.services.lib.viewers.keyed.driver import KeyedDisplay
    from vut.services.lib.viewers.keyed.project import pane_title
    kind = lambda name: N(name=name)
    origin = N(line_n_in_subject=2, line_n_in_nominal=2)
    def cs(t, kind_name, rel="OK_GOOD"):
        return N(tolerance_id=kind(kind_name), relation_id=kind(rel), subject=t)
    def cn(t, kind_name, ref, rel="OK_GOOD", org=None):
        return N(tolerance_id=kind(kind_name), relation_id=kind(rel), nominal=t,
                 subject_ref_i=ref, analogy_origin_line_number_pair=org)
    pair_list = [
        report.Pair(2, 2, [cs("((a))", "ANALOGY")],
                    [cn("((x))", "ANALOGY", 0, org=origin)]),
        report.Pair(5, 4, [cs("((a))", "ANALOGY", "BAD_NOMINAL_DIFFERS")],
                    [cn("((y))", "ANALOGY", 0, "BAD_NOMINAL_DIFFERS", origin)]),
        report.Pair(7, 6, [cs("0x1f", "EQUIVALENCE_PATTERN")],
                    [cn("0X1F", "EQUIVALENCE_PATTERN", 0)]),
        report.Pair(8, 7, [cs("same", "EQUIVALENCE_PATTERN")],
                    [cn("same", "EQUIVALENCE_PATTERN", 0)]),
        report.Pair(9, 8, [cs("<id>", "CONSTRAINT_BINDING", "BAD_NOMINAL_DIFFERS")],
                    [cn("<other>", "CONSTRAINT_BINDING", 0, "BAD_NOMINAL_DIFFERS")]),
    ]
    print("\n-- the report, three sections")
    for line in report.lines_of(pair_list): print("     %s" % line)
    print("   (a pattern matching identical text is not listed)")
    print("\n-- the scroll cursor rests on element rows, never headings")
    from vut.services.lib.viewers.keyed.driver import KeyedDisplay
    from vut.services.lib.viewers.keyed.act import E_Act as _A
    disp = KeyedDisplay(act_script=[], color_f=False)
    disp.pair_db = pair_list
    disp._apply(_A.REPORT)
    seen = [disp.report_row]
    for _ in range(6):
        disp._apply(_A.MOVE_DOWN); seen.append(disp.report_row)
    lines = report.lines_of(pair_list)
    print("     rows visited: %s" % seen)
    print("     all name a line pair: %s"
          % all(report.line_pair_at(lines, r) is not None for r in seen))

    print("\n-- <enter> on a report row names its line pair; headings name none")
    line_list = report.lines_of(pair_list)
    for row in range(len(line_list)):
        pair = report.line_pair_at(line_list, row)
        if pair is not None: print("     row %2i -> %s" % (row, pair))
    print("\n-- with nothing to report")
    for line in report.lines_of([]): print("     %s" % line)

    print("\n-- <number>g: the cursor to that line; a spent line sends it on")
    display = KeyedDisplay(act_script=[], color_f=False)
    display.state = MergeState(subject_line_list=SUBJECT, nominal_line_list=NOMINAL,
                               pairing=PAIRING, copied_s=frozenset({1}))
    for line_n in ("1", "2", "99", "x"):
        display._apply(E_Act.GOTO, line_n)
        print("     %-3s -> cursor_s=%i" % (line_n, display.state.cursor_s))
    display.state = display.state.with_(pane=E_Pane.NOMINAL)
    display._apply(E_Act.GOTO, "4")
    print("     GOOD 4 -> cursor_n=%i" % display.state.cursor_n)

    print("\n-- the count in GOOD's title: unpaired and differing OUTPUT lines,")
    print("   spent ones not counted")
    display.state = MergeState(subject_line_list=("a", "b", "c", "<hwut-end>"),
                               nominal_line_list=("a", "c", "<hwut-end>"),
                               pairing={0: 0, 1: None, 2: 1, 3: 2})
    print("     %s" % pane_title(display.state, E_Pane.NOMINAL, "", display._differ_n()))
    display.state = display.state.with_(copied_s=frozenset({1}))
    print("     %s" % pane_title(display.state, E_Pane.NOMINAL, "", display._differ_n()))
    print("     %s" % pane_title(display.state, E_Pane.SUBJECT, "t.sh one", 0))


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
                                       E_Act.UNDO, E_Act.DONE,
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
    print("     hints          %s" % display._hints())


CHOICE_DB = {
    "report":   test_report,
    "element":  test_element,
    "merge-colour":  test_merge_colour,
    "remove":   test_remove,
    "header":   test_header,
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

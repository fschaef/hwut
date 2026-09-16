"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: reduce(state, act) -> state. THE ONE PLACE an act becomes a
         consequence.

DESCRIPTION
       AN ACT THAT CANNOT APPLY IS NOT AN ERROR. A move at the last
       line, a take with nothing marked -- the same state comes back and
       nothing is said. It is a keystroke that changed nothing, which is
       what an author expects of an editor. Anything that must be
       refused LOUDLY is therefore a law of shape, not a complaint: a
       spent line is unreachable because no act can move a cursor onto
       it, not because a take is told off for aiming there.

       THE LAWS, each pinned by its own choice in TEST:

       L-1  a take replaces the target range WHOLE; N != M is legal
       L-2  a take inside a region SPLITS it around what was taken
       L-3  a region emptied by a take is REMOVED, framing and all
       L-4  a take outside every region replaces, and creates none
       L-5  while virgin, the target is DERIVED and follows the subject
       L-6  virginity falls only when the target range's first or last
            line differs from the derived one -- entry alone never
       L-7  after a take, virginity returns and both anchors clear
       L-8  TAKE_REGION reaches one region; TAKE_ALL reaches everything
       L-9  UNDO restores the whole state, latch included; a bulk take
            is ONE entry
       L-10 every take raises the stale count; REALIGN zeroes it
       L-11 THE CLOSING TOKEN IS TAKEABLE, AND IT ENDS THE NOMINAL
            (services E-77, retracting 'no act reaches it'): a take
            whose range holds the subject's token cuts the nominal right
            after the taken lines -- whatever followed is gone
       L-12 the local re-index shifts what is below by N-M and pairs the
            taken stretch 1:1 -- it invents no tolerance and no analogy
       L-13 A COPIED SUBJECT SECTION IS SPENT. No cursor stands on one,
            no range intersects one, no take covers one again. It is
            unreachable -- a place, not a refusal shouted at a
            keystroke.
______________________________________________________________________________
"""
from vut.services.lib.viewers.keyed.act    import E_Act, E_Pane
from vut.services.lib.viewers.keyed.state  import MergeState
from vut.services.lib.viewers.keyed.region import (take_placed as region_take_placed,
                                                   region_list_of, region_of)
from vut.engine.compare.reading.line_scanner import REGION_END_LINE

PAGE_LINE_N = 20


def reduce(state, act, argument=None):
    """RETURN: MergeState, the state after 'act' -- a NEW object, with
               'state' left untouched.

               'state' itself, where the act cannot apply: a move at the
               last line, a take with no lines to take. That is not an
               error and says nothing; it is a keystroke that changed
               nothing.

    'argument' carries the search term for SEARCH_UP and SEARCH_DOWN,
    and is None for every other act.
    """
    handler = _HANDLER_DB.get(act)
    if handler is None: return state
    return handler(state, argument)


#  ---------------------------------------------------------------- the cursor

def _moved(state, delta_n):
    """RETURN: MergeState, the state with the ACTIVE pane's cursor moved
               by 'delta_n', clamped to what a cursor may reach.

               'state', where the cursor is already at that end.

    Moving the SUBJECT cursor while the target is virgin is what makes
    the target follow (L-5): the target is derived, so it needs no
    updating -- it is computed from the cursor that just moved.

    A COPIED LINE IS STEPPED OVER (L-13), in the direction of travel;
    where every line that way is spent, nothing moves.
    """
    if state.pane is E_Pane.SUBJECT:
        wanted = _clamped(state.cursor_s + delta_n, state.last_reachable_s())
        wanted = state.reachable_s(wanted, +1 if delta_n >= 0 else -1)
        if wanted is None or wanted == state.cursor_s: return state
        return state.with_(cursor_s=wanted)

    wanted = _clamped(state.cursor_n + delta_n, state.last_reachable_n())
    if wanted == state.cursor_n: return state
    return _latched_if_moved(state.with_(cursor_n=wanted), state)


def _clamped(i, last_i):
    """RETURN: int, 'i' brought inside 0..'last_i'."""
    return max(0, min(i, last_i))


def _latched_if_moved(new_state, old_state):
    """RETURN: MergeState, 'new_state' with virginity cleared where the
               target range it now yields differs, at its first or last
               line, from the range the alignment derives (L-6).

               'new_state' unchanged where the two still agree: entering
               the nominal pane and looking about costs nothing.
    """
    if not new_state.virgin_f: return new_state

    marked = new_state.marked_nominal_range()
    if marked is None:                       return new_state
    if marked == new_state.derived_target(): return new_state
    return new_state.with_(virgin_f=False)


def _swap_pane(state, _):
    """RETURN: MergeState, the state with the other pane active.

    SWAP_PANE ALONE NEVER CLEARS VIRGINITY (L-6). Tab in, look, Tab out
    and the target is still tracking.
    """
    return state.with_(pane=state.pane.other())


def _anchor(state, _):
    """RETURN: MergeState, the state with a range anchored at the active
               pane's cursor -- or with that anchor dropped, where one
               already stood there.
    """
    if state.pane is E_Pane.SUBJECT:
        wanted = None if state.anchor_s == state.cursor_s else state.cursor_s
        return state.with_(anchor_s=wanted)

    wanted = None if state.anchor_n == state.cursor_n else state.cursor_n
    return _latched_if_moved(state.with_(anchor_n=wanted), state)


def _search(state, term, downward_f):
    """RETURN: MergeState, the state with the active pane's cursor on the
               next line containing 'term', searched in the given
               direction and wrapping at neither end.

               'state', where 'term' is empty or stands nowhere ahead.
    """
    if not term: return state
    if state.pane is E_Pane.SUBJECT:
        line_list, cursor, last_i = (state.subject_line_list,
                                     state.cursor_s, state.last_reachable_s())
    else:
        line_list, cursor, last_i = (state.nominal_line_list,
                                     state.cursor_n, state.last_reachable_n())

    step_list = range(cursor+1, last_i+1) if downward_f else range(cursor-1, -1, -1)
    for i in step_list:
        if term not in line_list[i]:
            continue
        if state.pane is E_Pane.SUBJECT:
            if state.copied_f(i): continue      # spent -- L-13
            return state.with_(cursor_s=i)
        return _latched_if_moved(state.with_(cursor_n=i), state)
    return state


#  ----------------------------------------------------------------- the takes

def _take_range(state, _):
    """RETURN: MergeState, the state after the marked subject range was
               taken into the target range -- the nominal rebuilt, the
               region split around what was taken, the pairing
               re-indexed, virginity restored and both anchors cleared.

               'state', where the marked subject range is empty.
    """
    first_s, last_s = state.subject_range()
    widened = _subject_range_whole(state, first_s, last_s)
    if widened is None: return state
    first_s, last_s = widened

    taken = state.subject_line_list[first_s:last_s+1]
    if not taken: return state

    target = state.target_range()
    if target is None:
        seam_i = state.insertion_seam()
        first_n, last_n = seam_i, seam_i - 1      # replaces nothing
    else:
        first_n, last_n = target
        #  THE NOMINAL'S OWN TOKEN IS NEVER REPLACED by an ordinary take:
        #  a target reaching it stops above it, and one holding nothing
        #  else becomes an insertion there. Measured: with the token the
        #  nominal's only line, the nominal cursor stands on it, and an
        #  aimed take replaced it -- a nominal that never COMPLETED.
        token_i_n = state.token_i_n()
        if token_i_n is not None and last_n >= token_i_n:
            last_n = token_i_n - 1
            if first_n > token_i_n: first_n = token_i_n

    if state.token_i_s() is not None and first_s <= state.token_i_s() <= last_s:
        return _applied_to_end(state, first_n, taken, first_s, last_s)
    return _applied(state, first_n, last_n, taken, first_s, last_s)


def _take_region(state, _):
    """RETURN: MergeState, the state after the region under the nominal
               cursor was taken whole from its associated subject lines.

               'state', where the nominal cursor stands in no region.
    """
    region = state.region_at_cursor()
    if region is None: return state

    first_n, last_n = region.content_range()
    first_s, last_s = _subject_span_of(state, first_n, last_n)
    if first_s is None: return state
    widened = _subject_range_whole(state, first_s, last_s)
    if widened is None: return state
    first_s, last_s = widened

    taken = state.subject_line_list[first_s:last_s+1]
    return _applied(state, first_n, last_n, taken, first_s, last_s)


def _take_all(state, _):
    """RETURN: MergeState, the state after the complete subject was taken
               over the complete nominal -- leaving no region standing,
               the closing token where it was, and EVERY subject line
               spent (L-13), the token among them: after TAKE_ALL
               nothing is selectable, which is the law and not a jam.
    """
    last_s = state.last_reachable_s()
    taken  = state.subject_line_list[:last_s+1]

    fresh = state.pushed().with_(nominal_line_list=tuple(taken),
                                 copied_s=frozenset(range(last_s+1)),
                                 anchor_s=None, anchor_n=None,
                                 virgin_f=True,
                                 take_n_since_realign=state.take_n_since_realign+1)
    return _reindexed(fresh, identity_f=True)


def _applied(state, first_n, last_n, taken, first_s, last_s):
    """RETURN: MergeState, the state with 'taken' put in place of the
               nominal lines 'first_n'..'last_n' -- the region split, the
               stale count raised, the latch reset, the pairing
               re-indexed by the local rule (L-12), the taken subject
               lines recorded as SPENT and the cursor carried off them
               (L-13).
    """
    placed = region_take_placed(state.nominal_line_list,
                                first_n, last_n, taken)
    if placed is None:
        #  The take would CUT a region of another kind. Refused: the
        #  same state comes back, and nothing is said -- a keystroke
        #  that changed nothing, as every inapplicable act is.
        return state
    nominal_line_list, begin_n = placed

    delta_n = len(nominal_line_list) - len(state.nominal_line_list)
    pairing = _pairing_shifted(state.pairing, first_s, last_s,
                               first_n, last_n, delta_n, begin_n)

    spent = state.copied_s | frozenset(range(first_s, last_s+1))
    fresh = state.pushed().with_(nominal_line_list=nominal_line_list,
                                 pairing=pairing,
                                 copied_s=spent,
                                 anchor_s=None, anchor_n=None,
                                 virgin_f=True,
                                 take_n_since_realign=state.take_n_since_realign+1)
    return _cursor_off_spent(fresh)


def _applied_to_end(state, first_n, taken, first_s, last_s):
    """RETURN: MergeState, the state after 'taken' -- which ends in the
               closing token -- was put in at 'first_n' and the nominal
               CUT right after it (L-11): whatever followed, the old
               token included, is gone.

               'state', where the take is refused as '_applied' refuses.

    THE TAKE ITSELF IS THE ORDINARY ONE; only the cut is new. A seam
    that falls ON a region's closing rule moves past it, so the region
    keeps its rule. A seam INSIDE a region replaces that region's rest,
    so the lines above it are framed as any split frames them. Then
    everything after the taken lines is dropped, and nothing can be
    left open: what followed the seam is exactly what is removed.
    """
    line_list = state.nominal_line_list
    if first_n < len(line_list) and line_list[first_n].strip() == REGION_END_LINE:
        first_n += 1
    region = region_of(region_list_of(line_list), first_n)
    last_n = region.content_range()[1] if region is not None else first_n - 1

    placed = region_take_placed(line_list, first_n, last_n, taken)
    if placed is None: return state
    whole_list, begin_n = placed
    nominal_line_list   = whole_list[:begin_n + len(taken)]

    pairing = _pairing_shifted(state.pairing, first_s, last_s,
                               first_n, len(line_list) - 1, 0, begin_n)
    spent = state.copied_s | frozenset(range(first_s, last_s+1))
    fresh = state.pushed().with_(nominal_line_list=nominal_line_list,
                                 pairing=pairing,
                                 copied_s=spent,
                                 anchor_s=None, anchor_n=None,
                                 virgin_f=True,
                                 take_n_since_realign=state.take_n_since_realign+1)
    return _cursor_off_spent(fresh)


def _cursor_off_spent(state):
    """
    RETURN: MergeState, 'state' with the subject cursor moved to the
            first line below it that is not spent -- or, where every
            line below is spent, to the first above.

            'state' unchanged, where the cursor already stands on a line
            a cursor may stand on, and where NO line is left at all: a
            fully spent subject leaves the cursor where it was, and no
            act it can reach does anything.
    """
    wanted = state.reachable_s(state.cursor_s, +1)
    if wanted is None: wanted = state.reachable_s(state.cursor_s, -1)
    if wanted is None or wanted == state.cursor_s: return state
    return state.with_(cursor_s=wanted)


def _pairing_shifted(pairing, first_s, last_s, first_n, last_n, delta_n,
                     begin_n):
    """RETURN: dict, the pairing after a take -- every partner below the
               taken stretch shifted by 'delta_n', and the taken subject
               lines paired 1:1 with where they now stand: 'begin_n' and
               the lines after it.

    IT INVENTS NOTHING. A tolerance, a numeric within its limit, an
    analogy binding -- only compare knows those, and they go STALE here.
    The banner says how stale, and 'r' asks compare again.
    """
    result = {}
    for i_s, i_n in pairing.items():
        if first_s <= i_s <= last_s:            continue
        if i_n is None:                         result[i_s] = None
        elif i_n > last_n:                      result[i_s] = i_n + delta_n
        elif i_n < first_n:                     result[i_s] = i_n
        else:                                   result[i_s] = None

    for offset, i_s in enumerate(range(first_s, last_s+1)):
        result[i_s] = begin_n + offset
    return result


def _subject_range_whole(state, first_s, last_s):
    """RETURN: (int, int), the subject range widened to take any region
               it touches ENTIRE -- '##! table' and '####' included, so
               the nominal receives the region framed as the test
               printed it.

               None, where the range INTERSECTS a section already copied
               (L-13), or would CUT a subject region -- cover part of a
               table's rows, or straddle its closing rule -- or touch
               two regions at once. Such a take is refused:
               raw rows copied without their framing are a nominal
               nobody wrote and compare cannot read.

    The SAME LAW AS THE NOMINAL SIDE, read off the subject's own text
    by the same scanner; no chunk list has to be threaded in from the
    face, because the text is already here.
    """
    if any(state.copied_f(i) for i in range(first_s, last_s+1)): return None

    touched_list = [r for r in region_list_of(state.subject_line_list)
                    if r.touches_f(first_s, last_s)]
    if len(touched_list) > 1: return None
    for region in touched_list:
        if not region.covers_content_f(first_s, last_s): return None
        first_s = min(first_s, region.begin_i)
        last_s  = max(last_s,  region.end_i)
    return (first_s, last_s)


def _subject_span_of(state, first_n, last_n):
    """RETURN: (int, int), the subject lines the pairing puts opposite the
               nominal lines 'first_n'..'last_n'.

               (None, None), where the pairing puts none there.
    """
    i_s_list = [i_s for i_s, i_n in state.pairing.items()
                if i_n is not None and first_n <= i_n <= last_n]
    if not i_s_list: return (None, None)
    return (min(i_s_list), max(i_s_list))


def _reindexed(state, identity_f):
    """RETURN: MergeState, the state with its pairing rebuilt 1:1 -- used
               where the nominal has just been made a copy of the
               subject, so every line stands against its own.
    """
    if not identity_f: return state
    last_s = state.last_reachable_s()
    return state.with_(pairing={i: i for i in range(last_s+1)})


#  ---------------------------------------------------------------- the rest

def _undo(state, _):
    """RETURN: MergeState, the state as it stood before the last act that
               changed anything -- the latch included, so undo-then-redo
               yields what the original did (L-9).

               'state', where nothing has been done yet.
    """
    if not state.undo_stack: return state
    return state.undo_stack[-1]


def _realign(state, _):
    """RETURN: MergeState, the state with its stale count zeroed.

    The RE-ALIGNMENT itself is the hub's: the driver answers REALIGN and
    compare re-aligns. The session never calls compare's door.
    """
    if not state.take_n_since_realign: return state
    return state.with_(take_n_since_realign=0)


_HANDLER_DB = {
    E_Act.MOVE_UP:      lambda s, a: _moved(s, -1),
    E_Act.MOVE_DOWN:    lambda s, a: _moved(s, +1),
    E_Act.PAGE_UP:      lambda s, a: _moved(s, -PAGE_LINE_N),
    E_Act.PAGE_DOWN:    lambda s, a: _moved(s, +PAGE_LINE_N),
    E_Act.SWAP_PANE:    _swap_pane,
    E_Act.ANCHOR:       _anchor,
    E_Act.TAKE_RANGE:   _take_range,
    E_Act.TAKE_REGION:  _take_region,
    E_Act.TAKE_ALL:     _take_all,
    E_Act.SEARCH_DOWN:  lambda s, a: _search(s, a, True),
    E_Act.SEARCH_UP:    lambda s, a: _search(s, a, False),
    E_Act.REALIGN:      _realign,
    E_Act.UNDO:         _undo,
}

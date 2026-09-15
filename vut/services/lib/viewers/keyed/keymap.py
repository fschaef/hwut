"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: KEY -> ACT. One table, and the only place a keystroke becomes a
         meaning.

DESCRIPTION
       'prompt_toolkit's own idiom buries a meaning in a decorator body:

           @kb.add("j")
           def _(event): ...

       Thirty of those are a keymap that exists NOWHERE -- it cannot be
       printed, cannot be checked for a key bound twice, and cannot be
       rebound without editing code. So the table stands here and the
       KeyBindings object is GENERATED from it. A help screen is then a
       loop over the table rather than prose that goes stale.

       THE FALLBACK'S TABLE LIVES HERE TOO. Where 'prompt_toolkit' will
       not import, today's line-based session answers 't'/'e'/'c'/'q' --
       the same acts, a different table, one vocabulary.
______________________________________________________________________________
"""
from vut.services.lib.viewers.keyed.act import E_Act


#  THE KEYED TABLE. Each row: the keys that mean it, the act, whether
#  Tab governs it, and what to tell a person who asks. 'prompt_toolkit'
#  key names are used verbatim ('c-d' is Ctrl-D, 'escape' is Esc).
#
#  HELP IS 'f1', NOT '?'. '?' is SEARCH_UP and has been since the table
#  was written; the banner said '?=help' and was measured to be a lie --
#  '?' opened the search line. The banner now names the key the table
#  binds, which is the only way the two cannot drift.
#
#  TAB IS A MODE SWITCH FOR A SUBSET OF THIS TABLE. The rows marked PANE
#  act on whichever pane Tab last selected -- the cursor moves, the
#  anchor, the search. The rows marked BOTH mean the same thing in
#  either pane: a take is a take, undo is undo. Only the PANE rows are
#  ever read differently, and the reducer is where that reading lives.
PANE, BOTH = "pane", "both"

KEYMAP = (
    (("enter",),        E_Act.TAKE_RANGE,   BOTH, "take the marked range"),
    (("a",),            E_Act.TAKE_REGION,  BOTH, "take this region"),
    (("A",),            E_Act.TAKE_ALL,     BOTH, "take the whole subject"),
    ((" ",),            E_Act.ANCHOR,       PANE, "mark a range here"),
    (("tab",),          E_Act.SWAP_PANE,    BOTH, "the other pane"),
    (("j", "down"),     E_Act.MOVE_DOWN,    PANE, "down"),
    (("k", "up"),       E_Act.MOVE_UP,      PANE, "up"),
    (("c-d",),          E_Act.PAGE_DOWN,    PANE, "a screen down"),
    (("c-u",),          E_Act.PAGE_UP,      PANE, "a screen up"),
    (("h", "left"),     E_Act.SCROLL_LEFT,  PANE, "scroll left"),
    (("l", "right"),    E_Act.SCROLL_RIGHT, PANE, "scroll right"),
    (("/",),            E_Act.SEARCH_DOWN,  PANE, "search down"),
    (("?",),            E_Act.SEARCH_UP,    PANE, "search up"),
    (("f1",),           E_Act.HELP,         BOTH, "this table"),
    (("r",),            E_Act.REALIGN,      BOTH, "re-align: ask compare again"),
    (("u",),            E_Act.UNDO,         BOTH, "undo"),
    (("e",),            E_Act.EDIT,         BOTH, "edit the nominal in $EDITOR"),
    (("c",),            E_Act.COMMIT,       BOTH, "commit the nominal as it stands"),
    (("q",),            E_Act.CANCEL,       BOTH, "cancel"),
)

#  THE LINE-BASED FALLBACK'S TABLE. The same acts, reached by answering a
#  prompt instead of pressing a key.
FALLBACK_KEYMAP = (
    (("t",),            E_Act.TAKE_ALL,     BOTH, "take the subject whole"),
    (("e",),            E_Act.EDIT,         BOTH, "edit the nominal in $EDITOR"),
    (("c",),            E_Act.COMMIT,       BOTH, "commit the nominal as it stands"),
    (("q",),            E_Act.CANCEL,       BOTH, "cancel"),
)


def act_of(key, keymap=KEYMAP):
    """RETURN: E_Act, what 'key' means under 'keymap'.

               None, where the table binds it to nothing: an unbound key
               is not an error, it is a keystroke that means nothing.
    """
    for key_tuple, act, _, _ in keymap:
        if key in key_tuple: return act
    return None


def key_list_of(act, keymap=KEYMAP):
    """RETURN: tuple[str], every key bound to 'act', in table order.

               An empty tuple, where no key is bound to it.
    """
    for key_tuple, each, _, _ in keymap:
        if each is act: return tuple(key_tuple)
    return ()


def help_line_list(keymap=KEYMAP):
    """RETURN: tuple[str], one line per row -- the keys, then what they
               do. A help screen is this, not prose that goes stale.
    """
    return tuple("%-14s %-5s %s" % (", ".join(_named(k) for k in key_tuple),
                                     scope, description)
                 for key_tuple, _, scope, description in keymap)


def _named(key):
    """RETURN: str, the key as a person would write it -- 'space' for
               the one key whose own text is invisible.
    """
    return "space" if key == " " else key


def pane_governed_f(act, keymap=KEYMAP):
    """RETURN: bool, True where Tab governs 'act' -- it reads the pane
               last selected and acts on that side only.

               False where it means the same in either pane, and where
               the table does not know it at all.
    """
    for _, each, scope, _ in keymap:
        if each is act: return scope == PANE
    return False


def duplicate_key_list(keymap=KEYMAP):
    """RETURN: tuple[str], every key the table binds MORE THAN ONCE.

               An empty tuple where the table is sound, which is what
               the suite asserts: a key bound twice is a meaning nobody
               can predict.
    """
    seen, result = set(), []
    for key_tuple, _, _, _ in keymap:
        for key in key_tuple:
            if key in seen and key not in result: result.append(key)
            seen.add(key)
    return tuple(result)


def key_bindings(act_f, keymap=KEYMAP):
    """RETURN: KeyBindings, 'prompt_toolkit's binding object built by
               walking the table -- every key of every row bound to a
               handler calling 'act_f' with that row's act.

               None, where 'prompt_toolkit' will not import: the caller
               then falls back to the line-based session, and a merge is
               never hard-failed for a missing import.
    """
    try:
        from prompt_toolkit.key_binding import KeyBindings
    except ImportError:
        return None

    result = KeyBindings()
    for key_tuple, act, _, _ in keymap:
        #  ONE 'add' PER KEY. 'add("j", "down")' would bind the CHORD
        #  'j' then 'down', not either key -- measured: nothing moved.
        for key in key_tuple:
            result.add(key)(_handler(act_f, act))
    return result


def _handler(act_f, act):
    """RETURN: callable, the binding handler that reports 'act' -- and
               nothing else. No meaning lives in the body.
    """
    def handle(event): act_f(act)
    return handle

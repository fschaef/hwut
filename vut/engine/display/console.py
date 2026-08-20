"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONSOLE'S OWN VOCABULARY (D-7) -- the tier flags, the
         colour flags, the gates and the width policy, in ONE place.
         A face states the user's words; this module decides what the
         console makes of them and hands back a view.

THREE KINDS OF WORD, THREE PARSERS, each owned by whoever understands
it:

    selection   the wish          'plan/wish.py'      parse_wish()
    execution   --jobs --no-store  the face itself
    rendering   the tier, colour   THIS module        parse_rendering()

A face never decides how something looks; this module never decides
what runs. 'parse_rendering()' mirrors 'parse_wish()' exactly: it takes
the words, yields what it understood and what it did not touch, and
raises where the words cannot want anything. The face turns the raise
into REFUSED, by name, with the usage line.

WHAT THE FACE STILL OWNS: whether its stdout is a terminal. The face
knows its own sink ('write' given, or 'print'); this module knows what
a terminal is worth.
______________________________________________________________________________
"""
from dataclasses import dataclass

from .plain import CPlainFlow, E_Tier
from .word  import CInk, colour_decision


class RenderingError(Exception):
    """The rendering words cannot want anything."""


#  The flag as the user spells it -> the tier it names.
TIER_FLAG_DB = {"-v":        E_Tier.VERBOSE,
                "--verbose": E_Tier.VERBOSE,
                "--quiet":   E_Tier.QUIET,
                "--silent":  E_Tier.SILENT}

#  '--plain' names the default; it is statable, so a script can pin
#  the rendering even where the default moves later (D-4).
PLAIN_FLAG = "--plain"

COLOUR_FLAG    = "--colour"
NO_COLOUR_FLAG = "--no-colour"

DEFAULT_WIDTH = 78
MINIMUM_WIDTH = 40


@dataclass(slots=True)
class CRenderingWish:
    """What the words said about rendering: which tier, and whether
    colour was enforced or refused."""
    tier:    E_Tier = E_Tier.PLAIN
    force_f: bool   = False
    veto_f:  bool   = False


def parse_rendering(argument_list):
    """
    RETURN: [0] CRenderingWish, the tier and the colour enforcement
                the words asked for; the defaults where they said
                nothing.
            [1] list, the words this module did not touch, in order.

    Raises 'RenderingError' where the words cannot want anything: two
    tiers at once, '--plain' beside another tier, or '--colour' beside
    '--no-colour'.
    """
    tier_flag_list = []
    plain_f        = False
    force_f        = False
    veto_f         = False
    rest_list      = []
    for argument in argument_list:
        if   argument in TIER_FLAG_DB:      tier_flag_list.append(argument)
        elif argument == PLAIN_FLAG:        plain_f = True
        elif argument == COLOUR_FLAG:       force_f = True
        elif argument == NO_COLOUR_FLAG:    veto_f  = True
        else:                               rest_list.append(argument)

    if len(set(TIER_FLAG_DB[flag] for flag in tier_flag_list)) > 1:
        raise RenderingError("choose one of -v/--verbose, --quiet, "
                             "--silent")
    if plain_f and tier_flag_list:
        raise RenderingError("'--plain' beside '%s' can want nothing"
                             % tier_flag_list[0])
    if force_f and veto_f:
        raise RenderingError("'--colour' beside '--no-colour' can want "
                             "nothing")

    tier = TIER_FLAG_DB[tier_flag_list[0]] if tier_flag_list \
           else E_Tier.PLAIN
    return CRenderingWish(tier=tier, force_f=force_f, veto_f=veto_f), \
           rest_list


def console_width(environ, tty_f):
    """
    RETURN: int, the width the dotted fill aims at: the terminal's
            COLUMNS where one listens and states it, never below
            MINIMUM_WIDTH; DEFAULT_WIDTH otherwise -- a piped or
            captured report is 78 wide, deterministically.
    """
    if tty_f and environ.get("COLUMNS", "").isdigit():
        return max(int(environ["COLUMNS"]), MINIMUM_WIDTH)
    return DEFAULT_WIDTH


def console_view(rendering_wish, write, write_error, environ, tty_f):
    """
    RETURN: CPlainFlow, the console view the words asked for -- tier,
            ink and width already decided.

    The colour decision is taken HERE, once, and handed to the view as
    a constructed pen; no line re-sniffs (D-2).
    """
    ink = CInk(colour_decision(environ, tty_f,
                               force_f=rendering_wish.force_f,
                               veto_f=rendering_wish.veto_f))
    return CPlainFlow(write, write_error,
                      width=console_width(environ, tty_f),
                      ink=ink, tier=rendering_wish.tier)
